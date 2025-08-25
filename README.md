# 🌍 Seismographer - Real Time Seismic Imaging 
Seismographer is an interactive tool that visualizes real-time seismic activity using live data feeds. Built for researchers for monitoring seismic movement, this project translates seismic signals into intuitive color-coded maps, providing a live, top-down view of ground motion as it happens.

## Key Features 
⚡ Real-time Data: Connects to seismic stations using SeedLink and processes streams via ObsPy.  
🗺️ Dynamic Mapping: Visualizes ground motion on an interactive map.  
🎨 Color-coded Intensity: Seismic intensity is rendered using color gradients for easy interpretation.  
🔁 Live Updates: The map auto-refreshes as new seismic data arrives.  
🔍 Customisable Views: Filter by station or time window.  

## Technologies Used
A website built using Flask and typical webdev technologies
    - Obspy, numpy, seedlink for data aggregation in Python
    - HTML, CSS, JS for frontend

## 👥 Project Team

| Student Name | Student Number | GitHub Username   |
|--------------|----------------|-------------------|
| Raynard      | 24006703       | IIEnat            |
| Yutong       | 23723494       | amiwaffletoday    |
| Jimmy        | 23661316       | JimmyTanUWA       |
| Aaron        | 23815248       | Attempt27         |
| Andrew       | 23384163       | Andrew-Biggins1   |
| Kathleen     | 24091081       | kathisabella      |

## Project Setup
Install dependencies 
*Note that requirements.txt needs to be updated
```
pip install -U flask obspy numpy
```

Change directory to /main/ and run using
```
flask run
```

## Project Structure
```
.
├─ app.py                         # Flask app; toggles dev vs real ingest
├─ python/
│  ├─ ingest.py                   # SyntheticIngest (dev) + SeedLinkIngest (real)
│  └─ receiver.py                 # Aggregator + Flask blueprint (/live, /wave, /debug/waves)
├─ templates/
│  └─ home.html                   # UI (map + waveform)
└─ static/
   └─ css/
      └─ global.css               # styles
```