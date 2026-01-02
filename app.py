from flask import Flask, request, jsonify
from flask_cors import CORS
import razorpay
from dotenv import load_dotenv
import os, time, uuid
from PyPDF2 import PdfReader
from queue import Queue
from functools import wraps

# ================= LOAD ENV =================
load_dotenv()

app = Flask(__name__)
CORS(app)

# ================= ENV =================
AGENT_SECRET = os.getenv("AGENT_SECRET")

# ================= RAZORPAY =================
razorpay_client = razorpay.Client(auth=(
    os.getenv("RAZORPAY_KEY_ID"),
    os.getenv("RAZORPAY_KEY_SECRET")
))

# ================= PATHS =================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ================= QUEUES & STATUS =================
agent_job_queue = Queue()
job_status = {}

# ================= AGENT AUTH =================
def agent_auth_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if auth != f"Bearer {AGENT_SECRET}":
            return jsonify({"error": "Unauthorized agent"}), 401
        return f(*args, **kwargs)
    return decorated

# ================= HOME =================
@app.route("/")
def home():
    return "SmartPrinter API running ✅"

# ================= UPLOAD =================
@app.route("/upload", methods=["POST"])
def upload_pdf():
    if "file" not in request.files:
        return jsonify({"error": "file missing"}), 400

    job_id = str(uuid.uuid4())
    pdf_path = os.path.join(UPLOAD_FOLDER, f"{job_id}.pdf")
    request.files["file"].save(pdf_path)

    time.sleep(0.2)
    job_status[job_id] = "UPLOADED"

    return jsonify({"job_id": job_id})

# ================= GET PAGES =================
@app.route("/get-pages", methods=["POST"])
def get_pages():
    job_id = request.json.get("job_id")
    pdf_path = os.path.join(UPLOAD_FOLDER, f"{job_id}.pdf")

    reader = PdfReader(pdf_path)
    return jsonify({"total_pages": len(reader.pages)})

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
    })

# ================= VERIFY PAYMENT =================
@app.route("/verify-payment", methods=["POST"])
def verify_payment():
    data = request.json
    razorpay_client.utility.verify_payment_signature(data)
    return jsonify({"status": "verified"})

# ================= CREATE PRINT JOB =================
@app.route("/print", methods=["POST"])
def print_job():
    data = request.json
    job_id = data["job_id"]

    job = {
        "job_id": job_id,
        "pdf_url": f"{request.host_url}uploads/{job_id}.pdf",
        "from": data["from"],
        "to": data["to"],
        "copies": data.get("copies", 1)
    }

    agent_job_queue.put(job)
    job_status[job_id] = "QUEUED"

    return jsonify({"status": "QUEUED", "job_id": job_id})

# ================= AGENT PULL JOB =================
@app.route("/agent/pull-job", methods=["GET"])
@agent_auth_required
def agent_pull_job():
    if agent_job_queue.empty():
        return jsonify({"status": "NO_JOB"})

    job = agent_job_queue.get()
    job_status[job["job_id"]] = "ASSIGNED"
    return jsonify(job)

# ================= AGENT JOB DONE =================
@app.route("/agent/job-done", methods=["POST"])
@agent_auth_required
def agent_job_done():
    job_id = request.json.get("job_id")
    job_status[job_id] = "COMPLETED"
    return jsonify({"status": "DONE"})

# ================= JOB STATUS =================
@app.route("/job-status/<job_id>")
def get_job_status(job_id):
    return jsonify({"status": job_status.get(job_id, "UNKNOWN")})

# ================= RUN =================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
