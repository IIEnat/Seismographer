"""
ingest_real.py — Thin ObsPy EasySeedLink wrapper.
Exposes RealEasySL with a *uniform* API:
  .select_stream(net, sta, loc, cha)  # falls back to 3-arg if needed
  .run()
Calls .on_data(Trace) for each incoming record.
"""
from __future__ import annotations
from typing import Callable, Optional
from obspy import Trace

try:
    from obspy.clients.seedlink.easyseedlink import EasySeedLinkClient
    _IMPORT_ERR: Optional[Exception] = None
except Exception as e:  # pragma: no cover
    EasySeedLinkClient = None  # type: ignore[assignment]
    _IMPORT_ERR = e

OnTrace = Callable[[Trace], None]

class RealEasySL(EasySeedLinkClient):  # type: ignore[misc]
    def __init__(self, server: str, on_trace: OnTrace):
        if EasySeedLinkClient is None:
            raise RuntimeError(
                "ObsPy SeedLink not available. Install ObsPy with SeedLink support.\n"
                f"Import error: {_IMPORT_ERR!r}"
            )
        super().__init__(server)
        self._on_trace = on_trace

    # Keep a forgiving select_stream signature
    def select_stream(self, net: str, sta: str, *rest: str):
        if len(rest) == 1:
            cha = rest[0]
            loc = ""
        elif len(rest) == 2:
            loc, cha = rest
        else:
            raise TypeError("select_stream expects (net, sta, cha) or (net, sta, loc, cha)")
        try:
            # Newer EasySeedLink supports 4-arg
            return super().select_stream(net, sta, loc, cha)  # type: ignore[arg-type]
        except TypeError:
            # Older signatures may be 3-arg
            return super().select_stream(net, sta, cha)       # type: ignore[arg-type]

    # ObsPy calls this for each Trace
    def on_data(self, trace: Trace):
        self._on_trace(trace)
