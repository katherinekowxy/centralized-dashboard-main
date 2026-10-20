"""Calendar overview: this week's permits, event orders and scheduled maintenance, one row per zone (SGT).

Design brief (docs/site-data-contract.md; Dan, 10 October 2026: "listing active ptws, event orders and scheduled
maintenance works. they still tie in with the ptw dashboard"): bars at a glance, minimal words, details on click in a
new tab. Permits wear their contractor's colour and logo; events (star) and maintenance (cone) stay neutral; the five
machine-state colours never appear here. Where a permit and an event overlap in the same zone, both get a Clash chip.
"""

from __future__ import annotations

import html
from datetime import datetime, time, timedelta, timezone
from typing import Any

from demo.asset_state import SGT, ts
from demo.asset_dashboard import CONE
from demo.ptw_dashboard import CSS as PTW_CSS, logo_html, window_text

WEEKS = {"Last week": -1, "This week": 0, "Next week": 1}
TYPES = ("Permits", "Events", "Maintenance")
STAR = ('<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m12 2.5 2.9 6 6.6.9-4.8 4.6 1.2 6.5L12 17.4l-5.9 3.1 1.2-6.5'
        '-4.8-4.6 6.6-.9z" fill="currentColor"/></svg>')

CSS = """
.sc-sum {display:flex;flex-wrap:wrap;gap:.5rem;margin:.1rem 0 .7rem}
.sc-sum span {display:inline-flex;align-items:center;gap:.4rem;background:var(--gbb-surface-2);border:1px solid var(--gbb-line);border-radius:.6rem;
  padding:.5rem .9rem;font-size:1.05rem;color:var(--gbb-ink-2)}
.sc-sum b {font-size:1.45rem;color:var(--gbb-ink)}
.sc-grid {display:block;border:1px solid var(--gbb-line);border-radius:12px;overflow:hidden;background:var(--gbb-surface)}
.sc-days {position:relative;display:grid;grid-template-columns:repeat(7,1fr);border-bottom:1px solid var(--gbb-line)}
.sc-days div {padding:.5rem .6rem;font-size:.95rem;font-weight:700;color:var(--gbb-ink-3);border-left:1px solid var(--gbb-line)}
.sc-days div b {display:block;font-size:1.2rem;color:var(--gbb-ink)}
.sc-days .sc-today {background:var(--gbb-pink-tint)}
.sc-days .sc-today b {color:var(--gbb-pink)}
.sc-corner {border-bottom:1px solid var(--gbb-line)}
.sc-zone {padding:.5rem .9rem;font-size:1.2rem;font-weight:800;color:var(--gbb-ink);background:var(--gbb-surface-2);border-top:2px solid var(--gbb-line-strong)}
.sc-cells {display:grid;grid-template-columns:repeat(7,minmax(0,1fr));grid-auto-flow:row dense;align-content:start;
  padding:4px 0;border-top:1px solid var(--gbb-line);min-height:40px}
.sc-chip {display:flex;align-items:center;gap:.3rem;min-height:34px;margin:6px 6px 3px 4px;padding:.15rem .45rem;border-radius:8px;min-width:0;position:relative;
  overflow:visible;white-space:normal;font-size:.92rem;font-weight:750;line-height:1.12;color:var(--gbb-ink) !important;text-decoration:none !important}
.sc-chip:hover {filter:brightness(1.25)}
.sc-chip .sc-text {display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;min-width:0;
  word-break:normal;overflow-wrap:normal;hyphens:none}
.sc-bang {flex:none;display:grid;place-items:center;width:1.25rem;height:1.25rem;border-radius:50%;
  background:var(--gbb-ink);color:#fff;font-size:.85rem;font-weight:900}
.sc-chip .sc-bang {position:absolute;top:-.5rem;right:-.4rem;box-shadow:0 0 0 2px #fff}  /* on the corner: the words keep their room */
.sc-chip.sc-clashing {outline:2px solid var(--gbb-ink);outline-offset:1px}
.sc-ptw {border:2px solid var(--c);border-left-width:7px;background:color-mix(in srgb, var(--c) 22%, var(--gbb-surface))}
.sc-ptw .sp-logo {font-size:.8rem}
.sc-event {border:1.5px solid var(--gbb-ink);background:var(--gbb-surface-2)}
.sc-maint {border:1.5px dashed var(--gbb-ink-3);background:var(--gbb-surface-2)}
.sc-chip svg {flex:none;width:18px;height:18px}
.sc-clash {flex:none;margin-left:auto;padding:0 .3rem;border-radius:4px;background:var(--gbb-ink);color:#fff;font-size:.62rem;
  font-weight:800;letter-spacing:.04em;text-transform:uppercase}
.sc-legend {display:flex;flex-wrap:wrap;gap:.3rem 1rem;margin:.8rem 0 .2rem;font-size:.95rem;color:var(--gbb-ink-2)}
.sc-legend span {display:inline-flex;align-items:center;gap:.35rem}
.sc-legend svg {width:14px;height:14px}
.sc-key {display:inline-block;width:22px;height:12px;border-radius:3px}
.sc-list {display:none}
.sc-list h4 {margin:.9rem 0 .35rem;font-size:1.1rem;color:var(--gbb-ink);font-weight:800}
.sc-list a {display:flex;align-items:center;gap:.5rem;padding:.6rem .7rem;margin:0 0 .4rem;border-radius:.6rem;font-size:1.05rem;
  color:var(--gbb-ink) !important;text-decoration:none !important;border:1px solid var(--gbb-line)}
.sc-list a.sc-ptw {border-left:4px solid var(--c)}
.sc-list small {margin-left:auto;color:var(--gbb-ink-3);font-variant-numeric:tabular-nums}
.sc-list svg {width:14px;height:14px;flex:none}
.sc-list .sc-text {overflow:hidden;text-overflow:ellipsis;white-space:nowrap;min-width:0}
.sc-note {font-size:.9rem;color:var(--gbb-ink-3);margin-top:.5rem}
.sc-head {font-size:2.4rem;font-weight:800;margin:.2rem 0 .3rem;display:flex;align-items:center;gap:.6rem;color:var(--gbb-ink)}
.sc-head svg {width:2rem;height:2rem}
.sc-meta {font-size:1.25rem;color:var(--gbb-ink-2);margin:0 0 1rem}
.sc-meta b {color:var(--gbb-ink)}
@media (max-width: 640px) {.sc-grid {display:none} .sc-list {display:block}}
"""


