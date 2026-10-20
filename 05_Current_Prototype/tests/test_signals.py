"""Diagnostic status dots: red only on a detector finding or trip, never on an unusual reading."""

import pandas as pd
import pytest

from demo.asset_data import build_asset_bucket
from demo.engine import ASSETS, DETECTOR_ASSET_IDS, analyze, generate_dataset
from demo.history import generate_history
from demo.signals import _status, asset_status, point_name, point_signals, point_unit


def _fleet(scenario: str) -> dict:
    dataset = generate_dataset(scenario, 42)
    analysis = analyze(dataset["readings"], dataset["events"])
    as_of = analysis["metrics"]["as_of"]
    run = {"dataset": dataset, "analysis": analysis, "as_of": as_of, "history": generate_history(as_of)}
    fleet = {}
    for asset in ASSETS:
        bucket = build_asset_bucket(run, asset["asset_id"])
        signals = point_signals(bucket)
        fleet[asset["asset_id"]] = (signals.set_index("point_id"), asset_status(bucket, signals))
    return fleet


def test_names_and_units_keep_engineering_case() -> None:
    assert (point_name("leakage_ma"), point_unit("leakage_ma")) == ("Earth leakage", "mA")
    assert (point_name("differential_pressure_kpa"), point_unit("differential_pressure_kpa")) == ("Differential pressure", "kPa")
    assert (point_name("vibration_mm_s"), point_unit("vibration_mm_s")) == ("Vibration", "mm/s")
    assert (point_name("supply_temp_c"), point_unit("supply_temp_c")) == ("Supply temp", "°C")
    assert point_unit("flow_l_s") == "L/s"


@pytest.mark.parametrize("scenario", ["normal", "high_neutral"])
def test_no_finding_means_no_red_and_no_amber(scenario) -> None:
    for asset_id, (signals, state) in _fleet(scenario).items():
        assert set(signals["status"]) <= {"ok", "idle"}
        assert state["status"] == ("ok" if asset_id in DETECTOR_ASSET_IDS else "idle")


def test_an_unusual_reading_alone_never_changes_the_dot() -> None:
    # Far outside its typical band, but no detector finding cites it.
    row = {"freshness": "fresh", "latest": 999.0, "low": 10, "high": 20, "covered": True, "in_finding": False}
    assert _status("bearing_temp_c", row) == ("ok", "No finding")


def test_uncovered_assets_are_grey_not_green() -> None:
    row = {"freshness": "fresh", "latest": 15.0, "covered": False, "in_finding": False}
    assert _status("supply_temp_c", row) == ("idle", "Not assessed")
    for asset_id, (_, state) in _fleet("normal").items():
        if asset_id not in DETECTOR_ASSET_IDS:
            assert state["status"] == "idle" and "Not assessed" in state["headline"]


def test_leakage_finding_turns_the_cited_point_red() -> None:
    signals, state = _fleet("leakage_ramp")["DB-01"]
    assert signals.loc["leakage_ma", "status"] == "alert"
    assert signals.loc["phase_voltage_v", "status"] == "ok"
    assert state["status"] == "alert" and "earth leakage" in state["headline"].lower()


def test_recent_trip_stays_red_after_the_bit_clears() -> None:
    signals, state = _fleet("sudden_trip")["DB-01"]
    assert signals.loc["relay_trip", "status"] == "alert"
    assert signals.loc["relay_trip", "note"].startswith("Tripped")
    assert state["status"] == "alert"


def test_stale_feed_is_grey_cannot_assess() -> None:
    signals, state = _fleet("telemetry_dropout")["DB-01"]
    assert signals.loc["leakage_ma", "note"] == "Stale"
    assert signals.loc["leakage_ma", "status"] == "idle"
    assert state["status"] == "idle" and "cannot assess" in state["headline"]


def test_missing_value_is_no_data() -> None:
    row = {"freshness": "fresh", "latest": float("nan"), "covered": True, "in_finding": False}
    assert _status("motor_current_a", row) == ("idle", "No data")
    assert asset_status({"asset": {"asset_id": "DB-01"}, "freshness": "fresh", "cases": []},
                        pd.DataFrame([{"status": "ok", "note": "No finding", "name": "Vibration"}]))["status"] == "ok"
