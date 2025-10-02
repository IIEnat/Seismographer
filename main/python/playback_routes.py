# playback_routes.py
from __future__ import annotations

import os
import glob
from typing import Dict, List, Tuple
from collections import defaultdict
from datetime import datetime, timezone

import numpy as np
from flask import Blueprint, current_app, jsonify, render_template, request
from werkzeug.utils import secure_filename
from obspy import read as obspy_read, Stream, Trace
from math import floor, ceil

def create_playback_blueprint(upload_dir: str, awst_tz: timezone) -> Blueprint:
    """
    Factory that returns a Blueprint encapsulating all playback endpoints and helpers.
    """
    bp = Blueprint("playback", __name__)

    # ---------- Data Extraction for JSON Structure ----------
    def extract_station_json(tr: Trace, env_fs: float = 1.0) -> dict:
        """
        Extracts the required JSON structure for a single trace (station/channel).
        Downsamples envelope and band arrays to env_fs (default 1Hz) for storage efficiency.
        """
        # Envelope: absolute value of the analytic signal (Hilbert transform)
        from scipy.signal import hilbert, decimate
        data = np.asarray(tr.data, dtype=np.float64)
        if data.size == 0:
            return None
        # Envelope calculation
        analytic = hilbert(data)
        envelope = np.abs(analytic)
        # Downsample envelope and band to 1Hz (or as close as possible)
        fs = float(getattr(tr.stats, "sampling_rate", 0.0) or 0.0)
        if fs <= 0:
            return None
        decim = max(1, int(round(fs / env_fs)))
        env_ds = envelope[::decim]
        band_ds = data[::decim]
        MAX = 3600
        env_ds  = env_ds[:MAX]
        band_ds = band_ds[:MAX]
        env_min = float(np.min(env_ds)) if env_ds.size else 0.0
        env_max = float(np.max(env_ds)) if env_ds.size else 0.0
        t0 = tr.stats.starttime.datetime.replace(tzinfo=awst_tz)
        return {
            "timestamp": t0.isoformat(),
            "band_len": int(len(band_ds)),
            "env_len": int(len(env_ds)),
            "env_min": env_min,
            "env_max": env_max,
            "band": band_ds.tolist(),
            "env": env_ds.tolist()
        }

    @bp.route("/playback_json/<filenames>")
    def playback_json(filenames: str):
        """
        Returns a JSON object for each station in the uploaded files, with the required structure.
        Only the first trace for each station is used for demonstration.
        """
        file_list = [f for f in filenames.split(",") if f]
        merged = _read_streams_for_files(file_list)
        if len(merged) == 0:
            return jsonify({"stations": []})
        by_station = _group_traces_by_station(merged)
        result = []
        for sid, traces in by_station.items():
            # Use the first trace for each station for this demo
            js = extract_station_json(traces[0])
            if js:
                js["id"] = sid
                result.append(js)
        return jsonify({"stations": result})

    # ---------- Helpers (scoped to this blueprint) ----------
    def clear_uploads_folder() -> None:
        """Remove previous batch so each upload is a fresh set."""
        for f in glob.glob(os.path.join(upload_dir, "*")):
            try:
                os.remove(f)
            except Exception:
                pass

    # Read all uploaded files into one ObsPy Stream, stores in a object
    def _read_streams_for_files(filenames: List[str]) -> Stream:
        """Read all uploaded files into a single ObsPy Stream (concatenated)."""
        merged = Stream()
        for fname in filenames:
            path = os.path.join(upload_dir, fname)
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

    # ---------- Routes ----------
    @bp.route("/playback", methods=["GET", "POST"])
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
                dest = os.path.join(upload_dir, filename)
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

    @bp.route("/playback_timeline/<filenames>")
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

        return jsonify({
            "start_iso": start.datetime.replace(tzinfo=awst_tz).isoformat(),
            "end_iso": end.datetime.replace(tzinfo=awst_tz).isoformat(),
            "steps": steps
        })

    @bp.route("/playback_data/<filenames>/<int:slider>")
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

    @bp.route("/playback_wave/<filenames>/<int:slider>/<path:station_id>")
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

    @bp.route("/playback_stats/<filenames>")
    def playback_stats(filenames: str):
        """
        Compute per-second RMS across the entire uploaded hour in one pass (server-side).
        Returns the global min/max RMS (value + station id + timestamp ISO).
        Efficient: vectorized binning by second using np.bincount; no N requests from client.
        """
        file_list = [f for f in filenames.split(",") if f]
        merged = _read_streams_for_files(file_list)
        if len(merged) == 0:
            return jsonify({"min": None, "max": None})

        # Work on Z only (matches your playback policy)
        z_traces = [tr for tr in merged if str(tr.stats.channel).endswith("Z")]
        if not z_traces:
            return jsonify({"min": None, "max": None})

        # Reference second grid for the hour
        t_start = min(tr.stats.starttime for tr in z_traces)
        t_end   = max(tr.stats.endtime   for tr in z_traces)
        base_sec = int(floor(t_start.timestamp))                      # anchor
        n_secs   = max(1, int(ceil(t_end.timestamp) - base_sec))      # ~3600

        # Per-station accumulators: second -> sum(x^2) and count
        sumsqs = defaultdict(lambda: np.zeros(n_secs, dtype=np.float64))
        counts = defaultdict(lambda: np.zeros(n_secs, dtype=np.int64))

        # Vectorized binning per trace
        for tr in z_traces:
            sid = _station_id(tr)
            fs = float(getattr(tr.stats, "sampling_rate", 0.0) or 0.0)
            if fs <= 0:
                continue
            data = np.asarray(tr.data, dtype=np.float64)
            if data.size == 0:
                continue

            # Offset seconds from base
            start_ts = tr.stats.starttime.timestamp
            # For each sample, compute which integer-second bucket it belongs to
            idx = np.floor((start_ts - base_sec) + np.arange(data.size) / fs).astype(np.int64)

            # Keep only indices within [0, n_secs)
            m = (idx >= 0) & (idx < n_secs)
            if not np.any(m):
                continue
            idx = idx[m]
            seg = data[m]
            seg2 = seg * seg

            # Accumulate sum of squares and counts into per-second bins
            sumsqs[sid] += np.bincount(idx, weights=seg2, minlength=n_secs)
            counts[sid] += np.bincount(idx, minlength=n_secs)

        # Compute RMS per second for each station, then global min/max
        best_min = None  # (rms, sid, sec_idx)
        best_max = None
        for sid in sumsqs.keys():
            c = counts[sid]
            s2 = sumsqs[sid]
            valid = c > 0
            if not np.any(valid):
                continue
            rms = np.zeros_like(s2, dtype=np.float64)
            rms[valid] = np.sqrt(s2[valid] / c[valid])

            # min (exclude zeros where no data)
            mi_idx = np.argmin(np.where(valid, rms, np.inf))
            ma_idx = np.argmax(np.where(valid, rms, -np.inf))
            mi_val = rms[mi_idx] if valid[mi_idx] else np.inf
            ma_val = rms[ma_idx] if valid[ma_idx] else -np.inf

            if best_min is None or mi_val < best_min[0]:
                best_min = (float(mi_val), sid, int(mi_idx))
            if best_max is None or ma_val > best_max[0]:
                best_max = (float(ma_val), sid, int(ma_idx))

        def pack(item):
            if not item:
                return None
            val, sid, sec_idx = item
            iso = datetime.fromtimestamp(base_sec + sec_idx, tz=awst_tz).isoformat()
            return {"value": val, "id": sid, "iso": iso}

        return jsonify({"min": pack(best_min), "max": pack(best_max)})

    return bp
