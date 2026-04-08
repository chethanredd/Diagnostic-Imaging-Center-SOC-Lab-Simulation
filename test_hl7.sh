#!/usr/bin/env bash
# Send the HL7 message natively across the WSL Docker bridge to the real RIS server
docker exec dic-attacker bash -c 'echo "MSH|^~\&|ATTACKER|LAB|RIS|DIC|20260401|ADT^A01" | nc -w 1 10.10.10.20 2575'
sleep 3
# Check logs to see if Host-mode Suricata caught it passing the bridge
docker cp dic-suricata:/var/log/suricata/fast.log /tmp/fast_test.log
cat /tmp/fast_test.log
