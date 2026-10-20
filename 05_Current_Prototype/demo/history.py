"""Synthetic CMMS history for the dashboard, separate from detector evidence.

Every timestamp is relative to a supplied replay cutoff.  These work orders
illustrate descriptive maintenance analytics, not measured predictive accuracy.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import pandas as pd

from demo.engine import ASSETS


# age in days, asset, fault, title, priority, status, elapsed repair hours,
# observed downtime hours, resolution.  Recurrences are deliberate.
_EPISODES = [
    (88, "AHU-01", "Filter restriction", "Replace loaded supply filters", "low", "closed", 22, 1.5, "Filters replaced; differential pressure checked."),
    (85, "DB-01", "Earth leakage", "Investigate feeder leakage", "high", "closed", 18, 2.0, "Damaged feeder termination repaired; relay retested."),
    (81, "FAN-01", "Belt wear", "Replace slipping drive belt", "medium", "closed", 27, 3.0, "Belt and pulley alignment corrected."),
    (76, "PUMP-01", "Seal leak", "Repair pump seal seepage", "high", "closed", 39, 5.5, "Mechanical seal renewed and leak test passed."),
    (73, "CHILLER-01", "Cooling performance", "Check high condenser approach", "high", "closed", 48, 4.0, "Condenser strainers cleaned and temperatures verified."),
    (69, "AHU-01", "Filter restriction", "Inspect recurring filter loading", "medium", "closed", 16, 1.0, "Filters replaced; outside air intake cleaned."),
    (65, "FAN-01", "Bearing vibration", "Investigate exhaust fan vibration", "medium", "closed", 31, 2.5, "Bearing lubricated and vibration rechecked."),
    (61, "DB-01", "Relay trip", "Review overnight relay trip", "high", "closed", 12, 1.2, "Relay log reviewed; affected feeder inspected and restored."),
    (58, "PUMP-01", "Seal leak", "Check seal drain flow", "medium", "closed", 29, 2.0, "Seal flush line cleared; no further seepage observed."),
    (55, "CHILLER-01", "Cooling performance", "Restore chilled water capacity", "high", "closed", 45, 6.0, "Fouled heat exchanger cleaned; supply temperature recovered."),
    (51, "AHU-01", "Filter restriction", "Replace clogged return filters", "low", "closed", 20, 1.0, "Return filters changed and airflow confirmed."),
    (47, "FAN-01", "Belt wear", "Correct fan belt tension", "medium", "closed", 15, 1.5, "Belt tension adjusted and guards refitted."),
    (43, "DB-01", "Earth leakage", "Trace intermittent leakage", "high", "closed", 37, 2.8, "Moisture ingress at cable gland corrected; relay trend checked."),
    (39, "PUMP-01", "Bearing vibration", "Inspect pump bearing noise", "medium", "closed", 32, 3.5, "Bearing replaced and vibration measured after restart."),
    (36, "CHILLER-01", "Cooling performance", "Check condenser water flow", "medium", "closed", 19, 1.0, "Condenser strainer cleaned; flow restored."),
    (32, "AHU-01", "Filter restriction", "Investigate reduced supply airflow", "medium", "closed", 24, 1.5, "Supply filters renewed; airflow balanced."),
    (28, "FAN-01", "Bearing vibration", "Inspect rising fan vibration", "medium", "closed", 42, 4.0, "Bearing housing secured and alignment verified."),
    (24, "DB-01", "Relay trip", "Investigate feeder trip indication", "high", "closed", 14, 1.8, "Trip circuit and feeder insulation tested before reset."),
    (20, "PUMP-01", "Seal leak", "Repair recurring seal drip", "high", "closed", 51, 7.0, "Seal faces and flush supply renewed; monitored after restart."),
    (17, "CHILLER-01", "Cooling performance", "Investigate low cooling output", "high", "closed", 35, 3.0, "Condenser tube fouling cleared; capacity confirmed."),
    (13, "AHU-01", "Filter restriction", "Replace heavily loaded filters", "low", "closed", 18, 1.0, "Filters replaced; pressure drop returned to normal."),
    (10, "FAN-01", "Belt wear", "Inspect belt dust at drive", "medium", "closed", 22, 2.0, "Worn belt replaced and sheaves aligned."),
    (7, "DB-01", "Earth leakage", "Review repeat leakage alarm", "high", "closed", 30, 2.5, "Cable gland sealed; follow-up relay reading stable."),
    (5, "PUMP-01", "Seal leak", "Investigate fresh seal seepage", "high", "in_progress", None, 0, None),
    (4, "CHILLER-01", "Cooling performance", "Check elevated return temperature", "medium", "open", None, 0, None),
    (3, "FAN-01", "Bearing vibration", "Investigate bearing temperature rise", "medium", "in_progress", None, 0, None),
    (2, "AHU-01", "Filter restriction", "Inspect recurring filter alarm", "low", "open", None, 0, None),
    (1, "DB-01", "Earth leakage", "Review relay leakage trend", "high", "open", None, 0, None),
]


def _time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("as_of and work-order timestamps require a UTC offset")
    return parsed.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return value.isoformat(timespec="seconds")


def generate_history(as_of: str) -> list[dict[str, Any]]:
    """Return fixed, repeatable work orders from the 90 days before ``as_of``."""
    cutoff = _time(as_of)
    valid_assets = {asset["asset_id"] for asset in ASSETS}
    orders = []
    for number, (age, asset, fault, title, priority, status, repair_h, downtime_h, resolution) in enumerate(_EPISODES, 1):
        if asset not in valid_assets:
            raise ValueError(f"Unregistered history asset: {asset}")
        reported = cutoff - timedelta(days=age, hours=4)
        closed = reported + timedelta(hours=repair_h) if repair_h is not None else None
        if closed is not None and closed > cutoff:
            raise ValueError("History episode closes after replay cutoff")
        orders.append({
            "work_order_id": f"CMMS-{number:04d}", "asset_id": asset,
            "fault_type": fault, "title": title, "priority": priority,
            "status": status, "reported_at": _iso(reported),
            "closed_at": _iso(closed) if closed else None,
            "downtime_hours": float(downtime_h), "resolution": resolution,
        })
    return sorted(orders, key=lambda row: row["reported_at"], reverse=True)


def summarize_history(work_orders: list[dict[str, Any]], as_of: str, asset_id: str | None = None) -> dict[str, Any]:
    """Aggregate observed CMMS counts, closures, and downtime with DataFrames."""
    cutoff = _time(as_of)
    start = (cutoff - timedelta(days=90)).date()
    first_monday = start - timedelta(days=start.weekday())
    last_monday = cutoff.date() - timedelta(days=cutoff.weekday())
    week_index = pd.date_range(first_monday.isoformat(), last_monday.isoformat(), freq="7D", tz="UTC")
    frame = pd.DataFrame.from_records(work_orders, columns=[
        "asset_id", "fault_type", "status", "reported_at", "closed_at", "downtime_hours",
    ])
    frame["reported_at"] = pd.to_datetime(frame["reported_at"], utc=True)
    frame["closed_at"] = pd.to_datetime(frame["closed_at"], utc=True)
    if asset_id is not None:
        frame = frame.loc[frame["asset_id"].eq(asset_id)]
    frame = frame.loc[frame["reported_at"].le(cutoff) & frame["reported_at"].ge(cutoff - timedelta(days=90))].copy()

    observed_closed = (
        frame["status"].eq("closed") & frame["closed_at"].notna()
        & frame["closed_at"].ge(frame["reported_at"]) & frame["closed_at"].le(cutoff)
    )
    frame["observed_closed"] = observed_closed
    frame["observed_downtime"] = pd.to_numeric(frame["downtime_hours"], errors="coerce").fillna(0).where(observed_closed, 0.0)
    closed = frame.loc[observed_closed]

    report_weeks = frame["reported_at"].dt.normalize() - pd.to_timedelta(frame["reported_at"].dt.weekday, unit="D")
    close_weeks = closed["closed_at"].dt.normalize() - pd.to_timedelta(closed["closed_at"].dt.weekday, unit="D")
    reported_counts = frame.groupby(report_weeks).size().reindex(week_index, fill_value=0)
    closed_counts = closed.groupby(close_weeks).size().reindex(week_index, fill_value=0)
    weekly = pd.DataFrame({"week": week_index.strftime("%Y-%m-%d"), "faults": reported_counts.to_numpy(), "closed": closed_counts.to_numpy()})
    by_fault = (
        frame.groupby("fault_type", as_index=False)
        .agg(faults=("fault_type", "size"), downtime_hours=("observed_downtime", "sum"))
        .sort_values(["faults", "fault_type"], ascending=[False, True])
    )
    by_fault["downtime_hours"] = by_fault["downtime_hours"].round(2)
    elapsed = (closed["closed_at"] - closed["reported_at"]).dt.total_seconds().div(3600)
    return {
        "total_faults": int(len(frame)), "open_faults": int((~observed_closed).sum()),
        "closed_faults": int(observed_closed.sum()),
        "downtime_hours": round(float(frame["observed_downtime"].sum()), 2),
        "median_resolution_hours": round(float(elapsed.median()), 2) if len(elapsed) else None,
        "weekly": weekly.to_dict("records"), "by_fault": by_fault.to_dict("records"),
    }
