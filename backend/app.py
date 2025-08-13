# backend/app.py
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

import uvicorn
from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from obspy import read
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from .models import open_db
from .processor import rms_last_window_z

# -----------------------------------------------------------------------------
# Paths / constants
# -----------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
REPO_ROOT = BASE_DIR.parent
DATA_DIR = REPO_ROOT / "data" / "miniseed"
STATIC_DIR = BASE_DIR / "static"      # vite build goes here (outDir)
STATIONS_FILE = BASE_DIR / "stations.json"

WINDOW_SECONDS = 10  # RMS window for Z channel

# -----------------------------------------------------------------------------
# FastAPI app
# -----------------------------------------------------------------------------
app = FastAPI(title="Seismographer")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # lock this down for prod if needed
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global DB handle (aiosqlite connection opened on startup)
DB = None  # type: ignore

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def iso_now() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


async def seed_stations_from_json_if_valid() -> bool:
    """
    Seed stations from stations.json if present & valid.
    Only inserts when table is empty on first run.
    Returns True if json existed (whether or not rows were inserted).
    """
    try:
        raw = STATIONS_FILE.read_text(encoding="utf-8").strip()
        stations = json.loads(raw) if raw else None
    except (FileNotFoundError, json.JSONDecodeError):
        stations = None

    if not stations:
        return False

    async with DB.execute("SELECT COUNT(*) FROM stations") as cur:
        (cnt,) = await cur.fetchone()
    if cnt == 0:
        for s in stations:
            await DB.execute(
                "INSERT OR REPLACE INTO stations(code, name, lat, lon, elev) VALUES (?,?,?,?,?)",
                (
                    s["code"],
                    s.get("name", s["code"]),
                    float(s["lat"]),
                    float(s["lon"]),
                    s.get("elev"),
                ),
            )
        await DB.commit()
    return True


async def seed_stations_from_miniseed_headers() -> None:
    """
    Scan MiniSEED files and insert NET.STA codes with placeholder coords.
    """
    if not DATA_DIR.exists():
        return

    seen: set[str] = set()
    files = list(DATA_DIR.glob("*.mseed")) + list(DATA_DIR.glob("*.miniseed"))
    for p in files:
        try:
            st = read(p.as_posix(), headonly=True)
        except Exception:
            continue
        for tr in st:
            code = f"{tr.stats.network}.{tr.stats.station}".strip(".")
            if not code or code in seen:
                continue
            seen.add(code)
            await DB.execute(
                "INSERT OR IGNORE INTO stations(code, name, lat, lon, elev) VALUES (?,?,?,?,?)",
                (code, tr.stats.station or code, 0.0, 0.0, None),
            )
    if seen:
        await DB.commit()


# -----------------------------------------------------------------------------
# MiniSEED watcher
# -----------------------------------------------------------------------------
class MiniSEEDHandler(FileSystemEventHandler):
    def __init__(self, queue: asyncio.Queue[Path], loop: asyncio.AbstractEventLoop):
        self.queue = queue
        self.loop = loop

    def _maybe_enqueue(self, path_str: str) -> None:
        if path_str.endswith(".mseed") or path_str.endswith(".miniseed"):
            asyncio.run_coroutine_threadsafe(self.queue.put(Path(path_str)), self.loop)

    def on_created(self, ev):
        if not ev.is_directory:
            self._maybe_enqueue(ev.src_path)

    def on_modified(self, ev):
        if not ev.is_directory:
            self._maybe_enqueue(ev.src_path)


def start_watcher(path: Path, queue: asyncio.Queue[Path], loop: asyncio.AbstractEventLoop) -> Observer:
    obs = Observer()
    obs.schedule(MiniSEEDHandler(queue, loop), path.as_posix(), recursive=False)
    obs.start()
    return obs


