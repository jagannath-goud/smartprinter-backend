from flask import Flask, request, jsonify
import os
import razorpay

app = Flask(__name__)

# Razorpay client
razorpay_client = razorpay.Client(auth=(
    os.environ.get("RAZORPAY_KEY_ID"),
    os.environ.get("RAZORPAY_KEY_SECRET")
))

# Health check
@app.route("/")
def home():
    return "SmartPrinter Backend Running"

# Page count test API (TEMP)
@app.route("/get-pages", methods=["GET"])
def get_pages():
    return jsonify({
        "total_pages": 10
    })

# Create Razorpay order
@app.route("/create-order", methods=["POST"])
def create_order():
    data = request.get_json()
    amount = int(data["amount"]) * 100  # rupees → paise

    order = razorpay_client.order.create({
        "amount": amount,
        "currency": "INR",
        "payment_capture": 1
    })

    return jsonify({
        "order_id": order["id"],
        "key_id": os.environ.get("RAZORPAY_KEY_ID")
    })

# Verify payment
@app.route("/verify-payment", methods=["POST"])
def verify_payment():
    data = request.get_json()

    razorpay_client.utility.verify_payment_signature({
        "razorpay_order_id": data["razorpay_order_id"],
        "razorpay_payment_id": data["razorpay_payment_id"],
        "razorpay_signature": data["razorpay_signature"]
    })

    return jsonify({"status": "verified"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
