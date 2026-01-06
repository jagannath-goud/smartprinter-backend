from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import razorpay
import os, uuid, time
from queue import Queue
from PyPDF2 import PdfReader, PdfWriter
from dotenv import load_dotenv

load_dotenv()

AGENT_SECRET = os.getenv("AGENT_SECRET")

app = Flask(__name__)
CORS(app)

razorpay_client = razorpay.Client(auth=(
    os.getenv("RAZORPAY_KEY_ID"),
    os.getenv("RAZORPAY_KEY_SECRET")
))

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

print_queue = Queue()

printer_state = {
    "status": "OFFLINE",
    "printer": None,
    "last_seen": 0
}

AVG_SECONDS_PER_JOB = 15

@app.route("/")
def home():
    return "VPrint Backend Running ✅"

@app.route("/printer-status")
def printer_status():
    q = print_queue.qsize()
    return jsonify({
        "status": printer_state["status"],
        "printer": printer_state["printer"],
        "queue_length": q,
        "eta_seconds": q * AVG_SECONDS_PER_JOB
    })

@app.route("/agent/heartbeat", methods=["POST"])
def heartbeat():
    if request.headers.get("Authorization") != f"Bearer {AGENT_SECRET}":
        return jsonify({"error": "unauthorized"}), 401

    data = request.json
    printer_state["status"] = data.get("status", "OFFLINE")
    printer_state["printer"] = data.get("printer")
    printer_state["last_seen"] = time.time()
    return jsonify({"ok": True})

@app.route("/upload", methods=["POST"])
def upload():
    file = request.files["file"]
    job_id = str(uuid.uuid4())
    path = os.path.join(UPLOAD_FOLDER, f"{job_id}.pdf")
    file.save(path)
    return jsonify({"job_id": job_id})

@app.route("/get-pages", methods=["POST"])
def get_pages():
    job_id = request.json["job_id"]
    reader = PdfReader(os.path.join(UPLOAD_FOLDER, f"{job_id}.pdf"))
    return jsonify({"total_pages": len(reader.pages)})

@app.route("/create-order", methods=["POST"])
def create_order():
    if printer_state["status"] == "OFFLINE":
        return jsonify({"error": "PRINTER_OFFLINE"}), 409

    amount = int(request.json["amount"]) * 100
    order = razorpay_client.order.create({
        "amount": amount,
        "currency": "INR",
        "payment_capture": 1
    })
    return jsonify(order)

@app.route("/print", methods=["POST"])
def print_job():
    if printer_state["status"] == "OFFLINE":
        return jsonify({"error": "PRINTER_OFFLINE"}), 409

    data = request.json
    job_id = data["job_id"]

    reader = PdfReader(os.path.join(UPLOAD_FOLDER, f"{job_id}.pdf"))
    writer = PdfWriter()

    for i in range(data["from"] - 1, data["to"]):
        writer.add_page(reader.pages[i])

    out = os.path.join(UPLOAD_FOLDER, f"{job_id}_print.pdf")
    with open(out, "wb") as f:
        writer.write(f)

    print_queue.put({
        "job_id": job_id,
        "from": data["from"],
        "to": data["to"],
        "copies": data["copies"]
    })

    return jsonify({
        "status": "QUEUED",
        "queue_position": print_queue.qsize(),
        "eta_seconds": print_queue.qsize() * AVG_SECONDS_PER_JOB
    })

if __name__ == "__main__":
    app.run()
