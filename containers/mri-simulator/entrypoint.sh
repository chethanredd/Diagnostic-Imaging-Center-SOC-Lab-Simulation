#!/usr/bin/env bash
set -e

PACS_HOST="${PACS_HOST:-10.10.10.10}"
PACS_PORT="${PACS_PORT:-4242}"
MODALITY="${MODALITY:-MR}"
SEND_INTERVAL="${SEND_INTERVAL:-120}"
OUTPUT_DIR="/opt/dicom_test"

echo "[${MODALITY}-SIM] Starting DIC ${MODALITY} Simulator"
echo "[${MODALITY}-SIM] Target PACS: ${PACS_HOST}:${PACS_PORT}"
echo "[${MODALITY}-SIM] Send interval: ${SEND_INTERVAL}s"

# Generate initial batch of DICOM files
python3 /opt/generate_dicom.py \
  --count 10 \
  --output "${OUTPUT_DIR}" \
  --modality "${MODALITY}" \
  --patients 5

echo "[${MODALITY}-SIM] Initial DICOM files generated."

# Wait for PACS to be ready
echo "[${MODALITY}-SIM] Waiting for PACS server at ${PACS_HOST}:${PACS_PORT}..."
RETRIES=0
until nc -z "${PACS_HOST}" "${PACS_PORT}" 2>/dev/null || [[ $RETRIES -gt 30 ]]; do
  sleep 5
  RETRIES=$((RETRIES + 1))
  echo "[${MODALITY}-SIM] Still waiting for PACS... (${RETRIES}/30)"
done

if nc -z "${PACS_HOST}" "${PACS_PORT}" 2>/dev/null; then
  echo "[${MODALITY}-SIM] PACS reachable. Starting transmission loop."
else
  echo "[${MODALITY}-SIM] WARNING: PACS not reachable, will retry on each send cycle."
fi

# ── Continuous send loop ────────────────────────────────────────
CYCLE=0
while true; do
  CYCLE=$((CYCLE + 1))
  echo ""
  echo "[${MODALITY}-SIM] === Send cycle #${CYCLE} at $(date) ==="

  # Generate 2 new images per cycle
  python3 /opt/generate_dicom.py \
    --count 2 \
    --output "${OUTPUT_DIR}" \
    --modality "${MODALITY}" \
    --patients 1 2>/dev/null || echo "[${MODALITY}-SIM] Generate skipped"

  # Send DICOM files using storescu (dcmtk)
  DCM_FILES=$(ls "${OUTPUT_DIR}"/*.dcm 2>/dev/null | head -3)
  if [[ -n "${DCM_FILES}" ]]; then
    for DCM_FILE in ${DCM_FILES}; do
      echo "[${MODALITY}-SIM] Sending $(basename ${DCM_FILE}) to PACS..."
      storescu \
        -aec DIC-PACS \
        -aet "${MODALITY}-SIM" \
        "${PACS_HOST}" "${PACS_PORT}" \
        "${DCM_FILE}" 2>&1 | tail -3 || \
        echo "[${MODALITY}-SIM] storescu: PACS not ready yet"
    done
  fi

  # Also send via Orthanc REST API as fallback
  for DCM_FILE in ${DCM_FILES:-}; do
    curl -s -u orthanc:orthanc \
      -X POST "http://${PACS_HOST}:8042/instances" \
      --data-binary @"${DCM_FILE}" \
      -H "Content-Type: application/dicom" \
      -o /dev/null && echo "[${MODALITY}-SIM] Sent via REST API" || true
  done

  echo "[${MODALITY}-SIM] Cycle #${CYCLE} complete. Sleeping ${SEND_INTERVAL}s..."
  sleep "${SEND_INTERVAL}"
done
