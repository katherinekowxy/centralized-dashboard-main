"""Pump-01 synthetic condition walkthrough and evidence boundary tests."""

from copy import deepcopy

import pytest

from demo.engine import DETECTOR_ASSET_IDS, analyze, evaluate, generate_dataset


def _pump_case(output):
    return next((case for case in output["cases"] if case["asset_id"] == "PUMP-01" and case["category"] == "condition"), None)


def _analyze(dataset, **kwargs):
    return analyze(dataset["readings"], dataset["events"], **kwargs)


def test_combined_pump_trend_has_three_signal_and_baseline_evidence():
    dataset = generate_dataset("pump_degradation", 42)
    assert dataset == generate_dataset("pump_degradation", 42)
    output = _analyze(dataset)
    case = _pump_case(output)
    assert case is not None
    assert case["start_at"] == "2026-09-22T13:30:00+00:00"
    assert case["end_at"] == "2026-09-22T15:00:00+00:00"
    assert case["ai_eligible"]
    assert "cause is unverified" in " ".join(case["observations"])
    assert all(any(f"R-PUMP-01-{point}-" in eid for eid in case["evidence_ids"])
               for point in ("vibration_mm_s", "bearing_temp_c", "motor_current_a"))
    assert "WO-PUMP-401" in case["evidence_ids"]
    assert dataset["events"][0]["reported_at"] >= case["start_at"]
    assert all(check["passed"] for check in evaluate(dataset, output))
    assert DETECTOR_ASSET_IDS == {"DB-01", "PUMP-01"}


def test_legitimate_pump_load_change_has_no_equipment_case():
    dataset = generate_dataset("pump_load_change", 42)
    output = _analyze(dataset)
    assert _pump_case(output) is None
    assert not any(case["category"] in {"condition", "trip"} for case in output["cases"])
    assert all(check["passed"] for check in evaluate(dataset, output))


def test_one_coincident_spike_and_disjoint_highs_do_not_qualify():
    dataset = generate_dataset("pump_load_change", 42)
    points = {"vibration_mm_s": (228, 237), "bearing_temp_c": (228, 240), "motor_current_a": (228, 243)}
    for row in dataset["readings"]:
        if row["asset_ref"] != "BMS:CHWP01" or row["point_id"] not in points:
            continue
        step = int(row["reading_id"].rsplit("-", 1)[-1])
        if step in points[row["point_id"]]:
            row["value"] += {"vibration_mm_s": 4, "bearing_temp_c": 13, "motor_current_a": 7}[row["point_id"]]
    assert _pump_case(_analyze(dataset)) is None


@pytest.mark.parametrize("damage", ["missing", "quarantined", "baseline_gap"])
def test_missing_or_untrusted_pump_signal_abstains(damage):
    dataset = generate_dataset("pump_degradation", 42)
    if damage == "missing":
        dataset["readings"] = [row for row in dataset["readings"]
                               if not (row["asset_ref"] == "BMS:CHWP01" and row["point_id"] == "vibration_mm_s"
                                       and int(row["reading_id"].rsplit("-", 1)[-1]) >= 216)]
    elif damage == "quarantined":
        for row in dataset["readings"]:
            if row["asset_ref"] == "BMS:CHWP01" and row["point_id"] == "vibration_mm_s" and int(row["reading_id"].rsplit("-", 1)[-1]) >= 216:
                row["quality"] = "sensor_fault"
    else:
        dataset["readings"] = [row for row in dataset["readings"]
                               if not (row["asset_ref"] == "BMS:CHWP01" and row["point_id"] == "vibration_mm_s"
                                       and 42 <= int(row["reading_id"].rsplit("-", 1)[-1]) < 102)]
    output = _analyze(dataset)
    assert _pump_case(output) is None
    assert any(issue["asset_id"] == "PUMP-01" for issue in output["quality_issues"])
    if damage == "missing":
        assert any(issue["issue_type"] == "stale" and issue["asset_id"] == "PUMP-01"
                   and issue["point_id"] == "vibration_mm_s" for issue in output["quality_issues"])
    if damage == "baseline_gap":
        abstention = next(case for case in output["cases"]
                          if case["case_id"] == "INSUFFICIENT-PUMP-01")
        assert not abstention["ai_eligible"]
        assert "No pump condition decision" in " ".join(abstention["observations"])


def test_cutoff_before_pump_rise_and_truth_change_do_not_create_case():
    dataset = generate_dataset("pump_degradation", 42)
    assert _pump_case(_analyze(dataset, as_of="2026-09-22T11:59:59+00:00")) is None
    changed = deepcopy(dataset)
    changed["ground_truth"] = {"scenario_id": "pump_load_change", "synthetic_only": True}
    changed["metadata"]["scenario_id"] = "pump_load_change"
    assert _analyze(changed) == _analyze(dataset)


def test_other_asset_highs_cannot_supply_pump_evidence():
    dataset = generate_dataset("pump_load_change", 42)
    for row in dataset["readings"]:
        if row["asset_ref"] == "BMS:EF01" and row["point_id"] in {"vibration_mm_s", "bearing_temp_c", "motor_current_a"}:
            step = int(row["reading_id"].rsplit("-", 1)[-1])
            if 216 <= step <= 249:
                row["value"] += {"vibration_mm_s": 3, "bearing_temp_c": 13, "motor_current_a": 7}[row["point_id"]]
    assert _pump_case(_analyze(dataset)) is None


def test_older_unrelated_asset_reading_cannot_shift_pump_baseline():
    dataset = generate_dataset("pump_degradation", 42)
    original = _pump_case(_analyze(dataset))
    unrelated = next(row for row in dataset["readings"] if row["asset_ref"] == "BMS:AHU01")
    dataset["readings"].append(dict(unrelated, reading_id="OLDER-AHU-READING",
                                    observed_at="2026-09-20T00:00:00+00:00",
                                    ingested_at="2026-09-20T00:01:00+00:00"))
    shifted = _pump_case(_analyze(dataset))
    assert shifted == original
