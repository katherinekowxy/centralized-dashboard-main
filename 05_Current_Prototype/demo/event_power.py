"""Event power: the OG boxes events plug into, each with its CEEform sockets and their live load, as a small schematic.

Dan, 13 October 2026: "have another asset schematic for events specifically, each og box has a few ceeforms that
events will use. use a few og boxes for various events and simulate power loads across the few ceeforms".

Each OG box is a panel: the DB that feeds it, the box with its total load against its incomer, then a busbar to its
sockets. Each socket shows its amps against its rating, what the event is using it for, and its state in socket words
(In use, Free, Warning, Tripped) with the Asset dashboard's colours and rules. When the feeding DB is Down, the feed
turns red and dashed and every socket says "No supply". An event booked on that box before power returns is called
out. Loads are synthetic. "Now" is the site data's as_of.
"""

from __future__ import annotations

from typing import Any

from demo.asset_dashboard import CSS as ASSET_CSS, esc, sgt, today_window
from demo.asset_state import COLOUR, LABEL, ORBS, asset_state, ts
from demo.calendar_overview import STAR

WORD = {"operational": "In use", "idle": "Free", "warning": "Warning", "down": "Tripped", "offline": "Offline"}
NO_SUPPLY = "nosupply"
ORDER = ("down", NO_SUPPLY, "warning", "offline", "operational", "idle")  # problems first, then boxes in use
LIVE_LINE, DEAD_LINE = "#8A8F93", "#B91C1C"

