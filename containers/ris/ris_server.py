#!/usr/bin/env python3
"""
ris_server.py — Radiology Information System (RIS) Simulator
Simulates HL7 v2.x ADT/ORM message handling and study management.
Listens on:
  - :8080  HTTP REST API
  - :2575  HL7 MLLP listener
"""
import json
import logging
import os
import socket
import threading
import time
from datetime import datetime, timedelta
from typing import Optional
import random

from flask import Flask, jsonify, request, render_template_string, redirect, session
from flask_cors import CORS

# ── Logging ─────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [RIS] %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler("/var/log/ris/ris.log"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("ris")

# ── Flask App ────────────────────────────────────────────────────
app = Flask("DIC-RIS")
app.secret_key = os.environ.get("RIS_SECRET_KEY", "dic-ris-secret-key")
CORS(app)
RIS_USERNAME = os.environ.get("RIS_USERNAME", "radiologist")
RIS_PASSWORD = os.environ.get("RIS_PASSWORD", "Radiology#2026")

# In-memory study database
STUDIES: list[dict] = []
PATIENTS: list[dict] = []

# Seed with sample data
SAMPLE_PATIENTS = [
    {"id": f"DIC{i:06d}", "name": f"Patient^{i:03d}", "dob": "19700101", "sex": "M"}
    for i in range(1, 21)
]
PROCEDURES = ["CT Chest", "CT Abdomen", "MRI Brain", "MRI Spine", "X-Ray Chest",
               "CT Head", "MRI Knee", "CT Pelvis", "X-Ray Hand", "MRI Shoulder"]

def seed_data():
    """Seed RIS with sample patient/study data."""
    for p in SAMPLE_PATIENTS:
        PATIENTS.append(p)
        for j in range(random.randint(1, 3)):
            STUDIES.append({
                "accession":  f"ACC{len(STUDIES):06d}",
                "patient_id": p["id"],
                "patient_name": p["name"],
                "procedure":  random.choice(PROCEDURES),
                "status":     random.choice(["SCHEDULED", "IN_PROGRESS", "COMPLETE", "READ"]),
                "modality":   random.choice(["CT", "MR", "CR", "DX"]),
                "scheduled":  (datetime.now() - timedelta(days=random.randint(0, 30))).isoformat(),
                "radiologist": random.choice(["Dr.Smith", "Dr.Jones", "Dr.Patel"]),
                "pacs_linked": True,
            })

seed_data()

