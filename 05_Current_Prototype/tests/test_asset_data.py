"""Evidence and time-window behavior of asset overview buckets."""

from datetime import datetime, timedelta, timezone

import pytest

from demo.asset_data import build_asset_bucket, filter_events, point_series
from demo.engine import ASSETS, POINTS, analyze, generate_dataset
from demo.history import generate_history


T0 = datetime(2026, 9, 22, 12, 0, tzinfo=timezone.utc)


def stamp(minutes=0):
    return (T0 + timedelta(minutes=minutes)).isoformat()


def reading(asset, point, minutes, value=1, mode="running"):
    return {
        "reading_id": f"{asset}:{point}:{minutes}", "asset_id": asset,
        "point_id": point, "observed_at": stamp(minutes), "value": value,
        "operating_mode": mode, "unit": POINTS[asset][point]["unit"],
    }


def simple_run(rows, *, cases=(), history=(), events=(), at=0):
    return {
        "as_of": stamp(at), "analysis": {"accepted": list(rows), "cases": list(cases)},
        "history": list(history), "dataset": {"events": list(events)},
    }


def test_point_freshness_is_per_expected_stream_and_zero_is_a_reading():
    db = "DB-01"
    rows = [reading(db, point, 0, value=0) for point in POINTS[db]]
    rows += [reading(db, point, 10, value=0) for point in POINTS[db] if point != "leakage_ma"]
    bucket = build_asset_bucket(simple_run(rows, at=20), db)
    assert bucket["points"]["leakage_ma"]["freshness"] == "stale"
    assert bucket["points"]["leakage_ma"]["latest"]["value"] == 0
    assert bucket["points"]["phase_current_a"]["freshness"] == "fresh"
    assert bucket["freshness"] == "partial"
    assert bucket["operating_state"] == "unknown"
    assert bucket["condition_label"] == "Data incomplete"


def test_missing_points_never_infer_mode_or_detector_clearance():
    db = "DB-01"
    bucket = build_asset_bucket(simple_run([], at=0), db)
    assert bucket["freshness"] == "missing"
    assert all(point["freshness"] == "missing" and point["latest"] is None for point in bucket["points"].values())
    assert bucket["operating_state"] == "unknown"
    assert bucket["condition_label"] == "Data incomplete"

    rows = [reading(db, point, 0) for point in POINTS[db]]
    rows.append(reading(db, "leakage_ma", 5, mode="standby"))
    bucket = build_asset_bucket(simple_run(rows, at=5), db)
    assert bucket["freshness"] == "fresh"
    assert bucket["operating_state"] == "unknown"  # Recent streams disagree.


def test_insufficient_evidence_never_reads_as_detector_clearance():
    pump = "PUMP-01"
    rows = [reading(pump, point, 0) for point in POINTS[pump]]
    case = {"case_id": "INSUFFICIENT-PUMP-01", "asset_id": pump,
            "category": "insufficient_evidence", "title": "Insufficient pump baseline",
            "start_at": stamp(0), "end_at": stamp(0)}
    bucket = build_asset_bucket(simple_run(rows, cases=[case], at=0), pump)
    assert bucket["freshness"] == "fresh"
    assert bucket["condition_label"] == "Insufficient detector evidence"


def test_scope_history_replay_cases_and_mode_events_with_original_records():
    db, ahu = "DB-01", "AHU-01"
    rows = [reading(db, point, 0) for point in POINTS[db]]
    rows += [reading(db, point, 10, mode="standby") for point in POINTS[db]]
    rows += [reading(ahu, point, 0) for point in POINTS[ahu]]
    replay_event = {
        "event_id": "PTW-1", "asset_id": db, "event_type": "ptw", "title": "Inspection",
        "start_at": stamp(-20), "end_at": stamp(20), "reported_at": stamp(-30),
        "status": "active", "notes": "Permit record",
    }
    foreign_event = {**replay_event, "event_id": "PTW-2", "asset_id": ahu}
    order = {"work_order_id": "CMMS-1", "asset_id": db, "title": "Repair", "reported_at": stamp(-40), "closed_at": None, "status": "open"}
    foreign_order = {**order, "work_order_id": "CMMS-2", "asset_id": ahu}
    case = {"case_id": "CASE-1", "asset_id": db, "category": "condition", "title": "Evidence finding", "start_at": stamp(0), "end_at": stamp(10)}
    foreign_case = {**case, "case_id": "CASE-2", "asset_id": ahu}
    run = simple_run(rows, cases=[case, foreign_case], history=[order, foreign_order], events=[replay_event, foreign_event], at=10)
    bucket = build_asset_bucket(run, db)
    assert bucket["asset"]["asset_id"] == db
    assert bucket["condition_label"] == "Detector finding"
    assert {row["asset_id"] for row in bucket["readings"] + bucket["cases"] + bucket["work_orders"] + bucket["events"]} == {db}
    assert {event["event_type"] for event in bucket["events"]} >= {"ptw", "work_order", "detector_case", "state", "stop"}
    assert next(event for event in bucket["events"] if event["event_id"] == "PTW-1")["record"] is replay_event
    assert next(event for event in bucket["events"] if event["source_id"] == "CMMS-1")["record"] is order
    assert next(event for event in bucket["events"] if event["source_id"] == "CASE-1")["record"] is case
    assert bucket["operating_state"] == "standby"
    assert len(point_series(bucket, "leakage_ma", stamp(10), stamp(10))) == 1


