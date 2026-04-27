"""
buddy_mode/server.py
---------------------
WebSocket server for ShieldHer Buddy Mode.

Protocol:
  • A user ("sharer") connects and sends their GPS location every few seconds.
  • A trusted contact ("watcher") connects with a share_token and receives
    live location updates in real time.

Message format (sharer → server):
    {
      "type": "share_location",
      "token": "<share_token>",
      "lat": 17.385,
      "lng": 78.486,
      "accuracy": 10.5,        // metres
      "timestamp": "2024-..."
    }

Message format (server → watcher):
    {
      "type": "location_update",
      "lat": 17.385,
      "lng": 78.486,
      "accuracy": 10.5,
      "timestamp": "2024-..."
    }

Run:
    python server.py
    # Starts WS on ws://localhost:8765
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, Set

import websockets
from websockets.server import WebSocketServerProtocol

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
)
logger = logging.getLogger(__name__)

# token → set of watcher WebSocket connections
watchers: Dict[str, Set[WebSocketServerProtocol]] = {}

# token → sharer WebSocket connection
sharers: Dict[str, WebSocketServerProtocol] = {}


# ── Helpers ──────────────────────────────────────────────────────────────────

def make_token() -> str:
    return uuid.uuid4().hex[:8].upper()   # e.g. "A3F7C2B1"


async def broadcast_to_watchers(token: str, message: dict) -> None:
    """Send a location update to all watchers of a given token."""
    if token not in watchers or not watchers[token]:
        return
    payload = json.dumps(message)
    dead = set()
    for ws in watchers[token]:
        try:
            await ws.send(payload)
        except websockets.ConnectionClosed:
            dead.add(ws)
    watchers[token] -= dead


# ── Connection handler ───────────────────────────────────────────────────────

async def handler(websocket: WebSocketServerProtocol, path: str) -> None:
    role = None
    token = None

    try:
        # First message must declare role
        raw = await websocket.recv()
        msg = json.loads(raw)

        if msg.get("type") == "start_share":
            # ── Sharer joining ───────────────────────────────────────────────
            token = make_token()
            role = "sharer"
            sharers[token] = websocket
            watchers.setdefault(token, set())

            await websocket.send(json.dumps({
                "type": "share_started",
                "token": token,
                "message": f"Share this token with your buddy: {token}"
            }))
            logger.info("Sharer connected  token=%s", token)

            async for raw in websocket:
                msg = json.loads(raw)
                if msg.get("type") == "share_location":
                    update = {
                        "type": "location_update",
                        "lat": msg["lat"],
                        "lng": msg["lng"],
                        "accuracy": msg.get("accuracy", None),
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                    await broadcast_to_watchers(token, update)

                elif msg.get("type") == "stop_share":
                    await broadcast_to_watchers(token, {"type": "share_ended"})
                    break

        elif msg.get("type") == "watch":
            # ── Watcher joining ──────────────────────────────────────────────
            token = msg.get("token", "").upper()
            role = "watcher"

            if token not in sharers:
                await websocket.send(json.dumps({
                    "type": "error",
                    "message": "Invalid or expired token."
                }))
                return

            watchers.setdefault(token, set()).add(websocket)
            await websocket.send(json.dumps({
                "type": "watch_started",
                "message": f"Connected. Waiting for location updates from token {token}."
            }))
            logger.info("Watcher connected  token=%s", token)

            # Keep connection alive; location is pushed by sharer handler
            await websocket.wait_closed()

        else:
            await websocket.send(json.dumps({"type": "error", "message": "Unknown message type."}))

    except websockets.ConnectionClosedOK:
        pass
    except websockets.ConnectionClosedError as e:
        logger.warning("Connection closed with error: %s", e)
    except json.JSONDecodeError:
        logger.warning("Received invalid JSON")
    finally:
        # Cleanup
        if role == "sharer" and token:
            sharers.pop(token, None)
            await broadcast_to_watchers(token, {"type": "share_ended", "message": "Sharer disconnected."})
            logger.info("Sharer disconnected  token=%s", token)
        elif role == "watcher" and token:
            if token in watchers:
                watchers[token].discard(websocket)
            logger.info("Watcher disconnected  token=%s", token)


# ── Entry point ──────────────────────────────────────────────────────────────

async def main():
    logger.info("🛡️  ShieldHer Buddy Mode WebSocket server starting on ws://0.0.0.0:8765")
    async with websockets.serve(handler, "0.0.0.0", 8765):
        await asyncio.Future()   # run forever


if __name__ == "__main__":
    asyncio.run(main())
