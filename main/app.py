"""
app.py — Minimal Flask + Socket.IO app (Band-pass live + Playback + /raw)
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

# --------------------------------- App ----------------------------------
# ================== GLOBAL STARTUP TICKDOWN ==================
# One global “buffering” period equal to your initial processing window.
# If you run faster than real-time during dev (SPEED_FACTOR > 1), we scale it down.
_STARTUP_DELAY = max(0, int(math.ceil(CFG.BATCH_SECONDS / max(1.0, getattr(CFG, "SPEED_FACTOR", 1.0)))))
_STARTUP_END   = time.monotonic() + _STARTUP_DELAY
app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

BASE_DIR   = os.path.dirname(__file__)
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

AWST = timezone(timedelta(hours=8))  # UTC+8

APP_BOOT_TS = time.time()

# Register playback blueprint (all playback endpoints)
from python.playback_routes import create_playback_blueprint
app.register_blueprint(create_playback_blueprint(UPLOAD_DIR, AWST))

# Demo coords for stations (override with real values if available)
COORDS: Dict[str, Tuple[float, float]] = {
    "WAR27": (-31.35, 115.92),
    "WAR32": (-31.40, 115.96),
    "WAR33": (-31.45, 115.98),
}


# ---------------------------- Live processors ---------------------------

_processors = make_processors()
_threads    = [start_processor_thread(p) for p in _processors]

def _sid(p) -> str:
    return f"{getattr(p, 'net', 'GG')}.{p.sta}..{getattr(p, 'chan', 'HNZ')}"

## ------------- NEW & CHANGED ------------- ## 
def _latlon(p) -> Tuple[float, float]:
    lat = getattr(p, "lat", None)
    lon = getattr(p, "lon", None)
    if isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
        return float(lat), float(lon)
    # fallback to config if receiver didn’t resolve coords
    return CFG.COORDS.get(p.sta, (-31.35, 115.92))
## ------------- NEW & CHANGED ------------- ## 

@socketio.on("connect")
def _on_connect():
    # When a client connects, tell *that client* how many seconds remain.
    remaining = max(0, int(round(_STARTUP_END - time.monotonic())))
    socketio.emit("startup_tickdown", {"delay": remaining}, to=request.sid)

def background_sender():
    # UI-only countdown hint (real buffering is enforced inside StationProcessor)
    STARTUP_SECONDS = CFG.STARTUP_SECONDS
    while True:
        stations = []
        for p in _processors:
            snap = p.to_json()
            if not snap["timestamp"]:
                continue

            env_min, env_max = snap["env_min"], snap["env_max"]
            env_last = snap["env"][-1] if snap["env_len"] else None
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

# ------------------------------- Routes ---------------------------------

@app.route("/")
def home():
    # Provide a default for the initial overlay (used only until first socket payload arrives)
    return render_template("home.html", title="Live Seismic Map",
                           active_page="home", startup_seconds=int(CFG.STARTUP_SECONDS))

@app.route("/raw")
def raw_dump_all():
    out = {}
    for p in _processors:
        snap = p.latest_raw()
        if snap is not None:
            # add coords from the processor instance
            snap = dict(snap)  # shallow copy so we don’t mutate receiver state
            snap["lat"] = getattr(p, "lat", None)
            snap["lon"] = getattr(p, "lon", None)
        out[_sid(p)] = snap
    return jsonify({
        "updated": datetime.now(timezone.utc).isoformat(),
        "stations": out
    })

# -------------------------------- Entrypoint -----------------------------

if __name__ == "__main__":
    socketio.start_background_task(background_sender)
    socketio.run(app, debug=False, host="0.0.0.0", port=5000)