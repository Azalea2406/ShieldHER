# 🛡️ ShieldHer — AI-Powered Women's Safety Platform

> **Zero SOS button needed.** ShieldHer monitors a woman's journey in real time, predicts dangerous zones using live sensor + community data, and automatically alerts contacts or police — before she even knows she's in danger.

---

## Team

| Member | Layer | Module |
|--------|-------|--------|
| Aditi | Layer 1 + 5 | SafeBeacon (ESP32 hardware) + SafeRoute navigation |
| Srinidhi | Layer 2 | Dynamic Risk Scoring Engine |
| Ishrath | Layer 3 | Journey Guardian (core detection engine) |
| Tulja | Layer 4 | HerMap community reporting |

---

## How It Works — One Flow

```
ESP32 Beacon         Risk Engine          Journey Guardian
(PIR + LDR +    →   (zone score      →   (Isolation Forest    →   🚨 Auto Alert
 density data)       0–100, 15 min)       detects deviation)       SMS + PCR van

                         ↑
                    HerMap reports
                 (community incident pins)
                         +
                    SafeRoute
                 (risk-weighted Dijkstra)
```

---

## Project Structure

```
ShieldHer/                          ← ROOT
│
├── shieldher_demo.html             ← 🎬 Visual browser demo (no setup needed)
├── demo_runner.py                  ← 🎬 Terminal demo (one command)
├── README.md
│
├── journey_guardian.py             ← Layer 3: core detection engine
├── api.py                          ← Layer 3: FastAPI routes (port 8001)
├── risk_engine.py                  ← Layer 2: risk scoring + /api/risk/zone
├── app.py                          ← Layer 5: SafeRoute API (port 8000)
├── server.py                       ← Layer 5: Buddy Mode WebSocket (port 8765)
├── simulator.py                    ← Layer 1: ESP32 beacon simulator
├── download_graph.py               ← One-time OSMnx graph download
├── main.py                         ← Layer 1: MicroPython firmware (ESP32 only)
├── requirements.txt
│
└── hermap_demo/
│     └── src/
│        ├── App.jsx
│        ├── App.css
│        ├── main.jsx
│        └── index.css
│
└── hermap/                         ← Layer 4: HerMap community module
    ├── hermap_server.py            ← FastAPI backend (port 8000)
    ├── test_hermap.py              ← Demo test script
    ├── requirements.txt
    ├── README.md
    │
    ├── react/                      ← Web dashboard
    │    ├── HermapDashboard.jsx ← Live risk heatmap dashboard
    │
    └── flutter/                    ← Mobile app
    │    ├── hermap_heatmap_screen.dart   ← Google Maps heatmap screen
    │    ├── hermap_report_screen.dart    ← Incident report submission
    │    └── pubspec_additions.yaml       ← Flutter dependencies
   

```

---

## The 5 Layers

### Layer 1 — SafeBeacon (Hardware)
ESP32 microcontroller with PIR motion, LDR light, and crowd density sensors. Posts a JSON reading to the backend every 60 seconds. A Python simulator (`simulator.py`) replicates identical output for development without physical hardware.

### Layer 2 — Dynamic Risk Scoring Engine
Every ~100m city zone gets a risk score from 0–100, refreshed every 15 minutes. Factors in time of day, NCRB crime data, beacon signals, community reports, and isolation. Built with Random Forest — no GPU needed.

| Score | Level | Color |
|-------|-------|-------|
| 0–39 | Safe | 🟢 |
| 40–69 | Caution | 🟡 |
| 70–100 | Danger | 🔴 |

### Layer 3 — Journey Guardian *(the glue)*
The only module that actively watches a real person in real time. Generates checkpoints along a route, runs Isolation Forest anomaly detection on live GPS pings, queries the risk score, and fires tiered alerts automatically.

**Escalation logic:**
- Score < 40 → passive log only
- Score 40–70 → Twilio SMS to emergency contact
- Score > 70 → SMS + POST to `/api/alerts/pcr` → nearest PCR van auto-alerted with live location

### Layer 4 — HerMap Community
Women anonymously pin incidents (harassment, bad lighting) to exact locations. No identity stored. Reports decay over time to stay fresh. Authorities are auto-alerted when a zone crosses the danger threshold.

### Layer 5 — SafeRoute Navigation
Downloads Hyderabad's road graph via OSMnx. Runs Dijkstra with risk-weighted edges to find the **safest** path, not the shortest. Buddy Mode lets a trusted contact watch live GPS over WebSocket.

---

## 🎬 Running the Demo

### Option A — Browser Demo *(recommended for judges)*

**No installation required.**

1. Download `shieldher_demo.html`
2. Double-click to open in any browser (Chrome recommended)
3. The demo auto-plays — all 5 layers animate in sequence

