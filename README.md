# DIC SOC Lab — Diagnostic Imaging Center

> **HIPAA-Aware SOC Lab: SIEM + SOAR + Threat Intelligence + DICOM Attack Simulation**
> All attack simulations are for authorized lab use only.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        MANAGEMENT VLAN (10.10.0.0/24)                   │
│                                                                         │
│  ┌─────────────────┐  ┌──────────────┐  ┌─────────────────────────┐   │
│  │  Wazuh Manager  │  │ Wazuh Indexer│  │   Wazuh Dashboard       │   │
│  │   10.10.0.10    │  │  10.10.0.5   │  │      10.10.0.15         │   │
│  │  SIEM/Manager   │  │  OpenSearch  │  │  https://localhost       │   │
│  └────────┬────────┘  └──────────────┘  └─────────────────────────┘   │
│           │                                                             │
│  ┌────────┴────────┐  ┌──────────────┐  ┌─────────────────────────┐   │
│  │    Suricata     │  │    Shuffle   │  │   Shuffle Database      │   │
│  │   10.10.0.2     │  │  10.10.0.12  │  │     10.10.0.14          │   │
│  │    IDS/IPS      │  │     SOAR     │  │    OpenSearch           │   │
│  └─────────────────┘  └──────────────┘  └─────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
         │                    │                       │
┌────────┴──────┐  ┌──────────┴──────┐  ┌────────────┴───────┐
│  MEDICAL VLAN │  │   ADMIN VLAN    │  │      DMZ           │
│ 10.10.10.0/24 │  │ 10.10.20.0/24   │  │  10.10.30.0/24     │
│               │  │                 │  │                    │
│ PACS  .10     │  │ DC      .10     │  │ Web Portal  .10    │
│ RIS   .20     │  │ Rad WS  .20     │  │ (Patient    .10)   │
│ MRI   .30     │  │ Admin   .21     │  └────────────────────┘
│ CT    .31     │  └─────────────────┘
└───────────────┘
```

---

## Quick Start

### Prerequisites
- Docker Engine 24+ and Docker Compose v2
- 16 GB RAM (minimum 12 GB), 50 GB disk
- `openssl` installed on the host

### 1. Clone / Extract the lab
```bash
cd dic-soc-lab
chmod +x start.sh demo.sh
```

### 2. Start the lab
```bash
./start.sh
```
> First run takes 5–10 minutes to pull images and generate certificates.

### 3. Open the dashboard
| Service | URL | Credentials |
|---|---|---|
| **Wazuh SIEM** | https://`<HOST_IP>` | `admin` / `SecretPassword1!` |
| **PACS (Orthanc)** | http://`<HOST_IP>`:8042 | `orthanc` / `orthanc` |
| **RIS Server** | http://`<HOST_IP>`:8081 | `radiologist` / `Radiology#2026` |
| **Patient Portal** | http://`<HOST_IP>`:8080 | `patient1` / `Patient#2026` |
| **SOAR (Shuffle)** | http://`<HOST_IP>`:3001 | `admin` / `SOCAdmin!2026` |
| **Wazuh API** | https://`<HOST_IP>`:56000 | `wazuh-wui` / `MyS3cr37P450r.*-` |

> Replace `<HOST_IP>` with the host machine IP on your LAN (shown at the end of `./start.sh`).

### 4. Run attack simulations
```bash
./demo.sh
```

### 5. Verify monitoring is active
```bash
# Should show 3 active agents: manager, pacs-server, ris-server
docker exec dic-wazuh-manager /var/ossec/bin/agent_control -l

# Generate baseline telemetry if dashboard is still quiet
./scripts/seed_soc_activity.sh
```

---

## Container Reference

