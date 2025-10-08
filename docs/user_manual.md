# Seismographer User Manual

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
