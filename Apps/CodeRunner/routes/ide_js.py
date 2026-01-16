from .. import coderun_bp
from flask import render_template

@coderun_bp.route("/ide-js")
def JSIDE():
  return render_template("simpleide_js.html")
  