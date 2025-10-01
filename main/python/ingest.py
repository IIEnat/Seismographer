"""
Ingest layer for Seismographer project.

Supports:
- SyntheticIngest
- SeedLinkIngest (placeholder)
- SimEasySeedLinkClient (TEST ONLY)

All ingest paths call a provided callback: on_trace(Trace).
"""
from __future__ import annotations
import threading, time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, List, Optional

import numpy as np
from obspy import Trace, UTCDateTime

import config as CFG

try:
    from obspy.clients.seedlink.easyseedlink import EasySeedLinkClient  # noqa: F401
except Exception:
    EasySeedLinkClient = None  # keep import optional so dev envs still run

OnTrace = Callable[[Trace], None]

# ---------------- Global speed control ----------------
SPEED_FACTOR = CFG.SPEED_FACTOR

# ---------------- Base + Data Classes ----------------
class IngestBase:
    def start(self): raise NotImplementedError
    def stop(self):  pass

@dataclass(frozen=True)
class Chan:
    net: str; sta: str; loc: str; cha: str
    lat: float; lon: float; freq: float; phase: float; amp: float = 1200.0

# ---------------- Real SeedLink Stub ----------------
class SeedLinkIngest(IngestBase):
    """Placeholder for future wiring to a real SeedLink server."""
    def __init__(self, server: str, on_trace: OnTrace):
        self.server = server
        self.on_trace = on_trace
        self._t: Optional[threading.Thread] = None
        self._stop = threading.Event()

    def start(self):
        raise NotImplementedError("SeedLinkIngest not yet implemented")

    def stop(self):
        self._stop.set()
        if self._t: self._t.join(timeout=1.0)

# ---------------- Synthetic Generator (1 Hz bursts) ----------------
class SyntheticIngest(IngestBase):
    def __init__(self, chans: List[Chan], sps: float, on_trace: OnTrace):
        self.chans = list(chans)
        self.sps = float(sps)
        self.on_trace = on_trace
        self._stop = threading.Event()
        self._t: Optional[threading.Thread] = None

    def _loop(self):
        n = int(self.sps)
        while not self._stop.is_set():
            t0 = datetime.now(timezone.utc)
            ut = UTCDateTime(t0)
            t = np.linspace(0, 1, n, endpoint=False)
            for ch in self.chans:
                w = np.sin(2*np.pi*(ch.freq*t + ch.phase)) + 0.15*np.random.randn(n)
                data = (w * ch.amp).astype(np.int32)
                tr = Trace(data=data)
                tr.stats.network = ch.net
                tr.stats.station = ch.sta
                tr.stats.location = ch.loc
                tr.stats.channel = ch.cha
                tr.stats.sampling_rate = self.sps
                tr.stats.starttime = ut
                tr.stats.coordinates = {"latitude": ch.lat, "longitude": ch.lon}
                self.on_trace(tr)
            now = datetime.now(timezone.utc).timestamp()
            sleep = max(0.0, 1.0 - (now - int(now)))
            time.sleep(sleep / SPEED_FACTOR)

    def start(self):
        if self._t and self._t.is_alive(): return
        self._stop.clear()
        self._t = threading.Thread(target=self._loop, name="SyntheticIngest", daemon=True)
        self._t.start()

    def stop(self):
        self._stop.set()
        if self._t: self._t.join(timeout=1.0)

# ---------------- Simulated SeedLink Client (TESTING ONLY) ----------------
class SimEasySeedLinkClient:
    """
    Simulates a SeedLink client producing synthetic ObsPy Trace objects.
    Useful for testing the bandpass/envelope StationProcessor pipeline.
    """
    def __init__(self, host: str, port: int = 18000, fs: float = CFG.FS,
                 burst_n: int = 206, burst_dt: float = 0.824):
        self.host = host
        self.port = port
        self.fs = fs
        self.burst_n = burst_n
        self.burst_dt = burst_dt
        self.on_data = None
        self._sel = []
        self._stop = False

    def select_stream(self, net: str, sta: str, chan: str):
        self._sel.append((net, sta, chan))

    def run(self):
        if self.on_data is None:
            raise RuntimeError("Assign .on_data before calling run()")
        t0 = UTCDateTime()
        phase = 0.0
        while not self._stop:
            for net, sta, chan in self._sel:
                t = np.arange(self.burst_n) / self.fs
                phase += 2 * np.pi * 0.12 * self.burst_dt
                sig = 3000 * np.sin(2*np.pi*0.12*t + phase) + 500 * np.random.randn(self.burst_n)
                sig = sig.astype(np.int32)
                tr = Trace(sig)
                tr.stats.network = net
                tr.stats.station = sta
                tr.stats.channel = chan
                tr.stats.sampling_rate = self.fs
                tr.stats.starttime = t0
                self.on_data(tr)
                t0 += self.burst_n / self.fs
            time.sleep(self.burst_dt / SPEED_FACTOR)

    def stop(self):
        self._stop = True

if __name__ == "__main__":
    def on_data(trace):
        print(trace)
        print(trace.data[:10])

    c = SimEasySeedLinkClient("127.0.0.1", 18000)
    c.on_data = on_data
    c.select_stream("GG", "WAR27", "HNZ")
    try:
        c.run()
    except KeyboardInterrupt:
        c.stop()
