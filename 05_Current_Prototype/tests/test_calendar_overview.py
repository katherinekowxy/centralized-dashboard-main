"""Calendar overview: SGT week boundaries, clash detection, lanes that never overlap, and the pages bars open."""

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from streamlit.testing.v1 import AppTest

from demo import calendar_overview, site_seed
from demo.asset_state import COLOUR
from site_fixture import seeded_db

AS_OF = datetime(2026, 10, 14, 6, 0, tzinfo=timezone.utc)  # Wednesday 14:00 SGT


@pytest.fixture()
def db():
    path = Path(__file__).resolve().parents[1] / "data" / f"test-calendar-{uuid4().hex}.sqlite3"
    site_seed.build(path, AS_OF)
    yield seeded_db(path)
    path.unlink(missing_ok=True)


def test_week_runs_monday_to_monday_in_sgt() -> None:
    start, end = calendar_overview.week_bounds(AS_OF)
    assert start.isoformat() == "2026-10-11T16:00:00+00:00"  # Mon 12 Oct 00:00 SGT
    assert end.isoformat() == "2026-10-18T16:00:00+00:00"
    assert calendar_overview.week_bounds("2026-10-18T15:59:00+00:00")[0] == start  # Sun 23:59 SGT is still this week
    assert calendar_overview.week_bounds("2026-10-18T16:00:00+00:00")[0] == end    # Mon 00:00 SGT starts the next


def test_clash_needs_the_same_zone_and_overlapping_times() -> None:
    ptw = {"ptw_id": "P", "zone_code": "SGV", "start_at": "2026-10-14T01:00:00+00:00", "end_at": "2026-10-14T10:00:00+00:00"}
    event = {"eo_id": "E", "zone_code": "SGV", "start_at": "2026-10-14T09:00:00+00:00", "end_at": "2026-10-14T12:00:00+00:00"}
    assert calendar_overview.clashes([ptw], [event]) == {"P", "E"}
    assert not calendar_overview.clashes([ptw], [{**event, "zone_code": "FDM"}])
    assert not calendar_overview.clashes([ptw], [{**event, "start_at": "2026-10-14T10:00:00+00:00"}])  # back to back


def test_this_week_has_every_kind_and_the_grove_clash(db) -> None:
    start, end = calendar_overview.week_bounds(db.as_of())
    items = calendar_overview.items(db, start, end)
    kinds = {item["kind"] for item in items}
    assert kinds == {"ptw", "event", "maint"}
    clashing = {item["id"] for item in items if item["clash"]}
    assert any(item["zone"] == "SGV" and item["kind"] == "ptw" and item["id"] in clashing for item in items)
    assert any(item["zone"] == "SGV" and item["kind"] == "event" and item["id"] in clashing for item in items)
    assert {item["kind"] for item in calendar_overview.items(db, start, end, ("Events",))} == {"event"}


def test_items_sit_in_the_sgt_days_they_touch() -> None:
    start, _ = calendar_overview.week_bounds(AS_OF)  # Mon 12 Oct SGT
    span = lambda a, b: calendar_overview.day_span({"start": a, "end": b}, start)  # noqa: E731
    assert span("2026-10-13T14:00:00+00:00", "2026-10-16T10:00:00+00:00") == (2, 6)   # Tue 22:00 to Fri 18:00 SGT
    assert span("2026-10-14T01:00:00+00:00", "2026-10-14T16:00:00+00:00") == (3, 4)   # ends at Thu 00:00 SGT: Wednesday only
    assert span("2026-10-09T01:00:00+00:00", "2026-10-12T04:00:00+00:00") == (1, 2)   # started last week: clipped to Monday
    assert span("2026-10-18T10:00:00+00:00", "2026-10-21T10:00:00+00:00") == (7, 8)   # runs into next week: clipped to Sunday


def test_grid_uses_contractor_colours_never_state_colours(db) -> None:
    start, end = calendar_overview.week_bounds(db.as_of())
    zones = {zone["zone_code"]: zone for zone in db.zones()}
    markup = calendar_overview.grid_html(calendar_overview.items(db, start, end), zones, start, end, db.as_of())
    assert "--c:#8B5CF6" in markup and 'href="?ptw=' in markup and 'href="?eo=' in markup and 'href="?wo=' in markup
    assert 'target="_blank"' in markup and "Clash" in markup and "grid-column:" in markup
    assert not any(colour in markup for colour in COLOUR.values())


def test_dashboard_and_record_pages_render(db) -> None:
    import site_fixture

    site_fixture.CALENDAR_DB = db
    run = lambda body: AppTest.from_string("import site_fixture\nfrom demo import calendar_overview\n" + body,  # noqa: E731
                                           default_timeout=30).run()
    at = run("calendar_overview.render(site_fixture.CALENDAR_DB)\n")
    assert not at.exception
    assert "permits" in "\n".join(item.value for item in at.markdown)
    at.button_group[0].set_value("Next week").run()
    assert not at.exception
    event_id = next(item["id"] for item in calendar_overview.items(db, *calendar_overview.week_bounds(db.as_of()))
                    if item["kind"] == "event" and item["clash"])
    page = run(f"calendar_overview.render_event_page({event_id!r}, site_fixture.CALENDAR_DB)\n")
    assert not page.exception and "Works in this zone during the event" in "\n".join(item.value for item in page.markdown)
    order = run("calendar_overview.render_work_order_page('WO-2026-0457', site_fixture.CALENDAR_DB)\n")
    assert not order.exception and "Under permit" in "\n".join(item.value for item in order.markdown)
    assert run("calendar_overview.render_event_page('EO-0000', site_fixture.CALENDAR_DB)\n").error
