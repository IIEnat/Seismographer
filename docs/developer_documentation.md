# Seismographer - Developer Documentation

## Project Structure
See [../README.md](../README.md)

## Technical Stack

- **Backend:**
  - Python (Flask, ObsPy, NumPy)
  - Modular design:
    - `receiver.py`: Connects to SeedLink or synthetic generators, processes signals.
    - `ingest.py`: Handles band/envelope streams and signal processing.
    - `location_retrieval.py`: Retrieves and manages station location data.
    - `playback_routes.py`: Implements playback features and endpoints.

- **Frontend:**
  - HTML, CSS, JavaScript.
  - Leaflet for interactive mapping.
  - Custom CSS for UI styling.

- **Templates:**
  - `home.html`: Main map and live view.
  - `navbar.html`: Navigation bar.
  - `playback.html`: Playback UI for historical data.

- **Uploads:**
  - MiniSEED files are uploaded to the `uploads/` directory for playback analysis.

## Module Breakdown

### `app.py`
- Entry point for the Flask application.
- Sets up routes for the homepage, playback, and diagnostics.
- Integrates Socket.IO for real-time updates.
- Loads configuration from `config.py`.
- Registers blueprints (e.g. playback routes).

### `config.py`
- Centralizes all tunable parameters:
  - Station connectivity (`HOSTS`, `NET`, `CHAN`).
  - Signal processing (`FS`, `BAND`, `TARGET_HZ`).
  - Buffering (`BATCH_SECONDS`, `RAW_SECONDS`).
  - Smoothing (`PATCH_TAIL_SECONDS`, `PATCH_INTERVAL_SECONDS`).
  - Startup and simulation (`STARTUP_SECONDS`, `SPEED_FACTOR`).

### `python/receiver.py`
- Handles connection to SeedLink servers or synthetic data generators.
- Receives raw seismic data streams.
- Passes data to `ingest.py` for processing.

### `python/ingest.py`
- Processes incoming seismic signals per station.
- Applies band-pass filtering and envelope detection.
- Implements seam smoothing and downsampling.
- Maintains per-station buffers for real-time and playback use.

### `python/location_retrieval.py`
- Retrieves and manages station location data.
- Likely parses station metadata (ID, network, channel, latitude, longitude).
- Provides location info for mapping and filtering.

### `python/playback_routes.py`
- Implements Flask blueprint for playback functionality.
- Handles MiniSEED file uploads.
- Generates timelines, per-station waveforms, and RMS statistics.
- Provides endpoints for playback data retrieval.

### `static/css/global.css`
- Styles the frontend UI, including map, controls, and playback elements.

### `templates/home.html`
- Renders the main map UI with live station data.

### `templates/navbar.html`
- Provides navigational linking for the app.

### `templates/playback.html`
- Renders the playback UI for historical data analysis.

## API Endpoints

| Endpoint                                           | Method   | Description                                   |
|----------------------------------------------------|----------|-----------------------------------------------|
| `/`                                                | GET      | Live seismic map UI                           |
| `/raw`                                             | GET      | Latest raw seismic samples per station (JSON) |
| `/playback`                                        | GET/POST | Playback UI (upload MiniSEED file)            |
| `/playback_json/<filenames>`                       | GET      | Per-station compact JSON (band/envelope)      |
| `/playback_timeline/<filenames>`                   | GET      | Global start/end times + slider steps         |
| `/playback_data/<filenames>/<slider>`              | GET      | Per-station RMS for current second            |
| `/playback_wave/<filenames>/<slider>/<station_id>` | GET      | 1-second waveform slice                       |
| `/playback_stats/<filenames>`                      | GET      | Global min/max RMS across dataset             |

## Configuration Reference

All tunable parameters are set in `config.py`:

- **Station Connectivity:**
  - `HOSTS`: List of SeedLink hosts or data sources
  - `NET`: Network code
  - `CHAN`: Channel code

- **Sampling and Filtering:**
  - `FS`: Sampling rate
  - `BAND`: Band-pass filter parameters
  - `TARGET_HZ`: Target frequency for downsampling

- **Buffering and Diagnostics:**
  - `BATCH_SECONDS`: Buffer duration for batch processing
  - `RAW_SECONDS`: Buffer duration for diagnostics

- **Seam Smoothing:**
  - `PATCH_TAIL_SECONDS`: Tail duration for smoothing
  - `PATCH_INTERVAL_SECONDS`: Interval for patching seams

- **Startup and Simulation:**
  - `STARTUP_SECONDS`: Countdown shown to frontend on startup
  - `SPEED_FACTOR`: Simulation speed control

## Suggestions for Future Development

- **User Experience**
  - Add tooltips, help popups, and a dedicated manual page within the application.
  - Create a single executable file that can run the server and open it in a browser.

- **Functionality**
  - Implement a database to save the live seismic streams.
  - Use a gradient colour overlay on the map instead of individually coloured stations.
  - Implement a conversion from the meaningless voltage measures given by seismometers (and currently displayed) to displacement in micrometers.
