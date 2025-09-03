# app.py
from __future__ import annotations

import os
import glob
from typing import Dict, List, Tuple

import numpy as np
from flask import Flask, render_template, request, jsonify
from werkzeug.utils import secure_filename
from obspy import read as obspy_read, Stream, Trace

# ---- Live/Synthetic seedlink pieces (kept from your original app) ----
try:
    from python.receiver import SLClientReceiver, create_blueprint
    from python.ingest import SyntheticIngest, Chan
except Exception:
    # If these are unavailable in some environments, keep the app runnable.
    SLClientReceiver = None
    create_blueprint = None
    SyntheticIngest = None
    Chan = None

app = Flask(__name__)
BASE_DIR = os.path.dirname(__file__)
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_DIR

# ------------------ Optional live map demo wiring ------------------
COORDS = {
    "XX.JINJ1..BHN": (-31.3447, 115.8923),
    "XX.JINJ1..BHE": (-31.3752, 115.9231),
    "XX.JINJ1..BHZ": (-31.3433, 115.9667),
}

USE_REAL_SEEDLINK = False

if SLClientReceiver is not None:
    rx = SLClientReceiver(coords=COORDS, metric="rms")
else:
    rx = None

if not USE_REAL_SEEDLINK and SyntheticIngest is not None and rx is not None:
    ingest = SyntheticIngest(
        chans=[
            Chan("XX", "JINJ1", "", "BHN", -31.3447, 115.8923, 2.0, 0.00),
            Chan("XX", "JINJ1", "", "BHE", -31.3752, 115.9231, 3.0, 0.33),
            Chan("XX", "JINJ1", "", "BHZ", -31.3433, 115.9667, 5.0, 0.66),
        ],
        sps=250.0,
        on_trace=getattr(rx, "on_trace", None),
    )
    ingest.start()

if create_blueprint is not None and rx is not None:
    app.register_blueprint(create_blueprint(rx))

# ------------------ Helpers ------------------


def clear_uploads_folder() -> None:
    """Remove previous batch so each upload is a fresh set."""
    for f in glob.glob(os.path.join(UPLOAD_DIR, "*")):
        try:
            os.remove(f)
        except Exception:
            pass


def _read_streams_for_files(filenames: List[str]) -> Stream:
    """Read all uploaded files into a single ObsPy Stream (concatenated)."""
    merged = Stream()
    for fname in filenames:
        path = os.path.join(UPLOAD_DIR, fname)
        if not os.path.exists(path):
            continue
        try:
            st = obspy_read(path)
            merged += st
        except Exception:
            # Ignore unreadable files; keep others
            continue
    return merged


def _station_id(tr: Trace) -> str:
    """Stable station key: NET.STA.LOC.CHA"""
    return f"{tr.stats.network}.{tr.stats.station}.{tr.stats.location}.{tr.stats.channel}"


def _group_traces_by_station(stream: Stream) -> Dict[str, List[Trace]]:
    """Group traces by station id."""
    grouped: Dict[str, List[Trace]] = {}
    for tr in stream:
        sid = _station_id(tr)
        grouped.setdefault(sid, []).append(tr)
    return grouped


def _slice_concat_values(
    traces: List[Trace], t_start, t_end
) -> Tuple[np.ndarray, Tuple[float, str, None]]:
    """
    Slice each trace in [t_start, t_end) and concatenate values.
    Returns (values, (fs, t0_iso, None)).
    - Concatenation means overlaps are combined back-to-back (for 1s windows this is fine).
    - The slice with the MOST samples defines fs and t0.
    """
    slices: List[np.ndarray] = []
    best = None  # (num_samples, fs, t0_iso, values)
    for tr in traces:
        try:
            sl = tr.slice(starttime=t_start, endtime=t_end)
        except Exception:
            continue
        vals = np.asarray(sl.data, dtype=np.float64)
        if vals.size:
            slices.append(vals)
            fs = float(getattr(tr.stats, "sampling_rate", 0.0))
            t0_iso = t_start.datetime.isoformat()
            cand = (vals.size, fs, t0_iso, vals)
            if best is None or cand[0] > best[0]:
                best = cand

    if not slices:
        return np.array([], dtype=np.float64), (0.0, None, None)

    all_vals = np.concatenate(slices, axis=0)
    _, fs_best, t0_iso_best, _ = best
    return all_vals, (fs_best, t0_iso_best, None)


def _hardcoded_latlon_for_trace(tr: Trace) -> Tuple[float, float]:
    """
    Try to get coordinates from trace.stats, otherwise fall back to a sensible default
    so Leaflet never breaks.
    """
    try:
        coords = getattr(tr.stats, "coordinates", {}) or {}
        lat = coords.get("latitude")
        lon = coords.get("longitude")
    except Exception:
        lat = lon = None

    if lat is None or lon is None:
        lat = getattr(tr.stats, "lat", None)
        lon = getattr(tr.stats, "lon", None)

    if lat is None or lon is None:
        # Final fallback near Gingin
        lat, lon = (-31.35, 115.92)
    return (lat, lon)


