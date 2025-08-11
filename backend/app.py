# backend/app.py
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Set

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from obspy import read
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from .models import open_db
from .processor import rms_last_window_z

# -----------------------------------------------------------------------------
# Paths / constants
# -----------------------------------------------------------------------------
BASE = Path(__file__).resolve().parent
DATA_DIR = BASE.parent / "data" / "miniseed"
STATIONS_FILE = BASE / "stations.json"

# -----------------------------------------------------------------------------
# FastAPI app
# -----------------------------------------------------------------------------
app = FastAPI(title="Seismographer REST")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve /static if you want to drop images/css later
app.mount("/static", StaticFiles(directory=BASE / "static", html=False), name="static")

# Globals
DB = None  # aiosqlite connection
# We use REST polling on the frontend, so no websocket client set needed.

# -----------------------------------------------------------------------------
# Utilities
# -----------------------------------------------------------------------------
async def seed_stations_from_json_if_valid() -> bool:
    """Seed stations from stations.json if present & valid. Returns True if seeded/exists."""
    try:
        raw = (STATIONS_FILE).read_text(encoding="utf-8").strip()
        stations = json.loads(raw) if raw else None
    except (FileNotFoundError, json.JSONDecodeError):
        stations = None

    if not stations:
        return False

    # Insert only if table is empty (first-time startup)
    async with DB.execute("SELECT COUNT(*) FROM stations") as cur:
        (cnt,) = await cur.fetchone()
    if cnt == 0:
        for s in stations:
            await DB.execute(
                "INSERT OR REPLACE INTO stations(code, name, lat, lon, elev) VALUES (?,?,?,?,?)",
                (s["code"], s.get("name", s["code"]), s["lat"], s["lon"], s.get("elev")),
            )
        await DB.commit()
    return True


async def seed_stations_from_miniseed_headers():
    """Scan MiniSEED files and insert NET.STA codes with placeholder coords."""
    seen = set()
    if not DATA_DIR.exists():
        return

    files = list(DATA_DIR.glob("*.mseed")) + list(DATA_DIR.glob("*.miniseed"))
    for p in files:
        try:
            st = read(p.as_posix(), headonly=True)
        except Exception:
            continue
        for tr in st:
            code = f"{tr.stats.network}.{tr.stats.station}"
            if not code or code in seen:
                continue
            seen.add(code)
            await DB.execute(
                "INSERT OR IGNORE INTO stations(code, name, lat, lon, elev) VALUES (?,?,?,?,?)",
                (code, tr.stats.station or code, 0.0, 0.0, None),
            )
    if seen:
        await DB.commit()


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


# -----------------------------------------------------------------------------
# Directory watcher: process MiniSEED updates
# -----------------------------------------------------------------------------
class MiniSEEDHandler(FileSystemEventHandler):
    def __init__(self, queue: asyncio.Queue):
        self.queue = queue

    def on_created(self, ev):
        if not ev.is_directory and (ev.src_path.endswith(".mseed") or ev.src_path.endswith(".miniseed")):
            asyncio.run_coroutine_threadsafe(self.queue.put(Path(ev.src_path)), asyncio.get_event_loop())

    def on_modified(self, ev):
        self.on_created(ev)


def start_watcher(path: Path, queue: asyncio.Queue) -> Observer:
    obs = Observer()
    obs.schedule(MiniSEEDHandler(queue), path.as_posix(), recursive=False)
    obs.start()
    return obs


async def process_events(queue: asyncio.Queue):
    """Consume modified/created files: compute Z-RMS and store as latest reading."""
    while True:
        path: Path = await queue.get()
        try:
            values = rms_last_window_z(path, window_s=10)  # { "GG.WAR8": 0.123, ... }
        except Exception:
            values = {}
        if not values:
            continue

        ts = iso_now()
        for sc, val in values.items():
            try:
                await DB.execute(
                    "INSERT INTO readings(station_code, ts_utc, z_value, window_s) VALUES (?,?,?,?)",
                    (sc, ts, float(val), 10),
                )
            except Exception:
                # If station code doesn't exist yet (new station), insert placeholder row.
                await DB.execute(
                    "INSERT OR IGNORE INTO stations(code, name, lat, lon, elev) VALUES (?,?,?,?,?)",
                    (sc, sc.split(".")[-1], 0.0, 0.0, None),
                )
                await DB.execute(
                    "INSERT INTO readings(station_code, ts_utc, z_value, window_s) VALUES (?,?,?,?)",
                    (sc, ts, float(val), 10),
                )
        await DB.commit()


# -----------------------------------------------------------------------------
# Lifecycle
# -----------------------------------------------------------------------------
@app.on_event("startup")
async def on_startup():
    global DB
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    # open DB and ensure schema (see backend/models.py)
    DB = await open_db()

    # Prefer stations.json if valid, else discover from MiniSEED headers
    used_json = await seed_stations_from_json_if_valid()
    if not used_json:
        await seed_stations_from_miniseed_headers()

    # Start file watcher + worker
    app.state.queue = asyncio.Queue()
    app.state.observer = start_watcher(DATA_DIR, app.state.queue)
    app.state.worker = asyncio.create_task(process_events(app.state.queue))


@app.on_event("shutdown")
async def on_shutdown():
    # stop watcher
    obs: Observer | None = getattr(app.state, "observer", None)
    if obs:
        obs.stop()
        obs.join(timeout=2)
    # stop worker
    worker: asyncio.Task | None = getattr(app.state, "worker", None)
    if worker:
        worker.cancel()
        try:
            await worker
        except Exception:
            pass
    # close DB
    if DB:
        await DB.close()


# -----------------------------------------------------------------------------
# Pages
# -----------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
async def index():
    index_html = BASE / "templates" / "index.html"
    if index_html.exists():
        return index_html.read_text(encoding="utf-8")
    # Fallback minimal page if template isn't present
    return HTMLResponse("<h3>Seismographer API is running. Add backend/templates/index.html for the map UI.</h3>")


# -----------------------------------------------------------------------------
# REST endpoints
# -----------------------------------------------------------------------------
@app.get("/api/stations")
async def api_stations():
    rows = []
    async with DB.execute("SELECT code, name, lat, lon, elev FROM stations ORDER BY code") as cur:
        async for code, name, lat, lon, elev in cur:
            rows.append({"code": code, "name": name, "lat": lat, "lon": lon, "elev": elev})
    return rows


@app.get("/api/readings/latest")
async def api_latest():
    """
    Returns { "GG.WAR8": {"ts": "...Z", "value": 0.123, "window_s": 10 }, ... }
    """
    q = """
    SELECT r.station_code, r.ts_utc, r.z_value, r.window_s
    FROM readings r
    JOIN (
      SELECT station_code, MAX(ts_utc) AS mx
      FROM readings
      GROUP BY station_code
    ) x ON x.station_code = r.station_code AND x.mx = r.ts_utc
    """
    out: Dict[str, Dict] = {}
    async with DB.execute(q) as cur:
        async for sc, ts, val, win in cur:
            out[sc] = {"ts": ts, "value": val, "window_s": win}
    return out


@app.post("/api/stations/rescan")
async def api_rescan():
    """
    Manually rescan MiniSEED headers to insert any *new* station codes.
    Useful if new files were added before the app started.
    """
    await seed_stations_from_miniseed_headers()
    return {"ok": True}


# -----------------------------------------------------------------------------
# Entrypoint
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    uvicorn.run("backend.app:app", host="127.0.0.1", port=8000, reload=False)
