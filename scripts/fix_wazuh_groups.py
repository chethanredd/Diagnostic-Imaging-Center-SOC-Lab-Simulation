#!/usr/bin/env python3
"""
fix_wazuh_groups.py
Live fix: creates /var/ossec/etc/shared/{default,dic-linux,pacs-server,ris-server}/agent.conf
Eliminates the recurring wazuh-db 'groups empty' WARNING.
Run: docker exec dic-wazuh-manager python3 /tmp/fix_wazuh_groups.py
"""
import os
import subprocess

GROUPS = ['default', 'dic-linux', 'pacs-server', 'ris-server']
BASE   = '/var/ossec/etc/shared'

# Minimal but valid agent.conf that satisfies wazuh-db
AGENT_CONF = """<agent_config>
  <!-- DIC SOC Lab — group config managed by dic-soc-lab repo -->
  <syscheck>
    <disabled>no</disabled>
    <frequency>300</frequency>
    <scan_on_start>yes</scan_on_start>
    <alert_new_files>yes</alert_new_files>
    <directories check_all="yes">/etc,/usr/bin,/usr/sbin,/bin,/sbin</directories>
    <ignore>/proc</ignore>
    <ignore>/sys</ignore>
  </syscheck>

  <localfile>
    <log_format>syslog</log_format>
    <location>/var/log/syslog</location>
  </localfile>

  <localfile>
    <log_format>syslog</log_format>
    <location>/var/log/auth.log</location>
  </localfile>

  <active-response>
    <disabled>no</disabled>
  </active-response>
</agent_config>
"""

def fix():
    ok = []
    for group in GROUPS:
        d = os.path.join(BASE, group)
        os.makedirs(d, exist_ok=True)
        conf_path = os.path.join(d, 'agent.conf')
        with open(conf_path, 'w') as f:
            f.write(AGENT_CONF)
        ok.append(conf_path)
        print(f'[OK] {conf_path}')

    # Fix ownership (wazuh or ossec depending on install)
    for user in ['wazuh', 'ossec']:
        r = subprocess.run(['chown', '-R', f'{user}:{user}', BASE],
                           capture_output=True)
        if r.returncode == 0:
            print(f'[OK] chown {user}:{user} {BASE}')
            break

    # Fix file permissions
    subprocess.run(
        ['find', BASE, '-name', 'agent.conf', '-exec', 'chmod', '640', '{}', '+'],
        capture_output=True
    )

    print('\n[+] Done. Group directories:')
    for item in sorted(os.listdir(BASE)):
        p = os.path.join(BASE, item)
        if os.path.isdir(p):
            files = os.listdir(p)
            print(f'    {item}/ -> {files}')

    print('\n[+] Reloading Wazuh manager to pick up new groups...')
    for cmd in [
        ['/var/ossec/bin/wazuh-control', 'reload'],
        ['/var/ossec/bin/ossec-control', 'reload'],
    ]:
        r = subprocess.run(cmd, capture_output=True)
        if r.returncode == 0:
            print(f'[OK] {" ".join(cmd)}')
            break
    else:
        # Kill -HUP the wazuh-modulesd / wazuh-db so they re-scan groups
        subprocess.run(['pkill', '-HUP', '-f', 'wazuh-db'], capture_output=True)
        print('[OK] Sent HUP to wazuh-db')

if __name__ == '__main__':
    fix()