def _db(db: Any) -> Any:
    if db is None:
        from demo import site_db as db
    return db


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def week_bounds(as_of: Any, offset: int = 0) -> tuple[datetime, datetime]:
    """Monday 00:00 to the next Monday 00:00, in SGT, shifted by ``offset`` weeks; returned in UTC."""
    day = ts(as_of).astimezone(SGT).date()
    monday = datetime.combine(day - timedelta(days=day.weekday()) + timedelta(weeks=offset), time.min, SGT)
    return monday.astimezone(timezone.utc), (monday + timedelta(days=7)).astimezone(timezone.utc)


def overlaps(a_start: Any, a_end: Any, b_start: Any, b_end: Any) -> bool:
    return ts(a_start) < ts(b_end) and ts(b_start) < ts(a_end)


def clashes(ptws: list[dict], events: list[dict]) -> set[str]:
    """IDs of permits and events that overlap in time in the same zone."""
    found: set[str] = set()
    for ptw in ptws:
        for event in events:
            if ptw["zone_code"] == event["zone_code"] and overlaps(ptw["start_at"], ptw["end_at"], event["start_at"], event["end_at"]):
                found.update({ptw["ptw_id"], event["eo_id"]})
    return found


def items(db: Any, start: datetime, end: datetime, types: tuple[str, ...] = TYPES) -> list[dict]:
    """Everything on the calendar between start and end, as uniform items: kind, id, zone, start, end, label, link."""
    db = _db(db)
    ptws = db.ptws(start=start.isoformat(), end=end.isoformat())
    events = db.event_orders(start.isoformat(), end.isoformat())
    clash = clashes(ptws, events)
    out = []
    if "Permits" in types:
        out += [{"kind": "ptw", "id": row["ptw_id"], "zone": row["zone_code"], "start": row["start_at"], "end": row["end_at"],
                 "label": row.get("title"), "title": row.get("title"), "contractor": row.get("contractor") or {},
                 "href": f"?ptw={row['ptw_id']}", "clash": row["ptw_id"] in clash} for row in ptws]
    if "Events" in types:
        out += [{"kind": "event", "id": row["eo_id"], "zone": row["zone_code"], "start": row["start_at"], "end": row["end_at"],
                 "label": row.get("title"), "title": row.get("title"), "href": f"?eo={row['eo_id']}", "clash": row["eo_id"] in clash}
                for row in events]
    if "Maintenance" in types:
        out += [{"kind": "maint", "id": row["wo_id"], "zone": row.get("zone_code"), "start": row["scheduled_start"],
                 "end": row["scheduled_end"], "label": row.get("asset_name") or row["asset_id"], "title": row.get("title"), "href": f"?wo={row['wo_id']}",
                 "clash": False, "status": row.get("status")} for row in db.work_orders(start.isoformat(), end.isoformat())]
    return sorted(out, key=lambda item: (item["start"], item["kind"], item["id"]))


