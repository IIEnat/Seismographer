#!/usr/bin/env python3
# serve_data.py — simple HTTP backend for Seismic Drilldown (no frameworks)

from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from pathlib import Path
from datetime import datetime, timezone
import os, re, json
import numpy as np
from obspy import read, UTCDateTime

# ---- CONFIG ---------------------------------------------------------------
# Point to the parent of your year folders (e.g., .../Seismic Data)
DATA_ROOT = Path(os.environ.get("SEISMIC_DATA_ROOT", "Seismic Data")).resolve()

# Accept both .mseed and .miniseed
EXTS = (".mseed", ".miniseed")

# Match filenames like ..._YYYYMMDD_HHMMSS.miniseed
FNAME_TS = re.compile(r".*_(\d{8})_(\d{6})\.(?:mini)?seed$", re.IGNORECASE)


# ---- FILE SYSTEM SCAN -----------------------------------------------------
def _iter_station_dirs():
    """Yield leaf station directories under DATA_ROOT/YYYY/StationX."""
    if not DATA_ROOT.exists():
        return
    for year_dir in DATA_ROOT.iterdir():
        if not year_dir.is_dir():
            continue
        for st_dir in year_dir.iterdir():
            if st_dir.is_dir():
                yield st_dir


def _list_stations():
    """Return dict: { 'Station1': [Path(...files)], ... }"""
    stations = {}
    for st_dir in _iter_station_dirs():
        files = [p for p in st_dir.iterdir()
                 if p.is_file() and p.suffix.lower() in EXTS]
        if files:
            stations.setdefault(st_dir.name, []).extend(files)

    # Sort each station's files by timestamp (from filename if present)
    def sort_key(p: Path):
        m = FNAME_TS.match(p.name)
        if not m:
            return (datetime.min.replace(tzinfo=timezone.utc), p.name)
        dt = datetime.strptime(m.group(1) + m.group(2), "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
        return (dt, p.name)

    for k in stations:
        stations[k] = sorted(stations[k], key=sort_key)
    return stations


def _headonly_channels(path: Path):
    """Return sorted list of channel codes from headers."""
    try:
        st = read(str(path), headonly=True)
        return sorted({tr.stats.channel for tr in st if getattr(tr.stats, "channel", None)})
    except Exception:
        return []


def _file_meta(path: Path):
    """Return overall start/end ISO and max sampling_rate from headers."""
    try:
        st = read(str(path), headonly=True)
        starts = [tr.stats.starttime.datetime.replace(tzinfo=timezone.utc) for tr in st]
        ends   = [tr.stats.endtime.datetime.replace(tzinfo=timezone.utc) for tr in st]
        srs    = [float(getattr(tr.stats, "sampling_rate", 0.0)) for tr in st]
        if not starts or not ends:
            return None
        return {
            "start": min(starts).isoformat(),
            "end":   max(ends).isoformat(),
            "sampling_rate": max(srs) if srs else None
        }
    except Exception:
        return None


# ---- LOD DOWNSAMPLING -----------------------------------------------------
def _slice_minmax(y: np.ndarray, max_points: int):
    """
    Min/max envelope downsampling.
    Returns:
      {"mode":"line", "y":[...]}               if n <= max_points
      {"mode":"minmax","ymin":[...],"ymax":[...]} otherwise
    """
    n = int(y.size)
    if max_points <= 0 or n <= max_points:
        return {"mode": "line", "y": y.astype(float).tolist()}

    # Equal bins across the array
    edges = np.linspace(0, n, max_points + 1).astype(np.int64)
    y_min = np.empty(max_points, dtype=float)
    y_max = np.empty(max_points, dtype=float)
    for i in range(max_points):
        seg = y[edges[i]:edges[i+1]]
        if seg.size:
            y_min[i] = float(np.min(seg))
            y_max[i] = float(np.max(seg))
        else:
            y_min[i] = np.nan
            y_max[i] = np.nan
    return {"mode": "minmax", "ymin": y_min.tolist(), "ymax": y_max.tolist()}


# ---- HTTP HANDLER ---------------------------------------------------------
class Handler(SimpleHTTPRequestHandler):
    # Serve index.html from current working dir (where this file lives)
    def translate_path(self, path):
        # Let SimpleHTTPRequestHandler serve local files (index.html, etc.)
        return super().translate_path(path)

    def _send_json(self, obj, status=200):
        payload = json.dumps(obj)
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload.encode())

    def _error(self, code, msg):
        self._send_json({"error": msg}, status=code)

    def do_GET(self):
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)

        # /stations  ->  { "stations": ["Station1", ...] }
        if parsed.path == "/stations":
            stations = _list_stations()
            self._send_json({"stations": sorted(stations.keys())})
            return

        # /files?station=Station1 -> { "files":[{"file": "...", "hour": "HHMMSS"}, ...] }
        if parsed.path == "/files":
            station = qs.get("station", [None])[0]
            if not station:
                self._error(400, "station required")
                return
            stations = _list_stations()
            files = stations.get(station, [])
            out = []
            for p in files:
                m = FNAME_TS.match(p.name)
                hour = m.group(2) if m else "unknown"
                out.append({"file": p.name, "hour": hour})
            self._send_json({"files": out})
            return

        # /meta?station=...&file=... -> { "channels":[...], "meta":{start,end,sampling_rate} }
        if parsed.path == "/meta":
            station = qs.get("station", [None])[0]
            fname   = qs.get("file", [None])[0]
            if not station or not fname:
                self._error(400, "station and file required"); return
            stations = _list_stations()
            fpath = next((p for p in stations.get(station, []) if p.name == fname), None)
            if not fpath:
                self._error(404, "file not found"); return
            chs  = _headonly_channels(fpath)
            meta = _file_meta(fpath) or {}
            self._send_json({"channels": chs, "meta": meta})
            return

        # /data?station=...&file=...&channel=...&start=ISO&end=ISO&max_points=3000
        if parsed.path == "/data":
            station = qs.get("station", [None])[0]
            fname   = qs.get("file", [None])[0]
            channel = qs.get("channel", [None])[0]
            start_s = qs.get("start", [None])[0]  # optional ISO8601
            end_s   = qs.get("end",   [None])[0]  # optional ISO8601
            try:
                max_pts = int(qs.get("max_points", [3000])[0])
            except Exception:
                max_pts = 3000

            if not station or not fname or not channel:
                self._error(400, "station, file, channel required"); return

            stations = _list_stations()
            fpath = next((p for p in stations.get(station, []) if p.name == fname), None)
            if not fpath:
                self._error(404, "file not found"); return

            # Read full file then select channel
            try:
                st = read(str(fpath)).select(channel=channel)
            except Exception as e:
                self._error(500, f"read error: {e}"); return

            if not st:
                # Channel not present
                self._send_json({"mode":"line","x0":None,"x1":None,"dt":0.0,"payload":{"y":[]}})
                return

            tr = st[0]

            # Optional time slice (ISO → UTCDateTime)
            if start_s and end_s:
                try:
                    tr = tr.slice(UTCDateTime(start_s), UTCDateTime(end_s))
                except Exception as e:
                    self._error(400, f"bad start/end: {e}"); return

            # After slicing: compute precise bounds
            x0_dt = tr.stats.starttime.datetime.replace(tzinfo=timezone.utc)
            x1_dt = tr.stats.endtime.datetime.replace(tzinfo=timezone.utc)
            fs = float(tr.stats.sampling_rate)
            y = np.asarray(tr.data, dtype=float)

            # Build payload with LOD
            payload = _slice_minmax(y, max_pts)

            # --- Zoom fix: choose dt based on payload mode ---
            if payload["mode"] == "minmax":
                bins = len(payload["ymin"])
                duration = float(tr.stats.endtime - tr.stats.starttime)  # seconds
                dt_out = (duration / bins) if bins else 0.0
            else:
                dt_out = 1.0 / fs

            self._send_json({
                "mode": payload["mode"],
                "x0": x0_dt.isoformat(),
                "x1": x1_dt.isoformat(),   # client uses this to space bin centers
                "dt": dt_out,
                "payload": payload
            })
            return

        # Fallback to static files (index.html, etc.)
        return super().do_GET()


# ---- MAIN -----------------------------------------------------------------
if __name__ == "__main__":
    print(f"[serve] DATA_ROOT = {DATA_ROOT}")
    HTTPServer(("127.0.0.1", 8000), Handler).serve_forever()
