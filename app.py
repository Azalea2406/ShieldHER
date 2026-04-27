"""
saferoute/app.py
-----------------
FastAPI service exposing GET /api/route/safe

Builds a risk-weighted road graph for Hyderabad using OSMnx,
then runs Dijkstra to find the safest path between two coordinates.

Risk weight formula (per edge):
    risk_weight = length * (1 + darkness_penalty + isolation_penalty)

Run:
    uvicorn app:app --reload --port 8000
"""

import os
import math
import logging
from functools import lru_cache
from typing import Optional

import networkx as nx
import osmnx as ox
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="ShieldHer SafeRoute API",
    description="Returns the safest walking/driving route in Hyderabad using risk-weighted Dijkstra.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Hyderabad bounding box (extend as needed) ────────────────────────────────
CITY = "Hyderabad, Telangana, India"
GRAPH_CACHE_PATH = "hyderabad_walk.graphml"


# ── Graph loading (cached on disk) ──────────────────────────────────────────

@lru_cache(maxsize=1)
def get_graph() -> nx.MultiDiGraph:
    if os.path.exists(GRAPH_CACHE_PATH):
        logger.info("Loading cached graph from %s", GRAPH_CACHE_PATH)
        G = ox.load_graphml(GRAPH_CACHE_PATH)
    else:
        logger.info("Downloading OSMnx graph for %s — this takes ~1 min on first run …", CITY)
        G = ox.graph_from_place(CITY, network_type="walk")
        ox.save_graphml(G, GRAPH_CACHE_PATH)
        logger.info("Graph saved to %s", GRAPH_CACHE_PATH)

    G = add_risk_weights(G)
    return G


# ── Risk-weight computation ──────────────────────────────────────────────────

# Known unsafe zones in Hyderabad (lat, lng, radius_m, penalty_multiplier)
UNSAFE_ZONES: list[tuple[float, float, float, float]] = [
    (17.3616, 78.4747, 500, 1.8),   # Secunderabad station area (night)
    (17.3850, 78.4867, 300, 1.5),   # Example dense market
    (17.4239, 78.4738, 400, 1.6),   # Example isolated stretch
]


def haversine(lat1, lng1, lat2, lng2) -> float:
    """Return distance in metres between two lat/lng points."""
    R = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def compute_risk_penalty(lat: float, lng: float) -> float:
    """Return an additive risk penalty [0, 2] based on proximity to unsafe zones."""
    penalty = 0.0
    for z_lat, z_lng, radius, mult in UNSAFE_ZONES:
        dist = haversine(lat, lng, z_lat, z_lng)
        if dist <= radius:
            # Penalty scales linearly with proximity
            penalty += mult * (1 - dist / radius)
    return min(penalty, 2.0)   # cap at 2×


def add_risk_weights(G: nx.MultiDiGraph) -> nx.MultiDiGraph:
    """Attach a `risk_weight` attribute to every edge in G."""
    logger.info("Computing risk weights for %d edges …", G.number_of_edges())
    for u, v, key, data in G.edges(keys=True, data=True):
        length = data.get("length", 1)
        # Use midpoint of the edge for zone lookup
        u_data = G.nodes[u]
        v_data = G.nodes[v]
        mid_lat = (u_data["y"] + v_data["y"]) / 2
        mid_lng = (u_data["x"] + v_data["x"]) / 2
        penalty = compute_risk_penalty(mid_lat, mid_lng)
        G[u][v][key]["risk_weight"] = length * (1 + penalty)
    return G


# ── Route computation ────────────────────────────────────────────────────────

def find_safe_route(
    G: nx.MultiDiGraph,
    orig_lat: float, orig_lng: float,
    dest_lat: float, dest_lng: float,
) -> dict:
    orig_node = ox.distance.nearest_nodes(G, orig_lng, orig_lat)
    dest_node = ox.distance.nearest_nodes(G, dest_lng, dest_lat)

    try:
        path_nodes = nx.dijkstra_path(G, orig_node, dest_node, weight="risk_weight")
    except nx.NetworkXNoPath:
        raise HTTPException(status_code=404, detail="No path found between the given coordinates.")

    # Build GeoJSON-style coordinate list
    coords = [
        {"lat": G.nodes[n]["y"], "lng": G.nodes[n]["x"]}
        for n in path_nodes
    ]

    # Total distance and risk
    total_length = 0.0
    total_risk = 0.0
    for a, b in zip(path_nodes[:-1], path_nodes[1:]):
        edge_data = min(G[a][b].values(), key=lambda d: d.get("risk_weight", float("inf")))
        total_length += edge_data.get("length", 0)
        total_risk += edge_data.get("risk_weight", 0)

    return {
        "origin": {"lat": orig_lat, "lng": orig_lng},
        "destination": {"lat": dest_lat, "lng": dest_lng},
        "waypoints": coords,
        "total_distance_m": round(total_length, 1),
        "total_risk_score": round(total_risk, 1),
        "node_count": len(path_nodes),
    }


# ── Endpoints ────────────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup_event():
    logger.info("Pre-loading OSMnx graph …")
    get_graph()   # warm up cache


@app.get("/api/route/safe")
def safe_route(
    from_lat: float = Query(..., description="Origin latitude"),
    from_lng: float = Query(..., description="Origin longitude"),
    to_lat: float = Query(..., description="Destination latitude"),
    to_lng: float = Query(..., description="Destination longitude"),
):
    """
    Returns the safest walking route between two coordinates in Hyderabad.

    Example:
        GET /api/route/safe?from_lat=17.385&from_lng=78.4867&to_lat=17.360&to_lng=78.474
    """
    G = get_graph()
    return find_safe_route(G, from_lat, from_lng, to_lat, to_lng)


@app.get("/health")
def health():
    return {"status": "ok", "service": "saferoute"}
