"""Asset schematic: the distribution boards with something to look at, and under each DB only the devices that need
attention. Built for the TV in GBTB's report colours (demo/site_theme.py).

Dan, 12 October 2026: "a rough schematic. what is tied to what asset. main thing is the db and what it supports".
Dan, 13 October 2026: "for the db, don't need to show healthy assets. when an asset is under maintainence, down or
warning, then only present it on the screen, under their respective parent db, else keep it hidden". The defaults
Dan approved: Offline shows too, because no data is not healthy. When a DB is Down, everything it feeds is listed, and a
device without a fault of its own reads "No supply", including devices SignalDesk isn't connected to. DBs with nothing to
show fold into one "all normal" line. A DB with something below it is shown as the parent even when it is fine itself.
"""

from __future__ import annotations

from typing import Any

from demo import site_theme
from demo.asset_dashboard import problems_note, reason_for, sgt, today_window
from demo.asset_state import EVENT_POWER_TYPES, LABEL, SEVERITY, asset_state, maintenance_today

UNCONNECTED = "unconnected"
RANK = (*SEVERITY, UNCONNECTED)  # problems first; a device with no readings sorts last
SHOW = {"down", "warning", "offline"}  # shown with a banner; anything with a cone is shown too


def _db(db: Any) -> Any:
    if db is None:
        from demo import site_db as db
    return db


def schematic(db: Any = None) -> dict[str, Any]:
    """Every asset with its state (or "unconnected"), what feeds what, and the DBs at the top of each zone."""
    db = _db(db)
    as_of = db.as_of()
    latest = db.latest_readings()
    start, end = today_window(as_of)
    work, impacts = db.work_orders(start, end), db.impacts(active_at=as_of)
    rows: dict[str, dict] = {}
    for asset in db.assets():
        if asset.get("asset_type") in EVENT_POWER_TYPES:  # OG boxes and sockets have their own tab, Event power
            continue
        maintenance = maintenance_today(asset["asset_id"], work, impacts, as_of)
        if asset.get("connected", 1):
            state = asset_state(asset, latest.get(asset["asset_id"], {}), as_of)
        else:
            state = {"state": UNCONNECTED, "reason": "SignalDesk gets no readings from it"}
        rows[asset["asset_id"]] = {**asset, **state, "maintenance": maintenance}
    feeds: dict[str, list[str]] = {}
    for asset_id, row in rows.items():
        if row.get("fed_from") in rows:
            feeds.setdefault(row["fed_from"], []).append(asset_id)

    def worst(asset_id: str, seen: frozenset = frozenset()) -> int:
        """The most severe state in a DB's whole feed, so problem DBs and zones sort first."""
        if asset_id in seen:  # a feed loop in bad data must not hang the page
            return RANK.index(rows[asset_id]["state"])
        return min([RANK.index(rows[asset_id]["state"]), *(worst(child, seen | {asset_id}) for child in feeds.get(asset_id, []))])

    for asset_id in rows:
        feeds.get(asset_id, []).sort(key=lambda child: (worst(child), rows[child]["asset_id"]))
    roots: dict[str, list[str]] = {}
    for asset_id, row in rows.items():
        if row.get("fed_from") not in rows:
            roots.setdefault(row["zone_code"], []).append(asset_id)
    reached: set[str] = set()

    def walk(asset_id: str) -> None:
        if asset_id not in reached:
            reached.add(asset_id)
            for child in feeds.get(asset_id, []):
                walk(child)

    for asset_id in [root for zone_roots in roots.values() for root in zone_roots] + sorted(rows):
        if asset_id not in reached:  # a feed loop in bad data: show its devices rather than drop them
            if asset_id not in roots.get(rows[asset_id]["zone_code"], []):
                roots.setdefault(rows[asset_id]["zone_code"], []).append(asset_id)
            walk(asset_id)
    for zone_roots in roots.values():
        zone_roots.sort(key=lambda asset_id: (worst(asset_id), asset_id))
    return {"as_of": as_of, "rows": rows, "feeds": feeds, "roots": roots, "worst": worst,
            "zones": {zone["zone_code"]: zone for zone in db.zones()}}


def needs_attention(row: dict) -> bool:
    return row["state"] in SHOW or bool(row.get("maintenance"))


