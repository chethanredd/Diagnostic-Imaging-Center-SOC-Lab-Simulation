#!/usr/bin/env python3
"""
realistic_traffic.py — DIC SOC Lab Realistic Log Generator
===========================================================
Injects realistic clinical workflow events into container logs so
Wazuh has continuous, meaningful data to collect and index.

Events generated:
  - Auth  : SSH logins/logouts, sudo commands, failed auth
  - Portal: Patient login success/fail (nginx access log)
  - PACS  : Orthanc DICOM C-STORE receives (MR/CT studies)
  - RIS   : HL7 ADT patient admission/discharge/transfer
  - System: Cron jobs, service health checks
  - Anomaly: Off-hours access bursts, failed-auth spikes (scheduled)

Usage:
  python3 realistic_traffic.py --host pacs
  python3 realistic_traffic.py --host ris
  python3 realistic_traffic.py --host web
  python3 realistic_traffic.py --host all --rate 1.5
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import logging
import os
import random
import signal
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from typing import Callable

# ── Logging ─────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [TRAFFIC] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("traffic-gen")

# ── Module-level random state (avoids repeated re-imports) ──────────────────
_RNG = random.Random()


def _rand_hash() -> str:
    """Fast SHA-256 hash snippet for SSH key fingerprints."""
    return hashlib.sha256(os.urandom(8)).hexdigest()[:43]


# ── Domain data ─────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Staff:
    user: str
    role: str
    ip:   str


@dataclass(frozen=True)
class Study:
    modality: str
    description: str


STAFF: list[Staff] = [
    Staff("radiologist1", "radiologist", "10.10.20.11"),
    Staff("radiologist2", "radiologist", "10.10.20.12"),
    Staff("tech_ct",      "ct-tech",     "10.10.10.31"),
    Staff("tech_mri",     "mri-tech",    "10.10.10.30"),
    Staff("nurse_icu",    "nurse",        "10.10.20.21"),
    Staff("admin_it",     "it-admin",    "10.10.20.10"),
    Staff("pacs_svc",     "service",     "10.10.10.10"),
]

# Pre-filtered role groups (computed once, not on every event call)
_RADIOLOGISTS  = [s for s in STAFF if s.role == "radiologist"]
_CLINICAL      = [s for s in STAFF if s.role in ("radiologist", "ct-tech", "mri-tech", "it-admin")]
_IT_ADMINS     = [s for s in STAFF if s.role == "it-admin"]
_NON_SERVICE   = [s for s in STAFF if s.role not in ("service",)]

PATIENTS: list[str] = [
    "PT-2024-001", "PT-2024-002", "PT-2024-003", "PT-2024-007",
    "PT-2024-015", "PT-2024-022", "PT-2024-031", "PT-2024-044",
]

STUDIES: list[Study] = [
    Study("CT", "Chest Abdomen Pelvis with contrast"),
    Study("MR", "Brain MRI without contrast"),
    Study("CT", "CT Head without contrast"),
    Study("MR", "Spine MRI lumbar"),
    Study("CT", "CT Thorax HRCT"),
    Study("MR", "MRI Knee with contrast"),
    Study("CT", "CT Abdomen pelvis"),
    Study("MR", "MRI Brain with and without"),
]

SUDO_COMMANDS: list[str] = [
    "/usr/bin/systemctl status orthanc",
    "/usr/bin/systemctl restart wazuh-agent",
    "/usr/bin/journalctl -u orthanc -n 50",
    "/usr/bin/tail -f /var/log/orthanc/orthanc.log",
    "/usr/bin/systemctl status nginx",
    "/usr/bin/df -h",
    "/usr/bin/top -bn1",
]

CRON_JOBS: list[str] = [
    "/usr/bin/find /opt/dicom_test -mtime +30 -delete",
    "/opt/backup/dicom_backup.sh >> /var/log/backup.log 2>&1",
    "/usr/bin/systemctl reload nginx",
    "/usr/sbin/service orthanc status",
    "/opt/soc/anomaly_detector.py --stdin < /var/ossec/logs/alerts/alerts.log",
]

SERVICES: list[tuple[str, str]] = [
    ("orthanc",     "active (running)"),
    ("wazuh-agent", "active (running)"),
    ("nginx",       "active (running)"),
    ("ris_server",  "active (running)"),
    ("ssh",         "active (running)"),
]

PORTAL_AGENTS: list[str] = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)",
]

PORTAL_USERS: list[str] = [
    "patient1", "patient2", "dr.smith",
    "radiologist1", "nurse_icu", "patient3",
]

# ── Counters (thread-safe via lock) ─────────────────────────────────────────
_stats: dict[str, int] = {}
_stats_lock = threading.Lock()


def _inc(key: str) -> None:
    with _stats_lock:
        _stats[key] = _stats.get(key, 0) + 1


def _print_stats() -> None:
    with _stats_lock:
        total = sum(_stats.values())
        log.info(f"── Stats ── total={total} " +
                 " ".join(f"{k}={v}" for k, v in sorted(_stats.items())))


# ── Syslog writer ────────────────────────────────────────────────────────────
# Open log file handles once per process rather than per event.
_log_handles: dict[str, object] = {}
_log_lock = threading.Lock()


def _get_handle(path: str):
    """Return a cached, open file handle for `path` (create dir if needed)."""
    if path not in _log_handles:
        with _log_lock:
            if path not in _log_handles:          # double-checked locking
                os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
                try:
                    _log_handles[path] = open(path, "a", buffering=1)  # line-buffered
                except PermissionError:
                    _log_handles[path] = None
    return _log_handles.get(path)


def write_syslog(message: str, facility: str = "auth", severity: str = "notice") -> None:
    """
    Append a syslog-format line to /var/log/syslog and /var/log/auth.log.
    Uses cached file handles — no open/close per call.
    Skips the `logger` subprocess entirely; it adds ~2–5 ms latency per event
    and the Wazuh agent reads the flat log files directly anyway.
    """
    hostname = _HOSTNAME
    ts       = datetime.datetime.now().strftime("%b %d %H:%M:%S")
    line     = f"{ts} {hostname} {facility}: {message}\n"

    for path in ("/var/log/syslog", "/var/log/auth.log"):
        fh = _get_handle(path)
        if fh:
            try:
                fh.write(line)
            except OSError:
                pass


def write_applog(path: str, line: str) -> None:
    """Append one line to an application log file using a cached handle."""
    fh = _get_handle(path)
    if fh:
        try:
            fh.write(line + "\n")
        except OSError:
            pass


# Cache hostname lookup
_HOSTNAME: str = os.uname().nodename


# ── Event functions ──────────────────────────────────────────────────────────

def event_ssh_login(staff: Staff) -> None:
    """
    Generate SSH session open + close pair.
    FIX: removed blocking time.sleep() — caller controls pacing.
    """
    port = _RNG.randint(49152, 65535)
    pid  = _RNG.randint(1000, 9999)

    write_syslog(
        f"sshd[{pid}]: Accepted publickey for {staff.user} from {staff.ip} "
        f"port {port} ssh2: RSA SHA256:{_rand_hash()}",
        "auth"
    )
    write_syslog(
        f"sshd[{pid}]: pam_unix(sshd:session): session opened for user "
        f"{staff.user} by (uid=0)",
        "auth"
    )
    # Close session in same tick (realistic log pattern without blocking)
    write_syslog(
        f"sshd[{pid}]: pam_unix(sshd:session): session closed for user {staff.user}",
        "auth"
    )
    _inc("ssh_login")
    log.info(f"SSH LOGIN  : {staff.user} from {staff.ip}")


def event_ssh_fail(ip: str | None = None, burst: int = 1) -> None:
    """
    Generate failed SSH authentication.
    `burst` > 1 writes multiple rapid failures — triggers Wazuh brute-force rules.
    """
    if ip is None:
        ip = f"10.10.{_RNG.randint(1, 50)}.{_RNG.randint(1, 254)}"

    bad_users = ["root", "admin", "test", "ubuntu", "orthanc", "oracle", "pi"]
    for _ in range(burst):
        pid  = _RNG.randint(1000, 9999)
        user = _RNG.choice(bad_users)
        write_syslog(
            f"sshd[{pid}]: Failed password for invalid user {user} from {ip} "
            f"port {_RNG.randint(49152, 65535)} ssh2",
            "auth", "warning"
        )
    _inc("ssh_fail")
    log.info(f"SSH FAIL   : {burst}x attempts from {ip}")


def event_sudo(staff: Staff) -> None:
    """Simulate a privileged sudo command by clinical/IT staff."""
    pid = _RNG.randint(1000, 9999)
    cmd = _RNG.choice(SUDO_COMMANDS)
    write_syslog(
        f"sudo:  {staff.user} : TTY=pts/0 ; PWD=/home/{staff.user} ; "
        f"USER=root ; COMMAND={cmd}",
        "auth"
    )
    _inc("sudo")
    log.info(f"SUDO       : {staff.user} → {cmd[:50]}")


def event_pacs_dicom() -> None:
    """Simulate Orthanc PACS receiving a DICOM study from a modality."""
    study   = _RNG.choice(STUDIES)
    patient = _RNG.choice(PATIENTS)
    uid     = (f"1.2.840.10008."
               f"{_RNG.randint(1000, 9999)}."
               f"{_RNG.randint(10000, 99999)}")
    count   = _RNG.randint(40, 320)
    ts      = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    lines = [
        f"W{ts}Z Orthanc Received DICOM instance for patient {patient} modality {study.modality}",
        f"W{ts}Z Orthanc Study UID: {uid}",
        f"W{ts}Z Orthanc Study description: {study.description}",
        f"W{ts}Z Orthanc Storing {count} DICOM instances",
        f"W{ts}Z Orthanc C-STORE completed successfully for {patient}",
    ]
    for line in lines:
        write_applog("/var/log/orthanc/orthanc.log", line)
        write_syslog(f"orthanc: {line[25:]}", "daemon")

    _inc("dicom")
    log.info(f"DICOM RECV : {study.modality} — {study.description} "
             f"patient={patient} instances={count}")


def event_ris_hl7() -> None:
    """Simulate RIS processing an HL7 ADT message."""
    patient    = _RNG.choice(PATIENTS)
    event_type = _RNG.choice(["Admission", "Discharge", "Transfer",
                               "OrderCreated", "ResultArrived"])
    source     = _RNG.choice(["RIS", "HIS", "EMR"])
    pid        = _RNG.randint(1000, 9999)
    ts         = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    write_applog(
        "/var/log/ris/ris.log",
        f"{ts} INFO [HL7-ADT] {event_type} event received for patient "
        f"{patient} from {source} [pid={pid}]"
    )
    write_syslog(
        f"ris_server[{pid}]: HL7 {event_type} patient={patient} src={source}",
        "daemon"
    )
    _inc("hl7")
    log.info(f"HL7 {event_type:14s}: patient={patient} src={source}")


def event_portal_login(success: bool = True) -> None:
    """Simulate a patient portal login — writes to nginx access.log."""
    user   = _RNG.choice(PORTAL_USERS)
    ip     = f"192.168.{_RNG.randint(1, 10)}.{_RNG.randint(1, 254)}"
    code   = 200 if success else 401
    ts_http = datetime.datetime.now().strftime("%d/%b/%Y:%H:%M:%S +0000")
    path   = _RNG.choice(["/login", "/portal", "/signin", "/auth"])
    agent  = _RNG.choice(PORTAL_AGENTS)
    size   = _RNG.randint(200, 4096)

    # nginx access log (Wazuh rule 31101 reads this)
    write_applog(
        "/var/log/nginx/access.log",
        f'{ip} - {user} [{ts_http}] "POST {path} HTTP/1.1" {code} {size} "-" "{agent}"'
    )
    # Auth log (Wazuh rule 31106 reads this for credential captures)
    result = "SUCCESS" if success else "FAILED"
    write_syslog(
        f"portal: PORTAL_LOGIN {result} src={ip} user={user} path={path}",
        "daemon", "warning" if not success else "notice"
    )
    # phish capture log (triggers Rule 100013 on CAPTURED CREDENTIALS)
    if not success and _RNG.random() < 0.3:
        write_applog(
            "/var/log/portal/phish_captures.log",
            f"{datetime.datetime.now()} CAPTURED CREDENTIALS: "
            f"{{'username': '{user}', 'password': 'redacted'}} from {ip}"
        )

    _inc("portal_ok" if success else "portal_fail")
    log.info(f"PORTAL {result:7s}: user={user} from={ip} → {path} [{code}]")


def event_cron_job() -> None:
    """Simulate a scheduled cron job execution."""
    pid = _RNG.randint(1000, 9999)
    cmd = _RNG.choice(CRON_JOBS)
    owner = _RNG.choice(["root", "pacs_svc", "orthanc"])
    write_syslog(f"cron[{pid}]: ({owner}) CMD ({cmd})", "cron")
    _inc("cron")
    log.info(f"CRON       : ({owner}) {cmd[:50]}")


def event_service_check() -> None:
    """Simulate systemd service status / watchdog ping."""
    pid        = _RNG.randint(1000, 9999)
    svc, state = _RNG.choice(SERVICES)
    write_syslog(
        f"systemd[{pid}]: {svc}.service: watchdog ping — state={state}",
        "daemon"
    )
    _inc("svc_check")


def event_anomaly_burst() -> None:
    """
    Off-hours anomaly: rapid SSH failures from a single external IP.
    Triggers Wazuh Rule 100005 (brute force threshold).
    Scheduled during night hours or randomly at low probability.
    """
    attacker_ip = f"185.{_RNG.randint(100, 220)}.{_RNG.randint(1, 254)}.{_RNG.randint(1, 254)}"
    burst_size  = _RNG.randint(12, 25)
    log.info(f"ANOMALY    : SSH brute burst {burst_size}x from {attacker_ip}")
    event_ssh_fail(ip=attacker_ip, burst=burst_size)
    _inc("anomaly_burst")


def event_off_hours_dicom() -> None:
    """
    Off-hours DICOM access anomaly.
    Triggers Wazuh Rule 100016 (after-hours file access).
    """
    staff = _RNG.choice(_RADIOLOGISTS)
    write_syslog(
        f"sshd[{_RNG.randint(1000,9999)}]: Accepted password for {staff.user} "
        f"from {staff.ip} port {_RNG.randint(49152,65535)} ssh2",
        "auth"
    )
    # Simulate accessing DICOM files at night
    event_pacs_dicom()
    _inc("off_hours")
    log.info(f"OFF-HOURS  : DICOM access by {staff.user} at "
             f"{datetime.datetime.now().strftime('%H:%M')}")


# ── Scenario tables ──────────────────────────────────────────────────────────
# Each entry: (callable, weight)
# Weights are normalised automatically by random.choices.

def _is_off_hours() -> bool:
    h = datetime.datetime.now().hour
    return h < 6 or h >= 20


def _pacs_scenario() -> None:
    scenarios: list[tuple[Callable, int]] = [
        (event_pacs_dicom,                          35),
        (lambda: event_ssh_login(_RNG.choice(_CLINICAL)), 18),
        (event_ssh_fail,                             4),
        (lambda: event_sudo(_RNG.choice(_IT_ADMINS)), 8),
        (lambda: event_portal_login(False),          4),
        (event_cron_job,                            16),
        (event_service_check,                        8),
        # Off-hours anomaly: always low weight, slightly higher at night
        (event_anomaly_burst,  3 if _is_off_hours() else 1),
        (event_off_hours_dicom, 4 if _is_off_hours() else 0),
    ]
    fns, weights = zip(*scenarios)
    _RNG.choices(fns, weights=weights, k=1)[0]()


def _ris_scenario() -> None:
    scenarios: list[tuple[Callable, int]] = [
        (event_ris_hl7,                                      40),
        (lambda: event_ssh_login(_RNG.choice(_NON_SERVICE)), 18),
        (event_ssh_fail,                                      4),
        (lambda: event_portal_login(True),                   10),
        (lambda: event_portal_login(False),                   5),
        (event_cron_job,                                     18),
        (event_anomaly_burst, 3 if _is_off_hours() else 1),
    ]
    fns, weights = zip(*scenarios)
    _RNG.choices(fns, weights=weights, k=1)[0]()


def _web_scenario() -> None:
    # Web server heavily skewed toward portal events
    success = _RNG.random() > 0.25   # 75% success rate
    event_portal_login(success=success)

    # Occasional background noise
    if _RNG.random() < 0.05:
        event_anomaly_burst()


# ── Host loop ────────────────────────────────────────────────────────────────

def run_loop(scenario_fn: Callable, label: str, rate: float) -> None:
    """
    Generic event loop.
    `rate`: multiplier on sleep interval. 1.0 = normal pace,
            2.0 = twice as fast, 0.5 = half speed.
    """
    log.info(f"[{label}] Traffic loop started (rate={rate:.1f}x)")
    stats_interval = 60          # print stats every N seconds
    last_stats     = time.monotonic()
    event_count    = 0

    while True:
        try:
            scenario_fn()
            event_count += 1
        except Exception as exc:
            log.warning(f"[{label}] Event error: {exc}")

        # Adaptive sleep: base 15–60s divided by rate multiplier
        sleep_s = _RNG.uniform(15, 60) / rate
        time.sleep(sleep_s)

        # Periodic stats summary
        now = time.monotonic()
        if now - last_stats >= stats_interval:
            _print_stats()
            last_stats = now


# ── Signal handling ──────────────────────────────────────────────────────────

def _on_exit(signum, frame):
    log.info("Shutting down traffic generator...")
    _print_stats()
    # Flush all open log handles
    for fh in _log_handles.values():
        if fh:
            try:
                fh.flush()
                fh.close()
            except Exception:
                pass
    sys.exit(0)


signal.signal(signal.SIGTERM, _on_exit)
signal.signal(signal.SIGINT,  _on_exit)


# ── Entry point ──────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="DIC SOC Lab — Realistic Traffic Generator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 realistic_traffic.py --host pacs
  python3 realistic_traffic.py --host all --rate 2.0
  python3 realistic_traffic.py --host web --rate 0.5
        """
    )
    parser.add_argument(
        "--host",
        choices=["pacs", "ris", "web", "all"],
        default="pacs",
        help="Which container role to simulate (default: pacs)"
    )
    parser.add_argument(
        "--rate",
        type=float,
        default=1.0,
        help="Event rate multiplier — 1.0=normal, 2.0=double speed (default: 1.0)"
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed for reproducible demos"
    )
    args = parser.parse_args()

    if args.seed is not None:
        _RNG.seed(args.seed)
        log.info(f"Random seed set to {args.seed}")

    if args.rate <= 0:
        parser.error("--rate must be > 0")

    host_map: dict[str, tuple[Callable, str]] = {
        "pacs": (_pacs_scenario, "PACS"),
        "ris":  (_ris_scenario,  "RIS"),
        "web":  (_web_scenario,  "WEB"),
    }

    if args.host == "all":
        # FIX: use Event for clean shutdown instead of joining daemon threads
        threads = [
            threading.Thread(
                target=run_loop,
                args=(fn, label, args.rate),
                name=f"traffic-{label.lower()}",
                daemon=True,
            )
            for fn, label in host_map.values()
        ]
        for t in threads:
            t.start()

        log.info("All 3 traffic loops running (PACS + RIS + WEB). Ctrl+C to stop.")
        # Keep main thread alive — signal handlers on main thread only
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            _on_exit(None, None)
    else:
        fn, label = host_map[args.host]
        run_loop(fn, label, args.rate)


if __name__ == "__main__":
    main()
