"""Diagnostic status dots for SignalDesk cards.

Dots are diagnostic, never predictive (Dan, 5 October 2026: "keep it
diagnostic. red and green"). Red: a detector finding cites this point, or the
relay tripped. Green: the asset has a detector, the data is current, and there
is no finding. Hollow grey: not assessed, or data missing or stale. An unusual
reading on its own never changes a dot. Only demo.engine raises findings.

Each point also carries a typical band (the 5th-95th percentile of the first
24 hours of accepted readings, in the same operating mode as the latest
reading). It is shaded on charts as context only and does not affect status.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from demo.engine import DETECTOR_ASSET_IDS


BASELINE_HOURS = 24
MIN_BASELINE = 6

STATUS_ORDER = {"alert": 0, "ok": 1, "idle": 2}
FINDING_CATEGORIES = {"condition", "trip"}

_UNITS = {"ma": "mA", "kpa": "kPa", "kw": "kW", "c": "°C", "v": "V", "a": "A", "mm_s": "mm/s", "l_s": "L/s"}
_NAMES = {"relay_trip": "Relay trip", "leakage_ma": "Earth leakage"}


def point_name(point_id: str) -> str:
    """Human label without the unit suffix, e.g. 'differential_pressure_kpa' -> 'Differential pressure'."""
    if point_id in _NAMES:
        return _NAMES[point_id]
    stem = point_id
    for suffix in sorted(_UNITS, key=len, reverse=True):
        if stem.endswith("_" + suffix):
            stem = stem[: -len(suffix) - 1]
            break
    return stem.replace("_", " ").capitalize()


def point_unit(point_id: str, unit: str | None = None) -> str:
    for suffix in sorted(_UNITS, key=len, reverse=True):
        if point_id.endswith("_" + suffix):
            return _UNITS[suffix]
    return unit or ""


def detector_covered(bucket: dict[str, Any]) -> bool:
    asset = bucket.get("asset", {})
    return bool(asset.get("detector_enabled", asset.get("asset_id") in DETECTOR_ASSET_IDS))


def _finding_points(bucket: dict[str, Any]) -> set[str]:
    cited = {eid for case in bucket.get("cases", []) if case.get("category") in FINDING_CATEGORIES
             for eid in case.get("evidence_ids") or []}
    return {row["point_id"] for row in bucket.get("readings", []) if row.get("reading_id") in cited}


def point_signals(bucket: dict[str, Any]) -> pd.DataFrame:
    """One row per registered point: latest value, typical band (context) and diagnostic dot."""
    covered = detector_covered(bucket)
    in_finding = _finding_points(bucket)
    readings = pd.DataFrame(bucket.get("readings", []))
    if not readings.empty:
        readings["observed_at"] = pd.to_datetime(readings["observed_at"], utc=True)
        readings["value"] = pd.to_numeric(readings["value"], errors="coerce")
        readings = readings.dropna(subset=["value"])
        start = readings["observed_at"].min()
    rows = []
    for point_id, data in bucket.get("points", {}).items():
        latest = data.get("latest") or {}
        value = pd.to_numeric(latest.get("value"), errors="coerce")
        row = {"point_id": point_id, "name": point_name(point_id), "unit": point_unit(point_id, data.get("unit")),
               "section": data.get("section"), "freshness": data.get("freshness"), "latest": value,
               "observed_at": latest.get("observed_at"), "mode": latest.get("operating_mode"),
               "low": None, "high": None, "median": None, "deviation": None, "recent_max": None, "last_trip_at": None,
               "covered": covered, "in_finding": point_id in in_finding}
        stream = readings[readings["point_id"].eq(point_id)] if not readings.empty else readings
        if not stream.empty:
            recent = stream[stream["observed_at"].ge(stream["observed_at"].max() - pd.Timedelta(hours=BASELINE_HOURS))]
            row["recent_max"] = recent["value"].max()
            trips = recent[recent["value"].eq(1)]
            if not trips.empty:
                row["last_trip_at"] = trips["observed_at"].max()
        if not stream.empty and pd.notna(value):
            base = stream[stream["observed_at"].le(start + pd.Timedelta(hours=BASELINE_HOURS))
                          & stream["operating_mode"].eq(row["mode"])]["value"]
            if len(base) >= MIN_BASELINE:
                low, high, median = base.quantile(.05), base.quantile(.95), base.median()
                width = max(high - low, abs(median) * .05, 1e-6)
                row.update(low=low, high=high, median=median, deviation=(value - median) / width)
        row["status"], row["note"] = _status(point_id, row)
        rows.append(row)
    return pd.DataFrame(rows)


def _status(point_id: str, row: dict[str, Any]) -> tuple[str, str]:
    if row["freshness"] == "missing" or pd.isna(row["latest"]):
        return "idle", "No data"
    if row["freshness"] == "stale":
        return "idle", "Stale"
    if point_id == "relay_trip":
        if row["latest"] == 1:
            return "alert", "Tripped"
        if row.get("last_trip_at") is not None:
            return "alert", f"Tripped {row['last_trip_at']:%d %b %H:%M} · now clear"
    if row.get("in_finding"):
        return "alert", "In detector finding"
    if not row.get("covered"):
        return "idle", "Not assessed"
    return "ok", "No finding"


def asset_status(bucket: dict[str, Any], signals: pd.DataFrame) -> dict[str, Any]:
    """Headline dot for a card: red finding, green checked, grey cannot tell."""
    findings = [case for case in bucket.get("cases", []) if case.get("category") in FINDING_CATEGORIES]
    feed = bucket.get("freshness")
    if findings:
        return {"status": "alert", "headline": findings[0].get("title", "Detector finding"), "rank": 0}
    if not signals.empty and signals["status"].eq("alert").any():
        return {"status": "alert", "headline": "Relay tripped", "rank": 0}
    if not detector_covered(bucket):
        return {"status": "idle", "headline": "Not assessed by a detector", "rank": 3}
    if feed != "fresh":
        return {"status": "idle", "headline": f"Data feed {feed}; cannot assess", "rank": 1}
    if any(case.get("category") in {"data_quality", "insufficient_evidence"} for case in bucket.get("cases", [])):
        return {"status": "idle", "headline": "Source data issue; cannot fully assess", "rank": 1}
    return {"status": "ok", "headline": "No detector finding", "rank": 2}
