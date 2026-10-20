"""Site overview: the landing page. One screen that says what needs attention, using only figures other pages own.

Every figure here is computed by the module that owns it (asset_dashboard, ptw_dashboard, event_power,
calendar_overview, and the diagnostics replay), and each appears once. There is no site-wide health score or
red/amber/green roll-up: an asset being Down, a permit being active, a socket having no supply and a detector finding
are different facts, so they stay in separate panels with their own words.

The diagnostics figures come from the replayed demonstration scenario, whose five assets are not site assets, so they
sit in their own panel and are never added to site counts.
"""

from __future__ import annotations

import html
from datetime import timedelta
from typing import Any

from demo import brand
from demo.asset_state import LABEL, SGT, ts

UPCOMING_HOURS = 48
ATTENTION_SHOWN = 8


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def sgt(value: Any, fmt: str = "%H:%M") -> str:
    return ts(value).astimezone(SGT).strftime(fmt)


def _attention(assets: list[dict], boxes: list[dict], clash_items: list[dict], zones: dict[str, dict]) -> list[dict]:
    """Things a person should look at now, most serious first. Each says what kind of fact it is."""
    from demo.asset_dashboard import reason_for

    rank = {"down": 0, "nosupply": 1, "warning": 2, "offline": 3, "clash": 4}
    out = []
    for row in assets:
        if row["state"] in ("down", "warning", "offline"):
            zone = (zones.get(row.get("zone_code")) or {}).get("name") or row.get("zone_code")
            out.append({"rank": rank[row["state"]], "kind": "Asset state", "state": row["state"], "word": LABEL[row["state"]],
                        "what": row.get("name") or row["asset_id"], "where": zone, "why": reason_for(row),
                        "href": f"?asset={row['asset_id']}"})
    for item in boxes:
        event = item.get("event")
        if item["dead"] and event and (item["live"] or (item["back_at"] is not None and ts(event["start_at"]) < item["back_at"])):
            back = f" until {sgt(item['back_at'])}" if item.get("back_at") else ""
            out.append({"rank": rank["nosupply"], "kind": "Event power", "state": "down", "word": "No supply",
                        "what": f"{event['title']} at {item['box']['name']}", "where": item["zone"],
                        "why": f"Feeding board is down{back}", "href": f"?eo={event['eo_id']}"})
        for socket in item["sockets"]:
            if not item["dead"] and socket["state"] in ("down", "warning"):
                out.append({"rank": rank[socket["state"]], "kind": "Event power", "state": socket["state"],
                            "word": "Tripped" if socket["state"] == "down" else "Warning", "what": socket.get("name") or socket["asset_id"],
                            "where": item["zone"], "why": socket.get("reason") or "", "href": f"?asset={socket['asset_id']}"})
    for item in clash_items:
        zone = (zones.get(item.get("zone")) or {}).get("name") or item.get("zone")
        out.append({"rank": rank["clash"], "kind": "Planning clash", "state": None, "word": "Clash",
                    "what": item.get("label") or item["id"], "where": zone,
                    "why": f"{'Permit' if item['kind'] == 'ptw' else 'Event'} overlaps {'an event' if item['kind'] == 'ptw' else 'a permit'} "
                           f"in the same zone, {sgt(item['start'])}–{sgt(item['end'])}", "href": item["href"]})
    return sorted(out, key=lambda row: (row["rank"], row["kind"], row["what"]))


