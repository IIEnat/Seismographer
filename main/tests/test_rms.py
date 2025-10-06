"""
Tests correctness of the RMS calculation.

Reasoning:
- RMS of a constant A = |A|
- RMS of a sine wave = A / sqrt(2)
- RMS is always non-negative
- RMS(k·x) = |k| * RMS(x)
"""
import math
import numpy as np
import importlib

def test_rms_properties():
    mod = importlib.import_module("python.receiver")
    rms = getattr(mod, "compute_rms")

    assert rms([0, 0, 0]) == 0.0  # zeros → 0
    assert rms([5, 5, 5]) == 5.0  # constant → magnitude

    # sine wave test
    A = 2.0
    t = np.linspace(0, 2 * np.pi, 1000)
    x = A * np.sin(t)
    expected = A / math.sqrt(2)
    assert abs(rms(x) - expected) < 0.05 * expected

    # non-negativity
    assert rms([-1, -2, -3]) >= 0

    # scale invariance
    arr = np.random.randn(100)
    assert abs(rms(3 * arr) - 3 * rms(arr)) < 1e-9
