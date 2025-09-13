# app.py
from flask import Flask, jsonify
from python.receiver import make_processors, start_processor_thread

app = Flask(__name__)
_processors = make_processors()
_threads = [start_processor_thread(p) for p in _processors]

@app.route("/")
def home():
    return "OK"

@app.route("/api/status")
def api_status():
    return jsonify({f"{p.sta}": p.to_json() for p in _processors})

if __name__ == "__main__":
    app.run(debug=False)
