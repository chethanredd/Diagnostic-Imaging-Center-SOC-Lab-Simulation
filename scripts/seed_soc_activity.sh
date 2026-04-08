#!/usr/bin/env bash
set -euo pipefail

echo "[seed] Generating baseline SOC telemetry..."

# Generate HTTP activity against portal + RIS APIs
curl -s "http://localhost:8080/" > /dev/null || true
curl -s "http://localhost:8081/" > /dev/null || true
curl -s "http://localhost:8081/api/studies" > /dev/null || true
curl -s "http://localhost:8081/api/patients" > /dev/null || true
curl -s "http://localhost:8081/api/worklist?modality=CT" > /dev/null || true

# Trigger phishing-style credential post for web log visibility
curl -s -X POST "http://localhost:8080/login" \
  -d "username=demo.user&password=Summer2026!" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  > /dev/null || true

# Trigger RIS HL7 simulation endpoint
curl -s -X POST "http://localhost:8081/api/hl7/admit" \
  -H "Content-Type: application/json" \
  -d '{"patient_id":"DIC000001","event":"ADT-A01","source":"seed-script"}' \
  > /dev/null || true

# Generate filesystem events in PACS DICOM directory for FIM
docker exec dic-pacs-server bash -lc 'echo "seed-$(date +%s)" >> /opt/dicom_test/seed_activity.txt' 2>/dev/null || true

echo "[seed] Telemetry seeding complete."
