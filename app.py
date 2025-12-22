# app.py
from flask import Flask, jsonify, request

app = Flask(__name__)

# Home route
@app.route('/')
def home():
    return "Hello, World! This is my simple Flask app."

# Example API endpoint
@app.route('/api/greet', methods=['GET'])
def greet():
    name = request.args.get('name', 'Guest')  # Get name from URL query parameter
    return jsonify({
        'message': f'Hello, {name}!'
    })

if __name__ == '__main__':
    app.run(debug=True)
