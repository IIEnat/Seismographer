# Seismographer - Technical User Documentation

[TO BE EDITED STILL]

### Data Sources

- **Live Data:**  
  - Streams from SeedLink servers using ObsPy.
  - Each station provides continuous seismic readings, processed in real time.

- **MiniSEED Playback:**  
  - Users can upload MiniSEED files for historical analysis.
  - Data is parsed and made available for playback and visualization.

### Data Format

- **Station Data:**
  - Each station has:
    - Station ID
    - Network code
    - Channel code
    - Latitude & Longitude
    - Sampling rate and filter parameters

- **Processed Data:**
  - Signals are processed per station:
    - Band-pass filtering (see `ingest.py`)
    - Envelope detection (see `ingest.py`)
    - Seam smoothing (see `ingest.py`)
    - Downsampling (see `ingest.py` and config)

- **Visualization Data:**
  - RMS (Root Mean Square) values represent seismic intensity.
  - Color gradients map RMS values to visual intensity.

### Data Interpretation

- **Color Coding:**
  - Blue/Green: Low seismic activity
  - Yellow/Red: High seismic activity

- **Waveforms:**
  - 1-second slices available for detailed analysis.
  - Envelope detection highlights overall energy.

- **Playback Data:**
  - Timeline slider allows navigation through historical data.
  - Per-station statistics and waveforms are available for each time slice.
