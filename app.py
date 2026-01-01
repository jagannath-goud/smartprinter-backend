from flask import Flask, request, jsonify
from flask_cors import CORS
import razorpay
import os, time, uuid, threading
from queue import Queue
from PyPDF2 import PdfReader
from dotenv import load_dotenv

# ================= LOAD ENV =================
load_dotenv()
APP_MODE = os.getenv("APP_MODE", "TEST")

app = Flask(__name__)
CORS(app)  # 🔥 CRITICAL FIX

# ================= RAZORPAY =================
razorpay_client = razorpay.Client(auth=(
    os.getenv("RAZORPAY_KEY_ID"),
    os.getenv("RAZORPAY_KEY_SECRET")
))

# ================= PATHS =================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ================= QUEUE & STATE =================
print_queue = Queue()
job_status = {}

# ================= PRINTER WORKER (CLOUD SAFE) =================
def printer_worker():
    while True:
        job = print_queue.get()
        job_id = job["job_id"]
        job_status[job_id] = "QUEUED_FOR_PRINT"
        # ⛔ Cloud cannot print – only queue
        print("PRINT JOB QUEUED:", job)
        print_queue.task_done()

threading.Thread(target=printer_worker, daemon=True).start()

# ================= HOME =================
@app.route("/")
def home():
    return "Smart Printer Backend Running ✅"

# ================= UPLOAD =================
@app.route("/upload", methods=["POST"])
def upload_pdf():
    if "file" not in request.files:
        return jsonify({"error": "file missing"}), 400

    job_id = str(uuid.uuid4())
    pdf_path = os.path.join(UPLOAD_FOLDER, f"{job_id}.pdf")
    request.files["file"].save(pdf_path)

    # 🔒 WAIT UNTIL FILE IS STABLE
    for _ in range(30):
        if os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 1024:
            break
        time.sleep(0.1)

    job_status[job_id] = "UPLOADED"
    return jsonify({"job_id": job_id}), 200

# ================= GET PAGES =================
@app.route("/get-pages", methods=["POST"])
def get_pages():
    job_id = request.json.get("job_id")
    pdf_path = os.path.join(UPLOAD_FOLDER, f"{job_id}.pdf")

    if not os.path.exists(pdf_path):
        return jsonify({"error": "file not found"}), 404

    for _ in range(5):
        try:
            reader = PdfReader(pdf_path)
            return jsonify({"total_pages": len(reader.pages)}), 200
        except Exception:
            time.sleep(0.2)

    return jsonify({"error": "pdf read failed"}), 500

# ================= CREATE ORDER =================
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
    }), 200

# ================= VERIFY PAYMENT =================
@app.route("/verify-payment", methods=["POST"])
def verify_payment():
    try:
        data = request.json

        razorpay_client.utility.verify_payment_signature({
            "razorpay_order_id": data["razorpay_order_id"],
            "razorpay_payment_id": data["razorpay_payment_id"],
            "razorpay_signature": data["razorpay_signature"]
        })

        return jsonify({"status": "verified"}), 200

    except Exception as e:
        print("VERIFY ERROR:", e)
        return jsonify({"status": "failed"}), 400

# ================= PRINT =================
@app.route("/print", methods=["POST"])
def print_pdf():
    data = request.json
    job_id = data["job_id"]

    print_queue.put({
        "job_id": job_id,
        "from": data["from"],
        "to": data["to"],
        "copies": data.get("copies", 1)
    })

    job_status[job_id] = "QUEUED"
    return jsonify({"status": "QUEUED", "job_id": job_id}), 200

# ================= JOB STATUS =================
@app.route("/job-status/<job_id>")
def job_status_api(job_id):
    return jsonify({"status": job_status.get(job_id, "UNKNOWN")})

# ================= RUN =================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
