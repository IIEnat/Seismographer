# python/location_retrieval.py
from __future__ import annotations
import json
import re
from typing import Any, Dict, Iterable, Tuple, Optional

# Prefer 'requests', fall back to urllib so this still works without extra deps.
try:
    import requests  # type: ignore
    _HAS_REQUESTS = True
except Exception:
    _HAS_REQUESTS = False

if not _HAS_REQUESTS:
    from urllib.request import urlopen  # type: ignore
    from urllib.error import URLError  # type: ignore

# Example value: "31.978620S 115.816783E 13m"
# We want: (-31.978620, 115.816783)
_EARTH_LOC_RE = re.compile(
    r"""
    ^\s*
    (?P<lat>\d+(?:\.\d+)?)\s*(?P<lat_hemi>[NS])   # latitude with N/S
    \s+
    (?P<lon>\d+(?:\.\d+)?)\s*(?P<lon_hemi>[EW])   # longitude with E/W
    (?:\s+(?P<elev>\-?\d+(?:\.\d+)?))?m?          # optional elevation in meters
    \s*$
    """,
    re.VERBOSE | re.IGNORECASE,
)

def _parse_earth_location(value: str) -> Tuple[float, float]:
    """
    Parse strings like '31.978620S 115.816783E 13m' into signed (lat, lon).
    South/West => negative.
    """
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

def _walk_items(obj: Any) -> Iterable[tuple[str, Any]]:
    """
    Walk a nested JSON-like structure (dicts/lists) yielding (key, value)
    for dict entries at any depth.
    """
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield k, v
            # recurse
            for kv in _walk_items(v):
                yield kv
    elif isinstance(obj, list):
        for it in obj:
            for kv in _walk_items(it):
                yield kv

def _find_earth_location_blob(root: Any) -> Optional[Dict[str, Any]]:
    """
    Search the parsed JSON for a key == 'instrument/earthLocation'.
    Return its value if it's a dict like {"value": "...", "time": "..."}.
    """
    for k, v in _walk_items(root):
        if k == "instrument/earthLocation" and isinstance(v, dict):
            # Expect {"value": "31.978620S 115.816783E 13m", "time": "..."}
            return v
    return None

def fetch_location_from_seismometer(host: str, timeout: float = 2.5) -> tuple[float, float]:
    """
    GET http://<host>/api/v1/instruments/soh, locate 'instrument/earthLocation',
    parse its 'value' into (lat, lon). Raises on failure.
    'timeout' applies to both connect and read.
    """
    import json as _json  # local alias to avoid shadowing
    url = f"http://{host}/api/v1/instruments/soh"

    if _HAS_REQUESTS:
        # Use (connect_timeout, read_timeout) so connect fails fast off-LAN.
        r = requests.get(url, timeout=(timeout, timeout))  # type: ignore
        r.raise_for_status()
        payload = r.json()
    else:
        try:
            with urlopen(url, timeout=timeout) as resp:  # type: ignore
                data = resp.read()
            payload = _json.loads(data.decode("utf-8", errors="replace"))
        except Exception as e:  # URLError etc.
            raise ConnectionError(f"Failed to GET {url}: {e}") from e

    blob = _find_earth_location_blob(payload)
    if not blob or "value" not in blob:
        raise KeyError("instrument/earthLocation key not found in SOH payload")

    return _parse_earth_location(str(blob["value"]))


def get_location_or_fallback(host: str, timeout: float = 0.4) -> tuple[float, float]:
    """
    Try the live device first with a small timeout (fast fail when off-LAN);
    if anything goes wrong, return a hard-coded fallback.
    """
    try:
        return fetch_location_from_seismometer(host, timeout=timeout)
    except Exception:
        coords = _FALLBACK_COORDS.get(host)
        if coords is not None:
            return coords
        # Final safety: don't crash startup — fall back to (0,0)
        return (0.0, 0.0)
    
# ---------------- Hard-coded fallbacks ----------------
_FALLBACK_COORDS: Dict[str, Tuple[float, float]] = {
    # Example entry (uncomment and edit as needed):
    "192.168.0.27": (-31.35, 115.92),
    "192.168.0.32": (-31.40, 115.96),
    "192.168.0.33": (-31.45, 115.98),
}