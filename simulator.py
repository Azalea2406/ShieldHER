"""
beacon_simulator/simulator.py
-------------------------------
Simulates an ESP32 beacon by generating fake PIR (motion),
LDR (light), and crowd-density sensor readings, then POSTing
them to the ShieldHer backend every N seconds.

Usage:
    python simulator.py --backend http://localhost:8000 --interval 60
"""

import argparse
import json
import random
import time
import uuid
from datetime import datetime, timezone

import requests


# ── Beacon identity ──────────────────────────────────────────────────────────

BEACON_ID = str(uuid.uuid4())          # unique per run; replace with a fixed ID for a real beacon
BEACON_LOCATION = {                    # lat/lng of the simulated beacon
    "lat": 17.3850,
    "lng": 78.4867,
    "label": "Hyderabad Central – Simulated Beacon"
}


# ── Sensor simulation helpers ────────────────────────────────────────────────

def simulate_pir() -> dict:
    """Simulate PIR motion sensor.  Returns motion detected + confidence."""
    motion = random.choices([True, False], weights=[30, 70])[0]
    return {
        "motion_detected": motion,
        "confidence": round(random.uniform(0.7, 1.0) if motion else random.uniform(0.0, 0.3), 2)
    }


def simulate_ldr() -> dict:
    """Simulate LDR light sensor.  Returns raw lux value + derived category."""
    hour = datetime.now().hour
    # Simulate realistic lighting: bright day, dim evening, dark night
    if 6 <= hour < 18:
        lux = random.randint(300, 1000)
    elif 18 <= hour < 21:
        lux = random.randint(50, 300)
    else:
        lux = random.randint(0, 50)

    if lux > 300:
        category = "bright"
    elif lux > 80:
        category = "dim"
    else:
        category = "dark"

    return {"lux": lux, "category": category}


def simulate_density() -> dict:
    """Simulate crowd density via a proxy metric (0–100 scale)."""
    density = random.randint(0, 100)
    if density < 20:
        level = "empty"
    elif density < 50:
        level = "sparse"
    elif density < 75:
        level = "moderate"
    else:
        level = "crowded"
    return {"score": density, "level": level}


def build_payload() -> dict:
    """Assemble a full beacon reading payload."""
    return {
        "beacon_id": BEACON_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "location": BEACON_LOCATION,
        "sensors": {
            "pir": simulate_pir(),
            "ldr": simulate_ldr(),
            "density": simulate_density(),
        }
    }


# ── POST to backend ──────────────────────────────────────────────────────────

def post_reading(backend_url: str, payload: dict) -> None:
    endpoint = f"{backend_url.rstrip('/')}/api/beacon/reading"
    try:
        resp = requests.post(endpoint, json=payload, timeout=10)
        resp.raise_for_status()
        print(f"[{payload['timestamp']}] ✅  Posted to {endpoint}  →  {resp.status_code}")
    except requests.exceptions.ConnectionError:
        print(f"[{payload['timestamp']}] ⚠️  Backend unreachable at {endpoint}  (payload logged locally)")
        _log_locally(payload)
    except requests.exceptions.HTTPError as e:
        print(f"[{payload['timestamp']}] ❌  HTTP error: {e}")


def _log_locally(payload: dict) -> None:
    """Fallback: append to a local JSONL file when backend is down."""
    with open("offline_readings.jsonl", "a") as f:
        f.write(json.dumps(payload) + "\n")


# ── Main loop ────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="ShieldHer beacon simulator")
    parser.add_argument("--backend", default="http://localhost:8000", help="Backend base URL")
    parser.add_argument("--interval", type=int, default=60, help="Posting interval in seconds")
    args = parser.parse_args()

    print(f"🚨 ShieldHer Beacon Simulator started")
    print(f"   Beacon ID : {BEACON_ID}")
    print(f"   Location  : {BEACON_LOCATION['label']}")
    print(f"   Backend   : {args.backend}")
    print(f"   Interval  : {args.interval}s\n")

    while True:
        payload = build_payload()
        print(json.dumps(payload["sensors"], indent=2))
        post_reading(args.backend, payload)
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
