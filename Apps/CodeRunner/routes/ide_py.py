from flask import render_template
from .. import coderun_bp
@coderun_bp.route("/ide-py")
def IDE():
  return render_template("simpleide_py.html")