| Container | Image | IP | Purpose |
|---|---|---|---|
| `dic-wazuh-manager` | `wazuh/wazuh-manager:4.7.5` | 10.10.0.10 | SIEM Manager |
| `dic-wazuh-indexer` | `wazuh/wazuh-indexer:4.7.5` | 10.10.0.5 | OpenSearch index |
| `dic-wazuh-dashboard` | `wazuh/wazuh-dashboard:4.7.5` | 10.10.0.15 | Kibana UI |
| `dic-suricata` | `jasonish/suricata:latest` | 10.10.0.2 | IDS/IPS |
| `dic-shuffle-frontend` | `ghcr.io/shuffle/shuffle-frontend` | 10.10.0.12 | SOAR UI |
| `dic-shuffle-backend` | `ghcr.io/shuffle/shuffle-backend` | 10.10.0.13 | SOAR Engine |
| `dic-pacs-server` | custom (Orthanc) | 10.10.10.10 | DICOM PACS |
| `dic-ris-server` | custom (Flask) | 10.10.10.20 | Radiology IS |
| `dic-mri-simulator` | custom | 10.10.10.30 | MR modality |
| `dic-ct-simulator` | custom | 10.10.10.31 | CT modality |
| `dic-web-server` | custom (nginx) | 10.10.30.10 | Patient portal |
| `dic-attacker` | `kalilinux/kali-rolling` | 10.10.x.99 | Red team |

---

## Attack Scenarios (MITRE ATT&CK)

| # | Scenario | MITRE | Wazuh Rule | Suricata SID |
|---|---|---|---|---|
| 1 | SSH Brute Force → PACS | T1110 | 100005 | 9000010 |
| 2 | DICOM Port Scan | T1046 | 100009 | 9000002 |
| 3 | Ransomware (DICOM encrypt) | T1486 | 100001, 100003, 100004 | — |
| 4 | Phishing Credential Harvest | T1566.002 | 100012, 100013 | — |
| 5 | DICOM Data Exfiltration | T1041 | 100011 | 9000003 |
| 6 | Unauthorized HL7 Message | T1071 | — | 9000020 |
| 7 | AD/LDAP Enumeration | T1087.002 | 100014 | 9000042 |
| 8 | Full APT Chain | All above | All | All |

---

## File Structure

```
dic-soc-lab/
├── docker-compose.yml          ← Main orchestration
├── .env                        ← Credentials & secrets
├── start.sh                    ← One-click lab setup
├── demo.sh                     ← Interactive attack menu
│
├── certs/                      ← Generated TLS certificates
│
├── configs/
│   ├── wazuh/
│   │   ├── dic_custom_rules.xml   ← 17 custom HIPAA/DICOM rules
│   │   ├── ossec_manager.conf     ← Wazuh manager config
│   │   ├── wazuh.indexer.yml      ← OpenSearch config
│   │   ├── internal_users.yml     ← User credentials
│   │   └── certs.yml              ← Cert generator config
│   ├── suricata/
│   │   ├── suricata.yaml          ← IDS/IPS config
│   │   └── dic.rules              ← 20 custom DICOM/medical rules
│   ├── orthanc/
│   │   └── orthanc.json           ← PACS configuration
│   └── nginx/
│       └── default.conf           ← Patient portal
│
├── containers/
│   ├── pacs/                   ← Orthanc PACS + Wazuh agent
│   │   ├── Dockerfile
│   │   ├── entrypoint.sh
│   │   ├── generate_dicom.py   ← Synthetic DICOM generator
│   │   └── ossec_agent.conf
│   ├── ris/                    ← Flask RIS + HL7 listener
│   │   ├── Dockerfile
│   │   ├── ris_server.py
│   │   └── entrypoint.sh
│   ├── mri-simulator/          ← DICOM MR modality
│   ├── ct-simulator/           ← DICOM CT modality
│   ├── web-server/             ← nginx patient portal
│   │   ├── index.html
│   │   ├── portal.py           ← Phishing target
│   │   └── entrypoint.sh
│   └── attacker/               ← Kali Linux red team
│       ├── ransomware_sim.py   ← T1486 simulation
│       ├── phish_server.py     ← T1566 simulation
│       ├── anomaly_detector.py ← ML anomaly detection
│       ├── threat_intel.py     ← VT + AbuseIPDB enrichment
│       └── run_attacks.sh      ← Quick attack launcher
│
└── scripts/
    ├── shuffle_playbooks.json  ← SOAR playbook templates
    └── dic_soc_dashboard.ndjson ← Kibana dashboard export
```

---

## Common Operations

### Watch live alerts
```bash
docker compose logs -f wazuh.manager | grep -E "CRITICAL|HIGH|Rule"
```

