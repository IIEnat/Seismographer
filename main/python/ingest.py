from __future__ import annotations
"""
@file ingest.py
@brief Ingest layer for the Seismographer project.

@details
Provides multiple ingestion backends to feed seismic data into the processing
pipeline. All ingest paths push data via a user-provided callback function
`on_trace(Trace)`.

Supported ingest classes:
- SyntheticIngest: generates synthetic sine wave bursts with noise.
- SeedLinkIngest: placeholder for future real SeedLink client integration.
- SimEasySeedLinkClient: simulation-only SeedLink client for testing.

Each ingest source ultimately produces ObsPy `Trace` objects.
"""

import threading, time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, List, Optional

import numpy as np
from obspy import Trace, UTCDateTime

import config as CFG

try:
    # ObsPy SeedLink client (optional, may not be present in dev environments)
    from obspy.clients.seedlink.easyseedlink import EasySeedLinkClient  # noqa: F401
except Exception:
    EasySeedLinkClient = None  # keep import optional to allow dev environments to run

# ------------------------------------------------------------------------
# Types
# ------------------------------------------------------------------------

# Type alias for ingest callback
OnTrace = Callable[[Trace], None]

# Global speed factor (mirrors CFG.SPEED_FACTOR for simulation)
SPEED_FACTOR = CFG.SPEED_FACTOR

# ------------------------------------------------------------------------
# Base Classes
# ------------------------------------------------------------------------

class IngestBase:
    """
    @brief Abstract base class for all ingest sources.

    @details
    Each subclass must implement a `start()` method that begins ingesting
    and pushing ObsPy `Trace` objects to the provided callback.
    """
    def start(self): raise NotImplementedError
    def stop(self):  pass

@dataclass(frozen=True)
class Chan:
    """
    @brief Metadata class describing a single synthetic channel.
    @param net Network code.
    @param sta Station code.
    @param loc Location identifier.
    @param cha Channel code.
    @param lat Latitude of station.
    @param lon Longitude of station.
    @param freq Frequency of synthetic signal (Hz).
    @param phase Initial phase of signal (radians).
    @param amp Amplitude scaling factor for synthetic data (default=1200).
    """
    net: str; sta: str; loc: str; cha: str
    lat: float; lon: float; freq: float; phase: float; amp: float = 1200.0

# ------------------------------------------------------------------------
# Real SeedLink Stub
# ------------------------------------------------------------------------

class SeedLinkIngest(IngestBase):
    """
    @brief Placeholder for a real SeedLink ingest implementation.

    @details
    Intended to connect to a SeedLink server, subscribe to streams,
    and emit ObsPy `Trace` objects to the callback.
    """
    def __init__(self, server: str, on_trace: OnTrace):
        self.server = server
        self.on_trace = on_trace
        self._t: Optional[threading.Thread] = None
        self._stop = threading.Event()

    def start(self):
        # Start ingest (not implemented yet).
        raise NotImplementedError("SeedLinkIngest not yet implemented")

    def stop(self):
        # Stop ingest and join thread if running.
        self._stop.set()
        if self._t: self._t.join(timeout=1.0)

# ------------------------------------------------------------------------
# Synthetic Generator (1 Hz bursts)
# ------------------------------------------------------------------------

