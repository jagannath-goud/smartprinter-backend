from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import razorpay
from dotenv import load_dotenv
import os, uuid, time
from PyPDF2 import PdfReader, PdfWriter
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
    return "SmartPrinter API running (BW ONLY) ✅"

# ================= UPLOAD =================
@app.route("/upload", methods=["POST"])
def upload_pdf():
    if "file" not in request.files:
        return jsonify({"error": "file missing"}), 400

    job_id = str(uuid.uuid4())
    pdf_path = os.path.join(UPLOAD_FOLDER, f"{job_id}.pdf")
    request.files["file"].save(pdf_path)

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
        except:
            time.sleep(0.2)

    return jsonify({"error": "unable to read pdf"}), 500

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
        razorpay_client.utility.verify_payment_signature({
            "razorpay_order_id": request.json["order_id"],
            "razorpay_payment_id": request.json["payment_id"],
            "razorpay_signature": request.json["signature"]
        })
        return jsonify({"status": "verified"}), 200
    except:
        return jsonify({"status": "failed"}), 400

# ================= PRINT (BW ONLY) =================
@app.route("/print", methods=["POST"])
def print_pdf():
    data = request.json

    job_id = data["job_id"]
    from_page = int(data.get("from", 1))
    to_page = int(data.get("to", 0))
    copies = int(data.get("copies", 1))

    # 🔒 FORCE BLACK & WHITE
    mode = "BW"

    original_pdf = os.path.join(UPLOAD_FOLDER, f"{job_id}.pdf")
    sliced_pdf = os.path.join(UPLOAD_FOLDER, f"{job_id}_print.pdf")

    reader = PdfReader(original_pdf)
    if to_page == 0 or to_page > len(reader.pages):
        to_page = len(reader.pages)

    writer = PdfWriter()
    for i in range(from_page - 1, to_page):
        writer.add_page(reader.pages[i])

    with open(sliced_pdf, "wb") as f:
        writer.write(f)

    print_queue.put({
        "job_id": job_id,
        "from": from_page,
        "to": to_page,
        "copies": copies,
        "mode": "BW"   # 🔒 HARD LOCK
    })

    job_status[job_id] = "QUEUED"
    return jsonify({
        "status": "QUEUED",
        "job_id": job_id,
        "mode": "BW"
    }), 200

# ================= AGENT AUTH =================
def agent_auth():
    return request.headers.get("Authorization") == f"Bearer {AGENT_SECRET}"

# ================= AGENT PULL =================
@app.route("/agent/pull-job", methods=["GET"])
def agent_pull_job():
    if not agent_auth():
        return jsonify({"error": "unauthorized"}), 401

    if print_queue.empty():
        return jsonify({"status": "NO_JOB"}), 200

    job = print_queue.get()
    job_status[job["job_id"]] = "PRINTING"

    return jsonify(job), 200

# ================= DOWNLOAD =================
@app.route("/agent/download/<job_id>")
def agent_download(job_id):
    if not agent_auth():
        return jsonify({"error": "unauthorized"}), 401

    sliced_pdf = os.path.join(UPLOAD_FOLDER, f"{job_id}_print.pdf")
    if not os.path.exists(sliced_pdf):
        return jsonify({"error": "file not found"}), 404

    return send_file(sliced_pdf, as_attachment=True)

# ================= DONE =================
@app.route("/agent/job-done", methods=["POST"])
def agent_job_done():
    if not agent_auth():
        return jsonify({"error": "unauthorized"}), 401

    job_id = request.json.get("job_id")

    for suffix in [".pdf", "_print.pdf"]:
        path = os.path.join(UPLOAD_FOLDER, f"{job_id}{suffix}")
        if os.path.exists(path):
            os.remove(path)

    job_status[job_id] = "DONE"
    return jsonify({"status": "DONE"}), 200

# ================= RUN =================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
