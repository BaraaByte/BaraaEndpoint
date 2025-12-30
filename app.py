from flask import Flask, jsonify, render_template, request
from flask_cors import CORS
import os, json, traceback
from data.apps import APPS
from dotenv import load_dotenv
from flask.json.provider import DefaultJSONProvider
from datetime import datetime
import logging
from logging.handlers import RotatingFileHandler

# ---------- JSON Provider ----------
class CustomJSONProvider(DefaultJSONProvider):
    def dumps(self, obj, **kwargs):
        kwargs.setdefault("ensure_ascii", False)
        return super().dumps(obj, **kwargs)
    
    def loads(self, s, **kwargs):
        return super().loads(s, **kwargs)

load_dotenv()

# ---------- Logging Setup ----------
LOG_FILE = os.path.expanduser("~/logs/flask.log")
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

def setup_logging(app):
    """Setup logging with sensible defaults"""
    app.logger.handlers.clear()
    
    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=10 * 1024 * 1024,
        backupCount=10,
        encoding='utf-8'
    )
    console_handler = logging.StreamHandler()
    
    detailed_formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)s in %(module)s [%(pathname)s:%(lineno)d]:\n%(message)s\n' + 
        '-' * 80
    )
    simple_formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)s: %(message)s'
    )
    
    file_handler.setFormatter(detailed_formatter)
    console_handler.setFormatter(simple_formatter)
    
    if app.debug:
        file_handler.setLevel(logging.DEBUG)
        console_handler.setLevel(logging.DEBUG)
        app.logger.setLevel(logging.DEBUG)
    else:
        file_handler.setLevel(logging.WARNING)
        console_handler.setLevel(logging.WARNING)
        app.logger.setLevel(logging.WARNING)
    
    app.logger.addHandler(file_handler)
    app.logger.addHandler(console_handler)
    app.logger.propagate = False
    app.logger.info("Logging initialized. Debug mode: %s", app.debug)

# ---------- Safe Traceback Extraction ----------
def safe_extract_traceback(error):
    try:
        if hasattr(error, '__traceback__'):
            return ''.join(traceback.format_exception(type(error), error, error.__traceback__))
        else:
            return traceback.format_exc()
    except Exception:
        try:
            return str(error)
        except Exception:
            return "Could not extract error details"

# ---------- App Factory ----------
def create_app():
    app = Flask(__name__)
    app.json_provider_class = CustomJSONProvider
    app.json = app.json_provider_class(app)
    
    # Enable CORS
    CORS(app, resources={
        r"/api/*": {
            "origins": ["http://localhost:3000", "http://localhost:5173", "http://127.0.0.1:3000"],
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization", "X-Requested-With"]
        }
    })
    
    # ---------- Setup Logging ----------
    setup_logging(app)
    
    # ---------- Error Handlers ----------
    @app.errorhandler(400)
    def bad_request(error):
        app.logger.warning("400 Bad Request: %s %s", request.method, request.path)
        return render_error_page(400, "Bad Request", "The server could not understand the request.", error)
    
    @app.errorhandler(404)
    def not_found(error):
        app.logger.info("404 Not Found: %s %s", request.method, request.path)
        return render_error_page(404, "Not Found", "The page you're looking for doesn't exist.", error)
    
    @app.errorhandler(405)
    def method_not_allowed(error):
        app.logger.warning("405 Method Not Allowed: %s %s", request.method, request.path)
        return render_error_page(405, "Method Not Allowed", "The method is not allowed for this endpoint.", error)
    
    @app.errorhandler(500)
    def internal_server_error(error):
        error_traceback = safe_extract_traceback(error)
        app.logger.error("500 Internal Server Error: %s %s\n%s", request.method, request.path, error_traceback)
        return render_error_page(500, "Internal Server Error", "Something went wrong on our end. We're working to fix it.", error)
    
    @app.errorhandler(Exception)
    def handle_all_exceptions(error):
        status_code = getattr(error, 'code', 500)
        error_traceback = safe_extract_traceback(error)
        if status_code >= 500:
            app.logger.error("Unhandled Exception (%s): %s %s\n%s", status_code, request.method, request.path, error_traceback)
        else:
            app.logger.warning("Client Error (%s): %s %s - %s", status_code, request.method, request.path, str(error))
        error_name = getattr(error, 'name', f'Error {status_code}')
        error_description = getattr(error, 'description', str(error))
        return render_error_page(status_code, error_name, error_description, error)
    
    def render_error_page(status_code, error_name, error_description, error):
        error_traceback = safe_extract_traceback(error) if status_code >= 500 else None
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if request.accept_mimetypes.accept_json and not request.accept_mimetypes.accept_html:
            response = {
                "success": False,
                "error": error_name,
                "message": error_description,
                "status_code": status_code,
                "path": request.path,
                "method": request.method,
                "timestamp": timestamp
            }
            if status_code >= 500:
                response["traceback"] = error_traceback
            return jsonify(response), status_code
        return render_template(
            'error.html',
            error_code=status_code,
            error_name=error_name,
            error_description=error_description,
            error_traceback=error_traceback,
            timestamp=timestamp
        ), status_code
    
    # ---------- Routes ----------
    @app.route('/')
    def index():
        app.logger.debug("Index page accessed from %s", request.remote_addr)
        return render_template("index.html", apps=APPS)
    
    @app.route("/_health")
    def health_check():
        return jsonify({
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "service": "Flask App"
        })
    
    return app

# ---------- Create App ----------
try:
    app = create_app()
    app.logger.info("Application started successfully")
except Exception as e:
    error_msg = f"🔥 APP STARTUP FAILED 🔥\n{traceback.format_exc()}"
    print(error_msg)
    os.makedirs(os.path.expanduser("~/logs"), exist_ok=True)
    with open(os.path.expanduser("~/logs/startup_error.log"), "a") as f:
        f.write(error_msg + "\n")
    raise

# ---------- Run Locally ----------
if __name__ == '__main__':
    app.logger.info("Starting development server...")
    app.run(debug=True, host='0.0.0.0', port=5000)
