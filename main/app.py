from flask import Flask, render_template, request, jsonify
from python.receiver import SLClientReceiver, create_blueprint
from python.ingest import SyntheticIngest, Chan

from werkzeug.utils import secure_filename
import os
import glob  # <-- needed
import numpy as np  # <-- needed
from obspy import read as obspy_read, Stream  # <-- needed

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(__file__), 'uploads')
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
UPLOAD_DIR = app.config['UPLOAD_FOLDER']  # <-- define once and reuse

# Placeholder Data, realistically this would be relpaced by real SeedLink data from the SOH
COORDS = {
  "XX.JINJ1..BHN": (-31.3447,115.8923),
  "XX.JINJ1..BHE": (-31.3752,115.9231),
  "XX.JINJ1..BHZ": (-31.3433,115.9667),
}
rx = SLClientReceiver(coords=COORDS, metric="rms")

USE_REAL_SEEDLINK = False
if USE_REAL_SEEDLINK:
    # For real SeedLink data, replace with actual server details
    pass
else:
    # Use to create the Obspy traces in ingest.py
    ingest = SyntheticIngest(
        chans=[
            Chan("XX","JINJ1","","BHN",-31.3447,115.8923,2.0,0.00),
            Chan("XX","JINJ1","","BHE",-31.3752,115.9231,3.0,0.33),
            Chan("XX","JINJ1","","BHZ",-31.3433,115.9667,5.0,0.66),
        ],
        sps=250.0,
        on_trace=rx.on_trace,
    )
    ingest.start()

app.register_blueprint(create_blueprint(rx))

# ------------------ Helpers for playback ------------------
def clear_uploads_folder():
    for f in glob.glob(os.path.join(UPLOAD_DIR, "*")):
        try:
            os.remove(f)
        except Exception:
            pass

def _read_streams_for_files(filenames):
    """Return merged ObsPy Stream for a list of filenames saved in UPLOAD_DIR."""
    streams = []
    for fname in filenames:
        path = os.path.join(UPLOAD_DIR, fname)
        if not os.path.exists(path):
            continue
        try:
            st = obspy_read(path)
            streams.append(st)
        except Exception:
            continue
    merged = Stream()
    for st in streams:
        merged += st
    return merged

def _hardcoded_latlon_for_trace(tr):
    """
    Hard-code location when unknown. For now:
    - If station contains 'WAR' and channel is Z/BHZ → fixed Gingin-ish point.
    - Else try embedded coordinates if present; otherwise None.
    """
    if "WAR" in tr.stats.station and (str(tr.stats.channel).endswith("Z") or tr.stats.channel == "BHZ"):
        return (-31.347, 115.895)
    coords = getattr(tr.stats, "coordinates", {}) or {}
    lat = coords.get("latitude")
    lon = coords.get("longitude")
    if lat is None or lon is None:
        lat = getattr(tr.stats, "lat", None)
        lon = getattr(tr.stats, "lon", None)
    return (lat, lon)

# ------------------ Routes ------------------
@app.route("/")
def home():
    return render_template("home.html")

@app.route("/playback", methods=["GET", "POST"])
def playback():
    if request.method == "POST":
        clear_uploads_folder()
        files = request.files.getlist("seedlink_file")
        if not files:
            return jsonify({"status": "error", "message": "No files uploaded"}), 400
        filenames = []
        for file in files:
            if not file or not file.filename:
                continue
            filename = secure_filename(file.filename)
            dest = os.path.join(UPLOAD_DIR, filename)
            file.save(dest)
            filenames.append(filename)
        if not filenames:
            return jsonify({"status": "error", "message": "No valid filenames"}), 400
        return jsonify({"status": "uploaded", "filenames": filenames})
    # GET
    return render_template("playback.html")

@app.route("/playback_timeline/<filenames>")
def playback_timeline(filenames):
    file_list = [f for f in filenames.split(",") if f]
    merged = _read_streams_for_files(file_list)
    if len(merged) == 0:
        return jsonify({"start_iso": None, "end_iso": None, "steps": 1})
    start = min(tr.stats.starttime for tr in merged)
    end   = max(tr.stats.endtime   for tr in merged)
    window_size = 1  # seconds per slider step
    steps = int((end - start) // window_size) + 1
    return jsonify({
        "start_iso": start.datetime.isoformat(),
        "end_iso":   end.datetime.isoformat(),
        "steps":     steps
    })

@app.route("/playback_data/<filenames>/<int:slider>")
def playback_data(filenames, slider):
    file_list = [f for f in filenames.split(",") if f]
    merged = _read_streams_for_files(file_list)
    if len(merged) == 0:
        return jsonify({"slider": slider, "stations": []})

    window_size = 1
    t0 = min(tr.stats.starttime for tr in merged)
    t_start = t0 + slider * window_size
    t_end   = t_start + window_size

    z_traces = [tr for tr in merged if str(tr.stats.channel).endswith("Z")]
    stations = []
    for tr in z_traces:
        sliced = tr.slice(starttime=t_start, endtime=t_end)
        data = np.asarray(sliced.data, dtype=np.float64)
        rms = float(np.sqrt(np.mean(data**2))) if data.size else 0.0

        station_id = f"{tr.stats.network}.{tr.stats.station}.{tr.stats.location}.{tr.stats.channel}"
        lat, lon = _hardcoded_latlon_for_trace(tr)

        stations.append({
            "id": station_id,
            "lat": lat,
            "lon": lon,
            "rms": rms
        })
    return jsonify({"slider": slider, "stations": stations})

@app.route("/playback_wave/<filenames>/<int:slider>/<path:station_id>")
def playback_wave(filenames, slider, station_id):
    file_list = [f for f in filenames.split(",") if f]
    merged = _read_streams_for_files(file_list)
    if len(merged) == 0:
        return jsonify({"fs": 0, "values": [], "t0_iso": None})

    window_size = 1
    t0 = min(tr.stats.starttime for tr in merged)
    t_start = t0 + slider * window_size
    t_end   = t_start + window_size

    target = None
    for tr in merged:
        sid = f"{tr.stats.network}.{tr.stats.station}.{tr.stats.location}.{tr.stats.channel}"
        if sid == station_id:
            target = tr
            break

    if target is None:
        return jsonify({"fs": 0, "values": [], "t0_iso": None})

    sliced = target.slice(starttime=t_start, endtime=t_end)
    data = np.asarray(sliced.data, dtype=np.float64)
    fs = float(getattr(target.stats, "sampling_rate", 0.0))
    return jsonify({
        "fs": fs,
        "values": data.tolist(),
        "t0_iso": t_start.datetime.isoformat()
    })

if __name__ == "__main__":
    # Run: python app.py
    app.run(host="0.0.0.0", port=8000, debug=True)
