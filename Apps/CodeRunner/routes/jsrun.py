from .. import coderun_bp
from flask import request, jsonify
import subprocess
import tempfile
import os
import json

EXEC_TIMEOUT = 5
MAX_OUTPUT_SIZE = 10_000

@coderun_bp.route("/run_js", methods=["POST"])
def run_js():
    data = request.get_json(silent=True)
    if not data or "code" not in data:
        return jsonify({"Status": False, "Message": "Missing 'code' field"}), 400

    code = data["code"]
    if not isinstance(code, str) or not code.strip():
        return jsonify({"Status": False, "Message": "Code must be a non-empty string"}), 400

    user_inputs = data.get("input", [])
    if not isinstance(user_inputs, list):
        return jsonify({"Status": False, "Message": "`input` must be a list"}), 400

    # Prepare JS with sandbox and fake input
    inputs_json = json.dumps(user_inputs)
    full_code = f"""
const {{ NodeVM }} = require('/home/qynix/public_html/Apps/CodeRunner/routes/node_modules/vm2');

const __inputs = {inputs_json};
let __input_index = 0;

function input(promptText) {{
    const val = __inputs[__input_index++];
    if (val === undefined) throw new Error("No more input provided");
    return val;
}}

const vm = new NodeVM({{
    console: 'redirect',
    sandbox: {{ input }},
    timeout: {EXEC_TIMEOUT * 1000},
    require: {{ external: false, builtin: [] }}
}});

vm.on('console.log', (...args) => {{
    process.stdout.write(args.join(' ') + '\\n');
}});

vm.run(`{code}`);
"""

    with tempfile.NamedTemporaryFile("w+", suffix=".js", delete=False) as f:
        f.write(full_code)
        temp_path = f.name

    try:
        result = subprocess.run(
            ["node", temp_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=EXEC_TIMEOUT + 1,
            text=True
        )
    except subprocess.TimeoutExpired:
        os.unlink(temp_path)
        return jsonify({"Status": False, "Message": "Execution timed out"}), 408
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)

    output = result.stdout + result.stderr
    if len(output) > MAX_OUTPUT_SIZE:
        output = output[:MAX_OUTPUT_SIZE] + "\n[Output truncated]"

    return jsonify({"Status": True, "Output": output})
