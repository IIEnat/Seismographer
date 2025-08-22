"""
Input: Obspy traces
Output: JSON payloads once per second
"""
import threading, json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Tuple, Optional, List
import numpy as np
from flask import Blueprint, jsonify, request
from obspy.core.trace import Trace

@dataclass(frozen=True)
class _WavePkt: iso: str; fs: float; values: List[float]

def _rms(a): 
    a=np.asarray(a, dtype=np.float64); 
    return float(np.sqrt(np.mean(a*a))) if a.size else 0.0

# Takes data from the Obspy Trace objects in ingest.py and turns them into json.
class _Aggregator:
    def __init__(self, metric="rms"):
        self.func = _rms if metric=="rms" else lambda a: float(np.mean(np.asarray(a,dtype=np.float64))) if len(a) else 0.0
        self.cur_key={}; self.cur_fs={}; self.buffers={}; self.last_value={}; self.last_wave={}
        self.lock=threading.Lock()

    @staticmethod
    def _key(tr: Trace): return int(tr.stats.starttime.timestamp)

    def add_trace(self, sid: str, tr: Trace):
        k=self._key(tr); fs=float(tr.stats.sampling_rate or 0.0); arr=np.asarray(tr.data, dtype=np.float64)
        if arr.size==0: return
        with self.lock:
            ok=self.cur_key.get(sid)
            if ok is None or k!=ok:
                if ok is not None:
                    buf=np.asarray(self.buffers.get(sid,[]),dtype=np.float64)
                    iso=datetime.fromtimestamp(ok, tz=timezone.utc).isoformat()
                    val=self.func(buf) if buf.size else 0.0
                    self.last_value[sid]=(iso,float(val))
                    self.last_wave[sid]=_WavePkt(iso=iso, fs=float(self.cur_fs.get(sid,0.0)), values=buf.tolist())
                self.cur_key[sid]=k; self.cur_fs[sid]=fs; self.buffers[sid]=[]
            self.buffers[sid].extend(arr.tolist()); 
            if fs>0: self.cur_fs[sid]=fs

    def snapshot(self, coords: Dict[str,Tuple[float,float]]):
        with self.lock:
            return [{"id":sid,"lat":lat,"lon":lon,"rms":float(self.last_value.get(sid,(None,0.0))[1]),"last":self.last_value.get(sid,(None,0))[0]}
                    for sid,(lat,lon) in coords.items()]

    def latest_wave(self, sid:str)->Optional[_WavePkt]:
        with self.lock:
            pkt=self.last_wave.get(sid)
            if pkt: return pkt
            k=self.cur_key.get(sid); vals=self.buffers.get(sid) or []
            if k is None or not vals: return None
            return _WavePkt(
                iso=datetime.fromtimestamp(k, tz=timezone.utc).isoformat(),
                fs=float(self.cur_fs.get(sid,0.0)),
                values=list(vals),
            )

# Called from app.py
class SLClientReceiver:
    def __init__(self, coords: Dict[str,Tuple[float,float]], metric="rms"):
        self.coords=dict(coords); self.agg=_Aggregator(metric)

    # called by ingest layer
    def on_trace(self, tr: Trace):
        sid=f"{tr.stats.network}.{tr.stats.station}.{tr.stats.location}.{tr.stats.channel}"
        self.agg.add_trace(sid, tr)

    def live_payload(self):
        return {"updated": datetime.now(timezone.utc).isoformat(),"interval_ms":1000,"stations": self.agg.snapshot(self.coords)}

    def wave_payload(self, sid:str):
        pkt=self.agg.latest_wave(sid)
        if not pkt: return None
        sec_key=int(datetime.fromisoformat(pkt.iso).timestamp())
        return {"id":sid,"t0_iso":pkt.iso,"fs":pkt.fs,"values":pkt.values,"sec_key":sec_key}

def create_blueprint(rx: SLClientReceiver) -> Blueprint:
    bp = Blueprint("seis_api", __name__)
    
    @bp.get("/live")
    def live():
        payload = rx.live_payload()
        #print("[LIVE payload]\n" + json.dumps(payload, indent=2, sort_keys=True), flush=True)
        return jsonify(payload)

    @bp.get("/wave")
    def wave():
        sid = request.args.get("id")
        if not sid:
            print("[WAVE] missing id", flush=True)
            return jsonify({"error": "missing id"}), 400
        payload = rx.wave_payload(sid)
        if not payload:
            print(f"[WAVE payload] {sid} -> 404", flush=True)
            return jsonify({"error": "no data yet for id"}), 404
        return jsonify(payload)
    
    # For debugging purposes, dumps the raw data of the /wave
    # Run this in terminal: curl -s http://127.0.0.1:5000/debug/waves | jq .
    # Additionally add ?limit=n where n is the limit of the number of samples returned, default is 10
    @bp.get("/debug/waves")
    def debug_waves():
        try:
            limit = int(request.args.get("limit", "10"))
        except (TypeError, ValueError):
            limit = 10

        out = {}
        for sid in rx.coords.keys():
            pkt = rx.agg.latest_wave(sid)
            if not pkt:
                out[sid] = None
                continue

            vals = pkt.values if isinstance(pkt.values, list) else list(pkt.values)
            ret = vals if limit < 0 else vals[:limit]

            out[sid] = {
                "t0_iso": pkt.iso,
                "fs": pkt.fs,
                "n_total": len(vals),
                "n_returned": len(ret),
                "values": ret,
            }

        return jsonify(out)

    return bp
