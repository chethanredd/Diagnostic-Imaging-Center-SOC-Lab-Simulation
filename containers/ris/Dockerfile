FROM python:3.11-slim
LABEL description="DIC RIS Server — Radiology Information System Simulator"

ENV DEBIAN_FRONTEND=noninteractive
ENV WAZUH_VERSION=4.7.5

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl wget gnupg lsb-release net-tools iproute2 ncat \
    && rm -rf /var/lib/apt/lists/*

# Install Wazuh agent for real endpoint monitoring in SOC views
RUN curl -s https://packages.wazuh.com/key/GPG-KEY-WAZUH | gpg --no-default-keyring --keyring gnupg-ring:/usr/share/keyrings/wazuh.gpg --import && \
    chmod 644 /usr/share/keyrings/wazuh.gpg && \
    echo "deb [signed-by=/usr/share/keyrings/wazuh.gpg] https://packages.wazuh.com/4.x/apt/ stable main" > /etc/apt/sources.list.d/wazuh.list && \
    apt-get update && \
    apt-get install -y --no-install-recommends "wazuh-agent=${WAZUH_VERSION}-1" && \
    rm -rf /var/lib/apt/lists/*

RUN pip3 install --no-cache-dir flask flask-cors requests

RUN mkdir -p /opt/ris /var/log/ris

COPY ris_server.py /opt/ris/ris_server.py
COPY ossec_agent.conf /var/ossec/etc/ossec.conf.tmpl
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8080 2575

ENTRYPOINT ["/entrypoint.sh"]
