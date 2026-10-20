"""Meeting rooms: the seeded rooms and bookings, booking rules, clashes, cancelling, reseeding, and the side-by-side page."""

import sys
from contextlib import closing
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from streamlit.testing.v1 import AppTest

from demo import room_booking, site_db, site_seed
from site_fixture import AS_OF, BOOKINGS, FAKE_DB, ROOMS, seeded_db

APP = Path(__file__).resolve().parents[1] / "app.py"
SATURDAY = AS_OF.astimezone(room_booking.SGT).date()  # the fixture's "now" is Saturday 10 October 2026, 14:00 SGT


@pytest.fixture()
def path():
    path = Path(__file__).resolve().parents[1] / "data" / f"test-rooms-{uuid4().hex}.sqlite3"
    site_seed.build(path, AS_OF)
    yield path
    path.unlink(missing_ok=True)


def sgt(day: date, hhmm: str) -> str:
    return datetime.combine(day, datetime.strptime(hhmm, "%H:%M").time(), room_booking.SGT).isoformat()


def test_seed_has_two_rooms_and_a_week_of_bookings_without_double_booking(path) -> None:
    assert [(room["room_id"], room["name"]) for room in site_db.rooms(path)] == [("MR-01", "Orchid Room"), ("MR-02", "Fern Room")]
    for n in range(7):
        begin, end = room_booking.day_window(SATURDAY + timedelta(days=n))
        rows = site_db.room_bookings(begin, end, path=path)
        assert rows, f"day {n} has no bookings"
        for room in ("MR-01", "MR-02"):
            mine = [row for row in rows if row["room_id"] == room]
            assert all(a["end_at"] <= b["start_at"] for a, b in zip(mine, mine[1:]))
            assert all(begin.isoformat() <= row["start_at"] and row["end_at"] <= end.isoformat() for row in mine)


def test_a_clash_is_refused_and_cancelling_frees_the_slot(path) -> None:
    taken = site_db.room_bookings(*room_booking.day_window(SATURDAY), room_id="MR-01", path=path)[0]
    with pytest.raises(site_db.BookingClash) as clash:
        site_db.book_room("MR-01", taken["start_at"], taken["end_at"], "Overlap", "Dan", path=path)
    assert clash.value.booking["booking_id"] == taken["booking_id"]
    assert site_db.cancel_booking(taken["booking_id"], path=path)
    assert not site_db.cancel_booking(taken["booking_id"], path=path)
    booking = site_db.book_room("MR-01", taken["start_at"], taken["end_at"], "Now free", "Dan", path=path)
    assert booking["source"] == "signaldesk" and booking["booking_id"] > taken["booking_id"]
    back_to_back = site_db.book_room("MR-01", taken["end_at"], site_db.utc(datetime.fromisoformat(taken["end_at"]) + timedelta(minutes=30)),
                                     "Right after", "Dan", path=path)
    assert back_to_back["start_at"] == taken["end_at"]  # touching ends are not a clash
    with pytest.raises(ValueError):
        site_db.book_room("MR-01", taken["end_at"], taken["start_at"], "Backwards", "Dan", path=path)
    with pytest.raises(LookupError):
        site_db.book_room("MR-99", sgt(SATURDAY, "18:00"), sgt(SATURDAY, "18:30"), "Nowhere", "Dan", path=path)


def test_a_signaldesk_booking_survives_a_reseed_and_displaces_a_clashing_seed_booking(path) -> None:
    tomorrow = SATURDAY + timedelta(days=1)
    seeded = site_db.room_bookings(*room_booking.day_window(tomorrow), room_id="MR-02", path=path)[0]
    site_db.cancel_booking(seeded["booking_id"], path=path)
    mine = site_db.book_room("MR-02", seeded["start_at"], seeded["end_at"], "Mine", "Dan", path=path)
    site_seed.build(path, AS_OF + timedelta(hours=7))  # the seed puts its meeting back in the slot, unless it is taken
    rows = site_db.room_bookings(*room_booking.day_window(tomorrow), room_id="MR-02", path=path)
    assert mine["booking_id"] in [row["booking_id"] for row in rows]
    assert seeded["booking_id"] not in [row["booking_id"] for row in rows]
    assert all(a["end_at"] <= b["start_at"] for a, b in zip(rows, rows[1:]))


