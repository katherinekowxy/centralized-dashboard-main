"""TV displays: every variant draws from owned figures with a source label, presentation mode hides all controls,
and the management page turns its assignments into bookmarkable screen and wall addresses."""

import sys
from pathlib import Path

from streamlit.testing.v1 import AppTest

from demo import displays, site_overview
from site_fixture import FAKE_DB

APP = Path(__file__).resolve().parents[1] / "app.py"


def ctx(**extra) -> dict:
    return {"summary": site_overview.summary(FAKE_DB), "cases": [], "real_permits": None, **extra}


def test_addresses_are_parsed_defensively() -> None:
    assert displays.parse_wall("assets,permits,coming-up,diagnostics") == ["assets", "permits", "coming-up", "diagnostics"]
    assert displays.parse_wall("assets,nope") == ["assets", *displays.DEFAULT_SCREENS[1:]]
    assert displays.parse_wall(None) == list(displays.DEFAULT_SCREENS)
    assert displays.parse_refresh("60") == 60 and displays.parse_refresh("7") == 0 and displays.parse_refresh("x") == 0


def test_every_variant_draws_with_a_source_label_and_no_controls() -> None:
    for key in displays.VARIANTS:
        page = displays.document([key], ctx())
        assert 'class="wall one"' in page and displays.VARIANTS[key] in page
        assert "gbb-demo" in page or "gbb-source" in page  # every panel says where its numbers come from
        assert "<button" not in page and "<select" not in page and "<input" not in page
        assert "dp-empty\">This panel could not be drawn" not in page
    wall = displays.document(["overview", "assets", "permits", "event-power"], ctx(), refresh=60)
    assert 'class="wall four"' in wall and wall.count('<section class="dp"') == 4 and "refreshes every 60 s" in wall


def test_permit_panel_uses_imported_records_when_given_and_says_counts_are_not_risk() -> None:
    real = {"points": [{"lat": 1.2839, "lon": 103.8658, "names": ["Cloud Forest"], "count": 2, "permits": []}],
            "counts": {"active": 2, "later": 1, "unplaced": 0}}
    page = displays.document(["permits"], ctx(real_permits=real))
    assert "Imported permit records · not live" in page and "not risk" in page and 'class="dp-map"' in page
    assert "Site operations data" in displays.document(["permits"], ctx())  # without real files: the labelled demo data


def test_presentation_mode_has_no_navigation_or_controls(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "demo.site_db", FAKE_DB)
    at = AppTest.from_file(str(APP), default_timeout=90)
    at.query_params["display"] = "assets"
    at.run()
    assert not at.exception
    assert not at.button and not at.selectbox and not at.text_input
    assert any("Display management" in item.value for item in at.markdown)  # the hover-only way back
    wall = AppTest.from_file(str(APP), default_timeout=90)
    wall.query_params["wall"] = "overview,assets,permits,diagnostics"
    wall.run()
    assert not wall.exception and not wall.button


def test_management_page_writes_the_preset_into_its_own_address(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "demo.site_db", FAKE_DB)
    at = AppTest.from_file(str(APP), default_timeout=90)
    at.query_params["view"] = "displays"
    at.query_params["s2"] = "coming-up"
    at.run()
    assert not at.exception
    assert at.selectbox(key="ds_s2").value == "coming-up"
    at.selectbox(key="ds_s4").set_value("diagnostics").run()
    assert at.query_params["s4"] == ["diagnostics"] and at.query_params["refresh"] == ["60"]
    codes = [block.value for block in at.code]
    assert any("display=diagnostics&screen=4&refresh=60" in code for code in codes)
    assert any("wall=overview%2Ccoming-up%2Cpermits%2Cdiagnostics" in code for code in codes)