CSS = """
.ep-boxes {display:grid;grid-template-columns:repeat(auto-fill,minmax(31rem,1fr));gap:.9rem;align-items:start}
.ep-panel {position:relative;border:2px solid var(--gbb-line-strong);border-radius:1.1rem;background:var(--gbb-surface);padding:.55rem .75rem .75rem}
.ep-top {display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:.3rem .8rem;margin:0 0 .45rem}
.ep-zone {font-size:1.35rem;font-weight:800;color:var(--gbb-ink)}
.ep-event {display:inline-flex;align-items:center;gap:.4rem;padding:.2rem .65rem;border:2px solid var(--gbb-ink);border-radius:.6rem;
  font-size:1rem;font-weight:750;color:var(--gbb-ink) !important;text-decoration:none !important;background:var(--gbb-surface-2)}
.ep-event svg {width:1.05rem;height:1.05rem;flex:none}
.ep-event.ep-none {border-style:dashed;border-color:var(--gbb-line-strong);background:none;color:var(--gbb-ink-3) !important}
.ep-event.ep-clash {background:var(--gbb-ink);color:#fff !important}
.ep-feeder {display:inline-flex;align-items:center;gap:.6rem;padding:.2rem .7rem;border:2px solid var(--gbb-line-strong);border-radius:.6rem;
  font-size:1rem;font-weight:750;color:var(--gbb-ink-2)}
.ep-feeder small {font-size:.88rem;font-weight:700;color:var(--gbb-ink-3)}
.ep-feeder.ep-nc {border-style:dashed}
.ep-feeder.ep-dead {border-color:#B91C1C;background:#B91C1C;color:#fff}
.ep-head {position:relative;display:flex;flex-wrap:wrap;align-items:center;gap:.25rem .9rem;margin-top:.8rem;padding:.4rem .75rem;
  border-radius:12px;border:3px solid color-mix(in srgb, var(--c) 85%, transparent);background:color-mix(in srgb, var(--c) 13%, var(--gbb-surface));
  color:var(--gbb-ink) !important;text-decoration:none !important}
.ep-head::before {content:"";position:absolute;left:1.6rem;top:calc(-.8rem - 3px);height:.8rem;border-left:3px var(--ls) var(--line)}
.ep-name {font-size:1.2rem;font-weight:800;color:var(--gbb-ink)}
.ep-word {display:inline-flex;align-items:center;gap:.4rem;font-size:1rem;font-weight:800;color:var(--gbb-ink);white-space:nowrap}
.ep-load {display:flex;align-items:center;gap:.6rem;flex:1;min-width:11rem;font-size:1rem;color:var(--gbb-ink-2);white-space:nowrap}
.ep-load b {font-size:1.35rem;color:var(--gbb-ink);font-variant-numeric:tabular-nums}
.ep-bar {flex:1;height:.55rem;border-radius:99px;background:var(--gbb-surface-3);overflow:hidden}
.ep-bar i {display:block;height:100%;border-radius:99px;background:var(--c)}
.ep-sockets {position:relative;display:grid;grid-template-columns:repeat(var(--n),minmax(0,1fr));gap:.5rem;margin-top:1.7rem}
.ep-sockets::before {content:"";position:absolute;top:-.85rem;left:calc((100% - (var(--n) - 1) * .5rem) / var(--n) / 2);
  right:calc((100% - (var(--n) - 1) * .5rem) / var(--n) / 2);border-top:3px var(--ls) var(--line)}
.ep-sockets::after {content:"";position:absolute;top:calc(-1.7rem - 3px);left:calc((100% - (var(--n) - 1) * .5rem) / var(--n) / 2);
  height:calc(.85rem + 3px);border-left:3px var(--ls) var(--line)}
.ep-sock {position:relative;display:flex;flex-direction:column;gap:.1rem;min-width:0;padding:.4rem .5rem .45rem;border-radius:12px;
  border:2px solid color-mix(in srgb, var(--c) 80%, transparent);background:color-mix(in srgb, var(--c) 13%, var(--gbb-surface));
  color:var(--gbb-ink) !important;text-decoration:none !important}
.ep-sock::before {content:"";position:absolute;left:50%;top:calc(-.85rem - 2px);height:.85rem;border-left:3px var(--ls) var(--line)}
.ep-sock:hover, .ep-head:hover {filter:brightness(1.15)}
.ep-sid {display:flex;align-items:baseline;justify-content:space-between;gap:.3rem;font-size:1.05rem;font-weight:800;color:var(--gbb-ink)}
.ep-sid small {font-size:.82rem;font-weight:700;color:var(--gbb-ink-3);white-space:nowrap}
.ep-amps {font-size:2rem;font-weight:800;line-height:1.05;color:var(--gbb-ink);font-variant-numeric:tabular-nums;white-space:nowrap}
.ep-amps small {font-size:.95rem;font-weight:700;color:var(--gbb-ink-2)}
.ep-sock .ep-bar {flex:none;margin:.15rem 0 .1rem}
.ep-sock .ep-word {margin:0;font-size:.95rem}
.ep-use {display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;font-size:.92rem;font-weight:700;
  color:var(--gbb-ink-2);line-height:1.15;word-break:normal;overflow-wrap:normal}
.ep-use.ep-later {color:var(--gbb-ink-3);font-weight:650}
.ep-sock.ep-off {border-style:dashed;border-color:#B91C1C;background:transparent}
.ep-legend .ep-key {display:inline-block;width:1.4rem;height:.9rem;border-radius:3px;border:2px dashed #B91C1C}
.ep-legend .ep-swatch {display:inline-block;width:2rem;height:.5rem;border-radius:99px;background:linear-gradient(90deg,#15803D 60%,var(--gbb-surface-3) 60%)}
@media (max-width: 640px) {
  .ep-boxes {grid-template-columns:1fr}
  .ep-sockets {grid-template-columns:repeat(auto-fill,minmax(6.5rem,1fr))}
  .ep-sockets::before, .ep-sockets::after, .ep-sock::before {display:none}
}
"""


def _db(db: Any) -> Any:
    if db is None:
        from demo import site_db as db
    return db


def amps(value: Any) -> str:
    return "–" if value is None else f"{float(value):.0f}"


