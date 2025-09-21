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

# NEW: import the playback blueprint factory
from playback_routes import create_playback_blueprint

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

BASE_DIR   = os.path.dirname(__file__)
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

AWST = timezone(timedelta(hours=8))  # UTC+8

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

# ------------------------------ Playback --------------------------------

def _clear_uploads():
    for f in glob.glob(os.path.join(UPLOAD_DIR, "*")):
        try: os.remove(f)
        except: pass

def _read_streams_for_files(filenames: List[str]) -> Stream:
    merged = Stream()
    for fname in filenames:
        path = os.path.join(UPLOAD_DIR, fname)
        if not os.path.exists(path): continue
        try: merged += obspy_read(path)
        except: pass
    return merged

def _station_id(tr: Trace) -> str:
    return f"{tr.stats.network}.{tr.stats.station}.{tr.stats.location}.{tr.stats.channel}"

def _group_by_station(stream: Stream) -> Dict[str, List[Trace]]:
    g: Dict[str, List[Trace]] = {}
    for tr in stream:
        g.setdefault(_station_id(tr), []).append(tr)
    return g

def _trace_coords(tr: Trace) -> Tuple[float, float]:
    coords = getattr(tr.stats, "coordinates", None) or {}
    lat, lon = coords.get("latitude"), coords.get("longitude")
    if lat is None or lon is None:
        lat, lon = getattr(tr.stats, "lat", None), getattr(tr.stats, "lon", None)
    return (lat if lat is not None else -31.35, lon if lon is not None else 115.92)

def _coords_for_traces(traces: List[Trace]) -> Tuple[float, float]:
    for tr in traces:
        lat, lon = _trace_coords(tr)
        if lat is not None and lon is not None:
            return (lat, lon)
    return (-31.35, 115.92)

def _slice_concat(traces: List[Trace], t_start, t_end):
    """Concat all samples in [t_start, t_end) across segments (1 s windows)."""
    chunks, best = [], None  # best defines fs and t0
    for tr in traces:
        try: sl = tr.slice(starttime=t_start, endtime=t_end)
        except: continue
        vals = np.asarray(sl.data, dtype=np.float64)
        if not vals.size: continue
        chunks.append(vals)
        fs = float(getattr(tr.stats, "sampling_rate", 0.0))
        cand = (vals.size, fs, t_start.datetime.isoformat(), vals)
        if best is None or cand[0] > best[0]:
            best = cand
    if not chunks: return np.array([], dtype=np.float64), (0.0, None)
    all_vals = np.concatenate(chunks, axis=0)
    return all_vals, (best[1], best[2])

# ------------------------------- Routes ---------------------------------

@app.route("/")
def home():
    return render_template("home.html", title="Live Seismic Map", active_page="home")

@app.route("/raw")
def raw_dump_all():
    """Return latest RAW slice for every live station (native fs)."""
    out = {}
    for p in _processors:
        out[_sid(p)] = p.latest_raw()
    return jsonify({"updated": datetime.now(timezone.utc).isoformat(), "stations": out})

@app.route("/playback", methods=["GET", "POST"])
def playback():
    if request.method == "POST":
        _clear_uploads()
        files = request.files.getlist("seedlink_file")
        if not files:
            return jsonify({"status": "error", "message": "No files uploaded"}), 400
        names = []
        for f in files:
            if not f or not f.filename: continue
            name = secure_filename(f.filename)
            try:
                f.save(os.path.join(UPLOAD_DIR, name))
                names.append(name)
            except Exception as e:
                print("Save error:", e)
        if not names:
            return jsonify({"status": "error", "message": "No valid filenames"}), 400
        return jsonify({"status": "uploaded", "filenames": names})
    return render_template("playback.html", title="Playback", active_page="playback")

@app.route("/playback_timeline/<filenames>")
def playback_timeline(filenames: str):
    files = [f for f in filenames.split(",") if f]
    st = _read_streams_for_files(files)
    if len(st) == 0:
        return jsonify({"start_iso": None, "end_iso": None, "steps": 1})
    start = min(tr.stats.starttime for tr in st)
    end   = max(tr.stats.endtime   for tr in st)
    steps = int((end - start)) + 1
    return jsonify({
        "start_iso": start.datetime.replace(tzinfo=AWST).isoformat(),
        "end_iso":   end.datetime.replace(tzinfo=AWST).isoformat(),
        "steps":     steps
    })

