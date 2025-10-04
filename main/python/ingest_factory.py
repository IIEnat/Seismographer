"""
ingest_factory.py — Returns the correct client object for SIMULATE vs REAL.
Both clients expose:
  .select_stream(...)
  .run()
and will call on_trace(Trace) for each new chunk.
"""
from __future__ import annotations
from typing import Callable
from obspy import Trace
import config as CFG

OnTrace = Callable[[Trace], None]

def make_client(on_trace: OnTrace, *, fs: float):
    if CFG.SIMULATE:
        from .ingest_sim import SimEasySeedLinkClient
        c = SimEasySeedLinkClient("127.0.0.1", 18000, fs=fs)
        c.on_data = on_trace
        return c
    else:
        from .ingest_real import RealEasySL
        return RealEasySL(CFG.SEEDLINK_SERVER, on_trace)
