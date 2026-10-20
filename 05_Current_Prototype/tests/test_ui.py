"""Checks for the chart-first local demo and its drilldowns."""

import json
from pathlib import Path
import sys
from types import SimpleNamespace
from uuid import uuid4

import pandas as pd
import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest


APP = Path(__file__).resolve().parents[1] / "app.py"
sys.path.insert(0, str(APP.parent))

from demo import feedback, imports, navigation


@pytest.fixture(autouse=True)
def isolated_import_registry(monkeypatch):
    """UI checks should not read or modify the operator's persistent registry."""
    test_db = APP.parent / "data" / f"test-import-registry-{uuid4().hex}.sqlite3"
    monkeypatch.setattr(imports, "DEFAULT_DB", test_db)
    yield
    test_db.unlink(missing_ok=True)


def _plot(at: AppTest, index: int) -> dict:
    return json.loads(at.get("plotly_chart")[index].proto.spec)


def _diagnostics(timeout: int = 30) -> AppTest:
    """The app opens on the Site dashboards; these checks cover the Diagnostics demo area."""
    at = AppTest.from_file(str(APP), default_timeout=timeout)
    at.session_state["nav"] = "diagnostics"
    return at


def _go(at: AppTest, page: str) -> AppTest:
    """Open a workbench page by its workbench name, through its sidebar button."""
    return at.button(key=f"nav-{navigation.BY_REPLAY_PAGE[page]}").click().run()


def test_external_references_are_separate_and_all_platforms_render() -> None:
    at = _diagnostics().run()
    _go(at, "System map")
    assert not at.exception
    _go(at, "Exploratory")
    assert not at.exception
    assert not any(widget.label == "Scenario" for widget in at.selectbox)
    assert not any(button.label == "Run replay" for button in at.button)
    picker = next(widget for widget in at.selectbox if widget.label == "Platform")
    assert len(picker.options) == 11
    for name in picker.options:
        next(widget for widget in at.selectbox if widget.label == "Platform").set_value(name).run()
        assert not at.exception
        markup = "\n".join(item.value for item in at.markdown)
        assert "Reference only · not integrated" in markup
        assert "demo / synthetic" not in markup
        assert "not SignalDesk" in markup
    _go(at, "Overview")
    assert not at.exception
    assert any(button.label == "Open DB-01" for button in at.button)


def test_default_overview_is_five_asset_cards() -> None:
    at = _diagnostics().run()
    assert not at.exception
    assert at.session_state["nav"] == "diagnostics" and at.query_params["view"] == ["diagnostics"]
    for key in navigation.BY_REPLAY_PAGE.values():
        assert at.button(key=f"nav-{key}")
    assert not at.get("plotly_chart")  # Overview is status dots only; graphs live on the asset page.
    assert not at.dataframe  # Detail tables stay off the landing view.
    markup = "\n".join(item.value for item in at.markdown)
    assert "Demo scenario" in markup
    assert "Open jobs" in markup and "Detector not assessed" in markup
    assert "<b>1</b> need attention" in markup and "Sustained rise in earth leakage" in markup
    # Attention first: DB-01's card and button precede the in-range assets.
    opens = [button.label for button in at.button if button.label.startswith("Open ")]
    assert opens[0] == "Open DB-01"
    for aid in ("PUMP-01", "AHU-01", "FAN-01", "CHILLER-01", "DB-01"):
        assert any(button.label == f"Open {aid}" for button in at.button)
    assert next(expander for expander in at.expander if expander.label == "Demo controls").proto.expanded is False
    assert any(button.label == "Run replay" for button in at.button)


def test_scenario_and_asset_switch_update_selected_charts() -> None:
    at = _diagnostics().run()
    scenario = next(widget for widget in at.selectbox if widget.label == "Scenario")
    scenario.set_value("normal").run()
    assert any("settings changed" in warning.value.lower() for warning in at.warning)
    next(button for button in at.button if button.label == "Run replay").click().run()
    assert not at.exception
    assert "Normal daily cycle" in "\n".join(item.value for item in at.markdown)
    next(button for button in at.button if button.label == "Open AHU-01").click().run()
    assert not at.exception
    assert at.session_state["nav"] == "asset-engineering"
    assert next(widget for widget in at.selectbox if widget.label == "Asset").value == "AHU-01"
    assert "Detector not assessed" in "\n".join(item.value for item in at.markdown)
    schematic = _plot(at, 0)
    assert all(trace["meta"]["asset_id"] == "AHU-01" for trace in schematic["data"])


