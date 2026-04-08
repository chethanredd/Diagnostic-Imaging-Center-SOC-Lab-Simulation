#!/usr/bin/env bash
set -e

# ── Ensure monitored log files exist ─────────────────────────────
mkdir -p /var/log/nginx /var/log/portal
rm -f /var/log/nginx/access.log /var/log/nginx/error.log
touch /var/log/nginx/access.log /var/log/nginx/error.log
touch /var/log/portal/auth.log

# ── Start Flask portal (handles portal login events) ─────────────
python3 /opt/portal.py &

# ── Start realistic traffic generator (background) ───────────────
if [[ -f /opt/scripts/realistic_traffic.py ]]; then
  echo "[WEB] Starting realistic traffic generator..."
  python3 /opt/scripts/realistic_traffic.py --host web &
fi

# ── Start nginx ───────────────────────────────────────────────────
exec nginx -g 'daemon off;'
