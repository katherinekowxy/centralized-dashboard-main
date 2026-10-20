"""Asset overview: both sources listed under shared categories, status columns kept apart, specialist pages linked."""

import sys
from pathlib import Path

from streamlit.testing.v1 import AppTest

from demo import asset_catalogue as ac
from demo.asset_dashboard import board
from site_fixture import FAKE_DB

APP = Path(__file__).resolve().parents[1] / "app.py"
PUMP = {"asset_id": "PUMP-01", "name": "Chilled Water Pump 01", "asset_type": "pump", "location": "Energy Centre", "criticality": "high"}


def test_site_rows_cover_the_register_and_keep_operational_state() -> None:
    rows = ac.site_rows(FAKE_DB)
    assert {row["asset_id"] for row in rows} == {asset["asset_id"] for asset in FAKE_DB.assets()}
    monitored = {row["asset_id"]: row["state"] for row in board(FAKE_DB, include_event_power=True)["rows"]}
    for row in rows:
        assert row["source"] == ac.SITE and row["finding"] == "No detector" and row["finding_key"] is None
        assert row["state"] == monitored.get(row["asset_id"], "unmonitored")
        assert row["href"] == f"?asset={row['asset_id']}"


def test_replay_rows_report_findings_but_no_operational_state() -> None:
    row = ac.replay_row(PUMP, "alert", "Bearing temperature finding", ["Motor current", "Bearing temp"], 2, "fresh")
    assert row["category"] == "Pumps" and row["state"] is None
    assert row["operational"] == "Not reported" and row["finding"] == "Detector finding"
    assert row["work"] == "2 open work orders" and ac.needs_attention(row)
    assert not ac.needs_attention(ac.replay_row(PUMP, "idle", "Not assessed", [], 0, "missing"))


def test_categories_filters_and_attention_ordering() -> None:
    rows = ac.site_rows(FAKE_DB) + [ac.replay_row(PUMP, "ok", "No finding", [], 0, "fresh")]
    counts = {item["category"]: item for item in ac.category_counts(rows)}
    assert counts["Pumps"]["replay"] == 1 and counts["Pumps"]["total"] == counts["Pumps"]["site"] + 1
    assert all(name in (*ac.CATEGORIES, "Other") for name in counts)
    chillers = ac.select(rows, categories=["Chillers"])
    assert chillers and all(row["category"] == "Chillers" for row in chillers)
    flagged = ac.select(rows, attention_only=True)
    assert flagged and all(ac.needs_attention(row) for row in flagged)
    ordered = ac.select(rows)
    assert ordered[0]["state"] == "down"  # problems first
    assert ac.select(rows, sources=[ac.REPLAY]) == [rows[-1]]


def test_page_lists_both_sources_and_opens_the_engineering_view(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "demo.site_db", FAKE_DB)
    at = AppTest.from_file(str(APP), default_timeout=90)
    at.query_params["view"] = "assets"
    at.run()
    assert not at.exception
    table = at.dataframe[0].value
    assert {ac.SITE, ac.REPLAY} == set(table["Source"])
    assert set(table.loc[table["Source"] == ac.REPLAY, "Operational state"]) == {"Not reported"}
    assert set(table.loc[table["Source"] == ac.SITE, "Diagnostic finding"]) == {"No detector"}
    markup = "\n".join(item.value for item in at.markdown)
    assert "Demo data" in markup and "Asset overview" in markup
