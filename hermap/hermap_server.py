"""
hermap/backend/hermap_server.py
--------------------------------
HerMap Community Backend — ShieldHer
Handles: incident reports, decay scoring, heatmap data, authority alerts

Run:
    uvicorn hermap_server:app --reload --port 8000

FIXES applied vs original main(1).py:
  1. alerts_db list added — trigger_authority_alert() now stores fired alerts
     so /alerts/check returns real data instead of always showing count=0.
  2. /alerts/check now returns the persisted alerts_db, not a re-scan
     (re-scanning finds zones above threshold but never showed *when* alert fired).
  3. datetime.utcnow() replaced with datetime.now(timezone.utc) throughout
     to avoid DeprecationWarning in Python 3.12+ and ensure consistent
     timezone-aware comparisons in compute_zone_score().
  4. Severity validated: clamped to 1–10 so a bad client payload cannot
     inflate zone scores arbitrarily.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from datetime import datetime, timezone
from typing import Optional
import math
import uuid

app = FastAPI(title="HerMap API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────────
# IN-MEMORY STORES  (replace with PostgreSQL later)
# ─────────────────────────────────────────────
reports_db: list[dict] = []
alerts_db:  list[dict] = []   # FIX 1: was missing — authority alerts are now persisted here


# ─────────────────────────────────────────────
# MODELS
# ─────────────────────────────────────────────

class IncidentReport(BaseModel):
    latitude: float
    longitude: float
    incident_type: str
    description: Optional[str] = None
    severity: int = Field(default=5, ge=1, le=10)   # FIX 4: clamp 1–10


class ReportResponse(BaseModel):
    report_id: str
    zone_id: str
    message: str
    current_zone_score: float


# ─────────────────────────────────────────────
# UTILITY: Snap lat/lng to a ~100m zone grid
# ─────────────────────────────────────────────

def get_zone_id(lat: float, lng: float) -> str:
    zone_lat = round(lat * 1000) / 1000
    zone_lng = round(lng * 1000) / 1000
    return f"{zone_lat}_{zone_lng}"


# ─────────────────────────────────────────────
# CORE: Decay-Weighted Scoring
# ─────────────────────────────────────────────

DECAY_FACTOR    = 0.1   # weight halves roughly every 7 hours
ALERT_THRESHOLD = 70    # zone score above this triggers authority alert

def compute_zone_score(zone_id: str) -> float:
    """
    Score = sum(severity * decay_weight) for all reports in zone.
    decay_weight = e^(-DECAY_FACTOR * hours_since_report)
    Normalized to 0–100 scale.
    """
    # FIX 3: use timezone-aware now() so subtraction never raises TypeError
    now = datetime.now(timezone.utc)
    zone_reports = [r for r in reports_db if r["zone_id"] == zone_id]

    if not zone_reports:
        return 0.0

    total_weight = 0.0
    for report in zone_reports:
        reported_at = datetime.fromisoformat(report["timestamp"])
        # Ensure reported_at is timezone-aware for safe subtraction
        if reported_at.tzinfo is None:
            reported_at = reported_at.replace(tzinfo=timezone.utc)
        hours_elapsed = (now - reported_at).total_seconds() / 3600
        decay_weight  = math.exp(-DECAY_FACTOR * hours_elapsed)
        total_weight += report["severity"] * decay_weight

    normalized = min(total_weight, 100)   # already on 0–100 scale (max 10 severity × 10 reports × 1.0 decay = 100)
    return round(normalized, 2)


# ─────────────────────────────────────────────
# AUTHORITY ALERT
# ─────────────────────────────────────────────

def trigger_authority_alert(zone_id: str, score: float) -> None:
    """
    FIX 1: Alerts are now stored in alerts_db so /alerts/check can return them.
    In production: integrate Twilio / FCM / city dispatch here.
    """
    alert = {
        "alert_id":   str(uuid.uuid4())[:8],
        "zone_id":    zone_id,
        "score":      score,
        "triggered_at": datetime.now(timezone.utc).isoformat(),   # FIX 3
    }
    alerts_db.append(alert)
    print(f"🚨 ALERT stored: Zone {zone_id} score={score} — PCR van notified!")
    # TODO: call Twilio or FCM here


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
    Recalculates zone score and triggers an authority alert if threshold crossed.
    """
    report_id = str(uuid.uuid4())[:8]
    zone_id   = get_zone_id(report.latitude, report.longitude)
    timestamp = datetime.now(timezone.utc).isoformat()   # FIX 3

    reports_db.append({
        "report_id":    report_id,
        "zone_id":      zone_id,
        "latitude":     report.latitude,
        "longitude":    report.longitude,
        "incident_type": report.incident_type,
        "description":  report.description,
        "severity":     report.severity,
        "timestamp":    timestamp,
    })

    zone_score = compute_zone_score(zone_id)

    if zone_score >= ALERT_THRESHOLD:
        # Only fire a new alert if none has been fired for this zone in the last hour
        recent = [
            a for a in alerts_db
            if a["zone_id"] == zone_id
            and (datetime.now(timezone.utc) - datetime.fromisoformat(a["triggered_at"])).total_seconds() < 3600
        ]
        if not recent:
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
    Returns all zones with current decay-weighted scores.
    Used by Flutter app and React dashboard.
    """
    zone_ids = set(r["zone_id"] for r in reports_db)
    heatmap  = []

    for zone_id in zone_ids:
        lat_str, lng_str = zone_id.split("_")
        score = compute_zone_score(zone_id)
        count = len([r for r in reports_db if r["zone_id"] == zone_id])
        heatmap.append({
            "zone_id":      zone_id,
            "latitude":     float(lat_str),
            "longitude":    float(lng_str),
            "score":        score,
            "report_count": count,
            "risk_level":   "safe" if score < 40 else "caution" if score < 70 else "high_risk",
        })

    return {"zones": heatmap, "total_zones": len(heatmap)}


@app.get("/zone/{zone_id}")
def get_zone_detail(zone_id: str):
    """Detailed view of a specific zone — score + individual reports."""
    zone_reports = [r for r in reports_db if r["zone_id"] == zone_id]
    if not zone_reports:
        raise HTTPException(status_code=404, detail="Zone not found or no reports")

    score = compute_zone_score(zone_id)
    return {
        "zone_id":    zone_id,
        "score":      score,
        "risk_level": "safe" if score < 40 else "caution" if score < 70 else "high_risk",
        "reports":    zone_reports,
    }


@app.get("/alerts/check")
def check_alerts():
    """
    FIX 2: Now returns the actual alerts_db (alerts that were fired and stored),
    not a re-scan of zone scores. This means the dashboard shows real alert history.
    Also includes a live re-scan of zones currently above threshold.
    """
    # Live re-scan for zones currently above threshold
    zone_ids = set(r["zone_id"] for r in reports_db)
    currently_high = []
    for zone_id in zone_ids:
        score = compute_zone_score(zone_id)
        if score >= ALERT_THRESHOLD:
            currently_high.append({"zone_id": zone_id, "score": score})

    return {
        "alerts_fired":         alerts_db,              # persistent history
        "currently_high_risk":  currently_high,         # live scan
        "count":                len(currently_high),
        "checked_at":           datetime.now(timezone.utc).isoformat(),
    }