# ── HTML Template ────────────────────────────────────────────────
RIS_UI = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>DIC Radiology Information System</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'Segoe UI', sans-serif; background: #0d1117; color: #c9d1d9; }
  header { background: #1a2332; padding: 16px 24px; border-bottom: 2px solid #3a7bd5; display:flex; align-items:center; gap:12px; }
  header h1 { font-size: 18px; color: #3a7bd5; }
  header span { font-size: 12px; color: #58a6ff; background:#1d3557; padding:3px 8px; border-radius:12px; }
  .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; padding: 20px; }
  .card { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 16px; }
  .card h2 { font-size: 14px; color: #8b949e; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 12px; }
  table { width: 100%; border-collapse: collapse; font-size: 13px; }
  th { text-align: left; padding: 8px 6px; color: #58a6ff; border-bottom: 1px solid #30363d; }
  td { padding: 7px 6px; border-bottom: 1px solid #21262d; }
  .badge { padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 600; }
  .SCHEDULED { background:#1d3557; color:#58a6ff; }
  .IN_PROGRESS { background:#332a00; color:#f0c040; }
  .COMPLETE { background:#1a3a1a; color:#56d364; }
  .READ { background:#2d1b69; color:#a78bfa; }
  .stats { display:flex; gap:12px; padding:16px 20px; }
  .stat-box { background:#161b22; border:1px solid #30363d; border-radius:8px; padding:14px 20px; flex:1; text-align:center; }
  .stat-box .n { font-size:28px; font-weight:700; color:#58a6ff; }
  .stat-box .l { font-size:12px; color:#8b949e; margin-top:4px; }
  footer { padding:12px 24px; font-size:11px; color:#8b949e; text-align:center; border-top:1px solid #21262d; }
</style>
</head>
<body>
<header>
  <h1>🏥 Diagnostic Imaging Center — Radiology Information System</h1>
  <span>HL7 v2.5 · DICOM Worklist · HIPAA Compliant</span>
  <span style="margin-left:auto; color:#56d364;">● SYSTEM ONLINE</span>
</header>
<div class="stats">
  <div class="stat-box"><div class="n">{{ patients }}</div><div class="l">Registered Patients</div></div>
  <div class="stat-box"><div class="n">{{ studies }}</div><div class="l">Total Studies</div></div>
  <div class="stat-box"><div class="n">{{ pending }}</div><div class="l">Pending Read</div></div>
  <div class="stat-box"><div class="n">{{ today }}</div><div class="l">Today's Orders</div></div>
</div>
<div class="grid">
  <div class="card">
    <h2>📋 Recent Study Orders</h2>
    <table>
      <thead><tr><th>Accession</th><th>Patient</th><th>Procedure</th><th>Status</th></tr></thead>
      <tbody>
        {% for s in studies_list %}
        <tr>
          <td>{{ s.accession }}</td>
          <td>{{ s.patient_id }}</td>
          <td>{{ s.procedure }}</td>
          <td><span class="badge {{ s.status }}">{{ s.status }}</span></td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
  <div class="card">
    <h2>👥 Registered Patients</h2>
    <table>
      <thead><tr><th>Patient ID</th><th>Name</th><th>DOB</th><th>Sex</th></tr></thead>
      <tbody>
        {% for p in patients_list %}
        <tr>
          <td>{{ p.id }}</td>
          <td>{{ p.name }}</td>
          <td>{{ p.dob }}</td>
          <td>{{ p.sex }}</td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
</div>
<footer>DIC RIS v2.0 | HL7 MLLP Listener: :2575 | REST API: :8080/api | SOC Monitored</footer>
</body>
</html>
"""

RIS_LOGIN_UI = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>DIC RIS Login</title>
<style>
  body { font-family: 'Segoe UI', sans-serif; background:#0d1117; color:#c9d1d9; display:flex; align-items:center; justify-content:center; height:100vh; margin:0; }
  .box { width:360px; background:#161b22; border:1px solid #30363d; border-radius:8px; padding:24px; }
  h2 { margin:0 0 14px; color:#58a6ff; }
  input { width:100%; box-sizing:border-box; padding:10px; margin:8px 0; border-radius:4px; border:1px solid #30363d; background:#0d1117; color:#c9d1d9; }
  button { width:100%; padding:10px; margin-top:8px; background:#238636; border:none; border-radius:4px; color:#fff; cursor:pointer; }
  p { font-size:12px; color:#8b949e; margin-top:10px; }
</style>
</head>
<body>
  <div class="box">
    <h2>DIC RIS Login</h2>
    <form method="POST" action="/login">
      <input name="username" placeholder="Username" required>
      <input name="password" type="password" placeholder="Password" required>
      <button type="submit">Sign in</button>
    </form>
    <p>All login attempts are audited for SOC monitoring.</p>
  </div>
</body>
</html>
"""

# ── REST Endpoints ───────────────────────────────────────────────

@app.route("/")
def index():
    if not session.get("ris_authenticated"):
        return render_template_string(RIS_LOGIN_UI)
    today_count = sum(1 for s in STUDIES if "today" in s.get("scheduled", ""))
    return render_template_string(
        RIS_UI,
        patients=len(PATIENTS),
        studies=len(STUDIES),
        pending=sum(1 for s in STUDIES if s["status"] in ("SCHEDULED", "IN_PROGRESS")),
        today=random.randint(3, 12),
        studies_list=STUDIES[:15],
        patients_list=PATIENTS[:15],
    )


@app.route("/login", methods=["POST"])
def login():
    username = request.form.get("username", "")
    password = request.form.get("password", "")
    src_ip = request.remote_addr
    success = username == RIS_USERNAME and password == RIS_PASSWORD
    result = "SUCCESS" if success else "FAILED"
    log.info("RIS_LOGIN %s src=%s user=%s", result, src_ip, username)
    if success:
        session["ris_authenticated"] = True
        return redirect("/")
    return render_template_string(RIS_LOGIN_UI), 401


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    log.info("RIS_LOGOUT src=%s", request.remote_addr)
    return redirect("/")

@app.route("/api/studies", methods=["GET"])
def list_studies():
    status_filter = request.args.get("status")
    src_ip = request.remote_addr
    log.info(f"REST /api/studies requested from {src_ip}")
    if status_filter:
        return jsonify([s for s in STUDIES if s["status"] == status_filter])
    return jsonify(STUDIES)

@app.route("/api/studies/<accession>", methods=["GET"])
def get_study(accession):
    log.info(f"REST /api/studies/{accession} from {request.remote_addr}")
    study = next((s for s in STUDIES if s["accession"] == accession), None)
    if not study:
        return jsonify({"error": "Not found"}), 404
    return jsonify(study)

@app.route("/api/patients", methods=["GET"])
def list_patients():
    log.info(f"REST /api/patients from {request.remote_addr}")
    return jsonify(PATIENTS)

@app.route("/api/worklist", methods=["GET"])
def worklist():
    """DICOM Modality Worklist endpoint."""
    modality = request.args.get("modality", "CT")
    pending = [s for s in STUDIES if s["status"] == "SCHEDULED" and s["modality"] == modality]
    log.info(f"Worklist query for {modality} from {request.remote_addr}: {len(pending)} items")
    return jsonify({"modality": modality, "worklist": pending})

@app.route("/api/hl7/admit", methods=["POST"])
def hl7_admit():
    """Simulate HL7 ADT-A01 patient admission."""
    data = request.json or {}
    src_ip = request.remote_addr
    log.info(f"HL7 ADT-A01 admission from {src_ip}: patient {data.get('patient_id')}")

    # Security check: flag if from unexpected source
    allowed_sources = ["10.10.10.10", "10.10.10.20", "10.10.0."]
    if not any(src_ip.startswith(a) for a in allowed_sources):
        log.warning(f"SECURITY: HL7 message from unexpected source {src_ip}")

    return jsonify({"status": "ACK", "message": "ADT-A01 processed"})

@app.route("/health")
def health():
    return jsonify({"status": "ok", "service": "DIC-RIS", "studies": len(STUDIES)})

# ── HL7 MLLP Listener ───────────────────────────────────────────
MLLP_START = b"\x0b"
MLLP_END   = b"\x1c\x0d"

def handle_hl7_client(conn, addr):
    """Handle a single HL7 MLLP connection."""
    log.info(f"HL7 MLLP connection from {addr[0]}:{addr[1]}")
    try:
        data = b""
        while True:
            chunk = conn.recv(4096)
            if not chunk:
                break
            data += chunk
            if MLLP_END in data:
                break
        # Extract HL7 message (strip MLLP wrapping)
        msg = data.replace(MLLP_START, b"").replace(MLLP_END, b"").decode("latin-1", errors="replace")
        log.info(f"HL7 Message from {addr[0]}: {msg[:120]}...")

        # Security check: unexpected source
        expected_hl7_sources = ["10.10.10.10", "10.10.10.20", "10.10.10.30", "10.10.10.31"]
        if not any(addr[0].startswith(s) for s in expected_hl7_sources):
            log.warning(f"SECURITY ALERT: HL7 from unauthorized source {addr[0]} — Suricata SID 9000020")

        # Send ACK
        ack = (f"MSH|^~\\&|DIC-RIS|DIC|SENDER|DIC|{datetime.now():%Y%m%d%H%M%S}||ACK|"
               f"ACK{int(time.time())}|P|2.5\rMSA|AA|OK|Message accepted\r")
        conn.sendall(MLLP_START + ack.encode() + MLLP_END)
    except Exception as e:
        log.error(f"HL7 handler error: {e}")
    finally:
        conn.close()

def hl7_listener():
    """HL7 MLLP TCP listener on port 2575."""
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("0.0.0.0", 2575))
    srv.listen(5)
    log.info("HL7 MLLP listener started on :2575")
    while True:
        conn, addr = srv.accept()
        t = threading.Thread(target=handle_hl7_client, args=(conn, addr), daemon=True)
        t.start()

if __name__ == "__main__":
    # Start HL7 listener in background
    hl7_thread = threading.Thread(target=hl7_listener, daemon=True)
    hl7_thread.start()

    log.info("DIC RIS Server starting — HTTP: :8080, HL7 MLLP: :2575")
    app.run(host="0.0.0.0", port=8080, threaded=True, debug=False)