### Query Wazuh alerts directly
```bash
# All alerts from PACS server
docker exec dic-wazuh-manager \
  grep "pacs-server" /var/ossec/logs/alerts/alerts.log | tail -20 | jq .

# DICOM-specific alerts
docker exec dic-wazuh-manager \
  grep '\.dcm' /var/ossec/logs/alerts/alerts.log | tail -10 | jq '.rule.description'

# Critical alerts (level 12+)
docker exec dic-wazuh-manager \
  cat /var/ossec/logs/alerts/alerts.log | \
  python3 -c "import json,sys; [print(json.dumps({'rule':a['rule']['description'],'level':a['rule']['level'],'agent':a['agent']['name']},indent=2)) for line in sys.stdin for a in [json.loads(line)] if a.get('rule',{}).get('level',0)>=12]"
```

### Suricata alerts
```bash
docker exec dic-suricata \
  jq -r '.alert.signature + " | " + .src_ip' /var/log/suricata/eve.json | \
  sort | uniq -c | sort -rn | head -20
```

### Enter attacker container
```bash
docker compose --profile attack up -d attacker
docker exec -it dic-attacker bash
# Then run: /opt/attacks/run_attacks.sh full_chain
```

### Import Kibana dashboards
```bash
curl -X POST "http://localhost:5601/api/saved_objects/_import" \
  -H "kbn-xsrf: true" \
  -H "osd-xsrf: true" \
  --form file=@scripts/dic_soc_dashboard.ndjson
```

### Shuffle workflows (auto-seeded)
`./start.sh` now auto-creates baseline SOC workflows from `scripts/shuffle_playbooks.json` if they do not already exist.

If you want to run only the workflow bootstrap manually:
```bash
python3 ./scripts/import_shuffle_workflows.py
```

### IR readiness pass (recommended before demos)
```bash
chmod +x ./scripts/ir_readiness_check.sh
./scripts/ir_readiness_check.sh
```
This validates:
- Wazuh + Shuffle + Suricata containers are up
- agents are enrolled and active
- manager has active-response binaries for containment
- recent high-severity alerts are visible
- Shuffle workflow bootstrap script can still run

### Restore DICOM files after ransomware demo
```bash
docker exec dic-attacker python3 /opt/attacks/ransomware_sim.py --decrypt
```

### Stop the lab
```bash
docker compose down          # stop, keep volumes
docker compose down -v       # stop, delete all data (full reset)
```

---

## HIPAA Compliance Mapping

| Control | § | Implementation | Status |
|---|---|---|---|
| Access Controls | 164.312(a) | VLAN segmentation + RBAC | ✅ |
| Audit Controls | 164.312(b) | Wazuh FIM + event logging | ✅ |
| Integrity | 164.312(c) | DICOM file hashing (syscheck) | ✅ |
| Transmission Security | 164.312(e) | TLS between all nodes | ✅ |
| Breach Notification | 164.400 | SOAR auto-creates incident | ✅ |
| Risk Analysis | 164.308(a)(1) | Attack simulation + Suricata | ✅ |
| Contingency Plan | 164.308(a)(7) | Snapshot on ransomware trigger | ✅ |

---

## Troubleshooting

**OpenSearch won't start**
```bash
sudo sysctl -w vm.max_map_count=262144  # run this first
```

**Wazuh dashboard shows "no data"**
```bash
# Wait 3-4 minutes for indexer to be fully ready, then:
docker compose restart wazuh.dashboard
```

**Agents not connecting**
```bash
docker exec dic-wazuh-manager /var/ossec/bin/manage_agents -l
# Check enrollment password matches .env ENROLLMENT_PASSWORD
```

**PACS not receiving DICOM**
```bash
# Test DICOM connectivity from MRI sim
docker exec dic-mri-simulator \
  echoscu -v 10.10.10.10 4242
```

**Reset everything**
```bash
./start.sh --clean
```

**Portal login audit logs**
```bash
# Patient portal login attempts
docker exec dic-web-server tail -f /var/log/portal/auth.log

# RIS login attempts
docker exec dic-ris-server tail -f /var/log/ris/ris.log
```
