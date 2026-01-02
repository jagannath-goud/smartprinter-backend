from flask import Flask, request, jsonify
import razorpay
from dotenv import load_dotenv
import os, uuid, time
from PyPDF2 import PdfReader

# ================= LOAD ENV =================
load_dotenv()

APP_MODE = os.getenv("APP_MODE", "TEST")   # TEST / LIVE
RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET")

app = Flask(__name__)

# ================= RAZORPAY =================
razorpay_client = razorpay.Client(auth=(
    RAZORPAY_KEY_ID,
    RAZORPAY_KEY_SECRET
))

# ================= PATHS =================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ================= IN-MEMORY STATE =================
jobs = {}              # job_id → job info
verified_payments = set()

# ================= HEALTH CHECK =================
@app.route("/", methods=["GET"])
def health():
    return "SmartPrinter API running ✅"

# ================= UPLOAD PDF =================
@app.route("/upload", methods=["POST"])
def upload_pdf():
    if "file" not in request.files:
        return jsonify({"error": "file missing"}), 400

    job_id = str(uuid.uuid4())
    pdf_path = os.path.join(UPLOAD_FOLDER, f"{job_id}.pdf")
    request.files["file"].save(pdf_path)

    # Ensure file is fully written
    for _ in range(20):
        if os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 0:
            break
        time.sleep(0.1)

    jobs[job_id] = {
        "pdf": pdf_path,
        "status": "UPLOADED",
        "pages": 0
    }

    return jsonify({"job_id": job_id}), 200

# ================= GET PAGE COUNT =================
@app.route("/get-pages", methods=["POST"])
def get_pages():
    data = request.json
    job_id = data.get("job_id")

    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "invalid job"}), 404

    try:
        reader = PdfReader(job["pdf"])
        pages = len(reader.pages)
        job["pages"] = pages
        return jsonify({"total_pages": pages}), 200
    except Exception as e:
        return jsonify({"error": "pdf read failed"}), 500

# ================= CREATE ORDER =================
@app.route("/create-order", methods=["POST"])
def create_order():
    amount = int(request.json.get("amount", 0)) * 100
    if amount <= 0:
        return jsonify({"error": "invalid amount"}), 400

    order = razorpay_client.order.create({
        "amount": amount,
        "currency": "INR",
        "payment_capture": 1
    })

    return jsonify({
        "order_id": order["id"],
        "key_id": RAZORPAY_KEY_ID
    }), 200

# ================= VERIFY PAYMENT =================
@app.route("/verify-payment", methods=["POST"])
def verify_payment():
    data = request.json

    try:
        razorpay_client.utility.verify_payment_signature({
            "razorpay_order_id": data["razorpay_order_id"],
            "razorpay_payment_id": data["razorpay_payment_id"],
            "razorpay_signature": data["razorpay_signature"]
        })

        verified_payments.add(data["razorpay_payment_id"])
        return jsonify({"status": "verified"}), 200

    except Exception as e:
        return jsonify({"status": "failed"}), 400

# ================= REQUEST PRINT =================
@app.route("/request-print", methods=["POST"])
def request_print():
    data = request.json
    job_id = data.get("job_id")
    payment_id = data.get("payment_id")

    if payment_id not in verified_payments:
        return jsonify({"error": "payment not verified"}), 403

    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "invalid job"}), 404

    job["status"] = "READY_FOR_PRINT"
    job["from"] = data.get("from")
    job["to"] = data.get("to")
    job["copies"] = data.get("copies", 1)

    return jsonify({"status": "queued"}), 200

# ================= JOB STATUS =================
@app.route("/job-status/<job_id>", methods=["GET"])
def job_status(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify({"status": "UNKNOWN"}), 404
    return jsonify({"status": job["status"]}), 200

# ================= RUN =================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