def summary(db: Any, run: dict | None = None) -> dict[str, Any]:
    """Every figure on the overview, from the modules that own it. ``run`` is the diagnostics replay, if loaded."""
    from demo import asset_dashboard, calendar_overview, event_power, ptw_dashboard

    as_of = db.as_of()
    now = ts(as_of)
    board = asset_dashboard.board(db)
    zones = board["zones"]
    states = {state: sum(row["state"] == state for row in board["rows"]) for state in brand.ASSET_STATE}
    not_monitored = sum(not asset.get("connected", 1) for asset in db.assets())

    permits = ptw_dashboard.todays_permits(db)
    active = [row for row in permits["rows"] if row["active"]]
    later = [row for row in permits["rows"] if not row["active"] and ts(row["start_at"]) > now]
    impacts = db.impacts(active_at=as_of)
    isolations = {"electrical": sum(row.get("kind") == "electrical" for row in impacts),
                  "physical": sum(row.get("kind") == "physical" for row in impacts)}

    power = event_power.board(db)
    sockets: dict[str, int] = {}
    for item in power["boxes"]:
        for row in item["sockets"]:
            key = "nosupply" if item["dead"] else row["state"]
            sockets[key] = sockets.get(key, 0) + 1
    events_today = {item["event"]["eo_id"] for item in power["boxes"] if item.get("event")}

    start = now - timedelta(hours=12)
    window = calendar_overview.items(db, start, now + timedelta(hours=UPCOMING_HOURS))
    upcoming = [item for item in window if ts(item["start"]) >= now][:8]
    clash_items = [item for item in window if item["clash"] and ts(item["end"]) > now]

    attention = _attention(board["rows"], power["boxes"], clash_items, zones)

    diagnostics = None
    if run:
        from demo.history import summarize_history

        cases = run["analysis"].get("cases", [])
        findings = [case for case in cases if case.get("category") in {"condition", "trip"}]
        diagnostics = {"findings": len(findings), "other_cases": len(cases) - len(findings),
                       "quality_issues": len(run["analysis"].get("quality_issues", [])),
                       "open_work_orders": summarize_history(run["history"], run["as_of"])["open_faults"],
                       "scenario": run.get("scenario_id"), "as_of": run["as_of"]}

    latest = max((ts(row["observed_at"]) for points in db.latest_readings().values() for row in points.values()), default=None)
    batches = db.ingest_batches() if hasattr(db, "ingest_batches") else []
    return {"as_of": as_of, "states": states, "monitored": len(board["rows"]), "not_monitored": not_monitored,
            "attention": attention, "permits": {"active": len(active), "later": len(later), "isolations": isolations,
                                                "zones": sorted({(zones.get(row["zone_code"]) or {}).get("name") or row["zone_code"] for row in active})},
            "sockets": sockets, "events_today": len(events_today), "upcoming": upcoming, "diagnostics": diagnostics,
            "latest_reading": latest.isoformat() if latest else None, "batches": batches, "zones": zones}


