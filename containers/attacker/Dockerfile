FROM kalilinux/kali-rolling
LABEL description="DIC SOC Lab — Red Team / Attacker Container"

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    nmap \
    hydra \
    ncat \
    netcat-openbsd \
    python3 \
    python3-pip \
    curl \
    wget \
    jq \
    iproute2 \
    net-tools \
    ldap-utils \
    tcpdump \
    dcmtk \
    sshpass \
    && rm -rf /var/lib/apt/lists/*

RUN pip3 install --no-cache-dir --break-system-packages \
    pydicom \
    numpy \
    cryptography \
    requests \
    scikit-learn

RUN mkdir -p /opt/attacks /opt/dicom_test /var/log

# Copy attack scripts
COPY ransomware_sim.py  /opt/attacks/ransomware_sim.py
COPY phish_server.py    /opt/attacks/phish_server.py
COPY generate_dicom.py  /opt/attacks/generate_dicom.py
COPY threat_intel.py    /opt/attacks/threat_intel.py
COPY anomaly_detector.py /opt/attacks/anomaly_detector.py
COPY run_attacks.sh     /opt/attacks/run_attacks.sh
RUN chmod +x /opt/attacks/run_attacks.sh

# Nice prompt for the demo
RUN echo 'export PS1="\[\033[01;31m\][ATTACKER]\[\033[00m\] \[\033[01;34m\]\w\[\033[00m\]\$ "' >> /root/.bashrc
RUN echo 'echo -e "\033[1;31m"' >> /root/.bashrc
RUN echo 'echo "  ██████╗ ███████╗██████╗     ████████╗███████╗ █████╗ ███╗   ███╗"' >> /root/.bashrc
RUN echo 'echo "  ██╔══██╗██╔════╝██╔══██╗    ╚══██╔══╝██╔════╝██╔══██╗████╗ ████║"' >> /root/.bashrc
RUN echo 'echo "  ██████╔╝█████╗  ██║  ██║       ██║   █████╗  ███████║██╔████╔██║"' >> /root/.bashrc
RUN echo 'echo "  ██╔══██╗██╔══╝  ██║  ██║       ██║   ██╔══╝  ██╔══██║██║╚██╔╝██║"' >> /root/.bashrc
RUN echo 'echo "  ██║  ██║███████╗██████╔╝       ██║   ███████╗██║  ██║██║ ╚═╝ ██║"' >> /root/.bashrc
RUN echo 'echo "  ╚═╝  ╚═╝╚══════╝╚═════╝        ╚═╝   ╚══════╝╚═╝  ╚═╝╚═╝     ╚═╝"' >> /root/.bashrc
RUN echo 'echo -e "\033[1;33m  DIC SOC Lab — Attacker Container | Authorized Use Only\033[0m"' >> /root/.bashrc
RUN echo 'echo ""' >> /root/.bashrc

CMD ["/bin/bash"]
