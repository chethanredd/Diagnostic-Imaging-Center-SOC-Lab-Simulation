#!/usr/bin/env bash
set -euo pipefail

echo "======================================================"
echo "  WAZUH API DIAGNOSTIC REPORT"
echo "======================================================"

echo ""
echo "--- [1] Container Status ---"
docker ps -a --format "{{.Names}} | {{.Status}}" | grep -E "wazuh|dic"

echo ""
echo "--- [2] Wazuh Manager: API service listening? ---"
docker exec dic-wazuh-manager bash -c "ss -tlnp | grep 55000 || echo 'PORT 55000 NOT LISTENING'"

echo ""
echo "--- [3] Wazuh Manager: Check wazuh-api process ---"
docker exec dic-wazuh-manager bash -c "ps aux | grep -E 'wazuh-apid|python|uvicorn' | grep -v grep || echo 'NO API PROCESS FOUND'"

echo ""
echo "--- [4] Wazuh Manager: wazuh-manager process ---"
docker exec dic-wazuh-manager bash -c "ps aux | grep wazuh | grep -v grep | head -20 || echo 'NO WAZUH PROCESSES'"

echo ""
echo "--- [5] Wazuh Manager: ossec.log last 20 lines ---"
docker exec dic-wazuh-manager bash -c "tail -20 /var/ossec/logs/ossec.log 2>/dev/null || echo 'NO ossec.log'"

echo ""
echo "--- [6] Wazuh Manager: api.log (full) ---"
docker exec dic-wazuh-manager bash -c "cat /var/ossec/logs/api.log 2>/dev/null || echo 'NO api.log'"

echo ""
echo "--- [7] Wazuh Manager: Check API users ---"
docker exec dic-wazuh-manager bash -c "ls /var/ossec/api/configuration/security/ 2>/dev/null && cat /var/ossec/api/configuration/security/*.yaml 2>/dev/null || echo 'NO SECURITY CONFIG'"

echo ""
echo "--- [8] Network: Dashboard -> Manager connectivity (port 55000) ---"
docker exec dic-wazuh-dashboard bash -c "curl -sk -o /dev/null -w '%{http_code}' https://wazuh.manager:55000/ || echo 'CURL FAILED'"

echo ""
echo "--- [9] Dashboard: wazuh.yml API config ---"
docker exec dic-wazuh-dashboard bash -c "cat /usr/share/wazuh-dashboard/data/wazuh/config/wazuh.yml 2>/dev/null || echo 'NO wazuh.yml found'"

echo ""
echo "--- [10] Dashboard: Check environment API vars ---"
docker exec dic-wazuh-dashboard bash -c "env | grep -E 'API|WAZUH|INDEXER' | sort"

echo ""
echo "--- [11] Manager: Check wazuh-wui user exists ---"
docker exec dic-wazuh-manager bash -c "curl -sk -u wazuh-wui:'MyS3cr37P450r.*-' https://localhost:55000/ 2>&1 | head -5 || echo 'AUTH TEST FAILED'"

echo ""
echo "--- [12] Manager: Test with default admin credentials ---"
docker exec dic-wazuh-manager bash -c "curl -sk -u wazuh:'wazuh' https://localhost:55000/ 2>&1 | head -5 || echo 'PLAIN AUTH FAILED'"

echo ""
echo "--- [13] Dashboard logs (last 30 lines) ---"
docker logs dic-wazuh-dashboard 2>&1 | tail -30

echo ""
echo "--- [14] Manager logs (last 30 lines) ---"
docker logs dic-wazuh-manager 2>&1 | tail -30

echo ""
echo "======================================================"
echo "  DIAGNOSIS COMPLETE"
echo "======================================================"
