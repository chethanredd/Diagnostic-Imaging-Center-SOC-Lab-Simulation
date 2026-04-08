#!/usr/bin/env python3
"""
Create baseline Shuffle workflows from scripts/shuffle_playbooks.json.

This script is idempotent by workflow name: existing names are skipped.
Authentication uses SHUFFLE_API_KEY if provided, otherwise it attempts to
extract the ops API key from dic-shuffle-backend logs.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from urllib import error, request


BASE_URL = os.environ.get("SHUFFLE_BASE_URL", "http://localhost:5001").rstrip("/")
PLAYBOOK_FILE = Path(__file__).resolve().parent / "shuffle_playbooks.json"
TIMEOUT_SECONDS = 3


def http_json(method: str, url: str, token: str, payload: dict | None = None):
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    req = request.Request(url=url, method=method, data=data)
    # Use cookies for auth, omit Authorization to prevent 401
    req.add_header("Cookie", f"session_token={token}; __session={token}")
    req.add_header("Content-Type", "application/json")
    with request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
        body = resp.read().decode("utf-8", errors="replace")
        if not body.strip():
            return None
        return json.loads(body)

def login_and_get_token() -> str:
    url = f"{BASE_URL}/api/v1/login"
    payload = {"username": "socadmin", "password": "SOCAdmin!2026"}
    data = json.dumps(payload).encode("utf-8")
    req = request.Request(url=url, method="POST", data=data)
    req.add_header("Content-Type", "application/json")
    try:
        with request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            resp_data = json.loads(body)
            for cookie in resp_data.get("cookies", []):
                if cookie.get("key") == "session_token":
                    return cookie.get("value", "")
            return ""
    except Exception as exc:
        print(f"[shuffle-import] login failed: {exc}")
        return ""


def wait_shuffle_ready(max_attempts: int = 30, delay: int = 2) -> bool:
    url = f"{BASE_URL}/api/v1/docs"
    for _ in range(max_attempts):
        try:
            with request.urlopen(url, timeout=TIMEOUT_SECONDS) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(delay)
    return False


def read_api_key() -> str:
    return login_and_get_token()


def get_existing_workflow_names(token: str) -> set[str]:
    data = http_json("GET", f"{BASE_URL}/api/v1/workflows", token)
    if isinstance(data, list):
        return {str(item.get("name", "")).strip() for item in data if isinstance(item, dict)}
    return set()


def main() -> int:
    if not PLAYBOOK_FILE.exists():
        print("[shuffle-import] playbook file not found; skipping.")
        return 0

    if not wait_shuffle_ready():
        print("[shuffle-import] Shuffle API not ready; skipping.")
        return 0

    token = read_api_key()
    if not token:
        print("[shuffle-import] could not resolve API key; skipping.")
        return 0

    try:
        with PLAYBOOK_FILE.open("r", encoding="utf-8") as f:
            playbooks = json.load(f)
    except Exception as exc:
        print(f"[shuffle-import] failed reading playbooks: {exc}")
        return 0

    if not isinstance(playbooks, list):
        print("[shuffle-import] invalid playbook format; expected array.")
        return 0

    try:
        existing = get_existing_workflow_names(token)
    except Exception as exc:
        print(f"[shuffle-import] failed listing existing workflows: {exc}")
        return 0

    created = 0
    skipped = 0
    for item in playbooks:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        if not name:
            continue
        description = str(item.get("description", "")).strip()

        if name in existing:
            skipped += 1
            continue

        try:
            http_json(
                "POST",
                f"{BASE_URL}/api/v1/workflows",
                token,
                {"name": name, "description": description},
            )
            created += 1
            existing.add(name)
        except error.HTTPError as exc:
            print(f"[shuffle-import] failed creating '{name}': HTTP {exc.code}")
        except Exception as exc:
            print(f"[shuffle-import] failed creating '{name}': {exc}")

    print(f"[shuffle-import] created={created} skipped={skipped}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
