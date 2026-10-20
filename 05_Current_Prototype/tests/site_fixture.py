"""A small stand-in for demo.site_db with the contract's shapes (docs/site-data-contract.md), for tests and previews."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

AS_OF = datetime(2026, 10, 10, 6, 0, tzinfo=timezone.utc)  # 14:00 SGT


def iso(delta_minutes: float = 0) -> str:
    return (AS_OF + timedelta(minutes=delta_minutes)).isoformat()


def _square(lat: float, lon: float, half: float) -> dict:
    """A zone outline for the fixture: a square GeoJSON polygon, with its label point."""
    ring = [[lon - half, lat - half], [lon + half, lat - half], [lon + half, lat + half], [lon - half, lat + half], [lon - half, lat - half]]
    return {"geometry": json.dumps({"type": "Polygon", "coordinates": [ring]}), "lat": lat, "lon": lon, "geo_source": "fixture"}


ZONES = [
    {"zone_code": "SGV", "name": "Supertree Grove", "map_no": 6, "kind": "garden", **_square(1.2820, 103.8639, .0008)},
    {"zone_code": "FDM", "name": "Flower Dome", "map_no": 3, "kind": "conservatory", **_square(1.2845, 103.8647, .0005)},
    {"zone_code": "DFB", "name": "Dragonfly Bridge", "map_no": None, "kind": "bridge", **_square(1.2825, 103.8624, .0001)},
]
CONTRACTORS = [
    {"contractor_id": "CTR-NWD", "name": "Northwind M&E Pte Ltd", "short_name": "Northwind", "colour": "#8B5CF6", "logo_svg": None},
    {"contractor_id": "CTR-HLX", "name": "Helix Civil Works", "short_name": "Helix", "colour": "#EC4899", "logo_svg": None},
]
ASSETS = [
    {"asset_id": "SGV-DB-03", "name": "Grove DB 3", "zone_code": "SGV", "asset_type": "DB", "criticality": "high", "fed_from": None,
     "rated_current_a": 200, "idle_current_a": 1, "operating_hours": "24h"},
    {"asset_id": "SGV-OUT-01", "name": "Grove outlets", "zone_code": "SGV", "asset_type": "OUT", "criticality": "low",
     "fed_from": "SGV-DB-03", "rated_current_a": 32, "idle_current_a": 0.5, "operating_hours": "08:00-22:00"},
    {"asset_id": "SGV-OUT-02", "name": "Kiosk outlets", "zone_code": "SGV", "asset_type": "OUT", "criticality": None,
     "fed_from": "SGV-DB-03", "rated_current_a": None, "idle_current_a": None, "operating_hours": None, "connected": 0},
    {"asset_id": "SGV-LGT-01", "name": "Supertree lights", "zone_code": "SGV", "asset_type": "LGT", "criticality": "medium",
     "fed_from": None, "rated_current_a": 60, "idle_current_a": 1, "operating_hours": "19:00-23:00"},
    {"asset_id": "FDM-CHL-01", "name": "Chiller 1", "zone_code": "FDM", "asset_type": "CHL", "criticality": "high", "fed_from": None,
     "rated_current_a": 80, "idle_current_a": 5, "operating_hours": "24h"},
    {"asset_id": "FDM-AHU-02", "name": "Air handler 2", "zone_code": "FDM", "asset_type": "AHU", "criticality": "high", "fed_from": None,
     "rated_current_a": 40, "idle_current_a": 2, "operating_hours": "24h"},
    {"asset_id": "FDM-PMP-01", "name": "Chilled water pump 1", "zone_code": "FDM", "asset_type": "PMP", "criticality": "high",
     "fed_from": None, "rated_current_a": 30, "idle_current_a": 2, "operating_hours": "24h"},
]
LATEST_VALUES = {  # asset -> (current, voltage, pf, trip, minutes since last reading)
    "SGV-DB-03": (0.0, 0.0, 0.0, 0, 0),       # isolated under a permit → Down, with a cone
    "SGV-OUT-01": (0.0, 0.0, 0.0, 0, 0),      # fed from the isolated DB → Down, with a cone
    "SGV-LGT-01": (0.2, 231, 0.95, 0, 0),     # outside 19:00–23:00 → Idle
    "FDM-CHL-01": (62, 232, 0.91, 0, 0),      # Operational
    "FDM-AHU-02": (31, 259, 0.90, 0, 0),      # voltage high → Warning
    "FDM-PMP-01": (18, 230, 0.88, 0, 120),    # stale → Offline
}
PTWS = [
    {"ptw_id": "PTW-2026-0142", "zone_code": "SGV", "contractor_id": "CTR-NWD", "title": "DB-03 replacement",
     "work_type": "electrical", "start_at": iso(-360), "end_at": iso(180), "source_file": None},
    {"ptw_id": "PTW-2026-0145", "zone_code": "DFB", "contractor_id": "CTR-HLX", "title": "Deck resurfacing",
     "work_type": "civil", "start_at": iso(-300), "end_at": iso(2 * 24 * 60), "source_file": None},
]
IMPACTS = [
    {"impact_id": "PTW-2026-0142/1", "ptw_id": "PTW-2026-0142", "kind": "electrical", "target_type": "asset", "target_id": "SGV-DB-03",
     "effect": "isolated", "summary": "DB-03 isolated", "start_at": iso(-360), "end_at": iso(180)},
    {"impact_id": "PTW-2026-0142/2", "ptw_id": "PTW-2026-0142", "kind": "electrical", "target_type": "asset", "target_id": "SGV-OUT-01",
     "effect": "down", "summary": "3 outlets down", "start_at": iso(-360), "end_at": iso(180)},
    {"impact_id": "PTW-2026-0145/1", "ptw_id": "PTW-2026-0145", "kind": "physical", "target_type": "zone", "target_id": "DFB",
     "effect": "closed", "summary": "Bridge closed", "start_at": iso(-300), "end_at": iso(2 * 24 * 60)},
]
WORK_ORDERS = [
    {"wo_id": "WO-2026-0457", "asset_id": "FDM-CHL-01", "title": "Quarterly service", "scheduled_start": iso(60),
     "scheduled_end": iso(180), "status": "scheduled", "ptw_id": None},
]

ROOMS = [
    {"room_id": "MR-01", "name": "Orchid Room", "seats": 12, "location": None},
    {"room_id": "MR-02", "name": "Fern Room", "seats": 6, "location": None},
]
BOOKINGS = [  # at AS_OF (14:00 SGT): Orchid is in use until 15:30 (two meetings back to back); Fern is free until 16:00
    {"booking_id": "RB-0001", "room_id": "MR-01", "title": "Daily operations huddle", "booked_by": "Facilities",
     "start_at": iso(-300), "end_at": iso(-270)},
    {"booking_id": "RB-0002", "room_id": "MR-01", "title": "Permit coordination", "booked_by": "Engineering",
     "start_at": iso(-30), "end_at": iso(60)},
    {"booking_id": "RB-0003", "room_id": "MR-01", "title": "Vendor call", "booked_by": "Engineering",
     "start_at": iso(60), "end_at": iso(90)},
    {"booking_id": "RB-0004", "room_id": "MR-02", "title": "Budget review", "booked_by": "Finance",
     "start_at": iso(120), "end_at": iso(180)},
]


def _latest() -> dict:
    out = {}
    for asset_id, (amps, volts, pf, trip, age) in LATEST_VALUES.items():
        at = iso(-age)
        out[asset_id] = {point: {"value": value, "unit": unit, "observed_at": at} for point, value, unit in (
            ("current_a", amps, "A"), ("voltage_v", volts, "V"), ("power_factor", pf, ""), ("trip_state", trip, "state"),
            ("power_kw", round(volts * amps * pf * 3 ** .5 / 1000, 1), "kW"), ("energy_kwh", 12345.0, "kWh"))}
    return out


def _readings(asset_id: str, start: str, end: str) -> list[dict]:
    amps, volts, pf, _, age = LATEST_VALUES[asset_id]
    rows = []
    for step in range(0, 24 * 4):
        minutes = -step * 15 - age
        for point, value, unit in (("current_a", amps + (step % 5) * .3, "A"), ("voltage_v", volts + (step % 3) * .4, "V"),
                                   ("power_factor", pf, ""), ("power_kw", amps * .4, "kW")):
            rows.append({"asset_id": asset_id, "point_id": point, "observed_at": iso(minutes), "value": value, "unit": unit})
    return rows


def _t(value) -> datetime:
    return datetime.fromisoformat(str(value))


def _overlaps(row: dict, start_key: str, end_key: str, active_at=None, start=None, end=None) -> bool:
    if active_at is not None:
        return _t(row[start_key]) <= _t(active_at) < _t(row[end_key])
    return (start is None or _t(row[end_key]) > _t(start)) and (end is None or _t(row[start_key]) < _t(end))


def _ptw_row(row: dict) -> dict:
    contractor = next(item for item in CONTRACTORS if item["contractor_id"] == row["contractor_id"])
    zone = next(item for item in ZONES if item["zone_code"] == row["zone_code"])
    return {**row, "contractor": contractor, "zone": zone}


FAKE_DB = SimpleNamespace(
    as_of=lambda: AS_OF.isoformat(),
    zones=lambda: [dict(row) for row in ZONES],
    contractors=lambda: [dict(row) for row in CONTRACTORS],
    assets=lambda: [dict(row) for row in ASSETS],
    latest_readings=_latest,
    readings=_readings,
    ptws=lambda active_at=None, start=None, end=None: [_ptw_row(row) for row in PTWS if _overlaps(row, "start_at", "end_at", active_at, start, end)],
    ptw=lambda ptw_id: next(({**_ptw_row(row), "impacts": [item for item in IMPACTS if item["ptw_id"] == ptw_id]}
                             for row in PTWS if row["ptw_id"] == ptw_id), None),
    impacts=lambda active_at=None: [dict(row) for row in IMPACTS if active_at is None or _overlaps(row, "start_at", "end_at", active_at)],
    work_orders=lambda start, end, asset_id=None: [dict(row) for row in WORK_ORDERS
                                                   if _overlaps(row, "scheduled_start", "scheduled_end", None, start, end)
                                                   and (asset_id is None or row["asset_id"] == asset_id)],
    event_orders=lambda start, end: [],
    event_power=lambda start=None, end=None: [],
    rooms=lambda: [dict(row) for row in ROOMS],
    room_bookings=lambda start, end, room_id=None: [dict(row) for row in BOOKINGS if _overlaps(row, "start_at", "end_at", None, start, end)
                                                    and (room_id is None or row["room_id"] == room_id)],
)


def seeded_db(path):
    """demo.site_db with every read bound to ``path`` (a database built by site_seed.build)."""
    from functools import partial

    from demo import site_db

    names = ("as_of", "zones", "contractors", "assets", "latest_readings", "readings", "ptws", "ptw", "impacts",
             "work_orders", "work_order", "event_orders", "event_order", "event_power", "rooms", "room_bookings", "book_room", "cancel_booking")
    return SimpleNamespace(**{name: partial(getattr(site_db, name), path=path) for name in names})
