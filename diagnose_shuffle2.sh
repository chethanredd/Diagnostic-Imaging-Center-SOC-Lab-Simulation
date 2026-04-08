#!/usr/bin/env bash
set -euo pipefail

echo "--- [7b] DB connectivity from backend (no bash, use sh) ---"
docker exec dic-shuffle-backend sh -c "wget -qO- http://shuffle-database:9200 2>&1 | head -5" || echo "wget failed, trying nc"

echo ""
echo "--- [8] DB indexes ---"
docker exec dic-shuffle-database sh -c "curl -s 'http://localhost:9200/_cat/indices?v'" 2>&1

echo ""
echo "--- [9] Check users index ---"
docker exec dic-shuffle-database sh -c "curl -s 'http://localhost:9200/users/_search?pretty'" 2>&1 | head -60

echo ""
echo "--- [10] Check shuffle-users index ---"
docker exec dic-shuffle-database sh -c "curl -s 'http://localhost:9200/shuffle-users/_search?pretty'" 2>&1 | head -60

echo ""
echo "--- [11] Backend: Test login API ---"
docker exec dic-shuffle-backend sh -c \
  "wget -qO- --post-data='{\"username\":\"socadmin\",\"password\":\"SOCAdmin!2026\"}' \
   --header='Content-Type: application/json' \
   http://localhost:5001/api/v1/login 2>&1 | head -20" || echo "Login test failed"

echo ""
echo "--- [12] Backend: list all users ---"
docker exec dic-shuffle-database sh -c \
  "curl -s 'http://localhost:9200/users/_search?pretty&size=5'" 2>&1 | head -80