def board(db: Any = None) -> dict[str, Any]:
    """Each OG box with its feeder, sockets, states, loads and today's events; problem boxes first."""
    db = _db(db)
    as_of = db.as_of()
    latest = db.latest_readings()
    assets = {asset["asset_id"]: asset for asset in db.assets()}
    impacts = db.impacts(active_at=as_of)
    start, end = today_window(as_of)
    bookings = db.event_power(start=start, end=end)
    zones = {zone["zone_code"]: zone for zone in db.zones()}

    def reading(asset_id: str) -> dict:
        asset = assets[asset_id]
        values = latest.get(asset_id, {})
        state = asset_state(asset, values, as_of) if asset.get("connected", 1) else {"state": "unconnected", "reason": "Not connected"}
        current = values.get("current_a", {}).get("value")
        return {**asset, **state, "amps": current}

    boxes = []
    for box_id, box in assets.items():
        if box.get("asset_type") != "OGB":
            continue
        feeder = reading(box["fed_from"]) if box.get("fed_from") in assets else None
        dead = feeder is not None and feeder["state"] == "down"
        back_at = max((ts(row["end_at"]) for row in impacts if feeder and row.get("target_id") == feeder["asset_id"]), default=None)
        sockets = [reading(asset_id) for asset_id, asset in sorted(assets.items())
                   if asset.get("asset_type") == "CEE" and asset.get("fed_from") == box_id]
        ids = {row["asset_id"] for row in sockets}
        events: dict[str, dict] = {}
        for row in bookings:
            if row["asset_id"] in ids:
                events.setdefault(row["eo_id"], {**row, "uses": {}})["uses"][row["asset_id"]] = row["use"]
        now = ts(as_of)
        on = [event for event in events.values() if ts(event["start_at"]) <= now < ts(event["end_at"])]
        later = sorted((event for event in events.values() if ts(event["start_at"]) > now), key=lambda event: event["start_at"])
        event = (on or later or [None])[0]
        state = NO_SUPPLY if dead else reading(box_id)["state"]
        worst = min(ORDER.index(NO_SUPPLY if dead and row["state"] == "idle" else row["state"]) for row in [{"state": state}, *sockets])
        boxes.append({"box": reading(box_id), "state": state, "feeder": feeder, "dead": dead, "back_at": back_at,
                      "sockets": sockets, "event": event, "live": bool(on), "worst": worst,
                      "zone": (zones.get(box["zone_code"]) or {}).get("name") or box["zone_code"]})
    zone_worst = {}
    for item in boxes:
        zone_worst[item["zone"]] = min(zone_worst.get(item["zone"], len(ORDER)), item["worst"])
    boxes.sort(key=lambda item: (zone_worst[item["zone"]], item["zone"], item["worst"], not item["live"], item["box"]["name"]))
    return {"as_of": as_of, "boxes": boxes}


def _word(state: str) -> tuple[str, str]:
    """(words, colour) for a box or socket state."""
    if state == NO_SUPPLY:
        return "No supply", COLOUR["down"]
    return WORD[state], COLOUR[state]


def event_html(item: dict) -> str:
    event = item["event"]
    if event is None:
        return '<span class="ep-event ep-none">No event today</span>'
    clash = item["dead"] and item["back_at"] is not None and ts(event["start_at"]) < item["back_at"] or item["dead"] and item["live"]
    window = (f'until {sgt(event["end_at"])}' if item["live"] else f'{sgt(event["start_at"])}' if clash
              else f'{sgt(event["start_at"])}–{sgt(event["end_at"])}')
    note = f' · no power until {sgt(item["back_at"])}' if clash and item["back_at"] else " · no power" if clash else ""
    return (f'<a class="ep-event{" ep-clash" if clash else ""}" href="?eo={esc(event["eo_id"])}" target="_blank">{STAR}'
            f'{"" if item["live"] else "Next: "}{esc(event["title"])} · {window}{note}</a>')


def feeder_html(item: dict) -> str:
    feeder = item["feeder"]
    if feeder is None:
        return ""
    if feeder["state"] == "unconnected":
        return f'<span class="ep-feeder ep-nc">{esc(feeder["name"])}<small>Not connected</small></span>'
    if item["dead"]:
        until = f' until {sgt(item["back_at"])}' if item["back_at"] else ""
        return f'<span class="ep-feeder ep-dead">{esc(feeder["name"])}<small style="color:#fff">Down{until}</small></span>'
    return f'<span class="ep-feeder">{esc(feeder["name"])}<small>{esc(LABEL.get(feeder["state"], ""))}</small></span>'


def _bar(value: Any, rated: Any) -> tuple[int, str]:
    share = 0 if not value or not rated else round(float(value) / float(rated) * 100)
    return share, f'<span class="ep-bar"><i style="width:{min(share, 100)}%"></i></span>'


