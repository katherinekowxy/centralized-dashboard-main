"""Site overview: the client's first screen. Six figures and a few short lists from the iSMM exports; demo figures
appear only with internal pages switched on, tagged "Demo".

iSMM's fault log also holds service requests and event support jobs. They are counted apart (registers.record_kind),
and every figure here uses the same rule and window as the page it links to, so the numbers tally across pages.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from demo import brand, ui
from demo.asset_state import SGT, ts

DEMO = brand.demo_badge("Demo")
AHEAD = 14  # days of events shown


def _clock(value: Any) -> str:
    return ts(value).astimezone(SGT).strftime("%H:%M")


def _short_day(day: date, today: date) -> str:
    return "Today" if day == today else "Tomorrow" if day == today + timedelta(days=1) else day.strftime("%a %d %b")


def _age(since: datetime, now: datetime) -> str:
    minutes = max(0, (now - since).total_seconds() / 60)
    return f"{minutes:.0f} min" if minutes < 90 else f"{minutes / 60:.0f} h" if minutes < 48 * 60 else f"{minutes / 1440:.0f} d"


def _bars(counts: list[tuple[str, int]], colour: str) -> str:
    if not counts:
        return '<div class="u-empty">None.</div>'
    peak = max(n for _, n in counts)
    return '<ul class="u-rows">' + "".join(
        f'<li><span class="u-main"><b>{ui.esc(name)}</b></span><span style="flex:0 0 45%;display:flex;align-items:center;gap:8px">'
        f'<i style="display:block;height:8px;border-radius:99px;background:{colour};width:{n / peak * 100:.0f}%"></i>'
        f'<span style="font-size:12px;font-weight:700">{n}</span></span></li>' for name, n in counts) + "</ul>"


def demo_panels(summary: dict) -> str:
    states = summary["states"]
    order = ("down", "warning", "offline", "idle", "operational")
    legend = "".join(f'<span>{brand.status_mark(brand.ASSET_STATE[k][0], brand.ASSET_STATE[k][2])}{brand.ASSET_STATE[k][1]}</span><b>{states[k]}</b>'
                     for k in order)
    health = ui.panel("Asset health", ui.bar([(states[k], brand.ASSET_STATE[k][0], brand.ASSET_STATE[k][1]) for k in order])
                      + f'<div class="u-legend">{legend}</div>', link=("Asset status", "?view=asset-status"))
    health = health.replace("<span>Asset health</span>", f"<span>Asset health {DEMO}</span>", 1)
    rows = [{"left": ui.pill({"down": "fault", "warning": "warn", "offline": "off"}.get(r["state"], "neutral") if r["state"] else "neutral", r["word"]),
             "main": r["what"], "sub": f'{r["where"]} · {r["why"]}' if r["why"] else r["where"], "href": r["href"]} for r in summary["attention"][:6]]
    attention = ui.panel("Needs attention", ui.rows(rows, "Nothing needs attention."), link=("Assets", "?view=assets"))
    attention = attention.replace("<span>Needs attention</span>", f"<span>Needs attention {DEMO}</span>", 1)
    return ui.grid([attention, health], "1.4fr 1fr")


def sources_line(real: dict) -> str:
    """One line saying when each export was taken, so nobody reads the page as live."""
    parts = [f"{name} {stamp:%d %b %H:%M}" for name, stamp in real["as_at"] if stamp]
    return "Data as at: " + " · ".join(parts) if parts else ""


def page_html(ctx: dict) -> str:
    real = ctx.get("real")
    if not real:
        return ui.kpis([{"label": "Real data", "value": "Not set", "caption": "Set GBB_DATA_DIR to the export folder"}]) + demo_panels(ctx["summary"])
    f = real["faults"]
    day = f["day"]
    cards = [
        {"label": "Open faults", "value": f["open"] + f["in_progress"], "caption": f"{f['in_progress']} being worked on · {f['over_30']} open over 30 days",
         "href": "?view=fault-log", "dot": "#B42D2D" if f["open"] else None},
        {"label": f"New jobs {day:%d %b}", "value": sum(f["today"].values()),
         "caption": f"{f['today']['fault']} faults · {f['today']['request']} requests · {f['today']['event']} event", "href": "?view=fault-log"},
        {"label": "Median time to site", "value": f["median"], "caption": "Faults, report to on-site, last 30 days", "href": "?view=fault-log"},
        {"label": "Permits active today", "value": len(real["permits_today"]), "caption": f"{len({p['company'] for p in real['permits_today']})} companies on site",
         "href": "?view=ptw-map"},
        {"label": "Tool-box meetings", "value": real["toolbox_week"], "caption": f"Last 7 days · {real['toolbox_today']} today", "href": "?view=permits"},
        {"label": "Spares out of stock", "value": real["stock_out"], "caption": f"{real['stock_low']} more below minimum", "href": "?view=spares",
         "dot": "#B42D2D" if real["stock_out"] else None},
    ]
    open_rows = ui.rows([{"left": ui.pill("fault" if x["state"] == "open" else "warn", "Not started" if x["state"] == "open" else "In progress"),
                          "main": x["what"], "sub": f'{x["building"]} · reported {_age(x["reported"], f["as_at"])} ago'}
                         for x in f["open_list"][:7]], "No open faults.")
    permit_rows = ui.rows([{"left": ui.date_cell(f"{p['start']:%d %b}–{p['end']:%d %b}"), "main": p["company"] or "Company not recorded",
                            "sub": " · ".join(x for x in (p["trades"], site_short(p["site"])) if x),
                            "right": ui.pill("warn" if p["special"] else "neutral", p["type"])}
                           for p in real["permits_today"][:7]], "No permits active today.")
    stock_rows = ui.rows([{"main": i["item"], "sub": i["store"], "right": ui.pill("fault", "Out of stock")} for i in real["stock_list"][:7]],
                         "Nothing out of stock.")
    power_rows = ui.rows([{"left": ui.date_cell(x["reported"].strftime("%a %d %b")), "main": x["what"],
                           "sub": " · ".join(v for v in (x["building"], x["room"]) if v)} for x in real["power_jobs"][:6]],
                         "No event power handovers in the last 7 days.")
    split = f["week_split"]
    html = ui.kpis(cards)
    html += ui.grid([ui.panel("Open faults", open_rows, link=("Faults", "?view=fault-log")),
                     ui.panel("Permits on site today", permit_rows, link=("PTW map", "?view=ptw-map")),
                     ui.panel("Out of stock", stock_rows, link=("Inventories", "?view=spares"))], "1.2fr 1.2fr 1fr")
    html += ui.grid([ui.panel("Event power handovers, last 7 days", power_rows, link=("Event power", "?view=event-power")),
                     ui.panel("Faults by trade, last 7 days", _bars(f["by_trade"], brand.SERIES[0])
                              + f'<div class="u-empty">Also in the last 7 days: {split["request"]} service requests and {split["event"]} event support jobs.</div>',
                              link=("Faults", "?view=fault-log"))], "1.2fr 1fr")
    if ctx.get("show_demo"):
        html += demo_panels(ctx["summary"])
    return html


def events_needing_power(events: list[dict], today: date, ahead: int = AHEAD) -> list[dict]:
    """Event orders over the next ``ahead`` days whose sheet asks for power, soonest first; long ranges say Running."""
    from demo.sources import registers

    out = []
    for event in registers.events_on(events, today, today + timedelta(days=ahead)):
        if not (event["power"] or event["power_on"]):
            continue
        days = [d for d in (event["days"] or []) if d >= today]
        running = event["days"] is None and event["first_day"] <= today
        first = days[0] if days else max(event["first_day"], today)
        out.append({**event, "when": "Running" if running else _short_day(first, today), "sort": (0 if running else 1, first)})
    return sorted(out, key=lambda e: e["sort"])


def real_context(data: dict, now: datetime) -> dict:
    """Overview figures from app.real_registers(). Every figure uses the same rules as the page it links to."""
    from demo.sources import ismm

    today = now.date()
    records = data["faults"]["faults"]
    faults = [x for x in records if x.get("kind", "fault") == "fault"]
    as_at = data["faults"]["exported_to"] or now
    recent = [x for x in faults if x["reported"] and x["reported"] > as_at - timedelta(days=30)]
    median = median_minutes(recent)
    week = [x for x in records if x["reported"] and x["reported"] > as_at - timedelta(days=7)]
    by_trade: dict[str, int] = {}
    for x in week:
        if x.get("kind", "fault") == "fault":
            by_trade[x["trade"] or "Not recorded"] = by_trade.get(x["trade"] or "Not recorded", 0) + 1
    open_list = sorted([x for x in faults if x["state"] in ("open", "in_progress")], key=lambda x: x["reported"] or as_at)
    todays = [x for x in records if x["reported"] and x["reported"].date() == as_at.date()]
    from demo.sources.registers import is_power_job

    power_jobs = sorted([x for x in records if is_power_job(x) and x["reported"] and x["reported"] > as_at - timedelta(days=7)],
                        key=lambda x: x["reported"], reverse=True)

    permits = [{**p, "special": any(kind in p["type"] for kind in ismm.SPECIAL_TYPES)}
               for p in ismm.permits_on(data["permits"]["permits"], today, today)]
    permits.sort(key=lambda p: (not p["special"], p["company"]))
    meetings = data["toolbox"]["meetings"]
    items = data["inventory"]["items"]
    count = lambda rows, kind: sum(x.get("kind", "fault") == kind for x in rows)
    return {"faults": {"open": sum(x["state"] == "open" for x in faults), "in_progress": sum(x["state"] == "in_progress" for x in faults),
                       "over_30": sum(1 for x in open_list if x["reported"] and x["reported"] < as_at - timedelta(days=30)),
                       "day": as_at.date(), "today": {k: count(todays, k) for k in ("fault", "request", "event")},
                       "week_split": {k: count(week, k) for k in ("fault", "request", "event")},
                       "reported_30": len(recent), "median": median, "open_list": open_list, "as_at": as_at,
                       "by_trade": sorted(by_trade.items(), key=lambda item: -item[1])[:6]},
            "permits_today": permits,
            "toolbox_today": sum(m["at"].date() == today for m in meetings),
            "toolbox_week": sum(today - timedelta(days=6) <= m["at"].date() <= today for m in meetings),
            "stock_out": sum(i["state"] == "out" for i in items), "stock_low": sum(i["state"] == "low" for i in items),
            "stock_list": sorted([i for i in items if i["state"] == "out"], key=lambda i: (i["store"], i["item"])),
            "power_jobs": power_jobs,
            "events_power": events_needing_power(data["events"]["events"], today),
            "as_at": [("Faults", data["faults"]["exported_to"]), ("Permits", data["permits"].get("exported")),
                      ("Tool-box", data["toolbox"].get("exported")), ("Stock", data["inventory"].get("exported"))]}


def median_minutes(faults: list[dict]) -> str:
    """Median minutes from report to someone on site, for records that recorded an on-site time and were not cancelled."""
    timed = sorted(max(0.0, (x["on_site"] - x["reported"]).total_seconds() / 60) for x in faults if x["on_site"] and not x["cancelled"])
    if not timed:
        return "—"
    mid = len(timed) // 2
    value = timed[mid] if len(timed) % 2 else (timed[mid - 1] + timed[mid]) / 2
    return f"{value:.0f} min"


def site_short(site: str) -> str:
    """'Gardens By The Bay (South)' as 'GBB South'."""
    import re

    match = re.search(r"\(([^()]+)\)", site or "")
    return f"GBB {match.group(1)}" if match else (site or "")
