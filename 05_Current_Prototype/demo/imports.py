"""Persistent local asset registry and deliberately small vendor CSV importer.

CSV observations are mapped to one canonical asset by an explicit vendor
equipment reference. A preview does not save assets, imports, or readings.
The commit checks everything again inside a transaction, so an old preview
cannot bypass validation or duplicate/conflict checks.
"""

from __future__ import annotations

import csv
import hashlib
import io
import re
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from math import isfinite
from pathlib import Path
from typing import Any

from demo.engine import ASSETS, POINTS


DEFAULT_DB = Path(__file__).resolve().parents[1] / "data" / "imports.sqlite3"
MAX_FILE_BYTES = 2_000_000
MAX_ROWS = 10_000
REQUIRED_COLUMNS = {"equipment_ref", "timestamp", "point", "value", "unit"}
OPTIONAL_COLUMNS = {"operating_mode"}
_ID_PATTERN = re.compile(r"[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*\Z")
_BUILTIN = {asset["asset_id"]: asset for asset in ASSETS}
_TYPE_TEMPLATE = {asset["asset_type"]: POINTS[asset["asset_id"]] for asset in ASSETS}


class ImportValidationError(ValueError):
    """A CSV import failed validation; ``preview`` contains row errors."""

    def __init__(self, preview: dict[str, Any]):
        self.preview = preview
        super().__init__(f"CSV import has {len(preview['errors'])} validation error(s)")


