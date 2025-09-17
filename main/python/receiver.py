# receiver.py
"""
To see the JSON generated, go to "/api/status" 
"""
from python.ingest import SimEasySeedLinkClient as EasySeedLinkClient
from collections import deque
from threading import Thread, Lock
from dataclasses import dataclass
import numpy as np
from scipy.signal import butter, sosfilt, hilbert, sosfilt_zi
from threading import Thread
import time

from python.location_retrieval import get_location_or_fallback

HOSTS = ["192.168.0.33", "192.168.0.32", "192.168.0.27"]
NET = "GG"
CHAN = "HNZ"
FS = 250.0
BAND = (0.05, 0.10)
QSIZE = 900
TARGET_HZ = 5.0      
DS_FACTOR = int(round(FS / TARGET_HZ)) 

@dataclass
class Queues:
    band: deque
    env: deque 

class StationProcessor:
    def __init__(self, host: str, net: str, sta: str, chan: str, fs: float, band: tuple[float, float], qsize: int):
        self.host, self.net, self.sta, self.chan, self.fs = host, net, sta, chan, fs
        self.lat, self.lon = get_location_or_fallback(host)
        self.q = Queues(band=deque(maxlen=qsize), env=deque(maxlen=qsize))
        low, high = band
        wn = (max(low, 1e-4) / (fs * 0.5), max(high, 2e-4) / (fs * 0.5))
        self.sos = butter(4, wn, btype="bandpass", output="sos", analog=False)
        self.zi = sosfilt_zi(self.sos) * 0.0
        self.lock = Lock()
        self.env_min = None
        self.env_max = None
        self.last_timestamp = None
        self.timestamp = None

        # Downsample state: keep track of where we are modulo the decimation factor
        self.ds_factor = DS_FACTOR         # 50
        self.ds_phase = 0                  # incremented by len(chunk) each burst

    def bandpass_stream(self, x: np.ndarray) -> np.ndarray:
        y, self.zi = sosfilt(self.sos, np.asarray(x, dtype=np.float64), zi=self.zi)
        return y

    def process_chunk(self, trace):
        data = trace.data
        if data.size == 0:
            return

        # 1) Bandpass at 250 Hz
        bp = self.bandpass_stream(data.astype(np.float64))

        # 2) Envelope (Hilbert) at 250 Hz
        env = np.abs(hilbert(bp))

        # 3) Pick only every 50th sample so the queues are ~5 Hz
        N = bp.shape[0]
        start_phase = self.ds_phase % self.ds_factor
        idx = np.arange(start_phase, N, self.ds_factor, dtype=int)  # vectorized picks

        if idx.size > 0:
            bp_ds = bp[idx]
            env_ds = env[idx]

            with self.lock:
                # append downsampled values (round for JSON readability)
                for v in bp_ds:
                    self.q.band.append(float(v))
                for v in env_ds:
                    self.q.env.append(float(v))

                # update window min/max from the current queue (maxlen=900 → cheap)
                if len(self.q.env):
                    arr = np.fromiter(self.q.env, dtype=np.float64)
                    self.env_min = float(arr.min())
                    self.env_max = float(arr.max())
                self.timestamp = str(trace.stats.endtime)
        
        # advance phase by the chunk length so next burst aligns correctly
        self.ds_phase += N

    def snapshot(self) -> dict:
        with self.lock:
            band = [round(v, 3) for v in self.q.band]
            env  = [round(v, 3) for v in self.q.env]
            return {
                "timestamp": self.timestamp, 
                "band_len": len(self.q.band),
                "env_len": len(self.q.env),
                "env_min": self.env_min,
                "env_max": self.env_max,
                "lat": self.lat,   # <— new
                "lon": self.lon,   # <— new
                "band": band,
                "env": env,
            }

    def to_json(self) -> dict:
        return self.snapshot()

def station_code_from_ip(host: str) -> str:
    tail = "".join([c for c in host.split(".")[-1] if c.isdigit()])[-2:]
    return f"WAR{tail.zfill(2)}"

def run_client(proc: StationProcessor):
    def on_data(trace):
        proc.process_chunk(trace)
    c = EasySeedLinkClient(proc.host, 18000)
    c.on_data = on_data
    c.select_stream(proc.net, proc.sta, CHAN)
    c.run()

def make_processors():
    return [StationProcessor(h, NET, station_code_from_ip(h), CHAN, FS, BAND, QSIZE) for h in HOSTS]

def start_processor_thread(proc: StationProcessor) -> Thread:
    t = Thread(target=run_client, args=(proc,), daemon=True)
    t.start()
    return t
