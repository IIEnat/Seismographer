from flask import Flask, render_template
from python.receiver import SLClientReceiver, create_blueprint
from python.ingest import SyntheticIngest, Chan

from flask import request, jsonify
import os
from werkzeug.utils import secure_filename
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(__file__), 'uploads')
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

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
    None
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


# Home page
@app.route("/")
def home():
    return render_template("home.html")

# Playback page

import glob
def clear_uploads_folder():
    for f in glob.glob(os.path.join(app.config['UPLOAD_FOLDER'], '*')):
        try:
            os.remove(f)
        except Exception:
            pass

@app.route("/playback", methods=["GET", "POST"])
def playback():
    if request.method == "POST":
        clear_uploads_folder()
        files = request.files.getlist("seedlink_file")
        if not files:
            return "No file uploaded", 400
        filenames = []
        for file in files:
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            filenames.append(filename)
        return jsonify({"status": "uploaded", "filenames": filenames})
    else:
        clear_uploads_folder()
        return render_template("playback.html")

# Endpoint for slider playback (stub)

from obspy import read as obspy_read
from python.receiver import SLClientReceiver


@app.route("/playback_data/<filenames>/<int:slider>")
def playback_data(filenames, slider):
    # Support multiple files (comma-separated)
    file_list = filenames.split(',')
    streams = []
    for fname in file_list:
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], fname)
        if not os.path.exists(filepath):
            continue
        try:
            st = obspy_read(filepath)
            streams.append(st)
        except Exception as e:
            continue

    if not streams:
        return jsonify({"slider": slider, "stations": []})

    # Merge all streams
    from obspy import Stream
    merged_stream = Stream()
    for st in streams:
        merged_stream += st

    # Use static COORDS for demo, but ideally extract from traces
    COORDS = {
        "XX.JINJ1..BHN": (-31.3447,115.8923),
        "XX.JINJ1..BHE": (-31.3752,115.9231),
        "XX.JINJ1..BHZ": (-31.3433,115.9667),
    }
    rx = SLClientReceiver(coords=COORDS, metric="rms")

    # Simulate slider as time window (e.g., seconds)
    window_size = 1  # seconds per slider step
    # Find earliest starttime
    if len(merged_stream) == 0:
        return jsonify({"slider": slider, "stations": []})
    t_start = min(tr.stats.starttime for tr in merged_stream) + slider * window_size
    t_end = t_start + window_size
    traces_in_window = merged_stream.slice(starttime=t_start, endtime=t_end)

    # Feed traces to receiver
    for tr in traces_in_window:
        rx.on_trace(tr)

    stations = rx.agg.snapshot(COORDS)
    for s in stations:
        s["intensity"] = s["rms"]

    return jsonify({"slider": slider, "stations": stations})

if __name__ == "__main__":
    app.run(debug=True)
