from flask import Flask, request, jsonify
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.route("/")
def home():
    return jsonify({"status": "SmartPrinter backend running"})

@app.route("/upload", methods=["POST"])
def upload_pdf():
    if "file" not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files["file"]
    from_page = request.form.get("fromPage")
    to_page = request.form.get("toPage")

    if file.filename == "":
        return jsonify({"error": "No selected file"}), 400

    filename = secure_filename(file.filename)
    save_path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(save_path)

    # This is where print-job creation logic will go later
    print("PDF saved:", save_path)
    print("From page:", from_page)
    print("To page:", to_page)

    return jsonify({
        "message": "PDF uploaded successfully",
        "filename": filename,
        "fromPage": from_page,
        "toPage": to_page
    })

if __name__ == "__main__":
    app.run(debug=True)
