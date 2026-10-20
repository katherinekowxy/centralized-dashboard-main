"""Asset state for the Asset dashboard: deterministic rules, never predictive.

Rules and order come from docs/site-data-contract.md (approved by Dan, 10 October 2026):
Offline → Down → Warning → Idle → Operational. Times are UTC in data and SGT on screen.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

SGT = timezone(timedelta(hours=8), "SGT")
SEVERITY = ("down", "warning", "offline", "idle", "operational")  # problems first
LABEL = {"operational": "Operational", "idle": "Idle", "warning": "Warning", "down": "Down", "offline": "Offline"}
COLOUR = {"operational": "#22C55E", "idle": "#2563EB", "warning": "#F59E0B", "down": "#EF4444", "offline": "#9CA3AF"}
ORBS = {"down", "warning"}  # Dan: orbs on Down and Warning only
EVENT_POWER_TYPES = ("OGB", "CEE")  # OG boxes and their CEEform sockets: shown on the Event power tab only

STALE_AFTER = timedelta(minutes=30)  # two 15-minute readings missed
VOLTAGE_RANGE = (216.0, 253.0)       # 230 V −6 % / +10 %
MIN_POWER_FACTOR = 0.80


def ts(value: Any) -> datetime:
    moment = value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def in_operating_hours(spec: str | None, at: Any) -> bool:
    """``24h`` or ``HH:MM-HH:MM`` in SGT; a range may run past midnight. ``on demand`` (an event socket) is never
    due to run, so no load means Idle (free), never Down."""
    if not spec or spec.strip().lower() == "24h":
        return True
    if spec.strip().lower() == "on demand":
        return False
    start, end = (datetime.strptime(part.strip(), "%H:%M").time() for part in spec.split("-"))
    now = ts(at).astimezone(SGT).time()
    return start <= now < end if start < end else now >= start or now < end


def _value(latest: dict[str, dict], point: str) -> float | None:
    row = latest.get(point)
    return None if row is None or row.get("value") is None else float(row["value"])


def asset_state(asset: dict, latest: dict[str, dict], as_of: Any) -> dict[str, str]:
    """Return ``{"state", "reason"}``; the reason is a few words for the asset page."""
    now = ts(as_of)
    current = latest.get("current_a")
    if current is None or now - ts(current["observed_at"]) > STALE_AFTER:
        last = max((ts(row["observed_at"]) for row in latest.values()), default=None)
        if last is None:
            return {"state": "offline", "reason": "No data received"}
        hours = (now - last).total_seconds() / 3600
        return {"state": "offline", "reason": f"No data for {hours:.0f} h" if hours >= 1 else "No recent data"}
    amps = float(current["value"])
    running = amps >= float(asset.get("idle_current_a") or 0)
    if (_value(latest, "trip_state") or 0) >= 1:
        return {"state": "down", "reason": "Tripped"}
    in_hours = in_operating_hours(asset.get("operating_hours"), now)
    if not running:
        return {"state": "down", "reason": "Not running in operating hours"} if in_hours else {"state": "idle", "reason": "Standby"}
    volts, pf, rated = _value(latest, "voltage_v"), _value(latest, "power_factor"), asset.get("rated_current_a")
    if volts is not None and not VOLTAGE_RANGE[0] <= volts <= VOLTAGE_RANGE[1]:
        return {"state": "warning", "reason": f"Voltage {volts:.0f} V"}
    if rated and amps > float(rated):
        return {"state": "warning", "reason": f"Current {amps:.0f} A, rated {float(rated):.0f} A"}
    if pf is not None and pf < MIN_POWER_FACTOR:
        return {"state": "warning", "reason": f"Power factor {pf:.2f}"}
    return {"state": "operational", "reason": "Running"}


def maintenance_today(asset_id: str, work_orders: Iterable[dict], impacts: Iterable[dict], as_of: Any) -> list[dict]:
    """What puts a cone on the box: a work order today (SGT) that isn't done, or an active PTW impact on it."""
    now = ts(as_of)
    day = now.astimezone(SGT).date()
    found = [row for row in work_orders if row.get("asset_id") == asset_id and row.get("status") != "done"
             and ts(row["scheduled_start"]).astimezone(SGT).date() <= day <= ts(row["scheduled_end"]).astimezone(SGT).date()]
    found += [row for row in impacts if row.get("target_type") == "asset" and row.get("target_id") == asset_id
              and ts(row["start_at"]) <= now < ts(row["end_at"])]
    return found
