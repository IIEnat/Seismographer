#!/usr/bin/env python3
"""
location_retrieval.py

Retrieve 'instrument/earthLocation' from a seismometer's SOH endpoint.

Public functions:
    - get_raw_earthlocation(host) -> dict | None
    - get_location(host) -> (lat, lon) | None
    - get_location_or_fallback(host, fallback=None) -> (lat, lon) | None

CLI examples:
    python3 -m python.location_retrieval --host 192.168.0.33
    python3 -m python.location_retrieval --host 192.168.0.33 --latlon
"""

from __future__ import annotations
import argparse, json, re, requests
from typing import Any, Optional, List, Tuple

KEY = "instrument/earthLocation"

# Regex parser for "31.978712S 115.816727E -12m"
_LOC_RE = re.compile(
    r"""
    (?P<lat>-?\d+(?:\.\d+)?)\s*(?P<lat_hemi>[NS])
    \s+
    (?P<lon>-?\d+(?:\.\d+)?)\s*(?P<lon_hemi>[EW])
    (?:\s+(?P<elev>-?\d+(?:\.\d+)?)\s*m)?
    """,
    re.IGNORECASE | re.VERBOSE,
)

def find_key_path(obj: Any, target: str, path: Optional[List[str]] = None):
    """DFS to find the first occurrence of `target` key in nested dict/list."""
    if path is None:
        path = []
    if isinstance(obj, dict):
        if target in obj:
            return path + [target], obj[target]
        for k, v in obj.items():
            found_path, found_val = find_key_path(v, target, path + [k])
            if found_path is not None:
                return found_path, found_val
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            found_path, found_val = find_key_path(item, target, path + [f"[{i}]"])
            if found_path is not None:
                return found_path, found_val
    return None, None

def _parse_latlon(value: str) -> Optional[Tuple[float, float]]:
    """Parse '31.978712S 115.816727E -12m' into (-31.978712, 115.816727)."""
    m = _LOC_RE.search(value)
    if not m:
        return None
    lat = float(m.group("lat"))
    lon = float(m.group("lon"))
    if m.group("lat_hemi").upper() == "S":
        lat = -abs(lat)
    if m.group("lon_hemi").upper() == "W":
        lon = -abs(lon)
    return (lat, lon)

def _fetch_soh_with_quick_then_slow(host: str) -> Optional[dict]:
    """
    Try a quick fetch first; if that fails, try one slower pass.
    Returns parsed JSON dict or None.
    """
    urls = [
        f"http://{host}/api/v1/instruments/soh",
        f"http://{host}/api/v1/instruments/soh/",  # some firmwares need the slash
    ]
    headers = {"Connection": "close", "Accept": "application/json, */*;q=0.8"}

    # 1) quick attempt (fast connect & read)
    for url in urls:
        try:
            r = requests.get(url, headers=headers, timeout=(2.0, 3.0), stream=False)
            r.raise_for_status()
            return r.json()
        except Exception:
            pass  # try the next URL / slower pass

    # 2) slower attempt (some boxes are slow on first hit)
    last_err = None
    for url in urls:
        try:
            r = requests.get(url, headers=headers, timeout=(3.0, 10.0), stream=False)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            last_err = e

    return None

# -------- Public API --------
def get_raw_earthlocation(host: str, timeout: Tuple[float, float] = (3.0, 5.0)) -> Optional[dict]:
    """
    Return the raw earthLocation dict {'value':..., 'time':...} or None.
    (timeout param kept for signature-compat; helper uses its own quick/slow.)
    """
    data = _fetch_soh_with_quick_then_slow(host)
    if data is None:
        return None

    _, val = find_key_path(data, KEY)
    if isinstance(val, dict) and "value" in val:
        return val
    return None

def get_location(host: str, timeout: Tuple[float, float] = (3.0, 5.0), fallback: Optional[Tuple[float, float]] = None) -> Optional[Tuple[float, float]]:
    """Return (lat, lon) or None (or fallback if provided)."""
    earth = get_raw_earthlocation(host, timeout=timeout)
    if earth and isinstance(earth.get("value"), str):
        parsed = _parse_latlon(earth["value"])
        if parsed:
            return parsed
    return fallback

def get_location_or_fallback(host: str, timeout: Tuple[float, float] = (3.0, 5.0), fallback=None):
    """Alias for get_location (for receiver.py compatibility)."""
    return get_location(host, timeout=timeout, fallback=fallback)

# -------- CLI for debugging --------
def _cli():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="192.168.0.33")
    parser.add_argument("--latlon", action="store_true", help="Show only lat/lon")
    args = parser.parse_args()

    if args.latlon:
        loc = get_location(args.host, fallback=None)
        print("Location:", loc if loc else "not available")
    else:
        obj = get_raw_earthlocation(args.host)
        if obj:
            print(json.dumps(obj, indent=2))
        else:
            print("not available")

if __name__ == "__main__":
    _cli()
