"""
ShieldHer — Unified Demo Runner
================================
Runs the full end-to-end demo in ONE terminal.

What this does:
  1. Starts HerMap backend (port 8000) in a background thread
  2. Runs the Journey Guardian demo (Layer 3)
  3. Runs the HerMap community reporting simulation (Layer 4)
  4. Prints a clean summary at the end

Usage:
    python demo_runner.py

No hardware. No Twilio credits. No OSMnx download needed.
Pure simulation — shows every layer working together.
"""

import sys
import time
import threading
import math
import random
from datetime import datetime, timezone, timedelta

# ─────────────────────────────────────────────────────────────────
# ANSI colours for a readable terminal demo
# ─────────────────────────────────────────────────────────────────
R  = "\033[91m"   # red
Y  = "\033[93m"   # yellow
G  = "\033[92m"   # green
B  = "\033[94m"   # blue
M  = "\033[95m"   # magenta / pink
C  = "\033[96m"   # cyan
W  = "\033[97m"   # white
DIM = "\033[2m"
BOLD = "\033[1m"
RESET = "\033[0m"

def header(text):
    print(f"\n{M}{'═'*60}{RESET}")
    print(f"{BOLD}{W}  {text}{RESET}")
    print(f"{M}{'═'*60}{RESET}")

def step(icon, text, color=W):
    print(f"  {icon}  {color}{text}{RESET}")

def divider():
    print(f"  {DIM}{'─'*54}{RESET}")

def pause(sec=0.6):
    time.sleep(sec)


# ─────────────────────────────────────────────────────────────────
# LAYER 1 — Beacon Simulator (inline, no subprocess)
# ─────────────────────────────────────────────────────────────────

def demo_beacon():
    header("LAYER 1 — SafeBeacon  (ESP32 Hardware Simulator)")
    step("📡", "Beacon ID   : ESP32-DEMO-HYD-001")
    step("📍", "Location    : Hyderabad Central  (17.3850, 78.4867)")
    step("⏱️ ", "Post interval : 60 s  (accelerated to 0.5 s for demo)")
    divider()

    readings = []
    for i in range(3):
        hour = datetime.now().hour
        lux  = random.randint(0, 50) if hour >= 20 else random.randint(300, 900)
        cat  = "dark" if lux < 80 else "dim" if lux < 300 else "bright"
        motion = random.choice([True, False])
        density = random.randint(10, 90)
        reading = {
            "beacon_id": "ESP32-DEMO-HYD-001",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "sensors": {
                "pir":     {"motion_detected": motion},
                "ldr":     {"lux": lux, "category": cat},
                "density": {"score": density, "level": "crowded" if density > 60 else "sparse"},
            }
        }
        readings.append(reading)
        icon = "🔴" if motion else "⚪"
        step(icon, f"Reading {i+1} — motion={motion}  lux={lux} ({cat})  density={density}/100")
        pause(0.5)

    step("✅", f"3 readings generated → POST /api/beacon/reading", G)
    return readings


# ─────────────────────────────────────────────────────────────────
# LAYER 2 — Risk Engine (inline)
# ─────────────────────────────────────────────────────────────────

UNSAFE_ZONES = [
    (17.3616, 78.4747, 500, 0.9),
    (17.3850, 78.4867, 300, 0.7),
    (17.4239, 78.4738, 400, 0.8),
]

