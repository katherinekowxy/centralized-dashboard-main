"""Descriptive synthetic CMMS history and cutoff behavior."""

from datetime import datetime, timedelta
from statistics import median

from demo.engine import ASSETS
from demo.history import generate_history, summarize_history


AS_OF = "2026-09-22T23:50:00+00:00"


def _dt(value):
    return datetime.fromisoformat(value)


def test_history_is_deterministic_chronological_and_censored():
    rows = generate_history(AS_OF)
    assert rows == generate_history(AS_OF)
    assert 20 <= len(rows) <= 30
    assert len({row["work_order_id"] for row in rows}) == len(rows)
    assert {row["asset_id"] for row in rows} == {asset["asset_id"] for asset in ASSETS}
    assert {"Earth leakage", "Relay trip", "Filter restriction", "Belt wear", "Bearing vibration", "Seal leak", "Cooling performance"} <= {row["fault_type"] for row in rows}
    cutoff = _dt(AS_OF)
    assert all(cutoff - timedelta(days=90) <= _dt(row["reported_at"]) <= cutoff for row in rows)
    assert [row["reported_at"] for row in rows] == sorted((row["reported_at"] for row in rows), reverse=True)
    for row in rows:
        assert row["priority"] in {"high", "medium", "low"}
        assert row["status"] in {"open", "in_progress", "closed"}
        if row["status"] == "closed":
            assert _dt(row["reported_at"]) < _dt(row["closed_at"]) <= cutoff
            assert row["downtime_hours"] > 0
            assert row["resolution"]
        else:
            assert row["closed_at"] is None
            assert row["downtime_hours"] == 0
            assert row["resolution"] is None


def test_summary_reconciles_counts_weeks_downtime_and_assets():
    rows = generate_history(AS_OF)
    summary = summarize_history(rows, AS_OF)
    closed = [row for row in rows if row["status"] == "closed"]
    assert summary["total_faults"] == len(rows)
    assert summary["open_faults"] == len(rows) - len(closed)
    assert summary["closed_faults"] == len(closed)
    assert summary["downtime_hours"] == round(sum(row["downtime_hours"] for row in closed), 2)
    assert summary["median_resolution_hours"] == round(median((_dt(row["closed_at"]) - _dt(row["reported_at"])).total_seconds() / 3600 for row in closed), 2)
    assert sum(week["faults"] for week in summary["weekly"]) == len(rows)
    assert sum(week["closed"] for week in summary["weekly"]) == len(closed)
    assert sum(row["faults"] for row in summary["by_fault"]) == len(rows)
    assert sum(row["downtime_hours"] for row in summary["by_fault"]) == summary["downtime_hours"]
    assert all(_dt(week["week"]).weekday() == 0 for week in summary["weekly"])
    for asset in ASSETS:
        own = [row for row in rows if row["asset_id"] == asset["asset_id"]]
        filtered = summarize_history(rows, AS_OF, asset["asset_id"])
        assert filtered["total_faults"] == len(own)
        assert filtered["closed_faults"] == sum(row["status"] == "closed" for row in own)
        assert filtered["downtime_hours"] == round(sum(row["downtime_hours"] for row in own), 2)
        assert any(week["faults"] == 0 for week in filtered["weekly"])


def test_future_work_and_future_closure_are_not_observed():
    rows = generate_history(AS_OF)
    cutoff = _dt(AS_OF)
    future_report = {**rows[0], "work_order_id": "FUTURE", "reported_at": (cutoff + timedelta(hours=1)).isoformat()}
    future_close = {**rows[0], "work_order_id": "OPEN-AS-OF", "reported_at": (cutoff - timedelta(hours=2)).isoformat(), "status": "closed", "closed_at": (cutoff + timedelta(hours=2)).isoformat(), "downtime_hours": 12.0}
    summary = summarize_history(rows + [future_report, future_close], AS_OF)
    baseline = summarize_history(rows, AS_OF)
    assert summary["total_faults"] == baseline["total_faults"] + 1
    assert summary["open_faults"] == baseline["open_faults"] + 1
    assert summary["closed_faults"] == baseline["closed_faults"]
    assert summary["downtime_hours"] == baseline["downtime_hours"]


def test_history_shifts_with_cutoff_without_changing_episode_shape():
    moved = "2026-10-02T23:50:00+00:00"
    before = generate_history(AS_OF)
    after = generate_history(moved)
    assert len(after) == len(before)
    for old, new in zip(before, after):
        assert old["work_order_id"] == new["work_order_id"]
        assert _dt(new["reported_at"]) - _dt(old["reported_at"]) == timedelta(days=10)
        if old["closed_at"]:
            assert _dt(new["closed_at"]) - _dt(old["closed_at"]) == timedelta(days=10)


def test_empty_and_exact_rolling_window_boundary():
    cutoff = _dt(AS_OF)
    empty = summarize_history([], AS_OF)
    assert empty["total_faults"] == 0
    assert empty["median_resolution_hours"] is None
    assert all(week["faults"] == week["closed"] == 0 for week in empty["weekly"])
    base = generate_history(AS_OF)[0]
    just_outside = {**base, "reported_at": (cutoff - timedelta(days=90, seconds=1)).isoformat()}
    on_boundary = {**base, "reported_at": (cutoff - timedelta(days=90)).isoformat()}
    assert summarize_history([just_outside], AS_OF)["total_faults"] == 0
    assert summarize_history([on_boundary], AS_OF)["total_faults"] == 1