What you'll see:
- Layer 1: Beacon readings (motion, lux, density) appear live
- Layer 2: Risk scores compute for each Hyderabad zone with animated bars
- Layer 3: Priya's GPS pings stream in → deviation detected → SMS alert fires
- Layer 4: Community reports accumulate → zone crosses threshold → authority alerted
- Layer 5: Safe vs shortest route comparison + Buddy Mode WebSocket log

Click **"Run Again"** to replay at any time.

---

### Option B — Terminal Demo

**Requirements:** Python 3.10+

**Step 1 — Install dependencies**
```bash
pip install numpy scikit-learn requests
```

**Step 2 — Run the demo**
```bash
python demo_runner.py
```

That's it. No server, no database, no Twilio credits needed. All 5 layers run with simulated data and coloured terminal output.

**Expected output:**
```
████████████████████████████████████████████████████████████
  🛡️  ShieldHer — AI-Powered Women's Safety Platform
████████████████████████████████████████████████████████████

══════════════════════════════════════════════════════════
  LAYER 1 — SafeBeacon  (ESP32 Hardware Simulator)
══════════════════════════════════════════════════════════
  ...beacon readings...

  LAYER 2 — Dynamic Risk Scoring Engine
  ...zone scores computed...

  LAYER 3 — Journey Guardian
  ...GPS pings → deviation → 🚨 SMS alert fired...

  LAYER 4 — HerMap Community Reporting
  ...reports accumulate → authority alert triggered...

  LAYER 5 — SafeRoute Navigation
  ...safe vs shortest route comparison...
```

---

### Option C — Live API Demo *(full system)*

**Step 1 — Install all dependencies**
```bash
pip install -r requirements.txt
```

**Step 2 — Start the HerMap backend**
```bash
cd hermap
uvicorn hermap_server:app --reload --port 8000
```

**Step 3 — In a new terminal, run the HerMap test**
```bash
cd hermap
python test_hermap.py
```

**Step 4 — Start the Journey Guardian API**
```bash
uvicorn api:app --reload --port 8001
```

**Step 5 — Run the standalone Journey Guardian demo**
```bash
python journey_guardian.py --demo
```

**Step 6 — (Optional) Start the Buddy Mode WebSocket server**
```bash
python server.py
```

**Step 7 — (Optional) Start the beacon simulator**
```bash
python simulator.py --backend http://localhost:8000 --interval 10
```

> **Note:** For the SafeRoute module (`app.py`), run `python download_graph.py` once first to download the Hyderabad road graph (~2 min). Then `uvicorn app:app --reload --port 8000`.

---

## API Reference

### HerMap (port 8000)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/report` | Submit anonymous incident report |
| GET | `/heatmap` | All zones with decay-weighted scores |
| GET | `/zone/{zone_id}` | Detail view of a specific zone |
| GET | `/alerts/check` | Authority alert history + live high-risk zones |

### Journey Guardian (port 8001)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/journey/start` | Register a new journey |
| POST | `/api/journey/ping` | Send live GPS update (every 30s) |
| GET | `/api/journey/status` | Check journey progress |
| POST | `/api/journey/end` | Mark journey safely completed |

### Risk Engine (port 8000)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/risk/zone?lat=&lng=` | Risk score for a coordinate |

### SafeRoute (port 8000)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/route/safe?from_lat=&from_lng=&to_lat=&to_lng=` | Safest route between two points |

---

## Tech Stack

| Component | Technology |
|-----------|------------|
| Hardware | ESP32, MicroPython, PIR/LDR sensors |
| Backend | FastAPI, Python 3.10+ |
| AI/ML | scikit-learn (Isolation Forest, Random Forest) |
| Navigation | OSMnx, NetworkX, Dijkstra |
| Alerts | Twilio SMS |
| Real-time | WebSockets |
| Frontend | React, Chart.js |
| Mobile | Flutter, Google Maps SDK |
| Data | In-memory (demo) → PostgreSQL (production) |

---

## Environment Variables (for live SMS alerts)

Create a `.env` file in the project root:
```
TWILIO_ACCOUNT_SID=your_account_sid
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_FROM_NUMBER=+1xxxxxxxxxx
```

Alerts will print to terminal in demo mode if these are not set — no crashes.

---

## Key Design Decisions

**Why Isolation Forest?** Unsupervised anomaly detection means the model works on day one with no labelled data. It learns what a "normal" journey looks like from synthetic pre-training and flags anything that diverges.

**Why decay-weighted scoring in HerMap?** A harassment report from 3 weeks ago shouldn't carry the same weight as one from 2 hours ago. Exponential decay keeps the community map fresh without manual cleanup.

**Why risk-weighted Dijkstra?** Shortest path is the wrong objective for safety. A 350m detour that avoids a dark isolated street is always worth it.

**Why zero SOS button?** In a real threat, a woman may not have the time, visibility, or ability to press anything. The system detects and responds automatically.
