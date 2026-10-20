"""Meeting rooms: one calendar per room, side by side, a day at a time; book and cancel from the page (SGT).

Dan, 12 October 2026: "4th tab, booking of meeting rooms, 2 for now. calender view, 2 calender, one on the right and
one on the left." Built for older staff (AGENTS.md §5): big room names, each meeting's name big on its booking, empty
space means free, nothing shown only on hover. Both calendars share the same hours and height, so a time lines up
across them. "Now" is the real clock, not the site data's as_of: a booking is for real time.
"""

from __future__ import annotations

import html
from datetime import date, datetime, time, timedelta, timezone
from typing import Any

from demo.asset_state import SGT, ts

OPEN, CLOSE = time(8), time(19)  # bookable hours, SGT
DAYS = 7                          # today and the next six days
SLOT = timedelta(minutes=30)
LENGTHS = {"30 min": 30, "1 hour": 60, "1½ hours": 90, "2 hours": 120, "3 hours": 180}

CSS = """
.rb-date {font-size:18px;font-weight:800;color:var(--gbb-ink);line-height:1.2;white-space:nowrap}
.rb-head {display:flex;flex-wrap:wrap;align-items:baseline;gap:.1rem .8rem}
.rb-name {font-size:24px;font-weight:800;color:var(--gbb-ink);line-height:1.1}
.rb-seats {font-size:14px;font-weight:650;color:var(--gbb-ink-3)}
.rb-state {display:flex;flex-wrap:wrap;align-items:center;gap:.2rem .6rem;margin-top:.35rem;font-size:14px;font-weight:650;color:var(--gbb-ink-2)}
.rb-pill {padding:.05rem .6rem;border:2px solid var(--gbb-grey);border-radius:.5rem;font-size:16px;font-weight:800;color:var(--gbb-ink)}
.rb-busy .rb-pill {background:var(--gbb-grey);color:#fff}
.rb-cal {display:grid;grid-template-columns:3.6rem minmax(0,1fr);height:calc(100vh - 21rem);min-height:640px;
  border:2px solid var(--gbb-line-strong);border-radius:1rem;background:var(--gbb-surface);overflow:hidden}
.rb-axis {position:relative;background:var(--gbb-surface-2);border-right:1px solid var(--gbb-line)}
.rb-axis span {position:absolute;left:0;right:.45rem;margin-top:.15rem;text-align:right;font-size:13px;font-weight:750;
  color:var(--gbb-ink-2);font-variant-numeric:tabular-nums}
.rb-track {position:relative;background-size:100% calc(100% / var(--hours));
  background-image:linear-gradient(var(--gbb-line) 1px,transparent 1px),linear-gradient(transparent calc(50% - 1px),var(--gbb-surface-2) calc(50% - 1px),var(--gbb-surface-2) 50%,transparent 50%)}
.rb-past {position:absolute;left:0;right:0;top:0;background:rgba(36,39,42,.06)}
.rb-now {position:absolute;left:0;right:0;z-index:3;border-top:3px solid var(--gbb-ink)}
.rb-now span {position:absolute;right:.3rem;top:-.8rem;padding:0 .4rem;border-radius:.3rem;background:var(--gbb-ink);color:#fff;
  font-size:13px;font-weight:900;font-variant-numeric:tabular-nums}
.rb-bk {position:absolute;left:.4rem;right:.4rem;z-index:2;box-sizing:border-box;display:flex;flex-direction:column;overflow:hidden;
  padding:.1rem .6rem;border:2px solid var(--gbb-grey);border-left-width:.5rem;border-radius:.55rem;
  background:color-mix(in srgb, var(--gbb-grey) 20%, var(--gbb-surface))}
.rb-bk b {display:-webkit-box;-webkit-line-clamp:1;-webkit-box-orient:vertical;overflow:hidden;flex:none;font-size:16px;font-weight:800;
  line-height:1.12;color:var(--gbb-ink);word-break:normal;overflow-wrap:normal}
.rb-long b {-webkit-line-clamp:2}
.rb-bk span {overflow:hidden;white-space:nowrap;text-overflow:ellipsis;font-size:14px;font-weight:650;line-height:1.2;color:var(--gbb-ink-2);
  font-variant-numeric:tabular-nums}
.rb-bk.rb-short {flex-direction:row;align-items:center;gap:.6rem;padding:0 .6rem}
.rb-short b {-webkit-line-clamp:1;font-size:14px;line-height:1.05}
.rb-short span {flex:none;font-size:14px;font-weight:800;color:var(--gbb-ink)}
.rb-on {background:color-mix(in srgb, var(--gbb-grey) 40%, var(--gbb-surface))}
.rb-done {opacity:.5}
.rb-new {outline:3px solid var(--gbb-ink);outline-offset:1px}
.st-key-rooms_day button p, .st-key-rooms_cancel button p {font-size:14px;font-weight:750}
[class*="st-key-rooms_book_"] button p {font-size:16px;font-weight:800}
[data-testid="stDialog"] h2 {font-size:18px !important;font-weight:800}
[data-testid="stDialog"] label p {font-size:14px;font-weight:750;color:var(--gbb-ink)}
[data-testid="stDialog"] input, [data-testid="stDialog"] [data-baseweb="select"] div, [data-testid="stDialog"] button p,
[data-testid="stDialog"] [role="radiogroup"] p {font-size:14px}
.st-key-rooms_bk_go button p, .st-key-rooms_cx_go button p {font-size:16px;font-weight:800}
"""


