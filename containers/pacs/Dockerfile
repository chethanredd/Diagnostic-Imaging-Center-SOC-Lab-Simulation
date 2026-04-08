FROM ubuntu:22.04
LABEL description="DIC PACS Server — Orthanc + Wazuh Agent"

ENV DEBIAN_FRONTEND=noninteractive
ENV WAZUH_VERSION=4.7.5

# Install base dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    orthanc \
    orthanc-dicomweb \
    python3 \
    python3-pip \
    curl \
    wget \
    gnupg \
    lsb-release \
    dcmtk \
    jq \
    iproute2 \
    net-tools \
    && rm -rf /var/lib/apt/lists/*

# Install Python packages for DICOM generation
RUN pip3 install --no-cache-dir pydicom numpy cryptography scikit-learn

# Create DICOM test directory
RUN mkdir -p /opt/dicom_test /var/lib/orthanc/db /var/log/orthanc

# Copy DICOM generator script
COPY generate_dicom.py /opt/generate_dicom.py

# Wazuh Agent installation
RUN curl -s https://packages.wazuh.com/key/GPG-KEY-WAZUH | gpg --no-default-keyring --keyring gnupg-ring:/usr/share/keyrings/wazuh.gpg --import && \
    chmod 644 /usr/share/keyrings/wazuh.gpg && \
    echo "deb [signed-by=/usr/share/keyrings/wazuh.gpg] https://packages.wazuh.com/4.x/apt/ stable main" | \
    tee -a /etc/apt/sources.list.d/wazuh.list && \
    apt-get update && \
    apt-get install -y "wazuh-agent=${WAZUH_VERSION}-1" || \
    echo "Wazuh agent install skipped (no internet or already installed)"

# Agent configuration
COPY ossec_agent.conf /var/ossec/etc/ossec.conf.tmpl

# Orthanc log symlink for Wazuh monitoring
RUN ln -sf /dev/stdout /var/log/orthanc/orthanc.log || true

# Entrypoint
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8042 4242

ENTRYPOINT ["/entrypoint.sh"]
