
## Features & Technical Implementation

### Key Features

- **Real-Time Visualization:**
  - Flask + Socket.IO backend streams live updates to the frontend.
  - Interactive Leaflet map displays station bubbles with color-coded intensity.

- **Customizable Views:**
  - Filter stations by name or time window.
  - Playback UI for uploading and analyzing MiniSEED files.

- **Diagnostics:**
  - `/raw` endpoint provides latest raw seismic samples for debugging and monitoring.

### Technical Stack

- **Backend:**
  - Python (Flask, ObsPy, numpy)
  - Modular design:
    - `receiver.py`: Connects to SeedLink or synthetic generators, processes signals.
    - `ingest.py`: Handles band/envelope streams and signal processing.
    - `location_retrieval.py`: Retrieves and manages station location data.
    - `playback_routes.py`: Implements playback features and endpoints.

- **Frontend:**
  - HTML, CSS, JavaScript
  - Leaflet for interactive mapping
  - Custom CSS for UI styling

- **Templates:**
  - `home.html`: Main map and live view
  - `navbar.html`: Navigation bar
  - `playback.html`: Playback UI for historical data

- **Uploads:**
  - MiniSEED files are uploaded to the `uploads/` directory for playback analysis.

---

## Module Breakdown

### `app.py`
- Entry point for the Flask application.
- Sets up routes for the homepage, playback, and diagnostics.
- Integrates Socket.IO for real-time updates.
- Loads configuration from `config.py`.
- Registers blueprints (e.g. playback routes).

### `config.py`
- Centralizes all tunable parameters:
  - Station connectivity (`HOSTS`, `NET`, `CHAN`)
  - Signal processing (`FS`, `BAND`, `TARGET_HZ`)
  - Buffering (`BATCH_SECONDS`, `RAW_SECONDS`)
  - Smoothing (`PATCH_TAIL_SECONDS`, `PATCH_INTERVAL_SECONDS`)
  - Startup and simulation (`STARTUP_SECONDS`, `SPEED_FACTOR`)

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
- Provides navigation links for the app.

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

## System Overview
- **Ingest (receiver.py, ingest.py):** Connects to SeedLink or synthetic generators, processes signals into band/envelope streams.
- **Processing:** Each station is handled by a StationProcessor that applies band-pass filtering, envelope detection, seam smoothing, and downsampling.
- **Backend (app.py):** Flask + Socket.IO app that streams live updates, serves HTML templates, and provides a `/raw` diagnostics endpoint.
- **Playback (playback_routes.py):** Blueprint for uploading MiniSEED files, generating timelines, per-station waveforms, and RMS stats.
- **Frontend (templates + static):** Interactive Leaflet map with color-coded station bubbles and a playback UI.


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

---


## Suggestions for Future Development

1. **User Documentation and Help**
   - Add tooltips, help popups, and a dedicated help page in the UI.
   - Provide onboarding guides for new users.

2. **Data Export and Sharing**
   - Enable exporting visualizations and raw data (CSV, PNG, JSON).
   - Allow sharing of playback sessions or map views.

3. **Advanced Filtering and Search**
   - Filter stations by geographic region, seismic intensity, or custom queries.
   - Implement search functionality for station names and locations.

4. **Mobile and Accessibility Support**
   - Optimize frontend for mobile devices and tablets.
   - Improve accessibility (ARIA labels, keyboard navigation).

5. **Performance and Scalability**
   - Implement caching for frequently accessed data.
   - Use asynchronous processing for large MiniSEED files and real-time streams.
   - Consider containerization (Docker) for deployment.

6. **Security Enhancements**
   - Add authentication and authorization for sensitive endpoints.
   - Validate and sanitize uploaded files to prevent malicious input.

7. **Integration and Extensibility**
   - Support additional seismic data sources and formats.
   - Provide API documentation for third-party integration.
   - Modularize frontend components for easier extension.

8. **Visualization Improvements**
   - Add heatmaps, historical trend graphs, and real-time alerting for significant seismic events.
   - Enable annotation and bookmarking of events on the map.

9. **Testing and Quality Assurance**
   - Expand unit and integration tests for backend modules.
   - Add frontend tests for UI components.
