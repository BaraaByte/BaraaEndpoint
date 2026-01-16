from flask import Blueprint, jsonify

coderun_bp = Blueprint("coderun_bp", __name__)

@coderun_bp.route("/", methods=["GET"])
def index():
  return jsonify({
    "status": "Beta",
    "Notes": "This app in Beta, Do not use it as Primary App",
    "routes":{
      "/run": "Run Code and return output (Run Only Python and Beta)",
      "/ide": "Simple IDE that can test the API (Only Python)"
    }
  })
  
from  .routes import ide_py, pythonrun, jsrun, ide_js