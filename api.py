"""
journey_guardian/api.py
------------------------
FastAPI routes for the Journey Guardian module.

Endpoints:
  POST /api/journey/start       — Register a new journey
  POST /api/journey/ping        — Send a live GPS update
  GET  /api/journey/status      — Get current journey status
  POST /api/journey/end         — Mark journey completed
  POST /api/journey/alerts/pcr  — Internal PCR van alert receiver

Mount this in the shared main FastAPI app:
    from journey_guardian.api import router as journey_router
    app.include_router(journey_router)

FIXES applied vs original:
  1. /alerts/pcr used query params (lat, lng, user_name, risk_score) but
     journey_guardian.py POSTs a JSON body → FastAPI returned 422 on every
     PCR alert. Fixed by adding PcrAlertRequest Pydantic model as body.
  2. /status had a division-by-zero when total_cps == 0. Added guard.
  3. req.origin.dict() deprecated in Pydantic v2 → changed to .model_dump().
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from journey_guardian import JourneySession

router = APIRouter(prefix="/api/journey", tags=["Journey Guardian"])

# In-memory session store (replace with Redis or DB in production)
active_sessions: dict[str, JourneySession] = {}


# ── Request / Response models ─────────────────────────────────────────────────

class Location(BaseModel):
    lat: float
    lng: float


class StartJourneyRequest(BaseModel):
    user_name: str
    emergency_contact: str
    origin: Location
    destination: Location


class PingRequest(BaseModel):
    journey_id: str
    lat: float
    lng: float
    speed_mps: Optional[float] = 1.4


class EndJourneyRequest(BaseModel):
    journey_id: str


# FIX 1: Pydantic body model so journey_guardian.py's JSON POST is accepted
class PcrAlertRequest(BaseModel):
    lat: float
    lng: float
    user_name: str
    risk_score: int
    timestamp: Optional[str] = None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/start")
def start_journey(req: StartJourneyRequest):
    """
    Register a new journey and return a journey_id.

    Example:
        POST /api/journey/start
        {
          "user_name": "Priya",
          "emergency_contact": "+91-9999999999",
          "origin":      {"lat": 17.385, "lng": 78.486},
          "destination": {"lat": 17.440, "lng": 78.450}
        }
    """
    journey_id = f"JRN-{uuid.uuid4().hex[:8].upper()}"

    journey = {
        "journey_id":        journey_id,
        "user_name":         req.user_name,
        "emergency_contact": req.emergency_contact,
        "origin":            req.origin.model_dump(),       # FIX 3: .dict() deprecated in Pydantic v2
        "destination":       req.destination.model_dump(),
        "started_at":        datetime.now(timezone.utc).isoformat(),
    }

    session = JourneySession(journey)
    active_sessions[journey_id] = session

    return {
        "journey_id":  journey_id,
        "checkpoints": session.checkpoints,
        "message":     f"Journey started. Monitoring {req.user_name}'s route.",
    }


@router.post("/ping")
def gps_ping(req: PingRequest):
    """
    Receive a live GPS update from the user's phone (every 30 sec).

    Example:
        POST /api/journey/ping
        {"journey_id": "JRN-ABC12345", "lat": 17.390, "lng": 78.481}
    """
    session = active_sessions.get(req.journey_id)
    if not session:
        raise HTTPException(status_code=404, detail="Journey not found or already ended.")

    result = session.process_ping(req.lat, req.lng, req.speed_mps)

    if session.completed:
        active_sessions.pop(req.journey_id, None)

    return result


@router.get("/status")
def journey_status(journey_id: str):
    """
    Get the current status of an active journey.

    Example:
        GET /api/journey/status?journey_id=JRN-ABC12345
    """
    session = active_sessions.get(journey_id)
    if not session:
        raise HTTPException(status_code=404, detail="Journey not found.")

    completed_cps = sum(1 for cp in session.checkpoints if cp["reached"])
    total_cps     = len(session.checkpoints)

    # FIX 2: guard against division by zero when journey has no checkpoints
    progress_pct = round(completed_cps / total_cps * 100) if total_cps > 0 else 0

    return {
        "journey_id":          journey_id,
        "user_name":           session.journey["user_name"],
        "completed":           session.completed,
        "alert_fired":         session.alert_fired,
        "checkpoints_reached": completed_cps,
        "checkpoints_total":   total_cps,
        "progress_pct":        progress_pct,
        "gps_pings_received":  len(session.gps_history),
        "last_ping":           session.gps_history[-1] if session.gps_history else None,
    }


@router.post("/end")
def end_journey(req: EndJourneyRequest):
    """
    Mark a journey as safely completed. Clears the session.

    Example:
        POST /api/journey/end
        {"journey_id": "JRN-ABC12345"}
    """
    session = active_sessions.pop(req.journey_id, None)
    if not session:
        raise HTTPException(status_code=404, detail="Journey not found or already ended.")

    return {
        "journey_id": req.journey_id,
        "message":    f"Journey ended safely. {len(session.gps_history)} pings recorded.",
        "summary": {
            "user_name":      session.journey["user_name"],
            "alert_fired":    session.alert_fired,
            "pings_received": len(session.gps_history),
        },
    }


# FIX 1: accepts JSON body (PcrAlertRequest) instead of query params
@router.post("/alerts/pcr")
def pcr_alert(req: PcrAlertRequest):
    """
    Internal endpoint — receives PCR van alert from the guardian engine.
    In production this would interface with police dispatch API.
    """
    print(f"🚨 PCR ALERT: {req.user_name} at ({req.lat},{req.lng}) — Risk: {req.risk_score}/100")
    return {
        "status":     "pcr_alerted",
        "lat":        req.lat,
        "lng":        req.lng,
        "user_name":  req.user_name,
        "risk_score": req.risk_score,
        "timestamp":  req.timestamp or datetime.now(timezone.utc).isoformat(),
    }
