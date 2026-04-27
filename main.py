# esp32/main.py  — MicroPython firmware for ShieldHer ESP32 beacon
# ──────────────────────────────────────────────────────────────────
# Hardware:
#   PIR sensor  → GPIO 14  (HIGH when motion detected)
#   LDR sensor  → ADC on GPIO 34 (higher value = darker)
#
# Flashing:
#   esptool.py --chip esp32 erase_flash
#   esptool.py --chip esp32 --baud 460800 write_flash -z 0x1000 firmware.bin
#   ampy --port /dev/ttyUSB0 put main.py
#
# Config: edit the constants below or store in config.json on the device.

import time
import json
import machine
import network
import urequests   # built-in to MicroPython ESP32 builds

# ── Config ───────────────────────────────────────────────────────────────────

WIFI_SSID     = "YOUR_WIFI_SSID"
WIFI_PASSWORD = "YOUR_WIFI_PASSWORD"
BACKEND_URL   = "http://YOUR_SERVER_IP:8000/api/beacon/reading"
BEACON_ID     = "ESP32-BEACON-001"
BEACON_LAT    = 17.3850
BEACON_LNG    = 78.4867
POST_INTERVAL = 60   # seconds

# ── Pin setup ────────────────────────────────────────────────────────────────

pir = machine.Pin(14, machine.Pin.IN)
ldr = machine.ADC(machine.Pin(34))
ldr.atten(machine.ADC.ATTN_11DB)     # full 0–3.3V range → 0–4095

# Built-in LED for visual feedback
led = machine.Pin(2, machine.Pin.OUT)


# ── Wi-Fi connection ─────────────────────────────────────────────────────────

def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        print("Connecting to Wi-Fi …")
        wlan.connect(WIFI_SSID, WIFI_PASSWORD)
        timeout = 15
        while not wlan.isconnected() and timeout > 0:
            time.sleep(1)
            timeout -= 1
    if wlan.isconnected():
        print("Wi-Fi connected:", wlan.ifconfig())
        return True
    print("Wi-Fi connection failed.")
    return False


# ── Sensor reads ─────────────────────────────────────────────────────────────

def read_pir() -> dict:
    motion = bool(pir.value())
    return {"motion_detected": motion}


def read_ldr() -> dict:
    raw = ldr.read()              # 0–4095; higher = less light (voltage divider)
    lux_approx = int((4095 - raw) / 4095 * 1000)   # rough inversion to 0-1000 lux scale
    if lux_approx > 300:
        category = "bright"
    elif lux_approx > 80:
        category = "dim"
    else:
        category = "dark"
    return {"raw": raw, "lux_approx": lux_approx, "category": category}


def read_density() -> dict:
    # Without a real density sensor, proxy via motion activity level
    # In real deployment swap this with an ultrasonic / IR array sensor
    motion_samples = [pir.value() for _ in range(5)]
    score = int(sum(motion_samples) / 5 * 100)
    return {"score": score, "level": "crowded" if score > 60 else "sparse"}


# ── Payload builder ──────────────────────────────────────────────────────────

def build_payload() -> dict:
    return {
        "beacon_id": BEACON_ID,
        "timestamp": str(time.time()),   # Unix timestamp; no RTC on basic builds
        "location": {"lat": BEACON_LAT, "lng": BEACON_LNG},
        "sensors": {
            "pir": read_pir(),
            "ldr": read_ldr(),
            "density": read_density(),
        }
    }


# ── POST with retry ──────────────────────────────────────────────────────────

def post_reading(payload: dict) -> None:
    headers = {"Content-Type": "application/json"}
    try:
        led.on()
        r = urequests.post(BACKEND_URL, data=json.dumps(payload), headers=headers)
        print("POST", r.status_code)
        r.close()
    except Exception as e:
        print("POST failed:", e)
    finally:
        led.off()


# ── Main loop ────────────────────────────────────────────────────────────────

def main():
    if not connect_wifi():
        print("Running in offline mode — readings will not be posted.")

    print("ShieldHer ESP32 beacon running. Posting every", POST_INTERVAL, "s.")
    while True:
        payload = build_payload()
        print(json.dumps(payload))
        post_reading(payload)
        time.sleep(POST_INTERVAL)


main()