def _coord_for_station(traces: List[Trace]) -> Tuple[float, float]:
    """Pick coordinates from any trace (with fallback)."""
    for tr in traces:
        lat, lon = _hardcoded_latlon_for_trace(tr)
        if lat is not None and lon is not None:
            return (lat, lon)
    return (-31.35, 115.92)


# ------------------ Routes ------------------


@app.route("/")
def home():
    # If your project has a separate "home.html" keep this; otherwise swap to playback.html
    try:
        return render_template("home.html")
    except Exception:
        return render_template("playback.html")


@app.route("/playback", methods=["GET", "POST"])
def playback():
    """GET: render UI. POST: accept multi-file upload and return filenames."""
    if request.method == "POST":
        clear_uploads_folder()
        files = request.files.getlist("seedlink_file")
        if not files:
            return jsonify({"status": "error", "message": "No files uploaded"}), 400

        filenames: List[str] = []
        for file in files:
            if not file or not file.filename:
                continue
            filename = secure_filename(file.filename)
            dest = os.path.join(UPLOAD_DIR, filename)
            try:
                file.save(dest)
                filenames.append(filename)
            except Exception as e:
                print("Save error:", e)

        if not filenames:
            return jsonify({"status": "error", "message": "No valid filenames"}), 400
        return jsonify({"status": "uploaded", "filenames": filenames})

    # GET -> playback UI
    return render_template("playback.html")


@app.route("/playback_timeline/<filenames>")
def playback_timeline(filenames: str):
    """
    Return the global start/end and slider steps (1-second step).
    Timeline spans the union of all uploaded files.
    """
    file_list = [f for f in filenames.split(",") if f]
    merged = _read_streams_for_files(file_list)
    if len(merged) == 0:
        return jsonify({"start_iso": None, "end_iso": None, "steps": 1})

    start = min(tr.stats.starttime for tr in merged)
    end = max(tr.stats.endtime for tr in merged)
    window_size = 1  # seconds per slider step
    steps = int((end - start) // window_size) + 1

    return jsonify(
        {"start_iso": start.datetime.isoformat(), "end_iso": end.datetime.isoformat(), "steps": steps}
    )


@app.route("/playback_data/<filenames>/<int:slider>")
def playback_data(filenames: str, slider: int):
    """
    Return per-station RMS for the current 1-second window.
    Multiple files for the same station are treated as one logical signal.
    """
    file_list = [f for f in filenames.split(",") if f]
    merged = _read_streams_for_files(file_list)
    if len(merged) == 0:
        return jsonify({"slider": slider, "stations": []})

    window_size = 1
    t0 = min(tr.stats.starttime for tr in merged)
    t_start = t0 + slider * window_size
    t_end = t_start + window_size

    # Only Z-channel traces for map badges
    z_traces = [tr for tr in merged if str(tr.stats.channel).endswith("Z")]
    by_station = _group_traces_by_station(z_traces)

    stations = []
    for sid, traces in by_station.items():
        # Merge all segments intersecting this second
        vals, _meta = _slice_concat_values(traces, t_start, t_end)
        rms = float(np.sqrt(np.mean(vals ** 2))) if vals.size else 0.0
        lat, lon = _coord_for_station(traces)
        stations.append({"id": sid, "lat": lat, "lon": lon, "rms": rms})

    return jsonify({"slider": slider, "stations": stations})


@app.route("/playback_wave/<filenames>/<int:slider>/<path:station_id>")
def playback_wave(filenames: str, slider: int, station_id: str):
    """
    Return the 1-second waveform slice for one station.
    If multiple files contain that station, we combine their samples within the window.
    """
    file_list = [f for f in filenames.split(",") if f]
    merged = _read_streams_for_files(file_list)
    if len(merged) == 0:
        return jsonify({"fs": 0, "values": [], "t0_iso": None})

    window_size = 1
    t0 = min(tr.stats.starttime for tr in merged)
    t_start = t0 + slider * window_size
    t_end = t_start + window_size

    # All traces belonging to exactly this station id (NET.STA.LOC.CHA)
    traces = [tr for tr in merged if _station_id(tr) == station_id]
    if not traces:
        return jsonify({"fs": 0, "values": [], "t0_iso": None})

    vals, (fs, t0_iso, _) = _slice_concat_values(traces, t_start, t_end)
    return jsonify({"fs": float(fs or 0.0), "values": vals.astype(np.float64).tolist(), "t0_iso": t0_iso})


# ------------------ Main ------------------

if __name__ == "__main__":
    # Run with: python app.py
    app.run(host="0.0.0.0", port=8000, debug=True)