def _db(db: Any) -> Any:
    if db is None:
        from demo import site_db as db
    return db


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def day_choices(now: Any) -> list[date]:
    """Today and the next six days, as SGT dates."""
    today = ts(now).astimezone(SGT).date()
    return [today + timedelta(days=n) for n in range(DAYS)]


def day_label(day: date, today: date) -> str:
    return "Today" if day == today else f"{day:%a} {day.day}"


def long_date(day: date) -> str:
    return f"{day:%A} {day.day} {day:%B}"


def day_window(day: date) -> tuple[datetime, datetime]:
    """The bookable hours of an SGT day, in UTC."""
    return (datetime.combine(day, OPEN, SGT).astimezone(timezone.utc), datetime.combine(day, CLOSE, SGT).astimezone(timezone.utc))


def start_choices() -> list[str]:
    """Half-hour start times from opening to the last half hour before closing."""
    first = datetime.combine(date.min, OPEN)
    return [f"{first + n * SLOT:%H:%M}" for n in range(int((datetime.combine(date.min, CLOSE) - first) / SLOT))]


def default_start(day: date, now: Any) -> int:
    """Index into ``start_choices``: the current half hour today, 09:00 on later days."""
    choices = start_choices()
    if day != ts(now).astimezone(SGT).date():
        return choices.index("09:00")
    current = ts(now).astimezone(SGT)
    label = f"{current.hour:02d}:{30 if current.minute >= 30 else 0:02d}"
    return choices.index(label) if label in choices else (0 if current.time() < OPEN else len(choices) - 1)


def hhmm(value: Any) -> str:
    return f"{ts(value).astimezone(SGT):%H:%M}"


def window(booking: dict) -> str:
    return f"{hhmm(booking['start_at'])}–{hhmm(booking['end_at'])}"


def check_booking(day: date, start: str, minutes: int, title: str, booked_by: str, now: Any) -> tuple[datetime, datetime]:
    """The booking's start and end in UTC, or a ValueError whose message is shown to the person booking."""
    if not str(title or "").strip():
        raise ValueError("Type the meeting name.")
    if not str(booked_by or "").strip():
        raise ValueError("Type your name or team.")
    begin = datetime.combine(day, time.fromisoformat(start), SGT)
    end = begin + timedelta(minutes=minutes)
    if begin.time() < OPEN or end > datetime.combine(day, CLOSE, SGT):
        raise ValueError(f"Rooms can be booked {OPEN:%H:%M} to {CLOSE:%H:%M}. Pick an earlier start or a shorter time.")
    if begin + SLOT <= ts(now):
        raise ValueError("That time has passed. Pick a later start.")
    return begin.astimezone(timezone.utc), end.astimezone(timezone.utc)


def book(db: Any, room: dict, day: date, start: str, minutes: int, title: str, booked_by: str, now: Any) -> tuple[bool, str, dict | None]:
    """Check and save a booking: (saved, message for the person, the booking)."""
    try:
        begin, end = check_booking(day, start, minutes, title, booked_by, now)
        booking = db.book_room(room["room_id"], begin.isoformat(), end.isoformat(), title.strip(), booked_by.strip())
    except ValueError as exc:
        taken = getattr(exc, "booking", None)  # site_db.BookingClash
        if taken is not None:
            return False, f"Already booked {window(taken)}: {taken['title']} ({taken['booked_by']}). Pick another time.", None
        return False, str(exc), None
    return True, f"Booked: {room['name']}, {day:%a} {day.day} {day:%b}, {window(booking)}", booking


