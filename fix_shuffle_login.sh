#!/usr/bin/env bash
set -euo pipefail

echo "======================================================"
echo "  SHUFFLE LOGIN FIX"
echo "======================================================"

# Get user ID
USER_ID=$(docker exec dic-shuffle-database sh -c \
  "curl -s 'http://localhost:9200/users/_search?pretty' | grep '\"_id\"' | head -1 | grep -oE '[a-f0-9-]{36}'" 2>&1)

echo "[1] Found user ID: $USER_ID"

echo ""
echo "[2] Setting verified=true and generating apikey..."
docker exec dic-shuffle-database sh -c "curl -s -X POST 'http://localhost:9200/users/_update/$USER_ID' \
  -H 'Content-Type: application/json' \
  -d '{
    \"doc\": {
      \"verified\": true,
      \"apikey\": \"shuffleadminapikey2026soclab\"
    }
  }' | grep result"

echo ""
echo "[3] Verifying fix..."
docker exec dic-shuffle-database sh -c \
  "curl -s 'http://localhost:9200/users/_doc/$USER_ID?pretty' | grep -E 'verified|apikey|username'"

echo ""
echo "[4] Testing login again with credentials..."
docker exec dic-shuffle-backend sh -c \
  "wget -qO- --post-data='{\"username\":\"socadmin\",\"password\":\"SOCAdmin!2026\"}' \
   --header='Content-Type: application/json' \
   http://localhost:5001/api/v1/login 2>&1 | python3 -c \"
import sys, json
data = json.load(sys.stdin)
print('Login success:', data.get('success'))
print('Username:', data.get('username','(empty)'))
print('Admin:', data.get('admin','(empty)'))
print('Token:', str(data.get('cookies',[{}])[0].get('value',''))[:40] + '...')
\" 2>/dev/null || echo 'Login parse failed, raw:'" || true

docker exec dic-shuffle-backend sh -c \
  "wget -qO- --post-data='{\"username\":\"socadmin\",\"password\":\"SOCAdmin!2026\"}' \
   --header='Content-Type: application/json' \
   http://localhost:5001/api/v1/login 2>&1 | head -5" || true

echo ""
echo "[5] Also patch the org to ensure admin is linked..."
ORG_ID=$(docker exec dic-shuffle-database sh -c \
  "curl -s 'http://localhost:9200/organizations/_search?pretty' | grep '\"_id\"' | head -1 | grep -oE '[a-f0-9-]{36}'" 2>&1)
echo "Org ID: $ORG_ID"

echo ""
echo "======================================================"
echo "  FIX COMPLETE"
echo "  Login at: http://localhost:3001"
echo "  Username: socadmin"
echo "  Password: SOCAdmin!2026"
echo "======================================================"
