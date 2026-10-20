"""Asset-scoped, evidence-only data for the SignalDesk overview."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from demo.engine import ASSETS, POINTS, DETECTOR_ASSET_IDS


_ASSETS = {asset["asset_id"]: asset for asset in ASSETS}


def _time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timestamps require a UTC offset")
    return parsed.astimezone(timezone.utc)


def _section(point_id: str, quantity: str) -> str:
    if point_id in {"bearing_temp_c", "vibration_mm_s"}:
        return "Mechanical"
    if point_id in {"relay_trip", "leakage_ma"} or any(
        term in quantity for term in ("current", "voltage", "electrical_power", "trip_state")
    ):
        return "Electrical"
    return "Process"


def _cutoff(run: dict[str, Any], readings: list[dict[str, Any]]) -> datetime:
    value = run.get("as_of") or run.get("analysis", {}).get("metrics", {}).get("as_of")
    if value:
        return _time(value)
    if readings:
        return max(_time(row["observed_at"]) for row in readings)
    raise ValueError("run needs a replay as_of when there are no accepted readings")


def _mode_events(readings: list[dict[str, Any]], asset_id: str) -> list[dict[str, Any]]:
    by_time: dict[datetime, list[dict[str, Any]]] = {}
    for row in readings:
        by_time.setdefault(_time(row["observed_at"]), []).append(row)

    changes: list[dict[str, Any]] = []
    previous: str | None = None
    for at, rows in sorted(by_time.items()):
        modes = {row.get("operating_mode") for row in rows}
        if len(modes) != 1:
            previous = None  # Conflicting observations cannot establish a transition.
            continue
        mode = modes.pop()
        if not isinstance(mode, str) or mode == previous:
            continue
        kind = "start" if mode == "running" and previous is not None else "stop" if previous == "running" else "state"
        changes.append({
            "event_id": f"MODE:{asset_id}:{at.isoformat()}", "asset_id": asset_id,
            "source_id": rows[0]["reading_id"],
            "event_type": kind, "title": f"Operating mode: {mode}",
            "start_at": at.isoformat(), "end_at": None, "status": mode,
            "source": "accepted_telemetry", "source_ids": [row["reading_id"] for row in rows],
            "record": rows,
        })
        previous = mode
    for current, following in zip(changes, changes[1:]):
        current["end_at"] = following["start_at"]
    return changes


def build_asset_bucket(
    run: dict[str, Any], asset_id: str, *,
    asset_catalog: dict[str, dict[str, Any]] | None = None,
    point_catalog: dict[str, dict[str, dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    """Join one registered asset's accepted evidence at the replay cutoff.

    Current telemetry is assessed against each expected point's own cadence.
    Historical CMMS rows and fixture-only equipment never imply detector coverage.
    """
    assets = _ASSETS if asset_catalog is None else asset_catalog
    catalog = POINTS if point_catalog is None else point_catalog
    if asset_id not in assets or asset_id not in catalog:
        raise ValueError(f"Unknown asset: {asset_id}")
    analysis = run.get("analysis", {})
    imported = run.get("imported_readings", [])
    custom_asset = asset_id not in _ASSETS
    source_rows = imported if custom_asset else analysis.get("accepted", [])
    readings = sorted(
        (row for row in source_rows if row.get("asset_id") == asset_id),
        key=lambda row: (_time(row["observed_at"]), row.get("point_id", "")),
    )
    cutoff = max((_time(row["observed_at"]) for row in readings), default=_cutoff(run, [])) if custom_asset else _cutoff(run, readings)
    # An accepted record later than the requested replay instant is not yet visible.
    readings = [row for row in readings if _time(row["observed_at"]) <= cutoff]
    cases = [] if custom_asset else [row for row in analysis.get("cases", []) if row.get("asset_id") == asset_id]
    work_orders = []
    for row in run.get("history", []):
        if row.get("asset_id") != asset_id or _time(row["reported_at"]) > cutoff:
            continue
        closed_at = row.get("closed_at")
        if closed_at and _time(closed_at) > cutoff:
            # A future closure is not part of this replay's observed history.
            work_orders.append({**row, "status": "open", "closed_at": None,
                                "resolution": None, "downtime_hours": 0.0,
                                "source_record": row})
        else:
            work_orders.append(row)

    points: dict[str, dict[str, Any]] = {}
    for point_id, spec in catalog[asset_id].items():
        stream = [row for row in readings if row.get("point_id") == point_id]
        latest = stream[-1] if stream else None
        if latest is None:
            freshness = "missing"
        elif cutoff - _time(latest["observed_at"]) <= timedelta(seconds=spec["cadence_s"] * 1.5):
            freshness = "fresh"
        else:
            freshness = "stale"
        points[point_id] = {
            "section": _section(point_id, spec["quantity"]),
            "unit": spec["unit"], "latest": latest, "freshness": freshness,
        }

    states = {item["freshness"] for item in points.values()}
    if states == {"fresh"}:
        freshness = "fresh"
    elif "fresh" in states:
        freshness = "partial"
    elif "stale" in states:
        freshness = "stale"
    else:
        freshness = "missing"

    latest_modes = {item["latest"].get("operating_mode") for item in points.values() if item["latest"]}
    operating_state = next(iter(latest_modes)) if freshness == "fresh" and len(latest_modes) == 1 else "unknown"
    if not isinstance(operating_state, str) or not operating_state:
        operating_state = "unknown"

    if asset_id not in DETECTOR_ASSET_IDS:
        condition_label = "Not assessed"
    elif any(case.get("category") in {"condition", "trip"} for case in cases):
        condition_label = "Detector finding"
    elif any(case.get("category") == "insufficient_evidence" for case in cases):
        condition_label = "Insufficient detector evidence"
    elif freshness != "fresh":
        condition_label = "Data incomplete"
    else:
        condition_label = "No current alert"

    events: list[dict[str, Any]] = []
    seen_replay_ids: set[str] = set()
    for row in run.get("dataset", {}).get("events", []):
        if not isinstance(row, dict) or row.get("asset_id") != asset_id:
            continue
        try:
            if (_time(row["reported_at"]) > cutoff or _time(row["start_at"]) > _time(row["end_at"])):
                continue
            event_id, event_type, title, status = (row[key] for key in ("event_id", "event_type", "title", "status"))
        except (KeyError, TypeError, ValueError, AttributeError):
            # Raw replay events can include malformed rows held by analysis.
            continue
        valid_status = {"ptw": {"planned", "active", "closed", "cancelled"},
                        "cmms": {"open", "in_progress", "completed", "cancelled"}}
        if (not isinstance(event_id, str) or not event_id.strip() or event_id in seen_replay_ids
                or not isinstance(title, str) or not isinstance(event_type, str)
                or event_type not in valid_status or not isinstance(status, str)
                or status not in valid_status[event_type]):
            continue
        seen_replay_ids.add(event_id)
        events.append({
            "event_id": event_id, "source_id": event_id, "asset_id": asset_id,
            "event_type": event_type, "title": title,
            "start_at": row["start_at"], "end_at": row.get("end_at"),
            "status": status, "source": "replay_event", "record": row,
        })
    for row in work_orders:
        if _time(row["reported_at"]) > cutoff:
            continue
        events.append({
            "event_id": f"WO:{row['work_order_id']}", "source_id": row["work_order_id"],
            "asset_id": asset_id, "event_type": "work_order", "title": row["title"],
            "start_at": row["reported_at"], "end_at": row.get("closed_at"),
            "status": row["status"], "source": "cmms_history", "record": row.get("source_record", row),
        })
    for row in cases:
        if row.get("category") == "context":
            continue  # Its underlying CMMS/PTW event already appears above.
        events.append({
            "event_id": f"CASE:{row['case_id']}", "source_id": row["case_id"],
            "asset_id": asset_id, "event_type": "detector_case", "title": row["title"],
            "start_at": row["start_at"], "end_at": row.get("end_at"),
            "status": row["category"], "source": "analysis", "record": row,
        })
    events.extend(_mode_events(readings, asset_id))
    events.sort(key=lambda row: (_time(row["start_at"]), row["event_id"]))
    return {
        "asset": assets[asset_id], "readings": readings, "cases": cases,
        "work_orders": work_orders, "events": events, "points": points,
        "as_of": cutoff.isoformat(), "point_specs": catalog[asset_id],
        "freshness": freshness, "operating_state": operating_state,
        "condition_label": condition_label,
    }


def filter_events(events: list[dict[str, Any]], start: str, end: str) -> list[dict[str, Any]]:
    """Return events whose recorded interval intersects an inclusive time range."""
    beginning, ending = _time(start), _time(end)
    if ending < beginning:
        raise ValueError("end precedes start")
    return [
        event for event in events
        if _time(event["start_at"]) <= ending
        and (event.get("end_at") is None or _time(event["end_at"]) >= beginning)
    ]


def point_series(bucket: dict[str, Any], point_id: str, start: str, end: str) -> list[dict[str, Any]]:
    """Return one point's accepted records within an inclusive time range."""
    if point_id not in bucket["points"]:
        raise ValueError(f"Unknown point: {point_id}")
    beginning, ending = _time(start), _time(end)
    if ending < beginning:
        raise ValueError("end precedes start")
    return [
        row for row in bucket["readings"]
        if row["point_id"] == point_id and beginning <= _time(row["observed_at"]) <= ending
    ]
