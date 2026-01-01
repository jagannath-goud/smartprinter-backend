from flask import Flask, request, jsonify
import os
import razorpay

app = Flask(__name__)

razorpay_client = razorpay.Client(auth=(
    os.environ.get("RAZORPAY_KEY_ID"),
    os.environ.get("RAZORPAY_KEY_SECRET")
))

@app.route("/")
def home():
    return "SmartPrinter Backend Running"

@app.route("/create-order", methods=["POST"])
def create_order():
    data = request.get_json()
    amount = int(data["amount"]) * 100

    order = razorpay_client.order.create({
        "amount": amount,
        "currency": "INR",
        "payment_capture": 1
    })

    return jsonify({
        "order_id": order["id"],
        "key_id": os.environ.get("RAZORPAY_KEY_ID")
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