def day_span(item: dict, start: datetime) -> tuple[int, int]:
    """Grid columns (1-based, end exclusive) for the SGT days the item touches inside the week."""
    first_day = start.astimezone(SGT).date()
    first = max(0, (ts(item["start"]).astimezone(SGT).date() - first_day).days)
    last = min(6, ((ts(item["end"]) - timedelta(seconds=1)).astimezone(SGT).date() - first_day).days)
    return first + 1, max(first, last) + 2


def _chip(item: dict, start: datetime) -> str:
    begin, stop = day_span(item, start)
    tip = f'{esc(item["id"])} · {esc(item.get("title"))} · {esc(window_text(item["start"], item["end"]))} SGT'
    clash = '<span class="sc-bang" title="Clash: permit and event at the same time">!</span>' if item["clash"] else ""
    if item["kind"] == "ptw":
        colour = item["contractor"].get("colour") or "#94a3b8"
        icon, cls, style = "", "sc-ptw", f"--c:{esc(colour)};"  # the thick colour edge says who; the words say what
    elif item["kind"] == "event":
        icon, cls, style = STAR, "sc-event", ""
    else:
        icon, cls, style = CONE, "sc-maint", ""
    cls += " sc-clashing" if item["clash"] else ""
    return (f'<a class="sc-chip {cls}" href="{esc(item["href"])}" target="_blank" title="{tip}" '
            f'style="{style}grid-column:{begin} / {stop}">{icon}<span class="sc-text">{esc(item["label"])}</span>{clash}</a>')