def test_dropout_keeps_full_time_axis_and_does_not_bridge_gap() -> None:
    at = _diagnostics().run()
    next(widget for widget in at.selectbox if widget.label == "Scenario").set_value("telemetry_dropout")
    next(button for button in at.button if button.label == "Run replay").click().run()
    assert not at.exception
    assert "Feed partial" in "\n".join(item.value for item in at.markdown)
    next(button for button in at.button if button.label == "Open DB-01").click().run()
    assert not at.exception
    plots = [_plot(at, i) for i in range(len(at.get("plotly_chart")))]
    trend = next(fig for fig in plots if fig["layout"].get("yaxis", {}).get("title", {}).get("text") == "Earth leakage (mA)")
    end = pd.Timestamp(trend["layout"]["xaxis"]["range"][1])
    last = max(pd.to_datetime(trace["x"][-1], utc=True) for trace in trend["data"] if len(trace.get("x", [])))
    assert end - last > pd.Timedelta(hours=3)
    assert "Detector: data incomplete" in "\n".join(item.value for item in at.markdown)


@pytest.mark.parametrize("aid", ["PUMP-01", "AHU-01", "FAN-01", "CHILLER-01", "DB-01"])
def test_asset_drilldown_scopes_schematic_sources_and_aligned_windows(aid) -> None:
    at = _diagnostics().run()
    next(button for button in at.button if button.label == f"Open {aid}").click().run()
    assert not at.exception
    assert [tab.label for tab in at.tabs] == ["Mechanical", "Electrical", "Process", "Maintenance history", "Events"]
    next(widget for widget in at.selectbox if widget.label == "Shared time range").set_value("Last 6 hours").run()
    assert not at.exception
    plots = [_plot(at, i) for i in range(len(at.get("plotly_chart")))]
    assert all(trace["meta"]["asset_id"] == aid for trace in plots[0]["data"])
    time_plots = [fig for fig in plots if "xaxis" in fig["layout"]]
    ranges = {tuple(fig["layout"]["xaxis"]["range"]) for fig in time_plots}
    assert len(ranges) == 1
    start, end = map(pd.Timestamp, next(iter(ranges)))
    assert end - start == pd.Timedelta(hours=6)
    for table in at.dataframe:
        frame = table.value
        if "reading_id" in frame:
            assert frame["reading_id"].str.contains(aid, regex=False).all()
            timestamps = pd.to_datetime(frame["observed_at"], utc=True)
            assert timestamps.between(start, end).all()
    next(widget for widget in at.selectbox if widget.label == "Schematic view").set_value("Top").run()
    assert not at.exception
    assert _plot(at, 0)["layout"]["scene"]["camera"]["eye"]["z"] == 2.5


def test_old_maintenance_event_focus_does_not_invent_telemetry() -> None:
    at = _diagnostics().run()
    next(button for button in at.button if button.label == "Open PUMP-01").click().run()
    orders = at.session_state["replay"]["history"]
    order = next(row for row in orders if row["asset_id"] == "PUMP-01" and row["status"] == "closed")
    focus = next(widget for widget in at.selectbox if widget.label == "Focus fault / event")
    focus.set_value(next(option for option in focus.options if option.startswith(f"WO:{order['work_order_id']} "))).run()
    assert not at.exception
    assert next(widget for widget in at.selectbox if widget.label == "Shared time range").value == "Focus selected event"
    plots = [_plot(at, i) for i in range(len(at.get("plotly_chart")))]
    assert all(not fig["data"] for fig in plots if "xaxis" in fig["layout"])
    assert any("predates" in item.value for item in at.info)
    next(widget for widget in at.selectbox if widget.label == "Asset").set_value("AHU-01").run()
    assert not at.exception  # A prior asset's focus must not break navigation.


def test_maintenance_history_and_table_filter() -> None:
    at = _go(_diagnostics().run(), "Maintenance")
    assert not at.exception
    assert len(at.get("plotly_chart")) == 2
    assert next(widget for widget in at.selectbox if widget.label == "History asset").value == "All assets"
    assert not any(widget.label == "Asset" for widget in at.selectbox)
    timeline = _plot(at, 0)
    assert sum(len(trace["x"]) for trace in timeline["data"]) == 28
    assert timeline["layout"]["showlegend"] is False  # legend is HTML above the chart, so it never hides dots
    assert any("Status at cutoff" in item.value for item in at.markdown)
    assert next(expander for expander in at.expander if expander.label == "Work orders").proto.expanded is False
    assert len(at.dataframe) == 1
    full = at.dataframe[0].value
    assert {"Order", "Asset", "Fault", "Status", "Downtime h"}.issubset(full.columns)
    assert len(full) == 28
    assert full.loc[full["Status"] != "closed", "Downtime h"].isna().all()
    next(widget for widget in at.selectbox if widget.label == "History asset").set_value("DB-01").run()
    assert not at.exception
    timeline = _plot(at, 0)
    assert sum(len(trace["x"]) for trace in timeline["data"]) == 6
    assert set(at.dataframe[0].value["Asset"]) == {"DB-01"}
    next(widget for widget in at.selectbox if widget.label == "Table status").set_value("open").run()
    assert not at.exception
    assert set(at.dataframe[0].value["Status"]) == {"open"}


