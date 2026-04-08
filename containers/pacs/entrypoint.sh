#!/usr/bin/env bash
set -e

echo "[PACS] Starting DIC PACS Server (Orthanc)..."

# ── Ensure monitored log files exist ───────────────────────────────────────
mkdir -p /var/log/orthanc /var/log/syslog.d
touch /var/log/auth.log /var/log/syslog /var/log/orthanc/orthanc.log
chmod 640 /var/log/auth.log

# ── Configure Wazuh agent ────────────────────────────────────────────────
if [[ -f /var/ossec/etc/ossec.conf.tmpl ]]; then
  sed "s|WAZUH_MANAGER_IP|${WAZUH_MANAGER:-10.10.0.10}|g" \
      /var/ossec/etc/ossec.conf.tmpl > /var/ossec/etc/ossec.conf

  # Write enrollment password if provided
  if [[ -n "${ENROLLMENT_PASSWORD:-}" ]]; then
    echo "${ENROLLMENT_PASSWORD}" > /var/ossec/etc/authd.pass
    chmod 640 /var/ossec/etc/authd.pass
  fi

  echo "[PACS] Waiting 10s for Wazuh manager to be ready..."
  sleep 10

  # Enroll if no key yet
  if [[ ! -s /var/ossec/etc/client.keys ]]; then
    /var/ossec/bin/agent-auth \
      -m "${WAZUH_MANAGER:-10.10.0.10}" \
      -p 1515 \
      -A "pacs-server" 2>/dev/null || true
  fi

  # Start Wazuh agent
  /var/ossec/bin/wazuh-control start 2>/dev/null || \
  /var/ossec/bin/wazuh-agentd 2>/dev/null || \
  echo "[PACS] Wazuh agent not available — skipping"
fi

# ── Generate synthetic DICOM test files ─────────────────────────
if [[ ! "$(ls -A /opt/dicom_test/*.dcm 2>/dev/null)" ]]; then
  echo "[PACS] Generating synthetic DICOM files..."
  python3 /opt/generate_dicom.py --count 20 --output /opt/dicom_test --modality CT
  echo "[PACS] Generated 20 DICOM test files."
fi

# ── Start realistic log traffic generator (background) ──────────
if [[ -f /opt/scripts/realistic_traffic.py ]]; then
  echo "[PACS] Starting realistic traffic generator..."
  python3 /opt/scripts/realistic_traffic.py --host pacs &
elif [[ -f /opt/realistic_traffic.py ]]; then
  python3 /opt/realistic_traffic.py --host pacs &
fi

# ── Start Orthanc ────────────────────────────────────────────────
echo "[PACS] Starting Orthanc PACS on ports 8042 (HTTP) and 4242 (DICOM)..."
exec /usr/sbin/Orthanc /etc/orthanc/ 2>&1 | tee /var/log/orthanc/orthanc.log
