from flask import Flask, jsonify
import os

app = Flask(__name__)

@app.route("/")
def home():
    return "SmartPrinter Backend Running"

@app.route("/health")
def health():
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
