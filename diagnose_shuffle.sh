#!/usr/bin/env bash
set -euo pipefail

echo "======================================================"
echo "  SHUFFLE SOAR DIAGNOSTIC REPORT"
echo "======================================================"

echo ""
echo "--- [1] Shuffle Container Status ---"
docker ps -a --format "{{.Names}} | {{.Status}} | {{.Ports}}" | grep shuffle

echo ""
echo "--- [2] Shuffle Backend Logs (last 40 lines) ---"
docker logs dic-shuffle-backend 2>&1 | tail -40

echo ""
echo "--- [3] Shuffle Frontend Logs (last 20 lines) ---"
docker logs dic-shuffle-frontend 2>&1 | tail -20

echo ""
echo "--- [4] Shuffle Orborus Logs (last 20 lines) ---"
docker logs dic-shuffle-orborus 2>&1 | tail -20

echo ""
echo "--- [5] Shuffle Database Logs (last 10 lines) ---"
docker logs dic-shuffle-database 2>&1 | tail -10

echo ""
echo "--- [6] Shuffle Backend Environment Variables ---"
docker exec dic-shuffle-backend env | grep -E "SHUFFLE|DEFAULT|DATASTORE|OPENSEARCH|ENCRYPTION" | sort

echo ""
echo "--- [7] Connectivity: Backend -> Database (port 9200) ---"
docker exec dic-shuffle-backend bash -c "wget -qO- http://shuffle-database:9200 2>&1 | head -5 || curl -s http://shuffle-database:9200 2>&1 | head -5 || echo 'CONNECTIVITY FAILED'"

echo ""
echo "--- [8] Shuffle Backend HTTP health check ---"
docker exec dic-shuffle-backend bash -c "wget -qO- http://localhost:5001/api/v1/health 2>&1 | head -10 || curl -s http://localhost:5001/api/v1/health 2>&1 | head -10 || echo 'HEALTH CHECK FAILED'"

echo ""
echo "--- [9] Check Users in Shuffle DB ---"
docker exec dic-shuffle-database bash -c "curl -s 'http://localhost:9200/users/_search?pretty' 2>&1 | head -40 || echo 'No users index found'"

echo ""
echo "--- [10] Check all Shuffle indexes ---"
docker exec dic-shuffle-database bash -c "curl -s 'http://localhost:9200/_cat/indices?v' 2>&1"

echo ""
echo "--- [11] Shuffle user data (active_users index) ---"
docker exec dic-shuffle-database bash -c "curl -s 'http://localhost:9200/shuffle-users/_search?pretty' 2>&1 | head -50 || echo 'No shuffle-users index'"

echo ""
echo "--- [12] Shuffle Backend API - List orgs ---"
docker exec dic-shuffle-backend bash -c "wget -qO- http://localhost:5001/api/v1/orgs 2>&1 | head -20 || curl -s http://localhost:5001/api/v1/orgs 2>&1 | head -20 || echo 'ORGS ENDPOINT FAILED'"

echo ""
echo "======================================================"
echo "  SHUFFLE DIAGNOSIS COMPLETE"
echo "======================================================"
