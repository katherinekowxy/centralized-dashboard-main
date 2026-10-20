"""Deterministic synthetic fixture and evidence based monitoring engine.

All timestamps are ISO 8601 with UTC offsets.  The five registered assets have
telemetry fixtures; the distribution board and pump have explicit demo rules.
No scenario label or ground truth enters :func:`analyze`.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from math import isfinite
from random import Random
from statistics import median
from typing import Any


ASSETS: list[dict[str, Any]] = [
    {"asset_id": "DB-01", "name": "LV Distribution Board 01", "asset_type": "distribution_board", "location": "Energy Centre / LV Room", "criticality": "high", "coverage": "Relay and meter demo triage", "detector_enabled": True, "aliases": ["DB-01", "LVDB-01", "BMS:LVDB01", "CMMS:DB-01"]},
    {"asset_id": "AHU-01", "name": "Air Handling Unit 01", "asset_type": "ahu", "location": "Tower A / Roof", "criticality": "medium", "coverage": "Schema and fixture only", "aliases": ["AHU-01", "BMS:AHU01"]},
    {"asset_id": "FAN-01", "name": "Exhaust Fan 01", "asset_type": "fan", "location": "Basement / Plant Room", "criticality": "medium", "coverage": "Schema and fixture only", "aliases": ["FAN-01", "BMS:EF01"]},
    {"asset_id": "PUMP-01", "name": "Chilled Water Pump 01", "asset_type": "pump", "location": "Energy Centre / Pump Room", "criticality": "high", "coverage": "Three-signal running-mode demo triage", "detector_enabled": True, "aliases": ["PUMP-01", "BMS:CHWP01"]},
    {"asset_id": "CHILLER-01", "name": "Chiller 01", "asset_type": "chiller", "location": "Energy Centre / Chiller Hall", "criticality": "high", "coverage": "Schema and fixture only", "aliases": ["CHILLER-01", "BMS:CH01"]},
]

# Bounds reject impossible measurements; they are engineering demo limits, not alarms.
POINTS: dict[str, dict[str, dict[str, Any]]] = {
    "DB-01": {
        "leakage_ma": {"quantity": "earth_leakage_current", "unit": "mA", "cadence_s": 600, "bounds": (0, 500), "source": "earth_leakage_relay"},
        "relay_trip": {"quantity": "trip_state", "unit": "state", "cadence_s": 600, "bounds": (0, 1), "source": "earth_leakage_relay"},
        "phase_voltage_v": {"quantity": "phase_voltage", "unit": "V", "cadence_s": 1200, "bounds": (0, 300), "source": "power_meter"},
        "phase_current_a": {"quantity": "phase_current", "unit": "A", "cadence_s": 1200, "bounds": (0, 250), "source": "power_meter"},
        "neutral_current_a": {"quantity": "neutral_current", "unit": "A", "cadence_s": 1200, "bounds": (0, 250), "source": "power_meter"},
    },
    "AHU-01": {
        "supply_temp_c": {"quantity": "supply_air_temperature", "unit": "°C", "cadence_s": 1800, "bounds": (-10, 60), "source": "bms"},
        "return_temp_c": {"quantity": "return_air_temperature", "unit": "°C", "cadence_s": 1800, "bounds": (-10, 60), "source": "bms"},
        "fan_current_a": {"quantity": "motor_current", "unit": "A", "cadence_s": 1800, "bounds": (0, 100), "source": "bms"},
    },
    "FAN-01": {
        "motor_current_a": {"quantity": "motor_current", "unit": "A", "cadence_s": 1800, "bounds": (0, 100), "source": "bms"},
        "bearing_temp_c": {"quantity": "bearing_temperature", "unit": "°C", "cadence_s": 1800, "bounds": (-10, 150), "source": "bms"},
        "vibration_mm_s": {"quantity": "vibration_velocity_overall", "unit": "mm/s", "cadence_s": 1800, "bounds": (0, 50), "source": "edge_scalar"},
    },
    "PUMP-01": {
        "motor_current_a": {"quantity": "motor_current", "unit": "A", "cadence_s": 1800, "bounds": (0, 150), "source": "bms"},
        "bearing_temp_c": {"quantity": "bearing_temperature", "unit": "°C", "cadence_s": 1800, "bounds": (-10, 150), "source": "bms"},
        "vibration_mm_s": {"quantity": "vibration_velocity_overall", "unit": "mm/s", "cadence_s": 1800, "bounds": (0, 50), "source": "edge_scalar"},
        "differential_pressure_kpa": {"quantity": "differential_pressure", "unit": "kPa", "cadence_s": 1800, "bounds": (0, 1500), "source": "bms"},
    },
    "CHILLER-01": {
        "power_kw": {"quantity": "electrical_power", "unit": "kW", "cadence_s": 1800, "bounds": (0, 1500), "source": "power_meter"},
        "supply_temp_c": {"quantity": "chilled_water_supply_temperature", "unit": "°C", "cadence_s": 1800, "bounds": (-10, 40), "source": "bms"},
        "return_temp_c": {"quantity": "chilled_water_return_temperature", "unit": "°C", "cadence_s": 1800, "bounds": (-10, 60), "source": "bms"},
        "flow_l_s": {"quantity": "water_flow", "unit": "L/s", "cadence_s": 1800, "bounds": (0, 500), "source": "bms"},
    },
}

SCENARIOS: list[dict[str, str]] = [
    {"scenario_id": "normal", "name": "Normal daily cycle", "description": "Two healthy running and standby cycles across all five assets."},
    {"scenario_id": "leakage_ramp", "name": "Rising earth leakage", "description": "DB-01 relay current rises gradually while the board remains in service."},
    {"scenario_id": "sudden_trip", "name": "Abrupt relay trip", "description": "A single relay trip indication without a preceding leakage ramp."},
    {"scenario_id": "planned_maintenance", "name": "Planned maintenance", "description": "A time-bounded permit and work order overlap a board shutdown."},
    {"scenario_id": "telemetry_dropout", "name": "Telemetry dropout", "description": "The relay stops reporting while the other feeds continue."},
    {"scenario_id": "messy_ingestion", "name": "Messy ingestion", "description": "Malformed, duplicate, delayed and fast valid rows test the quality lane."},
    {"scenario_id": "unknown_asset", "name": "Unknown asset", "description": "One otherwise valid measurement uses an unmapped source alias."},
    {"scenario_id": "high_neutral", "name": "High neutral, healthy relay", "description": "Load-dependent neutral current is high while measured earth leakage stays normal."},
    {"scenario_id": "insufficient_baseline", "name": "Insufficient relay baseline", "description": "Few comparable relay readings remain; the detector must abstain."},
    {"scenario_id": "conflicting_context", "name": "Fault during active permit", "description": "A leakage rise overlaps a permit and work order; context must not hide it."},
    {"scenario_id": "startup_transient", "name": "Startup transient", "description": "An isolated relay spike at startup returns to normal."},
    {"scenario_id": "isolated_zero", "name": "Isolated zero", "description": "One current reading is zero while voltage and run state remain normal."},
    {"scenario_id": "pump_degradation", "name": "Pump condition trend", "description": "Day-two running vibration, bearing temperature and motor current rise together; a CMMS investigation follows the observations."},
    {"scenario_id": "pump_load_change", "name": "Pump load change", "description": "A legitimate day-two load change raises current and differential pressure without persistent vibration or bearing temperature rise."},
]

DETECTOR_ASSET_IDS = frozenset({"DB-01", "PUMP-01"})

_ASSET_BY_ID = {asset["asset_id"]: asset for asset in ASSETS}
_ALIASES: dict[str, set[str]] = defaultdict(set)
for _asset in ASSETS:
    for _alias in _asset["aliases"]:
        _ALIASES[_alias.strip().casefold()].add(_asset["asset_id"])
_ALIASES["plant-01"].update({"DB-01", "PUMP-01"})  # Deliberate ambiguous legacy name.
_START = datetime(2026, 9, 21, 0, 0, tzinfo=timezone.utc)
_STEPS = 288
_INJECTION = 238
_PUMP_INJECTION = 216  # Day two at 12:00 UTC, during running mode.


def _iso(value: datetime) -> str:
    return value.isoformat(timespec="seconds")


def _parse_time(value: Any) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("missing timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("invalid timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timestamp lacks timezone")
    return parsed.astimezone(timezone.utc)


def _resolve(ref: Any) -> tuple[str | None, str | None]:
    if not isinstance(ref, str) or not ref.strip():
        return None, "missing_asset_ref"
    matches = _ALIASES.get(ref.strip().casefold(), set())
    if not matches:
        return None, "unknown_asset"
    if len(matches) > 1:
        return None, "ambiguous_asset"
    return next(iter(matches)), None


def _mode(step: int) -> str:
    hour = (_START + timedelta(minutes=10 * step)).hour
    return "running" if 7 <= hour < 20 else "standby"


def _value(asset_id: str, point_id: str, step: int, rng: Random) -> float:
    running = _mode(step) == "running"
    jitter = rng.uniform(-1.0, 1.0)
    wave = (step % 36) / 36
    if asset_id == "DB-01":
        return {
            "leakage_ma": 20 + (3 if running else -2) + jitter * 1.3 + wave,
            "relay_trip": 0,
            "phase_voltage_v": 230 + jitter * 1.5,
            "phase_current_a": (83 if running else 16) + jitter * 3,
            "neutral_current_a": (23 if running else 7) + jitter * 2,
        }[point_id]
    if asset_id == "AHU-01":
        return {"supply_temp_c": (14 if running else 23) + jitter * .4, "return_temp_c": (23 if running else 24) + jitter * .6, "fan_current_a": (15 if running else 0) + (jitter * .5 if running else 0)}[point_id]
    if asset_id == "FAN-01":
        return {"motor_current_a": (9 if running else 0) + (jitter * .3 if running else 0), "bearing_temp_c": (51 if running else 29) + jitter, "vibration_mm_s": (2.1 if running else .25) + jitter * .15}[point_id]
    if asset_id == "PUMP-01":
        return {"motor_current_a": (38 if running else 0) + (jitter if running else 0), "bearing_temp_c": (58 if running else 30) + jitter, "vibration_mm_s": (2.5 if running else .3) + jitter * .18, "differential_pressure_kpa": (290 if running else 0) + (jitter * 5 if running else 0)}[point_id]
    return {"power_kw": (510 if running else 0) + (jitter * 12 if running else 0), "supply_temp_c": (6.8 if running else 17) + jitter * .3, "return_temp_c": (12.1 if running else 19) + jitter * .4, "flow_l_s": (72 if running else 0) + (jitter * 1.5 if running else 0)}[point_id]


def _event(event_id: str, event_type: str, status: str, start: int, end: int, title: str, notes: str,
           asset_id: str = "DB-01", reported: int | None = None) -> dict[str, Any]:
    start_at = _START + timedelta(minutes=start * 10)
    return {"event_id": event_id, "asset_id": asset_id, "event_type": event_type, "status": status,
            "start_at": _iso(start_at), "end_at": _iso(_START + timedelta(minutes=end * 10)),
            "reported_at": _iso(_START + timedelta(minutes=reported * 10) if reported is not None else start_at - timedelta(hours=2)), "title": title, "notes": notes,
            "source": "synthetic_work_management"}


def generate_dataset(scenario_id: str = "leakage_ramp", seed: int = 42) -> dict[str, Any]:
    """Generate reproducible, clearly synthetic readings and separate scenario truth."""
    if scenario_id not in {scenario["scenario_id"] for scenario in SCENARIOS}:
        raise ValueError(f"Unknown scenario: {scenario_id}")
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("seed must be an integer")
    rng = Random(seed)
    readings: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    for asset in ASSETS:
        aid = asset["asset_id"]
        for point_id, spec in POINTS[aid].items():
            stride = spec["cadence_s"] // 600
            for step in range(0, _STEPS, stride):
                if scenario_id == "telemetry_dropout" and aid == "DB-01" and point_id in {"leakage_ma", "relay_trip"} and step >= 263:
                    continue
                if scenario_id == "insufficient_baseline" and aid == "DB-01" and point_id == "leakage_ma" and step < 281:
                    continue
                at = _START + timedelta(minutes=10 * step)
                mode = _mode(step)
                if scenario_id == "startup_transient" and aid == "DB-01" and 186 <= step <= 188:
                    mode = "startup"
                value = _value(aid, point_id, step, rng)
                if aid == "DB-01":
                    if scenario_id in {"leakage_ramp", "conflicting_context"} and point_id == "leakage_ma" and step >= _INJECTION:
                        value += min(84, (step - _INJECTION) * 2.1)
                    elif scenario_id == "sudden_trip" and step == 252:
                        if point_id == "relay_trip":
                            value = 1
                        elif point_id == "leakage_ma":
                            value = 150
                    elif scenario_id == "startup_transient" and point_id == "leakage_ma" and step == 187:
                        value = 94
                    elif scenario_id == "high_neutral" and point_id == "neutral_current_a" and step >= _INJECTION:
                        value = (94 if mode == "running" else 43) + rng.uniform(-2, 2)
                    elif scenario_id == "isolated_zero" and point_id == "phase_current_a" and step == 252:
                        value = 0
                    if scenario_id == "planned_maintenance" and 246 <= step <= 265:
                        mode = "maintenance"
                        if point_id in {"phase_current_a", "neutral_current_a"}:
                            value = 0
                        elif point_id == "leakage_ma":
                            value = 7 + rng.uniform(-.5, .5)
                if aid == "PUMP-01" and mode == "running" and step >= _PUMP_INJECTION:
                    elapsed = step - _PUMP_INJECTION
                    if scenario_id == "pump_degradation":
                        if point_id == "vibration_mm_s":
                            value += min(4.5, elapsed * .24)
                        elif point_id == "bearing_temp_c":
                            value += min(15, elapsed * .8)
                        elif point_id == "motor_current_a":
                            value += min(10, elapsed * .55)
                    elif scenario_id == "pump_load_change":
                        if point_id == "motor_current_a":
                            value += 8
                        elif point_id == "differential_pressure_kpa":
                            value += 45
                observed = _iso(at)
                readings.append({"reading_id": f"R-{aid}-{point_id}-{step:03d}", "asset_ref": asset["aliases"][2 if aid == "DB-01" else 1],
                                 "point_id": point_id, "observed_at": observed,
                                 "ingested_at": _iso(at + timedelta(seconds=25 + rng.randrange(0, 60))),
                                 "value": round(value, 3), "unit": spec["unit"], "quality": "good",
                                 "operating_mode": mode, "source": spec["source"], "schema_version": "1"})
    if scenario_id == "planned_maintenance":
        events = [
            _event("PTW-104", "ptw", "active", 244, 270, "LV board isolation permit", "Approved inspection window; isolation must be confirmed by site staff."),
            _event("WO-104", "cmms", "in_progress", 246, 268, "Planned relay inspection", "Visual check and relay test recorded as planned work."),
        ]
    elif scenario_id == "conflicting_context":
        events = [
            _event("PTW-205", "ptw", "active", 245, 267, "Adjacent feeder cable works", "Permit covers adjacent feeder, not an explanation for rising relay current."),
            _event("WO-205", "cmms", "open", 251, 280, "Investigate board relay trend", "Raised after leakage trend observed; cause unconfirmed."),
        ]
    elif scenario_id == "sudden_trip":
        events = [_event("WO-301", "cmms", "open", 253, 280, "Investigate relay trip", "Operator reported trip after relay indication.")]
    elif scenario_id == "pump_degradation":
        events = [_event("WO-PUMP-401", "cmms", "open", 234, 287,
                         "Investigate pump condition trend", "Operator requested vibration, temperature and current checks; cause unconfirmed.",
                         asset_id="PUMP-01", reported=234)]
    if scenario_id == "messy_ingestion":
        base = next(row for row in readings if row["asset_ref"] == "BMS:LVDB01" and row["point_id"] == "leakage_ma" and row["observed_at"] == _iso(_START + timedelta(minutes=2500)))
        changes = [
            {"reading_id": "BAD-UNIT", "unit": "A"},
            {"reading_id": "BAD-TIME", "observed_at": "2026-09-22T17:40:00"},
            {"reading_id": "BAD-VALUE", "value": None},
            {"reading_id": "BAD-QUALITY", "quality": "sensor_fault"},
            {"reading_id": "BAD-BOUNDS", "value": -17},
        ]
        for index, change in enumerate(changes):
            row = dict(base, **change)
            row["observed_at"] = change.get("observed_at", _iso(_START + timedelta(minutes=(270 + index) * 10)))
            row["ingested_at"] = _iso(_START + timedelta(minutes=(270 + index) * 10 + 2))
            readings.append(row)
        duplicate = dict(base, reading_id="DUP-ROW", ingested_at=_iso(_START + timedelta(minutes=2505)))
        readings.append(duplicate)
        # A faster valid relay reading has its own timestamp; it is not a duplicate.
        fast = dict(base, reading_id="FAST-VALID", observed_at=_iso(_START + timedelta(minutes=2505)),
                    ingested_at=_iso(_START + timedelta(minutes=2506)), value=round(float(base["value"]) + .2, 3))
        readings.append(fast)
        old = dict(base, reading_id="LATE-OLD", observed_at=_iso(_START + timedelta(minutes=1005)),
                   ingested_at=_iso(_START + timedelta(minutes=2750)), value=21.4)
        readings.append(old)
    if scenario_id == "unknown_asset":
        bad_ref = dict(readings[-1], reading_id="UNKNOWN-ASSET-001", asset_ref="BMS:UNREGISTERED-77")
        readings.append(bad_ref)
    expected = {
        "normal": (set(), set()), "leakage_ramp": ({"condition"}, {"trip"}),
        "sudden_trip": ({"trip"}, {"condition"}), "planned_maintenance": ({"context"}, {"condition", "trip"}),
        "telemetry_dropout": ({"data_quality"}, {"condition", "trip"}),
        "messy_ingestion": ({"data_quality"}, {"condition", "trip"}),
        "unknown_asset": ({"data_quality"}, {"condition", "trip"}),
        "high_neutral": (set(), {"condition", "trip"}),
        "insufficient_baseline": ({"insufficient_evidence"}, {"condition", "trip"}),
        "conflicting_context": ({"condition", "context"}, {"trip"}),
        "startup_transient": (set(), {"condition", "trip"}),
        "isolated_zero": (set(), {"condition", "trip"}),
        "pump_degradation": ({"condition", "context"}, {"trip"}),
        "pump_load_change": (set(), {"condition", "trip"}),
    }[scenario_id]
    ground_truth = {
        "scenario_id": scenario_id,
        "target_asset_id": "PUMP-01" if scenario_id.startswith("pump_") else "DB-01",
        "injection_start_at": _iso(_START + timedelta(minutes=10 * (_PUMP_INJECTION if scenario_id.startswith("pump_") else _INJECTION))),
        "expected_categories": sorted(expected[0]),
        "forbidden_categories": sorted(expected[1]),
        "description": next(s["description"] for s in SCENARIOS if s["scenario_id"] == scenario_id),
        "synthetic_only": True,
    }
    metadata = {"synthetic": True, "generator_version": "v0.1", "seed": seed, "scenario_id": scenario_id,
                "start_at": _iso(_START), "end_at": _iso(_START + timedelta(minutes=10 * (_STEPS - 1))),
                "timezone": "UTC", "asset_count": len(ASSETS), "point_catalog": POINTS,
                "scope": "DB-01 relay/meter and PUMP-01 three-signal demo detection; three additional schema and fixture assets"}
    return {"readings": readings, "events": events, "ground_truth": ground_truth, "metadata": metadata}


def _issue(issue_type: str, detail: str, evidence_ids: list[str], asset_id: str | None = None,
           point_id: str | None = None, observed_at: str | None = None) -> dict[str, Any]:
    return {"issue_type": issue_type, "detail": detail, "evidence_ids": evidence_ids,
            "asset_id": asset_id, "point_id": point_id, "observed_at": observed_at}


def _case(case_id: str, asset_id: str, category: str, severity: str, title: str,
          summary: str, evidence_ids: list[str], observations: list[str],
          recommended_checks: list[str], start_at: str, end_at: str,
          ai_eligible: bool = False, ai_gate_reason: str = "") -> dict[str, Any]:
    return {"case_id": case_id, "asset_id": asset_id, "category": category,
            "severity": severity, "title": title, "summary": summary,
            "evidence_ids": list(dict.fromkeys(evidence_ids)), "observations": observations,
            "recommended_checks": recommended_checks, "ai_eligible": ai_eligible,
            "ai_gate_reason": ai_gate_reason, "start_at": start_at, "end_at": end_at}


def _overlapping(events: list[dict[str, Any]], asset_id: str, start: datetime, end: datetime) -> list[dict[str, Any]]:
    return [event for event in events if event["asset_id"] == asset_id and event["_start"] <= end and event["_end"] >= start]


def analyze(readings: list[dict[str, Any]], events: list[dict[str, Any]], as_of: str | None = None) -> dict[str, Any]:
    """Route, validate, and classify evidence without receiving scenario truth."""
    accepted: list[dict[str, Any]] = []
    quarantine: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    cases: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    seen_points: dict[tuple[str, str, datetime], dict[str, Any]] = {}
    previous_observed: dict[tuple[str, str], datetime] = {}
    requested_as_of = _parse_time(as_of) if as_of is not None else None
    required = {"reading_id", "asset_ref", "point_id", "observed_at", "ingested_at", "value", "unit", "quality", "operating_mode", "source", "schema_version"}
    for raw in readings:
        row = dict(raw) if isinstance(raw, dict) else {"raw": raw}
        rid = str(row.get("reading_id") or "<missing-id>")
        aid, route_error = _resolve(row.get("asset_ref"))
        point = row.get("point_id")
        reason = route_error
        if reason is None and (not isinstance(point, str) or point not in POINTS[aid]):
            reason = "unknown_point"
        if reason is None and required - row.keys():
            reason = "missing_field"
        if reason is None and (not isinstance(row["reading_id"], str) or not row["reading_id"].strip()):
            reason = "missing_reading_id"
        observed: datetime | None = None
        ingested: datetime | None = None
        if reason is None:
            try:
                observed, ingested = _parse_time(row["observed_at"]), _parse_time(row["ingested_at"])
            except ValueError:
                reason = "invalid_timestamp"
        if reason is None and requested_as_of is not None and (ingested > requested_as_of or observed > requested_as_of):
            # The observation has not reached this replay instant.
            continue
        if reason is None and ingested < observed:
            reason = "invalid_timestamp_order"
        if reason is None and row["schema_version"] != "1":
            reason = "unsupported_schema"
        if reason is None and row["unit"] != POINTS[aid][point]["unit"]:
            reason = "unit_mismatch"
        if reason is None and (isinstance(row["value"], bool) or not isinstance(row["value"], (int, float)) or not isfinite(row["value"])):
            reason = "invalid_value"
        if reason is None:
            lower, upper = POINTS[aid][point]["bounds"]
            if not lower <= row["value"] <= upper or (point == "relay_trip" and row["value"] not in (0, 1)):
                reason = "outside_physical_bounds"
        if reason is None and row["quality"] != "good":
            reason = "source_quality"
        if reason is None and (not isinstance(row["operating_mode"], str) or row["operating_mode"] not in {"running", "standby", "off", "startup", "maintenance"}):
            reason = "invalid_operating_mode"
        if reason is None and (not isinstance(row["source"], str) or not row["source"].strip()):
            reason = "missing_source"
        if reason is None and row["source"] != POINTS[aid][point]["source"]:
            reason = "source_mismatch"
        if reason is None and rid in seen_ids:
            reason = "duplicate_id"
        if reason is None:
            key = (aid, point, observed)
            previous = seen_points.get(key)
            if previous is not None:
                reason = "duplicate" if (previous["value"], previous["unit"], previous["quality"]) == (row["value"], row["unit"], row["quality"]) else "conflicting_duplicate"
        if reason is not None:
            quarantine.append({"reading": row, "reason": reason, "asset_id": aid, "point_id": point if isinstance(point, str) else None})
            issues.append(_issue(reason, f"Reading {rid} held: {reason.replace('_', ' ')}.",
                                 [rid] if rid != "<missing-id>" else [], aid,
                                 point if isinstance(point, str) else None, str(row.get("observed_at", ""))))
            continue
        assert observed is not None and ingested is not None and aid is not None and isinstance(point, str)
        accepted_row = {**row, "asset_id": aid, "observed_at": _iso(observed), "ingested_at": _iso(ingested),
                        "quantity": POINTS[aid][point]["quantity"], "expected_cadence_s": POINTS[aid][point]["cadence_s"]}
        if (aid, point) in previous_observed and observed < previous_observed[(aid, point)]:
            issues.append(_issue("out_of_order", f"Reading {rid} arrived after a newer observation; retained at its event time.", [rid], aid, point, _iso(observed)))
        if ingested - observed > timedelta(seconds=POINTS[aid][point]["cadence_s"] * 3):
            issues.append(_issue("late_arrival", f"Reading {rid} was ingested well after observation.", [rid], aid, point, _iso(observed)))
        previous_observed[(aid, point)] = observed
        seen_ids.add(rid)
        seen_points[(aid, point, observed)] = accepted_row
        accepted.append(accepted_row)
    accepted.sort(key=lambda row: (row["observed_at"], row["asset_id"], row["point_id"]))
    if requested_as_of is not None:
        now = requested_as_of
    elif accepted:
        now = max(_parse_time(row["observed_at"]) for row in accepted)
    else:
        now = datetime.now(timezone.utc)
    by_stream: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in accepted:
        by_stream[(row["asset_id"], row["point_id"])].append(row)
    for (aid, point), stream in by_stream.items():
        cadence = POINTS[aid][point]["cadence_s"]
        first = _parse_time(stream[0]["observed_at"])
        earliest = min((_parse_time(row["observed_at"]) for row in accepted), default=first)
        opening_gap = (first - earliest).total_seconds()
        if opening_gap > cadence * 2.5:
            issues.append(_issue("opening_gap", f"{point} begins {opening_gap / 60:.0f} minutes after the replay begins (expected {cadence / 60:.0f} minute cadence).", [stream[0]["reading_id"]], aid, point, stream[0]["observed_at"]))
        for prior, current in zip(stream, stream[1:]):
            gap = (_parse_time(current["observed_at"]) - _parse_time(prior["observed_at"])).total_seconds()
            if gap > cadence * 2.5:
                issues.append(_issue("gap", f"{point} has a {gap / 60:.0f} minute observation gap (expected {cadence / 60:.0f} minutes).", [prior["reading_id"], current["reading_id"]], aid, point, current["observed_at"]))
        age = (now - _parse_time(stream[-1]["observed_at"])).total_seconds()
        if age > cadence * 2.5:
            issues.append(_issue("stale", f"{point} is {age / 60:.0f} minutes old at replay time.", [stream[-1]["reading_id"]], aid, point, _iso(now)))
    for aid, catalogue in POINTS.items():
        for point in catalogue:
            if (aid, point) not in by_stream:
                issues.append(_issue("missing_stream", f"No accepted readings for {point}.", [], aid, point, _iso(now)))
    # One unexpected zero with an energized board is an ambiguous measurement,
    # not evidence that the feeder has failed or recovered.
    voltage = by_stream.get(("DB-01", "phase_voltage_v"), [])
    for row in by_stream.get(("DB-01", "phase_current_a"), []):
        if row["operating_mode"] != "running" or row["value"] != 0:
            continue
        time = _parse_time(row["observed_at"])
        near = [item for item in voltage if abs((_parse_time(item["observed_at"]) - time).total_seconds()) <= 1200 and item["value"] >= 200]
        if near:
            issues.append(_issue("ambiguous_zero", "An isolated zero current reading occurs during running mode with voltage present; verify source state before interpreting it.",
                                 [row["reading_id"], near[0]["reading_id"]], "DB-01", "phase_current_a", row["observed_at"]))
    valid_events: list[dict[str, Any]] = []
    seen_events: set[str] = set()
    for raw in events:
        if not isinstance(raw, dict):
            issues.append(_issue("invalid_event", "Event record is not an object.", []))
            continue
        eid = str(raw.get("event_id") or "<missing-event-id>")
        aid, error = _resolve(raw.get("asset_id"))
        event_type = raw.get("event_type")
        allowed_status = {"ptw": {"planned", "active", "closed", "cancelled"},
                          "cmms": {"open", "in_progress", "completed", "cancelled"}}
        if (not isinstance(raw.get("event_id"), str) or not raw["event_id"].strip() or error is not None
                or not isinstance(event_type, str) or event_type not in allowed_status
                or not isinstance(raw.get("status"), str) or raw["status"] not in allowed_status[event_type]):
            issues.append(_issue("invalid_event", f"Event {eid} has invalid identity, type or status.", [eid] if eid != "<missing-event-id>" else [], aid))
            continue
        if eid in seen_events:
            issues.append(_issue("duplicate_event", f"Event {eid} appears more than once; later copy held.", [eid], aid))
            continue
        try:
            start, end, reported = (_parse_time(raw[key]) for key in ("start_at", "end_at", "reported_at"))
        except (ValueError, KeyError):
            issues.append(_issue("invalid_event", f"Event {eid} has invalid timing.", [eid], aid))
            continue
        if end < start:
            issues.append(_issue("invalid_event", f"Event {eid} ends before it starts.", [eid], aid))
            continue
        if requested_as_of is not None and reported > requested_as_of:
            continue
        valid_events.append({**raw, "asset_id": aid, "_start": start, "_end": end, "_reported": reported})
        seen_events.add(eid)
    # A valid permit or work order is preserved as time-bounded context.
    for event in valid_events:
        cases.append(_case(f"CTX-{event['event_id']}", event["asset_id"], "context", "info",
                           f"{event['event_type'].upper()} · {event.get('title', event['event_id'])}",
                           f"{event['event_type'].upper()} status {event['status']} within the recorded time window.",
                           [event["event_id"]], [f"Reported {_iso(event['_reported'])}; window {_iso(event['_start'])} to {_iso(event['_end'])}.",
                                                  str(event.get("notes") or "No notes supplied.")],
                           ["Confirm the work scope and actual plant state with the responsible person."],
                           _iso(event["_start"]), _iso(event["_end"]), ai_gate_reason="Context alone does not warrant AI explanation."))
    # Relay trip is an explicit state, independent of leakage trend magnitude.
    trips = [row for row in by_stream.get(("DB-01", "relay_trip"), []) if row["value"] == 1]
    if trips:
        trip = trips[0]
        time = _parse_time(trip["observed_at"])
        nearby = [row for row in by_stream.get(("DB-01", "leakage_ma"), []) if abs((_parse_time(row["observed_at"]) - time).total_seconds()) <= 600]
        context = _overlapping(valid_events, "DB-01", time, time)
        evidence = [trip["reading_id"]] + [row["reading_id"] for row in nearby] + [event["event_id"] for event in context]
        observations = [f"Relay trip state = 1 at {trip['observed_at']}."]
        if nearby:
            observations.append(f"Nearest measured earth leakage = {nearby[0]['value']:.1f} mA.")
        if context:
            observations.append("Recorded work context overlaps the trip; it does not establish the cause.")
        cases.append(_case("TRIP-DB-01", "DB-01", "trip", "critical", "Relay trip indication",
                           "The accepted relay state records a trip indication.", evidence, observations,
                           ["Confirm the relay event and downstream state at the board.", "Review relay logs and site isolation procedures before any work."],
                           trip["observed_at"], trip["observed_at"], True,
                           "Accepted relay trip with traceable evidence; optional explanation requires a user request."))
    # Establish a same-mode baseline from the first 24 hours, excluding maintenance.
    leakage = by_stream.get(("DB-01", "leakage_ma"), [])
    early_end = min((_parse_time(row["observed_at"]) for row in accepted), default=now) + timedelta(hours=24)
    baseline: dict[str, list[dict[str, Any]]] = {mode: [row for row in leakage if row["operating_mode"] == mode and _parse_time(row["observed_at"]) < early_end] for mode in ("running", "standby")}
    comparable = baseline["running"]
    baseline_span_h = ((_parse_time(comparable[-1]["observed_at"]) - _parse_time(comparable[0]["observed_at"])).total_seconds() / 3600) if len(comparable) > 1 else 0.0
    expected_in_span = round(baseline_span_h * 3600 / POINTS["DB-01"]["leakage_ma"]["cadence_s"]) + 1
    baseline_coverage = len(comparable) / max(1, expected_in_span)
    sufficient_baseline = len(comparable) >= 24 and baseline_span_h >= 6 and baseline_coverage >= .75
    if leakage and not sufficient_baseline:
        evidence = [row["reading_id"] for row in comparable[:4]] + [row["reading_id"] for row in leakage[-4:]]
        cases.append(_case("INSUFFICIENT-DB-01", "DB-01", "insufficient_evidence", "info", "Insufficient relay baseline",
                           f"The first 24 hours contain {len(comparable)} running-mode readings spanning {baseline_span_h:.1f} hours at {baseline_coverage:.0%} coverage; need at least 24 readings, six hours and 75% coverage.",
                           evidence, ["A sufficiently covered running-mode baseline is unavailable.", "No leakage condition decision is made."],
                           ["Restore relay history and review source coverage before comparing trends."],
                           leakage[0]["observed_at"], leakage[-1]["observed_at"], ai_gate_reason="Insufficient baseline; AI explanation is not warranted."))
    if sufficient_baseline:
        base_values = [float(row["value"]) for row in comparable]
        centre = median(base_values)
        mad = median(abs(value - centre) for value in base_values)
        threshold = max(centre + 20, centre + 8 * max(mad, 1), centre * 1.8)
        candidates = [row for row in leakage if row["operating_mode"] == "running" and _parse_time(row["observed_at"]) >= early_end]
        qualifying: list[dict[str, Any]] = []
        for index in range(5, len(candidates)):
            window = candidates[index - 5:index + 1]
            values = [float(row["value"]) for row in window]
            span = (_parse_time(window[-1]["observed_at"]) - _parse_time(window[0]["observed_at"])).total_seconds()
            rises = sum(b > a for a, b in zip(values, values[1:]))
            if span <= 5400 and median(values[-3:]) > threshold and rises >= 4 and values[-1] - values[0] >= 8:
                qualifying = window
                break
        if qualifying:
            first, last = qualifying[0], qualifying[-1]
            start, end = _parse_time(first["observed_at"]), _parse_time(last["observed_at"])
            context = _overlapping(valid_events, "DB-01", start, end)
            observations = [f"Running-mode baseline median {centre:.1f} mA from {len(comparable)} accepted readings over {baseline_span_h:.1f} hours ({baseline_coverage:.0%} coverage).",
                            f"Six consecutive accepted readings rise from {first['value']:.1f} to {last['value']:.1f} mA; qualifying threshold {threshold:.1f} mA."]
            if context:
                observations.append("CMMS/PTW context overlaps this trend; scope and causal relationship remain unverified.")
            cases.append(_case("LEAKAGE-DB-01", "DB-01", "condition", "high", "Sustained rise in earth leakage",
                               "A sustained rise in relay-measured earth leakage exceeds the comparable running baseline.",
                               [row["reading_id"] for row in qualifying] + [row["reading_id"] for row in comparable[-3:]] + [event["event_id"] for event in context],
                               observations, ["Review the relay trend and confirm the measurement at the board.",
                                              "Inspect the affected circuit only under site procedures and appropriate permit controls."],
                               first["observed_at"], last["observed_at"], True,
                               "Sustained accepted relay trend with a comparable baseline; optional explanation requires a user request."))
    # Pump demo heuristic: compare three independent accepted streams in the
    # same running mode. Every point must have a covered first-day baseline;
    # four consecutive, time-aligned samples must exceed their own thresholds.
    pump_points = ("vibration_mm_s", "bearing_temp_c", "motor_current_a")
    pump_readings = [row for point in pump_points for row in by_stream.get(("PUMP-01", point), [])]
    pump_early_end = (min(_parse_time(row["observed_at"]) for row in pump_readings) + timedelta(hours=24)) if pump_readings else now
    pump_baselines: dict[str, list[dict[str, Any]]] = {}
    pump_stats: dict[str, tuple[float, float, float, int, float]] = {}
    pump_coverage: dict[str, tuple[int, float, float]] = {}
    for point in pump_points:
        rows = [row for row in by_stream.get(("PUMP-01", point), [])
                if row["operating_mode"] == "running" and _parse_time(row["observed_at"]) < pump_early_end]
        pump_baselines[point] = rows
        span_h = ((_parse_time(rows[-1]["observed_at"]) - _parse_time(rows[0]["observed_at"])).total_seconds() / 3600) if len(rows) > 1 else 0.0
        expected = round(span_h * 3600 / POINTS["PUMP-01"][point]["cadence_s"]) + 1
        coverage = len(rows) / max(1, expected)
        pump_coverage[point] = (len(rows), span_h, coverage)
        if len(rows) >= 20 and span_h >= 10 and coverage >= .8:
            centre = median(float(row["value"]) for row in rows)
            absolute_rise = {"vibration_mm_s": 1.3, "bearing_temp_c": 6.0, "motor_current_a": 4.0}[point]
            relative_rise = {"vibration_mm_s": 1.5, "bearing_temp_c": 1.10, "motor_current_a": 1.10}[point]
            pump_stats[point] = (centre, max(centre + absolute_rise, centre * relative_rise), span_h, len(rows), coverage)
    if pump_readings and len(pump_stats) != len(pump_points):
        evidence = [row["reading_id"] for point in pump_points for row in pump_baselines[point][:2]]
        evidence += [row["reading_id"] for point in pump_points for row in by_stream.get(("PUMP-01", point), [])[-2:]]
        coverage_text = "; ".join(
            f"{point}: {pump_coverage[point][0]} running readings over {pump_coverage[point][1]:.1f} h at {pump_coverage[point][2]:.0%} coverage"
            for point in pump_points)
        cases.append(_case("INSUFFICIENT-PUMP-01", "PUMP-01", "insufficient_evidence", "info",
                           "Insufficient pump running baseline",
                           "A three-signal pump condition decision requires each first-day running stream to have at least 20 readings, 10 hours and 80% coverage.",
                           evidence, [coverage_text + ".", "No pump condition decision is made."],
                           ["Restore the missing pump history and verify source coverage before comparing trends."],
                           min(row["observed_at"] for row in pump_readings), max(row["observed_at"] for row in pump_readings),
                           ai_gate_reason="Insufficient three-signal baseline; AI explanation is not warranted."))
    if len(pump_stats) == len(pump_points):
        aligned: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
        for point in pump_points:
            for row in by_stream.get(("PUMP-01", point), []):
                if row["operating_mode"] == "running" and _parse_time(row["observed_at"]) >= pump_early_end:
                    aligned[row["observed_at"]][point] = row
        joint = [(stamp, aligned[stamp]) for stamp in sorted(aligned) if len(aligned[stamp]) == len(pump_points)]
        qualifying_pump: list[tuple[str, dict[str, dict[str, Any]]]] = []
        for index in range(3, len(joint)):
            window = joint[index - 3:index + 1]
            times = [_parse_time(stamp) for stamp, _ in window]
            # No missing half-hour interval or mixed operating mode can bridge a run.
            if any((later - prior).total_seconds() > 2700 for prior, later in zip(times, times[1:])):
                continue
            if not all(all(float(record[point]["value"]) > pump_stats[point][1] for point in pump_points)
                       for _, record in window):
                continue
            minimum_rises = {"vibration_mm_s": .7, "bearing_temp_c": 2.0, "motor_current_a": 1.0}
            if not all(float(window[-1][1][point]["value"]) - float(window[0][1][point]["value"]) >= minimum_rises[point]
                       for point in pump_points):
                continue
            qualifying_pump = window
            break
        if qualifying_pump:
            start = _parse_time(qualifying_pump[0][0])
            end = _parse_time(qualifying_pump[-1][0])
            context = _overlapping(valid_events, "PUMP-01", start, end)
            evidence = [record[point]["reading_id"] for _, record in qualifying_pump for point in pump_points]
            evidence += [row["reading_id"] for point in pump_points for row in pump_baselines[point][-2:]]
            evidence += [event["event_id"] for event in context]
            observations = [
                "First-day running baselines: " + "; ".join(
                    f"{point} median {pump_stats[point][0]:.2f} {POINTS['PUMP-01'][point]['unit']} from {pump_stats[point][3]} readings over {pump_stats[point][2]:.1f} h ({pump_stats[point][4]:.0%} coverage)"
                    for point in pump_points) + ".",
                "Four aligned running observations from " + _iso(start) + " to " + _iso(end) + " exceed demo thresholds: " + "; ".join(
                    f"{point} > {pump_stats[point][1]:.2f} {POINTS['PUMP-01'][point]['unit']}"
                    for point in pump_points) + ".",
                "The observed rise is multi-signal; the equipment cause is unverified."
            ]
            if context:
                observations.append("A reported CMMS investigation overlaps the observed window; it does not establish a cause.")
            cases.append(_case("CONDITION-PUMP-01", "PUMP-01", "condition", "high",
                               "Sustained pump condition trend",
                               "A historical running window shows coincident vibration, bearing temperature and motor current rise above comparable first-day baselines.",
                               evidence, observations,
                               ["Confirm the three sensor trends and current operating state with the operator.",
                                "Inspect the pump and drive under site procedures; record findings before assigning a cause."],
                               _iso(start), _iso(end), True,
                               "Four contiguous accepted three-signal running samples exceed covered baselines; optional explanation requires a user request."))
    # Aggregate quality issues by asset, including an unroutable bucket.
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for issue in issues:
        grouped[issue["asset_id"] or "UNROUTED"].append(issue)
    for aid, records in grouped.items():
        evidence = list(dict.fromkeys(eid for item in records for eid in item["evidence_ids"]))
        types = ", ".join(f"{name}: {count}" for name, count in sorted(Counter(item["issue_type"] for item in records).items()))
        times = [item["observed_at"] for item in records if item["observed_at"]]
        cases.append(_case(f"QUALITY-{aid}", aid, "data_quality", "warning", f"Data quality · {aid}",
                           f"{len(records)} quality finding(s): {types}.", evidence,
                           [item["detail"] for item in records[:6]],
                           ["Review source mapping, timestamps and held rows before interpreting the affected feed."],
                           min(times) if times else _iso(now), max(times) if times else _iso(now),
                           ai_gate_reason="Quality findings require source review, not AI interpretation."))
    counts = Counter(case["asset_id"] for case in cases)
    quality_counts = Counter(issue["asset_id"] for issue in issues)
    summaries: list[dict[str, Any]] = []
    for asset in ASSETS:
        aid = asset["asset_id"]
        own = [case for case in cases if case["asset_id"] == aid]
        status = "critical" if any(case["severity"] == "critical" for case in own) else "attention" if any(case["category"] in {"condition", "data_quality", "insufficient_evidence"} for case in own) else "context" if own else "normal" if aid in DETECTOR_ASSET_IDS else "fixture_only"
        summaries.append({**asset, "status": status, "case_count": counts[aid], "quality_issue_count": quality_counts[aid],
                          "accepted_count": sum(len(by_stream.get((aid, point), [])) for point in POINTS[aid]),
                          "point_count": len(POINTS[aid]), "observed_point_count": sum(bool(by_stream.get((aid, point))) for point in POINTS[aid])})
    metrics = {"accepted_count": len(accepted), "quarantine_count": len(quarantine), "issue_count": len(issues),
               "missing_episode_count": sum(item["issue_type"] in {"gap", "opening_gap", "stale", "missing_stream"} for item in issues),
               "late_arrival_count": sum(item["issue_type"] == "late_arrival" for item in issues),
               "out_of_order_count": sum(item["issue_type"] == "out_of_order" for item in issues),
               "case_count": len(cases), "assets_covered": sum(summary["observed_point_count"] > 0 for summary in summaries),
               "condition_count": sum(case["category"] == "condition" for case in cases),
               "trip_count": sum(case["category"] == "trip" for case in cases),
               "data_quality_count": sum(case["category"] == "data_quality" for case in cases),
               "ai_eligible_count": sum(bool(case["ai_eligible"]) for case in cases), "as_of": _iso(now)}
    return {"accepted": accepted, "quarantine": quarantine, "quality_issues": issues,
            "cases": cases, "asset_summaries": summaries, "metrics": metrics}


def evaluate(dataset: dict[str, Any], analysis: dict[str, Any]) -> list[dict[str, Any]]:
    """Compare a replay against declared scenario outcomes and evidence integrity."""
    truth = dataset["ground_truth"]
    scenario = truth["scenario_id"]
    cases = analysis["cases"]
    target = truth["target_asset_id"]
    target_categories = {case["category"] for case in cases if case["asset_id"] == target}
    relevant_categories = target_categories | {case["category"] for case in cases if case["asset_id"] == "UNROUTED"}
    checks: list[dict[str, Any]] = []

    def add(check: str, passed: bool, detail: str) -> None:
        checks.append({"check": check, "passed": bool(passed), "detail": detail})

    add("Five registered assets routed", len({row["asset_id"] for row in analysis["accepted"]}) == 5,
        f"Accepted streams cover {len({row['asset_id'] for row in analysis['accepted']})} assets.")
    for category in truth["expected_categories"]:
        add(f"Expected {category}", category in relevant_categories,
            f"Relevant categories: {', '.join(sorted(relevant_categories)) or 'none'}.")
    for category in truth["forbidden_categories"]:
        add(f"No false {category}", category not in target_categories,
            f"{target} categories: {', '.join(sorted(target_categories)) or 'none'}.")
    if scenario in {"normal", "high_neutral", "startup_transient", "isolated_zero", "pump_load_change"}:
        add("Normal control remains clear", not any(case["category"] in {"condition", "trip"} for case in cases),
            "No equipment fault should be raised for this control.")
    if scenario in {"leakage_ramp", "conflicting_context"}:
        condition = next((case for case in cases if case["category"] == "condition" and case["asset_id"] == "DB-01"), None)
        add("Ramp detected during injection", bool(condition and condition["start_at"] >= truth["injection_start_at"]),
            "A qualifying trend should begin after injected rise, before the replay ends.")
        add("Ramp evidence grounded", bool(condition and len(condition["evidence_ids"]) >= 6),
            "The trend must cite multiple readings.")
        if scenario == "conflicting_context":
            add("Permit does not hide fault", bool(condition and any(eid.startswith("PTW-") for eid in condition["evidence_ids"])),
                "The concurrent permit should appear in the fault evidence.")
    if scenario == "sudden_trip":
        add("Trip is explicit relay state", any(case["category"] == "trip" and any("relay_trip" in eid for eid in case["evidence_ids"]) for case in cases),
            "Trip classification must cite relay state evidence.")
    if scenario == "telemetry_dropout":
        add("Missing feed surfaced", any(item["issue_type"] == "stale" and item["point_id"] == "leakage_ma" for item in analysis["quality_issues"]),
            "Relay leakage should be stale while other feeds continue.")
    if scenario == "messy_ingestion":
        reasons = {item["reason"] for item in analysis["quarantine"]}
        add("Bad rows held", {"unit_mismatch", "invalid_timestamp", "invalid_value", "source_quality", "outside_physical_bounds", "duplicate"} <= reasons,
            f"Held reasons: {', '.join(sorted(reasons))}.")
        add("Fast valid row retained", any(row["reading_id"] == "FAST-VALID" for row in analysis["accepted"]),
            "A unique five-minute observation is valid despite a ten-minute expected cadence.")
    if scenario == "unknown_asset":
        add("Unknown alias held", any(item["reason"] == "unknown_asset" for item in analysis["quarantine"]),
            "Unmapped source names must not route by partial match.")
    if scenario == "insufficient_baseline":
        add("Detector abstains", "insufficient_evidence" in target_categories and "condition" not in target_categories,
            "An incomplete comparable baseline cannot support a condition finding.")
    if scenario == "pump_degradation":
        condition = next((case for case in cases if case["category"] == "condition" and case["asset_id"] == "PUMP-01"), None)
        add("Three-signal pump trend detected", bool(condition and condition["start_at"] >= truth["injection_start_at"]),
            "The condition window must follow the day-two running-mode injection.")
        add("Pump baseline and observations traceable", bool(condition and all(
            any(point in eid for eid in condition["evidence_ids"])
            for point in ("vibration_mm_s", "bearing_temp_c", "motor_current_a"))),
            "The case must cite each of the three measured signals.")
        add("Pump CMMS follows symptoms", bool(condition and any(
            event["event_id"] in condition["evidence_ids"] and event["asset_id"] == "PUMP-01"
            and event["reported_at"] >= condition["start_at"]
            for event in dataset["events"])),
            "A linked investigation must be reported after the first observed symptom.")
    evidence_set = {row["reading_id"] for row in analysis["accepted"]} | {event["event_id"] for event in dataset["events"]} | {str(item["reading"].get("reading_id")) for item in analysis["quarantine"]}
    add("Case evidence traceable", all(set(case["evidence_ids"]) <= evidence_set for case in cases),
        "Every case reference must resolve to an accepted reading, held row or event.")
    add("AI gate limited to equipment findings", all(case["category"] in {"condition", "trip"} for case in cases if case["ai_eligible"]),
        "Data quality, context and insufficient evidence cases should not request AI.")
    return checks
