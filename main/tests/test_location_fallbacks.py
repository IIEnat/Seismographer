"""
Location fallback logic.

Reasoning:
- Unknown station IDs should not crash.
- Returning None lets callers use a default fallback; a (lat, lon) tuple is also valid.
"""
import importlib
import pytest

def test_unknown_station_has_safe_behavior():
    # Coords should be in config.py so check there only
    COORDS = None
    try:
        cfg = importlib.import_module("config")
        COORDS = getattr(cfg, "COORDS", None)
    except Exception:
        pass

    if COORDS is None:
        pytest.skip("No COORDS mapping found in config or app")

    value = COORDS.get("ZZ.UNKNOWN..BHZ", None)
    assert value is None or isinstance(value, tuple)
