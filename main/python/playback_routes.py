from __future__ import annotations

import os, glob, io
from collections import defaultdict
from datetime import datetime, timezone
from math import floor, ceil
from typing import Dict, List, Tuple

import numpy as np
from scipy import signal
from flask import Blueprint, jsonify, render_template, request
from werkzeug.utils import secure_filename
from obspy import read as obspy_read, Stream, Trace
import config as CFG


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
    
    def compute_rms(x) -> float:
        arr = np.asarray(x, dtype=float)
        if arr.size == 0:
            return 0.0
        return float(np.sqrt(np.mean(arr * arr)))

    def _design_bandpass(fs: float, band: tuple[float, float]):
        lo, hi = band
        nyq = max(1e-12, 0.5 * fs)
        wn = (max(lo, 1e-4) / nyq, max(hi, 2e-4) / nyq)
        return signal.butter(4, wn, btype="bandpass", output="sos")

    def _bandpass_sos(x: np.ndarray, sos, zi=None):
        y, zi_out = signal.sosfilt(sos, np.asarray(x, dtype=np.float64), zi=zi)
        return y.astype(float), zi_out

    def _env_native(band_native: np.ndarray, fs: float) -> np.ndarray:
        if band_native.size == 0:
            return np.empty(0, dtype=float)
        env = np.abs(signal.hilbert(band_native.astype(np.float64)))
        nyq = max(1e-6, 0.5 * fs)
        wc = min(0.3 / nyq, 0.99)  # gentle smoothing of the envelope
        sos = signal.butter(2, wc, btype="low", output="sos")
        env = signal.sosfiltfilt(sos, env)
        return np.maximum(env, 0.0).astype(float)

    def _decimate_to_tgt(x: np.ndarray, fs: float, tgt_hz: float) -> np.ndarray:
        if x.size == 0:
            return np.empty(0, dtype=float)
        fs_i = int(round(fs))
        tgt_i = int(round(tgt_hz))
        if fs_i > tgt_i and fs_i % tgt_i == 0:
            q = fs_i // tgt_i
            return signal.decimate(x.astype(np.float64), q, ftype="iir", zero_phase=True).astype(float)
        # fallback rational resample
        from math import gcd
        up, down = tgt_i, fs_i
        g = gcd(up, down) if down else 1
        up //= max(g, 1); down //= max(g, 1)
        return signal.resample_poly(x.astype(np.float64), up, down).astype(float)

    def process_samples_to_5hz(samples: np.ndarray, fs: float) -> dict:
        """raw -> band-pass -> hilbert envelope -> lp smooth -> decimate to TARGET_HZ"""
        samples = np.asarray(samples, dtype=np.float64)
        sos = _design_bandpass(fs, CFG.BAND)
        band_native, _ = _bandpass_sos(samples, sos, zi=signal.sosfilt_zi(sos) * 0.0)
        env_native = _env_native(band_native, fs)

        band_5 = _decimate_to_tgt(band_native, fs, CFG.TARGET_HZ)
        env_5  = _decimate_to_tgt(env_native,  fs, CFG.TARGET_HZ)
        n = min(band_5.size, env_5.size)
        if n:
            band_5 = band_5[:n]
            env_5  = env_5[:n]

        return {
            "band": [round(v, 3) for v in band_5],
            "env":  [round(v, 3) for v in env_5],
            "env_min": float(np.min(env_5)) if env_5.size else None,
            "env_max": float(np.max(env_5)) if env_5.size else None,
            "target_hz": float(CFG.TARGET_HZ),
        }

    # ---------- Routes ----------
# --- ROUTES: split GET and POST cleanly, use bp only ---

    @bp.route("/playback", methods=["GET"])
    def playback_get():
        return render_template("playback.html")

    @bp.route("/playback", methods=["POST"])
    def upload_and_process_playback():
        files = request.files.getlist("seedlink_file")
        if len(files) != 1:
            return ("Only one file may be uploaded", 400)

        f = files[0]
        filename = (f.filename or "").strip()
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        # accept ONLY .miniseed
        if ext != "miniseed":
            return ("Unsupported file type; please upload a .miniseed file", 415)

        # fresh batch: clear previous uploads, then save this file to disk
        clear_uploads_folder()
        from werkzeug.utils import secure_filename
        safe = secure_filename(filename)
        dest = os.path.join(upload_dir, safe)
        f.stream.seek(0)
        f.save(dest)

        # Optional: immediate preview processing (so UI can show a quick result)
        try:
            st = obspy_read(dest)
            st.merge(fill_value="interpolate")
            tr = st[0]
            data = tr.data.astype(np.float64)
            fs = float(tr.stats.sampling_rate)
            preview = process_samples_to_5hz(data, fs)

            rid = {
                "network": getattr(tr.stats, "network", ""),
                "station": getattr(tr.stats, "station", ""),
                "location": getattr(tr.stats, "location", ""),
                "channel": getattr(tr.stats, "channel", ""),
            }
            preview["rms_env"] = compute_rms(np.array(preview["env"], dtype=float))
            preview["id"] = f'{rid["network"]}.{rid["station"]}.{rid["location"]}.{rid["channel"]}'
        except Exception:
            # if preview fails, still let the client proceed to timeline/data endpoints
            preview = {}

        # IMPORTANT: return filenames saved to disk — front-end will use these
        return jsonify({"status": "uploaded", "filenames": [safe], **preview})


    def playback():
        """GET: render UI. POST: accept exactly ONE MiniSEED file and return its filename."""
        if request.method == "POST":
            clear_uploads_folder()

            files = [f for f in request.files.getlist("seedlink_file") if f and f.filename]

            if len(files) == 0:
                return jsonify({"status": "error", "message": "No file uploaded"}), 400
            if len(files) > 1:
                return jsonify({"status": "error", "message": "Only one file may be uploaded"}), 400

            file = files[0]
            filename = secure_filename(file.filename)
            dest = os.path.join(upload_dir, filename)
            try:
                file.save(dest)
            except Exception as e:
                return jsonify({"status": "error", "message": f"Failed to save file: {e}"}), 500

            return jsonify({"status": "uploaded", "filename": filename, **out})


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