@app.route("/playback_data/<filenames>/<int:slider>")
def playback_data(filenames: str, slider: int):
    files = [f for f in filenames.split(",") if f]
    st = _read_streams_for_files(files)
    if len(st) == 0:
        return jsonify({"slider": slider, "stations": []})
    t0 = min(tr.stats.starttime for tr in st)
    t_start, t_end = t0 + slider, t0 + slider + 1
    z_traces = [tr for tr in st if str(tr.stats.channel).endswith("Z")]
    stations = []
    for sid, traces in _group_by_station(z_traces).items():
        vals, _meta = _slice_concat(traces, t_start, t_end)
        rms = float(np.sqrt(np.mean(vals ** 2))) if vals.size else 0.0
        lat, lon = _coords_for_traces(traces)
        stations.append({"id": sid, "lat": lat, "lon": lon, "rms": rms})
    return jsonify({"slider": slider, "stations": stations})

@app.route("/playback_wave/<filenames>/<int:slider>/<path:station_id>")
def playback_wave(filenames: str, slider: int, station_id: str):
    files = [f for f in filenames.split(",") if f]
    st = _read_streams_for_files(files)
    if len(st) == 0:
        return jsonify({"fs": 0, "values": [], "t0_iso": None})
    t0 = min(tr.stats.starttime for tr in st)
    t_start, t_end = t0 + slider, t0 + slider + 1
    traces = [tr for tr in st if f"{tr.stats.network}.{tr.stats.station}.{tr.stats.location}.{tr.stats.channel}" == station_id]
    if not traces:
        return jsonify({"fs": 0, "values": [], "t0_iso": None})
    vals, (fs, t0_iso) = _slice_concat(traces, t_start, t_end)
    return jsonify({"fs": float(fs or 0.0), "values": vals.astype(np.float64).tolist(), "t0_iso": t0_iso})

@app.route("/playback_stats/<filenames>")
def playback_stats(filenames: str):
    files = [f for f in filenames.split(",") if f]
    st = _read_streams_for_files(files)
    if len(st) == 0:
        return jsonify({"min": None, "max": None})
    z_traces = [tr for tr in st if str(tr.stats.channel).endswith("Z")]
    if not z_traces:
        return jsonify({"min": None, "max": None})

    t_start = min(tr.stats.starttime for tr in z_traces)
    t_end   = max(tr.stats.endtime   for tr in z_traces)
    base = int(floor(t_start.timestamp))
    n    = max(1, int(ceil(t_end.timestamp) - base))

    sumsqs = defaultdict(lambda: np.zeros(n, dtype=np.float64))
    counts = defaultdict(lambda: np.zeros(n, dtype=np.int64))

    for tr in z_traces:
        sid = f"{tr.stats.network}.{tr.stats.station}.{tr.stats.location}.{tr.stats.channel}"
        fs  = float(getattr(tr.stats, "sampling_rate", 0.0) or 0.0)
        if fs <= 0: continue
        data = np.asarray(tr.data, dtype=np.float64)
        if data.size == 0: continue

        idx = np.floor((tr.stats.starttime.timestamp - base) + np.arange(data.size) / fs).astype(np.int64)
        m = (idx >= 0) & (idx < n)
        if not np.any(m): continue
        idx = idx[m]; seg = data[m]; seg2 = seg * seg

        sumsqs[sid] += np.bincount(idx, weights=seg2, minlength=n)
        counts[sid] += np.bincount(idx, minlength=n)

    best_min = None
    best_max = None
    for sid in sumsqs.keys():
        c, s2 = counts[sid], sumsqs[sid]
        valid = c > 0
        if not np.any(valid): continue
        rms = np.zeros_like(s2, dtype=np.float64)
        rms[valid] = np.sqrt(s2[valid] / c[valid])
        mi_idx = np.argmin(np.where(valid, rms, np.inf))
        ma_idx = np.argmax(np.where(valid, rms, -np.inf))
        mi_val = rms[mi_idx] if valid[mi_idx] else np.inf
        ma_val = rms[ma_idx] if valid[ma_idx] else -np.inf
        if best_min is None or mi_val < best_min[0]: best_min = (float(mi_val), sid, int(mi_idx))
        if best_max is None or ma_val > best_max[0]: best_max = (float(ma_val), sid, int(ma_idx))

    def pack(item):
        if not item: return None
        val, sid, sec_idx = item
        iso = datetime.fromtimestamp(base + sec_idx, tz=AWST).isoformat()
        return {"value": val, "id": sid, "iso": iso}

    return jsonify({"min": pack(best_min), "max": pack(best_max)})

# -------------------------------- Entrypoint -----------------------------

if __name__ == "__main__":
    socketio.start_background_task(background_sender)
    socketio.run(app, debug=False, host="0.0.0.0", port=5000)
