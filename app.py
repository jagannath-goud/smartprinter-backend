from flask import Flask, request, jsonify
from flask_cors import CORS
import razorpay
from dotenv import load_dotenv
import os, time, uuid
from queue import Queue
from PyPDF2 import PdfReader

# ================= LOAD ENV =================
load_dotenv()

app = Flask(__name__)
CORS(app)

# ================= ENV =================
RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET")
AGENT_SECRET = os.getenv("AGENT_SECRET")

# ================= RAZORPAY =================
razorpay_client = razorpay.Client(auth=(
    RAZORPAY_KEY_ID,
    RAZORPAY_KEY_SECRET
))

# ================= PATHS =================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ================= JOB QUEUE =================
print_queue = Queue()
job_status = {}

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

    # wait until file fully written
    for _ in range(10):
        if os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 0:
            break
        time.sleep(0.1)

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
        "key_id": RAZORPAY_KEY_ID
    })

# ================= VERIFY PAYMENT =================
@app.route("/verify-payment", methods=["POST"])
def verify_payment():
    try:
        razorpay_client.utility.verify_payment_signature(request.json)
        return jsonify({"status": "verified"})
    except Exception as e:
        return jsonify({"status": "failed", "error": str(e)}), 400

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
    return jsonify({"status": "QUEUED", "job_id": job_id})

# ================= JOB STATUS =================
@app.route("/job-status/<job_id>")
def job_status_api(job_id):
    return jsonify({"status": job_status.get(job_id, "UNKNOWN")})

# ================= AGENT AUTH =================
def agent_auth(req):
    token = req.headers.get("Authorization", "").replace("Bearer ", "")
    return token == AGENT_SECRET

# ================= AGENT PULL JOB =================
@app.route("/agent/pull-job", methods=["GET"])
def agent_pull_job():
    if not agent_auth(request):
        return jsonify({"error": "unauthorized"}), 401

    if print_queue.empty():
        return jsonify({"status": "NO_JOB"})

    job = print_queue.get()
    job_id = job["job_id"]

    job_status[job_id] = "PRINTING"

    return jsonify({
        "job_id": job_id,
        "pdf_url": f"/uploads/{job_id}.pdf",
        "from": job["from"],
        "to": job["to"],
        "copies": job["copies"]
    })

# ================= AGENT JOB DONE =================
@app.route("/agent/job-done", methods=["POST"])
def agent_job_done():
    if not agent_auth(request):
        return jsonify({"error": "unauthorized"}), 401

    job_id = request.json.get("job_id")
    job_status[job_id] = "COMPLETED"

    return jsonify({"status": "DONE"})

# ================= RUN =================
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
