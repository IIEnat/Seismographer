"""
app.py — Minimal Flask + Socket.IO app (Band-pass live + Playback + /raw)

Live (Socket.IO):
  - Creates StationProcessors and streams 'station_update' once per second:
      { id, lat, lon, norm, env_min/max, timestamp, band[], env[], fs_env }
  - No RMS polling, no /live or /wave endpoints.

Playback (HTTP):
  - Upload MiniSEED, browse timeline, per-second RMS for map, waveform slices, stats.
  - Kept concise but functionally identical.

Raw export:
  - /raw → latest native-fs values per live station, for debugging/export.
"""

from __future__ import annotations

import os, glob
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from math import ceil, floor
from typing import Dict, List, Tuple

import numpy as np
from flask import Flask, jsonify, render_template, request
from flask_socketio import SocketIO
from obspy import read as obspy_read, Stream, Trace
from werkzeug.utils import secure_filename

from python.receiver import (
    make_processors, start_processor_thread,  # live (band-pass only)
)

# --------------------------------- App ----------------------------------

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

BASE_DIR   = os.path.dirname(__file__)
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

AWST = timezone(timedelta(hours=8))  # UTC+8

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

def _latlon(p) -> Tuple[float, float]:
    return COORDS.get(p.sta, (-31.35, 115.92))

@socketio.on("connect")
def _on_connect():
    # First payload will arrive from the background task
    pass

def background_sender():
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
                "env_min": env_min,
                "env_max": env_max,
                "norm": norm,
                "band": snap["band"],
                "env_series": snap["env"],
                "env_fs": 5.0,
            })

        socketio.emit("station_update", {"stations": stations})
        socketio.sleep(1)


# -------------------------------- Entrypoint -----------------------------

if __name__ == "__main__":
    socketio.start_background_task(background_sender)
    socketio.run(app, debug=False, host="0.0.0.0", port=5000)
