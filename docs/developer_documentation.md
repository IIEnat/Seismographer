<!-- If you can read this you are viewing this document as unrendered markdown.  For readability view this document on Github or use one of the many widely available tools to render it as a PDF. -->

# Seismographer - Developer Documentation

## Project Structure
See [README.md](../README.md)

## Technical Stack

- **Backend:**
  - Python
    - Flask server.
    - ObsPy for handling seedlink data.
    - NumPy for calculations.
    - SciPy for data filtering.
    - Modular design:
      - `receiver.py`: Connects to SeedLink or synthetic generators, processes signals.
      - `ingest.py`: Handles band/envelope streams and signal processing.
      - `location_retrieval.py`: Retrieves and manages station location data.
      - `playback_routes.py`: Implements playback features and endpoints.

- **Frontend:**
  - HTML, CSS, JavaScript.
  - Leaflet for interactive mapping.
  - Custom CSS for UI styling.
  - Templates:
    - `home.html`: Main map and live view.
    - `navbar.html`: Navigation bar.
    - `playback.html`: Playback UI for historical data.

## Module Breakdown

### `app.py`
- Entry point for the Flask application.
- Sets up routes for the homepage, playback, and diagnostics.
- Integrates Socket.IO for real-time updates.
- Loads configuration from `config.py`.
- Registers blueprints (e.g. playback routes).

### `config.py`
- Centralizes all tuneable parameters (see Configuration Reference below for details):

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

| Endpoint                                           | Method   | Description                                    |
|----------------------------------------------------|----------|------------------------------------------------|
| `/`                                                | GET      | Live seismic map UI.                           |
| `/raw`                                             | GET      | Latest raw seismic samples per station (JSON). |
| `/playback`                                        | GET/POST | Playback UI (upload MiniSEED file).            |
| `/playback_json/<filenames>`                       | GET      | Per-station compact JSON (band/envelope).      |
| `/playback_timeline/<filenames>`                   | GET      | Global start/end times + slider steps.         |
| `/playback_data/<filenames>/<slider>`              | GET      | Per-station RMS for current second.            |
| `/playback_wave/<filenames>/<slider>/<station_id>` | GET      | 1-second waveform slice.                       |
| `/playback_stats/<filenames>`                      | GET      | Global min/max RMS across dataset.             |

## Configuration Reference

All tuneable parameters are set in [`config.py`](../main/config.py):

- **Station Connectivity:**
  - `HOSTS`: List containing SeedLink host IP `string`s.
  - `NET`: Network code `string`.
  - `CHAN`: Channel code `string`.

- **Simulation:**
  - `SIMULATE`: Whether to use real or simulated data.  Can be set with a `bool` but any other value (i.e. "auto") will attempt real first before defaulting to simulated.
  - `COORDS`: Demo coordinates for simulated running.  Takes a `dict` with station name `string`s as keys and a `tuple` containing latitude and longitude in decimal degrees form (`float`s) as values.

- **Sampling and Filtering:**
  - `FS`: Native sampling rate of instruments.  Number of Hz as a `float`.
  - `BAND`: `tuple` containing the minimum and maximum Hz the band-pass filter will let through.
  - `TARGET_HZ`: Downsample rate for UI envelope streaming.  Takes a `float` for number of Hz.
  - `QSIZE`: Size of circular queue used for enveloping.  Takes an `int`.
  - `MIN_PEAK_DIST_SEC`: Minimum distance between peaks (`float`).  Calculated from `BAND`.

- **Startup Buffering:**
  - `BATCH_SECONDS`: Buffer duration for batch processing.  Initial processing window `int` in seconds.
  - `STARTUP_SECONDS`: Countdown shown to frontend on startup.  Takes an `int` for number of seconds, but should normally be equal to `BATCH_SECONDS`.

- **Seam Smoothing:**
  - `PATCH_TAIL_SECONDS`: Number of seconds as `float` from previous block of data to stitch together with the next block to smooth reduce edge artefacts.
  - `PATCH_INTERVAL_SECONDS`: Interval of how often patching is done.  Takes `float` for number of seconds.

- **UI:**
  - `FRONTEND_FORCE_REDRAW_SECONDS`: UI redraw safety interval.  Takes an `int` for number of seconds.
  - `STATION_RADIUS`: Controls the size the stations as they will appear on map.  Takes an `int` for number of meters.

- **Miscellaneous:**
  - `RAW_SECONDS`: `int` for number of seconds of waveform history kept in `/raw` endpoint.
  - `SPEED_FACTOR`: Multiplier for how fast playback should occur.  Takes a `float`

## Tests
Automated tests are provided in the `main/tests/` directory to ensure reliability and correctness of some of the core functionality. All tests use the `pytest` framework.

- **`conftest.py`**  
  Contains shared fixtures and setup code for use across multiple test files. This includes sample data generation and configuration overrides.

- **`test_location_fallbacks.py`**  
  Verifies the logic for fallback when retrieving station locations and primary sources are unavailable. Ensures correct handling of missing or malformed location data.

- **`test_playback_upload.py`**  
  Tests the upload and handling of MiniSEED files in playback mode. Checks file validation, error handling, and correct parsing of seismic data for playback.

- **`test_rms.py`**  
  Validates the RMS calculation functions used for signal amplitude analysis. Includes tests for edge cases, such as empty or constant signals, and compares results against expected values.

## Suggestions for Future Development

- **User Experience**
  - Add tooltips, help pop-ups, and a dedicated manual page within the application.
  - Create a single executable file that can elegantly run the server and open it in a browser.

- **Functionality**
  - Implement a database to save the live seismic streams.
  - Use a gradient colour overlay on the map instead of individually coloured stations to better visualise waves.
  - Implement a conversion from the meaningless voltage measures given by seismometers (and currently displayed) to displacement in micrometres.
