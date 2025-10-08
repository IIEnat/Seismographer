"""
app.py — Minimal Flask + Socket.IO app (Band-pass live + Playback + /raw)

@file -- app.py
@brief -- Flask + Socket.IO backend for live seismic monitoring and playback 
@details 
- Providing real-time streaming of processed seismic data over WebSockets
- Includes a UI "startup countdown" to account for buffer initialization
- Serves both live and playback routes via Flask
- Exposes a '/raw' JSONN endpoint for latest raw seismic snapshot
"""
from __future__ import annotations

import os, glob
from collections import defaultdict
from datetime import datetime, timezone, timedelta
import time
import math
from typing import Dict, List, Tuple

import numpy as np
from flask import Flask, jsonify, render_template, request
from flask_socketio import SocketIO, emit, disconnect, join_room, leave_room
from obspy import read as obspy_read, Stream, Trace
from werkzeug.utils import secure_filename

import config as CFG
from python.receiver import make_processors, start_processor_thread
from python.playback_routes import create_playback_blueprint

# -------------------------------------------------------------------
# Global setup and app initialization
# -------------------------------------------------------------------

# Global buffering countdown: how long clients must wait before data is ready 
# This equals one processing window (BATCH_SECONDS), adjusted if SPEED_FACTOR > 1
_STARTUP_DELAY = max(0, int(math.ceil(CFG.BATCH_SECONDS / max(1.0, getattr(CFG, "SPEED_FACTOR", 1.0)))))
_STARTUP_END   = time.monotonic() + _STARTUP_DELAY
app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

BASE_DIR   = os.path.dirname(__file__)
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Local timezone (for rendering playback times, not for UTC logs)
AWST = timezone(timedelta(hours=8))  # UTC+8

# Timestamp when app started 
APP_BOOT_TS = time.time()

# Register playback endpoints (for uploaded waveform files)
from python.playback_routes import create_playback_blueprint
app.register_blueprint(create_playback_blueprint(UPLOAD_DIR, AWST))

# Demo station coordinates (use real ones if available / resolved dynamically)
COORDS: Dict[str, Tuple[float, float]] = {
    "WAR27": (-31.35, 115.92),
    "WAR32": (-31.40, 115.96),
    "WAR33": (-31.45, 115.98),
}


# -------------------------------------------------------------------
# Processor setup: live data processing threads
# -------------------------------------------------------------------

_processors = make_processors()
_threads    = [start_processor_thread(p) for p in _processors]

def _sid(p) -> str:
    """
    @brief Generate a SEED-like station indentifier string
    @param p A StationProcessor-like object with fields: net, sta, chan
    @return Identifier of form NET.STA..CHAN (defaults: net=GG, chan=HNZ)
    """
    return f"{getattr(p, 'net', 'GG')}.{p.sta}..{getattr(p, 'chan', 'HNZ')}"

def _latlon(p) -> Tuple[float, float]:
    """
    @brief Resolve latitude/longitude for a given processor
    @param p Processor with optional lat/lon attributes
    @return (lat, lon) tuple, falling back to config or hardcoded demo coords
    """
    lat = getattr(p, "lat", None)
    lon = getattr(p, "lon", None)
    if isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
        return float(lat), float(lon)
    # fallback if processor has no lat/lon
    return CFG.COORDS.get(p.sta, (-31.35, 115.92))

# ------------------------------------------------------------------------
# Socket.IO events
# ------------------------------------------------------------------------

@socketio.on("connect")
def _on_connect():
    """
    @brief Handle new client connections.
    @details Sends a one-time countdown event ("startup_tickdown") so the client
             knows how many seconds remain before data streams become valid.
    """
    remaining = max(0, int(round(_STARTUP_END - time.monotonic())))
    socketio.emit("startup_tickdown", {"delay": remaining}, to=request.sid)

def background_sender():
    """
    @brief Background task that emits station updates every second.
    @details For each processor, collects the latest snapshot (envelope, band, coords),
             computes normalization for the last sample, and broadcasts to all clients
             under the `station_update` event.
    """
    STARTUP_SECONDS = CFG.STARTUP_SECONDS
    while True:
        stations = []
        for p in _processors:
            snap = p.to_json()
            if not snap["timestamp"]:
                continue # skip processors with no data yet

            env_min, env_max = snap["env_min"], snap["env_max"]
            env_last = snap["env"][-1] if snap["env_len"] else None

            # normalize last sample into [0,1] if min/max available
            norm = None
            if env_last is not None and env_min is not None and env_max is not None and env_max > env_min:
                norm = (env_last - env_min) / (env_max - env_min)

            stations.append({
                "id": _sid(p),
                "sta": p.sta,
                "lat": _latlon(p)[0],
                "lon": _latlon(p)[1],
                "timestamp": snap["timestamp"],
                "startup_seconds": STARTUP_SECONDS,  # UI-only countdown hint
                "server_elapsed": time.time() - APP_BOOT_TS,
                "env_min": env_min,
                "env_max": env_max,
                "norm": norm,
                "band": snap["band"],
                "env_series": snap["env"],
                "env_fs": CFG.TARGET_HZ,
            })

        socketio.emit("station_update", {"stations": stations})
        socketio.sleep(1)

# ------------------------------------------------------------------------
# Flask routes
# ------------------------------------------------------------------------

@app.route("/")
def home():
    """
    @brief Home page route.
    @return Rendered `home.html` template for the live seismic map.
    @details Provides a default `startup_seconds` value until Socket.IO updates arrive.
    """
    return render_template("home.html", title="Live Seismic Map",
                           active_page="home", startup_seconds=int(CFG.STARTUP_SECONDS))

@app.route("/raw")
def raw_dump_all():
    """
    @brief Return raw snapshot data for all stations.
    @return JSON response with timestamp + per-station latest raw data.
    @details Each station includes lat/lon (if available) along with raw data fields.
    """
    out = {}
    for p in _processors:
        snap = p.latest_raw()
        if snap is not None:
            # shallow copy so original processor state is not mutated
            snap = dict(snap)
            snap["lat"] = getattr(p, "lat", None)
            snap["lon"] = getattr(p, "lon", None)
        out[_sid(p)] = snap
    return jsonify({
        "updated": datetime.now(timezone.utc).isoformat(),
        "stations": out
    })

# ------------------------------------------------------------------------
# Entrypoint
# ------------------------------------------------------------------------

if __name__ == "__main__":
    # Start background station update loop
    socketio.start_background_task(background_sender)
    # Launch Flask-SocketIO server
    socketio.run(app, debug=False, host="0.0.0.0", port=5000)
