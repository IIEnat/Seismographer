#!/usr/bin/env python3
"""
seedlink_multi_receiver.py (strict per-second aggregation + /wave drilldown)

- Connects to multiple TCP MiniSEED sources (1 record/second containing 250 samples).
- For each station, aggregates **within that exact second only** (no rolling window).
- Keeps BOTH:
    * last finalized per-second aggregate (RMS or mean) for /live
    * last finalized per-second raw samples + fs for /wave

HTTP:
  GET /            -> serves RMS_station_viewer.html
  GET /live        -> latest finalized per-second values for each station (for the map)
  GET /wave?id=NET.STA..CHA -> last finalized 1s { id, t0_iso, fs, values[], sec_key }
"""
import argparse
import json
import signal
import socket
import threading
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from io import BytesIO
from typing import Dict, List, Tuple
from urllib.parse import urlparse, parse_qs
import os

import numpy as np
from obspy import read, UTCDateTime


@dataclass
class Source:
    host: str
    port: int
    net: str
    sta: str
    loc: str
    cha: str
    lat: float
    lon: float


def parse_source(s: str) -> Source:
    hp, netsta, latlon = s.split("@")
    host, port = hp.split(":")
    net, sta, loc, cha = netsta.split(".")
    lat, lon = latlon.split(",")
    return Source(host, int(port), net, sta, loc, cha, float(lat), float(lon))


def rms(arr: np.ndarray) -> float:
    if arr.size == 0:
        return 0.0
    a = arr.astype(np.float64, copy=False)
    return float(np.sqrt(np.mean(a * a)))


def mean(arr: np.ndarray) -> float:
    if arr.size == 0:
        return 0.0
    return float(np.mean(arr.astype(np.float64, copy=False)))


class Aggregator:
    def __init__(self, metric: str = "rms"):
        self.metric = metric.lower()
        self.func = rms if self.metric == "rms" else mean
        # per-station "current" UTC second key & buffer
        self.cur_key: Dict[str, int] = {}
        self.buffers: Dict[str, list] = defaultdict(list)
        self.cur_fs: Dict[str, float] = {}  # fs seen for current second

        # finalized values for the LAST completed second
        self.last_value: Dict[str, Tuple[str, float]] = {}          # (iso_second, value)
        self.last_wave: Dict[str, Tuple[str, float, List[float]]] = {}  # (iso_second, fs, values[])
        self.lock = threading.Lock()

    @staticmethod
    def second_key(t: UTCDateTime) -> int:
        return int(t.timestamp)

    def _finalize(self, sid: str, key: int):
        arr = np.asarray(self.buffers[sid], dtype=np.float64)
        val = self.func(arr) if arr.size else 0.0
        iso = datetime.utcfromtimestamp(key).replace(tzinfo=timezone.utc).isoformat()
        fs = float(self.cur_fs.get(sid, 0.0))
        # store aggregate and raw waveform for the last second
        self.last_value[sid] = (iso, float(val))
        self.last_wave[sid] = (iso, fs, arr.astype(np.float64, copy=False).tolist())
        # reset buffer for next second
        self.buffers[sid].clear()

    def add_block(self, sid: str, start: UTCDateTime, data: np.ndarray, fs: float):
        key = self.second_key(start)
        with self.lock:
            old_key = self.cur_key.get(sid)
            if old_key is None:
                self.cur_key[sid] = key
                self.cur_fs[sid] = fs
            elif key != old_key:
                # finalize previous second
                self._finalize(sid, old_key)
                # new second
                self.cur_key[sid] = key
                self.cur_fs[sid] = fs
            else:
                # same second; ensure fs is at least set
                if sid not in self.cur_fs:
                    self.cur_fs[sid] = fs
            # append current block's samples
            self.buffers[sid].extend(np.asarray(data, dtype=np.float64))

    def snapshot(self, coords: Dict[str, Tuple[float, float]]):
        with self.lock:
            stations = []
            for sid, (lat, lon) in coords.items():
                iso, val = self.last_value.get(sid, (None, 0.0))
                stations.append({
                    "id": sid, "lat": lat, "lon": lon, "rms": float(val), "last": iso
                })
            return stations

    def last_wave_packet(self, sid: str):
        with self.lock:
            return self.last_wave.get(sid)  # (iso, fs, values)


