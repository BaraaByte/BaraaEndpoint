from .. import coderun_bp
from flask import request, jsonify
import subprocess
import tempfile
import os
import sys
import json

# =============================
# CONFIG
# =============================
EXEC_TIMEOUT = 10
MAX_OUTPUT_SIZE = 10_000
MAX_MEMORY_MB = 128

@coderun_bp.route("/run_js", methods=["POST"])
def run_js():
    data = request.get_json(silent=True)
    if not data or "code" not in data:
        return jsonify({"Status": False, "Message": "Missing 'code' field"}), 400

    code = data.get("code", "")
    user_inputs = data.get("input", [])

    # The wrapper is the 'security guard' for the V8 Isolate
    wrapper_code = f"""
const ivm = require('/home/ayero/public_html/Apps/CodeRunner/routes/node_modules/isolated-vm');
const isolate = new ivm.Isolate({{ memoryLimit: {MAX_MEMORY_MB} }});
const context = isolate.createContextSync();
const jail = context.global;

const inputs = {json.dumps(user_inputs)};
let inputIdx = 0;

// Mapping internal sandbox 'log' to the real process stdout
jail.setSync('log', new ivm.Reference((...args) => {{
    process.stdout.write(args.join(' ') + '\\n');
}}));

jail.setSync('input', new ivm.Reference(() => {{
    return inputs[inputIdx++];
}}));

try {{
    const script = isolate.compileScriptSync(`
        const console = {{ log: (...args) => log.applySync(undefined, args) }};
        const input = () => input.applySync(undefined, []);
        {code}
    `);
    script.runSync(context, {{ timeout: {EXEC_TIMEOUT * 1000} }});
}} catch (e) {{
    // If it's a timeout, we send a specific string for the parent to catch
    if (e.message === 'Script execution timed out.') {{
        process.stderr.write('ISOLATE_TIMEOUT');
    }} else {{
        process.stderr.write(e.stack || e.toString());
    }}
    process.exit(1);
}}
"""

    with tempfile.NamedTemporaryFile("w+", suffix=".js", delete=False) as f:
        f.write(wrapper_code)
        temp_path = f.name

    # =============================
    # PARENT MONITORING LOOP
    # =============================
    output_buffer = []
    current_size = 0
    output_exceeded = False
    runtime_error_msg = "Runtime Error"

    # Start Node process
    proc = subprocess.Popen(
        ["node", temp_path],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, # Keep stderr separate for error parsing
        text=True,
        bufsize=1
    )

    try:
        # 1. Read stdout for user output
        # Using a simple read loop to monitor size
        while True:
            char = proc.stdout.read(1)
            if not char: break
            current_size += 1
            if current_size > MAX_OUTPUT_SIZE:
                output_exceeded = True
                proc.kill()
                break
            output_buffer.append(char)
        
        # 2. Capture stderr and return code
        stdout_rem, stderr_data = proc.communicate(timeout=2)
        
        if "ISOLATE_TIMEOUT" in stderr_data:
            return jsonify({"Status": False, "Message": "Execution timed out"}), 408
        
        if stderr_data:
            runtime_error_msg = stderr_data.strip()

    except subprocess.TimeoutExpired:
        proc.kill()
        return jsonify({"Status": False, "Message": "Execution timed out"}), 408
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)

    final_output = "".join(output_buffer)

    # =============================
    # FINAL API RESPONSE
    # =============================
    if output_exceeded:
        return jsonify({
            "Status": False, 
            "Message": "Output limit exceeded",
            "Output": final_output + "\n[KILLED: MAX OUTPUT REACHED]"
        }), 413

    if proc.returncode != 0:
        return jsonify({
            "Status": False,
            "Message": "Runtime Error",
            "Output": runtime_error_msg
        }), 400

    return jsonify({
        "Status": True,
        "Output": final_output
    })