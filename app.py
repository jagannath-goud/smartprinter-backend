from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import razorpay
from dotenv import load_dotenv
import os, uuid
from PyPDF2 import PdfReader
from queue import Queue

# ================= LOAD ENV =================
load_dotenv()

AGENT_SECRET = os.getenv("AGENT_SECRET")

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

# ================= HOME =================
@app.route("/")
def home():
    return "SmartPrinter API running ✅"

# ================= UPLOAD PDF =================
@app.route("/upload", methods=["POST"])
def upload_pdf():
    if "file" not in request.files:
        return jsonify({"error": "file missing"}), 400

    job_id = str(uuid.uuid4())
    pdf_path = os.path.join(UPLOAD_FOLDER, f"{job_id}.pdf")
    request.files["file"].save(pdf_path)

    job_status[job_id] = "UPLOADED"
    return jsonify({"job_id": job_id})

# ================= GET PAGE COUNT =================
@app.route("/get-pages", methods=["POST"])
def get_pages():
    job_id = request.json.get("job_id")
    pdf_path = os.path.join(UPLOAD_FOLDER, f"{job_id}.pdf")

    reader = PdfReader(pdf_path)
    return jsonify({"total_pages": len(reader.pages)})

# ================= CREATE RAZORPAY ORDER =================
@app.route("/create-order", methods=["POST"])
def create_order():
    amount = int(request.json["amount"]) * 100

    order = razorpay_client.order.create({
        "amount": amount,
        "currency": "INR",
        "payment_capture": 1
    })

    return jsonify({
        "order_id": order["id"],
        "key_id": os.getenv("RAZORPAY_KEY_ID")
    })

# ================= VERIFY PAYMENT =================
@app.route("/verify-payment", methods=["POST"])
def verify_payment():
    data = request.json
    razorpay_client.utility.verify_payment_signature({
        "razorpay_order_id": data["order_id"],
        "razorpay_payment_id": data["payment_id"],
        "razorpay_signature": data["signature"]
    })
    return jsonify({"status": "verified"})

# ================= DOWNLOAD PDF (IMPORTANT) =================
@app.route("/download/<job_id>")
def download_pdf(job_id):
    pdf_path = os.path.join(UPLOAD_FOLDER, f"{job_id}.pdf")
    if not os.path.exists(pdf_path):
        return jsonify({"error": "file not found"}), 404
    return send_file(pdf_path, as_attachment=True)

# ================= SEND PRINT JOB =================
@app.route("/print", methods=["POST"])
def print_pdf():
    data = request.json
    job_id = data["job_id"]

    print_queue.put({
        "job_id": job_id,
        "pdf_url": f"{request.host_url}download/{job_id}",
        "pages": data.get("pages", "ALL"),
        "copies": data.get("copies", 1)
    })

    job_status[job_id] = "QUEUED"
    return jsonify({"status": "QUEUED", "job_id": job_id})

# ================= AGENT AUTH =================
def agent_auth():
    auth = request.headers.get("Authorization", "")
    return auth == f"Bearer {AGENT_SECRET}"

# ================= AGENT PULL JOB =================
@app.route("/agent/pull-job", methods=["GET"])
def agent_pull_job():
    if not agent_auth():
        return jsonify({"error": "unauthorized"}), 401

    if print_queue.empty():
        return jsonify({"status": "NO_JOB"})

    job = print_queue.get()
    job_status[job["job_id"]] = "PRINTING"
    return jsonify(job)

# ================= AGENT JOB DONE =================
@app.route("/agent/job-done", methods=["POST"])
def agent_job_done():
    if not agent_auth():
        return jsonify({"error": "unauthorized"}), 401

    job_id = request.json.get("job_id")
    job_status[job_id] = "DONE"
    return jsonify({"status": "DONE"})

# ================= JOB STATUS =================
@app.route("/job-status/<job_id>")
def get_job_status(job_id):
    return jsonify({
        "job_id": job_id,
        "status": job_status.get(job_id, "UNKNOWN")
    })

# ================= RUN =================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
