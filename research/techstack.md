**Backend**
SeedLink + ObsPy → Seedlink continuously receive real-time seismic data streams from stations. ObsPy handles parsing, processing, filtering, and downsampling the data from miniseed.

SQLAlchemy (with a SQL database) → Cache metadata, processed/aggregated data (e.g., per-second averages), and store session info. Raw miniSEED files are NOT stored. 

FastAPI → Exposes REST API endpoints and WebSocket connections. (should be similar to flask in agile)
- REST APIs serve historical or metadata queries.
- WebSockets push live, processed seismic data streams efficiently to frontend clients.

**Frontend**
React → Builds the interactive user interface, manages state, and integrates data visualizations.

Leaflet → Displays interactive maps showing seismic station locations and overlays real-time event markers or data.

D3.js → Creates custom, dynamic waveform/time series visualizations within React components, allowing rich interactivity (zoom, pan, annotations).

**How it flows**
- SeedLink + ObsPy ingest seismic data → process and downsample → store/cache relevant data with SQLAlchemy.
- FastAPI serves as the communication bridge
- REST API for static/historical queries
- WebSocket for streaming live updates
- Uses WebSocket connection to receive live data from FastAPI
- Renders seismic waveforms with D3.js
- Shows station locations and overlays on a Leaflet map
- User interacts with UI for zoom, pan, station selection, and sees near real-time updates.
 