def test_event_overlap_includes_touching_boundaries_and_open_periods():
    events = [
        {"event_id": "before", "start_at": stamp(-20), "end_at": stamp(-10)},
        {"event_id": "touch-start", "start_at": stamp(-10), "end_at": stamp(0)},
        {"event_id": "inside", "start_at": stamp(2), "end_at": stamp(8)},
        {"event_id": "touch-end", "start_at": stamp(10), "end_at": stamp(20)},
        {"event_id": "open", "start_at": stamp(4), "end_at": None},
        {"event_id": "after", "start_at": stamp(21), "end_at": None},
    ]
    assert {row["event_id"] for row in filter_events(events, stamp(0), stamp(10))} == {"touch-start", "inside", "touch-end", "open"}
    with pytest.raises(ValueError):
        filter_events(events, stamp(10), stamp(0))


def test_backward_cutoff_hides_future_work_and_future_closure():
    db = "DB-01"
    rows = [reading(db, point, 0) for point in POINTS[db]]
    rows += [reading(db, point, 20, mode="standby") for point in POINTS[db]]
    closing_later = {
        "work_order_id": "CMMS-FUTURE-CLOSE", "asset_id": db, "title": "Repair",
        "reported_at": stamp(-20), "closed_at": stamp(20), "status": "closed",
        "resolution": "Repaired later", "downtime_hours": 2.0,
    }
    reported_later = {**closing_later, "work_order_id": "CMMS-FUTURE-REPORT", "reported_at": stamp(20)}
    malformed = {"event_id": "BAD", "asset_id": db, "reported_at": "not a date"}
    invalid_status = {"event_id": "BAD-STATUS", "asset_id": db, "event_type": "ptw",
                      "title": "Unverified", "status": "invalid", "reported_at": stamp(-5),
                      "start_at": stamp(-5), "end_at": stamp(5)}
    run = simple_run(rows, history=[closing_later, reported_later], events=[malformed, invalid_status], at=0)
    bucket = build_asset_bucket(run, db)
    assert len(bucket["readings"]) == len(POINTS[db])
    assert len(bucket["work_orders"]) == 1
    assert bucket["work_orders"][0]["status"] == "open"
    assert bucket["work_orders"][0]["closed_at"] is None
    assert bucket["work_orders"][0]["downtime_hours"] == 0
    event = next(row for row in bucket["events"] if row["event_type"] == "work_order")
    assert event["status"] == "open" and event["end_at"] is None
    assert event["record"] is closing_later
    assert all(row["event_id"] not in {"BAD", "BAD-STATUS"} for row in bucket["events"])


def test_real_replay_dropout_is_partial_and_other_assets_are_not_assessed():
    dataset = generate_dataset("telemetry_dropout", seed=42)
    analysis = analyze(dataset["readings"], dataset["events"])
    as_of = analysis["metrics"]["as_of"]
    run = {"dataset": dataset, "analysis": analysis, "history": generate_history(as_of), "as_of": as_of}
    db = build_asset_bucket(run, "DB-01")
    assert db["freshness"] == "partial"
    assert db["points"]["leakage_ma"]["freshness"] == "stale"
    assert db["points"]["relay_trip"]["freshness"] == "stale"
    assert db["points"]["phase_voltage_v"]["freshness"] == "fresh"
    assert db["operating_state"] == "unknown"
    assert db["condition_label"] == "Data incomplete"
    ahu = build_asset_bucket(run, "AHU-01")
    assert ahu["freshness"] == "fresh"
    assert ahu["condition_label"] == "Not assessed"
    assert all(event["asset_id"] == "AHU-01" for event in ahu["events"])


def test_custom_asset_uses_its_imported_snapshot_and_explicit_catalog():
    asset = {"asset_id": "PUMP-02", "name": "Pump 02", "asset_type": "pump", "location": "Annex",
             "criticality": "unspecified", "coverage": "Imported telemetry; no commissioned detector"}
    observed = "2026-10-05T09:00:00+00:00"
    row = {"reading_id": "IMP-1", "asset_id": "PUMP-02", "point_id": "motor_current_a",
           "observed_at": observed, "value": 37.0, "unit": "A", "operating_mode": "running",
           "source": "vendor_csv", "source_file": "vendor.csv", "source_row": 2}
    replay_row = reading("DB-01", "leakage_ma", 0)
    run = simple_run([replay_row], at=0)
    run["imported_readings"] = [row]
    catalog = {item["asset_id"]: item for item in ASSETS}
    catalog[asset["asset_id"]] = asset
    specs = {**POINTS, asset["asset_id"]: POINTS["PUMP-01"]}
    bucket = build_asset_bucket(run, asset["asset_id"], asset_catalog=catalog, point_catalog=specs)
    assert bucket["as_of"] == observed
    assert bucket["readings"] == [row]
    assert bucket["points"]["motor_current_a"]["latest"]["source_file"] == "vendor.csv"
    assert bucket["condition_label"] == "Not assessed"
    assert not bucket["cases"]
