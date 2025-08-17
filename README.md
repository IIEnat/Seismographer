# Realtime MiniSEED Simulator + Map

Simulates seismic stations streaming MiniSEED on different TCP ports and visualizes
per-station **per-second aggregates** (RMS or mean) on a Leaflet map.

- **Sender**: once per second sends **one MiniSEED record** with **250 samples**.
- **Receiver**: computes a **strict per-second aggregate** (no rolling windows) and serves:
  - `/live` → latest per-second value per station
  - `index_map.html` → interactive map UI

---

## Requirements

- Python 3.9+
- Obspy
- Numpy

## Files

```
.
├─ seedlink_multi_sender.py      # Simulator: per-second MiniSEED packets (250 samples each)
├─ seedlink_multi_receiver.py    # Multi-source receiver + HTTP server (/live + static)
├─ index_map.html                # Leaflet frontend (1 km circles, colored by per-second value)
└─ README.md
```

---

## How to Run (PowerShell / Windows)

### 1) Start the sender (3 stations on ports 18001–18003)
```powershell
python .\seedlink_multi_sender.py
```

### 2) Start the receiver (strict per-second aggregation)
```powershell
python .\seedlink_multi_receiver.py --http-port 8081 `
  --source "127.0.0.1:18001@XX.JINJ1..BHZ@-31.9619,115.9488" `
  --source "127.0.0.1:18002@XX.JINJ2..BHZ@-31.9389,115.9670" `
  --source "127.0.0.1:18003@XX.JINJ3..BHZ@-31.9200,115.9900"
```

Options:
- `--metric rms` (default) → root mean square of that second's 250 samples
- `--metric mean` → arithmetic mean of that second's 250 samples

### 3) Open the UI
```
http://127.0.0.1:8081/index_map.html
```

You’ll see:
- 1 km circles at the coordinates you passed via `--source`
- Five fixed colors (Red, Green, Blue, Yellow, Orange) with station-specific offsets
- A tooltip above each station showing the **latest finalized per-second value**

---

## Customization

- **Add stations**: In the sender, pass more ports via `--ports`; in the receiver, add more `--source` entries.
- **Metric**: Switch receiver metric with `--metric rms|mean`.
- **Color legend & labels**: Edit `index_map.html` (`LEVELS`, `COLORS5`) to change thresholds/colors.
- **Circle radius**: `index_map.html` → `CIRCLE_RADIUS_M = 1000` (meters).
- **Port / host**: Change receiver `--http-port` or sender `--host` as needed.

---

## Graceful Shutdown

- `Ctrl + C` in each running terminal.

---

## Notes

- Sender amplitude cycles across five levels each second to demonstrate visible changes.
- Sender waveforms: sine (JINJ1), square (JINJ2), triangle (JINJ3). Add more if desired.
- Receiver computes the value **only from samples within that second**. No interpolation, no averaging-across-seconds.
