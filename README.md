# Seismographer - Real Time Seismic Imaging

## Context
Seismographer was developed as a group project assigned as part of the unit [CITS3200: Professional Computing](https://teaching.csse.uwa.edu.au/units/CITS3200/) at [The University of Western Australia](https://www.uwa.edu.au/) during the second semester of 2025.  The project proposal was submitted by a client in the Physics department who needed data from a seismic array at the Gingin High Optical Power Facility collected, processed, and graphically displayed.

## Project Team
| Student Name | Student Number | GitHub Username |
|--------------|----------------|-----------------|
| Raynard      | 24006703       | IIEnat          |
| Yutong       | 23723494       | amiwaffletoday  |
| Jimmy        | 23661316       | JimmyTanUWA     |
| Kathleen     | 24091081       | kathisabella    |
| Andrew       | 23384163       | Andrew-Biggins1 |
| Aaron        | 23815248       | Attempt27       |

## Project Setup
To **install dependancies** change directory to ```/main/``` and run:
```
$ pip install -r requirements.txt
```

To **run** the app, from the same ```/main/``` directory run:
```
$ python3 app.py
```

## License
This project is licensed under the terms of the GNU General Public License v3.0.  See [COPYING.txt](COPYING.txt) for more information.




## Purpose
Seismographer is an interactive tool that visualises real-time seismic activity using live data feeds. Built for researchers for monitoring gravitational waves, this project translates seismic signals into intuitive color-coded maps, providing a live, top-down view of ground motion as it happens.

## Key Features 
- Real-time Data: Connects to seismometers using SeedLink and processes streams via ObsPy.  
- Dynamic Mapping: Visualizes ground motion on an interactive map.  
- Color-coded Intensity: Seismic intensity is rendered using color gradients for easy interpretation.  
- Live Updates: The map auto-refreshes as new seismic data arrives.  
- Customisable Views: Filter by station or time window.  

## Technologies Used
A web-app built using Flask and typical webdev technologies:
- Obspy, numpy, seedlink for data aggregation in Python.
- HTML, CSS, JS for frontend.

## Running Tests


## Project Structure
```
├── README.md
└── main/
    ├── app.py
    ├── config.py
    ├── python/
    │   ├── ingest.py
    │   ├── location_retrieval.py
    │   ├── playback_routes.py
    │   └── receiver.py
    ├── requirements.txt
    ├── static/
    │   └── css/
    │       └── global.css
    └── templates/
        ├── home.html
        ├── navbar.html
        └── playback.html
```

## System Overview
- **Ingest (receiver.py, ingest.py):** Connects to SeedLink or synthetic generators, processes signals into band/envelope streams.
- **Processing:** Each station is handled by a StationProcessor that applies band-pass filtering, envelope detection, seam smoothing, and downsampling.
- **Backend (app.py):** Flask + Socket.IO app that streams live updates, serves HTML templates, and provides a `/raw` diagnostics endpoint.
- **Playback (playback_routes.py):** Blueprint for uploading MiniSEED files, generating timelines, per-station waveforms, and RMS stats.
- **Frontend (templates + static):** Interactive Leaflet map with color-coded station bubbles and a playback UI.

## API Endpoints
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Live seismic map UI |
| `/raw` | GET | Latest raw seismic samples per station (JSON) |
| `/playback` | GET/POST | Playback UI (upload MiniSEED file) |
| `/playback_json/<filenames>` | GET | Per-station compact JSON (band/envelope) |
| `/playback_timeline/<filenames>` | GET | Global start/end times + slider steps |
| `/playback_data/<filenames>/<slider>` | GET | Per-station RMS for current second |
| `/playback_wave/<filenames>/<slider>/<station_id>` | GET | 1-second waveform slice |
| `/playback_stats/<filenames>` | GET | Global min/max RMS across dataset |

## Configuration
All tunables are in `config.py`:
- `HOSTS`, `NET`, `CHAN`: Station connectivity
- `FS`, `BAND`, `TARGET_HZ`: Sampling and filter parameters
- `BATCH_SECONDS`, `RAW_SECONDS`: Buffering and diagnostics
- `PATCH_TAIL_SECONDS`, `PATCH_INTERVAL_SECONDS`: Seam smoothing
- `STARTUP_SECONDS`: Countdown shown to frontend
- `SPEED_FACTOR`: Simulation speed control
