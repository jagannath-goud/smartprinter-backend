from flask import Flask, request, jsonify
from flask_cors import CORS
import razorpay
import os
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
from PyPDF2 import PdfReader
import uuid

# ================== INIT ==================
load_dotenv()

app = Flask(__name__)
CORS(app)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ================== RAZORPAY ==================
RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET")

razorpay_client = razorpay.Client(
    auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET)
)

# ================== MEMORY STORE (TEMP) ==================
jobs = {}  # job_id -> file_path

# ================== ROUTES ==================

@app.route("/")
def home():
    return jsonify({
        "message": "VPrint Backend Running",
        "status": "OK"
    })

# ---------- PRINTER STATUS ----------
@app.route("/printer-status")
def printer_status():
    return jsonify({
        "status": "ONLINE"
    })

# ---------- UPLOAD PDF ----------
@app.route("/upload", methods=["POST"])
def upload_pdf():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    filename = secure_filename(file.filename)

    job_id = str(uuid.uuid4())
    save_path = os.path.join(UPLOAD_FOLDER, f"{job_id}_{filename}")
    file.save(save_path)

    jobs[job_id] = save_path

    return jsonify({
        "job_id": job_id
    })

# ---------- GET PAGE COUNT ----------
@app.route("/get-pages", methods=["POST"])
def get_pages():
    data = request.json
    job_id = data.get("job_id")

    if job_id not in jobs:
        return jsonify({"error": "Invalid job_id"}), 400

    reader = PdfReader(jobs[job_id])
    total_pages = len(reader.pages)

    return jsonify({
        "total_pages": total_pages
    })

# ---------- CREATE RAZORPAY ORDER ----------
@app.route("/create-order", methods=["POST"])
def create_order():
    data = request.json
    amount = int(data["amount"]) * 100  # rupees → paise

    order = razorpay_client.order.create({
        "amount": amount,
        "currency": "INR",
        "payment_capture": 1
    })

    return jsonify({
        "order_id": order["id"],
        "key_id": RAZORPAY_KEY_ID
    })

# ---------- PRINT JOB ----------
@app.route("/print", methods=["POST"])
def print_job():
    data = request.json

    job_id = data.get("job_id")
    from_page = data.get("from")
    to_page = data.get("to")
    copies = data.get("copies")

    if job_id not in jobs:
        return jsonify({"error": "Invalid job_id"}), 400

    # (Printer agent will pick this later)
    print("🖨 PRINT JOB RECEIVED")
    print("Job:", job_id)
    print("Pages:", from_page, "to", to_page)
    print("Copies:", copies)

    return jsonify({
        "status": "QUEUED"
    })

# ================== START SERVER ==================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
