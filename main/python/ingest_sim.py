"""
ingest_sim.py — SeedLink-like simulator with 5 non-repeating wave textures.
All patterns avoid strict periodicity; 1→5 increases randomness/burstiness.

API:
  SimEasySeedLinkClient(host, port=18000, fs=CFG.FS, burst_n=206, burst_dt=0.824,
                        pattern=CFG.WAVE_PATTERN, rng_seed=None)
    .select_stream(net, sta, cha)  # or (net, sta, loc, cha)
    .run()                         # calls .on_data(Trace) per burst
"""
from __future__ import annotations
import time, math, random
from typing import Callable, List, Tuple, Optional

import numpy as np
from obspy import Trace, UTCDateTime

import config as CFG

OnTrace = Callable[[Trace], None]

def _ar1(n: int, a: float = 0.985, scale: float = 1.0, rng: np.random.Generator | None = None) -> np.ndarray:
    """AR(1) colored noise (red-ish)."""
    g = rng or np.random.default_rng()
    x = np.empty(n, dtype=np.float64)
    e = g.normal(0.0, 1.0, size=n)
    x[0] = e[0] * scale
    for i in range(1, n):
        x[i] = a * x[i-1] + e[i] * math.sqrt(1 - a*a)
    return x * scale

def _gauss_envelope(n: int, center: float, width: float) -> np.ndarray:
    t = np.linspace(0, 1, n, endpoint=False)
    return np.exp(-0.5 * ((t - center) / (width + 1e-6))**2)

