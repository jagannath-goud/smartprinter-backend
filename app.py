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

# ================= APP =================
app = Flask(__name__)
CORS(app)

# ================= RAZORPAY =================
razorpay_client = razorpay.Client(auth=(
    os.getenv("RAZORPAY_KEY_ID"),
    os.getenv("RAZORPAY_KEY_SECRET")
))

# ================= PATHS =================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ================= MEMORY =================
print_queue = Queue()
job_status = {}

# 🔥 REAL PRINTER STATE (UPDATED ONLY BY AGENT)
printer_state = {
    "status": "OFFLINE",        # OFFLINE | ONLINE_IDLE | ONLINE_PRINTING
    "printer": None,
    "last_seen": 0
}

AVG_SECONDS_PER_JOB = 15  # ETA calculation (safe demo value)

# ================= HOME =================
@app.route("/")
def home():
    return "SmartPrinter API running (REAL MODE) ✅"

# ================= PRINTER STATUS (FOR ANDROID) =================
@app.route("/printer-status", methods=["GET"])
def get_printer_status():
    queue_len = print_queue.qsize()
    return jsonify({
        "status": printer_state["status"],
        "printer": printer_state["printer"],
        "queue_length": queue_len,
        "eta_seconds": queue_len * AVG_SECONDS_PER_JOB
    })

# ================= AGENT HEARTBEAT =================
@app.route("/agent/heartbeat", methods=["POST"])
def agent_heartbeat():
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

    job_status[job_id] = "UPLOADED"
    return jsonify({"job_id": job_id})

# ================= GET PAGES =================
@app.route("/get-pages", methods=["POST"])
def get_pages():
    job_id = request.json["job_id"]
    reader = PdfReader(os.path.join(UPLOAD_FOLDER, f"{job_id}.pdf"))
    return jsonify({"total_pages": len(reader.pages)})

# ================= CREATE ORDER (BLOCK IF OFFLINE) =================
@app.route("/create-order", methods=["POST"])
def create_order():
    if printer_state["status"] == "OFFLINE":
        return jsonify({
            "error": "PRINTER_OFFLINE",
            "message": "Printer is not available right now"
        }), 409

    amount = int(request.json["amount"]) * 100
    order = razorpay_client.order.create({
        "amount": amount,
        "currency": "INR",
        "payment_capture": 1
    })
    return jsonify(order)

# ================= VERIFY PAYMENT =================
@app.route("/verify-payment", methods=["POST"])
def verify_payment():
    try:
        razorpay_client.utility.verify_payment_signature(request.json)
        return jsonify({"status": "verified"})
    except:
        return jsonify({"status": "failed"}), 400

# ================= PRINT =================
@app.route("/print", methods=["POST"])
def print_job():
    if printer_state["status"] == "OFFLINE":
        return jsonify({
            "error": "PRINTER_OFFLINE",
            "message": "Printer is offline"
        }), 409

    data = request.json
    job_id = data["job_id"]

    reader = PdfReader(os.path.join(UPLOAD_FOLDER, f"{job_id}.pdf"))
    writer = PdfWriter()

    from_p = int(data.get("from", 1)) - 1
    to_p = int(data.get("to", len(reader.pages)))

    for i in range(from_p, to_p):
        writer.add_page(reader.pages[i])

    sliced = os.path.join(UPLOAD_FOLDER, f"{job_id}_print.pdf")
    with open(sliced, "wb") as f:
        writer.write(f)

    print_queue.put({
        "job_id": job_id,
        "from": from_p + 1,
        "to": to_p,
        "copies": int(data.get("copies", 1))
    })

    job_status[job_id] = "QUEUED"

    return jsonify({
        "status": "QUEUED",
        "queue_position": print_queue.qsize(),
        "eta_seconds": print_queue.qsize() * AVG_SECONDS_PER_JOB
    })

# ================= AGENT AUTH =================
def agent_auth():
    return request.headers.get("Authorization") == f"Bearer {AGENT_SECRET}"

# ================= AGENT PULL =================
@app.route("/agent/pull-job", methods=["GET"])
def pull_job():
    if not agent_auth():
        return jsonify({"error": "unauthorized"}), 401

    if print_queue.empty():
        return jsonify({"status": "NO_JOB"})

    job = print_queue.get()
    job_status[job["job_id"]] = "PRINTING"
    return jsonify(job)

# ================= AGENT DOWNLOAD =================
@app.route("/agent/download/<job_id>", methods=["GET"])
def download(job_id):
    if not agent_auth():
        return jsonify({"error": "unauthorized"}), 401

    return send_file(
        os.path.join(UPLOAD_FOLDER, f"{job_id}_print.pdf"),
        as_attachment=True
    )

# ================= AGENT DONE =================
@app.route("/agent/job-done", methods=["POST"])
def job_done():
    if not agent_auth():
        return jsonify({"error": "unauthorized"}), 401

    job_id = request.json["job_id"]
    job_status[job_id] = "DONE"

    for f in (f"{job_id}.pdf", f"{job_id}_print.pdf"):
        p = os.path.join(UPLOAD_FOLDER, f)
        if os.path.exists(p):
            os.remove(p)

    return jsonify({"status": "DONE"})

# ================= RUN =================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