def test_an_older_seed_file_is_rebuilt_once_to_gain_rooms(path) -> None:
    with closing(site_db.connect(path)) as connection, connection:  # as a file made before rooms existed
        connection.execute("DELETE FROM room_bookings")
        connection.execute("DELETE FROM rooms")
        connection.execute("DELETE FROM site_meta WHERE key = 'seed_version'")
    site_seed.ensure_fresh(path=path, now=AS_OF + timedelta(minutes=30))
    assert len(site_db.rooms(path)) == 2
    assert site_db.meta("seed_version", path) == site_seed.SEED_VERSION


def test_days_labels_and_start_times() -> None:
    days = room_booking.day_choices(AS_OF)
    assert len(days) == 7 and days[0] == SATURDAY
    assert [room_booking.day_label(day, days[0]) for day in days[:3]] == ["Today", "Sun 11", "Mon 12"]
    assert room_booking.long_date(days[2]) == "Monday 12 October"
    choices = room_booking.start_choices()
    assert choices[0] == "08:00" and choices[-1] == "18:30" and len(choices) == 22
    assert choices[room_booking.default_start(SATURDAY, AS_OF)] == "14:00"
    assert choices[room_booking.default_start(days[1], AS_OF)] == "09:00"


def test_booking_rules_give_plain_messages() -> None:
    now = AS_OF
    begin, end = room_booking.check_booking(SATURDAY, "14:00", 60, "Meeting", "Dan", now)  # the current half hour is allowed
    assert (begin.isoformat(), end.isoformat()) == ("2026-10-10T06:00:00+00:00", "2026-10-10T07:00:00+00:00")
    for args, words in [(("13:00", 30, "Meeting", "Dan"), "has passed"), (("18:30", 60, "Meeting", "Dan"), "08:00 to 19:00"),
                        (("15:00", 60, " ", "Dan"), "meeting name"), (("15:00", 60, "Meeting", ""), "your name")]:
        with pytest.raises(ValueError, match=words):
            room_booking.check_booking(SATURDAY, *args, now)


def test_book_saves_or_explains_the_clash(path) -> None:
    db = seeded_db(path)
    room = {"room_id": "MR-02", "name": "Fern Room"}
    taken = site_db.room_bookings(*room_booking.day_window(SATURDAY + timedelta(days=1)), room_id="MR-02", path=path)[0]
    tomorrow = SATURDAY + timedelta(days=1)
    saved, message, _ = room_booking.book(db, room, tomorrow, room_booking.hhmm(taken["start_at"]), 30, "Clash", "Dan", AS_OF)
    assert not saved and message.startswith(f"Already booked {room_booking.window(taken)}: {taken['title']}")
    saved, message, booking = room_booking.book(db, room, tomorrow, "18:30", 30, "  Late call ", "Dan", AS_OF)
    assert saved and booking["title"] == "Late call" and message == "Booked: Fern Room, Sun 11 Oct, 18:30–19:00"


def test_room_status_now_and_on_later_days() -> None:
    orchid = [row for row in BOOKINGS if row["room_id"] == "MR-01"]
    fern = [row for row in BOOKINGS if row["room_id"] == "MR-02"]
    assert room_booking.room_status(orchid, SATURDAY, AS_OF) == ("In use", "until 15:30", True)  # two meetings back to back
    assert room_booking.room_status(fern, SATURDAY, AS_OF) == ("Free now", "next at 16:00", False)
    assert room_booking.room_status(fern, SATURDAY, AS_OF + timedelta(hours=4)) == ("Free now", "no more bookings today", False)
    later = SATURDAY + timedelta(days=1)
    assert room_booking.room_status([], later, AS_OF) == ("Free all day", "", False)
    assert room_booking.room_status(fern, later, AS_OF) == ("1 booking", "first at 16:00", False)


