"""Asset dashboard: states, dots for healthy assets, banners for problems, the cone, problems first, and the asset page."""

from streamlit.testing.v1 import AppTest

from demo import asset_dashboard
from site_fixture import FAKE_DB


def _rows() -> dict:
    return {row["asset_id"]: row for row in asset_dashboard.board(FAKE_DB)["rows"]}


def test_every_state_from_the_fixture_and_problems_first() -> None:
    rows = _rows()
    assert {asset_id: row["state"] for asset_id, row in rows.items()} == {
        "SGV-DB-03": "down", "SGV-OUT-01": "down", "SGV-LGT-01": "idle",
        "FDM-CHL-01": "operational", "FDM-AHU-02": "warning", "FDM-PMP-01": "offline"}
    order = [row["state"] for row in asset_dashboard.board(FAKE_DB)["rows"]]
    assert order == sorted(order, key=asset_dashboard.SEVERITY.index)


def test_dots_for_healthy_banners_for_problems_and_cone_for_maintenance_today() -> None:
    rows = _rows()
    for asset_id, row in rows.items():
        markup = asset_dashboard.row_html(row)
        healthy = row["state"] in {"operational", "idle"}
        assert ('class="tv-dot"' in markup) is healthy and ("tv-ban" in markup) is not healthy, asset_id
        assert f'href="?asset={asset_id}" target="_blank"' in markup
    assert {asset_id for asset_id, row in rows.items() if row["maintenance"]} == {"SGV-DB-03", "SGV-OUT-01", "FDM-CHL-01"}
    chiller = asset_dashboard.row_html(rows["FDM-CHL-01"])
    assert 'class="tv-cone"' in chiller and 'class="tv-dot"' in chiller  # the cone sits beside the green dot: the dot is the state
    assert "Isolated under permit until 17:00" in asset_dashboard.row_html(rows["SGV-DB-03"])  # says why, not "not running"


def test_zones_with_problems_come_first() -> None:
    markup = asset_dashboard.overview_html(asset_dashboard.board(FAKE_DB))
    assert markup.index("Supertree Grove") < markup.index("Flower Dome")


def test_dashboard_and_asset_page_render() -> None:
    at = AppTest.from_string("from demo import asset_dashboard\nfrom site_fixture import FAKE_DB\nasset_dashboard.render(FAKE_DB)\n",
                             default_timeout=30).run()
    assert not at.exception
    markup = "\n".join(item.value for item in at.markdown)
    assert "Down</small><b>2</b>" in markup and "demo data" in markup
    page = AppTest.from_string("from demo import asset_dashboard\nfrom site_fixture import FAKE_DB\n"
                               "asset_dashboard.render_asset_page('FDM-CHL-01', FAKE_DB)\n", default_timeout=30).run()
    assert not page.exception
    text = "\n".join(item.value for item in page.markdown)
    assert "Chiller 1" in text and "WO-2026-0457" in text and "Operational" in text
    assert len(page.get("plotly_chart")) == 4
    missing = AppTest.from_string("from demo import asset_dashboard\nfrom site_fixture import FAKE_DB\n"
                                  "asset_dashboard.render_asset_page('NOPE', FAKE_DB)\n", default_timeout=30).run()
    assert missing.error