def grid_html(all_items: list[dict], zones: dict[str, dict], start: datetime, end: datetime, as_of: Any) -> str:
    """One row per zone, seven day columns; each item is a chip in its day, multi-day items span their days."""
    days = [start + timedelta(days=n) for n in range(7)]
    today = ts(as_of).astimezone(SGT).date()
    today_col = next((n for n, day in enumerate(days) if day.astimezone(SGT).date() == today), None)
    header = "".join(f'<div class="{"sc-today" if n == today_col else ""}">{day.astimezone(SGT):%a}<b>{day.astimezone(SGT):%d %b}</b></div>'
                     for n, day in enumerate(days))
    lines = ",".join(f"transparent calc({n}00%/7 - 1px),#DCDEE0 calc({n}00%/7 - 1px),#DCDEE0 calc({n}00%/7),transparent calc({n}00%/7)"
                     for n in range(1, 7))
    shade = (f"linear-gradient(90deg,transparent calc({today_col}00%/7),rgba(131,174,243,.08) calc({today_col}00%/7),"
             f"rgba(131,174,243,.08) calc({today_col + 1}00%/7),transparent calc({today_col + 1}00%/7)),") if today_col is not None else ""
    background = f"background:{shade}linear-gradient(90deg,{lines})"
    order = sorted({item["zone"] for item in all_items},
                   key=lambda code: ((zones.get(code) or {}).get("map_no") or 99, (zones.get(code) or {}).get("name") or code))
    rows = "".join(f'<div class="sc-zone">{esc((zones.get(code) or {}).get("name") or code)}</div>'
                   f'<div class="sc-cells" style="{background}">'
                   + "".join(_chip(item, start) for item in all_items if item["zone"] == code) + "</div>" for code in order)
    return f'<div class="sc-grid"><div class="sc-days">{header}</div>{rows}</div>'


def list_html(all_items: list[dict], zones: dict[str, dict]) -> str:
    """Phones: the same items by day, in time order."""
    by_day: dict[str, list[dict]] = {}
    for item in all_items:
        by_day.setdefault(ts(item["start"]).astimezone(SGT).strftime("%a %d %b"), []).append(item)
    parts = []
    for day, day_items in by_day.items():
        parts.append(f"<h4>{esc(day)}</h4>")
        for item in day_items:
            icon = (logo_html(item["contractor"]) if item["kind"] == "ptw" else STAR if item["kind"] == "event" else CONE)
            colour = (item.get("contractor") or {}).get("colour") or "#94a3b8"
            clash = ' <span class="sc-clash">Clash</span>' if item["clash"] else ""
            parts.append(f'<a class="{"sc-ptw" if item["kind"] == "ptw" else ""}" style="--c:{esc(colour)}" href="{esc(item["href"])}" '
                         f'target="_blank">{icon}<span class="sc-text">{esc((zones.get(item["zone"]) or {}).get("name") or item["zone"])}'
                         f'<span style="color:var(--gbb-ink-3)"> · {esc(item["label"])}</span></span>{clash}'
                         f'<small>{ts(item["start"]).astimezone(SGT):%H:%M}</small></a>')
    return f'<div class="sc-list">{"".join(parts)}</div>'


def summary_html(all_items: list[dict]) -> str:
    count = lambda kind: sum(item["kind"] == kind for item in all_items)  # noqa: E731
    clash = sum(item["clash"] for item in all_items if item["kind"] == "ptw")
    chips = [(count("ptw"), "permits"), (count("event"), "events"), (count("maint"), "maintenance")]
    html_ = "".join(f"<span><b>{n}</b>{label}</span>" for n, label in chips)
    if clash:
        html_ += f'<span><span class="sc-clash">Clash</span><b>{clash}</b>permit{"s" if clash != 1 else ""} during an event</span>'
    return f'<div class="sc-sum">{html_}</div>'


def legend_html() -> str:
    return ('<div class="sc-legend"><span><i class="sc-key" style="border:2px solid #94a3b8;border-left-width:7px"></i>Permit: the edge is the contractor\'s colour</span>'
            f'<span>{STAR}Event</span><span>{CONE}Maintenance</span><span><span class="sc-bang">!</span><span class="sc-clash">Clash</span>'
            'Permit and event in the same zone at the same time</span></div>')


