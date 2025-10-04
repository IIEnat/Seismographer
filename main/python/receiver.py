# --- START OF python/receiver.py ---
"""
receiver.py — 30 s buffered start, then drip at 5 Hz.
Seam is smoothed exactly once per block boundary using prev tail + next head.

This version is ingest-agnostic:
- Uses ingest_factory.make_client() to pick SIM vs REAL.
- StationProcessor unchanged in DSP; accepts optional lat/lon overrides.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from threading import Lock, Thread
from typing import List, Optional, Tuple
from math import gcd

import numpy as np
from obspy.core.trace import Trace
from scipy import signal

import config as CFG
from .ingest_factory import make_client
from .location_retrieval import get_location_or_fallback

# ---------------------------- Data classes ------------------------------
@dataclass
class Queues:
    band: deque[float]
    env: deque[float]

# --------------------------- Core processor -----------------------------
class StationProcessor:
    """
    Startup
      • Buffer BATCH_SECONDS native samples.
      • Compute 5 Hz band-pass & 5 Hz envelope for that block.
      • Then ready=True and we start dripping at TARGET_HZ.
    Streaming
      • For each completed block, drip precomputed 5 Hz series.
      • Patch envelope seam exactly once at each block boundary.
    """
    def __init__(
        self,
        host: str,
        net: str,
        sta: str,
        chan: str,
        fs: float = CFG.FS,
        band: Tuple[float, float] = CFG.BAND,
        qsize: int = CFG.QSIZE,
        raw_seconds: int = CFG.RAW_SECONDS,
        lat: float | None = None,
        lon: float | None = None,
    ) -> None:
        self.host, self.net, self.sta, self.chan, self.fs = host, net, sta, chan, float(fs)

        # Coordinates: prefer explicit override; otherwise SOH; finally (0,0)
        if lat is not None and lon is not None:
            self.lat, self.lon = float(lat), float(lon)
        else:
            try:
                self.lat, self.lon = get_location_or_fallback(self.host, timeout=0.4)
            except Exception:
                self.lat, self.lon = 0.0, 0.0

        # UI queues (~5 Hz)
        self.q = Queues(band=deque(maxlen=qsize), env=deque(maxlen=qsize))

        # RAW ring buffer (native fs) for diagnostics/export
        self._raw = deque(maxlen=int(max(1.0, self.fs) * raw_seconds))

        # Band-pass (4th-order Butterworth)
        lo, hi = band
        wn = (max(lo, 1e-4) / (self.fs * 0.5), max(hi, 2e-4) / (self.fs * 0.5))
        self._sos = signal.butter(4, wn, btype="bandpass", output="sos")
        self._zi = signal.sosfilt_zi(self._sos) * 0.0

        # Block state (native fs)
        self._block_n = int(round(self.fs * CFG.BATCH_SECONDS))
        self._block_hist = deque(maxlen=self._block_n)
        self._samples_in_block = 0

        # Pending 5 Hz series to drip
        self._band_ready = deque()
        self._env_ready = deque()

        # Keep previous completed block (native) for seam fix
        self._last_block: Optional[np.ndarray] = None

        # Seam params (native samples / 5 Hz points)
        self._seam_tail_n = int(round(CFG.PATCH_TAIL_SECONDS * self.fs))
        self._seam_tail_pts = int(round(CFG.PATCH_TAIL_SECONDS * CFG.TARGET_HZ))

        # Status
        self._ready = False
        self._patch_epoch = 0
        self._lock = Lock()
        self.env_min: Optional[float] = None
        self.env_max: Optional[float] = None
        self.timestamp: Optional[str] = None

    # ---- DSP helpers ----
    def _bandpass(self, x: np.ndarray) -> np.ndarray:
        y, self._zi = signal.sosfilt(self._sos, np.asarray(x, dtype=np.float64), zi=self._zi)
        return y

    def _decimate_to_5hz(self, x: np.ndarray) -> np.ndarray:
        if x.size == 0:
            return np.empty(0, dtype=float)
        fs = int(round(self.fs))
        tgt = int(round(CFG.TARGET_HZ))
        if fs % tgt == 0 and fs > tgt:
            q = fs // tgt  # e.g., 250 -> 5 => q=50
            return signal.decimate(x.astype(np.float64), q, ftype="iir", zero_phase=True).astype(float)
        up, down = tgt, fs
        g = gcd(up, down) if down != 0 else 1
        up //= max(g, 1); down //= max(g, 1)
        return signal.resample_poly(x.astype(np.float64), up, down).astype(float)

    def _env_native(self, band_native: np.ndarray) -> np.ndarray:
        if band_native.size == 0:
            return np.empty(0, dtype=float)
        env = np.abs(signal.hilbert(band_native.astype(np.float64)))
        nyq = max(1e-6, 0.5 * self.fs)
        wc = min(0.3 / nyq, 0.99)  # normalized cutoff
        sos = signal.butter(2, wc, btype="low", output="sos")
        env = signal.sosfiltfilt(sos, env)
        return np.maximum(env, 0.0).astype(float)

    def _env_5hz_from_block(self, band_native_block: np.ndarray) -> np.ndarray:
        env_native = self._env_native(band_native_block)
        return self._decimate_to_5hz(env_native)

    def _patch_seam_once(self, cur_block: np.ndarray, env5_cur: np.ndarray) -> np.ndarray:
        if self._last_block is None or self._seam_tail_n <= 0 or self._seam_tail_pts <= 0:
            return env5_cur

        tail_n = min(self._seam_tail_n, self._last_block.size)
        head_n = min(self._seam_tail_n, cur_block.size)
        if tail_n == 0 or head_n == 0:
            return env5_cur

        prev_tail = self._last_block[-tail_n:]
        next_head = cur_block[:head_n]
        combo = np.concatenate([prev_tail, next_head], axis=0)

        env_combo_5 = self._decimate_to_5hz(self._env_native(combo))
        if env_combo_5.size == 0:
            return env5_cur

        tail_pts = min(self._seam_tail_pts, env_combo_5.size)
        head_pts = min(self._seam_tail_pts, max(0, env_combo_5.size - tail_pts))
        prev_tail_5 = env_combo_5[:tail_pts]
        next_head_5 = env_combo_5[tail_pts:tail_pts + head_pts]

        with self._lock:
            if self.q.env and prev_tail_5.size:
                qe = list(self.q.env)
                k = min(len(qe), prev_tail_5.size)
                qe[-k:] = prev_tail_5[-k:].tolist()
                self.q.env.clear(); self.q.env.extend(qe)

            if next_head_5.size and env5_cur.size:
                k2 = min(env5_cur.size, next_head_5.size)
                env5_cur[:k2] = next_head_5[:k2]

            if self.q.env:
                arr = np.fromiter(self.q.env, dtype=np.float64)
                self.env_min = float(arr.min()); self.env_max = float(arr.max())
            self._patch_epoch += 1

        return env5_cur

    def process_chunk(self, trace: Trace) -> None:
        x = np.asarray(trace.data, dtype=np.float64)
        if x.size == 0:
            return

        self._raw.extend(map(float, x))
        bp = self._bandpass(x)

        self._block_hist.extend(bp.tolist())
        self._samples_in_block += bp.size

        if self._samples_in_block >= self._block_n and len(self._block_hist) == self._block_n:
            block = np.asarray(self._block_hist, dtype=np.float64)
            band_5hz = self._decimate_to_5hz(block)
            env_5hz  = self._env_5hz_from_block(block)
            n = min(band_5hz.size, env_5hz.size)
            if n > 0:
                band_5hz = band_5hz[:n]
                env_5hz  = env_5hz[:n]

            env_5hz = self._patch_seam_once(block, env_5hz)
            self._band_ready.extend(map(float, band_5hz))
            self._env_ready .extend(map(float, env_5hz))

            self._ready = True
            self._last_block = block
            self._samples_in_block = 0
            self._block_hist.clear()

        if self._ready:
            burst_seconds = x.size / self.fs
            k = int(round(CFG.TARGET_HZ * burst_seconds))
            band_out, env_out = [], []
            for _ in range(k):
                if not self._band_ready or not self._env_ready:
                    break
                band_out.append(self._band_ready.popleft())
                env_out.append(self._env_ready.popleft())

            if band_out or env_out:
                with self._lock:
                    if band_out: self.q.band.extend(band_out)
                    if env_out:  self.q.env.extend(env_out)
                    if self.q.env:
                        arr = np.fromiter(self.q.env, dtype=np.float64)
                        self.env_min = float(arr.min()); self.env_max = float(arr.max())

        self.timestamp = trace.stats.endtime.isoformat()

    def to_json(self) -> dict:
        with self._lock:
            return {
                "ready": self._ready,
                "timestamp": self.timestamp,
                "band_len": len(self.q.band),
                "env_len": len(self.q.env),
                "env_min": self.env_min,
                "env_max": self.env_max,
                "lat": self.lat,
                "lon": self.lon,
                "band": [round(v, 3) for v in self.q.band],
                "env":  [round(v, 3) for v in self.q.env],
                "patch_epoch": self._patch_epoch,
            }

    def latest_raw(self) -> Optional[dict]:
        with self._lock:
            vals = list(self._raw)
            if not vals:
                return None
            return {"t0_iso": self.timestamp, "fs": float(self.fs), "values": vals}

# ----------------------------- Client glue ------------------------------
def station_code_from_ip(host: str) -> str:
    tail = "".join([c for c in host.split(".")[-1] if c.isdigit()])[-2:]
    return f"WAR{tail.zfill(2)}"

def _run_client(proc: StationProcessor) -> None:
    def on_data(trace: Trace) -> None:
        proc.process_chunk(trace)

    c = make_client(on_data, fs=CFG.FS)

    if CFG.SIMULATE:
        # One logical stream per processor, station code derived from IP
        c.select_stream(proc.net, proc.sta, CFG.CHAN)
    else:
        # Subscribe to all configured real streams at once
        # (The processors list still controls how many StationProcessor instances you run)
        for tup in CFG.SEEDLINK_STREAMS:
            net, sta, loc, cha = (tup + ("", "", ""))[:4]
            c.select_stream(net, sta, loc, cha)

    c.run()  # blocking; runs inside a daemon thread

def make_processors(hosts: Optional[List[str]] = None) -> List[StationProcessor]:
    if CFG.SIMULATE:
        hs = hosts or CFG.HOSTS
        return [StationProcessor(h, CFG.NET, station_code_from_ip(h), CFG.CHAN) for h in hs]
    else:
        procs: List[StationProcessor] = []
        for tup in CFG.SEEDLINK_STREAMS:
            net, sta, loc, cha = tup[:4]
            lat = tup[4] if len(tup) > 4 else None
            lon = tup[5] if len(tup) > 5 else None
            # Use server host (without port) purely for potential SOH fallback if lat/lon missing
            host_only = CFG.SEEDLINK_SERVER.split(":", 1)[0]
            procs.append(StationProcessor(host_only, net, sta, cha, lat=lat, lon=lon))
        return procs

def start_processor_thread(proc: StationProcessor) -> Thread:
    t = Thread(target=_run_client, args=(proc,), daemon=True)
    t.start()
    return t
# --- END OF python/receiver.py ---
