from flask import Flask, request, jsonify
import razorpay
import os, uuid
from PyPDF2 import PdfReader
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

razorpay_client = razorpay.Client(auth=(
    os.getenv("RAZORPAY_KEY_ID"),
    os.getenv("RAZORPAY_KEY_SECRET")
))

@app.route("/")
def home():
    return "SmartPrinter Backend Running"

@app.route("/upload", methods=["POST"])
def upload():
    if "file" not in request.files:
        return jsonify({"error": "file missing"}), 400

    job_id = str(uuid.uuid4())
    path = os.path.join(UPLOAD_DIR, f"{job_id}.pdf")
    request.files["file"].save(path)

    return jsonify({"job_id": job_id})

@app.route("/get-pages", methods=["POST"])
def get_pages():
    job_id = request.json.get("job_id")
    path = os.path.join(UPLOAD_DIR, f"{job_id}.pdf")

    if not os.path.exists(path):
        return jsonify({"error": "file not found"}), 404

    reader = PdfReader(path)
    return jsonify({"total_pages": len(reader.pages)})

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

@app.route("/verify-payment", methods=["POST"])
def verify_payment():
    data = request.json
    razorpay_client.utility.verify_payment_signature({
        "razorpay_order_id": data["razorpay_order_id"],
        "razorpay_payment_id": data["razorpay_payment_id"],
        "razorpay_signature": data["razorpay_signature"]
    })
    return jsonify({"status": "verified"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