CSS = """
.block-container {max-width:1760px !important}
.ov {color:var(--gbb-ink)}
.ov-asof {display:flex;flex-wrap:wrap;align-items:center;gap:.4rem 1rem;margin:-.3rem 0 1rem;font-size:.85rem;color:var(--gbb-ink-2)}
.ov-grid {display:grid;grid-template-columns:minmax(0,1.7fr) minmax(0,1fr);gap:1.4rem;margin:0 0 1.4rem}
.ov-row {display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:1.4rem;margin:0 0 1.4rem}
.ov-row2 {display:grid;grid-template-columns:minmax(0,1.7fr) minmax(0,1fr);gap:1.4rem}
.ov-panel .ov-h {display:flex;align-items:baseline;justify-content:space-between;gap:.6rem;font-size:1rem;font-weight:750;
  margin:0 0 .55rem;padding:0 0 .4rem;border-bottom:2px solid var(--gbb-ink);color:var(--gbb-ink)}
.ov-panel .ov-h a {font-size:.8rem;font-weight:650;text-decoration:none;white-space:nowrap}
.ov-panel .ov-h small {font-size:.72rem;font-weight:600;color:var(--gbb-ink-3)}
.ov-list {list-style:none;margin:0;padding:0}
.ov-list li {display:grid;grid-template-columns:7.4rem minmax(0,1fr) auto;align-items:baseline;gap:.2rem .8rem;padding:.5rem 0;
  border-bottom:1px solid var(--gbb-line)}
.ov-word {display:inline-flex;align-items:center;gap:.35rem;font-weight:750;font-size:.86rem}
.ov-what {font-weight:650;font-size:.92rem;min-width:0}
.ov-what a {color:var(--gbb-ink);text-decoration:none}
.ov-what a:hover {text-decoration:underline}
.ov-what small {display:block;font-weight:500;font-size:.8rem;color:var(--gbb-ink-2)}
.ov-kind {font-size:.72rem;font-weight:700;letter-spacing:.05em;text-transform:uppercase;color:var(--gbb-ink-3);white-space:nowrap}
.ov-clear {padding:1rem 0;font-size:.95rem;color:var(--gbb-ink-2)}
.ov-more {padding:.5rem 0 0;font-size:.8rem;color:var(--gbb-ink-3)}
.ov-bar {display:flex;height:.9rem;border-radius:3px;overflow:hidden;background:var(--gbb-surface-3);margin:.2rem 0 .7rem}
.ov-bar i {display:block;height:100%}
.ov-legend {display:grid;grid-template-columns:auto 1fr;gap:.35rem .9rem;align-items:center;font-size:.9rem}
.ov-legend b {font-size:1.25rem;font-variant-numeric:tabular-nums;text-align:right}
.ov-legend span {display:inline-flex;align-items:center;gap:.4rem}
.ov-note {font-size:.78rem;color:var(--gbb-ink-3);margin:.6rem 0 0;line-height:1.45}
.ov-figs {display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:.7rem 1rem}
.ov-fig b {display:block;font-size:1.9rem;font-weight:750;line-height:1.05;font-variant-numeric:tabular-nums}
.ov-fig span {display:block;font-size:.82rem;color:var(--gbb-ink-2);margin-top:.1rem}
.ov-up {list-style:none;margin:0;padding:0}
.ov-up li {display:grid;grid-template-columns:5.6rem 6.2rem minmax(0,1fr);gap:.2rem .7rem;padding:.42rem 0;border-bottom:1px solid var(--gbb-line);
  font-size:.88rem;align-items:baseline}
.ov-up time {font-variant-numeric:tabular-nums;font-weight:650}
.ov-src {list-style:none;margin:0;padding:0;font-size:.86rem}
.ov-src li {padding:.45rem 0;border-bottom:1px solid var(--gbb-line)}
.ov-src li small {display:block;color:var(--gbb-ink-3);font-size:.78rem;margin-top:.15rem}
@media (max-width: 1100px) {.ov-grid, .ov-row, .ov-row2 {grid-template-columns:1fr}}
"""

KIND_WORD = {"ptw": "Permit", "event": "Event", "maint": "Maintenance"}


def _mark(state: str | None) -> str:
    if state is None:
        return brand.status_mark(brand.INK, "ring")
    colour, _, shape = brand.ASSET_STATE[state]
    return brand.status_mark(colour, shape)


def _day(value: Any, now: Any) -> str:
    at, today = ts(value).astimezone(SGT), ts(now).astimezone(SGT).date()
    days = (at.date() - today).days
    return f"{'Today' if days == 0 else 'Tomorrow' if days == 1 else at.strftime('%a %d %b')} {at:%H:%M}"


def attention_html(data: dict) -> str:
    rows = data["attention"]
    if not rows:
        body = '<div class="ov-clear">Nothing needs attention: no asset is Down, in Warning or Offline, no event is without power, and no permit clashes with an event.</div>'
    else:
        body = '<ul class="ov-list">' + "".join(
            f'<li><span class="ov-word">{_mark(row["state"])}{esc(row["word"])}</span>'
            f'<span class="ov-what"><a href="{esc(row["href"])}" target="_blank">{esc(row["what"])}</a>'
            f'<small>{esc(row["where"])}{" · " + esc(row["why"]) if row["why"] else ""}</small></span>'
            f'<span class="ov-kind">{esc(row["kind"])}</span></li>' for row in rows[:ATTENTION_SHOWN]) + "</ul>"
        if len(rows) > ATTENTION_SHOWN:
            body += f'<div class="ov-more">{len(rows) - ATTENTION_SHOWN} more on the pages linked from each item.</div>'
    count = f"<small>{len(rows)} item{'s' if len(rows) != 1 else ''}</small>" if rows else ""
    return f'<section class="ov-panel"><div class="ov-h">Needs attention now {count}</div>{body}</section>'


