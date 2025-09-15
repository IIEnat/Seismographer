# app.py
from __future__ import annotations

import os
from datetime import timezone, timedelta

from flask import Flask, render_template

# ---- Live/Synthetic seedlink pieces (kept from your original app) ----
try:
    from python.receiver import SLClientReceiver, create_blueprint
    from python.ingest import SyntheticIngest, Chan
except Exception:
    SLClientReceiver = None
    create_blueprint = None
    SyntheticIngest = None
    Chan = None

# NEW: import the playback blueprint factory
from playback_routes import create_playback_blueprint

app = Flask(__name__)

BASE_DIR = os.path.dirname(__file__)
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_DIR

# ------------------ Optional live map demo wiring ------------------
COORDS = {
    "XX.JINJ1..BHN": (-31.3447, 115.8923),
    "XX.JINJ1..BHE": (-31.3752, 115.9231),
    "XX.JINJ1..BHZ": (-31.3433, 115.9667),
}
AWST = timezone(timedelta(hours=8))  # UTC+8
USE_REAL_SEEDLINK = False

if SLClientReceiver is not None:
    rx = SLClientReceiver(coords=COORDS, metric="rms")
else:
    rx = None

if not USE_REAL_SEEDLINK and SyntheticIngest is not None and rx is not None:
    ingest = SyntheticIngest(
        chans=[
            Chan("XX", "JINJ1", "", "BHN", -31.3447, 115.8923, 2.0, 0.00),
            Chan("XX", "JINJ1", "", "BHE", -31.3752, 115.9231, 3.0, 0.33),
            Chan("XX", "JINJ1", "", "BHZ", -31.3433, 115.9667, 5.0, 0.66),
        ],
        sps=250.0,
        on_trace=getattr(rx, "on_trace", None),
    )
    ingest.start()

if create_blueprint is not None and rx is not None:
    app.register_blueprint(create_blueprint(rx))

# Register the Playback blueprint (all /playback* endpoints)
app.register_blueprint(create_playback_blueprint(
    upload_dir=app.config["UPLOAD_FOLDER"],
    awst_tz=AWST
))

# ------------------ Routes ------------------
@app.route("/")
def home():
    # If your project has a separate "home.html" keep this; otherwise swap to playback.html
    try:
        return render_template("home.html")
    except Exception:
        return render_template("playback.html")


# ------------------ Main ------------------
if __name__ == "__main__":
    # Run with: python app.py
    app.run(host="0.0.0.0", port=8000, debug=True)
