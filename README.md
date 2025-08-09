# 🌍 Seismographer - Real Time Seismic Imaging 
Seismographer is an interactive tool that visualizes real-time seismic activity using live data feeds. Built for researchers for monitoring seismic movement, this project translates seismic signals into intuitive color-coded maps, providing a live, top-down view of ground motion as it happens.

## Key Features 
⚡ Real-time Data: Connects to seismic stations using SeedLink and processes streams via ObsPy.  
🗺️ Dynamic Mapping: Visualizes ground motion on an interactive map.  
🎨 Color-coded Intensity: Seismic intensity is rendered using color gradients for easy interpretation.  
🔁 Live Updates: The map auto-refreshes as new seismic data arrives.  
🔍 Customisable Views: Filter by station or time window.  

## Technologies Used
- Frontend: Vite, React, Leaflet.js

- Backend: FastAPI (Python), Uvicorn

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

## How to Run (Linux only)
## THIS CAN BE SIMPLIFIED

1. Clone the repository
```
git clone https://github.com/<your-org>/<your-repo>.git
cd <your-repo>
```

2. Setup Python environment
```
python -m venv venv
source venv/bin/activate 
pip install -r requirements.txt
```

3. Setup Node.js environment
```
cd src
npm install
```

4. Run backend server
```
uvicorn app.main:app --reload
```

5. Run frontend
```cd src
npm run dev
```

## Project Structure (NOT ACCURATE)
```
.
├── research/           # Research files
├── src/                # Frontend code (Vite, React)
│   ├── vite.config.js
│   ├── package.json
│   └── ...
├── backend/            # FastAPI backend code
│   ├── app/
│   │   ├── main.py
│   │   └── ...
├── requirements.txt    # Python dependencies
├── README.md           # This file
└── .gitignore
```


