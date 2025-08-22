"""
Generates synthetic data and streams it as ObsPy Trace objects.
Seedlink Implementation is not yet done but should be here and replaces the synthetic one.
"""

from __future__ import annotations
import threading, time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, List, Optional

import numpy as np
from obspy import Trace, Stream, UTCDateTime
from obspy.clients.seedlink.easyseedlink import EasySeedLinkClient

OnTrace = Callable[[Trace], None]

class IngestBase:
    def start(self): raise NotImplementedError
    def stop(self):  pass

@dataclass(frozen=True)
class Chan:
    net: str; sta: str; loc: str; cha: str
    lat: float; lon: float; freq: float; phase: float; amp: float = 1200.0

# Currently does nothing, but this should be the one for real SeedLink data.
class SeedLinkIngest(IngestBase):
    def __init__(self, server: str, on_trace: OnTrace):
        self.server = server
        self.on_trace = on_trace

# Sets up traces for each station. A trace is what Obspy uses for one continuous time series for one channel from one station.
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
                tr = Trace(
                    data=data,
                    header={
                        "network": ch.net, "station": ch.sta, "location": ch.loc, "channel": ch.cha,
                        "sampling_rate": self.sps, "starttime": ut,
                        "coordinates": {"latitude": ch.lat, "longitude": ch.lon},
                    },
                )
                # This is the Obspy Trace object used to stream data for each station
                self.on_trace(tr)
            now = datetime.now(timezone.utc).timestamp()
            time.sleep(max(0.0, 1.0 - (now - int(now))))

    def start(self):
        if self._t and self._t.is_alive(): return
        self._stop.clear()
        self._t = threading.Thread(target=self._loop, name="SyntheticIngest", daemon=True)
        self._t.start()

    def stop(self):
        self._stop.set()
        if self._t: self._t.join(timeout=1.0)
