#!/usr/bin/env python3
"""
anomaly_detector.py — ML-based anomaly detection for DICOM access patterns.
Uses Isolation Forest on Wazuh alert features.
"""
import json
import sys
import os

try:
    import numpy as np
    from sklearn.ensemble import IsolationForest
    from sklearn.preprocessing import StandardScaler
    HAS_ML = True
except ImportError:
    HAS_ML = False
    print("[ANOMALY] sklearn/numpy not installed — using rule-based fallback")


# ── Baseline "normal" feature vectors ───────────────────────────
# [hour_of_day, rule_level, bytes_sent, login_failures, dicom_access]
BASELINE = [
    [9,  3, 1024,    0, 1],
    [10, 3, 2048,    0, 1],
    [11, 2, 512,     0, 1],
    [14, 3, 1024,    0, 1],
    [15, 3, 2048,    0, 1],
    [9,  5, 1024,    1, 0],
    [10, 4, 768,     0, 1],
    [13, 3, 1536,    0, 1],
    [16, 2, 256,     0, 0],
    [11, 3, 4096,    0, 1],
]

if HAS_ML:
    _scaler = StandardScaler()
    _X      = _scaler.fit_transform(BASELINE)
    _model  = IsolationForest(contamination=0.1, random_state=42)
    _model.fit(_X)


def extract_features(alert: dict) -> list:
    ts   = alert.get("timestamp", "T09:00:00")
    hour = int(ts[11:13]) if len(ts) > 13 else 9
    level   = int(alert.get("rule", {}).get("level", 0))
    bytes_s = int(alert.get("data", {}).get("bytes_sent", 0))
    groups  = alert.get("rule", {}).get("groups", [])
    login_fail = 1 if any("auth" in g for g in groups) else 0
    dicom      = 1 if any("dicom" in g for g in groups) else 0
    return [hour, level, bytes_s, login_fail, dicom]


def score_alert(alert: dict) -> dict:
    features = extract_features(alert)

    if HAS_ML:
        scaled     = _scaler.transform([features])
        score      = float(_model.decision_function(scaled)[0])
        is_anomaly = bool(_model.predict(scaled)[0] == -1)
    else:
        # Simple rule-based fallback
        hour, level, bytes_s = features[0], features[1], features[2]
        is_anomaly = (hour < 6 or hour > 22) or level >= 12 or bytes_s > 50_000_000
        score      = -0.5 if is_anomaly else 0.1

    return {
        "anomaly_score": round(score, 4),
        "is_anomaly":    is_anomaly,
        "risk_level":    ("CRITICAL" if score < -0.4 else
                          "HIGH"     if score < -0.2 else
                          "MEDIUM"   if score < 0.0  else "LOW"),
        "features":      dict(zip(
            ["hour", "rule_level", "bytes_sent", "login_failures", "dicom_access"],
            features
        )),
    }


DEMO_ALERTS = [
    {
        "name": "Normal DICOM transmission (daytime)",
        "timestamp": "2024-01-15T10:30:00+0000",
        "rule": {"level": 3, "groups": ["dicom"]},
        "data": {"bytes_sent": 2048},
    },
    {
        "name": "After-hours DICOM access (2:30 AM)",
        "timestamp": "2024-01-15T02:30:00+0000",
        "rule": {"level": 8, "groups": ["dicom", "after_hours"]},
        "data": {"bytes_sent": 1024},
    },
    {
        "name": "Ransomware: 50 MB encrypted at 3 AM",
        "timestamp": "2024-01-15T03:15:00+0000",
        "rule": {"level": 15, "groups": ["ransomware", "dicom", "critical"]},
        "data": {"bytes_sent": 52_428_800},
    },
    {
        "name": "Brute force SSH (multiple failures)",
        "timestamp": "2024-01-15T14:22:00+0000",
        "rule": {"level": 12, "groups": ["brute_force", "authentication_failure", "ssh"]},
        "data": {"bytes_sent": 0},
    },
    {
        "name": "Large exfiltration (100 MB)",
        "timestamp": "2024-01-15T04:10:00+0000",
        "rule": {"level": 13, "groups": ["exfiltration", "dicom"]},
        "data": {"bytes_sent": 104_857_600},
    },
]


def main():
    print("\n" + "=" * 65)
    print("  DIC SOC Lab — AI Anomaly Detector (Isolation Forest)")
    print("  Trained on normal DICOM access baseline patterns")
    print("=" * 65)

    for alert in DEMO_ALERTS:
        result = score_alert(alert)
        icon   = "🔴" if result["is_anomaly"] else "🟢"
        print(f"\n  {icon} {alert['name']}")
        print(f"     Score  : {result['anomaly_score']:+.4f}  "
              f"({'ANOMALY' if result['is_anomaly'] else 'NORMAL'})")
        print(f"     Risk   : {result['risk_level']}")
        print(f"     Features: hour={result['features']['hour']}, "
              f"level={result['features']['rule_level']}, "
              f"bytes={result['features']['bytes_sent']:,}")

    print("\n" + "=" * 65)
    print("  [ANOMALY] Run with stdin JSON to score live Wazuh alerts:")
    print("  cat alert.json | python3 anomaly_detector.py --stdin")
    print("=" * 65 + "\n")

    if "--stdin" in sys.argv:
        for line in sys.stdin:
            try:
                alert = json.loads(line.strip())
                result = score_alert(alert)
                print(json.dumps(result))
            except Exception as e:
                print(json.dumps({"error": str(e)}))


if __name__ == "__main__":
    main()