def room_status(bookings: list[dict], day: date, now: Any) -> tuple[str, str, bool]:
    """(big word, detail, in use) for a room's header: right now for today, a count for later days."""
    now = ts(now)
    if day != now.astimezone(SGT).date():
        count = len(bookings)
        return ("Free all day", "", False) if not count else (f"{count} booking{'s' if count != 1 else ''}", f"first at {hhmm(bookings[0]['start_at'])}", False)
    ordered = sorted(bookings, key=lambda row: row["start_at"])
    current = next((row for row in ordered if ts(row["start_at"]) <= now < ts(row["end_at"])), None)
    if current is not None:
        until = ts(current["end_at"])
        for row in ordered:  # back-to-back meetings keep the room in use
            if ts(row["start_at"]) <= until < ts(row["end_at"]):
                until = ts(row["end_at"])
        return "In use", f"until {hhmm(until)}", True
    upcoming = next((row for row in ordered if ts(row["start_at"]) > now), None)
    return "Free now", (f"next at {hhmm(upcoming['start_at'])}" if upcoming else "no more bookings today"), False


def room_head_html(room: dict, bookings: list[dict], day: date, now: Any) -> str:
    state, detail, busy = room_status(bookings, day, now)
    seats = f'<span class="rb-seats">{esc(room["seats"])} seats</span>' if room.get("seats") else ""
    return (f'<div class="rb-head"><span class="rb-name">{esc(room["name"])}</span>{seats}</div>'
            f'<div class="rb-state{" rb-busy" if busy else ""}"><span class="rb-pill">{esc(state)}</span>{esc(detail)}</div>')


def _pct(moment: datetime, day: date) -> float:
    begin, end = day_window(day)
    return max(0.0, min(100.0, (moment - begin) / (end - begin) * 100))


def _block(booking: dict, day: date, now: datetime, new_id: str | None) -> str:
    begin, end = ts(booking["start_at"]), ts(booking["end_at"])
    top, bottom = _pct(begin, day), _pct(end, day)
    if bottom <= top:
        return ""
    classes = ["rb-bk"]
    short = end - begin <= SLOT
    classes += ["rb-short"] if short else ["rb-long"] if end - begin >= 3 * SLOT else []
    classes += ["rb-done"] if end <= now else ["rb-on"] if begin <= now else []
    classes += ["rb-new"] if booking["booking_id"] == new_id else []
    title, who = esc(booking["title"]), esc(booking["booked_by"])
    text = (f"<span>{hhmm(begin)}</span><b>{title}</b>" if short
            else f"<b>{title}</b><span>{esc(window(booking))} · {who}</span>")
    return (f'<div class="{" ".join(classes)}" style="top:calc({top:.3f}% + 2px);height:calc({bottom - top:.3f}% - 4px)" '
            f'title="{esc(window(booking))} · {title} · {who}">{text}</div>')


def calendar_html(bookings: list[dict], day: date, now: Any, new_id: str | None = None) -> str:
    """One room's day: an hour scale on the left, bookings placed by time, the past shaded and a Now line today."""
    now = ts(now)
    hours = CLOSE.hour - OPEN.hour
    axis = "".join(f'<span style="top:{n / hours * 100:.3f}%">{OPEN.hour + n:02d}:00</span>' for n in range(hours))
    marks = ""
    if day == now.astimezone(SGT).date():
        here = _pct(now, day)
        marks += f'<div class="rb-past" style="height:{here:.3f}%"></div>'
        if 0 < here < 100:
            marks += f'<div class="rb-now" style="top:{here:.3f}%"><span>Now {hhmm(now)}</span></div>'
    blocks = "".join(_block(row, day, now, new_id) for row in sorted(bookings, key=lambda row: row["start_at"]))
    return f'<div class="rb-cal" style="--hours:{hours}"><div class="rb-axis">{axis}</div><div class="rb-track">{marks}{blocks}</div></div>'


def _open(what: str) -> None:
    """Which dialog is open lives in session state, so it stays open through a full rerun until it is closed."""
    import streamlit as st

    st.session_state["rooms_open"] = what


def _close() -> None:
    import streamlit as st

    st.session_state.pop("rooms_open", None)


