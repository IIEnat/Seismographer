# backend/processor.py
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict
import numpy as np
from obspy import read

def rms_last_window_z(path: Path, window_s: int = 10) -> Dict[str, float]:
    st = read(path.as_posix())
    now = datetime.now(timezone.utc)
    out: Dict[str, float] = {}
    for tr in st:
        if not tr.stats.channel.endswith("Z"):
            continue
        try:
            t_end = tr.stats.endtime.datetime.replace(tzinfo=timezone.utc)
            t_start = max(tr.stats.starttime.datetime.replace(tzinfo=timezone.utc),
                          now - timedelta(seconds=window_s))
            trw = tr.slice(starttime=t_start, endtime=t_end)
            data = trw.data.astype(float)
        except Exception:
            data = tr.data.astype(float)
        if data.size == 0: 
            continue
        rms = float(np.sqrt(np.mean(np.square(data))))
        code = f"{tr.stats.network}.{tr.stats.station}"
        out[code] = rms
    return out
