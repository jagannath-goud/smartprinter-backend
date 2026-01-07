from flask import Flask, jsonify, request
from flask_cors import CORS
import razorpay
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)

RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET")

razorpay_client = razorpay.Client(
    auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET)
)

@app.route("/")
def home():
    return "Backend OK"

@app.route("/create-order", methods=["POST"])
def create_order():
    data = request.json
    amount = int(data["amount"]) * 100  # convert to paise

    order = razorpay_client.order.create({
        "amount": amount,
        "currency": "INR",
        "payment_capture": 1
    })

    return jsonify({
        "order_id": order["id"],
        "key_id": RAZORPAY_KEY_ID
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
