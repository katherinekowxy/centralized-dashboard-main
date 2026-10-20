"""Site database for the PTW dashboard, Asset dashboard, Calendar overview and Meeting rooms (docs/site-data-contract.md).

Sources write here only through the ingest layer (seed, Excel, PTW PDF; APIs later); the dashboards read only through
the functions below. The one write from a dashboard is a room booking (``book_room``, ``cancel_booking``). Times are stored as UTC ISO strings in one format, so text comparison in SQL is time order.
"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

DEFAULT_DB = Path(__file__).resolve().parents[1] / "data" / "site.sqlite3"

SCHEMA = """
CREATE TABLE IF NOT EXISTS site_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS ingest_batches (batch_id TEXT PRIMARY KEY, source_type TEXT NOT NULL, file_name TEXT,
  sha256 TEXT, received_at TEXT NOT NULL, row_count INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS zones (zone_code TEXT PRIMARY KEY, name TEXT NOT NULL, map_no INTEGER, kind TEXT,
  x0 REAL, y0 REAL, x1 REAL, y1 REAL, geometry TEXT, lat REAL, lon REAL, geo_source TEXT);
CREATE TABLE IF NOT EXISTS contractors (contractor_id TEXT PRIMARY KEY, name TEXT NOT NULL, short_name TEXT,
  colour TEXT NOT NULL, logo_svg TEXT);
CREATE TABLE IF NOT EXISTS assets (asset_id TEXT PRIMARY KEY, name TEXT NOT NULL, zone_code TEXT NOT NULL REFERENCES zones,
  asset_type TEXT NOT NULL, criticality TEXT, fed_from TEXT REFERENCES assets, rated_current_a REAL, idle_current_a REAL,
  operating_hours TEXT, connected INTEGER NOT NULL DEFAULT 1, phases INTEGER, ingest_batch_id TEXT REFERENCES ingest_batches);
CREATE TABLE IF NOT EXISTS asset_aliases (alias TEXT PRIMARY KEY, asset_id TEXT NOT NULL REFERENCES assets, system TEXT);
CREATE TABLE IF NOT EXISTS readings (asset_id TEXT NOT NULL REFERENCES assets, point_id TEXT NOT NULL, observed_at TEXT NOT NULL,
  value REAL, unit TEXT, ingest_batch_id TEXT REFERENCES ingest_batches, PRIMARY KEY (asset_id, point_id, observed_at));
CREATE TABLE IF NOT EXISTS ptws (ptw_id TEXT PRIMARY KEY, zone_code TEXT NOT NULL REFERENCES zones,
  contractor_id TEXT NOT NULL REFERENCES contractors, title TEXT NOT NULL, work_type TEXT, start_at TEXT NOT NULL,
  end_at TEXT NOT NULL, source_file TEXT, ingest_batch_id TEXT REFERENCES ingest_batches);
CREATE TABLE IF NOT EXISTS ptw_impacts (impact_id TEXT PRIMARY KEY, ptw_id TEXT NOT NULL REFERENCES ptws, kind TEXT NOT NULL,
  target_type TEXT NOT NULL, target_id TEXT NOT NULL, effect TEXT, summary TEXT NOT NULL, start_at TEXT NOT NULL, end_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS event_orders (eo_id TEXT PRIMARY KEY, zone_code TEXT NOT NULL REFERENCES zones, title TEXT NOT NULL,
  start_at TEXT NOT NULL, end_at TEXT NOT NULL, organiser TEXT, expected_guests INTEGER, ingest_batch_id TEXT REFERENCES ingest_batches);
CREATE TABLE IF NOT EXISTS work_orders (wo_id TEXT PRIMARY KEY, asset_id TEXT NOT NULL REFERENCES assets, title TEXT NOT NULL,
  scheduled_start TEXT NOT NULL, scheduled_end TEXT NOT NULL, status TEXT NOT NULL, ptw_id TEXT REFERENCES ptws,
  ingest_batch_id TEXT REFERENCES ingest_batches);
CREATE TABLE IF NOT EXISTS event_power (eo_id TEXT NOT NULL REFERENCES event_orders, asset_id TEXT NOT NULL REFERENCES assets,
  use TEXT NOT NULL, ingest_batch_id TEXT REFERENCES ingest_batches, PRIMARY KEY (eo_id, asset_id));
CREATE TABLE IF NOT EXISTS rooms (room_id TEXT PRIMARY KEY, name TEXT NOT NULL, seats INTEGER, location TEXT);
CREATE TABLE IF NOT EXISTS room_bookings (booking_id TEXT PRIMARY KEY, room_id TEXT NOT NULL REFERENCES rooms, title TEXT NOT NULL,
  booked_by TEXT NOT NULL, start_at TEXT NOT NULL, end_at TEXT NOT NULL, source TEXT NOT NULL, created_at TEXT NOT NULL,
  cancelled_at TEXT, ingest_batch_id TEXT REFERENCES ingest_batches);
CREATE INDEX IF NOT EXISTS ptws_window ON ptws (start_at, end_at);
CREATE INDEX IF NOT EXISTS room_bookings_window ON room_bookings (room_id, start_at, end_at);
CREATE INDEX IF NOT EXISTS work_orders_window ON work_orders (scheduled_start, scheduled_end);
"""
TABLES = ("site_meta", "ingest_batches", "zones", "contractors", "assets", "asset_aliases", "readings", "ptws",
          "ptw_impacts", "event_orders", "work_orders", "event_power", "rooms", "room_bookings")


def utc(value: Any) -> str:
    """Any ISO time or datetime as the stored form: UTC, seconds, ``+00:00``. Callers pass times with an offset;
    a naive time is read as UTC (the importers refuse naive times before they get here)."""
    moment = value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
    moment = moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc).replace(microsecond=0).isoformat()


ADDED_COLUMNS = {"zones": {"geometry": "TEXT", "lat": "REAL", "lon": "REAL", "geo_source": "TEXT"},  # 12 October 2026
                 "assets": {"connected": "INTEGER NOT NULL DEFAULT 1", "phases": "INTEGER"}}


def connect(path: Path | str | None = None) -> sqlite3.Connection:
    connection = sqlite3.connect(str(path or DEFAULT_DB), timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(SCHEMA)
    for table, columns in ADDED_COLUMNS.items():  # databases made before a column existed get it added
        present = {row["name"] for row in connection.execute(f"PRAGMA table_info({table})")}
        for column, kind in columns.items():
            if column not in present:
                connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {kind}")
    return connection


def insert(connection: sqlite3.Connection, table: str, rows: Iterable[dict], mode: str = "insert") -> int:
    """Insert rows (dicts with the table's column names); ``mode`` is insert, replace or ignore (on key clashes)."""
    rows = list(rows)
    if table not in TABLES:
        raise ValueError(f"unknown table {table}")
    if not rows:
        return 0
    columns = list(rows[0])
    verb = {"insert": "INSERT", "replace": "INSERT OR REPLACE", "ignore": "INSERT OR IGNORE"}[mode]
    connection.executemany(f"{verb} INTO {table} ({', '.join(columns)}) VALUES ({', '.join('?' * len(columns))})",
                           [tuple(row[column] for column in columns) for row in rows])
    return len(rows)


def _all(sql: str, params: Iterable[Any] = (), path: Path | str | None = None) -> list[dict]:
    with closing(connect(path)) as connection:
        return [dict(row) for row in connection.execute(sql, tuple(params))]


def meta(key: str, path: Path | str | None = None) -> str | None:
    rows = _all("SELECT value FROM site_meta WHERE key = ?", (key,), path)
    return rows[0]["value"] if rows else None


def as_of(path: Path | str | None = None) -> str:
    value = meta("as_of", path)
    if value is None:
        raise LookupError("site database has no as_of; run demo.site_seed.ensure_fresh()")
    return value


def zones(path=None) -> list[dict]:
    return _all("SELECT * FROM zones ORDER BY COALESCE(map_no, 99), zone_code", path=path)


def contractors(path=None) -> list[dict]:
    return _all("SELECT * FROM contractors ORDER BY contractor_id", path=path)


def assets(path=None) -> list[dict]:
    """Every asset in the register. ``connected`` is 0 for a device SignalDesk gets no readings from: it has no state,
    and only the Asset schematic shows it."""
    return _all("SELECT * FROM assets ORDER BY asset_id", path=path)


def latest_readings(path=None) -> dict[str, dict[str, dict]]:
    """Each asset's latest reading per point, as of ``site_meta.as_of``: a reading stamped after "now" never counts."""
    now = meta("as_of", path) or "9999"
    rows = _all("""SELECT r.asset_id, r.point_id, r.value, r.unit, r.observed_at FROM readings r
                   JOIN (SELECT asset_id, point_id, MAX(observed_at) AS last FROM readings WHERE observed_at <= ?
                         GROUP BY asset_id, point_id) x
                   ON r.asset_id = x.asset_id AND r.point_id = x.point_id AND r.observed_at = x.last""", (now,), path)
    out: dict[str, dict[str, dict]] = {}
    for row in rows:
        out.setdefault(row["asset_id"], {})[row["point_id"]] = {"value": row["value"], "unit": row["unit"],
                                                                "observed_at": row["observed_at"]}
    return out


def readings(asset_id: str, start: Any, end: Any, path=None) -> list[dict]:
    return _all("SELECT * FROM readings WHERE asset_id = ? AND observed_at >= ? AND observed_at <= ? ORDER BY observed_at",
                (asset_id, utc(start), utc(end)), path)


def _window(start_col: str, end_col: str, active_at: Any = None, start: Any = None, end: Any = None) -> tuple[str, list]:
    if active_at is not None:
        return f"{start_col} <= ? AND ? < {end_col}", [utc(active_at), utc(active_at)]
    clauses, params = [], []
    if start is not None:
        clauses.append(f"{end_col} > ?")
        params.append(utc(start))
    if end is not None:
        clauses.append(f"{start_col} < ?")
        params.append(utc(end))
    return " AND ".join(clauses) or "1 = 1", params


def _ptw_rows(where: str, params: list, path=None) -> list[dict]:
    rows = _all(f"""SELECT p.*, c.name AS c_name, c.short_name AS c_short_name, c.colour AS c_colour, c.logo_svg AS c_logo_svg,
                    z.name AS z_name, z.map_no AS z_map_no, z.kind AS z_kind, z.x0 AS z_x0, z.y0 AS z_y0, z.x1 AS z_x1, z.y1 AS z_y1,
                    z.geometry AS z_geometry, z.lat AS z_lat, z.lon AS z_lon, z.geo_source AS z_geo_source
                    FROM ptws p JOIN contractors c USING (contractor_id) JOIN zones z USING (zone_code)
                    WHERE {where} ORDER BY p.start_at, p.ptw_id""", params, path)
    out = []
    for row in rows:
        contractor = {"contractor_id": row["contractor_id"], **{key[2:]: row.pop(key) for key in list(row) if key.startswith("c_")}}
        zone = {"zone_code": row["zone_code"], **{key[2:]: row.pop(key) for key in list(row) if key.startswith("z_")}}
        out.append({**row, "contractor": contractor, "zone": zone})
    return out


def ptws(active_at: Any = None, start: Any = None, end: Any = None, path=None) -> list[dict]:
    """Permits active at an instant, or overlapping a window; each with its contractor and zone."""
    where, params = _window("p.start_at", "p.end_at", active_at, start, end)
    return _ptw_rows(where, params, path)


def ptw(ptw_id: str, path=None) -> dict | None:
    rows = _ptw_rows("p.ptw_id = ?", [ptw_id], path)
    if not rows:
        return None
    return {**rows[0], "impacts": _all("SELECT * FROM ptw_impacts WHERE ptw_id = ? ORDER BY impact_id", (ptw_id,), path)}


def impacts(active_at: Any = None, path=None) -> list[dict]:
    where, params = _window("start_at", "end_at", active_at)
    return _all(f"SELECT * FROM ptw_impacts WHERE {where} ORDER BY impact_id", params, path)


def work_orders(start: Any, end: Any, asset_id: str | None = None, path=None) -> list[dict]:
    where, params = _window("w.scheduled_start", "w.scheduled_end", None, start, end)
    if asset_id is not None:
        where, params = f"{where} AND w.asset_id = ?", [*params, asset_id]
    return _all(f"""SELECT w.*, a.name AS asset_name, a.zone_code FROM work_orders w JOIN assets a USING (asset_id)
                    WHERE {where} ORDER BY w.scheduled_start, w.wo_id""", params, path)


def work_order(wo_id: str, path=None) -> dict | None:
    rows = _all("""SELECT w.*, a.name AS asset_name, a.zone_code FROM work_orders w JOIN assets a USING (asset_id)
                   WHERE w.wo_id = ?""", (wo_id,), path)
    return rows[0] if rows else None


def event_orders(start: Any, end: Any, path=None) -> list[dict]:
    where, params = _window("start_at", "end_at", None, start, end)
    return _all(f"SELECT * FROM event_orders WHERE {where} ORDER BY start_at, eo_id", params, path)


def event_order(eo_id: str, path=None) -> dict | None:
    rows = _all("SELECT * FROM event_orders WHERE eo_id = ?", (eo_id,), path)
    return rows[0] if rows else None


def event_power(start: Any = None, end: Any = None, path=None) -> list[dict]:
    """Which CEEform sockets each event has booked, and what for, for events overlapping a window."""
    where, params = _window("e.start_at", "e.end_at", None, start, end)
    return _all(f"""SELECT p.eo_id, p.asset_id, p.use, e.title, e.zone_code, e.start_at, e.end_at
                    FROM event_power p JOIN event_orders e USING (eo_id) WHERE {where} ORDER BY e.start_at, p.asset_id""", params, path)


def rooms(path=None) -> list[dict]:
    return _all("SELECT * FROM rooms ORDER BY room_id", path=path)


def room_bookings(start: Any, end: Any, room_id: str | None = None, path=None) -> list[dict]:
    """Bookings overlapping a window, cancelled ones left out."""
    where, params = _window("start_at", "end_at", None, start, end)
    if room_id is not None:
        where, params = f"{where} AND room_id = ?", [*params, room_id]
    return _all(f"SELECT * FROM room_bookings WHERE {where} AND cancelled_at IS NULL ORDER BY start_at, booking_id", params, path)


class BookingClash(ValueError):
    """The room is already booked for part of that time; ``booking`` is the first booking in the way."""

    def __init__(self, booking: dict):
        super().__init__(f"{booking['room_id']} is booked from {booking['start_at']} to {booking['end_at']}")
        self.booking = booking


def book_room(room_id: str, start: Any, end: Any, title: str, booked_by: str, source: str = "signaldesk",
              path=None) -> dict:
    """Book a room and return the booking, or raise ``BookingClash``. The clash check and the insert share one write
    lock, so two people booking the same slot at once can't both succeed."""
    start, end = utc(start), utc(end)
    title, booked_by = str(title or "").strip(), str(booked_by or "").strip()
    if not start < end:
        raise ValueError("a booking must end after it starts")
    if not title or not booked_by:
        raise ValueError("a booking needs a meeting name and who booked it")
    connection = connect(path)
    try:
        connection.execute("BEGIN IMMEDIATE")
        if connection.execute("SELECT 1 FROM rooms WHERE room_id = ?", (room_id,)).fetchone() is None:
            raise LookupError(f"no room {room_id}")
        clash = connection.execute("""SELECT * FROM room_bookings WHERE room_id = ? AND cancelled_at IS NULL
                                      AND start_at < ? AND ? < end_at ORDER BY start_at LIMIT 1""", (room_id, end, start)).fetchone()
        if clash is not None:
            raise BookingClash(dict(clash))
        number = connection.execute("SELECT COALESCE(MAX(CAST(SUBSTR(booking_id, 4) AS INTEGER)), 0) + 1 FROM room_bookings").fetchone()[0]
        row = {"booking_id": f"RB-{number:04d}", "room_id": room_id, "title": title, "booked_by": booked_by, "start_at": start,
               "end_at": end, "source": source, "created_at": utc(datetime.now(timezone.utc)), "cancelled_at": None,
               "ingest_batch_id": None}
        insert(connection, "room_bookings", [row])
        connection.commit()
        return row
    except BaseException:
        connection.rollback()
        raise
    finally:
        connection.close()


def cancel_booking(booking_id: str, path=None) -> bool:
    """Cancel a booking; the row stays, marked with when it was cancelled. False when there was nothing to cancel."""
    with closing(connect(path)) as connection:
        with connection:
            done = connection.execute("UPDATE room_bookings SET cancelled_at = ? WHERE booking_id = ? AND cancelled_at IS NULL",
                                      (utc(datetime.now(timezone.utc)), booking_id)).rowcount
    return done == 1
