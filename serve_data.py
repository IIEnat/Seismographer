#!/usr/bin/env python3
import os
import json
import glob
from urllib.parse import urlparse, parse_qs
from http.server import HTTPServer, BaseHTTPRequestHandler

from obspy import read
import numpy as np

# Adjusted root to match your structure
SEISMIC_DATA_ROOT = os.path.join(os.path.dirname(__file__), "Seismic Data", "2022")
PORT = 8080


def list_stations():
    return [d for d in os.listdir(SEISMIC_DATA_ROOT)
            if os.path.isdir(os.path.join(SEISMIC_DATA_ROOT, d))]


def list_files(station):
    path = os.path.join(SEISMIC_DATA_ROOT, station)
    files = sorted(glob.glob(os.path.join(path, "*.miniseed")))
    return [
        {"file": os.path.basename(f),
         "hour": os.path.basename(f).split("_")[0]}
        for f in files
    ]


def file_metadata(station, file):
    path = os.path.join(SEISMIC_DATA_ROOT, station, file)
    st = read(path, headonly=True)
    chans = sorted(set(tr.stats.channel for tr in st))
    return {"channels": chans}


def downsample_trace(tr, max_points, t0=None, t1=None):
    data = tr.data.astype(float)
    n = len(data)

    if t0 and t1:
        tr = tr.slice(starttime=t0, endtime=t1)
        data = tr.data.astype(float)
        n = len(data)

    dt = tr.stats.delta
    t0 = tr.stats.starttime
    t1 = tr.stats.endtime

    if n <= max_points:
        return {
            "mode": "line",
            "x0": str(t0),
            "x1": str(t1),
            "dt": dt,
            "payload": {"y": data.tolist()},
        }

    step = int(np.ceil(n / max_points))
    ymin, ymax = [], []
    for i in range(0, n, step):
        chunk = data[i:i + step]
        ymin.append(float(np.min(chunk)))
        ymax.append(float(np.max(chunk)))
    return {
        "mode": "minmax",
        "x0": str(t0),
        "x1": str(t1),
        "dt": dt * step,
        "payload": {"ymin": ymin, "ymax": ymax},
    }


class Handler(BaseHTTPRequestHandler):
    def _json(self, obj):
        data = json.dumps(obj).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)
        path = parsed.path

        try:
            if path == "/stations":
                self._json({"stations": list_stations()})

            elif path == "/files":
                station = qs.get("station", [None])[0]
                self._json({"files": list_files(station)})

            elif path == "/meta":
                station = qs.get("station", [None])[0]
                file = qs.get("file", [None])[0]
                self._json(file_metadata(station, file))

            elif path == "/data":
                station = qs.get("station", [None])[0]
                file = qs.get("file", [None])[0]
                chan = qs.get("channel", [None])[0]
                max_points = int(qs.get("max_points", [3000])[0])
                start = qs.get("start", [None])[0]
                end = qs.get("end", [None])[0]

                path = os.path.join(SEISMIC_DATA_ROOT, station, file)
                st = read(path)
                tr = st.select(channel=chan)[0]

                t0 = tr.stats.starttime if not start else tr.stats.starttime.__class__(start)
                t1 = tr.stats.endtime if not end else tr.stats.endtime.__class__(end)

                result = downsample_trace(tr, max_points, t0, t1)
                self._json(result)

            else:
                if path in ("/", "/index.html"):
                    fpath = os.path.join(os.path.dirname(__file__), "index.html")
                    with open(fpath, "rb") as f:
                        self.send_response(200)
                        self.send_header("Content-Type", "text/html")
                        self.end_headers()
                        self.wfile.write(f.read())
                else:
                    self.send_error(404, f"No route for {path}")

        except Exception as e:
            self.send_error(500, f"Server error: {e}")


if __name__ == "__main__":
    httpd = HTTPServer(("0.0.0.0", PORT), Handler)
    print(f"Serving on http://127.0.0.1:{PORT}")
    httpd.serve_forever()