async def process_events(queue: asyncio.Queue[Path]) -> None:
    """
    Consume modified/created files: compute Z-RMS and store as latest reading.
    """
    while True:
        path = await queue.get()
        try:
            values = rms_last_window_z(path, window_s=WINDOW_SECONDS)  # { "NET.STA": 0.123, ... }
        except Exception:
            values = {}

        if not values:
            continue

        ts = iso_now()
        for sc, val in values.items():
            try:
                await DB.execute(
                    "INSERT INTO readings(station_code, ts_utc, z_value, window_s) VALUES (?,?,?,?)",
                    (sc, ts, float(val), WINDOW_SECONDS),
                )
            except Exception:
                # Ensure station exists (placeholder row if new)
                await DB.execute(
                    "INSERT OR IGNORE INTO stations(code, name, lat, lon, elev) VALUES (?,?,?,?,?)",
                    (sc, sc.split(".")[-1], 0.0, 0.0, None),
                )
                await DB.execute(
                    "INSERT INTO readings(station_code, ts_utc, z_value, window_s) VALUES (?,?,?,?)",
                    (sc, ts, float(val), WINDOW_SECONDS),
                )
        await DB.commit()


# -----------------------------------------------------------------------------
# Lifecycle
# -----------------------------------------------------------------------------
@app.on_event("startup")
async def on_startup():
    global DB
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Open DB and ensure schema (handled in models.open_db)
    DB = await open_db()

    # Prefer stations.json if present; otherwise, infer from MiniSEED headers
    used_json = await seed_stations_from_json_if_valid()
    if not used_json:
        await seed_stations_from_miniseed_headers()

    # Start watcher + worker
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[Path] = asyncio.Queue()
    app.state.queue = queue
    app.state.observer = start_watcher(DATA_DIR, queue, loop)
    app.state.worker = asyncio.create_task(process_events(queue))


@app.on_event("shutdown")
async def on_shutdown():
    # Stop watcher
    obs: Optional[Observer] = getattr(app.state, "observer", None)
    if obs:
        obs.stop()
        obs.join(timeout=2)

    # Stop worker
    worker: Optional[asyncio.Task] = getattr(app.state, "worker", None)
    if worker:
        worker.cancel()
        try:
            await worker
        except Exception:
            pass

    # Close DB
    if DB:
        await DB.close()


# -----------------------------------------------------------------------------
# API routes (under /api)
# -----------------------------------------------------------------------------
api = APIRouter(prefix="/api")


@api.get("/health")
async def api_health():
    return {"status": "ok", "time": iso_now()}


@api.get("/stations")
async def api_stations():
    rows = []
    async with DB.execute("SELECT code, name, lat, lon, elev FROM stations ORDER BY code") as cur:
        async for code, name, lat, lon, elev in cur:
            rows.append(
                {"code": code, "name": name, "lat": float(lat), "lon": float(lon), "elev": elev}
            )
    return rows


@api.get("/readings/latest")
async def api_latest():
    """
    Returns:
      { "NET.STA": {"ts": "...Z", "value": 0.123, "window_s": 10 }, ... }
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
            out[sc] = {"ts": ts, "value": float(val), "window_s": int(win)}
    return out


@api.post("/stations/rescan")
async def api_rescan():
    """
    Manually rescan MiniSEED headers to insert any *new* station codes.
    Useful if new files were added before the app started.
    """
    await seed_stations_from_miniseed_headers()
    return {"ok": True}


app.include_router(api)

# -----------------------------------------------------------------------------
# Static + SPA (built by Vite into backend/static)
# -----------------------------------------------------------------------------
# Serve the built assets (index.html + /assets/*) at the root.
# IMPORTANT: This comes *after* app.include_router(api),
# so that /api/* keeps working.
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="spa")

# Fallback when the frontend hasn't been built yet
@app.get("/__dev", response_class=HTMLResponse)
async def __dev_hint():
    if (STATIC_DIR / "index.html").exists():
        return HTMLResponse("<p>Build exists. Visit <a href='/'>/</a>.</p>")
    return HTMLResponse(
        "<h3>No frontend build found.</h3>"
        "<p>Run: <code>npm --prefix frontend run build</code> to generate <code>backend/static/</code>.</p>"
    )


# -----------------------------------------------------------------------------
# Entrypoint
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    uvicorn.run("backend.app:app", host="0.0.0.0", port=8000, reload=False)
