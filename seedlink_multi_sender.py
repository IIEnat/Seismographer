
#!/usr/bin/env python3
"""
seedlink_multi_sender.py (per-second packeted)
----------------------------------------------
Once per second, sends ONE MiniSEED record containing 250 float samples.
Amplitude cycles across 5 levels every second. Each station is on its own TCP port.

Requires: obspy, numpy
"""
import argparse
import math
import signal
import socket
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from io import BytesIO
from typing import List

import numpy as np
from obspy import Stream, Trace, UTCDateTime

DEFAULT_RECLEN = 4096
ENCODING = "FLOAT32"   # fixed
SAMPLES_PER_SECOND = 250   # number of samples in each one-second record


@dataclass
class StationSpec:
    port: int
    net: str
    sta: str
    loc: str
    cha: str
    lat: float
    lon: float
    wave: str  # 'sine'|'square'|'triangle'|'saw'|'noise'


def sawtooth(x: float) -> float:
    return 2.0 * (x - math.floor(x + 0.5))


def triangle(x: float) -> float:
    return 2.0 * abs(2.0 * (x - math.floor(x + 0.5))) - 1.0


def gen_wave_block(wave: str, base_freq: float, amp: float, n: int) -> np.ndarray:
    # Generate n samples across one second (uniform grid)
    t = np.linspace(0.0, 1.0, n, endpoint=False)
    phase = (base_freq * t) % 1.0
    if wave == "sine":
        w = np.sin(2.0 * np.pi * phase)
    elif wave == "square":
        w = np.sign(np.sin(2.0 * np.pi * phase))
        w[w==0] = 1.0
    elif wave == "triangle":
        w = 2.0 * np.abs(2.0 * (phase - np.floor(phase + 0.5))) - 1.0
    elif wave == "saw":
        w = 2.0 * (phase - np.floor(phase + 0.5))
    else:
        w = np.random.rand(n) * 2.0 - 1.0
    return (amp * w).astype(np.float32)


def make_mseed_record(block: np.ndarray, sr: float, spec: StationSpec, t_utc: UTCDateTime, reclen=DEFAULT_RECLEN) -> bytes:
    tr = Trace(
        data=block,
        header={
            "network": spec.net,
            "station": spec.sta,
            "location": spec.loc,
            "channel": spec.cha,
            "sampling_rate": sr,
            "npts": len(block),
            "starttime": t_utc,
            "coordinates": {"latitude": spec.lat, "longitude": spec.lon},
        },
    )
    st = Stream([tr])
    buf = BytesIO()
    st.write(buf, format="MSEED", reclen=reclen, encoding=ENCODING)
    return buf.getvalue()


def station_server(stop_evt: threading.Event, host: str, spec: StationSpec, base_freq: float, reclen: int):
    rms_levels = [100.0, 300.0, 500.0, 800.0, 1200.0]  # cycles each second
    print(f"[sender:{spec.sta}] {host}:{spec.port} 1 pkt/sec, {SAMPLES_PER_SECOND} samples, wave={spec.wave}")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as srv:
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        srv.bind((host, spec.port))
        srv.listen(1)
        print(f"[sender:{spec.sta}] Listening...")
        conn, addr = srv.accept()
        print(f"[sender:{spec.sta}] Client connected from {addr}")
        with conn:
            sec_idx = 0
            try:
                while not stop_evt.is_set():
                    amp = rms_levels[sec_idx % len(rms_levels)]
                    block = gen_wave_block(spec.wave, base_freq, amp, SAMPLES_PER_SECOND)
                    start = UTCDateTime(datetime.now(timezone.utc).isoformat())
                    rec = make_mseed_record(block, SAMPLES_PER_SECOND, spec, start, reclen)
                    conn.sendall(rec)
                    sec_idx += 1
                    time.sleep(1.0)  # exactly one packet per second
            except (BrokenPipeError, ConnectionResetError):
                print(f"[sender:{spec.sta}] Client disconnected")
            except Exception as e:
                print(f"[sender:{spec.sta}] Error: {e!r}")


def main():
    ap = argparse.ArgumentParser(description="Per-second MiniSEED simulator (250 samples per second)")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--freq", type=float, default=5.0, help="waveform frequency inside each second (Hz)")
    ap.add_argument("--reclen", type=int, default=DEFAULT_RECLEN, choices=(512, 1024, 2048, 4096))
    ap.add_argument("--ports", nargs="*", type=int, default=[18001, 18002, 18003])
    args = ap.parse_args()

    stations: List[StationSpec] = [
        StationSpec(args.ports[0], "XX", "JINJ1", "", "BHZ", -31.9619, 115.9488, "sine"),
        StationSpec(args.ports[1], "XX", "JINJ2", "", "BHZ", -31.9389, 115.9670, "square"),
        StationSpec(args.ports[2], "XX", "JINJ3", "", "BHZ", -31.9200, 115.9900, "triangle"),
    ]

    stop_evt = threading.Event()

    def handle_sig(*_a):
        print("\n[sender] Stopping... (graceful)")
        stop_evt.set()

    signal.signal(signal.SIGINT, handle_sig)
    signal.signal(signal.SIGTERM, handle_sig)

    threads = []
    for s in stations:
        th = threading.Thread(target=station_server, args=(stop_evt, args.host, s, args.freq, args.reclen), daemon=True)
        th.start()
        threads.append(th)

    try:
        while not stop_evt.is_set():
            time.sleep(0.2)
    finally:
        stop_evt.set()
        for th in threads:
            th.join(timeout=1.0)
        print("[sender] Bye.")


if __name__ == "__main__":
    main()
