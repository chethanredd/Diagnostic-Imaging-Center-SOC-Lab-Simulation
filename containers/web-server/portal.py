#!/usr/bin/env python3
"""Patient portal with audited login events for SOC monitoring."""
import logging
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs

LOG_PATH = "/var/log/portal/auth.log"
os.makedirs("/var/log/portal", exist_ok=True)
logging.basicConfig(filename=LOG_PATH, level=logging.INFO, format="%(asctime)s %(message)s")

PORTAL_USERNAME = os.environ.get("PORTAL_USERNAME", "patient1")
PORTAL_PASSWORD = os.environ.get("PORTAL_PASSWORD", "Patient#2026")

LOGIN_HTML = b"""
<html><head><title>DIC Portal Login</title>
<style>body{font-family:sans-serif;background:#0d47a1;display:flex;align-items:center;justify-content:center;height:100vh;margin:0}
.box{background:white;padding:32px;border-radius:8px;width:360px;box-shadow:0 4px 20px rgba(0,0,0,0.3)}
h2{color:#0d47a1;margin-bottom:20px}input{width:100%;padding:10px;margin:8px 0;border:1px solid #ccc;border-radius:4px;font-size:14px}
button{width:100%;padding:12px;background:#0d47a1;color:white;border:none;border-radius:4px;font-size:15px;cursor:pointer}</style>
</head><body><div class='box'>
<h2>&#127973; DIC Patient Portal</h2>
<form method='POST' action='/login'>
<input name='username' placeholder='Patient ID' required>
<input name='password' type='password' placeholder='Password' required>
<button type='submit'>Sign In</button>
</form><p style='font-size:12px;color:#555;margin-top:12px'>All login attempts are audited.</p></div></body></html>
"""

OK_HTML = b"""
<html><head><title>DIC Portal</title></head>
<body style='font-family:sans-serif;background:#f7f9fc;padding:30px'>
<h2>Login successful</h2>
<p>Welcome to the DIC patient portal.</p>
<p><a href='/'>Back to login</a></p>
</body></html>
"""

class PhishHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # suppress default logging

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(LOGIN_HTML)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8", errors="replace")
        params = parse_qs(body)
        creds = {k: v[0] for k, v in params.items()}
        src = self.client_address[0]

        username = creds.get("username", "")
        password = creds.get("password", "")
        success = username == PORTAL_USERNAME and password == PORTAL_PASSWORD
        result = "SUCCESS" if success else "FAILED"
        logging.info(
            "PORTAL_LOGIN %s src=%s user=%s ua=%s",
            result,
            src,
            username,
            self.headers.get("User-Agent", "-"),
        )
        print(f"[PORTAL] Login {result} from {src} user={username}", flush=True)

        if success:
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(OK_HTML)
            return

        self.send_response(401)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(LOGIN_HTML)


print("[PORTAL] Audited login portal server on :8888", flush=True)
HTTPServer(("0.0.0.0", 8888), PhishHandler).serve_forever()
