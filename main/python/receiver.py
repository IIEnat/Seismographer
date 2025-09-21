"""
receiver.py  —  Band-pass + Envelope live processing (no RMS polling)

What this provides
------------------
• StationProcessor
    - 4th-order Butterworth band-pass (0.05–0.10 Hz) @ native fs (default 250 Hz)
    - Hilbert envelope
    - Downsample to ~5 Hz for UI (band + env queues)
    - Small rolling RAW buffer @ native fs for diagnostics (/raw)

• Helpers
    - station_code_from_ip(host)   -> "WAR##"
    - make_processors(hosts=None)  -> list[StationProcessor]
    - start_processor_thread(proc) -> Thread (runs simulated client)

This module is framework-agnostic: no Flask globals. Your app should:
    - call p.to_json() in a Socket.IO background task and emit "station_update"
    - call p.latest_raw() in your /raw route
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from threading import Lock, Thread
from typing import List, Optional, Tuple

import numpy as np
from obspy.core.trace import Trace
from scipy.signal import butter, sosfilt, hilbert, sosfilt_zi

# Simulated SeedLink client for local testing.
# Swap out in production while keeping the same on_data(trace) callback.
from python.ingest import SimEasySeedLinkClient


# ----------------------------- Tunables ---------------------------------

HOSTS       = ["192.168.0.33", "192.168.0.32", "192.168.0.27"]
NET         = "GG"
CHAN        = "HNZ"
FS          = 250.0                   # native sampling rate
BAND        = (0.05, 0.10)            # 20-second band
TARGET_HZ   = 5.0                     # downsampled UI rate
QSIZE       = 900                     # ~3 min @ 5 Hz
RAW_SECONDS = 3                       # keep ~3 s of native RAW for /raw


# ---------------------------- Data classes ------------------------------

@dataclass
class Queues:
    band: deque[float]
    env:  deque[float]


# --------------------------- Core processor -----------------------------

class StationProcessor:
    """
    Consume streaming ObsPy Trace bursts:
      1) band-pass @ native fs
      2) envelope (Hilbert)
      3) downsample to ~5 Hz (phase-aware slice)
      4) keep a small RAW buffer for /raw

    Thread-safe for snapshot via self._lock.
    """

    def __init__(
        self,
        host: str,
        net: str,
        sta: str,
        chan: str,
        fs: float = FS,
        band: Tuple[float, float] = BAND,
        qsize: int = QSIZE,
        raw_seconds: int = RAW_SECONDS,
    ) -> None:
        self.host, self.net, self.sta, self.chan, self.fs = host, net, sta, chan, float(fs)

        # UI series (~5 Hz) and RAW ring buffer (native fs)
        self.q    = Queues(band=deque(maxlen=qsize), env=deque(maxlen=qsize))
        self._raw = deque(maxlen=int(max(1.0, self.fs) * raw_seconds))

        # Band-pass design (4th-order Butterworth)
        lo, hi = band
        wn = (max(lo, 1e-4) / (self.fs * 0.5), max(hi, 2e-4) / (self.fs * 0.5))
        self._sos = butter(4, wn, btype="bandpass", output="sos", analog=False)
        self._zi  = sosfilt_zi(self._sos) * 0.0

        # Downsample state
        self._ds_factor = int(round(self.fs / TARGET_HZ))  # ≈50 @ 250 Hz
        self._ds_phase  = 0

        # Stats / sync
        self._lock = Lock()
        self.env_min: Optional[float] = None
        self.env_max: Optional[float] = None
        self.timestamp: Optional[str] = None  # ISO of latest burst end

    def _bandpass(self, x: np.ndarray) -> np.ndarray:
        y, self._zi = sosfilt(self._sos, np.asarray(x, dtype=np.float64), zi=self._zi)
        return y

    def process_chunk(self, trace: Trace) -> None:
        """Consume one ObsPy Trace burst (native fs)."""
        data = np.asarray(trace.data, dtype=np.float64)
        if data.size == 0:
            return

        # Keep RAW buffer (native fs)
        self._raw.extend(map(float, data))

        # Band-pass and envelope
        bp  = self._bandpass(data)
        env = np.abs(hilbert(bp))

        # Downsample via phase-aware slice
        N = bp.shape[0]
        start = int(self._ds_phase % self._ds_factor)
        sl = slice(start, None, self._ds_factor)
        bp_ds, env_ds = bp[sl], env[sl]

        if bp_ds.size:
            with self._lock:
                self.q.band.extend(float(v) for v in bp_ds)
                self.q.env.extend(float(v) for v in env_ds)

                if self.q.env:
                    arr = np.fromiter(self.q.env, dtype=np.float64)
                    self.env_min = float(arr.min())
                    self.env_max = float(arr.max())

                self.timestamp = trace.stats.endtime.isoformat()

        self._ds_phase += N

    # ---- snapshots ----

    def to_json(self) -> dict:
        """Thread-safe snapshot for Socket.IO 'station_update' payloads."""
        with self._lock:
            return {
                "timestamp": self.timestamp,
                "band_len": len(self.q.band),
                "env_len":  len(self.q.env),
                "env_min":  self.env_min,
                "env_max":  self.env_max,
                "band":     [round(v, 3) for v in self.q.band],
                "env":      [round(v, 3) for v in self.q.env],
            }

    def latest_raw(self) -> Optional[dict]:
        """Return latest RAW buffer at native fs for the /raw API."""
        with self._lock:
            vals = list(self._raw)
            if not vals:
                return None
            return {"t0_iso": self.timestamp, "fs": float(self.fs), "values": vals}


# ----------------------------- Client glue ------------------------------

def station_code_from_ip(host: str) -> str:
    """Turn '192.168.0.33' → 'WAR33' for demo station IDs."""
    tail = "".join([c for c in host.split(".")[-1] if c.isdigit()])[-2:]
    return f"WAR{tail.zfill(2)}"


def _run_client(proc: StationProcessor) -> None:
    """Drive a (simulated) SeedLink client that calls proc.process_chunk(trace)."""
    def on_data(trace: Trace) -> None:
        proc.process_chunk(trace)

    c = SimEasySeedLinkClient(proc.host, 18000, fs=FS)
    c.on_data = on_data
    c.select_stream(proc.net, proc.sta, CHAN)
    c.run()  # blocking; run in a daemon thread


def make_processors(hosts: Optional[List[str]] = None) -> List[StationProcessor]:
    """Create one StationProcessor per host."""
    hs = hosts or HOSTS
    return [StationProcessor(h, NET, station_code_from_ip(h), CHAN) for h in hs]


def start_processor_thread(proc: StationProcessor) -> Thread:
    """Start a background thread for a single processor's client loop."""
    t = Thread(target=_run_client, args=(proc,), daemon=True)
    t.start()
    return t