class Receiver:
    def __init__(self, sources: List[Source], reclen: int, metric: str):
        self.sources = sources
        self.reclen = reclen
        self.stop_evt = threading.Event()
        self.coords: Dict[str, Tuple[float, float]] = {}
        self.errors: Dict[str, str] = {}
        self.lock = threading.Lock()
        self.agg = Aggregator(metric)

    def id_for(self, s: Source) -> str:
        return f"{s.net}.{s.sta}.{s.loc}.{s.cha}"

    def _connect_loop(self, src: Source):
        sid = self.id_for(src)
        self.coords[sid] = (src.lat, src.lon)
        backoff = 1.0
        while not self.stop_evt.is_set():
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                    sock.settimeout(5.0)
                    sock.connect((src.host, src.port))
                    sock.settimeout(None)
                    self.errors.pop(sid, None)
                    buf = bytearray()
                    while not self.stop_evt.is_set():
                        chunk = sock.recv(8192)
                        if not chunk:
                            raise ConnectionError("eof")
                        buf.extend(chunk)
                        while len(buf) >= self.reclen:
                            rec = bytes(buf[:self.reclen])
                            del buf[:self.reclen]
                            try:
                                st = read(BytesIO(rec), format="MSEED")
                            except Exception:
                                continue
                            for tr in st:
                                data = tr.data
                                if data is None or len(data) == 0:
                                    continue
                                start = tr.stats.starttime
                                fs = float(tr.stats.sampling_rate or 0.0)
                                self.agg.add_block(sid, start, data, fs)
            except Exception as e:
                self.errors[sid] = str(e)
                time.sleep(min(backoff, 5.0))
                backoff *= 1.5

    def start(self):
        self.threads = []
        for s in self.sources:
            th = threading.Thread(target=self._connect_loop, args=(s,), daemon=True)
            th.start()
            self.threads.append(th)

    def stop(self):
        self.stop_evt.set()
        for th in self.threads:
            th.join(timeout=1.0)

    def snapshot(self):
        stations = self.agg.snapshot(self.coords)
        return {
            "updated": datetime.now(timezone.utc).isoformat(),
            "interval_ms": 1000,
            "stations": stations
        }

    def wave_payload(self, sid: str):
        pkt = self.agg.last_wave_packet(sid)
        if not pkt:
            return None
        iso, fs, values = pkt
        # sec_key used by UI to detect new seconds
        sec_key = int(datetime.fromisoformat(iso).timestamp())
        return {
            "id": sid,
            "t0_iso": iso,
            "fs": fs,
            "values": values,
            "sec_key": sec_key
        }


class Handler(SimpleHTTPRequestHandler):
    receiver: 'Receiver' = None
    here = os.path.dirname(os.path.abspath(__file__))

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        super().end_headers()

    def _send_json(self, obj, code=200):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store, max-age=0")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, fname: str, ctype="text/html"):
        try:
            fpath = os.path.join(self.here, fname)
            with open(fpath, "rb") as f:
                data = f.read()
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except Exception as e:
            self.send_error(404, f"Not found: {fname} ({e})")

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/live":
            return self._send_json(self.receiver.snapshot())

        if parsed.path == "/wave":
            qs = parse_qs(parsed.query or "")
            sid = (qs.get("id") or [None])[0]
            if not sid:
                return self._send_json({"error": "missing id"}, code=400)
            payload = self.receiver.wave_payload(sid)
            if not payload:
                return self._send_json({"error": "no data yet for id"}, code=404)
            return self._send_json(payload)

        # Serve your RMS_station_viewer.html by default
        if parsed.path in ("/", "/index.html", "/RMS_station_viewer.html"):
            return self._send_file("RMS_station_viewer.html", "text/html")

        # fall back to normal static handler
        return super().do_GET()


def run_http(receiver: Receiver, http_port: int):
    httpd = ThreadingHTTPServer(("0.0.0.0", http_port), Handler)
    Handler.receiver = receiver
    print(f"[receiver] HTTP on http://127.0.0.1:{http_port}/  (opens RMS_station_viewer.html)")
    try:
        httpd.serve_forever()
    finally:
        httpd.server_close()


def main():
    ap = argparse.ArgumentParser(description="MiniSEED multi-receiver with strict per-second aggregation + /wave")
    ap.add_argument("--reclen", type=int, default=4096)
    ap.add_argument("--http-port", type=int, default=8081)
    ap.add_argument("--metric", choices=["rms", "mean"], default="rms", help="aggregate within a second (default: rms)")
    ap.add_argument("--source", action="append", required=True, help="host:port@NET.STA..CHA@lat,lon")
    args = ap.parse_args()

    sources = [parse_source(s) for s in args.source]
    rx = Receiver(sources, args.reclen, args.metric)
    rx.start()

    stop_evt = threading.Event()

    def handle_sig(*_a):
        print("\n[receiver] Stopping... (graceful)")
        stop_evt.set()

    signal.signal(signal.SIGINT, handle_sig)
    signal.signal(signal.SIGTERM, handle_sig)

    http_thread = threading.Thread(target=run_http, args=(rx, args.http_port), daemon=True)
    http_thread.start()

    try:
        while not stop_evt.is_set():
            time.sleep(0.2)
    finally:
        rx.stop()
        print("[receiver] Bye.")


if __name__ == "__main__":
    main()
