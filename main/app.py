# app.py
from flask import Flask, jsonify, render_template, request
from python.receiver import make_processors, start_processor_thread
from flask_socketio import SocketIO, emit
from python import receiver

app = Flask(__name__)
_processors = make_processors()
_threads = [start_processor_thread(p) for p in _processors]
socketio = SocketIO(app, cors_allowed_origins="*")

# Websocket
@socketio.on("connect")
def handle_connect():
    print("Client Connected")

@socketio.on("disconnect")
def handle_disconnect():
    print("Client Disconnected")

#processors = receiver.make_processors()

def background_sender():
    while True:
        data = {p.sta: p.to_json() for p in _processors}
        socketio.emit("station_update", data)   
        socketio.sleep(1)  

@app.route("/")
def home():

    # If your project has a separate "home.html" keep this; otherwise swap to playback.html
    try:
        return render_template("home.html", title = "Live Seismic Map", active_page = "home")
    except Exception:
        return render_template("playback.html", title = "Playback File", active_page = "playback")


@app.route("/playback", methods=["GET", "POST"])
def playback():
    """GET: render UI. POST: accept multi-file upload and return filenames."""
    if request.method == "POST":
        clear_uploads_folder()
        files = request.files.getlist("seedlink_file")
        if not files:
            return jsonify({"status": "error", "message": "No files uploaded"}), 400

        filenames: List[str] = []
        for file in files:
            if not file or not file.filename:
                continue
            filename = secure_filename(file.filename)
            dest = os.path.join(UPLOAD_DIR, filename)
            try:
                file.save(dest)
                filenames.append(filename)
            except Exception as e:
                print("Save error:", e)

        if not filenames:
            return jsonify({"status": "error", "message": "No valid filenames"}), 400
        return jsonify({"status": "uploaded", "filenames": filenames})

    # GET -> playback UI
    return render_template("playback.html", title = "Playback File", active_page = "playback")


