## location_retrieval.py
from __future__ import annotations
import re
from typing import Any, Dict, Tuple, Optional

# We prefer 'requests', but if it isn't installed we'll just use the fallback.
# "pip install requests"
try:
    import requests  # type: ignore
    _HAS_REQUESTS = True
except Exception:
    _HAS_REQUESTS = False

_EARTH_LOC_RE = re.compile(
    r"""
    ^\s*
    (?P<lat>\d+(?:\.\d+)?)\s*(?P<lat_hemi>[NS])   # latitude number + N/S
    \s+
    (?P<lon>\d+(?:\.\d+)?)\s*(?P<lon_hemi>[EW])   # longitude number + E/W
    \s+
    (?P<elev>\d+)\s*m                             # elevation in meters (ignored)
    \s*$
    """,
    re.VERBOSE | re.IGNORECASE,
)

# Turn '31.978620S 115.816783E 13m' into (-31.978620, 115.816783).
def _parse_earth_location(value: str) -> Tuple[float, float]:
    m = _EARTH_LOC_RE.match(value.strip())
    if not m:
        raise ValueError(f"Unrecognized earthLocation format: {value!r}")

    lat = float(m.group("lat"))
    lon = float(m.group("lon"))

    if m.group("lat_hemi").upper() == "S":
        lat = -lat
    if m.group("lon_hemi").upper() == "W":
        lon = -lon

    return lat, lon

# Look for a key anywhere in a nested dict/list structure.
# Returns the value for 'key' or None if not found.
def _deep_get(obj: Any, key: str) -> Optional[Any]:
    if isinstance(obj, dict):
        if key in obj:
            return obj[key]
        for v in obj.values():
            found = _deep_get(v, key)
            if found is not None:
                return found
    elif isinstance(obj, list):
        for item in obj:
            found = _deep_get(item, key)
            if found is not None:
                return found
    return None

# Ask the device at http://{host}/api/v1/instruments/soh for coordinates.
def fetch_location_from_seismometer(host: str, timeout: float = 2.5) -> Tuple[float, float]:
    if not _HAS_REQUESTS:
        raise RuntimeError("The 'requests' package is not installed; cannot fetch live location.")

    url = f"http://{host}/api/v1/instruments/soh"
    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()

    node = _deep_get(data, "instrument/earthLocation")
    if node is None:
        raise KeyError("Key 'instrument/earthLocation' not found in SOH payload")

    # It might be a dict {"value": "..."} or already a string; handle both.
    value = node.get("value") if isinstance(node, dict) else node
    if not isinstance(value, str):
        raise TypeError("'instrument/earthLocation' value is not a string")

    return _parse_earth_location(value)

# Fallback coordinates to use when you are not on the instrument network
# Customize as needed.
_FALLBACK_COORDS: Dict[str, Tuple[float, float]] = {
    "192.168.0.27": (-31.978620, 115.816783),
    "192.168.0.32": (-31.978620, 115.816783),
    "192.168.0.33": (-31.978620, 115.816783),
}

# Try the live device first; if anything goes wrong (not on same LAN,
# 'requests' missing, device offline), return a hard-coded fallback.
def get_location_or_fallback(host: str) -> Tuple[float, float]:
    try:
        return fetch_location_from_seismometer(host)
    except Exception:
        coords = _FALLBACK_COORDS.get(host)
        if coords is not None:
            return coords
        raise

