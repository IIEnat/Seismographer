# Seismographer Documentation

## Table of Contents
- [Overview](#overview)
- [How to Use the Website (Basic Users)](#how-to-use-the-website-basic-users)
- [Data Specifications (Technical Users)](#data-specifications-technical-users)
- [Features & Technical Implementation](#features--technical-implementation)
- [Module Breakdown](#module-breakdown)
- [API Endpoints](#api-endpoints)
- [Configuration Reference](#configuration-reference)
- [Project Structure](#project-structure)
- [Suggestions for Future Development](#suggestions-for-future-development)
- [Project Team](#project-team)

---

## Overview

**Seismographer** is an interactive web application for visualizing real-time and historical seismic activity. It is designed for researchers monitoring gravitational waves and seismic events, providing intuitive, color-coded maps and playback features for ground motion data.

- **Real-time Data:** Connects to seismometers using SeedLink and processes streams via ObsPy.
- **Dynamic Mapping:** Visualizes ground motion on an interactive map.
- **Color-coded Intensity:** Seismic intensity is rendered using color gradients for easy interpretation.
- **Live Updates:** The map auto-refreshes as new seismic data arrives.
- **Customisable Views:** Filter by station or time window.

---

## How to Use the Website (Basic Users)

### Getting Started

1. **Installation**
   - Open a terminal and navigate to the `main/` directory.
   - Install dependencies:
     ```
     pip install -r requirements.txt
     ```
   - Start the application:
     ```
     python3 app.py
     ```
   - Open your browser and go to `http://localhost:5000`.

2. **Homepage: Live Seismic Map**
   - View a top-down map showing all active seismic stations.
   - Each station is represented by a bubble; the color indicates current seismic intensity.
   - The map updates automatically as new data arrives.

3. **Interacting with Stations**
   - Click on a station bubble to view details such as location, station ID, and recent readings.
   - Use filter controls to display specific stations or time windows.

4. **Playback Feature**
   - Navigate to the playback page via the navigation bar.
   - Upload a MiniSEED file to analyze historical seismic data.
   - Use the timeline slider to move through the dataset.
   - View per-station waveforms and RMS statistics for selected time slices.

5. **Diagnostics**
   - Access the `/raw` endpoint for a JSON view of the latest raw seismic samples per station (for advanced users).

---

## Data Specifications (Technical Users)

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

---

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
- Registers blueprints (e.g., playback routes).

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

---

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

---

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

## Project Structure

```
Seismographer/
├── README.md
└── main/
    ├── app.py                # Flask application entry point
    ├── config.py             # Configuration parameters
    ├── requirements.txt      # Python dependencies
    ├── python/
    │   ├── ingest.py         # Signal processing logic
    │   ├── location_retrieval.py # Station location management
    │   ├── playback_routes.py    # Playback endpoints and logic
    │   └── receiver.py           # Data ingestion from SeedLink/synthetic sources
    ├── static/
    │   └── css/
    │       └── global.css    # Global CSS styles
    └── templates/
        ├── home.html         # Main map UI
        ├── navbar.html       # Navigation bar
        └── playback.html     # Playback UI
    └── uploads/
        └── *.miniseed        # Uploaded MiniSEED files
```

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

---

## Project Team

| Student Name | Student Number | GitHub Username   |
|--------------|----------------|-------------------|
| Raynard      | 24006703       | IIEnat            |
| Yutong       | 23723494       | amiwaffletoday    |
| Jimmy        | 23661316       | JimmyTanUWA       |
| Aaron        | 23815248       | Attempt27         |
| Andrew       | 23384163       | Andrew-Biggins1   |
| Kathleen     | 24091081       | kathisabella      |

---

For further details, refer to the source code in the `main/` directory and configuration in `config.py`.