def test_existing_session_replay_is_upgraded_for_history() -> None:
    at = _diagnostics().run()
    old_run = dict(at.session_state["replay"])
    old_run.pop("history")
    old_run.pop("as_of")
    at.session_state["replay"] = old_run
    at.run()
    assert not at.exception
    assert len(at.session_state["replay"]["history"]) >= 5
    assert any(button.label == "Open DB-01" for button in at.button)


def test_messy_replay_shows_original_held_rows_in_investigate() -> None:
    at = _diagnostics().run()
    next(widget for widget in at.selectbox if widget.label == "Scenario").set_value("messy_ingestion")
    next(button for button in at.button if button.label == "Run replay").click().run()
    _go(at, "Investigate")
    assert not at.exception
    held_tables = [table.value for table in at.dataframe if "reason" in table.value.columns]
    assert held_tables
    held = held_tables[0]
    assert {"reading_id", "asset_ref", "value", "unit", "reason"}.issubset(held.columns)
    assert len(held) > 0


def test_explicit_ai_falls_back_and_review_keeps_replay_context(monkeypatch) -> None:
    test_db = APP.parent / "data" / f"test-feedback-{uuid4().hex}.sqlite3"
    monkeypatch.setattr(feedback, "DB_PATH", test_db)
    for name in ("DEMO_AI_BASE_URL", "DEMO_AI_MODEL", "DEMO_AI_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    try:
        at = _go(_diagnostics().run(), "Investigate")
        assert not at.exception
        next(button for button in at.button if button.label == "Request AI explanation").click().run()
        assert not at.exception
        assert any("AI is not configured" in caption.value for caption in at.caption)
        next(widget for widget in at.text_input if widget.label == "Note (optional)").set_value("Checked source trace")
        next(button for button in at.button if button.label == "Save review").click().run()
        assert not at.exception
        records = feedback.load_feedback()
        assert len(records) == 1
        assert records[0]["note"] == "Checked source trace"
        assert records[0]["context"]["scenario_id"] == "leakage_ramp"
        assert records[0]["context"]["replay_fingerprint"]
    finally:
        test_db.unlink(missing_ok=True)


def test_sixth_asset_and_import_survive_fresh_app_session(monkeypatch) -> None:
    test_db = APP.parent / "data" / f"test-import-ui-{uuid4().hex}.sqlite3"
    monkeypatch.setattr(imports, "DEFAULT_DB", test_db)
    at = _go(_diagnostics().run(), "Data import")
    assert not at.exception
    next(item for item in at.text_input if item.label == "Canonical ID").set_value("PUMP-02")
    next(item for item in at.text_input if item.label == "Asset name").set_value("Annex pump")
    next(item for item in at.text_input if item.label == "Location").set_value("Annex / Plant")
    next(item for item in at.selectbox if item.label == "Asset type").set_value("pump")
    next(button for button in at.button if button.label == "Add asset").click().run()
    assert not at.exception
    assert any(asset["asset_id"] == "PUMP-02" for asset in imports.list_assets())
    rows = [f"VENDOR-P2,2026-10-05T{hour:02d}:00:00+00:00,motor_current_a,{30 + hour},A,running"
            for hour in range(6)]
    content = ("equipment_ref,timestamp,point,value,unit,operating_mode\n" + "\n".join(rows) + "\n").encode()
    upload = SimpleNamespace(name="annex-vendor.csv", size=len(content), getvalue=lambda: content)
    monkeypatch.setattr(st, "file_uploader", lambda *args, **kwargs: upload)
    at.run()
    assert not at.exception
    assert any("6 ready" in item.value and "0 errors" in item.value for item in at.markdown)
    next(button for button in at.button if button.label == "Save import").click().run()
    assert not at.exception
    assert any("Saved 6 readings" in item.value for item in at.success)
    again = imports.commit_import(content, "PUMP-02", "VENDOR-P2", filename="annex-vendor.csv")
    assert (again["saved"], again["skipped"]) == (0, 6)

    fresh = _diagnostics().run()
    assert not fresh.exception
    next(button for button in fresh.button if button.label == "Open PUMP-02").click().run()
    assert not fresh.exception
    assert next(item for item in fresh.selectbox if item.label == "Asset").value == "PUMP-02"
    assert any("Imported snapshot" in item.value for item in fresh.caption)
    assert any("Schematic unavailable" in item.value for item in fresh.info)
    imported_tables = [table.value for table in fresh.dataframe if "source_file" in table.value.columns]
    assert imported_tables
    records = next(table for table in imported_tables if "source_hash" in table.columns)
    assert len(records) == 6
    assert set(records["source_file"]) == {"annex-vendor.csv"}
    assert set(records["source_equipment_ref"]) == {"VENDOR-P2"}
    test_db.unlink(missing_ok=True)
