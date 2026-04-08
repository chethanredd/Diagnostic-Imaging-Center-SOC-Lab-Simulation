#!/usr/bin/env bash
# ================================================================
# DIC SOC Lab — Start Script
# Usage: ./start.sh          → normal start (keeps data volumes)
#        ./start.sh --clean  → full wipe and fresh start
# ================================================================
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
log()    { echo -e "${GREEN}[+]${NC} $*"; }
warn()   { echo -e "${YELLOW}[!]${NC} $*"; }
err()    { echo -e "${RED}[✗]${NC} $*"; exit 1; }
banner() { echo -e "\n${CYAN}$*${NC}"; }
detect_host_ip() {
  ip route get 1.1.1.1 2>/dev/null | awk '{for (i=1;i<=NF;i++) if ($i=="src") {print $(i+1); exit}}'
}
wait_url() {
  local url="$1"
  local label="$2"
  local expected_regex="$3"
  local max_attempts="${4:-30}"
  local delay_seconds="${5:-3}"
  local code

  log "Checking ${label} readiness..."
  for i in $(seq 1 "$max_attempts"); do
    code=$(curl -ks -o /dev/null -w "%{http_code}" "$url" 2>/dev/null || echo "000")
    if [[ "$code" =~ $expected_regex ]]; then
      log "${label} ready (HTTP ${code})"
      return 0
    fi
    printf "  [%02d/%02d] %s status: %s\r" "$i" "$max_attempts" "$label" "$code"
    sleep "$delay_seconds"
  done
  echo ""
  warn "${label} did not become ready in time (last HTTP status: ${code})."
  return 1
}

CLEAN=false
[[ "${1:-}" == "--clean" ]] && CLEAN=true

banner "================================================================"
banner " DIC SOC Lab — Diagnostic Imaging Center Security Operations"
banner "================================================================"
echo ""

# ================================================================
# Prerequisites
# ================================================================
command -v docker  >/dev/null || err "Docker not installed."
command -v openssl >/dev/null || err "OpenSSL not found."
docker compose version >/dev/null 2>&1 || err "Docker Compose v2 required."

