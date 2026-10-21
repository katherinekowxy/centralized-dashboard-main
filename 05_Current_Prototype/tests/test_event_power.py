"""Event power: OG boxes with their CEEform sockets, simulated loads, socket words, no supply from an isolated DB, and
event power kept off the Asset dashboard and Asset schematic."""

import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from streamlit.testing.v1 import AppTest

from demo import asset_dashboard, asset_schematic, event_power, site_seed
from demo.asset_state import COLOUR
from site_fixture import FAKE_DB, seeded_db

APP = Path(__file__).resolve().parents[1] / "app.py"
AS_OF = datetime(2026, 10, 13, 6, 0, tzinfo=timezone.utc)  # 14:00 SGT


@pytest.fixture()
def db():
    path = Path(__file__).resolve().parents[1] / "data" / f"test-event-power-{uuid4().hex}.sqlite3"
    site_seed.build(path, AS_OF)
    yield seeded_db(path)
    path.unlink(missing_ok=True)


def by_name(data: dict, name: str) -> dict:
    return next(item for item in data["boxes"] if item["box"]["name"] == name)


def test_boxes_problems_first_with_socket_counts(db) -> None:
    data = event_power.board(db)
    assert [item["box"]["name"] for item in data["boxes"]] == [
        "Meadow OG box 2", "LG-OG-4", "LG-OG-3", "Active Garden OG box", "Plaza OG box"]  # a zone's boxes together
    assert [len(item["sockets"]) for item in data["boxes"]] == [5, 5, 4, 4, 4]
    tally = event_power.tally_html(data)
    for count, words in [(1, "Tripped"), (4, "No supply"), (1, "Warning"), (10, "In use"), (6, "Free")]:
        assert f"<b>{count}</b>{words}" in tally


def test_live_event_loads_and_socket_words(db) -> None:
    meadow = by_name(event_power.board(db), "Meadow OG box 2")
    assert meadow["live"] and meadow["event"]["title"] == "Music festival"
    page = event_power.box_html(meadow)
    assert "until 19:00" in page and "Next:" not in page
    bar = next(row for row in meadow["sockets"] if row["asset_id"] == "MDW-CEE-07")
    assert bar["state"] == "down" and f'--c:{COLOUR["down"]}' in event_power.socket_html(bar, 2, meadow)
    assert "Tripped" in event_power.socket_html(bar, 2, meadow) and "Bar" in event_power.socket_html(bar, 2, meadow)
    market = by_name(event_power.board(db), "Active Garden OG box")
    stalls = next(row for row in market["sockets"] if row["asset_id"] == "ACT-CEE-02")
    html = event_power.socket_html(stalls, 2, market)
    assert stalls["state"] == "warning" and "</i>Warning</span>" in html and "18<small> / 16 A" in html and "Food stalls" in html


def test_an_isolated_db_leaves_its_box_without_supply_and_flags_the_next_event(db) -> None:
    grove = by_name(event_power.board(db), "LG-OG-3")
    assert grove["dead"] and grove["state"] == event_power.NO_SUPPLY
    page = event_power.box_html(grove)
    assert f"--line:{event_power.DEAD_LINE};--ls:dashed" in page
    assert page.count('</i>No supply</span>') == 5        # shown on the box and its four sockets
    assert "Next: Corporate reception · 17:00 · no power until 19:00" in page and "ep-clash" in page
    assert "17:00: Catering" in page                        # what each socket is booked for later today
    assert "Grove DB 3<small style=\"color:#fff\">Down until 19:00" in page


def test_a_box_with_no_event_today_says_so(db) -> None:
    plaza = by_name(event_power.board(db), "Plaza OG box")
    assert plaza["event"] is None and "No event today" in event_power.box_html(plaza)


def test_event_power_stays_off_the_asset_views_but_opens_on_the_asset_page(db) -> None:
    kinds = {row["asset_type"] for row in asset_dashboard.board(db)["rows"]}
    assert not kinds & {"OGB", "CEE"}
    assert not {row["asset_type"] for row in asset_schematic.schematic(db)["rows"].values()} & {"OGB", "CEE"}
    assert any(row["asset_id"] == "MDW-CEE-01" for row in asset_dashboard.board(db, include_event_power=True)["rows"])


def test_tab_renders_and_the_permit_page_says_the_box_has_no_supply(monkeypatch, db) -> None:
    monkeypatch.setitem(sys.modules, "demo.site_db", db)
    at = AppTest.from_file(str(APP), default_timeout=60)
    at.query_params["all"] = "1"
    at.run()
    at.button(key="nav-event-power").click().run()
    assert not at.exception
    assert "LG-OG-4" in "\n".join(item.value for item in at.markdown)
    permit = AppTest.from_file(str(APP), default_timeout=60)
    permit.query_params["ptw"] = "PTW-2026-0142"
    permit.run()
    assert "LG-OG-3 · No supply" in "\n".join(item.value for item in permit.markdown)


def test_empty_database_shows_a_message(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "demo.site_db", FAKE_DB)
    at = AppTest.from_file(str(APP), default_timeout=60)
    at.query_params["all"] = "1"
    at.run()
    at.button(key="nav-event-power").click().run()
    assert not at.exception and "No OG boxes" in at.info[0].value
