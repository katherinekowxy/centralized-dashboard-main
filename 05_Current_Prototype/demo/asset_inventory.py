"""Asset status by location: which equipment each location holds comes from the iSMM inventory exports (``Assets/``,
one per store, each line with its Ref. ID); the Down, Warning and Offline states are demo, because no sensor feed exists.

Only equipment lines count (DBs, isolators, breakers, pumps, fans, ceeforms, power supplies...), not consumables such
as bulbs, locksets or taps. The demo states are fixed per Ref. ID, so they do not change between reloads.
"""

from __future__ import annotations

import hashlib
import html
from typing import Any

from demo import site_theme

EQUIPMENT = ("DB", "Isolator", "Circuit Breaker", "Pump", "Fan", "Ceeform", "Power Supply", "Transformer", "Contactor", "Meter")
DEMO_COUNTS = (("down", 3), ("warning", 5), ("offline", 2))  # how many lines get each demo state
DEMO_REASON = {
    "down": {"Pump": "Not running", "Fan": "Not running", "default": "Tripped"},
    "warning": {"Pump": "Current above rating", "Fan": "Vibration high", "default": "Running hot"},
    "offline": {"default": "No data for 2 h"},
}
ORDER = ("down", "warning", "offline", "operational")
LABEL = {"down": "Down", "warning": "Warning", "offline": "Offline", "operational": "Running"}


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def location_name(store: str) -> str:
    """The store as iSMM names it; the site stores are shortened ("Gardens By The Bay (South)" reads "GBB South")."""
    return store.replace("Gardens By The Bay (", "GBB ").rstrip(")") if store.startswith("Gardens By The Bay (") else store


def _rank(item: dict) -> str:
    return hashlib.sha256(f"{item['store']}|{item['ref']}|{item['name']}".encode()).hexdigest()


def equipment(items: list[dict]) -> list[dict]:
    """Equipment lines from the inventories, each with a demo state and a few words of reason."""
    rows = [{"location": location_name(item["store"]), "type": item["subcategory"], "name": item["item"], "ref": item["ref"],
             "quantity": item["quantity"], "store": item["store"]}
            for item in items if item.get("subcategory") in EQUIPMENT]
    ranked = sorted(rows, key=_rank)
    states, start = {}, 0
    for state, count in DEMO_COUNTS:
        for row in ranked[start:start + count]:
            states[id(row)] = state
        start += count
    for row in rows:
        row["state"] = states.get(id(row), "operational")
        reasons = DEMO_REASON.get(row["state"], {})
        row["reason"] = reasons.get(row["type"], reasons.get("default", ""))
    rows.sort(key=lambda row: (row["location"], ORDER.index(row["state"]), EQUIPMENT.index(row["type"]), row["name"]))
    return rows


def counts(rows: list[dict]) -> dict[str, int]:
    return {state: sum(row["state"] == state for row in rows) for state in ORDER}


def location_html(location: str, rows: list[dict]) -> str:
    """One location: problem lines as banners (name, Ref. ID, demo reason), then one row per healthy equipment type."""
    problems = [row for row in rows if row["state"] != "operational"]
    lines = "".join(site_theme.row_html(f"{row['type']} · {row['name']}", row["state"],
                                        reason=f"Ref. {row['ref'] or 'not recorded'} · {row['reason']} (demo)",
                                        title=f"{row['name']} · Ref. {row['ref']}") for row in problems)
    healthy: dict[str, int] = {}
    for row in rows:
        if row["state"] == "operational":
            healthy[row["type"]] = healthy.get(row["type"], 0) + 1
    lines += "".join(site_theme.row_html(f"{kind} · {n} item{'s' if n != 1 else ''}", "operational")
                     for kind, n in sorted(healthy.items(), key=lambda pair: EQUIPMENT.index(pair[0])))
    note = " · ".join(f"{n} {LABEL[state]}" for state in ("down", "warning", "offline")
                      if (n := sum(row["state"] == state for row in rows)))
    return site_theme.zone_html(location, lines, note)


def board_html(rows: list[dict], exported: Any) -> str:
    tally = counts(rows)
    cards = site_theme.cards_html([(LABEL[state], tally[state], site_theme.CARD_MARK[state])
                                   for state in ORDER])
    when = f"Inventories exported {exported:%d %b %Y, %H:%M}" if exported else "Inventory export time not recorded"
    head = (f'<div class="tv-top"><div><div class="tv-updated">{esc(when)} · states are demo</div></div>{cards}</div>'
            f'<div class="tv-meta">{site_theme.key_html(("operational", "down", "warning", "offline"), cone=False)}</div>')
    grouped: dict[str, list[dict]] = {}
    for row in rows:
        grouped.setdefault(row["location"], []).append(row)
    order = sorted(grouped, key=lambda name: (min(ORDER.index(row["state"]) for row in grouped[name]), name))
    zones = "".join(location_html(name, grouped[name]) for name in order)
    return f'<div class="tv">{head}<div class="tv-zones" style="--col:17rem">{zones}</div></div>'


def table(rows: list[dict]):
    import pandas as pd

    return pd.DataFrame([{"Location": row["location"], "Type": row["type"], "Item": row["name"], "Ref. ID": row["ref"],
                          "Held": row["quantity"], "State (demo)": LABEL[row["state"]]} for row in rows])


def render(inventory: dict) -> None:
    import streamlit as st

    rows = equipment(inventory.get("items") or [])
    if not rows:
        st.info("No equipment lines (DB, isolator, pump...) were found in the inventory exports in Assets/.")
        return
    st.markdown(site_theme.style() + board_html(rows, inventory.get("exported")), unsafe_allow_html=True)
    st.caption(f"{len(rows)} equipment lines across {len({row['location'] for row in rows})} locations, from the iSMM inventories. "
               "Down, Warning and Offline are demo states: there is no sensor feed yet.")
    with st.expander("All equipment, with Ref. ID"):
        c1, c2 = st.columns(2)
        places = c1.multiselect("Location", sorted({row["location"] for row in rows}), placeholder="All locations", key="ai_loc")
        kinds = c2.multiselect("Type", [kind for kind in EQUIPMENT if any(row["type"] == kind for row in rows)],
                               placeholder="All types", key="ai_type")
        shown = [row for row in rows if (not places or row["location"] in places) and (not kinds or row["type"] in kinds)]
        st.dataframe(table(shown), hide_index=True, width="stretch")
