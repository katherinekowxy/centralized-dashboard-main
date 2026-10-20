"""Site overview: figures come from the modules that own them, each appears once, and replay figures stay apart."""

import sys
from pathlib import Path

from streamlit.testing.v1 import AppTest

from demo import asset_dashboard, event_power, ptw_dashboard, site_overview
from site_fixture import FAKE_DB

APP = Path(__file__).resolve().parents[1] / "app.py"


def test_counts_match_the_owning_pages() -> None:
    data = site_overview.summary(FAKE_DB)
    rows = asset_dashboard.board(FAKE_DB)["rows"]
    assert data["states"] == {state: sum(row["state"] == state for row in rows) for state in data["states"]}
    assert data["monitored"] == len(rows) == sum(data["states"].values())
    permits = ptw_dashboard.todays_permits(FAKE_DB)["rows"]
    assert data["permits"]["active"] == sum(row["active"] for row in permits)
    sockets = sum(len(item["sockets"]) for item in event_power.board(FAKE_DB)["boxes"])
    assert sum(data["sockets"].values()) == sockets
    assert data["diagnostics"] is None  # no replay passed: nothing is invented in its place


def test_attention_lists_problems_first_with_the_kind_of_fact() -> None:
    data = site_overview.summary(FAKE_DB)
    downs = [row for row in data["attention"] if row["kind"] == "Asset state" and row["state"] == "down"]
    assert len(downs) == data["states"]["down"] == 2
    assert data["attention"][0]["word"] == "Down"
    assert all(row["kind"] in {"Asset state", "Event power", "Planning clash"} for row in data["attention"])
    assert all(row["href"].startswith("?") for row in data["attention"])


def test_page_has_no_health_score_and_labels_synthetic_and_replay_data() -> None:
    run = {"analysis": {"cases": [{"category": "condition"}, {"category": "data_quality"}], "quality_issues": [{}]},
           "history": [], "as_of": "2026-09-22T23:50:00+00:00", "scenario_id": "leakage_ramp"}
    page = site_overview.page_html(site_overview.summary(FAKE_DB, run))
    lowered = page.lower()
    assert "health score" not in lowered and "% healthy" not in lowered and "risk score" not in lowered
    assert "not a risk rating" in lowered and "not a live feed" in lowered and "no live feed is connected" in lowered
    assert "Diagnostics replay" in page and "not added to the counts above" in page
    assert '<b>1</b><span>detector findings to review' in page and '<b>1</b><span>other cases' in page


def test_app_lands_on_the_overview(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "demo.site_db", FAKE_DB)
    at = AppTest.from_file(str(APP), default_timeout=90).run()
    assert not at.exception
    markup = "\n".join(item.value for item in at.markdown)
    assert "Needs attention" in markup and "Asset health" in markup and "Demo data" in markup
    assert "Set GBB_DATA_DIR" in markup  # without the export folder the page says so instead of showing empty figures