def states_html(data: dict) -> str:
    states, total = data["states"], max(1, data["monitored"])
    order = ("down", "warning", "offline", "idle", "operational")
    bar = "".join(f'<i style="width:{states[s] / total * 100:.2f}%;background:{brand.ASSET_STATE[s][0]}" title="{esc(brand.ASSET_STATE[s][1])}: {states[s]}"></i>'
                  for s in order if states[s])
    legend = "".join(f'<b>{states[s]}</b><span>{brand.status_mark(brand.ASSET_STATE[s][0], brand.ASSET_STATE[s][2])}{esc(brand.ASSET_STATE[s][1])}</span>'
                     for s in order)
    note = (f"{data['monitored']} monitored site assets, excluding event-power boxes and sockets."
            + (f" {data['not_monitored']} more are in the register without readings." if data["not_monitored"] else ""))
    return (f'<section class="ov-panel"><div class="ov-h">Asset operational state <a href="?view=asset-status" target="_self">Fleet status →</a></div>'
            f'<div class="ov-bar" role="img" aria-label="Asset operational state distribution">{bar}</div>'
            f'<div class="ov-legend">{legend}</div><div class="ov-note">{esc(note)} Operational state only; '
            f'diagnostic findings are reported separately below.</div></section>')


def permits_html(data: dict) -> str:
    p = data["permits"]
    where = ", ".join(p["zones"][:4]) + (f" and {len(p['zones']) - 4} more" if len(p["zones"]) > 4 else "")
    return (f'<section class="ov-panel"><div class="ov-h">Permits to work today <a href="?view=ptw-map" target="_self">PTW map →</a></div>'
            f'<div class="ov-figs"><div class="ov-fig"><b>{p["active"]}</b><span>active now</span></div>'
            f'<div class="ov-fig"><b>{p["later"]}</b><span>start later today</span></div>'
            f'<div class="ov-fig"><b>{p["isolations"]["electrical"]}</b><span>electrical isolations in force</span></div>'
            f'<div class="ov-fig"><b>{p["isolations"]["physical"]}</b><span>closures or restrictions in force</span></div></div>'
            f'<div class="ov-note">{"Active in " + esc(where) + ". " if where else ""}Counts of permits, not a risk rating.</div></section>')


def power_html(data: dict) -> str:
    s = data["sockets"]
    problem = s.get("down", 0) + s.get("nosupply", 0)
    return (f'<section class="ov-panel"><div class="ov-h">Event power today <a href="?view=event-power" target="_self">Event power →</a></div>'
            f'<div class="ov-figs"><div class="ov-fig"><b>{data["events_today"]}</b><span>events booked on OG boxes</span></div>'
            f'<div class="ov-fig"><b>{s.get("operational", 0)}</b><span>sockets in use</span></div>'
            f'<div class="ov-fig"><b>{problem}</b><span>sockets tripped or without supply</span></div>'
            f'<div class="ov-fig"><b>{s.get("idle", 0)}</b><span>sockets free</span></div></div>'
            f'<div class="ov-note">Simulated socket loads. Socket states, not the asset states above.</div></section>')


