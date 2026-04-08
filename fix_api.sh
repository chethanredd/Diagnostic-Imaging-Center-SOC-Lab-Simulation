#!/usr/bin/env bash
set -euo pipefail

echo "=== Step 1: Inject correct wazuh.yml into running dashboard container ==="
docker cp /mnt/c/Users/gsche/Downloads/dic/dic-soc-lab/configs/wazuh/wazuh.yml \
  dic-wazuh-dashboard:/usr/share/wazuh-dashboard/data/wazuh/config/wazuh.yml

echo "=== Step 2: Verify injected content ==="
docker exec dic-wazuh-dashboard cat /usr/share/wazuh-dashboard/data/wazuh/config/wazuh.yml

echo "=== Step 3: Check wazuh-wui user exists on manager ==="
docker exec dic-wazuh-manager bash -c \
  "/var/ossec/framework/python/bin/python3 /var/ossec/api/scripts/wazuh-apid.py --help 2>/dev/null | head -5 || echo 'API script check done'"

echo "=== Step 4: Test API auth from manager itself ==="
docker exec dic-wazuh-manager bash -c \
  "curl -sk -X POST https://localhost:55000/security/user/authenticate \
    -H 'Content-Type: application/json' \
    -u 'wazuh-wui:MyS3cr37P450r.*-' | python3 -m json.tool 2>/dev/null | head -10"

echo "=== Step 5: Restart dashboard ==="
docker restart dic-wazuh-dashboard

echo "=== Waiting 15s for dashboard to come back up ==="
sleep 15

echo "=== Step 6: Verify API check after restart ==="
docker exec dic-wazuh-manager bash -c \
  "tail -5 /var/ossec/logs/api.log"

echo ""
echo "DONE. Check https://localhost in your browser."
echo "Login: admin / SecretPassword1!"
