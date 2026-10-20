"""Asset dashboard states: the five deterministic rules, their order, and the maintenance cone."""

from demo.asset_state import asset_state, in_operating_hours, maintenance_today

AS_OF = "2026-10-10T06:00:00+00:00"  # 14:00 SGT
ASSET = {"asset_id": "FDM-CHL-01", "idle_current_a": 5, "rated_current_a": 80, "operating_hours": "08:00-22:00"}


def latest(**values) -> dict:
    stamp = values.pop("at", "2026-10-10T05:45:00+00:00")
    base = {"current_a": 40, "voltage_v": 231, "power_factor": 0.92, "trip_state": 0}
    return {point: {"value": value, "observed_at": stamp} for point, value in {**base, **values}.items()}


def state(asset=ASSET, **values) -> str:
    return asset_state(asset, latest(**values), AS_OF)["state"]


def test_each_rule() -> None:
    assert state() == "operational"
    assert state(at="2026-10-10T05:00:00+00:00") == "offline"  # an hour without data
    assert state(trip_state=1) == "down"
    assert state(current_a=0.5) == "down"  # not running at 14:00 SGT, inside operating hours
    assert state({**ASSET, "operating_hours": "18:00-23:00"}, current_a=0.5) == "idle"
    assert state(voltage_v=258) == "warning"
    assert state(current_a=95) == "warning"
    assert state(power_factor=0.71) == "warning"


def test_order_offline_then_down_then_warning() -> None:
    assert state(at="2026-10-10T03:00:00+00:00", trip_state=1) == "offline"  # stale data can't prove a trip
    assert state(trip_state=1, voltage_v=258) == "down"
    assert asset_state(ASSET, {}, AS_OF) == {"state": "offline", "reason": "No data received"}
    assert asset_state(ASSET, latest(at="2026-10-10T04:00:00+00:00"), AS_OF)["reason"] == "No data for 2 h"


def test_operating_hours_are_sgt_and_may_cross_midnight() -> None:
    assert in_operating_hours("08:00-22:00", "2026-10-10T06:00:00+00:00")       # 14:00 SGT
    assert not in_operating_hours("08:00-22:00", "2026-10-10T15:00:00+00:00")   # 23:00 SGT
    assert in_operating_hours("18:00-02:00", "2026-10-10T17:30:00+00:00")       # 01:30 SGT
    assert in_operating_hours("24h", AS_OF) and in_operating_hours(None, AS_OF)


def test_cone_for_maintenance_today_or_an_active_permit() -> None:
    today = {"asset_id": "FDM-CHL-01", "status": "scheduled",
             "scheduled_start": "2026-10-10T01:00:00+00:00", "scheduled_end": "2026-10-10T03:00:00+00:00"}
    assert maintenance_today("FDM-CHL-01", [today], [], AS_OF)
    assert not maintenance_today("FDM-CHL-01", [{**today, "status": "done"}], [], AS_OF)
    tomorrow = {**today, "scheduled_start": "2026-10-10T17:00:00+00:00", "scheduled_end": "2026-10-10T18:00:00+00:00"}
    assert not maintenance_today("FDM-CHL-01", [tomorrow], [], AS_OF)  # 01:00 SGT on the 11th
    impact = {"target_type": "asset", "target_id": "FDM-CHL-01",
              "start_at": "2026-10-10T00:00:00+00:00", "end_at": "2026-10-10T09:00:00+00:00"}
    assert maintenance_today("FDM-CHL-01", [], [impact], AS_OF)
    assert not maintenance_today("FDM-CHL-01", [], [{**impact, "end_at": "2026-10-10T05:00:00+00:00"}], AS_OF)
