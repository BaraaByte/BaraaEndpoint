from .. import coderun_bp
import ast
import sys
import subprocess
import json
import tempfile
import os
import resource
from flask import request, jsonify
import builtins

# =============================
# CONFIG
# =============================
EXEC_TIMEOUT = 10               # seconds
MAX_OUTPUT_SIZE = 10_000        # characters
MAX_MEMORY_MB = 128             # megabytes

# =============================
# SAFE MODULES & AST CHECKS
# =============================
SAFE_MODULES = {"math", "datetime", "random", "itertools", "functools", "string", "statistics"}

DISALLOWED_NODES = (ast.Global, ast.Nonlocal, ast.With, ast.Raise)
DISALLOWED_NAMES = {"__import__", "eval", "exec", "open", "compile", "globals", "locals", "vars", "dir", "quit"}

def validate_ast(tree):
    for node in ast.walk(tree):
        # Block dangerous imports
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] not in SAFE_MODULES:
                    raise ValueError(f"Import of '{alias.name}' is not allowed")
        elif isinstance(node, ast.ImportFrom):
            if node.module.split(".")[0] not in SAFE_MODULES:
                raise ValueError(f"Import from '{node.module}' is not allowed")
        # Block dangerous names
        elif isinstance(node, ast.Name) and node.id in DISALLOWED_NAMES:
            raise ValueError(f"Disallowed name: {node.id}")
        # Block other dangerous nodes
        elif isinstance(node, DISALLOWED_NODES):
            raise ValueError(f"Disallowed syntax: {type(node).__name__}")

# =============================
# SAFE __import__ INJECTION
# =============================
original_import = builtins.__import__

def safe_import(name, globals=None, locals=None, fromlist=(), level=0):
    if name.split(".")[0] not in SAFE_MODULES:
        raise ImportError(f"Import of '{name}' is not allowed")
    return original_import(name, globals, locals, fromlist, level)

# =============================
# ROUTE
# =============================
@coderun_bp.route("/run-py", methods=["POST"])
def run_code():
    data = request.get_json(silent=True)
    if not data or "code" not in data:
        return jsonify({"Status": False, "Message": "Missing 'code' field"}), 400

    code = data.get("code", "")
    user_inputs = data.get("input", [])

    try:
        tree = ast.parse(code, mode="exec")
        validate_ast(tree)
    except Exception as e:
        return jsonify({"Status": False, "Message": f"Invalid code: {e}"}), 400

    # =============================
    # WORKER SCRIPT GENERATION
    # =============================
    worker_script = f"""
import sys
import json
import resource
import builtins

# OS-level protection
mem_limit = {MAX_MEMORY_MB} * 1024 * 1024
resource.setrlimit(resource.RLIMIT_AS, (mem_limit, mem_limit))
resource.setrlimit(resource.RLIMIT_CPU, ({EXEC_TIMEOUT}, {EXEC_TIMEOUT}))

inputs = {json.dumps(user_inputs)}
def safe_input(prompt=None):
    if not inputs: raise EOFError("No more input")
    return str(inputs.pop(0))

# ===== SAFE BUILTINS WITH SAFE IMPORT =====
original_import = builtins.__import__

def safe_import(name, globals=None, locals=None, fromlist=(), level=0):
    allowed_modules = {list(SAFE_MODULES)}
    if name.split('.')[0] not in allowed_modules:
        raise ImportError(f"Import of '{{name}}' is not allowed")
    return original_import(name, globals, locals, fromlist, level)

safe_builtins = {{
    "print": print,
    "input": safe_input,
    "range": range,
    "len": len,
    "int": int,
    "float": float,
    "str": str,
    "bool": bool,
    "abs": abs,
    "min": min,
    "max": max,
    "sum": sum,
    "list": list,
    "dict": dict,
    "tuple": tuple,
    "set": set,
    "help": help,
    "__import__": safe_import
}}

try:
    exec({repr(code)}, {{"__builtins__": safe_builtins}}, {{}})
except Exception as e:
    import traceback
    sys.stderr.write(traceback.format_exc())
"""

    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write(worker_script)
        temp_path = f.name

    # =============================
    # PARENT-SIDE MONITORING
    # =============================
    output_buffer = []
    current_size = 0
    output_exceeded = False
    
    proc = subprocess.Popen(
        [sys.executable, temp_path],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )

    try:
        # Stream output and enforce size limit
        for line in proc.stdout:
            current_size += len(line)
            if current_size > MAX_OUTPUT_SIZE:
                output_exceeded = True
                proc.kill()
                break
            output_buffer.append(line)
        
        proc.wait(timeout=EXEC_TIMEOUT)
    except subprocess.TimeoutExpired:
        proc.kill()
        return jsonify({"Status": False, "Message": "Execution timed out"}), 408
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)

    final_output = "".join(output_buffer)

    # =============================
    # OUTPUT HANDLING
    # =============================
    if output_exceeded:
        return jsonify({
            "Status": False,
            "Message": "Output limit exceeded",
            "Output": final_output + "\n[KILLED: MAX OUTPUT REACHED]"
        }), 413

    if proc.returncode != 0 and not output_exceeded:
        return jsonify({
            "Status": False,
            "Message": "Runtime Error",
            "Output": final_output
        }), 400

    return jsonify({
        "Status": True,
        "Output": final_output
    })
