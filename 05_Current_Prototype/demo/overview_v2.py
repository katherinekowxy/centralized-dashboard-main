"""Site overview in the clean style: six figures, then a few short lists. Real files first, demo data only where no
real source exists, and every figure says which it is in one short caption or a "Demo" tag.

Real sources (when GBB_DATA_DIR is set): iSMM contractor-work schedules, permit-to-work forms, the event workbook and
the iSMM fault log (open at the end of its export). Demo sources: asset operational state and event power.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from demo import brand, ui
from demo.asset_state import SGT, ts

DEMO = brand.demo_badge("Demo")
AHEAD = 30  # days shown under "Coming up"


def _clock(value: Any) -> str:
    return ts(value).astimezone(SGT).strftime("%H:%M")


def _hours(text: str) -> str:
    """'10:00 AM - 5:30pm' as '10:00–17:30'; the written text when it cannot be read."""
    from demo.sources.registers import parse_times

    times = parse_times(text) if text else None
    return f"{times[0]:%H:%M}–{times[1]:%H:%M}" if times else (text or "All day")


def _short_day(day: date, today: date) -> str:
    return "Today" if day == today else "Tomorrow" if day == today + timedelta(days=1) else day.strftime("%a %d %b")


def page_html(ctx: dict) -> str:
    s, today, now = ctx["summary"], ctx["today"], ctx["now"]
    states = s["states"]
    attention = states["down"] + states["warning"] + states["offline"]
    no_power = s["sockets"].get("down", 0) + s["sockets"].get("nosupply", 0)
    real = ctx.get("real")

    cards = []
    if real:
        on_site = real["on_site"]
        cards += [
            {"label": "Works on site today", "value": len(on_site), "caption": "iSMM schedules", "href": "?view=calendar"},
            {"label": "Permits active now", "value": real["permits_active"], "caption": "Permit-to-work forms", "href": "?view=ptw-map"},
            {"label": "Events today", "value": len(real["events_today"]), "caption": "Event orders", "href": "?view=calendar"},
            {"label": "Open faults", "value": f'{real["open_faults"]:,}', "caption": f'iSMM fault log, as at {real["faults_to"]:%d %b %Y}',
             "href": "?view=fault-log"},
        ]
    else:
        cards += [{"label": "Permits active now", "value": s["permits"]["active"], "caption": "", "tag": DEMO, "href": "?view=ptw-map"},
                  {"label": "Events today", "value": s["events_today"], "caption": "", "tag": DEMO, "href": "?view=event-power"}]
    cards += [
        {"label": "Assets needing attention", "value": attention, "caption": "Down, warning or offline", "tag": DEMO, "href": "?view=asset-status"},
        {"label": "Event sockets without power", "value": no_power, "caption": "Tripped or no supply", "tag": DEMO, "href": "?view=event-power"},
    ]

    if real:
        rows = [{"left": ui.date_cell(_hours(item["time_text"])), "main": item["title"],
                 "sub": " · ".join(part for part in (item["building"], item["trade"]) if part)} for item in real["on_site"][:7]]
        more = len(real["on_site"]) - 7
        today_panel = ui.panel("On site today", ui.rows(rows, "No scheduled works today.")
                               + (f'<div class="u-empty"><a href="?view=calendar" target="_self">+{more} more</a></div>' if more > 0 else ""),
                               link=("Calendar", "?view=calendar"))
        coming = sorted([(e["first_day"], e["title"], e["location"], "Event") for e in real["events_next"]]
                        + [(w["start"], w["title"], w["building"], "Works") for w in real["works_next"]])[:7]
        coming_panel = ui.panel("Coming up", ui.rows(
            [{"left": ui.date_cell(_short_day(day, today)), "main": title, "sub": f"{kind} · {place}" if place else kind,
              "right": ""} for day, title, place, kind in coming], "The latest schedule and event exports list nothing after today."), note=f"Next {AHEAD} days")
    else:
        rows = [{"left": ui.date_cell(_clock(item["start"])), "main": item.get("title") or item["label"],
                 "sub": {"ptw": "Permit", "event": "Event", "maint": "Maintenance"}[item["kind"]]} for item in s["upcoming"][:7]]
        today_panel = ui.panel("Coming up", ui.rows(rows, "Nothing planned."), note="Demo")
        coming_panel = ""

    order = ("down", "warning", "offline", "idle", "operational")
    legend = "".join(f'<span>{brand.status_mark(brand.ASSET_STATE[k][0], brand.ASSET_STATE[k][2])}{brand.ASSET_STATE[k][1]}</span><b>{states[k]}</b>'
                     for k in order)
    health = ui.panel("Asset health", ui.bar([(states[k], brand.ASSET_STATE[k][0], brand.ASSET_STATE[k][1]) for k in order])
                      + f'<div class="u-legend">{legend}</div>', link=("Fleet status", "?view=asset-status"))
    health = health.replace('<div class="u-panel-h"><span>Asset health</span>', f'<div class="u-panel-h"><span>Asset health {DEMO}</span>', 1)

    attention_rows = [{"left": ui.pill({"down": "fault", "warning": "warn", "offline": "off"}.get(r["state"], "neutral") if r["state"] else "neutral", r["word"]),
                       "main": r["what"], "sub": f'{r["where"]} · {r["why"]}' if r["why"] else r["where"], "href": r["href"]}
                      for r in s["attention"][:6]]
    attention_panel = ui.panel("Needs attention", ui.rows(attention_rows, "Nothing needs attention."), link=("Assets", "?view=assets"))
    attention_panel = attention_panel.replace('<span>Needs attention</span>', f'<span>Needs attention {DEMO}</span>', 1)

    panels = [today_panel, health, coming_panel] if coming_panel else [today_panel, health]
    second = [attention_panel]
    if real and real["faults_by_building"]:
        top = real["faults_by_building"][:6]
        peak = max(n for _, n in top)
        fault_rows = "".join(f'<li><span class="u-main"><b>{ui.esc(name)}</b></span><span style="flex:0 0 45%;display:flex;align-items:center;gap:8px">'
                             f'<i style="display:block;height:8px;border-radius:99px;background:{brand.SERIES[1]};width:{n / peak * 100:.0f}%"></i>'
                             f'<span style="font-size:12px;font-weight:700">{n}</span></span></li>' for name, n in top)
        second.append(ui.panel("Open faults by building", f'<ul class="u-rows">{fault_rows}</ul>', link=("Fault log", "?view=fault-log")))
    return (ui.kpis(cards) + ui.grid(panels, "1.25fr 1fr 1.25fr" if len(panels) == 3 else "1.4fr 1fr")
            + ui.grid(second, "1.4fr 1fr" if len(second) == 2 else "1fr"))


def real_context(folder: str, registers_data: dict, permits_data: tuple | None, now: datetime) -> dict:
    """Figures from the real files for the overview. ``registers_data`` comes from app.real_registers."""
    from demo.sources import registers
    from demo.sources.ptw_forms import timing, unique

    today = now.date()
    schedules = registers_data["schedules"]["schedules"]
    events = registers_data["events"]["events"]
    faults = registers_data["faults"]
    on_site = sorted(registers.schedules_on(schedules, today, today), key=lambda w: (w["time_text"] == "", w["time_text"], w["title"]))
    week = today + timedelta(days=AHEAD)
    works_next = [w for w in registers.schedules_on(schedules, today + timedelta(days=1), week) if w["start"] > today]
    events_next = []
    for event in registers.events_on(events, today + timedelta(days=1), week):
        if event["days"] is None and (event["last_day"] - event["first_day"]).days > 13:
            continue  # long written ranges (a season of bookings) are not "coming up"
        future = [d for d in (event["days"] or [event["first_day"]]) if d > today]
        events_next.append({**event, "first_day": future[0] if future else event["first_day"]})
    open_faults = [f for f in faults["faults"] if f["state"] in ("open", "in_progress")]
    by_building: dict[str, int] = {}
    for fault in open_faults:
        by_building[fault["building"]] = by_building.get(fault["building"], 0) + 1
    permits_active = 0
    if permits_data is not None:
        permits_active = sum(timing(record, now) == "active" for record in unique(permits_data[0]["records"]))
    return {"on_site": on_site, "works_next": works_next, "events_today": registers.events_on(events, today, today),
            "events_next": events_next, "open_faults": len(open_faults), "faults_to": faults["exported_to"] or now,
            "faults_by_building": sorted(by_building.items(), key=lambda item: -item[1]), "permits_active": permits_active}
