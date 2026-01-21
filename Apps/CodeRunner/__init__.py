from flask import Blueprint, jsonify

coderun_bp = Blueprint("coderun_bp", __name__)

@coderun_bp.route("/", methods=["GET"])
def index():
  return jsonify({
    "status": "Stable",
    "routes":{
      "/run-py": "Run Python Code and return output",
      "/js_run": "Run JavaScript Code and return output",
      "/ide-py": "Simple IDE that can test the Python API",
      "/ide-js": "Simple IDE that can test the JavaScript	 API",
    }
  })
  
from  .routes import ide_py, pythonrun, jsrun, ide_js