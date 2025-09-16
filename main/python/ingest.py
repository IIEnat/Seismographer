"""
This file is only used to simulate the seedlink client.
Meant for TESTING ONLY.
Generates synthetic ObsPy Trace objects that should look exactly like the real thing.
"""

import time
import numpy as np
from obspy import Trace, UTCDateTime

class SimEasySeedLinkClient:
    def __init__(self, host: str, port: int = 18000, fs: float = 250.0, burst_n: int = 206, burst_dt: float = 0.824):
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
                # synthetic signal: low-freq sine (~0.12 Hz) + noise
                t = np.arange(self.burst_n) / self.fs
                phase += 2 * np.pi * 0.12 * self.burst_dt
                sig = 3000 * np.sin(2 * np.pi * 0.12 * t + phase) + 500 * np.random.randn(self.burst_n)
                sig = sig.astype(np.int32)
                tr = Trace(sig)
                tr.stats.network = net
                tr.stats.station = sta
                tr.stats.channel = chan
                tr.stats.sampling_rate = self.fs
                tr.stats.starttime = t0
                self.on_data(tr)
                t0 += self.burst_n / self.fs
            time.sleep(self.burst_dt)
    def stop(self):
        self._stop = True

# This is the exact same output as the actual seedlink server. To see it run this file directly from the terminal.
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