@app.route("/playback_timeline/<filenames>")
def playback_timeline(filenames: str):
    """
    Return the global start/end and slider steps (1-second step).
    Timeline spans the union of all uploaded files.
    """
    file_list = [f for f in filenames.split(",") if f]
    merged = _read_streams_for_files(file_list)
    if len(merged) == 0:
        return jsonify({"start_iso": None, "end_iso": None, "steps": 1})

    start = min(tr.stats.starttime for tr in merged)
    end = max(tr.stats.endtime for tr in merged)
    window_size = 1  # seconds per slider step
    steps = int((end - start) // window_size) + 1

    return jsonify({
    "start_iso": start.datetime.replace(tzinfo=AWST).isoformat(),
    "end_iso": end.datetime.replace(tzinfo=AWST).isoformat(),
    "steps": steps
    })


@app.route("/playback_data/<filenames>/<int:slider>")
def playback_data(filenames: str, slider: int):
    """
    Return per-station RMS for the current 1-second window.
    Multiple files for the same station are treated as one logical signal.
    """
    file_list = [f for f in filenames.split(",") if f]
    merged = _read_streams_for_files(file_list)
    if len(merged) == 0:
        return jsonify({"slider": slider, "stations": []})

    window_size = 1
    t0 = min(tr.stats.starttime for tr in merged)
    t_start = t0 + slider * window_size
    t_end = t_start + window_size

    # Only Z-channel traces for map badges
    z_traces = [tr for tr in merged if str(tr.stats.channel).endswith("Z")]
    by_station = _group_traces_by_station(z_traces)

    stations = []
    for sid, traces in by_station.items():
        # Merge all segments intersecting this second
        vals, _meta = _slice_concat_values(traces, t_start, t_end)
        rms = float(np.sqrt(np.mean(vals ** 2))) if vals.size else 0.0
        lat, lon = _coord_for_station(traces)
        stations.append({"id": sid, "lat": lat, "lon": lon, "rms": rms})

    return jsonify({"slider": slider, "stations": stations})


@app.route("/playback_wave/<filenames>/<int:slider>/<path:station_id>")
def playback_wave(filenames: str, slider: int, station_id: str):
    """
    Return the 1-second waveform slice for one station.
    If multiple files contain that station, we combine their samples within the window.
    """
    file_list = [f for f in filenames.split(",") if f]
    merged = _read_streams_for_files(file_list)
    if len(merged) == 0:
        return jsonify({"fs": 0, "values": [], "t0_iso": None})

    window_size = 1
    t0 = min(tr.stats.starttime for tr in merged)
    t_start = t0 + slider * window_size
    t_end = t_start + window_size

    # All traces belonging to exactly this station id (NET.STA.LOC.CHA)
    traces = [tr for tr in merged if _station_id(tr) == station_id]
    if not traces:
        return jsonify({"fs": 0, "values": [], "t0_iso": None})

    vals, (fs, t0_iso, _) = _slice_concat_values(traces, t_start, t_end)
    return jsonify({"fs": float(fs or 0.0), "values": vals.astype(np.float64).tolist(), "t0_iso": t0_iso})

@app.route("/playback_stats/<filenames>")
def playback_stats(filenames: str):
    """
    Compute per-second RMS across the entire uploaded hour in one pass (server-side).
    Returns the global min/max RMS (value + station id + timestamp ISO).
    Efficient: vectorized binning by second using np.bincount; no N requests from client.
    """
    file_list = [f for f in filenames.split(",") if f]
    merged = _read_streams_for_files(file_list)
    if len(merged) == 0:
        return jsonify({"min": None, "max": None})

    # Work on Z only (matches your playback policy)
    z_traces = [tr for tr in merged if str(tr.stats.channel).endswith("Z")]
    if not z_traces:
        return jsonify({"min": None, "max": None})

    # Reference second grid for the hour
    t_start = min(tr.stats.starttime for tr in z_traces)
    t_end   = max(tr.stats.endtime   for tr in z_traces)
    base_sec = int(floor(t_start.timestamp))                      # anchor
    n_secs   = max(1, int(ceil(t_end.timestamp) - base_sec))      # ~3600

    # Per-station accumulators: second -> sum(x^2) and count
    sumsqs = defaultdict(lambda: np.zeros(n_secs, dtype=np.float64))
    counts = defaultdict(lambda: np.zeros(n_secs, dtype=np.int64))
    coords = {}  # station -> (lat, lon) (optional, not used in result)

    # Vectorized binning per trace
    for tr in z_traces:
        sid = _station_id(tr)
        coords.setdefault(sid, _hardcoded_latlon_for_trace(tr))
        fs = float(getattr(tr.stats, "sampling_rate", 0.0) or 0.0)
        if fs <= 0:
            continue
        data = np.asarray(tr.data, dtype=np.float64)
        if data.size == 0:
            continue

        # Offset seconds from base
        start_ts = tr.stats.starttime.timestamp
        # For each sample, compute which integer-second bucket it belongs to
        idx = np.floor((start_ts - base_sec) + np.arange(data.size) / fs).astype(np.int64)

        # Keep only indices within [0, n_secs)
        m = (idx >= 0) & (idx < n_secs)
        if not np.any(m):
            continue
        idx = idx[m]
        seg = data[m]
        seg2 = seg * seg

        # Accumulate sum of squares and counts into per-second bins
        sumsqs[sid] += np.bincount(idx, weights=seg2, minlength=n_secs)
        counts[sid] += np.bincount(idx, minlength=n_secs)

    # Compute RMS per second for each station, then global min/max
    best_min = None  # (rms, sid, sec_idx)
    best_max = None
    for sid in sumsqs.keys():
        c = counts[sid]
        s2 = sumsqs[sid]
        valid = c > 0
        if not np.any(valid):
            continue
        rms = np.zeros_like(s2, dtype=np.float64)
        rms[valid] = np.sqrt(s2[valid] / c[valid])

        # min (exclude zeros where no data)
        mi_idx = np.argmin(np.where(valid, rms, np.inf))
        ma_idx = np.argmax(np.where(valid, rms, -np.inf))
        mi_val = rms[mi_idx] if valid[mi_idx] else np.inf
        ma_val = rms[ma_idx] if valid[ma_idx] else -np.inf

        if best_min is None or mi_val < best_min[0]:
            best_min = (float(mi_val), sid, int(mi_idx))
        if best_max is None or ma_val > best_max[0]:
            best_max = (float(ma_val), sid, int(ma_idx))

    def pack(item):
        if not item:
            return None
        val, sid, sec_idx = item
        iso = datetime.fromtimestamp(base_sec + sec_idx, tz=AWST).isoformat()
        return {"value": val, "id": sid, "iso": iso}
    return "OK"

@app.route("/api/status")
def api_status():
    return jsonify({f"{p.sta}": p.to_json() for p in _processors})

if __name__ == "__main__":
    socketio.start_background_task(background_sender)
    socketio.run(app, debug=False, host = '0.0.0.0', port=5000)
