FROM ubuntu:22.04
LABEL description="DIC CT Simulator — Generates and sends DICOM CT images to PACS"

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip dcmtk curl net-tools iproute2 \
    && rm -rf /var/lib/apt/lists/*

RUN pip3 install --no-cache-dir pydicom numpy requests

COPY generate_dicom.py /opt/generate_dicom.py
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
