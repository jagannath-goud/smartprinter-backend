import requests
import time
import os
import subprocess
import win32print
import win32api

# ================= CONFIG =================
API_BASE = "https://api.smartprinter.in"
AGENT_SECRET = "smartprinter_agent_secret"
POLL_INTERVAL = 5

SUMATRA_PATH = r"C:\print_tools\SumatraPDF.exe"
DOWNLOAD_DIR = "downloads"

os.makedirs(DOWNLOAD_DIR, exist_ok=True)

HEADERS = {
    "Authorization": f"Bearer {AGENT_SECRET}"
}

# ================= REAL PRINTER STATUS =================
def get_real_printer_status():
    try:
        printer = win32print.GetDefaultPrinter()
        handle = win32print.OpenPrinter(printer)
        info = win32print.GetPrinter(handle, 2)
        win32print.ClosePrinter(handle)

        if info["Attributes"] & win32print.PRINTER_ATTRIBUTE_WORK_OFFLINE:
            return "OFFLINE", printer

        if info["Status"] != 0:
            return "OFFLINE", printer

        port = info["pPortName"]
        if not port or port.upper().startswith("FILE"):
            return "OFFLINE", printer

        return "ONLINE_IDLE", printer

    except:
        return "OFFLINE", None


# ================= HEARTBEAT =================
def send_heartbeat(status, printer):
    try:
        requests.post(
            f"{API_BASE}/agent/heartbeat",
            json={
                "status": status,
                "printer": printer
            },
            headers=HEADERS,
            timeout=5
        )
    except:
        pass


# ================= CLOUD =================
def fetch_job():
    try:
        r = requests.get(
            f"{API_BASE}/agent/pull-job",
            headers=HEADERS,
            timeout=10
        )
        if r.status_code == 200:
            return r.json()
    except:
        pass
    return None


def download_pdf(job_id):
    path = os.path.join(DOWNLOAD_DIR, f"{job_id}.pdf")
    r = requests.get(
        f"{API_BASE}/agent/download/{job_id}",
        headers=HEADERS,
        stream=True,
        timeout=20
    )
    if r.status_code != 200:
        raise Exception("Download failed")

    with open(path, "wb") as f:
        for chunk in r.iter_content(8192):
            f.write(chunk)

    return path


def print_pdf(pdf, from_p, to_p, copies, printer):
    page_range = f"{from_p}-{to_p}"
    for _ in range(copies):
        subprocess.run([
            SUMATRA_PATH,
            "-print-to",
            printer,
            "-silent",
            "-exit-on-print",
            "-print-settings",
            page_range,
            pdf
        ], check=True)
        time.sleep(3)


def mark_done(job_id):
    requests.post(
        f"{API_BASE}/agent/job-done",
        json={"job_id": job_id},
        headers=HEADERS,
        timeout=5
    )


# ================= MAIN =================
def main():
    print("🖨 VPrint Agent started (REAL STATUS MODE)")

    while True:
        status, printer = get_real_printer_status()

        # 🔥 SEND HEARTBEAT ALWAYS
        send_heartbeat(status, printer)

        print(f"💓 Heartbeat sent → {status} | {printer}")

        if status == "OFFLINE":
            time.sleep(POLL_INTERVAL)
            continue

        job = fetch_job()
        if not job or job.get("status") == "NO_JOB":
            time.sleep(POLL_INTERVAL)
            continue

        try:
            pdf = download_pdf(job["job_id"])
            print_pdf(
                pdf,
                job["from"],
                job["to"],
                job["copies"],
                printer
            )
            mark_done(job["job_id"])
            os.remove(pdf)
            print("✅ Job printed")

        except Exception as e:
            print("❌ Print failed:", e)

        time.sleep(2)


if __name__ == "__main__":
    main()
