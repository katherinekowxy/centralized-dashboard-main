"""Replay expectations and adversarial input tests at the public engine boundary."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta

import pytest

from demo.engine import ASSETS, SCENARIOS, analyze, evaluate, generate_dataset


EXPECTED = {
    "normal": (set(), {"condition", "trip"}),
    "leakage_ramp": ({"condition"}, {"trip"}),
    "sudden_trip": ({"trip"}, {"condition"}),
    "planned_maintenance": ({"context"}, {"condition", "trip"}),
    "telemetry_dropout": ({"data_quality"}, {"condition", "trip"}),
    "messy_ingestion": ({"data_quality"}, {"condition", "trip"}),
    "unknown_asset": ({"data_quality"}, {"condition", "trip"}),
    "high_neutral": (set(), {"condition", "trip"}),
    "insufficient_baseline": ({"insufficient_evidence"}, {"condition", "trip"}),
    "conflicting_context": ({"condition", "context"}, {"trip"}),
    "startup_transient": (set(), {"condition", "trip"}),
    "isolated_zero": (set(), {"condition", "trip"}),
}


@pytest.mark.parametrize("scenario,expected", EXPECTED.items())
def test_scenario_behavior_and_evidence(scenario, expected):
    dataset = generate_dataset(scenario, seed=42)
    analysis = analyze(dataset["readings"], dataset["events"])
    required, forbidden = expected
    categories = {case["category"] for case in analysis["cases"] if case["asset_id"] in {"DB-01", "UNROUTED"}}
    assert required <= categories
    assert not categories & forbidden
    assert len(ASSETS) == 5
    assert {row["asset_id"] for row in analysis["accepted"]} == {asset["asset_id"] for asset in ASSETS}
    evidence = {row["reading_id"] for row in analysis["accepted"]} | {event["event_id"] for event in dataset["events"]} | {item["reading"].get("reading_id") for item in analysis["quarantine"]}
    assert all(set(case["evidence_ids"]) <= evidence for case in analysis["cases"])
    assert all(item["passed"] for item in evaluate(dataset, analysis)), scenario


def test_seed_replay_and_truth_separation():
    first = generate_dataset("leakage_ramp", seed=42)
    assert first == generate_dataset("leakage_ramp", seed=42)
    assert first["readings"] != generate_dataset("leakage_ramp", seed=43)["readings"]
    analysis = analyze(first["readings"], first["events"])
    changed_truth = deepcopy(first)
    changed_truth["ground_truth"] = {"scenario_id": "normal", "synthetic_only": True}
    assert analyze(changed_truth["readings"], changed_truth["events"]) == analysis


def test_routing_is_exact_and_cross_asset_point_is_held():
    row = next(row for row in generate_dataset("normal")["readings"] if row["point_id"] == "leakage_ma")
    bad = [dict(row, reading_id="ALIAS", asset_ref="plant-01"),
           dict(row, reading_id="PARTIAL", asset_ref="LVDB"),
           dict(row, reading_id="CROSS", asset_ref="BMS:AHU01")]
    output = analyze(bad, [])
    reasons = {item["reading"]["reading_id"]: item["reason"] for item in output["quarantine"]}
    assert reasons == {"ALIAS": "ambiguous_asset", "PARTIAL": "unknown_asset", "CROSS": "unknown_point"}
    assert output["accepted"] == []


@pytest.mark.parametrize("change,reason", [
    ({"unit": "A"}, "unit_mismatch"),
    ({"value": None}, "invalid_value"),
    ({"value": float("nan")}, "invalid_value"),
    ({"value": float("inf")}, "invalid_value"),
    ({"observed_at": "2026-09-21T01:00:00"}, "invalid_timestamp"),
    ({"ingested_at": "bad"}, "invalid_timestamp"),
    ({"quality": "sensor_fault"}, "source_quality"),
    ({"operating_mode": "unknown"}, "invalid_operating_mode"),
    ({"reading_id": ""}, "missing_reading_id"),
])
def test_bad_readings_are_held_without_fault(change, reason):
    row = next(row for row in generate_dataset("normal")["readings"] if row["point_id"] == "leakage_ma")
    output = analyze([dict(row, **change)], [])
    assert len(output["quarantine"]) == 1
    assert output["quarantine"][0]["reason"] == reason
    assert not any(case["category"] in {"condition", "trip"} for case in output["cases"])


def test_invalid_event_window_and_status_do_not_become_context():
    dataset = generate_dataset("planned_maintenance")
    event = dataset["events"][0]
    reversed_window = dict(event, event_id="BAD-WINDOW", start_at=event["end_at"], end_at=event["start_at"])
    bad_status = dict(event, event_id="BAD-STATUS", status="nonsense")
    missing_id = {key: value for key, value in event.items() if key != "event_id"}
    output = analyze([], [reversed_window, bad_status, missing_id])
    assert not any(case["category"] == "context" for case in output["cases"])
    assert sum(item["issue_type"] == "invalid_event" for item in output["quality_issues"]) == 3


def test_as_of_excludes_future_evidence_and_event_context():
    dataset = generate_dataset("conflicting_context")
    as_of = dataset["metadata"]["start_at"]
    output = analyze(dataset["readings"], dataset["events"], as_of=as_of)
    cutoff = datetime.fromisoformat(as_of)
    assert all(datetime.fromisoformat(row["observed_at"]) <= cutoff for row in output["accepted"])
    assert all(datetime.fromisoformat(row["ingested_at"]) <= cutoff for row in output["accepted"])
    assert not any(case["category"] in {"condition", "trip", "context"} for case in output["cases"])


def test_ingestion_before_observation_is_held():
    row = next(row for row in generate_dataset("normal")["readings"] if row["point_id"] == "leakage_ma")
    observed = datetime.fromisoformat(row["observed_at"])
    output = analyze([dict(row, ingested_at=(observed - timedelta(minutes=5)).isoformat())], [])
    assert len(output["quarantine"]) == 1
    assert output["accepted"] == []
