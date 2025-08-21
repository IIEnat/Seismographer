# 🌍 Seismographer - Real Time Seismic Imaging 
Seismographer is an interactive tool that visualizes real-time seismic activity using live data feeds. Built for researchers for monitoring seismic movement, this project translates seismic signals into intuitive color-coded maps, providing a live, top-down view of ground motion as it happens.

## Key Features 
⚡ Real-time Data: Connects to seismic stations using SeedLink and processes streams via ObsPy.  
🗺️ Dynamic Mapping: Visualizes ground motion on an interactive map.  
🎨 Color-coded Intensity: Seismic intensity is rendered using color gradients for easy interpretation.  
🔁 Live Updates: The map auto-refreshes as new seismic data arrives.  
🔍 Customisable Views: Filter by station or time window.  

## Technologies Used
An app built with Electron-Vite and Python. Additionally:
- Frontend: Vite, React, Leaflet.js
- Data Processing: ObsPy
- Data Sources: SeedLink protocol, MiniSEED files

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

### Install

```bash
$ npm install
```

### Development

```bash
$ npm run dev
```

### Build

```bash
# For windows
$ npm run build:win

# For macOS
$ npm run build:mac

# For Linux
$ npm run build:linux
```

## Project Structure
```
app/
├── electron.vite.config.ts
├── package.json
├── tsconfig.json
├── src/
│   ├── main/                      # Electron Main process
│   │   ├── index.ts               # boots Electron, spawns Python receiver, IPC handlers
│   │   └── types.d.ts             # (optional) type defs if needed
│   │
│   ├── preload/                   # Preload bridge (contextIsolation-safe API)
│   │   └── index.ts               # exposes window.api.getData(), .getStations(), etc
│   │
│   └── renderer/                  # React (Vite) frontend
│       ├── App.tsx                # Your map app (uses window.api.*)
│       ├── index.html
│       ├── main.tsx               # React entrypoint
│       └── components/            # (optional split if UI grows)
│
├── python/
│   ├── seedlink_sender.py         # fake SeedLink server (simulates Centaur)
│   ├── seedlink_multi_receiver.py # bridge receiver → JSON (/live, /wave)
│   └── requirements.txt           # (if you want to pin obspy, flask, etc)
│
├── dist/                          # built renderer output (from Vite)
└── out/                           # electron-builder output (packaged app)
```