def _book_dialog(db: Any, room: dict, days: list[date], labels: list[str], current: str, now: datetime) -> None:
    import streamlit as st

    @st.dialog(f"Book {room['name']}", width="medium", on_dismiss=_close)
    def dialog() -> None:
        label = st.segmented_control("Day", labels, default=current, required=True, key="rooms_bk_day") or current
        day = days[labels.index(label)]
        start = st.selectbox("Start", start_choices(), index=default_start(day, now), key="rooms_bk_start")
        length = st.segmented_control("How long", list(LENGTHS), default="1 hour", required=True, key="rooms_bk_len") or "1 hour"
        title = st.text_input("Meeting", max_chars=60, key="rooms_bk_title", placeholder="e.g. Works meeting")
        who = st.text_input("Booked by", max_chars=40, key="rooms_bk_who", placeholder="Your name or team")
        if st.button("Book", type="primary", width="stretch", key="rooms_bk_go"):
            saved, message, booking = book(db, room, day, start, LENGTHS[length], title, who, datetime.now(timezone.utc))
            if not saved:
                st.error(message)
                return
            st.session_state.update(rooms_flash=message, rooms_new=booking["booking_id"], rooms_goto=label)
            _close()
            st.rerun()

    dialog()


def _cancel_dialog(db: Any, rooms: list[dict], bookings: list[dict], day: date, now: datetime) -> None:
    import streamlit as st

    names = {room["room_id"]: room["name"] for room in rooms}
    choices = {row["booking_id"]: row for row in bookings if ts(row["end_at"]) > now}

    @st.dialog("Cancel a booking", width="medium", on_dismiss=_close)
    def dialog() -> None:
        picked = st.radio(long_date(day), list(choices), index=None, key="rooms_cx_pick",
                          format_func=lambda key: f"{names.get(choices[key]['room_id'], choices[key]['room_id'])} · "
                                                  f"{window(choices[key])} · {choices[key]['title']} ({choices[key]['booked_by']})")
        if st.button("Cancel this booking", type="primary", width="stretch", key="rooms_cx_go"):  # a greyed button is hard to see
            if picked is None:
                st.error("Pick a booking first.")
                return
            row = choices[picked]
            if db.cancel_booking(picked):
                st.session_state["rooms_flash"] = f"Cancelled: {names.get(row['room_id'], row['room_id'])}, {window(row)} {row['title']}"
            _close()
            st.rerun()

    dialog()


def render(db: Any = None, now: Any = None) -> None:
    import streamlit as st

    db = _db(db)
    now = ts(now) if now is not None else datetime.now(timezone.utc)
    days = day_choices(now)
    labels = [day_label(day, days[0]) for day in days]
    goto = st.session_state.pop("rooms_goto", None)
    if goto in labels or st.session_state.get("rooms_day") not in labels:  # after a booking, or a new day since last visit
        st.session_state["rooms_day"] = goto if goto in labels else labels[0]
    st.markdown(f"<style>{CSS}</style>", unsafe_allow_html=True)
    if flash := st.session_state.pop("rooms_flash", None):
        st.toast(flash, icon=":material/check_circle:")

    rooms = db.rooms()
    when, picker, cancel = st.columns([1.5, 4, 1.3], vertical_alignment="center")
    with picker:
        label = st.segmented_control("Day", labels, key="rooms_day", required=True, label_visibility="collapsed") or labels[0]
    day = days[labels.index(label)]
    begin, end = day_window(day)
    bookings = db.room_bookings(begin.isoformat(), end.isoformat())
    with when:
        st.markdown(f'<div class="rb-date">{esc(long_date(day))}</div>', unsafe_allow_html=True)
    with cancel:
        st.button("Cancel a booking", width="stretch", key="rooms_cancel", on_click=_open, args=("cancel",),
                  disabled=not any(ts(row["end_at"]) > now for row in bookings))
    if not rooms:
        st.info("No meeting rooms in the site database yet.")
        return
    new_id = st.session_state.get("rooms_new")
    for column, room in zip(st.columns(len(rooms), gap="large"), rooms):
        mine = [row for row in bookings if row["room_id"] == room["room_id"]]
        with column:
            head, action = st.columns([3, 1], vertical_alignment="center")
            head.markdown(room_head_html(room, mine, day, now), unsafe_allow_html=True)
            action.button("Book", key=f"rooms_book_{room['room_id']}", type="primary", width="stretch", icon=":material/add:",
                          on_click=_open, args=(f"book:{room['room_id']}",))
            st.markdown(calendar_html(mine, day, now, new_id), unsafe_allow_html=True)
    opened = st.session_state.get("rooms_open") or ""
    room = next((room for room in rooms if opened == f"book:{room['room_id']}"), None)
    if room is not None:
        _book_dialog(db, room, days, labels, label, now)
    elif opened == "cancel":
        _cancel_dialog(db, rooms, bookings, day, now)
