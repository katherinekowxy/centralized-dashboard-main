"""Asset schematic: only problems and maintenance show, under their DB; a down DB lists everything it feeds; the rest folds away."""

import html
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from streamlit.testing.v1 import AppTest

from demo import asset_schematic, site_seed, site_theme
from site_fixture import FAKE_DB, seeded_db

APP = Path(__file__).resolve().parents[1] / "app.py"


@pytest.fixture()
def seeded():
    path = Path(__file__).resolve().parents[1] / "data" / f"test-schematic-{uuid4().hex}.sqlite3"
    site_seed.build(path, datetime(2026, 10, 12, 6, 0, tzinfo=timezone.utc))
    yield seeded_db(path)
    path.unlink(missing_ok=True)


def test_feeds_and_states_from_the_fixture() -> None:
    data = asset_schematic.schematic(FAKE_DB)
    assert data["feeds"]["SGV-DB-03"] == ["SGV-OUT-01", "SGV-OUT-02"]  # the down outlets before the device with no readings
    assert data["rows"]["SGV-OUT-02"]["state"] == "unconnected"
    assert data["rows"]["SGV-DB-03"]["state"] == "down"
    assert data["roots"]["SGV"][0] == "SGV-DB-03"                    # the zone's worst DB first


def test_a_down_db_lists_everything_it_feeds() -> None:
    data = asset_schematic.schematic(FAKE_DB)
    branch, states = asset_schematic.branch_html("SGV-DB-03", data)
    assert 'class="tv-feeds tv-dead"' in branch                      # the feed line turns red and dashed
    assert 'href="?asset=SGV-OUT-01"' in branch and "<b>Down</b>Grove outlets" in branch
    assert "<b>No supply</b>Kiosk outlets<small>Its DB is down · not connected</small>" in branch
    assert 'href="?asset=SGV-OUT-02"' not in branch                   # no readings, so nothing to open
    assert states.count("down") == 2 and states.count(site_theme.NO_SUPPLY) == 1


def _shown_below(asset_id: str, data: dict) -> bool:
    return any(asset_schematic.needs_attention(data["rows"][child]) or _shown_below(child, data)
               for child in data["feeds"].get(asset_id, []))


def test_only_problems_maintenance_and_their_parent_dbs_show(seeded) -> None:
    data = asset_schematic.schematic(seeded)
    page = asset_schematic.board_html(data)
    down_dbs = {aid for aid, row in data["rows"].items() if row["asset_type"] == "DB" and row["state"] == "down"}
    for asset_id, row in data["rows"].items():
        connected = row["state"] != "unconnected"
        marker = f'href="?asset={asset_id}"' if connected else f"({asset_id})"
        expected = asset_schematic.needs_attention(row) or _shown_below(asset_id, data) or row.get("fed_from") in down_dbs
        assert (marker in page) is expected, asset_id
    zones = [html.unescape(part.split("<")[0]) for part in page.split('<div class="tv-zh"><span>')[1:]]
    assert zones[0] in {"Supertree Grove", "Cloud Forest"}
    hidden = sum(1 for roots in data["roots"].values() for root in roots if not asset_schematic.branch_html(root, data)[0])
    assert f"{hidden} other DBs · all normal" in page and hidden > 5


def test_nothing_wrong_says_so() -> None:
    data = asset_schematic.schematic(FAKE_DB)
    for row in data["rows"].values():
        row.update(state="operational" if row["state"] != "unconnected" else "unconnected", maintenance=[])
    page = asset_schematic.board_html(data)
    assert "All assets normal" in page and "tv-zh" not in page


def test_a_feed_loop_in_bad_data_does_not_hang() -> None:
    rows = [{**row, "fed_from": "SGV-OUT-01"} if row["asset_id"] == "SGV-DB-03" else row for row in FAKE_DB.assets()]
    looped = type(FAKE_DB)(**{**vars(FAKE_DB), "assets": lambda: rows})
    page = asset_schematic.board_html(asset_schematic.schematic(looped))
    for asset_id in ("SGV-DB-03", "SGV-OUT-01"):  # both sit in the loop, so neither has a DB above it; both are still shown
        assert f'href="?asset={asset_id}"' in page


def test_tab_renders_and_the_permit_page_names_unconnected_devices(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "demo.site_db", FAKE_DB)
    at = AppTest.from_file(str(APP), default_timeout=60)
    at.query_params["all"] = "1"
    at.run()
    at.button(key="nav-electrical").click().run()
    assert not at.exception
    text = "\n".join(item.value for item in at.markdown)
    assert "Kiosk outlets" in text and "Down</small><b>2</b>" in text and "Supertree lights" not in text  # idle: hidden
    permit = AppTest.from_file(str(APP), default_timeout=60)
    permit.query_params["ptw"] = "PTW-2026-0142"
    permit.run()
    assert "Kiosk outlets · Not connected" in "\n".join(item.value for item in permit.markdown)
    unconnected = AppTest.from_file(str(APP), default_timeout=60)
    unconnected.query_params["asset"] = "SGV-OUT-02"
    unconnected.run()
    assert not unconnected.exception and "Not connected" in "\n".join(item.value for item in unconnected.markdown)