# ================================================================
# Clean mode — full wipe
# ================================================================
if $CLEAN; then
  warn "Clean mode — wiping all containers, volumes and certs..."
  docker compose down -v --remove-orphans 2>/dev/null || true
  docker rm -f tenzir-node 2>/dev/null || true
  rm -rf certs/*
  log "Clean complete."
fi

# ================================================================
# STEP 1 — Kill stray containers that steal ports
# ================================================================
banner "STEP 1/5 — Clearing stray containers..."

docker rm -f tenzir-node 2>/dev/null && \
  log "Removed stray tenzir-node container." || true

# Kill zombie docker-proxy processes holding our ports
for PORT in 1514 9200 443 8080 3001 5001; do
  PIDS=$(sudo ss -tlnp "sport = :$PORT" 2>/dev/null \
    | awk 'NR>1 {print $6}' \
    | grep -oP 'pid=\K[0-9]+' || true)
  for PID in $PIDS; do
    PROC=$(cat /proc/$PID/comm 2>/dev/null || echo "unknown")
    if [[ "$PROC" == "docker-proxy" ]]; then
      warn "Port $PORT held by zombie docker-proxy (pid=$PID) — killing..."
      sudo kill -9 "$PID" 2>/dev/null || true
    fi
  done
done

log "Port sweep done."

# ================================================================
# STEP 2 — System tuning for OpenSearch
# ================================================================
banner "STEP 2/5 — Applying system tuning..."

CURRENT_MAP=$(sysctl -n vm.max_map_count 2>/dev/null || echo 0)
if [[ "$CURRENT_MAP" -lt 262144 ]]; then
  warn "vm.max_map_count=$CURRENT_MAP — needs 262144 for OpenSearch"
  sudo sysctl -w vm.max_map_count=262144 || \
    err "Failed. Run manually: sudo sysctl -w vm.max_map_count=262144"
  grep -qxF 'vm.max_map_count=262144' /etc/sysctl.conf || \
    echo "vm.max_map_count=262144" | sudo tee -a /etc/sysctl.conf > /dev/null
  log "vm.max_map_count set to 262144"
else
  log "vm.max_map_count=$CURRENT_MAP — OK"
fi

# ================================================================
# STEP 3 — Generate PKI certificates
# ================================================================
banner "STEP 3/5 — Generating PKI certificates..."
mkdir -p certs

if [[ ! -f certs/root-ca.pem ]]; then
  log "Generating Root CA..."
  openssl genrsa -out certs/root-ca-key.pem 4096 2>/dev/null
  openssl req -new -x509 -sha256 \
    -key certs/root-ca-key.pem \
    -out certs/root-ca.pem \
    -days 730 \
    -subj "/C=US/ST=Lab/O=DIC-SOC/CN=root-ca" 2>/dev/null
  cp certs/root-ca.pem certs/root-ca-manager.pem

  log "Generating admin cert..."
  openssl genrsa -out certs/admin-key.pem 4096 2>/dev/null
  openssl req -new -sha256 \
    -key certs/admin-key.pem \
    -out certs/admin.csr \
    -subj "/C=US/ST=Lab/O=Wazuh/CN=admin" 2>/dev/null
  openssl x509 -req -sha256 -days 730 \
    -in certs/admin.csr \
    -CA certs/root-ca.pem \
    -CAkey certs/root-ca-key.pem \
    -CAcreateserial \
    -out certs/admin.pem 2>/dev/null

  for NODE in wazuh.indexer wazuh.manager wazuh.dashboard; do
    log "Generating cert for $NODE..."
    openssl genrsa -out "certs/${NODE}-key.pem" 4096 2>/dev/null
    openssl req -new -sha256 \
      -key "certs/${NODE}-key.pem" \
      -out "certs/${NODE}.csr" \
      -subj "/C=US/ST=Lab/O=Wazuh/CN=${NODE}" 2>/dev/null
    openssl x509 -req -sha256 -days 730 \
      -in "certs/${NODE}.csr" \
      -CA certs/root-ca.pem \
      -CAkey certs/root-ca-key.pem \
      -CAcreateserial \
      -out "certs/${NODE}.pem" 2>/dev/null
  done

  # 644 so Docker containers can read them — NOT 600
  chmod 644 certs/*.pem certs/*.csr 2>/dev/null || true
  log "Certificates generated successfully."
else
  log "Certificates already exist — skipping generation."
  # Always ensure correct permissions on existing certs
  chmod 644 certs/*.pem 2>/dev/null || true
fi

# ================================================================
# STEP 4 — Pull and build images
# ================================================================
banner "STEP 4/5 — Pulling and building images..."
docker compose pull --ignore-buildable 2>&1 | \
  grep -E "Pulling|pulled|already|Skipped" || true
docker compose build --parallel

# ================================================================
# STEP 5 — Staged launch
# ================================================================
banner "STEP 5/5 — Launching SOC lab (staged startup)..."

# --- Stage A: Start Wazuh Indexer + Shuffle DB ---
log "Stage A — Starting Wazuh Indexer and Shuffle DB..."
docker compose up -d wazuh.indexer shuffle-database

# --- Stage B: Wait for indexer to be healthy ---
log "Waiting for Wazuh indexer to become healthy (2-4 minutes)..."
HEALTHY=false
SECURITY_BOOTSTRAPPED=false
for i in $(seq 1 40); do
  STATUS=$(docker inspect \
    --format='{{.State.Health.Status}}' \
    dic-wazuh-indexer 2>/dev/null || echo "starting")
  printf "  [%02d/40] status: %-12s\r" "$i" "$STATUS"

  # Bootstrap security index once indexer can accept requests.
  # Safe to run every boot — idempotent operation.
  if [[ "$SECURITY_BOOTSTRAPPED" == "false" && "$STATUS" == "healthy" ]]; then
    echo ""
    log "Bootstrapping OpenSearch security index..."
    docker exec dic-wazuh-indexer bash -c "
      chmod +x /usr/share/wazuh-indexer/plugins/opensearch-security/tools/securityadmin.sh
      export JAVA_HOME=/usr/share/wazuh-indexer/jdk
      INSTALL=/usr/share/wazuh-indexer
      \$INSTALL/plugins/opensearch-security/tools/securityadmin.sh \
        -cd \$INSTALL/opensearch-security/ \
        -nhnv \
        -cacert \$INSTALL/certs/root-ca.pem \
        -cert \$INSTALL/certs/admin.pem \
        -key \$INSTALL/certs/admin-key.pem \
        -p 9200 \
        -icl
    " 2>&1 | grep -E "SUCC|ERROR|Done|failed" || true
    SECURITY_BOOTSTRAPPED=true
  fi

  if [[ "$STATUS" == "healthy" ]]; then
    echo ""
    log "Wazuh indexer is healthy!"
    HEALTHY=true
    break
  fi

  # Fail fast if container crashed
  RUNNING=$(docker inspect \
    --format='{{.State.Running}}' \
    dic-wazuh-indexer 2>/dev/null || echo "false")
  if [[ "$RUNNING" == "false" ]]; then
    echo ""
    err "Wazuh indexer crashed. Check logs: docker logs dic-wazuh-indexer"
  fi

  sleep 10
done

if [[ "$HEALTHY" == "false" ]]; then
  echo ""
  warn "Indexer did not reach healthy state in time."
  warn "Check: docker logs dic-wazuh-indexer --tail 20"
  err "Fix the issue and retry: ./start.sh"
fi

# --- Stage C: Kill tenzir before Orborus can spawn it ---
log "Stage C — Pre-emptive tenzir cleanup..."
docker rm -f tenzir-node 2>/dev/null || true
docker rmi frikky/shuffle:tenzir 2>/dev/null || true

# --- Stage D: Start Wazuh Manager + Dashboard ---
log "Stage D — Starting Wazuh Manager and Dashboard..."
docker compose up -d wazuh.manager wazuh.dashboard
sleep 5

# --- Stage E: Start Shuffle SOAR (Orborus last) ---
log "Stage E — Starting Shuffle SOAR..."
docker compose up -d shuffle-backend shuffle-frontend
sleep 3
docker rm -f tenzir-node 2>/dev/null || true
docker compose up -d shuffle-orborus

# --- Stage F: Start all medical + DMZ services ---
log "Stage F — Starting medical systems, Suricata and web server..."
docker compose up -d --remove-orphans

# Final tenzir cleanup after Orborus has started
sleep 10
docker rm -f tenzir-node 2>/dev/null || true

# --- Stage G: Generate initial SOC telemetry ---
log "Stage G — Seeding baseline SOC telemetry..."
chmod +x ./scripts/seed_soc_activity.sh 2>/dev/null || true
./scripts/seed_soc_activity.sh 2>/dev/null || true

# --- Stage H: Bootstrap Shuffle demo workflows ---
log "Stage H — Ensuring Shuffle workflows exist..."
if command -v python3 >/dev/null 2>&1; then
  python3 ./scripts/import_shuffle_workflows.py 2>/dev/null || true
else
  warn "python3 not found; skipping Shuffle workflow bootstrap."
fi

# --- Stage I: Validate key URLs before declaring ready ---
log "Stage I — Validating service URLs..."
wait_url "https://localhost"      "Wazuh Dashboard" "^(200|302)$" 50 4 || true
wait_url "http://localhost:3001"  "Shuffle Frontend" "^200$"      30 2 || true
wait_url "http://localhost:8042"  "PACS Orthanc"     "^(200|401)$" 30 2 || true

# ================================================================
# Status
# ================================================================
echo ""
banner "================================================================"
banner " Container Status"
banner "================================================================"
docker compose ps --format \
  "table {{.Name}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null || \
  docker compose ps

echo ""
banner "================================================================"
banner " Lab is ready!"
banner "================================================================"
echo ""
HOST_IP="$(detect_host_ip || true)"
[[ -z "${HOST_IP}" ]] && HOST_IP="127.0.0.1"
echo -e "  ${CYAN}Host LAN IP${NC}     →  ${HOST_IP}"
echo ""
echo -e "  ${CYAN}Wazuh SIEM${NC}      →  https://${HOST_IP}"
echo -e "                     admin / SecretPassword1!"
echo ""
echo -e "  ${CYAN}PACS (Orthanc)${NC}  →  http://${HOST_IP}:8042"
echo -e "                     orthanc / orthanc"
echo ""
echo -e "  ${CYAN}Patient Portal${NC}  →  http://${HOST_IP}:8080"
echo -e "                     ${PORTAL_USERNAME:-patient1} / ${PORTAL_PASSWORD:-Patient#2026}"
echo ""
echo -e "  ${CYAN}RIS Server${NC}      →  http://${HOST_IP}:8081"
echo -e "                     ${RIS_USERNAME:-radiologist} / ${RIS_PASSWORD:-Radiology#2026}"
echo ""
echo -e "  ${CYAN}Shuffle SOAR${NC}    →  http://${HOST_IP}:3001"
echo -e "                     admin / SOCAdmin!2026"
echo ""
echo -e "  ${CYAN}Wazuh API${NC}       →  https://${HOST_IP}:56000"
echo -e "                     wazuh-wui / MyS3cr37P450r.*-"
echo ""
echo -e "  ${YELLOW}Attack Sim${NC}      →  ./demo.sh"
echo ""
log "Logs    : docker compose logs -f"
log "Stop    : docker compose down"
log "Restart : ./start.sh"
log "Reset   : ./start.sh --clean"
