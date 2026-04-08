#!/usr/bin/env bash
# ================================================================
# DIC SOC Lab — Stop Script
# Usage: ./stop.sh [--clean]
# ================================================================
CLEAN=false
[[ "${1:-}" == "--clean" ]] && CLEAN=true

echo "[*] Stopping DIC SOC Lab..."
if $CLEAN; then
  docker compose --profile attack down -v --remove-orphans
  rm -rf certs/*
  echo "[+] Lab stopped and volumes cleared."
else
  docker compose --profile attack down --remove-orphans
  echo "[+] Lab stopped. Data preserved. Run './stop.sh --clean' to wipe volumes."
fi