def _row(row: dict, state: str, parent: bool) -> str:
    connected = row["state"] != UNCONNECTED
    reason = reason_for(row) if state in site_theme.BANNER else ("Its DB is down" if state == site_theme.NO_SUPPLY else "")
    if state == site_theme.NO_SUPPLY and not connected:
        reason = "Its DB is down · not connected"
    return site_theme.row_html(row.get("name") or row["asset_id"], state, href=f"?asset={row['asset_id']}" if connected else None,
                               reason=reason, cone=bool(row.get("maintenance")), parent=parent,
                               title=f"{row.get('name')} ({row['asset_id']}) · {LABEL.get(row['state'], 'Not connected')}")


def branch_html(asset_id: str, data: dict, no_supply: bool = False, seen: frozenset = frozenset()) -> tuple[str, list[str]]:
    """An asset and whatever below it needs attention, as (html, states shown). Empty when nothing here needs a look.
    ``no_supply``: a DB above is Down, so this asset is listed whatever its own state."""
    row = data["rows"][asset_id]
    dead = no_supply or row["state"] == "down"
    parts, shown = [], []
    for child in data["feeds"].get(asset_id, []):
        if child not in seen:
            html, states = branch_html(child, data, dead, seen | {asset_id})
            parts.append(html)
            shown += states
    inner = "".join(parts)
    if not (needs_attention(row) or no_supply or inner):
        return "", []
    state = row["state"] if row["state"] in SHOW else site_theme.NO_SUPPLY if no_supply else row["state"]
    node = _row(row, state, parent=bool(data["feeds"].get(asset_id)))
    states = [state] + (["maintenance"] if row.get("maintenance") else []) + shown
    if not inner:
        return node, states
    return f'<div class="tv-branch">{node}<div class="tv-feeds{" tv-dead" if dead else ""}">{inner}</div></div>', states


def board_html(data: dict) -> str:
    """Zones with something to look at, problem zones first; everything else folds into one line."""
    order = sorted(data["roots"], key=lambda code: (min(data["worst"](root) for root in data["roots"][code]),
                                                    (data["zones"].get(code) or {}).get("name") or code))
    zones, shown, hidden = [], [], []
    for code in order:
        parts = []
        for root in data["roots"][code]:
            html, states = branch_html(root, data)
            if html:
                parts.append(html)
                shown += states
            else:
                hidden.append(root)
        if parts:
            zone_rows = [row for row in data["rows"].values() if row["zone_code"] == code]
            zones.append(site_theme.zone_html((data["zones"].get(code) or {}).get("name") or code, "".join(parts), problems_note(zone_rows)))
    noun = "DB" if all(data["rows"][root]["asset_type"] == "DB" for root in hidden) else "asset"
    rest = f'{len(hidden)} other {noun}{"s" if len(hidden) != 1 else ""} · all normal' if hidden else ""
    counts = [(label, shown.count(state), site_theme.CARD_MARK.get(state) or ("#EF4444" if state == site_theme.NO_SUPPLY else None))
              for state, label in (("down", "Down"), (site_theme.NO_SUPPLY, "No supply"), ("warning", "Warning"),
                                   ("offline", "Offline"), ("maintenance", "Maintenance"))]
    cards = site_theme.cards_html([card for card in counts if card[1]] + [("DBs all normal", len(hidden), site_theme.CARD_MARK["operational"])])
    key = site_theme.key_html(("down", "warning", "offline"), cone=True, no_supply=True)
    header = site_theme.header_html("Asset schematic", sgt(data["as_of"], "%d %b %Y, %H:%M"), cards, key)
    if not zones:
        body = (f'<div class="tv-clear">All assets normal<small>{len(data["rows"])} assets on '
                f'{sum(row["asset_type"] == "DB" for row in data["rows"].values())} DBs checked</small></div>')
    else:
        body = f'<div class="tv-zones" style="--col:24rem">{"".join(zones)}</div>' + (f'<div class="tv-note"><i class="tv-dot" style="--d:{site_theme.DOT["operational"]}"></i>{rest}</div>' if rest else "")
    return f'<div class="tv">{header}{body}</div>'


def render(db: Any = None) -> None:
    import streamlit as st

    st.markdown(site_theme.style() + board_html(schematic(db)), unsafe_allow_html=True)