def render(db: Any = None) -> None:
    import streamlit as st

    db = _db(db)
    as_of = db.as_of()
    st.markdown(f"<style>{PTW_CSS}{CSS}</style>", unsafe_allow_html=True)
    left, right = st.columns([1, 2])
    with left:
        week = st.segmented_control("Week", list(WEEKS), default="This week", key="calendar_week", label_visibility="collapsed") or "This week"
    with right:
        types = tuple(st.pills("Show", TYPES, default=list(TYPES), selection_mode="multi", key="calendar_types",
                               label_visibility="collapsed") or ())
    start, end = week_bounds(as_of, WEEKS[week])
    zones = {zone["zone_code"]: zone for zone in db.zones()}
    all_items = items(db, start, end, types)
    st.markdown(summary_html(all_items), unsafe_allow_html=True)
    if not all_items:
        st.info("Nothing scheduled in this week.")
        return
    st.markdown(grid_html(all_items, zones, start, end, as_of) + list_html(all_items, zones) + legend_html()
                + f'<div class="sc-note">Synthetic schedule · week of {start.astimezone(SGT):%d %b} · times in SGT · '
                  'open a bar for details</div>', unsafe_allow_html=True)


def render_event_page(eo_id: str, db: Any = None) -> None:
    import streamlit as st

    db = _db(db)
    st.markdown(f"<style>{PTW_CSS}{CSS}</style>", unsafe_allow_html=True)
    event = db.event_order(eo_id)
    if event is None:
        st.error(f"No event order {eo_id} in the site database.")
        return
    zones = {zone["zone_code"]: zone for zone in db.zones()}
    during = [row for row in db.ptws(start=event["start_at"], end=event["end_at"]) if row["zone_code"] == event["zone_code"]]
    guests = f' · {event["expected_guests"]:,} guests' if event.get("expected_guests") else ""
    st.markdown(f'<div class="sc-head">{STAR}{esc(event["title"])}</div>'
                f'<div class="sc-meta"><b>{esc(window_text(event["start_at"], event["end_at"]))} SGT</b> · '
                f'{esc((zones.get(event["zone_code"]) or {}).get("name"))}{esc(guests)} · {esc(event.get("organiser"))} · {esc(eo_id)}</div>',
                unsafe_allow_html=True)
    if during:
        links = "".join(f'<a class="sc-ptw" style="--c:{esc((row.get("contractor") or {}).get("colour") or "#94a3b8")}" '
                        f'href="?ptw={esc(row["ptw_id"])}" target="_blank">{logo_html(row.get("contractor") or {})}{esc(row["title"])}'
                        f' <span class="sc-clash">Clash</span><small>{esc(window_text(row["start_at"], row["end_at"]))}</small></a>'
                        for row in during)
        st.markdown(f'<div class="sc-head" style="font-size:1rem">Works in this zone during the event</div>'
                    f'<div class="sc-list" style="display:block">{links}</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="sc-meta">No permits in this zone during the event.</div>', unsafe_allow_html=True)
    st.markdown('<div class="sc-note">Synthetic event order</div>', unsafe_allow_html=True)


def render_work_order_page(wo_id: str, db: Any = None) -> None:
    import streamlit as st

    db = _db(db)
    st.markdown(f"<style>{PTW_CSS}{CSS}</style>", unsafe_allow_html=True)
    order = db.work_order(wo_id)
    if order is None:
        st.error(f"No work order {wo_id} in the site database.")
        return
    status = str(order.get("status") or "").replace("_", " ").capitalize()
    st.markdown(f'<div class="sc-head">{CONE}{esc(order["title"])}</div>'
                f'<div class="sc-meta"><b>{esc(status)}</b> · {esc(window_text(order["scheduled_start"], order["scheduled_end"]))} SGT · '
                f'<a href="?asset={esc(order["asset_id"])}" target="_blank">{esc(order.get("asset_name"))} ({esc(order["asset_id"])})</a> · '
                f'{esc(wo_id)}</div>', unsafe_allow_html=True)
    if order.get("ptw_id"):
        st.markdown(f'<div class="sc-meta">Under permit <a href="?ptw={esc(order["ptw_id"])}" target="_blank">{esc(order["ptw_id"])}</a></div>',
                    unsafe_allow_html=True)
    st.markdown('<div class="sc-note">Synthetic work order</div>', unsafe_allow_html=True)
