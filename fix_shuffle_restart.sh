#!/usr/bin/env bash
set -euo pipefail

echo "======================================================"
echo "  SHUFFLE COMPLETE FIX"
echo "======================================================"

echo ""
echo "[1] Restart shuffle-backend to clear session cache and reload verified user..."
docker restart dic-shuffle-backend
sleep 8

echo ""
echo "[2] Restart shuffle-frontend..."
docker restart dic-shuffle-frontend
sleep 5

echo ""
echo "[3] Test login after restart..."
docker exec dic-shuffle-backend sh -c \
  "wget -qO- --post-data='{\"username\":\"socadmin\",\"password\":\"SOCAdmin!2026\"}' \
   --header='Content-Type: application/json' \
   http://localhost:5001/api/v1/login 2>&1" | \
  python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print('success:', data.get('success'))
    print('username from resp:', data.get('username'))
    cookies = data.get('cookies', [])
    for c in cookies:
        print('cookie:', c.get('key'), '=', str(c.get('value',''))[:30])
except Exception as e:
    print('parse error:', e)
" 2>/dev/null || \
  docker exec dic-shuffle-backend sh -c \
  "wget -qO- --post-data='{\"username\":\"socadmin\",\"password\":\"SOCAdmin!2026\"}' \
   --header='Content-Type: application/json' \
   http://localhost:5001/api/v1/login 2>&1 | head -3"

echo ""
echo "[4] Final DB verification..."
docker exec dic-shuffle-database sh -c \
  "curl -s 'http://localhost:9200/users/_search?pretty&_source=username,verified,apikey'" 2>&1 | \
  grep -E '"username"|"verified"|"apikey"' | head -10

echo ""
echo "======================================================"
echo "  RESTART COMPLETE"
echo "  Open: http://localhost:3001"  
echo "  Username : socadmin"
echo "  Password : SOCAdmin!2026"
echo "======================================================"
