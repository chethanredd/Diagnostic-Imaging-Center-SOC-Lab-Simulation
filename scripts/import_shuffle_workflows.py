#!/usr/bin/env python3
"""
Create baseline Shuffle workflow shells from scripts/shuffle_playbooks.json.

This script is idempotent by workflow name: existing names are skipped.
Authentication uses SHUFFLE_API_KEY if provided, otherwise it attempts to
extract the ops API key from dic-shuffle-backend logs.

Note: the bundled JSON contains full trigger/action templates for the lab,
but this bootstrap path only creates the workflow shell entry in Shuffle.
Use the JSON as the source of truth when building out the workflow in the UI.
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
DEFAULT_USERNAME = os.environ.get("SHUFFLE_DEFAULT_USERNAME", "socadmin")
DEFAULT_PASSWORD = os.environ.get("SHUFFLE_DEFAULT_PASSWORD", "")
PLAYBOOK_FILE = Path(__file__).resolve().parent / "shuffle_playbooks.json"
ENV_FILE = Path(__file__).resolve().parents[1] / ".env"
TIMEOUT_SECONDS = 3


def load_env_file() -> None:
    if not ENV_FILE.exists():
        return

    try:
        for raw_line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
    except Exception as exc:
        print(f"[shuffle-import] warning: failed reading .env: {exc}")


load_env_file()
DEFAULT_USERNAME = os.environ.get("SHUFFLE_DEFAULT_USERNAME", DEFAULT_USERNAME)
DEFAULT_PASSWORD = os.environ.get("SHUFFLE_DEFAULT_PASSWORD", DEFAULT_PASSWORD)


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
    if not DEFAULT_PASSWORD:
        print("[shuffle-import] missing SHUFFLE_DEFAULT_PASSWORD environment variable.")
        return ""
    payload = {"username": DEFAULT_USERNAME, "password": DEFAULT_PASSWORD}
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


def load_playbooks() -> list[dict] | None:
    if not PLAYBOOK_FILE.exists():
        print("[shuffle-import] playbook file not found; skipping.")
        return None

    try:
        with PLAYBOOK_FILE.open("r", encoding="utf-8") as f:
            playbooks = json.load(f)
    except Exception as exc:
        print(f"[shuffle-import] failed reading playbooks: {exc}")
        return None

    if not isinstance(playbooks, list):
        print("[shuffle-import] invalid playbook format; expected array.")
        return None

    return playbooks


def import_workflows(playbooks: list[dict], token: str) -> tuple[int, int]:
    try:
        existing = get_existing_workflow_names(token)
    except Exception as exc:
        print(f"[shuffle-import] failed listing existing workflows: {exc}")
        return -1, -1

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

    return created, skipped


def main() -> int:
    playbooks = load_playbooks()
    if playbooks is None:
        return 0

    if not wait_shuffle_ready():
        print("[shuffle-import] Shuffle API not ready; skipping.")
        return 1

    token = read_api_key()
    if not token:
        print("[shuffle-import] could not resolve API key; skipping.")
        return 1

    created, skipped = import_workflows(playbooks, token)
    if created < 0:
        return 1

    print(f"[shuffle-import] created={created} skipped={skipped}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
