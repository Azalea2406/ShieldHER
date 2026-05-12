"""
HerMap Community Backend — ShieldHer
Handles: incident reports, decay scoring, heatmap data, authority alerts
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime
from typing import Optional
import math
import uuid

app = FastAPI(title="HerMap API", version="1.0")

# Allow Flutter app and React dashboard to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────────
# IN-MEMORY STORE (replace with PostgreSQL later)
# ─────────────────────────────────────────────
reports_db: list[dict] = []

# ─────────────────────────────────────────────
# MODELS
# ─────────────────────────────────────────────
class IncidentReport(BaseModel):
    latitude: float
    longitude: float
    incident_type: str          # e.g. "harassment", "poor_lighting", "suspicious_person"
    description: Optional[str] = None
    severity: int = 5           # 1 (minor) to 10 (critical)

class ReportResponse(BaseModel):
    report_id: str
    zone_id: str
    message: str
    current_zone_score: float

# ─────────────────────────────────────────────
# UTILITY: Snap lat/lng to a 100m zone grid
# ─────────────────────────────────────────────
def get_zone_id(lat: float, lng: float) -> str:
    """Round coordinates to ~100m grid cells."""
    zone_lat = round(lat * 1000) / 1000   # ~111m precision
    zone_lng = round(lng * 1000) / 1000
    return f"{zone_lat}_{zone_lng}"

# ─────────────────────────────────────────────
# CORE: Decay-Weighted Scoring
# ─────────────────────────────────────────────
DECAY_FACTOR = 0.1   # Weight halves roughly every 7 hours
ALERT_THRESHOLD = 70 # Score above this triggers authority alert

def compute_zone_score(zone_id: str) -> float:
    """
    Score = sum(severity * decay_weight) for all reports in zone
    decay_weight = e^(-decay_factor * hours_since_report)
    Normalized to 0–100 scale.
    """
    now = datetime.utcnow()
    zone_reports = [r for r in reports_db if r["zone_id"] == zone_id]

    if not zone_reports:
        return 0.0

    total_weight = 0.0
    for report in zone_reports:
        reported_at = datetime.fromisoformat(report["timestamp"])
        hours_elapsed = (now - reported_at).total_seconds() / 3600
        decay_weight = math.exp(-DECAY_FACTOR * hours_elapsed)
        total_weight += report["severity"] * decay_weight

    # Normalize: max theoretical score (10 severity * 1.0 decay * 10 reports) = 100
    normalized = min((total_weight / 10) * 10, 100)
    return round(normalized, 2)

# ─────────────────────────────────────────────
# AUTHORITY ALERT (stub — replace with SMS/email)
# ─────────────────────────────────────────────
def trigger_authority_alert(zone_id: str, score: float):
    """
    In production: call Twilio / send email / push to city dashboard.
    For hackathon demo: prints to console and logs to alerts list.
    """
    print(f"🚨 ALERT: Zone {zone_id} score = {score} — Alerting nearest PCR van!")
    # TODO: integrate Twilio or FCM here

# ─────────────────────────────────────────────
# ROUTES
# ─────────────────────────────────────────────

@app.get("/")
def root():
    return {"status": "HerMap API running", "version": "1.0"}


@app.post("/report", response_model=ReportResponse)
def submit_report(report: IncidentReport):
    """
    Submit an anonymous incident report.
    Automatically recalculates zone score and triggers alert if needed.
    """
    report_id = str(uuid.uuid4())[:8]
    zone_id = get_zone_id(report.latitude, report.longitude)
    timestamp = datetime.utcnow().isoformat()

    # Store the report
    reports_db.append({
        "report_id": report_id,
        "zone_id": zone_id,
        "latitude": report.latitude,
        "longitude": report.longitude,
        "incident_type": report.incident_type,
        "description": report.description,
        "severity": report.severity,
        "timestamp": timestamp,
    })

    # Recalculate zone score
    zone_score = compute_zone_score(zone_id)

    # Trigger authority alert if threshold crossed
    if zone_score >= ALERT_THRESHOLD:
        trigger_authority_alert(zone_id, zone_score)

    return ReportResponse(
        report_id=report_id,
        zone_id=zone_id,
        message="Report received. Thank you for keeping your community safe.",
        current_zone_score=zone_score,
    )


@app.get("/heatmap")
def get_heatmap():
    """
    Returns all zones with their current decay-weighted scores.
    Used by Flutter app and React dashboard to render live heatmap.
    """
    zone_ids = set(r["zone_id"] for r in reports_db)
    heatmap = []

    for zone_id in zone_ids:
        lat, lng = zone_id.split("_")
        score = compute_zone_score(zone_id)
        # Include a sample report count for transparency
        count = len([r for r in reports_db if r["zone_id"] == zone_id])
        heatmap.append({
            "zone_id": zone_id,
            "latitude": float(lat),
            "longitude": float(lng),
            "score": score,
            "report_count": count,
            "risk_level": "safe" if score < 40 else "caution" if score < 70 else "high_risk",
        })

    return {"zones": heatmap, "total_zones": len(heatmap)}


@app.get("/zone/{zone_id}")
def get_zone_detail(zone_id: str):
    """
    Detailed view of a specific zone — score + individual reports.
    """
    zone_reports = [r for r in reports_db if r["zone_id"] == zone_id]
    if not zone_reports:
        raise HTTPException(status_code=404, detail="Zone not found or no reports")

    score = compute_zone_score(zone_id)
    return {
        "zone_id": zone_id,
        "score": score,
        "risk_level": "safe" if score < 40 else "caution" if score < 70 else "high_risk",
        "reports": zone_reports,
    }


@app.get("/alerts/check")
def check_all_zones_for_alerts():
    """
    Utility endpoint: scan all zones and return which ones are high risk.
    Can be called by a cron job every 15 minutes.
    """
    zone_ids = set(r["zone_id"] for r in reports_db)
    high_risk_zones = []

    for zone_id in zone_ids:
        score = compute_zone_score(zone_id)
        if score >= ALERT_THRESHOLD:
            high_risk_zones.append({"zone_id": zone_id, "score": score})

    return {
        "high_risk_zones": high_risk_zones,
        "count": len(high_risk_zones),
        "checked_at": datetime.utcnow().isoformat(),
    }
