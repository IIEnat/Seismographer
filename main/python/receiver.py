# --- START OF python/receiver.py ---
"""
receiver.py — 30 s buffered start, then drip at 5 Hz.
Seam is smoothed exactly once per block boundary using look-ahead into the next
block head; no periodic re-patching (prevents saw-tooth artifacts).

All tunables are static in config.py.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from threading import Lock, Thread
from typing import List, Optional, Tuple

import numpy as np
from obspy.core.trace import Trace
from scipy import signal
from scipy.interpolate import PchipInterpolator

import config as CFG
from python.ingest import SimEasySeedLinkClient


# ---------------------------- Data classes ------------------------------
@dataclass
class Queues:
    band: deque[float]
    env: deque[float]


# --------------------------- Core processor -----------------------------
class StationProcessor:
    """
    Startup
      • Buffer BATCH_SECONDS of native samples (strict).
      • Compute 5 Hz band-pass and 5 Hz envelope for that block.
      • Then ready=True and we start dripping at TARGET_HZ.

    Streaming
      • For each completed block, drip its precomputed 5 Hz series.
      • At each block boundary, smooth the seam once using prev tail + next head.
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
    ) -> None:
        self.host, self.net, self.sta, self.chan, self.fs = host, net, sta, chan, float(fs)

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

    def _downsample_to_5hz(self, segment: np.ndarray, duration_s: float) -> np.ndarray:
        m = int(round(max(0.0, duration_s) * CFG.TARGET_HZ))
        if m <= 1 or segment.size == 0:
            return np.empty(0, dtype=float)
        idx = np.linspace(0, segment.size - 1, m, endpoint=True)
        idx = np.clip(np.round(idx).astype(int), 0, segment.size - 1)
        return segment[idx].astype(float)

    def _env_from_segment(self, seg_abs: np.ndarray, duration_s: float) -> np.ndarray:
        n = seg_abs.size
        if n == 0 or duration_s <= 0:
            return np.empty(0, dtype=float)

        # Peak anchors + PCHIP (causal-friendly, smooth, no ringing)
        min_dist = max(1, int(round(self.fs * CFG.MIN_PEAK_DIST_SEC)))
        prom = 0.05 * (float(seg_abs.max()) - float(seg_abs.min()) + 1e-9)
        pk_idx, _ = signal.find_peaks(seg_abs, distance=min_dist, prominence=prom)

        # Ensure endpoints are included
        if pk_idx.size == 0 or pk_idx[0] != 0:
            pk_idx = np.insert(pk_idx, 0, 0)
        if pk_idx[-1] != (n - 1):
            pk_idx = np.append(pk_idx, n - 1)

        pk_t = pk_idx / self.fs
        pk_val = seg_abs[pk_idx].astype(float)
        interp = PchipInterpolator(pk_t, pk_val, extrapolate=True)

        t_env = np.arange(0.0, duration_s, 1.0 / CFG.TARGET_HZ)
        t_max = (n - 1) / self.fs
        env = interp(np.clip(t_env, 0.0, t_max))
        return np.maximum(env, 0.0).astype(float)

    def _env_from_block(self, block_abs: np.ndarray) -> np.ndarray:
        return self._env_from_segment(block_abs, CFG.BATCH_SECONDS)

    # ---- one-time seam fix at block boundary ----
    def _patch_seam_once(self, cur_block: np.ndarray, env5_cur: np.ndarray) -> np.ndarray:
        """
        Recompute envelope over [prev_tail | cur_head] and patch:
          • tail of already-published q.env
          • head of env5_cur (before we queue it)
        Returns possibly modified env5_cur.
        """
        if self._last_block is None or self._seam_tail_n <= 0 or self._seam_tail_pts <= 0:
            return env5_cur

        tail_n = min(self._seam_tail_n, self._last_block.size)
        head_n = min(self._seam_tail_n, cur_block.size)
        if tail_n == 0 or head_n == 0:
            return env5_cur

        prev_tail = self._last_block[-tail_n:]
        next_head = cur_block[:head_n]
        combo = np.concatenate([prev_tail, next_head], axis=0)
        duration = combo.size / self.fs

        env_combo = self._env_from_segment(np.abs(combo), duration)
        if env_combo.size == 0:
            return env5_cur

        # split combo env into tail/head (in 5 Hz domain)
        tail_pts = min(self._seam_tail_pts, env_combo.size)
        head_pts = min(self._seam_tail_pts, max(0, env_combo.size - tail_pts))
        prev_tail_5 = env_combo[:tail_pts]
        next_head_5 = env_combo[tail_pts:tail_pts + head_pts]

        with self._lock:
            # patch the tail of already-published env (if any)
            if self.q.env and prev_tail_5.size:
                qe = list(self.q.env)
                k = min(len(qe), prev_tail_5.size)
                qe[-k:] = prev_tail_5[-k:].tolist()
                self.q.env.clear()
                self.q.env.extend(qe)

            # patch head of the just-built block series (before queuing)
            if next_head_5.size and env5_cur.size:
                k2 = min(env5_cur.size, next_head_5.size)
                env5_cur[:k2] = next_head_5[:k2]

            # refresh stats + epoch
            if self.q.env:
                arr = np.fromiter(self.q.env, dtype=np.float64)
                self.env_min = float(arr.min())
                self.env_max = float(arr.max())
            self._patch_epoch += 1

        return env5_cur

    # ---- main streaming method ----
    def process_chunk(self, trace: Trace) -> None:
        x = np.asarray(trace.data, dtype=np.float64)
        if x.size == 0:
            return

        # keep raw
        self._raw.extend(map(float, x))

        # native band-pass
        bp = self._bandpass(x)

        # accumulate into block
        self._block_hist.extend(bp.tolist())
        self._samples_in_block += bp.size

        # on full block: compute series, patch seam once, then queue
        if self._samples_in_block >= self._block_n and len(self._block_hist) == self._block_n:
            block = np.asarray(self._block_hist, dtype=np.float64)

            band_5hz = self._downsample_to_5hz(block, CFG.BATCH_SECONDS)
            env_5hz = self._env_from_block(np.abs(block))

            # patch once at seam with previous block
            env_5hz = self._patch_seam_once(block, env_5hz)

            # queue for dripping
            self._band_ready.extend(map(float, band_5hz))
            self._env_ready.extend(map(float, env_5hz))

            # ready after first block
            self._ready = True

            # keep as "previous" for next seam
            self._last_block = block

            # start new block (non-overlapping)
            self._samples_in_block = 0
            self._block_hist.clear()

        # drip if ready
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
                        self.env_min = float(arr.min())
                        self.env_max = float(arr.max())

        # timestamp for UI
        self.timestamp = trace.stats.endtime.isoformat()

    # ---- JSON for the UI sender ----
    def to_json(self) -> dict:
        with self._lock:
            return {
                "ready": self._ready,
                "startup_seconds": CFG.BATCH_SECONDS,
                "timestamp": self.timestamp,
                "band_len": len(self.q.band),
                "env_len": len(self.q.env),
                "env_min": self.env_min,
                "env_max": self.env_max,
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

    c = SimEasySeedLinkClient(proc.host, 18000, fs=CFG.FS)
    c.on_data = on_data
    c.select_stream(proc.net, proc.sta, CFG.CHAN)
    c.run()  # blocking; run in a daemon thread


def make_processors(hosts: Optional[List[str]] = None) -> List[StationProcessor]:
    hs = hosts or CFG.HOSTS
    return [StationProcessor(h, CFG.NET, station_code_from_ip(h), CFG.CHAN) for h in hs]


def start_processor_thread(proc: StationProcessor) -> Thread:
    t = Thread(target=_run_client, args=(proc,), daemon=True)
    t.start()
    return t
# --- END OF python/receiver.py ---
