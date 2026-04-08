#!/usr/bin/env bash
set -e

# ── Ensure monitored log files exist before Wazuh agent starts ──
touch /var/log/auth.log /var/log/syslog
mkdir -p /var/log/ris
touch /var/log/ris/ris.log
chmod 640 /var/log/auth.log

# Configure and enroll Wazuh agent (best-effort)
if [[ -f /var/ossec/etc/ossec.conf.tmpl ]]; then
  sed "s|WAZUH_MANAGER_IP|${WAZUH_MANAGER:-10.10.0.10}|g" \
      /var/ossec/etc/ossec.conf.tmpl > /var/ossec/etc/ossec.conf

  if [[ -n "${ENROLLMENT_PASSWORD:-}" ]]; then
    echo "${ENROLLMENT_PASSWORD}" > /var/ossec/etc/authd.pass
    chmod 640 /var/ossec/etc/authd.pass
  fi

  echo "[RIS] Waiting 15s for Wazuh manager to be ready..."
  sleep 15

  # Try enrollment once if key is absent
  if [[ ! -s /var/ossec/etc/client.keys ]]; then
    /var/ossec/bin/agent-auth -m "${WAZUH_MANAGER:-10.10.0.10}" \
      -p 1515 \
      -A "ris-server" 2>/dev/null || true
  fi

  /var/ossec/bin/wazuh-control start 2>/dev/null || \
  /var/ossec/bin/wazuh-agentd 2>/dev/null || true
fi

# ── Start realistic traffic generator (background) ─────────────────
if [[ -f /opt/scripts/realistic_traffic.py ]]; then
  echo "[RIS] Starting realistic traffic generator..."
  python3 /opt/scripts/realistic_traffic.py --host ris &
elif [[ -f /opt/realistic_traffic.py ]]; then
  python3 /opt/realistic_traffic.py --host ris &
fi

echo "[RIS] Starting DIC Radiology Information System..."
mkdir -p /var/log/ris
exec python3 /opt/ris/ris_server.py 2>&1 | tee /var/log/ris/ris.log
