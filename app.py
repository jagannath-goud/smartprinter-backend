from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import sqlite3
import os
from datetime import datetime
from werkzeug.utils import secure_filename

app = Flask(__name__)
CORS(app)

UPLOAD_FOLDER = "uploads"
DB_NAME = "print_jobs.db"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ---------------- DB INIT ----------------
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS print_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT,
            page_from INTEGER,
            page_to INTEGER,
            amount REAL,
            status TEXT,
            created_at TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

# ---------------- UPLOAD PDF ----------------
@app.route("/upload", methods=["POST"])
def upload_pdf():
    file = request.files.get("file")
    page_from = request.form.get("page_from")
    page_to = request.form.get("page_to")
    amount = request.form.get("amount")

    if not file:
        return jsonify({"error": "No file"}), 400

    filename = secure_filename(file.filename)
    save_path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(save_path)

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        INSERT INTO print_jobs
        (filename, page_from, page_to, amount, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        filename,
        page_from,
        page_to,
        amount,
        "PENDING",
        datetime.now().isoformat()
    ))
    conn.commit()
    conn.close()

    return jsonify({"message": "Uploaded & job created"}), 200

# ---------------- GET PENDING JOB ----------------
@app.route("/print-jobs", methods=["GET"])
def get_print_jobs():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        SELECT id, filename, page_from, page_to
        FROM print_jobs
        WHERE status='PENDING'
        ORDER BY id ASC
        LIMIT 1
    """)
    row = c.fetchone()
    conn.close()

    if not row:
        return jsonify({"message": "No jobs"}), 200

    return jsonify({
        "job_id": row[0],
        "filename": row[1],
        "page_from": row[2],
        "page_to": row[3],
        "file_url": f"/download/{row[1]}"
    })

# ---------------- DOWNLOAD PDF ----------------
@app.route("/download/<filename>")
def download_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

# ---------------- UPDATE STATUS ----------------
@app.route("/update-status", methods=["POST"])
def update_status():
    job_id = request.json.get("job_id")
    status = request.json.get("status")

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        UPDATE print_jobs SET status=? WHERE id=?
    """, (status, job_id))
    conn.commit()
    conn.close()

    return jsonify({"message": "Status updated"})

# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
