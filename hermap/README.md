# HerMap — Complete Build Guide
## ShieldHer Hackathon | Tulja's Module

---

## What You're Building

HerMap is the **community intelligence layer** of ShieldHer. It collects anonymous incident
reports from users, applies a decay-weighted scoring model, renders a live heatmap, and
auto-triggers authority alerts when a zone crosses the risk threshold.

---

## Folder Structure

```
shieldher/
└── hermap/
    ├── main.py            ← FastAPI backend (all logic lives here)
    ├── requirements.txt   ← Python dependencies
    ├── test_hermap.py     ← Demo/test script
    └── README.md          ← This file
```

---

## Component 1 — FastAPI Backend

### Setup (run once in WSL terminal)

```bash
cd ~/shieldher/hermap
pip install -r requirements.txt
uvicorn main:app --reload
```

API will be live at: http://localhost:8000
Auto-docs (Swagger UI): http://localhost:8000/docs   ← show judges this!

### Endpoints

| Method | Route | Purpose |
|--------|-------|---------|
| GET | / | Health check |
| POST | /report | Submit anonymous incident |
| GET | /heatmap | All zones + scores (for map rendering) |
| GET | /zone/{zone_id} | Single zone detail |
| GET | /alerts/check | Scan all zones for high-risk |

### POST /report — Request Body

```json
{
  "latitude": 17.3850,
  "longitude": 78.4867,
  "incident_type": "harassment",
  "description": "Optional text",
  "severity": 8
}
```

Incident types you should support:
- `harassment`
- `poor_lighting`
- `suspicious_person`
- `unsafe_area`
- `crowding`
- `other`

---

## Component 2 — Decay-Weighted Scoring

### The Formula

```
decay_weight = e^(-0.1 * hours_since_report)
zone_score = Σ(severity × decay_weight) → normalized to 0–100
```

### What this means

| Hours since report | Decay weight | Effect |
|-------------------|-------------|--------|
| 0 hours (fresh) | 1.00 | Full weight |
| 7 hours | ~0.50 | Half weight |
| 14 hours | ~0.25 | Quarter weight |
| 24 hours | ~0.09 | Nearly gone |

**Why this matters for your demo:** Simulate time-shifting 2pm → 10pm.
Old afternoon reports decay; new evening reports dominate. Score changes visibly.

### Changing sensitivity

In `main.py`, adjust these constants:

```python
DECAY_FACTOR = 0.1    # Higher = faster decay (reports expire sooner)
ALERT_THRESHOLD = 70  # Score above this triggers authority alert
```

---

## Component 3 — Heatmap Data (GET /heatmap)

This endpoint returns JSON that your Flutter app or React dashboard maps to colored circles:

```json
{
  "zones": [
    {
      "zone_id": "17.385_78.487",
      "latitude": 17.385,
      "longitude": 78.487,
      "score": 83.4,
      "report_count": 7,
      "risk_level": "high_risk"
    }
  ]
}
```

### Risk level color mapping (for frontend)

| Score | risk_level | Color to show |
|-------|-----------|---------------|
| 0–39 | safe | 🟢 Green |
| 40–69 | caution | 🟡 Yellow |
| 70–100 | high_risk | 🔴 Red |

### Connecting to Flutter (your teammate's app)

Tell Aditi / your Flutter developer to hit:
```
GET http://<your-ip>:8000/heatmap
```
Then plot each zone as a colored circle on Google Maps using `score` for radius/color.

---

## Component 4 — Authority Alert Trigger

Currently the alert prints to console (good for demo). For production:

### Option A: Twilio SMS (easiest)
```bash
pip install twilio
```
```python
from twilio.rest import Client
client = Client(ACCOUNT_SID, AUTH_TOKEN)
client.messages.create(
    body=f"🚨 ShieldHer Alert: High risk zone {zone_id}, score {score}",
    from_="+1XXXXXXXXXX",
    to="+91XXXXXXXXXX"
)
```

### Option B: FCM Push Notification (city dashboard)
Send to React dashboard via Firebase Cloud Messaging.

### Option C: Demo-friendly (just log it)
Already implemented — console prints `🚨 ALERT: Zone ... score = ...`
This is enough for the hackathon demo.

---

## Running the Live Demo (for judges)

### Step 1: Start the API
```bash
cd ~/shieldher/hermap
uvicorn main:app --reload
```

### Step 2: Run the demo script (in a second terminal)
```bash
python test_hermap.py
```

### What judges will see
1. Reports submitted → zone score increases in real time
2. Score crosses 70 → alert fires automatically
3. Heatmap endpoint shows all active zones with risk levels
4. No SOS button pressed — the system reacted on its own

### Bonus: Show Swagger UI
Open http://localhost:8000/docs in browser — judges can submit reports themselves live!

---

## Connecting HerMap to Srinidhi's Risk Engine

Your zone scores feed into the master risk score. Tell Srinidhi:

```
GET http://localhost:8000/heatmap
```

Response gives `zone_id` + `score` per zone. The risk engine combines this with
NCRB data, weather, time-of-day, and beacon signals.

The weight for community reports in the master formula:
```
master_score = 0.3×community_score + 0.25×crime_data + 0.2×time + 0.15×beacons + 0.1×weather
```
(Adjust weights with Srinidhi based on your team's formula.)

---

## Things to Wire Up Later (Post-MVP)

- [ ] Replace in-memory list with PostgreSQL (1 table: `reports`)
- [ ] Add rate limiting (1 report per user per zone per hour) — prevents spam
- [ ] Add report verification (downvoting false reports)
- [ ] Connect real authority API (PCR van dispatch)
- [ ] Deploy to Railway or Render (both free tier)

---

## Quick Debugging

| Problem | Fix |
|---------|-----|
| `uvicorn not found` | Run `pip install uvicorn` |
| `Address already in use` | Run `uvicorn main:app --reload --port 8001` |
| Flutter can't reach API | Use your WSL IP: `ip addr show eth0` — not localhost |
| Score always 0 | Check zone_id rounding — lat/lng must round to same zone |

---

## WSL-Specific: Find Your IP for Flutter

Flutter on Android emulator can't use `localhost`. Run this in WSL:
```bash
ip addr show eth0 | grep "inet "
```
Use that IP (e.g. `192.168.x.x`) in your Flutter app's base URL.
