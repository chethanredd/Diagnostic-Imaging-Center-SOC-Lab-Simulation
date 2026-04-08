#!/usr/bin/env python3
"""
threat_intel.py — IOC enrichment via VirusTotal + AbuseIPDB
Used by Shuffle SOAR playbooks for automated alert enrichment.
"""
import json
import os
import sys
import requests

VT_API_KEY    = os.environ.get("VT_API_KEY",    "YOUR_VIRUSTOTAL_KEY")
ABUSE_API_KEY = os.environ.get("ABUSE_API_KEY", "YOUR_ABUSEIPDB_KEY")


def check_virustotal(ioc: str, ioc_type: str = "ip") -> dict:
    endpoints = {
        "ip":     f"https://www.virustotal.com/api/v3/ip_addresses/{ioc}",
        "domain": f"https://www.virustotal.com/api/v3/domains/{ioc}",
        "hash":   f"https://www.virustotal.com/api/v3/files/{ioc}",
    }
    headers = {"x-apikey": VT_API_KEY}
    try:
        resp = requests.get(endpoints[ioc_type], headers=headers, timeout=10)
        if resp.status_code == 200:
            stats = resp.json()["data"]["attributes"].get("last_analysis_stats", {})
            return {
                "malicious":  stats.get("malicious", 0),
                "suspicious": stats.get("suspicious", 0),
                "harmless":   stats.get("harmless", 0),
                "verdict":    "MALICIOUS" if stats.get("malicious", 0) > 3 else "CLEAN",
                "source":     "virustotal",
            }
        return {"error": f"HTTP {resp.status_code}", "source": "virustotal"}
    except Exception as e:
        return {"error": str(e), "source": "virustotal"}


def check_abuseipdb(ip: str) -> dict:
    url = "https://api.abuseipdb.com/api/v2/check"
    headers = {"Key": ABUSE_API_KEY, "Accept": "application/json"}
    params  = {"ipAddress": ip, "maxAgeInDays": 90, "verbose": True}
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=10)
        if resp.status_code == 200:
            d = resp.json()["data"]
            score = d.get("abuseConfidenceScore", 0)
            return {
                "abuse_score":   score,
                "total_reports": d.get("totalReports", 0),
                "country":       d.get("countryCode", ""),
                "isp":           d.get("isp", ""),
                "verdict": ("HIGH RISK"   if score > 75 else
                            "MEDIUM RISK" if score > 25 else "LOW RISK"),
                "source": "abuseipdb",
            }
        return {"error": f"HTTP {resp.status_code}", "source": "abuseipdb"}
    except Exception as e:
        return {"error": str(e), "source": "abuseipdb"}


def enrich_alert(alert_json: dict) -> dict:
    src_ip = alert_json.get("data", {}).get("srcip")
    if not src_ip:
        return alert_json
    vt    = check_virustotal(src_ip, "ip")
    abuse = check_abuseipdb(src_ip)
    alert_json["threat_intel"] = {
        "virustotal": vt,
        "abuseipdb":  abuse,
        "enriched":   True,
    }
    if vt.get("verdict") == "MALICIOUS" or abuse.get("verdict") == "HIGH RISK":
        alert_json["enriched_severity"] = "CRITICAL"
        alert_json["auto_block"] = True
    return alert_json


def main():
    import argparse
    parser = argparse.ArgumentParser(description="DIC Threat Intelligence Enrichment")
    parser.add_argument("ip", nargs="?", default="185.220.101.50", help="IP to check")
    parser.add_argument("--json", action="store_true", help="Output JSON only")
    args = parser.parse_args()

    ip = args.ip
    if not args.json:
        print(f"\n[THREAT-INTEL] Checking IP: {ip}")
        print("-" * 50)

    vt_result    = check_virustotal(ip, "ip")
    abuse_result = check_abuseipdb(ip)

    result = {
        "ip":         ip,
        "virustotal": vt_result,
        "abuseipdb":  abuse_result,
    }

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"VirusTotal  : {json.dumps(vt_result, indent=2)}")
        print(f"AbuseIPDB   : {json.dumps(abuse_result, indent=2)}")
        overall = ("🔴 MALICIOUS" if vt_result.get("verdict") == "MALICIOUS" or
                   abuse_result.get("verdict") == "HIGH RISK" else "🟢 CLEAN")
        print(f"\nVerdict: {overall}")


if __name__ == "__main__":
    main()
