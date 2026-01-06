from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import razorpay
import os, uuid, time
from queue import Queue
from PyPDF2 import PdfReader, PdfWriter
from dotenv import load_dotenv

# ================= LOAD ENV =================
load_dotenv()

AGENT_SECRET = os.getenv("AGENT_SECRET")
RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET")

# ================= APP =================
app = Flask(__name__)
CORS(app)

# ================= RAZORPAY (TEST MODE) =================
razorpay_client = razorpay.Client(auth=(
    RAZORPAY_KEY_ID,
    RAZORPAY_KEY_SECRET
))

# ================= PATHS =================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ================= MEMORY =================
print_queue = Queue()

printer_state = {
    "status": "OFFLINE",
    "printer": None,
    "last_seen": 0
}

AVG_SECONDS_PER_JOB = 15

# ================= HOME =================
@app.route("/")
def home():
    return "VPrint Backend Running (TEST MODE) ✅"

# ================= PRINTER STATUS =================
@app.route("/printer-status", methods=["GET"])
def printer_status():
    # Auto offline if agent silent
    if time.time() - printer_state["last_seen"] > 15:
        printer_state["status"] = "OFFLINE"
        printer_state["printer"] = None

    q = print_queue.qsize()
    return jsonify({
        "status": printer_state["status"],
        "printer": printer_state["printer"],
        "queue_length": q,
        "eta_seconds": q * AVG_SECONDS_PER_JOB
    })

# ================= AGENT HEARTBEAT =================
@app.route("/agent/heartbeat", methods=["POST"])
def heartbeat():
    if request.headers.get("Authorization") != f"Bearer {AGENT_SECRET}":
        return jsonify({"error": "unauthorized"}), 401

    data = request.json
    printer_state["status"] = data.get("status", "OFFLINE")
    printer_state["printer"] = data.get("printer")
    printer_state["last_seen"] = time.time()
    return jsonify({"ok": True})

# ================= UPLOAD =================
@app.route("/upload", methods=["POST"])
def upload():
    file = request.files.get("file")
    if not file:
        return jsonify({"error": "file missing"}), 400

    job_id = str(uuid.uuid4())
    path = os.path.join(UPLOAD_FOLDER, f"{job_id}.pdf")
    file.save(path)

    return jsonify({"job_id": job_id})

# ================= GET PAGES =================
@app.route("/get-pages", methods=["POST"])
def get_pages():
    job_id = request.json["job_id"]
    reader = PdfReader(os.path.join(UPLOAD_FOLDER, f"{job_id}.pdf"))
    return jsonify({"total_pages": len(reader.pages)})

# ================= CREATE ORDER (REAL TEST ORDER) =================
@app.route("/create-order", methods=["POST"])
def create_order():
    if printer_state["status"] == "OFFLINE":
        return jsonify({"error": "PRINTER_OFFLINE"}), 409

    amount_rupees = int(request.json["amount"])
    amount_paise = amount_rupees * 100

    order = razorpay_client.order.create({
        "amount": amount_paise,
        "currency": "INR",
        "payment_capture": 1
    })

    return jsonify({
        "order_id": order["id"],
        "amount": amount_paise,
        "currency": "INR",
        "key_id": RAZORPAY_KEY_ID
    })

# ================= PRINT =================
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

# ================= RUN =================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
