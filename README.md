## Seismic Drilldown Tool

Browser-based viewer for seismic MiniSEED data.

```bash
python serve_data.py
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000) in your browser.

**Options:**  
- **Station** – select station folder.  
- **File/Hour** – choose MiniSEED file (by timestamp).  
- **Channel** – pick channel (HNX, HNY, HNZ).  
- **LOD max points** – control downsampling (default 3000, higher = smoother zoom).  
- **Load** – fetch and plot data.  

**Features:**  
Zoom & pan on waveform, min/max envelope sampling for large files, and toolbar tools (reset, zoom, save, inspect).
