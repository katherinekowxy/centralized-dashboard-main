"""PTW dashboard: today's permits on the map in contractor colours, and the PTW page's impacts."""

from streamlit.testing.v1 import AppTest

from demo import ptw_dashboard
from demo.asset_state import COLOUR
from site_fixture import FAKE_DB


def test_todays_permits_become_filled_zones_with_the_details_written_on_them() -> None:
    data = ptw_dashboard.todays_permits(FAKE_DB)
    assert [row["ptw_id"] for row in data["rows"]] == ["PTW-2026-0142", "PTW-2026-0145"]
    features = ptw_dashboard.map_features(data["rows"], data["zones"])
    assert [feature["href"] for feature in features] == ["?ptw=PTW-2026-0142", "?ptw=PTW-2026-0145"]
    grove = features[0]
    assert grove["style"]["fillColor"] == "#8B5CF6" and grove["style"]["fillOpacity"] >= .5  # coloured in
    assert "DB-03 replacement" in grove["label"] and "08:00–17:00" in grove["label"] and ">NM<" in grove["label"]
    assert "10 Oct–12 Oct" in features[1]["label"]  # multi-day duration on the bridge's box
    page = ptw_dashboard.map_page(features)
    assert "leaflet" in page and "tile.openstreetmap.org" in page and "window.open" in page
    hostile = {**data["rows"][0], "title": "</script><script>alert(1)</script>"}
    payload = ptw_dashboard.map_page(ptw_dashboard.map_features([hostile], data["zones"])).split("const D = ")[1].split("if (!window.L)")[0]
    assert "</script>" not in payload  # data can't break out of the script tag
    assert not any(colour in page for colour in COLOUR.values())  # state colours never appear here


def test_later_today_is_dashed_and_says_when_it_starts() -> None:
    data = ptw_dashboard.todays_permits(FAKE_DB)
    later = {**data["rows"][0], "active": False}
    feature = ptw_dashboard.map_features([later], data["zones"])[0]
    assert feature["style"]["dashArray"] and feature["style"]["fillOpacity"] < .2 and "from 08:00" in feature["label"]


def test_zone_bounds_cover_the_outline() -> None:
    geometry = {"type": "MultiPolygon", "coordinates": [[[[103.86, 1.28], [103.87, 1.28], [103.87, 1.29], [103.86, 1.28]]]]}
    (south, west), (north, east) = ptw_dashboard.geo_bounds(geometry, pad=.001)
    assert (round(south, 6), round(west, 6), round(north, 6), round(east, 6)) == (1.279, 103.859, 1.291, 103.871)


def test_monogram_and_readable_text_on_any_brand_colour() -> None:
    assert ptw_dashboard.monogram("Northwind M&E") == "NM" and ptw_dashboard.monogram("Helix") == "HE"
    assert ptw_dashboard.ink_for("#4C1D95") == "#ffffff" and ptw_dashboard.ink_for("#FDE047") == "#0b1524"


def test_dashboard_and_ptw_page_render() -> None:
    at = AppTest.from_string("from demo import ptw_dashboard\nfrom site_fixture import FAKE_DB\nptw_dashboard.render(FAKE_DB)\n",
                             default_timeout=30).run()
    assert not at.exception
    assert "<b>2</b>active now" in "\n".join(item.value for item in at.markdown)
    page = AppTest.from_string("from demo import ptw_dashboard\nfrom site_fixture import FAKE_DB\n"
                               "ptw_dashboard.render_ptw_page('PTW-2026-0142', FAKE_DB)\n", default_timeout=30).run()
    assert not page.exception
    text = "\n".join(item.value for item in page.markdown)
    assert "What is affected" in text and "3 outlets down" in text and "DB-03 isolated" in text
    assert "Grove outlets · Down" in text  # affected assets show their state as a word, not a coloured box
    assert text.count("Grove outlets") == 2  # once as the feed of DB-03, once as its own impact; no repeats
    assert not any(colour in text for colour in COLOUR.values())
    assert not page.expander  # nothing hidden: the details are shown big
    assert "ACTIVE NOW" in text and ">When<" in text and "08:00 – 17:00" in text and ">Where<" in text and ">Who<" in text
    bridge = AppTest.from_string("from demo import ptw_dashboard\nfrom site_fixture import FAKE_DB\n"
                                 "ptw_dashboard.render_ptw_page('PTW-2026-0145', FAKE_DB)\n", default_timeout=30).run()
    assert "Bridge closed" in "\n".join(item.value for item in bridge.markdown)
    missing = AppTest.from_string("from demo import ptw_dashboard\nfrom site_fixture import FAKE_DB\n"
                                  "ptw_dashboard.render_ptw_page('PTW-0000', FAKE_DB)\n", default_timeout=30).run()
    assert missing.error
