"""
@file config.py
@brief Central static configuration for seismic Flask app.
@details
This file centralizes all constants for station connectivity, signal processing,
UI behavior, and simulator options. No environment variables are required.
"""

# ------------------------------------------------------------------------
# Stations / connectivity
# ------------------------------------------------------------------------

HOSTS = ["192.168.0.33", "192.168.0.32", "192.168.0.27"] # IPs of connected instruments
NET = "GG"      # Default seismic network code
CHAN = "HNZ"    # Default channel code (vertical component, high-gain)

SIMULATE = 'auto' # Simulate flag
# Demo coordinates (used if station metadata doesn’t provide lat/lon).
# Override with real values for production.
COORDS = {
    "WAR33": (-31.35, 115.92),
    "WAR32": (-31.40, 115.96),
    "WAR27": (-31.45, 115.98),
}

# ------------------------------------------------------------------------
# Signal processing parameters
# ------------------------------------------------------------------------

FS = 250.0                          # Native sampling rate (Hz) of instrument data
BAND = (0.05, 0.10)                 # Band-pass filter (Hz), applied during processing
TARGET_HZ = 5.0                     # Downsample rate for UI envelope streaming (Hz)
QSIZE = 900                         # Size of circular queue for envelope (~3 min @ 5 Hz)
MIN_PEAK_DIST_SEC = max(3.0, 0.5 / max(BAND[1], 1e-6))

# Strict buffering: accumulate one full batch before emitting first output
BATCH_SECONDS = 20               # Initial processing window size (s)
STARTUP_SECONDS = BATCH_SECONDS  # Countdown shown to users on startup

# Minimum distance between peaks: >= 3 s or half of shortest wave period

# ------------------------------------------------------------------------
# Seam smoothing (block reconciliation)
# ------------------------------------------------------------------------
# When stitching processed data blocks, the last PATCH_TAIL_SECONDS of the
# previous block is re-processed with a small look-ahead from the next block
# every PATCH_INTERVAL_SECONDS, to reduce edge artifacts.

PATCH_TAIL_SECONDS = 20.0           # Duration of overlap region for smoothing (s)
PATCH_INTERVAL_SECONDS = 2.0        # How often to apply patching (s)

# ------------------------------------------------------------------------
# UI options
# ------------------------------------------------------------------------

FRONTEND_FORCE_REDRAW_SECONDS = 40  # UI redraw safety interval (s)
STATION_RADIUS = 1000               # Station marker radius (m) for UI

# ------------------------------------------------------------------------
# Development / testing speed controls (simulator only)
# ------------------------------------------------------------------------

RAW_SECONDS = 3      # Length of raw waveform history kept for /raw endpoint
SPEED_FACTOR = 1.0   # Playback speed multiplier (1.0 = real-time, 2.0 = 2× faster, etc.)
