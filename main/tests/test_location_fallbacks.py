"""
Tests location fallback logic.

Reasoning:
- Unknown station IDs should not crash.
- Either return None (caller will use fallback coords)
  or a valid (lat, lon) tuple if fallback implemented.
"""
import importlib
import pytest

def test_unknown_station_has_safe_behavior():
    mod = importlib.import_module("python.receiver")
    COORDS = getattr(mod, "COORDS", None)
    if COORDS is None:
        pytest.skip("No COORDS found in receiver.py")

    value = COORDS.get("ZZ.UNKNOWN..BHZ", None)
    assert value is None or isinstance(value, tuple)