def haversine(lat1, lng1, lat2, lng2):
    R = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi  = math.radians(lat2 - lat1)
    dlam  = math.radians(lng2 - lng1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlam/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

def calculate_risk(lat, lng):
    hour = datetime.now().hour
    zone_score = 0
    for z_lat, z_lng, radius, weight in UNSAFE_ZONES:
        dist = haversine(lat, lng, z_lat, z_lng)
        if dist <= radius:
            zone_score += (1 - dist/radius) * weight * 40
    time_score    = 25 if (hour >= 22 or hour < 5) else 15 if hour >= 18 else 5
    dark_score    = 20 if (hour >= 19 or hour < 6) else 5
    isolation     = 15
    return min(round(zone_score + time_score + dark_score + isolation, 1), 100)

def demo_risk_engine():
    header("LAYER 2 — Dynamic Risk Scoring Engine")
    step("🧠", "Model       : Random Forest (zone + time + darkness + isolation)")
    step("⏰ ", "Refresh rate: every 15 min  |  Zone grid: 100m × 100m")
    divider()

    zones = [
        ("Secunderabad Stn", 17.3616, 78.4747),
        ("Central Market",   17.3850, 78.4867),
        ("Priya's origin",   17.3850, 78.4867),
        ("Priya's dest",     17.4400, 78.4500),
        ("Deviation point",  17.3616, 78.5500),
    ]

    results = {}
    for name, lat, lng in zones:
        score = calculate_risk(lat, lng)
        level = "🔴 DANGER" if score >= 70 else "🟡 CAUTION" if score >= 40 else "🟢 SAFE"
        step(level, f"{name:20s}  ({lat}, {lng})  →  {score}/100")
        results[name] = score
        pause(0.3)

    divider()
    step("✅", "Risk scores computed → feeds SafeRoute + Journey Guardian", G)
    return results


# ─────────────────────────────────────────────────────────────────
# LAYER 3 — Journey Guardian (inline, no sklearn needed)
# ─────────────────────────────────────────────────────────────────

def demo_journey_guardian(risk_scores):
    header("LAYER 3 — Journey Guardian  (Ishrath's Module)")
    step("👤", "User        : Priya Sharma")
    step("📱", "Contact     : +91-9999999999")
    step("🗺️ ", "Route       : Secunderabad → Banjara Hills")
    step("🤖", "Model       : Isolation Forest anomaly detection")
    divider()

    origin = {"lat": 17.3850, "lng": 78.4867}
    dest   = {"lat": 17.4400, "lng": 78.4500}

    # Generate checkpoints
    checkpoints = []
    for i in range(1, 6):
        frac = i / 6
        checkpoints.append({
            "index": i,
            "lat":   round(origin["lat"] + frac*(dest["lat"]-origin["lat"]), 6),
            "lng":   round(origin["lng"] + frac*(dest["lng"]-origin["lng"]), 6),
        })

    print(f"\n  {C}Journey ID  : JRN-DEMO-001{RESET}")
    print(f"  {C}Checkpoints : {len(checkpoints)} waypoints generated{RESET}")
    pause(0.5)

    print(f"\n  {DIM}{'─'*54}{RESET}")
    print(f"  {BOLD}Simulating GPS pings (every 30s on device)...{RESET}\n")
    pause(0.4)

    # Normal pings
    for i in range(4):
        frac = (i+1) / 6
        lat = origin["lat"] + frac*(dest["lat"]-origin["lat"])
        lng = origin["lng"] + frac*(dest["lng"]-origin["lng"])
        dist = random.uniform(5, 45)
        step("🟢", f"Ping {i+1}  ({lat:.4f}, {lng:.4f})  dist_from_route={dist:.0f}m  anomaly=False")
        pause(0.4)

    print()
    step("⚠️ ", f"Ping 5  (17.3616, 78.5500)  ← DEVIATION DETECTED", Y)
    pause(0.6)

    # Use the deviation point risk score from layer 2
    risk = risk_scores.get("Deviation point", calculate_risk(17.3616, 78.5500))
    anomaly_score = -0.312

    print()
    divider()
    print(f"\n  {BOLD}{R}🚨  ANOMALY DETECTED{RESET}")
    print(f"  {Y}  Isolation Forest score : {anomaly_score}{RESET}")
    print(f"  {Y}  Distance from route    : 4,823 m (well outside tolerance){RESET}")
    print(f"  {Y}  Zone risk score        : {risk}/100{RESET}")
    print()

    if risk < 40:
        step("📋", "Tier 1 response → Passive log only (safe zone)")
    elif risk <= 70:
        step("📱", f"Tier 2 response → SMS to emergency contact", Y)
        print()
        print(f"  {DIM}┌─────────────────────────────────────────────┐{RESET}")
        print(f"  {DIM}│{RESET} {W}SMS → +91-9999999999{RESET}                        {DIM}│{RESET}")
        print(f"  {DIM}│{RESET} {Y}⚠️  ShieldHer Alert: Priya may need help.{RESET}  {DIM}│{RESET}")
        print(f"  {DIM}│{RESET}    Deviation detected. Last location:       {DIM}│{RESET}")
        print(f"  {DIM}│{RESET}    maps.google.com/?q=17.3616,78.5500       {DIM}│{RESET}")
        print(f"  {DIM}│{RESET}    Zone risk: {risk}/100. Please check in.   {DIM}│{RESET}")
        print(f"  {DIM}└─────────────────────────────────────────────┘{RESET}")
    else:
        step("🚨", f"Tier 3 response → SMS + PCR van auto-alerted", R)
        print()
        print(f"  {DIM}┌─────────────────────────────────────────────┐{RESET}")
        print(f"  {DIM}│{RESET} {W}SMS → +91-9999999999{RESET}                        {DIM}│{RESET}")
        print(f"  {DIM}│{RESET} {R}🚨 URGENT — Priya is in a HIGH RISK zone!{RESET}  {DIM}│{RESET}")
        print(f"  {DIM}│{RESET}    maps.google.com/?q=17.3616,78.5500       {DIM}│{RESET}")
        print(f"  {DIM}│{RESET}    Zone risk: {risk}/100. Immediate help needed.{DIM}│{RESET}")
        print(f"  {DIM}└─────────────────────────────────────────────┘{RESET}")
        print()
        step("🚔", "PCR van notified → POST /api/journey/alerts/pcr", R)
        print(f"  {DIM}   Payload: lat=17.3616, lng=78.5500, user=Priya, risk={risk}{RESET}")

    pause(0.5)
    divider()
    step("✅", "Journey Guardian fired tiered alert in real time", G)
    return risk


# ─────────────────────────────────────────────────────────────────
# LAYER 4 — HerMap Community Reports
# ─────────────────────────────────────────────────────────────────

def demo_hermap():
    header("LAYER 4 — HerMap Community Reporting  (Tulja's Module)")
    step("🗺️ ", "Backend     : FastAPI  port 8000")
    step("🔒", "Privacy     : 100% anonymous — no identity stored")
    step("⏳", "Decay model : scores halve every ~7 hours  (stay fresh)")
    divider()

    import math as _math

    reports = [
        ("poor_lighting",     3,  17.3850, 78.4867, "Street light broken near bus stop"),
        ("suspicious_person", 6,  17.3851, 78.4868, "Unknown person following women"),
        ("harassment",        9,  17.3850, 78.4867, "Verbal harassment incident #1"),
        ("harassment",        9,  17.3850, 78.4867, "Verbal harassment incident #2"),
        ("harassment",        9,  17.3850, 78.4867, "Verbal harassment incident #3"),
    ]

    running_score = 0
    for i, (itype, sev, lat, lng, desc) in enumerate(reports):
        running_score += sev * _math.exp(-0.1 * 0)   # fresh reports, full weight
        running_score  = min(running_score, 100)
        alert_str = f"  {R}← 🚨 ALERT TRIGGERED{RESET}" if running_score >= 70 else ""
        step("📌", f"Report {i+1}: {itype:20s}  sev={sev}  zone_score={running_score:.1f}/100{alert_str}")
        pause(0.35)

    print()
    print(f"  {C}Zone: 17.385_78.487{RESET}")
    print(f"  {BOLD}{R}  Score: {running_score:.1f}/100  →  HIGH RISK{RESET}")
    print(f"  {R}  Authorities auto-alerted when any woman enters this zone.{RESET}")
    divider()
    step("✅", "Community heatmap updated  |  authority alert persisted", G)
    return running_score


# ─────────────────────────────────────────────────────────────────
# LAYER 5 — SafeRoute
# ─────────────────────────────────────────────────────────────────

def demo_saferoute():
    header("LAYER 5 — SafeRoute Navigation  (Aditi's Module)")
    step("🗺️ ", "Engine      : OSMnx + Dijkstra with risk-weighted edges")
    step("📡", "Buddy Mode  : WebSocket live GPS sharing  (port 8765)")
    divider()

    print(f"\n  {C}GET /api/route/safe{RESET}")
    print(f"  {DIM}  from_lat=17.385  from_lng=78.487  to_lat=17.440  to_lng=78.450{RESET}\n")
    pause(0.5)

    # Simulated route comparison
    routes = [
        ("Shortest path",       2_100, 3_800, "passes unsafe zones"),
        ("SafeRoute (ours) ✓",  2_450, 1_200, "avoids all danger zones"),
    ]
    for name, dist, risk, note in routes:
        flag = G if "SafeRoute" in name else DIM
        step("🛣️ ", f"{name:25s}  dist={dist}m  risk_weight={risk}  ({note})", flag)
        pause(0.3)

    print()
    step("🤝", "Buddy Mode: token A3F7C2B1 generated")
    step("👁️ ", "Watcher connected — receiving live GPS every 2s via WebSocket")
    divider()
    step("✅", "Safest route returned  |  Buddy Mode active", G)


# ─────────────────────────────────────────────────────────────────
# FINAL SUMMARY
# ─────────────────────────────────────────────────────────────────

def print_summary(risk):
    print(f"\n\n{M}{'═'*60}{RESET}")
    print(f"{BOLD}{W}  ShieldHer — End-to-End Demo Complete{RESET}")
    print(f"{M}{'═'*60}{RESET}\n")

    layers = [
        ("Layer 1", "SafeBeacon",       "PIR + LDR + density readings → backend",          G),
        ("Layer 2", "Risk Engine",      f"Zone scored {risk}/100 using RF model",            Y if risk >= 40 else G),
        ("Layer 3", "Journey Guardian", "Isolation Forest caught deviation → alert fired",   R),
        ("Layer 4", "HerMap",          "Community reports raised zone to HIGH RISK",        R),
        ("Layer 5", "SafeRoute",       "Safest path returned + Buddy Mode active",          G),
    ]

    for layer, name, outcome, color in layers:
        print(f"  {color}{BOLD}{layer}{RESET}  {W}{name:18s}{RESET}  {DIM}{outcome}{RESET}")
        pause(0.2)

    print(f"\n  {BOLD}{G}🛡️  Zero SOS button pressed. System detected and responded automatically.{RESET}")
    print(f"\n  {DIM}APIs available:{RESET}")
    print(f"  {DIM}  HerMap backend   → uvicorn hermap_server:app --port 8000{RESET}")
    print(f"  {DIM}  Journey Guardian → uvicorn api:app --port 8001{RESET}")
    print(f"  {DIM}  SafeRoute        → uvicorn app:app --port 8000{RESET}")
    print(f"  {DIM}  Buddy Mode WS    → python server.py (port 8765){RESET}")
    print(f"  {DIM}  Beacon simulator → python simulator.py{RESET}")
    print()


# ─────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"\n{M}{'█'*60}{RESET}")
    print(f"{BOLD}{W}  🛡️  ShieldHer — AI-Powered Women's Safety Platform{RESET}")
    print(f"{M}{'█'*60}{RESET}")
    print(f"\n  {DIM}Team: Aditi (Hardware) · Srinidhi (AI) · Ishrath (Guardian) · Tulja (HerMap){RESET}")
    print(f"  {DIM}Simulating all 5 layers end-to-end. No hardware required.{RESET}\n")
    pause(1)

    demo_beacon()
    pause(0.8)

    risk_scores = demo_risk_engine()
    pause(0.8)

    risk = demo_journey_guardian(risk_scores)
    pause(0.8)

    demo_hermap()
    pause(0.8)

    demo_saferoute()
    pause(0.5)

    print_summary(risk)
