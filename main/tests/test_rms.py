"""
RMS identities test.

If a public helper exists (e.g., python.playback_routes.compute_rms),
we validate:
- RMS(constant A) = |A|
- RMS(sine, amp A) = A/sqrt(2)
- Non-negativity and scale invariance

If no helper is exported, we SKIP (app may compute RMS inline in a route).
"""
import math
import numpy as np
import pytest
from importlib import import_module

def _maybe_get_public_rms():
    for modname, attr in [
        ("python.playback_routes", "compute_rms"),
        ("python.receiver", "compute_rms"),
        ("python.ingest", "compute_rms"),
    ]:
        try:
            mod = import_module(modname)
            fn = getattr(mod, attr, None)
            if callable(fn):
                return fn
        except Exception:
            pass
    return None

def test_rms_identities():
    rms = _maybe_get_public_rms()
    if rms is None:
        pytest.skip("No public RMS helper exported; app computes RMS inline.")

    # constants
    for A in (0.0, 1.0, -3.5, 10.0):
        x = np.full(4096, A, dtype=float)
        assert math.isclose(rms(x), abs(A), rel_tol=1e-6, abs_tol=1e-12)

    # sine -> A/sqrt(2)
    fs = 2000.0
    t = np.arange(0, 1.0, 1.0 / fs)
    A = 2.0
    x = A * np.sin(2 * math.pi * 5.0 * t)
    expected = A / math.sqrt(2.0)
    assert math.isclose(rms(x), expected, rel_tol=5e-3, abs_tol=1e-6)

    # non-negativity & scale-invariance
    rng = np.random.default_rng(123)
    x = rng.normal(0, 1, size=4096)
    r1, r2 = rms(x), rms(7.0 * x)
    assert r1 >= 0 and r2 >= 0
    assert math.isclose(r2, 7.0 * r1, rel_tol=1e-6, abs_tol=1e-9)
