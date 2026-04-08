#!/usr/bin/env bash
set -euo pipefail

echo "[IR] DIC SOC IR readiness check"
echo "================================"

echo ""
echo "[1/5] Core container status"
docker compose ps wazuh.manager wazuh.dashboard shuffle-backend shuffle-frontend suricata 2>/dev/null || true

echo ""
echo "[2/5] Active agents"
docker exec dic-wazuh-manager /var/ossec/bin/agent_control -l || true

echo ""
echo "[3/5] Active-response command inventory"
docker exec dic-wazuh-manager sh -c "test -f /var/ossec/etc/shared/ar.conf && grep -E 'restart|wazuh' /var/ossec/etc/shared/ar.conf" || true
docker exec dic-wazuh-manager sh -c "ls -1 /var/ossec/active-response/bin | grep -E 'firewall-drop|host-deny|restart-wazuh'" || true

echo ""
echo "[4/5] Recent high-severity alerts (level >= 10)"
docker exec dic-wazuh-manager sh -c "tail -n 200 /var/ossec/logs/alerts/alerts.log | grep -E '\"level\":(10|11|12|13|14|15)' | tail -n 10" || true

echo ""
echo "[5/5] Shuffle API/workflow sanity"
if command -v python3 >/dev/null 2>&1; then
  python3 ./scripts/import_shuffle_workflows.py || true
elif command -v python >/dev/null 2>&1; then
  python ./scripts/import_shuffle_workflows.py || true
else
  echo "[IR] python runtime not available on host; skipping workflow import check."
fi

echo ""
echo "[IR] Check complete."
echo "Run './demo.sh' and trigger options 1, 3, and 5 to validate brute-force, ransomware, and exfiltration response paths."
