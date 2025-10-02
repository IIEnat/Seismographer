# Central, static configuration (no env vars needed)

# ---- Stations / connectivity ----
HOSTS = ["192.168.0.33", "192.168.0.32", "192.168.0.27"]
NET = "GG"
CHAN = "HNZ"

# Demo coordinates (override with real values if available)
COORDS = {
    "WAR27": (-31.35, 115.92),
    "WAR32": (-31.40, 115.96),
    "WAR33": (-31.45, 115.98),
}

# ---- Signal processing ----
FS = 250.0                     # native sampling rate (Hz)
BAND = (0.05, 0.10)            # band-pass (Hz)
TARGET_HZ = 5.0                # UI drip rate (band & env)
QSIZE = 900                    # ~3 min @ 5 Hz
RAW_SECONDS = 3                # keep ~3 s of native RAW for /raw
FRONTEND_FORCE_REDRAW_SECONDS = 40


# Strict buffering: accumulate one whole block before first output
BATCH_SECONDS = 20         # first-block length (s) — also used as UI countdown
MIN_PEAK_DIST_SEC = max(3.0, 0.5 / max(BAND[1], 1e-6))  # >=3 s or half of shortest period

# ---- Seam smoothing (reconciliation) ----
# Recompute the last PATCH_TAIL_SECONDS of the previous block using
# a small look-ahead from the next block every PATCH_INTERVAL_SECONDS.
PATCH_TAIL_SECONDS = 20.0
PATCH_INTERVAL_SECONDS = 2.0

# ---- UI hints ----
STARTUP_SECONDS = BATCH_SECONDS  # surfaced to front-end for the first countdown

# ---- Dev/test speed control for the simulator (optional) ----
SPEED_FACTOR = 1.0   # 1.0 = realtime, 2.0 = 2x faster, etc.
