"""
journey_guardian/journey_guardian.py
--------------------------------------
ShieldHer Journey Guardian — Core Detection Engine

Responsibilities:
  1. Accept a journey (start → destination + user contact info)
  2. Compute expected checkpoints and arrival times along the route
  3. Receive live GPS pings from the user's phone
  4. Run Isolation Forest anomaly detection on the trajectory
  5. On deviation → query risk score → fire appropriate alert

Deviation escalation:
  Zone score < 40  → log only, passive monitoring
  Zone score 40–70 → SMS emergency contact via Twilio
  Zone score > 70  → SMS contact + notify nearest PCR van

Run standalone demo:
    python journey_guardian.py --demo

FIXES applied vs original:
  1. get_zone_risk_score() was calling resp.json().get("score", 50) but
     risk_engine.py returns the key "risk_score". Fixed to "risk_score".
  2. alert_fired flag locked after first alert forever. Now uses a
     cooldown (ALERT_COOLDOWN_SEC = 300) so re-alerts fire after 5 min
     if the user is still deviating — critical for a safety app.
  3. last_alert_time tracked per session so the cooldown works correctly.
"""

import math
import time
import json
import random
import argparse
import os
from datetime import datetime, timezone, timedelta
from typing import Optional
import numpy as np
from sklearn.ensemble import IsolationForest

ALERT_COOLDOWN_SEC = 300   # FIX 2: re-alert after 5 minutes if still deviating


# ── Haversine distance helper ─────────────────────────────────────────────────

def haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Return distance in metres between two GPS coordinates."""
    R = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lng2 - lng1)
    a = (math.sin(dphi / 2) ** 2
         + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ── Checkpoint generator ──────────────────────────────────────────────────────

def generate_checkpoints(
    origin: dict,
    destination: dict,
    num_checkpoints: int = 5,
    speed_mps: float = 1.4,
) -> list[dict]:
    """
    Divide the straight-line route into evenly spaced checkpoints.
    In production, replace linear interpolation with /api/route/safe waypoints.
    """
    total_dist     = haversine(origin["lat"], origin["lng"], destination["lat"], destination["lng"])
    total_time_sec = total_dist / speed_mps
    checkpoints    = []
    now            = datetime.now(timezone.utc)

    for i in range(1, num_checkpoints + 1):
        fraction = i / (num_checkpoints + 1)
        cp_lat   = origin["lat"] + fraction * (destination["lat"] - origin["lat"])
        cp_lng   = origin["lng"] + fraction * (destination["lng"] - origin["lng"])
        cp_time  = now + timedelta(seconds=total_time_sec * fraction)

        checkpoints.append({
            "index":         i,
            "lat":           round(cp_lat, 6),
            "lng":           round(cp_lng, 6),
            "expected_time": cp_time.isoformat(),
            "tolerance_sec": 120,
            "reached":       False,
        })

    # Final destination as last checkpoint
    checkpoints.append({
        "index":         num_checkpoints + 1,
        "lat":           destination["lat"],
        "lng":           destination["lng"],
        "expected_time": (now + timedelta(seconds=total_time_sec)).isoformat(),
        "tolerance_sec": 180,
        "reached":       False,
    })

    return checkpoints


# ── Isolation Forest anomaly detector ────────────────────────────────────────

class DeviationDetector:
    """
    Trains an Isolation Forest on 'normal' GPS trajectories,
    then flags anomalous pings in real time.

    Features per GPS ping:
      [lat, lng, speed_mps, heading_deg, dist_from_expected_m, delay_sec]
    """

    def __init__(self, contamination: float = 0.05):
        self.model = IsolationForest(
            n_estimators=100,
            contamination=contamination,
            random_state=42
        )
        self.is_trained = False
        self._training_data: list[list[float]] = []

    def _featurize(
        self,
        lat: float,
        lng: float,
        speed_mps: float,
        heading_deg: float,
        dist_from_expected_m: float,
        delay_sec: float,
    ) -> list[float]:
        return [lat, lng, speed_mps, heading_deg, dist_from_expected_m, delay_sec]

    def add_training_sample(self, **kwargs) -> None:
        self._training_data.append(self._featurize(**kwargs))

    def train(self) -> None:
        if len(self._training_data) < 10:
            print("⚠️  Not enough training samples — using rule-based detection only.")
            return
        X = np.array(self._training_data)
        self.model.fit(X)
        self.is_trained = True
        print(f"✅  Isolation Forest trained on {len(self._training_data)} samples.")

    def is_anomaly(self, **kwargs) -> tuple[bool, float]:
        """
        Returns (is_anomaly: bool, anomaly_score: float).
        Falls back to rule-based check if model not trained yet.
        """
        features = np.array([self._featurize(**kwargs)])

        if not self.is_trained:
            dist   = kwargs.get("dist_from_expected_m", 0)
            delay  = kwargs.get("delay_sec", 0)
            anomaly = dist > 200 or delay > 300
            return anomaly, -1.0 if anomaly else 0.5

        pred  = self.model.predict(features)[0]
        score = self.model.score_samples(features)[0]
        return (pred == -1), float(score)


# ── Alert dispatcher ──────────────────────────────────────────────────────────

def get_zone_risk_score(lat: float, lng: float) -> int:
    """
    Fetch the current risk score for a zone from the Risk Engine API.
    Returns an integer 0–100.
    """
    try:
        import requests
        resp = requests.get(
            "http://localhost:8000/api/risk/zone",
            params={"lat": lat, "lng": lng},
            timeout=5
        )
        if resp.status_code == 200:
            # FIX 1: risk_engine.py returns "risk_score", not "score"
            return resp.json().get("risk_score", 50)
    except Exception:
        pass

    # Demo fallback — simulate based on time of day
    hour = datetime.now().hour
    if 22 <= hour or hour < 5:
        return random.randint(60, 90)
    elif 18 <= hour < 22:
        return random.randint(35, 65)
    else:
        return random.randint(10, 40)


def send_alert(
    journey: dict,
    ping: dict,
    risk_score: int,
    anomaly_score: float,
) -> None:
    """
    Fire the appropriate alert based on risk score tier.

    Tier 1 (score < 40)  → log only
    Tier 2 (score 40–70) → SMS emergency contact
    Tier 3 (score > 70)  → SMS contact + PCR van alert
    """
    user_name = journey.get("user_name", "User")
    contact   = journey.get("emergency_contact", "Unknown")
    lat, lng  = ping["lat"], ping["lng"]
    maps_link = f"https://maps.google.com/?q={lat},{lng}"
    timestamp = datetime.now().strftime("%H:%M, %d %b")

    if risk_score < 40:
        print(f"\n📋 [LOG] Deviation detected for {user_name}")
        print(f"   Zone risk: {risk_score}/100 — passive monitoring only.")

    elif 40 <= risk_score <= 70:
        message = (
            f"⚠️ ShieldHer Alert: {user_name} may need help.\n"
            f"Deviation detected at {timestamp}.\n"
            f"Last known location: {maps_link}\n"
            f"Zone risk score: {risk_score}/100. Please check in."
        )
        print(f"\n📱 [SMS → {contact}]\n   {message}")
        _send_twilio_sms(contact, message, journey.get("journey_id"))

    else:  # risk_score > 70
        message = (
            f"🚨 URGENT — ShieldHer Alert: {user_name} is in a HIGH RISK zone.\n"
            f"Deviation detected at {timestamp}.\n"
            f"Last known location: {maps_link}\n"
            f"Zone risk score: {risk_score}/100. Immediate attention required."
        )
        print(f"\n🚨 [SMS → {contact}]\n   {message}")
        _send_twilio_sms(contact, message, journey.get("journey_id"))
        _alert_pcr_van(lat, lng, user_name, risk_score)


def _send_twilio_sms(to_number: str, message: str, journey_id: str) -> None:
    """
    Send SMS via Twilio.
    Requires TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM_NUMBER in .env
    """
    try:
        from twilio.rest import Client
        client = Client(
            os.getenv("TWILIO_ACCOUNT_SID"),
            os.getenv("TWILIO_AUTH_TOKEN")
        )
        client.messages.create(
            body=message,
            from_=os.getenv("TWILIO_FROM_NUMBER"),
            to=to_number
        )
        print(f"   ✅ Twilio SMS sent to {to_number}")
    except ImportError:
        print("   ⚠️  twilio package not installed — SMS skipped (demo mode)")
    except Exception as e:
        print(f"   ❌ Twilio error: {e}")


def _alert_pcr_van(lat: float, lng: float, user_name: str, risk_score: int) -> None:
    """
    Notify nearest PCR van via backend endpoint.
    POST body matches the Pydantic model in api.py (fixed).
    """
    try:
        import requests
        requests.post(
            "http://localhost:8000/api/journey/alerts/pcr",
            json={
                "lat":        lat,
                "lng":        lng,
                "user_name":  user_name,
                "risk_score": risk_score,
                "timestamp":  datetime.now(timezone.utc).isoformat(),
            },
            timeout=5
        )
        print(f"   ✅ PCR van alerted at ({lat}, {lng})")
    except Exception:
        print(f"   ⚠️  PCR alert endpoint unreachable (demo mode)")


# ── Journey session ───────────────────────────────────────────────────────────

class JourneySession:
    """
    Represents one active journey for one user.
    Holds checkpoints, GPS history, and the anomaly detector.
    """

    def __init__(self, journey: dict):
        self.journey        = journey
        self.journey_id     = journey["journey_id"]
        self.checkpoints    = generate_checkpoints(journey["origin"], journey["destination"])
        self.detector       = DeviationDetector()
        self.gps_history:   list[dict] = []
        self.alert_fired    = False
        self.completed      = False
        self.last_alert_time: Optional[datetime] = None   # FIX 2: track cooldown

        self._pretrain()

        print(f"\n🛡️  Journey started: {self.journey_id}")
        print(f"   From : {journey['origin']}")
        print(f"   To   : {journey['destination']}")
        print(f"   User : {journey.get('user_name', 'Unknown')}")
        print(f"   Checkpoints: {len(self.checkpoints)}")

    def _pretrain(self) -> None:
        """Generate synthetic 'normal journey' samples to bootstrap the model."""
        origin = self.journey["origin"]
        dest   = self.journey["destination"]
        for _ in range(50):
            frac = random.random()
            lat  = origin["lat"] + frac * (dest["lat"] - origin["lat"]) + random.gauss(0, 0.0001)
            lng  = origin["lng"] + frac * (dest["lng"] - origin["lng"]) + random.gauss(0, 0.0001)
            self.detector.add_training_sample(
                lat=lat, lng=lng,
                speed_mps=random.uniform(0.8, 2.0),
                heading_deg=random.uniform(0, 360),
                dist_from_expected_m=random.uniform(0, 50),
                delay_sec=random.uniform(0, 60),
            )
        self.detector.train()

    def _nearest_checkpoint(self) -> Optional[dict]:
        for cp in self.checkpoints:
            if not cp["reached"]:
                return cp
        return None

    def _should_alert(self) -> bool:
        """
        FIX 2: Allow re-alerting after ALERT_COOLDOWN_SEC.
        First alert always fires; subsequent ones only after cooldown.
        """
        if self.last_alert_time is None:
            return True
        elapsed = (datetime.now(timezone.utc) - self.last_alert_time).total_seconds()
        return elapsed >= ALERT_COOLDOWN_SEC

    def process_ping(self, lat: float, lng: float, speed_mps: float = 1.4) -> dict:
        """
        Process one GPS ping from the user.
        Returns a status dict with deviation info and any alert fired.
        """
        now  = datetime.now(timezone.utc)
        ping = {"lat": lat, "lng": lng, "speed_mps": speed_mps, "timestamp": now.isoformat()}
        self.gps_history.append(ping)

        cp = self._nearest_checkpoint()
        if cp is None:
            self.completed = True
            return {"status": "completed", "message": "Journey completed safely. ✅"}

        dist_from_expected = haversine(lat, lng, cp["lat"], cp["lng"])
        expected_dt        = datetime.fromisoformat(cp["expected_time"])
        if expected_dt.tzinfo is None:
            expected_dt = expected_dt.replace(tzinfo=timezone.utc)
        delay_sec          = max(0, (now - expected_dt).total_seconds())

        heading = 0.0
        if len(self.gps_history) >= 2:
            prev = self.gps_history[-2]
            dy   = lat - prev["lat"]
            dx   = lng - prev["lng"]
            heading = math.degrees(math.atan2(dx, dy)) % 360

        is_anomaly, anomaly_score = self.detector.is_anomaly(
            lat=lat, lng=lng,
            speed_mps=speed_mps,
            heading_deg=heading,
            dist_from_expected_m=dist_from_expected,
            delay_sec=delay_sec,
        )

        if dist_from_expected < 80:
            cp["reached"] = True
            print(f"   ✅ Checkpoint {cp['index']} reached.")

        result = {
            "ping":                  ping,
            "checkpoint":            cp["index"],
            "dist_from_expected_m":  round(dist_from_expected, 1),
            "delay_sec":             round(delay_sec, 1),
            "anomaly_score":         round(anomaly_score, 3),
            "is_deviation":          is_anomaly,
            "alert_fired":           False,
        }

        # FIX 2: fire alert on every deviation after cooldown, not just the first ever
        if is_anomaly and self._should_alert():
            risk_score = get_zone_risk_score(lat, lng)
            send_alert(self.journey, ping, risk_score, anomaly_score)
            result["alert_fired"] = True
            result["risk_score"]  = risk_score
            self.alert_fired      = True
            self.last_alert_time  = now   # FIX 2: record time for cooldown

        return result


# ── Demo simulation ───────────────────────────────────────────────────────────

def run_demo():
    print("=" * 60)
    print("  ShieldHer Journey Guardian — Demo Mode")
    print("=" * 60)

    journey = {
        "journey_id":        "JRN-DEMO-001",
        "user_name":         "Priya",
        "emergency_contact": "+91-9999999999",
        "origin":            {"lat": 17.3850, "lng": 78.4867},
        "destination":       {"lat": 17.4400, "lng": 78.4500},
    }

    session = JourneySession(journey)

    print("\n--- Simulating normal pings ---")
    origin = journey["origin"]
    dest   = journey["destination"]

    for i in range(4):
        frac   = (i + 1) / 6
        lat    = origin["lat"] + frac * (dest["lat"] - origin["lat"])
        lng    = origin["lng"] + frac * (dest["lng"] - origin["lng"])
        result = session.process_ping(lat, lng, speed_mps=1.4)
        print(f"   Ping {i+1}: dist_from_expected={result['dist_from_expected_m']}m  "
              f"anomaly={result['is_deviation']}")
        time.sleep(0.3)

    print("\n--- Simulating DEVIATION (sudden detour) ---")
    result = session.process_ping(lat=17.3616, lng=78.5500, speed_mps=0.2)
    print(f"   Deviation ping: dist_from_expected={result['dist_from_expected_m']}m  "
          f"anomaly={result['is_deviation']}  alert_fired={result['alert_fired']}")
    if result.get("risk_score"):
        print(f"   Zone risk score: {result['risk_score']}/100")

    print("\n✅ Demo complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--demo", action="store_true", help="Run standalone demo simulation")
    args = parser.parse_args()
    if args.demo:
        run_demo()
