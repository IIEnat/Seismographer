# backend/models.py
from pathlib import Path
import aiosqlite

DB_PATH = Path(__file__).parent / "seismo.sqlite"

SCHEMA = """
CREATE TABLE IF NOT EXISTS stations (
  code TEXT PRIMARY KEY,
  name TEXT,
  lat REAL NOT NULL,
  lon REAL NOT NULL,
  elev REAL
);
CREATE TABLE IF NOT EXISTS readings (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  station_code TEXT NOT NULL,
  ts_utc TEXT NOT NULL,
  z_value REAL NOT NULL,
  window_s INTEGER NOT NULL,
  FOREIGN KEY(station_code) REFERENCES stations(code)
);
CREATE INDEX IF NOT EXISTS idx_readings_station_ts ON readings(station_code, ts_utc);
"""

async def open_db():
    db = await aiosqlite.connect(DB_PATH.as_posix())
    await db.execute("PRAGMA journal_mode=WAL;")
    await db.executescript(SCHEMA)
    await db.commit()
    return db