def test_calendar_places_bookings_by_time_and_shades_the_past() -> None:
    hostile = {**BOOKINGS[1], "title": "<script>alert(1)</script>"}
    page = room_booking.calendar_html([BOOKINGS[0], hostile, BOOKINGS[2]], SATURDAY, AS_OF, new_id="RB-0003")
    assert 'style="top:calc(50.000% + 2px);height:calc(13.636% - 4px)"' in page  # 13:30-15:00 within 08:00-19:00
    assert 'class="rb-past" style="height:54.545%"' in page and "Now 14:00" in page
    assert 'class="rb-bk rb-short rb-done"' in page            # the 09:00 huddle is over
    assert 'class="rb-bk rb-long rb-on"' in page               # the meeting in the room now; 90 min, so its name may wrap
    assert 'class="rb-bk rb-short rb-new"' in page             # the booking just made is outlined
    assert "<script>" not in page and "&lt;script&gt;" in page
    assert page.count("<span style=\"top:") == 11               # 08:00 to 18:00 on the scale
    tomorrow = room_booking.calendar_html([], SATURDAY + timedelta(days=1), AS_OF)
    assert "rb-past" not in tomorrow and "rb-now" not in tomorrow


def test_page_shows_both_rooms_side_by_side(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "demo.site_db", FAKE_DB)
    at = AppTest.from_file(str(APP), default_timeout=60).run()
    at.button(key="nav-rooms").click().run()
    assert not at.exception
    text = "\n".join(item.value for item in at.markdown)
    for room in ROOMS:
        assert f'<span class="rb-name">{room["name"]}</span>' in text
    assert [button.label for button in at.button if button.label in {"Book", "Cancel a booking"}] == ["Cancel a booking", "Book", "Book"]
    assert next(group for group in at.button_group if group.key == "rooms_day").value == "Today"


def test_booking_through_the_dialog_lands_on_the_calendar(monkeypatch, path) -> None:
    site_seed.build(path, datetime.now(timezone.utc))  # the page uses the real clock
    monkeypatch.setitem(sys.modules, "demo.site_db", seeded_db(path))
    at = AppTest.from_file(str(APP), default_timeout=60).run()
    at.button(key="nav-rooms").click().run()
    at.button(key="rooms_book_MR-02").click().run()
    assert not at.exception
    day = next(group for group in at.button_group if group.key == "rooms_bk_day")
    tomorrow = day.options[1]
    day.set_value(tomorrow).run()
    at.selectbox(key="rooms_bk_start").set_value("18:00").run()
    next(group for group in at.button_group if group.key == "rooms_bk_len").set_value("30 min").run()
    at.text_input(key="rooms_bk_title").input("Dialog test").run()
    at.text_input(key="rooms_bk_who").input("Dan").run()
    at.button(key="rooms_bk_go").click().run()
    assert not at.exception
    assert [row["title"] for row in site_db.room_bookings("2000-01-01T00:00:00+00:00", "2100-01-01T00:00:00+00:00", path=path)
            if row["source"] == "signaldesk"] == ["Dialog test"]
    assert next(group for group in at.button_group if group.key == "rooms_day").value == tomorrow
    assert "Dialog test" in "\n".join(item.value for item in at.markdown)


def test_cancelling_through_the_dialog_frees_the_room(monkeypatch, path) -> None:
    now = datetime.now(timezone.utc)
    site_seed.build(path, now)
    day = room_booking.day_choices(now)[1]
    target = site_db.room_bookings(*room_booking.day_window(day), room_id="MR-01", path=path)[0]
    monkeypatch.setitem(sys.modules, "demo.site_db", seeded_db(path))
    at = AppTest.from_file(str(APP), default_timeout=60).run()
    at.button(key="nav-rooms").click().run()
    days = next(group for group in at.button_group if group.key == "rooms_day")
    days.set_value(days.options[1]).run()
    at.button(key="rooms_cancel").click().run()
    at.button(key="rooms_cx_go").click().run()
    assert "Pick a booking first." in [item.value for item in at.error]  # nothing picked yet, nothing cancelled
    at.radio(key="rooms_cx_pick").set_value(target["booking_id"]).run()
    at.button(key="rooms_cx_go").click().run()
    assert not at.exception
    assert target["booking_id"] not in [row["booking_id"] for row in site_db.room_bookings(*room_booking.day_window(day), path=path)]
    assert not [button for button in at.button if button.key == "rooms_cx_go"]  # the dialog closed
