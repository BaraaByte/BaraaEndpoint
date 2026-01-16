from .. import coderun_bp
import ast
import sys
import io
import signal
from flask import request, jsonify


# =============================
# CONFIG
# =============================
EXEC_TIMEOUT = 10          # seconds
MAX_INPUT_CALLS = 10
MAX_OUTPUT_SIZE = 10_000   # chars

# =============================
# TIMEOUT HANDLER
# =============================
class TimeoutError(Exception):
    pass

def timeout_handler(signum, frame):
    raise TimeoutError("Execution time exceeded")

# =============================
# SAFE INPUT
# =============================
def make_safe_input(inputs):
    calls = {"count": 0}

    def safe_input(prompt=None):
        calls["count"] += 1

        if calls["count"] > MAX_INPUT_CALLS:
            raise RuntimeError("Too many input() calls")

        if not inputs:
            raise RuntimeError("No more input provided")

        return str(inputs.pop(0))

    return safe_input

# =============================
# AST SECURITY CHECK
# =============================
DISALLOWED_NODES = (
    ast.Import,
    ast.ImportFrom,
    ast.Global,
    ast.Nonlocal,
    ast.With,
    ast.Raise,
    ast.Lambda,
)

DISALLOWED_NAMES = {
    "__import__", "eval", "exec", "open", "compile",
    "globals", "locals", "vars", "dir",
    "help", "exit", "quit"
}

def validate_ast(tree):
    for node in ast.walk(tree):
        if isinstance(node, DISALLOWED_NODES):
            raise ValueError(f"Disallowed syntax: {type(node).__name__}")

        if isinstance(node, ast.Name):
            if node.id in DISALLOWED_NAMES:
                raise ValueError(f"Disallowed name: {node.id}")

# =============================
# ROUTE
# =============================
@coderun_bp.route("/run-py", methods=["POST"])
def run_code():
    data = request.get_json(silent=True)

    if not data or "code" not in data:
        return jsonify({
            "Status": False,
            "Message": "Missing 'code' field"
        }), 400

    code = data["code"]

    if not isinstance(code, str) or not code.strip():
        return jsonify({
            "Status": False,
            "Message": "Code must be a non-empty string"
        }), 400

    user_inputs = data.get("input", [])
    if not isinstance(user_inputs, list):
        return jsonify({
            "Status": False,
            "Message": "`input` must be a list"
        }), 400

    # =============================
    # PARSE & VALIDATE
    # =============================
    try:
        tree = ast.parse(code, mode="exec")
        validate_ast(tree)
    except Exception as e:
        return jsonify({
            "Status": False,
            "Message": f"Invalid code: {e}"
        }), 400

    # =============================
    # SAFE BUILTINS
    # =============================
    safe_input = make_safe_input(user_inputs.copy())

    SAFE_BUILTINS = {
        "print": print,
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
        "input": safe_input,
        "__build_class__": __build_class__,
        "__name__": __name__,
        "object": object,
        "isinstance": isinstance,
        "Exception": Exception,
    	"ValueError": ValueError,
    }

    # =============================
    # EXECUTION
    # =============================
    stdout = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = stdout

    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(EXEC_TIMEOUT)

    try:
        exec(
            compile(tree, "<user_code>", "exec"),
            {"__builtins__": SAFE_BUILTINS},
            {}
        )
    except TimeoutError:
        return jsonify({
            "Status": False,
            "Message": "Execution timed out"
        }), 408
    except Exception as e:
        return jsonify({
            "Status": False,
            "Message": str(e)
        }), 400
    finally:
        signal.alarm(0)
        sys.stdout = old_stdout

    output = stdout.getvalue()

    if len(output) > MAX_OUTPUT_SIZE:
        return jsonify({
            "Status": False,
            "Message": "Output too large"
        }), 413

    return jsonify({
        "Status": True,
        "Output": output
    })
