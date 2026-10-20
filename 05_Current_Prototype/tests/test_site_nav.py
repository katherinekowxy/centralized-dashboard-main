"""Navigation: six areas, one button per page, bookmarkable ?view= URLs, and detail pages that open on their own."""

import html
import sys
from pathlib import Path

from streamlit.testing.v1 import AppTest

from demo import navigation
from site_fixture import FAKE_DB

APP = Path(__file__).resolve().parents[1] / "app.py"


def test_every_page_belongs_to_one_area_and_says_what_its_status_means() -> None:
    assert navigation.AREAS[0] == "Site Overview" and navigation.DEFAULT == "overview"
    assert len({page.key for page in navigation.PAGES}) == len(navigation.PAGES)
    for page in navigation.PAGES:
        assert page.area in navigation.AREAS and page.status and page.summary
        assert bool(page.module) + bool(page.replay_page) <= 1  # one data source per page, never both
    assert [page.key for page in navigation.PAGES if page.secondary] == ["rooms"]  # booking is a transaction, not a display
    assert navigation.resolve("no-such-page") == "overview" and navigation.resolve(None) == "overview"


def test_app_opens_on_site_overview_with_grouped_navigation() -> None:
    at = AppTest.from_file(str(APP), default_timeout=60).run()
    assert not at.exception
    assert at.query_params["view"] == ["overview"]
    assert at.button(key="nav-overview").proto.type == "primary"  # the current page is marked
    visible_pages = [page for page in navigation.PAGES if page.client]
    for page in visible_pages:
        assert at.button(key=f"nav-{page.key}").label == page.label
    assert "nav-assets" not in {button.key for button in at.button}
    markup = "\n".join(item.value for item in at.markdown)
    for area in {page.area for page in visible_pages}:
        assert html.escape(area) in markup


def test_internal_pages_appear_when_show_all_is_enabled() -> None:
    at = AppTest.from_file(str(APP), default_timeout=60).run()
    at.toggle(key="nav_all").set_value(True).run()
    assert not at.exception
    for page in navigation.PAGES:
        assert at.button(key=f"nav-{page.key}").label == page.label


def test_demo_workspace_route_and_presentation_mode() -> None:
    workspace = AppTest.from_file(str(APP), default_timeout=90)
    workspace.query_params["view"] = "demo-workspace"
    workspace.run()
    assert not workspace.exception
    assert workspace.button(key="nav-demo-workspace").label == "Display wall"
    assert any("Display wall" in item.value for item in workspace.markdown)

    presentation = AppTest.from_file(str(APP), default_timeout=90)
    presentation.query_params["view"] = "demo-workspace"
    presentation.query_params["presentation"] = "1"
    presentation.run()
    assert not presentation.exception
    assert any(button.label == "Exit presentation" for button in presentation.button)
    assert not any(button.key and button.key.startswith("nav-") for button in presentation.button)


def test_embedded_module_route_hides_sidebar_widgets() -> None:
    at = AppTest.from_file(str(APP), default_timeout=60)
    at.query_params["view"] = "overview"
    at.query_params["workspace_embed"] = "1"
    at.run()
    assert not at.exception
    assert not any(button.key and button.key.startswith("nav-") for button in at.button)


def test_app_handles_navigation_module_without_imported_constant(monkeypatch) -> None:
    monkeypatch.delattr(navigation, "IMPORTED")
    at = AppTest.from_file(str(APP), default_timeout=60).run()
    assert not at.exception


def test_a_view_url_opens_that_page_and_buttons_update_the_url(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "demo.site_db", FAKE_DB)
    at = AppTest.from_file(str(APP), default_timeout=60)
    at.query_params["view"] = "asset-status"
    at.run()
    assert not at.exception
    assert "Down</small><b>2</b>" in "\n".join(item.value for item in at.markdown)
    at.button(key="nav-diagnostics").click().run()
    assert not at.exception
    assert at.query_params["view"] == ["diagnostics"] and at.session_state["nav"] == "diagnostics"
    assert "Demo scenario" in "\n".join(item.value for item in at.markdown)


def test_site_dashboard_and_new_tab_detail_read_the_site_database(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "demo.site_db", FAKE_DB)
    at = AppTest.from_file(str(APP), default_timeout=60).run()
    at.toggle(key="nav_all").set_value(True).run()
    at.button(key="nav-asset-status").click().run()
    assert not at.exception
    markup = "\n".join(item.value for item in at.markdown)
    assert "Down</small><b>2</b>" in markup and "Operational asset state" in markup  # the status key, in the tag's tooltip
    detail = AppTest.from_file(str(APP), default_timeout=60)
    detail.query_params["asset"] = "FDM-CHL-01"
    detail.run()
    assert not detail.exception
    assert "Chiller 1" in "\n".join(item.value for item in detail.markdown)
    assert not any(button.key and button.key.startswith("nav-") for button in detail.button)  # a detail tab has no navigation