class SyntheticIngest(IngestBase):
    """
    @brief Synthetic sine-wave ingest generator.

    @details
    Produces ObsPy `Trace` objects containing sine signals + Gaussian noise
    for each channel. Runs in its own thread and emits data once per second.
    """
    def __init__(self, chans: List[Chan], sps: float, on_trace: OnTrace):
        self.chans = list(chans)       # list of Chan metadata
        self.sps = float(sps)          # samples per second
        self.on_trace = on_trace
        self._stop = threading.Event()
        self._t: Optional[threading.Thread] = None

    def _loop(self):
        # Internal loop: generate synthetic waveforms and push via callback.
        n = int(self.sps) # number of samples per burst (1 second of data)
        while not self._stop.is_set():
            t0 = datetime.now(timezone.utc)
            ut = UTCDateTime(t0)
            t = np.linspace(0, 1, n, endpoint=False)

            for ch in self.chans:
                # Generate sine wave + random noise
                w = np.sin(2*np.pi*(ch.freq*t + ch.phase)) + 0.15*np.random.randn(n)
                data = (w * ch.amp).astype(np.int32)

                # Build ObsPy Trace with metadata
                tr = Trace(data=data)
                tr.stats.network = ch.net
                tr.stats.station = ch.sta
                tr.stats.location = ch.loc
                tr.stats.channel = ch.cha
                tr.stats.sampling_rate = self.sps
                tr.stats.starttime = ut
                tr.stats.coordinates = {"latitude": ch.lat, "longitude": ch.lon}

                self.on_trace(tr) # push trace to callback

            # Pace to ~1 Hz loop (scaled by SPEED_FACTOR)
            now = datetime.now(timezone.utc).timestamp()
            sleep = max(0.0, 1.0 - (now - int(now)))
            time.sleep(sleep / SPEED_FACTOR)

    def start(self):
        # Start synthetic data generation in a background thread.
        if self._t and self._t.is_alive(): return
        self._stop.clear()
        self._t = threading.Thread(target=self._loop, name="SyntheticIngest", daemon=True)
        self._t.start()

    def stop(self):
        # Stop generation and join the background thread.
        self._stop.set()
        if self._t: self._t.join(timeout=1.0)

# ------------------------------------------------------------------------
# Simulated SeedLink Client (Testing Only)
# ------------------------------------------------------------------------

class SimEasySeedLinkClient:
    """
    @brief Simulation-only SeedLink client (testing pipeline integration).

    @details
    Mimics the ObsPy `EasySeedLinkClient` but produces synthetic traces.
    Useful for testing band-pass and envelope processing without a real server.
    """
    def __init__(self, host: str, port: int = 18000, fs: float = CFG.FS,
                 burst_n: int = 206, burst_dt: float = 0.824):
        self.host = host
        self.port = port
        self.fs = fs
        self.burst_n = burst_n      # number of samples per burst
        self.burst_dt = burst_dt    # spacing between bursts (seconds)
        self.on_data = None         # callback (must be set before run)
        self._sel = []              # list of subscribed streams
        self._stop = False

    def select_stream(self, net: str, sta: str, chan: str):
        # Register a (net, sta, chan) stream to simulate.
        self._sel.append((net, sta, chan))

    def run(self):
        """
        @brief Run the simulation loop.

        @details
        For each selected stream, generates sine + noise bursts and pushes ObsPy
        `Trace` objects to `self.on_data`. Runs until stopped.
        """
        if self.on_data is None:
            raise RuntimeError("Assign .on_data before calling run()")
        
        t0 = UTCDateTime()
        phase = 0.0
        while not self._stop:
            for net, sta, chan in self._sel:
                t = np.arange(self.burst_n) / self.fs
                phase += 2 * np.pi * 0.12 * self.burst_dt

                # synthetic sine + noise burst
                sig = 3000 * np.sin(2*np.pi*0.12*t + phase) + 500 * np.random.randn(self.burst_n)
                sig = sig.astype(np.int32)

                tr = Trace(sig)
                tr.stats.network = net
                tr.stats.station = sta
                tr.stats.channel = chan
                tr.stats.sampling_rate = self.fs
                tr.stats.starttime = t0

                self.on_data(tr)                # push trace to callback
                t0 += self.burst_n / self.fs    # advance time
            time.sleep(self.burst_dt / SPEED_FACTOR)

    def stop(self):
        # Stop the simulation loop.
        self._stop = True

# ------------------------------------------------------------------------
# Standalone test harness
# ------------------------------------------------------------------------

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