def _connect(db_path: str | Path | None) -> sqlite3.Connection:
    path = Path(db_path) if db_path is not None else DEFAULT_DB
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS assets (
            asset_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            asset_type TEXT NOT NULL,
            location TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS imports (
            import_id INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_id TEXT NOT NULL,
            equipment_ref TEXT NOT NULL,
            filename TEXT NOT NULL,
            source_hash TEXT NOT NULL,
            imported_at TEXT NOT NULL,
            saved_count INTEGER NOT NULL,
            UNIQUE(asset_id, equipment_ref, source_hash)
        );
        CREATE TABLE IF NOT EXISTS equipment_map (
            ref_key TEXT PRIMARY KEY,
            equipment_ref TEXT NOT NULL,
            asset_id TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS readings (
            reading_id TEXT PRIMARY KEY,
            asset_id TEXT NOT NULL,
            asset_ref TEXT NOT NULL,
            point_id TEXT NOT NULL,
            observed_at TEXT NOT NULL,
            ingested_at TEXT NOT NULL,
            value REAL NOT NULL,
            unit TEXT NOT NULL,
            quality TEXT NOT NULL,
            operating_mode TEXT NOT NULL,
            source TEXT NOT NULL,
            schema_version TEXT NOT NULL,
            source_file TEXT NOT NULL,
            source_hash TEXT NOT NULL,
            source_row INTEGER NOT NULL,
            source_equipment_ref TEXT NOT NULL,
            import_id INTEGER NOT NULL REFERENCES imports(import_id),
            UNIQUE(asset_id, point_id, observed_at)
        );
        CREATE INDEX IF NOT EXISTS readings_asset_time ON readings(asset_id, observed_at);
    """)
    # Populate mappings for databases created by earlier versions of this
    # importer. A legacy conflicting reference remains blocked by _evaluate.
    conn.execute("""
        INSERT OR IGNORE INTO equipment_map(ref_key, equipment_ref, asset_id)
        SELECT lower(trim(equipment_ref)), min(equipment_ref), min(asset_id)
        FROM imports GROUP BY lower(trim(equipment_ref))
        HAVING count(DISTINCT asset_id) = 1
    """)
    conn.commit()
    return conn


def _custom_asset(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "asset_id": row["asset_id"], "name": row["name"],
        "asset_type": row["asset_type"], "location": row["location"],
        "criticality": "unspecified", "coverage": "Imported telemetry; no commissioned detector",
        "detector_enabled": False, "aliases": [row["asset_id"]],
    }


def list_assets(db_path: str | Path | None = None) -> list[dict[str, Any]]:
    """Return built-in and user-added assets in the engine's asset shape."""
    with closing(_connect(db_path)) as conn:
        custom = [_custom_asset(row) for row in conn.execute("SELECT * FROM assets ORDER BY asset_id")]
    return [dict(asset) for asset in ASSETS] + custom


def expected_points(asset_type: str) -> dict[str, dict[str, Any]]:
    """Return the point template for a supported equipment type."""
    if asset_type not in _TYPE_TEMPLATE:
        raise ValueError(f"Unsupported asset type: {asset_type}")
    return {point: dict(spec) for point, spec in _TYPE_TEMPLATE[asset_type].items()}


def create_asset(
    asset_id: str, name: str, asset_type: str, location: str,
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    """Save a new canonical asset; IDs cannot shadow built-in IDs or aliases."""
    if not isinstance(asset_id, str) or len(asset_id) > 64 or not _ID_PATTERN.fullmatch(asset_id):
        raise ValueError("Canonical ID must be uppercase letters, numbers and hyphens, starting with a letter")
    for label, value in (("Name", name), ("Location", location)):
        if not isinstance(value, str) or not value.strip() or len(value.strip()) > 200:
            raise ValueError(f"{label} must contain 1–200 characters")
    expected_points(asset_type)
    reserved = {alias.casefold() for asset in ASSETS for alias in asset["aliases"]}
    reserved.add("plant-01")  # Engine's intentionally ambiguous legacy alias.
    if asset_id.casefold() in reserved:
        raise ValueError("Canonical ID conflicts with a built-in asset reference")
    with closing(_connect(db_path)) as conn:
        try:
            conn.execute(
                "INSERT INTO assets(asset_id, name, asset_type, location, created_at) VALUES (?, ?, ?, ?, ?)",
                (asset_id, name.strip(), asset_type, location.strip(), datetime.now(timezone.utc).isoformat()),
            )
        except sqlite3.IntegrityError as exc:
            raise ValueError(f"Canonical ID already exists: {asset_id}") from exc
        conn.commit()
    return next(asset for asset in list_assets(db_path) if asset["asset_id"] == asset_id)


def _asset(conn: sqlite3.Connection, asset_id: str) -> dict[str, Any] | None:
    if asset_id in _BUILTIN:
        return _BUILTIN[asset_id]
    row = conn.execute("SELECT * FROM assets WHERE asset_id = ?", (asset_id,)).fetchone()
    return _custom_asset(row) if row else None


def _payload(content: bytes | str) -> tuple[bytes, str]:
    if isinstance(content, str):
        raw = content.encode("utf-8")
    elif isinstance(content, bytes):
        raw = content
    else:
        raise TypeError("CSV content must be bytes or text")
    if len(raw) > MAX_FILE_BYTES:
        raise ValueError(f"CSV exceeds {MAX_FILE_BYTES} bytes")
    try:
        return raw, raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("CSV must be UTF-8 encoded") from exc


def _timestamp(text: str) -> str:
    try:
        parsed = datetime.fromisoformat(text.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("timestamp must be ISO 8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timestamp requires a timezone offset")
    return parsed.astimezone(timezone.utc).isoformat(timespec="microseconds" if parsed.microsecond else "seconds")


def _same(existing: sqlite3.Row | dict[str, Any], row: dict[str, Any]) -> bool:
    return (float(existing["value"]) == row["value"] and existing["unit"] == row["unit"]
            and existing["operating_mode"] == row["operating_mode"])


def _evaluate(
    conn: sqlite3.Connection, content: bytes | str, asset_id: str, equipment_ref: str, filename: str,
) -> dict[str, Any]:
    raw, decoded = _payload(content)
    clean_filename = str(filename).replace("\\", "/").rsplit("/", 1)[-1].strip()
    if not clean_filename or len(clean_filename) > 255:
        raise ValueError("Filename must contain 1–255 characters")
    source_hash = hashlib.sha256(raw).hexdigest()
    result: dict[str, Any] = {
        "asset_id": asset_id, "equipment_ref": equipment_ref, "filename": clean_filename,
        "source_hash": source_hash, "accepted": [], "errors": [], "duplicates": 0, "total_rows": 0,
    }
    asset = _asset(conn, asset_id)
    if asset is None:
        result["errors"].append({"row": 0, "message": "Unknown canonical asset ID"})
        return result
    if not isinstance(equipment_ref, str) or not equipment_ref.strip() or len(equipment_ref.strip()) > 200:
        result["errors"].append({"row": 0, "message": "Equipment reference is required (up to 200 characters)"})
        return result
    equipment_ref = equipment_ref.strip()
    result["equipment_ref"] = equipment_ref
    ref_key = equipment_ref.casefold()
    builtin_matches = {
        item["asset_id"] for item in ASSETS
        if any(alias.casefold() == ref_key for alias in item["aliases"])
    }
    if ref_key == "plant-01":
        builtin_matches.update({"DB-01", "PUMP-01"})
    if builtin_matches and builtin_matches != {asset_id}:
        result["errors"].append({"row": 0, "message": "Equipment reference belongs to another or ambiguous built-in asset"})
        return result
    custom_owner = conn.execute("SELECT asset_id FROM assets WHERE lower(asset_id) = ?", (ref_key,)).fetchone()
    if custom_owner and custom_owner["asset_id"] != asset_id:
        result["errors"].append({"row": 0, "message": "Equipment reference is another asset's canonical ID"})
        return result
    mapping = conn.execute("SELECT asset_id FROM equipment_map WHERE ref_key = ?", (ref_key,)).fetchone()
    if mapping and mapping["asset_id"] != asset_id:
        result["errors"].append({"row": 0, "message": "Equipment reference is already mapped to another asset"})
        return result
    legacy_owners = {row["asset_id"] for row in conn.execute(
        "SELECT DISTINCT asset_id FROM imports WHERE lower(trim(equipment_ref)) = ?", (ref_key,)
    )}
    if legacy_owners and legacy_owners != {asset_id}:
        result["errors"].append({"row": 0, "message": "Equipment reference is already mapped to another asset"})
        return result
    specs = expected_points(asset["asset_type"])
    try:
        reader = csv.DictReader(io.StringIO(decoded, newline=""), strict=True)
        header = reader.fieldnames
        if not header or len(header) != len(set(header)) or not REQUIRED_COLUMNS <= set(header):
            result["errors"].append({"row": 1, "message": "CSV needs unique equipment_ref,timestamp,point,value,unit columns"})
            return result
        unexpected = set(header) - REQUIRED_COLUMNS - OPTIONAL_COLUMNS
        if unexpected:
            result["errors"].append({"row": 1, "message": f"Unsupported columns: {', '.join(sorted(unexpected))}"})
            return result
        seen: dict[tuple[str, str], dict[str, Any]] = {}
        for row_number, source in enumerate(reader, start=2):
            result["total_rows"] += 1
            if result["total_rows"] > MAX_ROWS:
                result["errors"].append({"row": row_number, "message": f"CSV exceeds {MAX_ROWS} data rows"})
                break
            try:
                if None in source or any(value is None for value in source.values()):
                    raise ValueError("Malformed CSV row")
                if source["equipment_ref"].strip() != equipment_ref:
                    raise ValueError("Equipment reference does not match the selected mapping")
                point_id = source["point"].strip()
                spec = specs.get(point_id)
                if spec is None:
                    raise ValueError(f"Unknown point for {asset['asset_type']}: {point_id}")
                observed_at = _timestamp(source["timestamp"])
                if source["unit"].strip() != spec["unit"]:
                    raise ValueError(f"Wrong unit for {point_id}; expected {spec['unit']}")
                value = float(source["value"])
                if not isfinite(value) or not spec["bounds"][0] <= value <= spec["bounds"][1]:
                    raise ValueError(f"Value outside valid bounds for {point_id}")
                mode = source.get("operating_mode", "unknown").strip() or "unknown"
                if len(mode) > 32 or not re.fullmatch(r"[a-z][a-z0-9_]*", mode):
                    raise ValueError("Operating mode must be a simple lowercase name")
                key = (point_id, observed_at)
                digest = hashlib.sha256(f"{asset_id}\0{point_id}\0{observed_at}".encode()).hexdigest()[:24]
                candidate = {
                    "reading_id": f"IMP-{digest}", "asset_id": asset_id,
                    "asset_ref": equipment_ref, "point_id": point_id,
                    "observed_at": observed_at, "value": value, "unit": spec["unit"],
                    "quality": "good", "operating_mode": mode, "source": "vendor_csv",
                    "schema_version": "1", "source_file": clean_filename,
                    "source_hash": source_hash, "source_row": row_number,
                    "source_equipment_ref": equipment_ref,
                }
                prior = seen.get(key)
                if prior is None:
                    prior = conn.execute(
                        "SELECT value, unit, operating_mode FROM readings WHERE asset_id = ? AND point_id = ? AND observed_at = ?",
                        (asset_id, point_id, observed_at),
                    ).fetchone()
                if prior is not None:
                    if _same(prior, candidate):
                        result["duplicates"] += 1
                    else:
                        raise ValueError("Conflicting reading already exists at this asset, point and timestamp")
                else:
                    seen[key] = candidate
                    result["accepted"].append(candidate)
            except (TypeError, ValueError, OverflowError) as exc:
                result["errors"].append({"row": row_number, "message": str(exc)})
    except csv.Error as exc:
        result["errors"].append({"row": max(1, result["total_rows"] + 2), "message": f"Malformed CSV: {exc}"})
    if result["total_rows"] == 0 and not result["errors"]:
        result["errors"].append({"row": 2, "message": "CSV has no data rows"})
    return result


def preview_csv(
    content: bytes | str, asset_id: str, equipment_ref: str, *,
    filename: str = "vendor.csv", db_path: str | Path | None = None,
) -> dict[str, Any]:
    """Validate without saving observations; every error includes a CSV row."""
    with closing(_connect(db_path)) as conn:
        return _evaluate(conn, content, asset_id, equipment_ref, filename)


def commit_import(
    content: bytes | str, asset_id: str, equipment_ref: str, *,
    filename: str = "vendor.csv", db_path: str | Path | None = None,
) -> dict[str, Any]:
    """Atomically revalidate and save; repeat files/readings are idempotent."""
    conn = _connect(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        preview = _evaluate(conn, content, asset_id, equipment_ref, filename)
        if preview["errors"]:
            raise ImportValidationError(preview)
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "INSERT OR IGNORE INTO equipment_map(ref_key, equipment_ref, asset_id) VALUES (?, ?, ?)",
            (preview["equipment_ref"].casefold(), preview["equipment_ref"], asset_id),
        )
        existing = conn.execute(
            "SELECT import_id FROM imports WHERE asset_id = ? AND equipment_ref = ? AND source_hash = ?",
            (asset_id, preview["equipment_ref"], preview["source_hash"]),
        ).fetchone()
        if existing is None:
            cursor = conn.execute(
                "INSERT INTO imports(asset_id, equipment_ref, filename, source_hash, imported_at, saved_count) VALUES (?, ?, ?, ?, ?, ?)",
                (asset_id, preview["equipment_ref"], preview["filename"], preview["source_hash"], now, len(preview["accepted"])),
            )
            import_id = cursor.lastrowid
        else:
            import_id = existing["import_id"]
        for row in preview["accepted"]:
            conn.execute(
                """INSERT INTO readings(reading_id, asset_id, asset_ref, point_id, observed_at, ingested_at,
                   value, unit, quality, operating_mode, source, schema_version, source_file, source_hash,
                   source_row, source_equipment_ref, import_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (row["reading_id"], row["asset_id"], row["asset_ref"], row["point_id"], row["observed_at"], now,
                 row["value"], row["unit"], row["quality"], row["operating_mode"], row["source"],
                 row["schema_version"], row["source_file"], row["source_hash"], row["source_row"],
                 row["source_equipment_ref"], import_id),
            )
        conn.commit()
        return {
            "import_id": import_id, "saved": len(preview["accepted"]), "skipped": preview["duplicates"],
            "total_rows": preview["total_rows"], "source_hash": preview["source_hash"],
            "filename": preview["filename"], "asset_id": asset_id,
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def list_readings(asset_id: str, db_path: str | Path | None = None) -> list[dict[str, Any]]:
    """Return stored observations with file, row, hash and vendor reference."""
    with closing(_connect(db_path)) as conn:
        return [dict(row) for row in conn.execute(
            "SELECT * FROM readings WHERE asset_id = ? ORDER BY observed_at, point_id", (asset_id,),
        )]


def list_imports(asset_id: str | None = None, db_path: str | Path | None = None) -> list[dict[str, Any]]:
    """Return provenance and save counts for prior import files."""
    with closing(_connect(db_path)) as conn:
        if asset_id is None:
            rows = conn.execute("SELECT * FROM imports ORDER BY import_id DESC")
        else:
            rows = conn.execute("SELECT * FROM imports WHERE asset_id = ? ORDER BY import_id DESC", (asset_id,))
        return [dict(row) for row in rows]
