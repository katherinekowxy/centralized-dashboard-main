"""Site area: the app opens on the six site dashboards, switches to the Diagnostics demo, and opens detail tabs."""

import sys
from pathlib import Path

from streamlit.testing.v1 import AppTest

from site_fixture import FAKE_DB

APP = Path(__file__).resolve().parents[1] / "app.py"


def test_app_opens_on_site_dashboards_and_switches_to_diagnostics() -> None:
    at = AppTest.from_file(str(APP), default_timeout=60).run()
    assert not at.exception
    assert at.button_group[0].value == "Site"
    assert next(radio for radio in at.radio if radio.label == "Dashboard").options == [
        "PTW dashboard", "Asset dashboard", "Asset schematic", "Event power", "Calendar overview", "Meeting rooms"]
    assert not any(radio.label == "View" for radio in at.radio)  # diagnostics pages stay out of the Site area
    at.button_group[0].set_value("Diagnostics demo").run()
    assert not at.exception
    assert next(radio for radio in at.radio if radio.label == "View").value == "Overview"


def test_site_dashboard_and_new_tab_detail_read_the_site_database(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "demo.site_db", FAKE_DB)
    at = AppTest.from_file(str(APP), default_timeout=60).run()
    next(radio for radio in at.radio if radio.label == "Dashboard").set_value("Asset dashboard").run()
    assert not at.exception
    assert "Down</small><b>2</b>" in "\n".join(item.value for item in at.markdown)
    detail = AppTest.from_file(str(APP), default_timeout=60)
    detail.query_params["asset"] = "FDM-CHL-01"
    detail.run()
    assert not detail.exception
    assert "Chiller 1" in "\n".join(item.value for item in detail.markdown)
    assert not detail.radio  # a detail tab shows the record only, without navigation