def socket_html(row: dict, n: int, item: dict) -> str:
    state = NO_SUPPLY if item["dead"] else row["state"]
    words, colour = _word(state)
    share, bar = _bar(row["amps"], row.get("rated_current_a"))
    orbs = '<span class="sa-orb"></span><span class="sa-orb"></span>' if state in ORBS else ""
    event = item["event"]
    use = (event or {}).get("uses", {}).get(row["asset_id"])
    if use and not item["live"]:
        use_html = f'<span class="ep-use ep-later">{sgt(event["start_at"])}: {esc(use)}</span>'
    else:
        use_html = f'<span class="ep-use">{esc(use or "")}</span>'
    return (f'<a class="ep-sock{" ep-off" if state == NO_SUPPLY else ""}" style="--c:{colour}" href="?asset={esc(row["asset_id"])}" '
            f'target="_blank" title="{esc(row["name"])} · {esc(words)}: {esc(row.get("reason"))}">{orbs}'
            f'<span class="ep-sid">S{n}<small>{"3-phase" if row.get("phases") == 3 else "1-phase"}</small></span>'
            f'<b class="ep-amps">{amps(row["amps"])}<small> / {amps(row.get("rated_current_a"))} A</small></b>{bar}'
            f'<span class="ep-word"><i class="sa-dot"></i>{esc(words)}</span>{use_html}</a>')


def box_html(item: dict) -> str:
    box = item["box"]
    words, colour = _word(item["state"])
    share, bar = _bar(box["amps"], box.get("rated_current_a"))
    orbs = '<span class="sa-orb"></span><span class="sa-orb"></span>' if item["state"] in ORBS else ""
    line = f"--line:{DEAD_LINE};--ls:dashed" if item["dead"] else f"--line:{LIVE_LINE};--ls:solid"
    head = (f'<a class="ep-head" style="--c:{colour}" href="?asset={esc(box["asset_id"])}" target="_blank" '
            f'title="{esc(box["name"])} · {esc(words)}">{orbs}<span class="ep-name">{esc(box["name"])}</span>'
            f'<span class="ep-load"><b>{amps(box["amps"])} A</b>of {amps(box.get("rated_current_a"))} A{bar}</span>'
            f'<span class="ep-word"><i class="sa-dot"></i>{esc(words)}</span></a>')
    sockets = "".join(socket_html(row, n, item) for n, row in enumerate(item["sockets"], start=1))
    return (f'<div class="ep-panel" style="{line}"><div class="ep-top"><span class="ep-zone">{esc(item["zone"])}</span>{event_html(item)}</div>'
            f'{feeder_html(item)}{head}<div class="ep-sockets" style="--n:{max(1, len(item["sockets"]))}">{sockets}</div></div>')


def tally_html(data: dict) -> str:
    counts: dict[str, int] = {}
    for item in data["boxes"]:
        for row in item["sockets"]:
            state = NO_SUPPLY if item["dead"] else row["state"]
            counts[state] = counts.get(state, 0) + 1
    chips = []
    for state in ORDER:
        if counts.get(state):
            words, colour = _word(state)
            chips.append(f'<span style="--c:{colour}"><i class="sa-dot"></i><b>{counts[state]}</b>{esc(words)}</span>')
    return '<div class="sa-tally">' + "".join(chips) + "</div>"


def legend_html() -> str:
    return ('<div class="sa-legend ep-legend"><span><i class="ep-key"></i>No supply: its DB is down</span>'
            '<span><i class="ep-swatch"></i>Load against the rating</span></div>')


def render(db: Any = None) -> None:
    import streamlit as st

    data = board(db)
    st.markdown(f"<style>{ASSET_CSS}{CSS}</style>", unsafe_allow_html=True)
    if not data["boxes"]:
        st.info("No OG boxes in the site database yet.")
        return
    st.markdown(f'<div class="sa-bar">{tally_html(data)}{legend_html()}'
                f'<div class="sa-note">Synthetic loads · sockets per OG box · as of {sgt(data["as_of"], "%d %b %H:%M")} SGT</div></div>'
                + '<div class="ep-boxes">' + "".join(box_html(item) for item in data["boxes"]) + "</div>", unsafe_allow_html=True)
