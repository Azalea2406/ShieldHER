"""
HerMap Demo Test Script
Run this to simulate the live demo: reports coming in, scores rising, alert triggering.
Usage: python test_hermap.py
"""

import requests
import time

BASE = "http://localhost:8000"

def separator(title):
    print(f"\n{'─'*50}")
    print(f"  {title}")
    print('─'*50)

# ── 1. Check API is alive ──
separator("1. API Health Check")
r = requests.get(f"{BASE}/")
print(r.json())

# ── 2. Submit a low-severity report ──
separator("2. Submit: Poor Lighting (low severity)")
r = requests.post(f"{BASE}/report", json={
    "latitude": 17.3850,
    "longitude": 78.4867,
    "incident_type": "poor_lighting",
    "description": "Street light broken near bus stop",
    "severity": 3
})
print(r.json())

# ── 3. Submit a medium report in same zone ──
separator("3. Submit: Suspicious person (medium severity)")
r = requests.post(f"{BASE}/report", json={
    "latitude": 17.3851,   # same zone after rounding
    "longitude": 78.4868,
    "incident_type": "suspicious_person",
    "severity": 6
})
print(r.json())

# ── 4. Submit high-severity reports to trigger alert ──
separator("4. Submit: Harassment — watch score rise and ALERT trigger")
for i in range(5):
    r = requests.post(f"{BASE}/report", json={
        "latitude": 17.3850,
        "longitude": 78.4867,
        "incident_type": "harassment",
        "description": f"Incident report #{i+1}",
        "severity": 9
    })
    resp = r.json()
    print(f"  Report {i+1}: zone_score = {resp['current_zone_score']}")
    time.sleep(0.3)

# ── 5. Get full heatmap ──
separator("5. Heatmap — all active zones")
r = requests.get(f"{BASE}/heatmap")
data = r.json()
for zone in data["zones"]:
    print(f"  Zone {zone['zone_id']} | Score: {zone['score']} | Risk: {zone['risk_level']} | Reports: {zone['report_count']}")

# ── 6. Check for alerts ──
separator("6. Authority Alert Check")
r = requests.get(f"{BASE}/alerts/check")
print(r.json())

print("\n✅ Demo complete. Judges can see the system thinking in real time.\n")
