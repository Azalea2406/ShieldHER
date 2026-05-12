"""
risk_engine.py
--------------
Risk Scoring Engine for ShieldHER

Provides:
GET /api/risk/zone?lat=...&lng=...

Returns risk score (0-100) based on:
- nearby unsafe zones
- time of day
- darkness
- isolation
"""

from fastapi import APIRouter, Query
from datetime import datetime
import math

router = APIRouter()

# --------------------------------------------------
# Known unsafe zones
# (lat, lng, radius_in_meters, severity_weight)
# --------------------------------------------------

UNSAFE_ZONES = [
    (17.3616, 78.4747, 500, 0.9),   # Secunderabad
    (17.3850, 78.4867, 300, 0.7),   # Central Hyderabad
    (17.4239, 78.4738, 400, 0.8),   # Isolated stretch
]


# --------------------------------------------------
# Distance helper
# --------------------------------------------------

def haversine(lat1, lng1, lat2, lng2):
    R = 6371000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)

    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)

    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1)
        * math.cos(phi2)
        * math.sin(dlambda / 2) ** 2
    )

    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# --------------------------------------------------
# Risk calculations
# --------------------------------------------------

def zone_risk(lat, lng):
    score = 0

    for z_lat, z_lng, radius, weight in UNSAFE_ZONES:
        dist = haversine(lat, lng, z_lat, z_lng)

        if dist <= radius:
            proximity = 1 - (dist / radius)
            score += proximity * weight * 40

    return min(score, 40)


def time_risk():
    hour = datetime.now().hour

    if 22 <= hour or hour < 5:
        return 25
    elif 18 <= hour < 22:
        return 15
    else:
        return 5


def darkness_risk():
    hour = datetime.now().hour

    if 19 <= hour or hour < 6:
        return 20
    return 5


def isolation_risk():
    # Placeholder static risk
    return 15


def calculate_total_risk(lat, lng):
    score = (
        zone_risk(lat, lng)
        + time_risk()
        + darkness_risk()
        + isolation_risk()
    )

    return min(round(score, 2), 100)


# --------------------------------------------------
# API endpoint
# --------------------------------------------------

@router.get("/api/risk/zone")
def get_risk_score(
    lat: float = Query(...),
    lng: float = Query(...)
):
    risk = calculate_total_risk(lat, lng)

    return {
        "lat": lat,
        "lng": lng,
        "risk_score": risk,
        "risk_level": (
            "High"
            if risk >= 70
            else "Medium"
            if risk >= 40
            else "Low"
        )
    }