def diagnostics_html(data: dict) -> str:
    d = data["diagnostics"]
    head = '<div class="ov-h">Faults &amp; investigations <a href="?view=investigations" target="_self">Investigation queue →</a></div>'
    if d is None:
        return f'<section class="ov-panel">{head}<div class="ov-clear">The diagnostics replay is not loaded.</div></section>'
    return (f'<section class="ov-panel">{head}'
            f'<div class="ov-figs"><div class="ov-fig"><b>{d["findings"]}</b><span>detector findings to review</span></div>'
            f'<div class="ov-fig"><b>{d["open_work_orders"]}</b><span>work orders open or in progress</span></div>'
            f'<div class="ov-fig"><b>{d["quality_issues"]}</b><span>data-quality issues</span></div>'
            f'<div class="ov-fig"><b>{d["other_cases"]}</b><span>other cases (context or insufficient evidence)</span></div></div>'
            f'<div class="ov-note">{brand.demo_badge("Diagnostics replay")} From the replayed demonstration scenario and its own '
            f'five assets; not site assets and not added to the counts above.</div></section>')


def upcoming_html(data: dict) -> str:
    rows = data["upcoming"]
    zones = data["zones"]
    body = ('<ul class="ov-up">' + "".join(
        f'<li><time>{esc(_day(item["start"], data["as_of"]))}</time><span class="ov-kind">{esc(KIND_WORD[item["kind"]])}'
        f'{" · clash" if item["clash"] else ""}</span><span class="ov-what"><a href="{esc(item["href"])}" target="_blank">{esc(item.get("title") or item["label"])}</a>'
        f'<small>{esc((zones.get(item.get("zone")) or {}).get("name") or item.get("zone") or "")}</small></span></li>' for item in rows) + "</ul>"
            if rows else f'<div class="ov-clear">Nothing planned in the next {UPCOMING_HOURS} hours.</div>')
    return (f'<section class="ov-panel"><div class="ov-h">Coming up · next {UPCOMING_HOURS} h <a href="?view=calendar" target="_self">Calendar →</a></div>'
            f'{body}</section>')


def sources_html(data: dict) -> str:
    latest = f"latest reading {sgt(data['latest_reading'], '%d %b %H:%M')} SGT" if data["latest_reading"] else "no readings"
    seeds = [row for row in data["batches"] if row.get("source_type") == "seed"]
    files = [row for row in data["batches"] if row.get("source_type") != "seed"]
    items = [f'<li>{brand.demo_badge("Site operations data")} <b>Generated</b>, as of {sgt(data["as_of"], "%d %b %H:%M")} SGT · {latest}'
             f'<small>Synthetic seed{" (" + esc(seeds[0]["batch_id"]) + ")" if seeds else ""}; regenerated when more than six hours old. Not a live feed.</small></li>']
    if files:
        kinds = ", ".join(sorted({str(row["source_type"]).upper() for row in files}))
        items.append(f'<li>{brand.source_badge("imported")} <b>{len(files)} imported file{"s" if len(files) != 1 else ""}</b> ({esc(kinds)})'
                     f'<small>Latest received {sgt(max(row["received_at"] for row in files), "%d %b %H:%M")} SGT.</small></li>')
    d = data["diagnostics"]
    if d:
        items.append(f'<li>{brand.demo_badge("Diagnostics replay")} <b>Replayed scenario</b> · cutoff {sgt(d["as_of"], "%d %b %Y %H:%M")} SGT'
                     f'<small>Scenario "{esc(d["scenario"])}". Historical replay, not current conditions.</small></li>')
    items.append(f'<li>{brand.source_badge("planned")} <b>Live building systems</b><small>No live feed is connected.</small></li>')
    return (f'<section class="ov-panel"><div class="ov-h">Data sources &amp; freshness <a href="?view=architecture" target="_self">Architecture →</a></div>'
            f'<ul class="ov-src">{"".join(items)}</ul></section>')


def page_html(data: dict) -> str:
    return (f'<style>{CSS}</style><div class="ov">'
            f'<div class="ov-asof">Site data as of <b>{sgt(data["as_of"], "%A %d %B %Y, %H:%M")} SGT</b></div>'
            f'<div class="ov-grid">{attention_html(data)}{states_html(data)}</div>'
            f'<div class="ov-row">{permits_html(data)}{power_html(data)}{diagnostics_html(data)}</div>'
            f'<div class="ov-row2">{upcoming_html(data)}{sources_html(data)}</div></div>')