class SimEasySeedLinkClient:
    def __init__(
        self,
        host: str,
        port: int = 18000,
        fs: float = CFG.FS,
        burst_n: int = 206,
        burst_dt: float = 0.824,
        pattern: int = getattr(CFG, "WAVE_PATTERN", 3),
        rng_seed: Optional[int] = None,
    ):
        self.host = host
        self.port = port
        self.fs = float(fs)
        self.burst_n = int(burst_n)
        self.burst_dt = float(burst_dt)
        self.pattern = max(1, min(5, int(pattern)))
        self.on_data: Optional[OnTrace] = None
        self._sel: List[Tuple[str, str, str]] = []   # (net, sta, cha)
        self._stop = False

        # persistent state so the signal evolves across bursts
        self._rng = np.random.default_rng(rng_seed)
        self._phase = 2 * math.pi * self._rng.uniform(0, 1)
        self._f_base = 0.10  # ~0.1 Hz center (10 s period) but we will wander
        self._amp = 1200.0
        self._fm_state = 0.0          # slow FM accumulator
        self._am_state = 1.0          # slow AM envelope
        self._brown_phase = 0.0       # for pattern 5
        self._packet_cooldown = 0.0   # for patterns with burst packets

    # Accept (net, sta, cha) or (net, sta, loc, cha); ignore LOC in sim
    def select_stream(self, net: str, sta: str, *rest: str):
        if len(rest) == 1:
            cha = rest[0]
        elif len(rest) == 2:
            _loc, cha = rest
        else:
            raise TypeError("select_stream expects (net, sta, cha) or (net, sta, loc, cha)")
        self._sel.append((net, sta, cha))

    # ------------------ texture cores ------------------

    def _sig_pattern_1(self, n: int) -> np.ndarray:
        """
        Gentle quasi-sine with very slow frequency + amplitude drift.
        Non-repeating due to random-walk FM/AM and phase jitter.
        """
        dt = 1.0 / self.fs
        # slow FM: red noise around ~0.1 Hz base
        fm = _ar1(n, a=0.999, scale=0.002, rng=self._rng)  # ±0.002 Hz wander
        # slow AM: mild envelope changes
        am = 1.0 + _ar1(n, a=0.995, scale=0.05, rng=self._rng)
        # small phase jitter
        pj = self._rng.normal(0.0, 0.002, size=n)

        y = np.empty(n, dtype=np.float64)
        f_inst = self._f_base + fm
        for i in range(n):
            self._phase += 2 * math.pi * (f_inst[i] * dt + pj[i]*dt)
            y[i] = am[i] * math.sin(self._phase)
        # low white tail to de-regularize further
        y += self._rng.normal(0.0, 0.03, size=n)
        return y

    def _sig_pattern_2(self, n: int) -> np.ndarray:
        """
        Quasi-periodic sum of incommensurate components + noise-driven FM.
        """
        dt = 1.0 / self.fs
        # three base freqs (irrational-ish ratios to avoid repetition)
        f1, f2, f3 = 0.07, 0.113, 0.163
        fm = _ar1(n, a=0.998, scale=0.003, rng=self._rng)
        am = 1.0 + _ar1(n, a=0.993, scale=0.08,  rng=self._rng)
        p1 = self._phase
        p2 = self._phase * 0.37 + 1.1
        p3 = self._phase * 0.19 - 0.6
        y = np.empty(n, dtype=np.float64)
        for i in range(n):
            p1 += 2*math.pi*( (self._f_base + fm[i]) * dt )
            p2 += 2*math.pi*( (f2 + 0.3*fm[i]) * dt )
            p3 += 2*math.pi*( (f3 - 0.2*fm[i]) * dt )
            y[i] = am[i] * (0.60*math.sin(p1) + 0.30*math.sin(p2) + 0.15*math.sin(p3))
        y += self._rng.normal(0.0, 0.04, size=n)
        self._phase = p1
        return y

    def _sig_pattern_3(self, n: int) -> np.ndarray:
        """
        Noise-driven instantaneous frequency (FM) with colored envelope (AM).
        Looks like a meandering 'organ pipe' with breathiness.
        """
        dt = 1.0 / self.fs
        fm_noise = _ar1(n, a=0.997, scale=0.006, rng=self._rng)
        am_env   = 1.0 + _ar1(n, a=0.990, scale=0.12,  rng=self._rng)
        y = np.empty(n, dtype=np.float64)
        for i in range(n):
            f = max(0.02, self._f_base + fm_noise[i])   # keep > 0
            self._phase += 2 * math.pi * f * dt
            y[i] = am_env[i] * math.sin(self._phase)
        # add a faint 1/f-ish hiss
        y += _ar1(n, a=0.95, scale=0.02, rng=self._rng)
        return y

    def _sig_pattern_4(self, n: int) -> np.ndarray:
        """
        Random wave packets: Gaussian-windowed cycles at random centers/Q,
        on top of a drifting carrier. Non-repeating packet placement.
        """
        base = self._sig_pattern_1(n) * 0.5
        # 1–3 packets per burst
        k = self._rng.integers(1, 4)
        x = np.linspace(0, 1, n, endpoint=False)
        y = np.zeros(n, dtype=np.float64)
        for _ in range(int(k)):
            center = float(self._rng.uniform(0.1, 0.9))
            width  = float(self._rng.uniform(0.05, 0.18))
            freq   = float(self._rng.uniform(0.07, 0.20))
            phase0 = float(self._rng.uniform(-math.pi, math.pi))
            env    = _gauss_envelope(n, center, width)
            y += env * np.sin(2*math.pi*freq*x*(n/self.fs) + phase0)
        y += base
        y += self._rng.normal(0.0, 0.05, size=n)
        return y

    def _sig_pattern_5(self, n: int) -> np.ndarray:
        """
        Stochastic 'stormy' texture:
        - Brownian phase walk → long-memory drift
        - Poisson bursts of high-Q packets
        - Colored noise bed
        """
        dt = 1.0 / self.fs
        # Brownian phase increment
        dphi = self._rng.normal(0.0, 0.08, size=n)  # random walk
        # slow amplitude wander
        am = 1.0 + _ar1(n, a=0.992, scale=0.18, rng=self._rng)
        y = np.empty(n, dtype=np.float64)
        for i in range(n):
            self._brown_phase += dphi[i]
            y[i] = am[i] * math.sin(self._brown_phase)
        # bursts (Poisson, ~0.7 per burst window on average)
        if self._rng.random() < 0.7:
            center = float(self._rng.uniform(0.15, 0.85))
            width  = float(self._rng.uniform(0.02, 0.08))
            freq   = float(self._rng.uniform(0.10, 0.35))
            qenv   = _gauss_envelope(n, center, width)
            ph0    = float(self._rng.uniform(-math.pi, math.pi))
            x = np.arange(n) * dt
            y += 1.2 * qenv * np.sin(2*math.pi*freq*x + ph0)
        # colored bed
        y += _ar1(n, a=0.97, scale=0.05, rng=self._rng)
        return y

    def _generate(self, n: int) -> np.ndarray:
        if   self.pattern == 1: sig = self._sig_pattern_1(n)
        elif self.pattern == 2: sig = self._sig_pattern_2(n)
        elif self.pattern == 3: sig = self._sig_pattern_3(n)
        elif self.pattern == 4: sig = self._sig_pattern_4(n)
        else:                   sig = self._sig_pattern_5(n)
        # normalize RMS to ~1 then scale to int32-ish seismic counts
        rms = np.sqrt(np.mean(sig*sig)) or 1.0
        return (sig / rms) * (self._amp)

    # ------------------ SeedLink-ish loop ------------------

    def run(self):
        if self.on_data is None:
            raise RuntimeError("Assign .on_data before run()")
        t0 = UTCDateTime()
        while not self._stop:
            for net, sta, cha in self._sel:
                sig = self._generate(self.burst_n).astype(np.int32)
                tr = Trace(sig)
                tr.stats.network = net
                tr.stats.station = sta
                tr.stats.location = ""
                tr.stats.channel = cha
                tr.stats.sampling_rate = self.fs
                tr.stats.starttime = t0
                self.on_data(tr)
                t0 += self.burst_n / self.fs
            # wall-time pacing (supports SPEED_FACTOR > 1)
            sleep = self.burst_dt / (CFG.SPEED_FACTOR if CFG.SPEED_FACTOR > 0 else 1.0)
            time.sleep(sleep)

    def stop(self):
        self._stop = True
