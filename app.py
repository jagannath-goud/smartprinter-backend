from flask import Flask, request, jsonify, send_file
import os
from werkzeug.utils import secure_filename
import uuid

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

print_jobs = []

@app.route("/")
def home():
    return jsonify({"status": "SmartPrinter backend running"})

@app.route("/upload", methods=["POST"])
def upload_pdf():
    file = request.files.get("file")
    from_page = request.form.get("fromPage")
    to_page = request.form.get("toPage")

    if not file:
        return jsonify({"error": "No file"}), 400

    job_id = str(uuid.uuid4())
    filename = secure_filename(file.filename)
    path = os.path.join(UPLOAD_FOLDER, job_id + "_" + filename)
    file.save(path)

    job = {
        "job_id": job_id,
        "file_path": path,
        "from_page": from_page,
        "to_page": to_page,
        "status": "pending"
    }

    print_jobs.append(job)

    return jsonify({"message": "Job created", "job_id": job_id})

@app.route("/get-job", methods=["GET"])
def get_job():
    for job in print_jobs:
        if job["status"] == "pending":
            job["status"] = "processing"
            return jsonify(job)
    return jsonify({"message": "No jobs"})

@app.route("/download/<job_id>")
def download(job_id):
    for job in print_jobs:
        if job["job_id"] == job_id:
            return send_file(job["file_path"], as_attachment=True)
    return jsonify({"error": "Job not found"}), 404

@app.route("/job-done/<job_id>", methods=["POST"])
def job_done(job_id):
    for job in print_jobs:
        if job["job_id"] == job_id:
            job["status"] = "done"
            return jsonify({"message": "Job marked done"})
    return jsonify({"error": "Job not found"}), 404

if __name__ == "__main__":
    app.run(debug=True)
