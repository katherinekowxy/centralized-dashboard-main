"""Real records behind each demo asset: the iSMM faults raised against that kind of equipment in that building, and the
matching spare parts (with their Ref. ID) in the store inventories. Read-only; works on the records that
demo.sources.registers.load_faults and demo.sources.ismm.load_inventory already return.

The demo seed (demo/site_seed.py) lists an asset only where this finds faults (21 October 2026). The inventories are
store stock, not installed equipment: a spare DB in the Meadow store says nothing about what is installed at the Meadow,
so spares are shown as "spares held", never as evidence that an asset exists.
"""

from __future__ import annotations

import re
from typing import Any

ZONE_BUILDINGS = {  # map zone -> the iSMM "Building" values for it
    "FDM": ("Flower Dome",), "CFR": ("Cloud Forest",), "SGV": ("Supertree Grove",), "SKY": ("Supertree Grove",),
    "SLV": ("Silver Garden",), "GLD": ("Golden Garden",), "CHG": ("Children Garden",), "BFP": ("Bayfront",),
    "ENT": ("Arrival Area",), "ACT": ("Active Garden",), "MDW": ("Meadow",), "DFL": ("Dragonfly Lake",),
    "HER": ("Heritage Gardens",), "SRN": ("Serene Garden",), "FFY": ("Floral Fantasy",), "CNP": ("Canopy Hub",),
}

TYPE_RULES = {  # asset type -> (iSMM trade categories, words in the remarks); either one matches
    "DB": ({"Distribution Boards", "Miniature Circuit Breaker", "Earth-leakage Circuit Breaker", "Electrical (Euler)", "Junction Box"},
           r"\bdb\b|distribution board|\bmccb\b|\bmcb\b|\belcb\b|\brccb\b|isolator|power trip|switch ?room"),
    "OUT": ({"Socket", "Socket Outlet"}, r"socket|power point"),
    "LGT": (set(), r"light|lamp"),
    "PMP": ({"Pump", "Aerator"}, r"pump"),
    "FTN": ({"Pump", "Water Poles"}, r"pump|weir|fountain"),
    "AHU": ({"Air Handling Unit"}, r"\bahu\b|air handl"),
    "LFT": ({"Lift System", "Lift & Escalator (Otis)"}, r"\blift\b"),
    "MST": (set(), r"\bfog\b|mist"),
    "OGB": ({"Power Handover", "Power Handover/Takeover"}, r"\bog\b|\bog-|og box|ceeform|cee form"),
    "CEE": ({"Power Handover", "Power Handover/Takeover"}, r"\bog\b|\bog-|og box|ceeform|cee form"),
}
EVENT_POWER = {"OGB", "CEE"}  # event power is handed over as event jobs, so those count too

ASSET_RULES = {  # assets named after one piece of equipment: only remarks naming it (and what it is) count
    "FDM-AHU-01": r"cd\s*-?\s*ahu\s*-?\s*0?7\b",
    "FDM-PMP-01": r"flower field.*pump|fd pump",
    "FDM-LFT-01": r"cd-?f-?l1\b",
    "CFR-AHU-01": r"ahu-?cm-?10\b",
    "CFR-MST-01": r"fog machine",
    "CFR-PMP-01": r"waterfall|water feature pump",
    "CFR-LFT-01": r"cm-?f-?l1\b|cmfl1",
    "SGV-OUT-01": r"(power|trip|supply).*\bco5\b|\bco5\b.*(power|trip|supply)",
    "SGV-PMP-01": r"supertree filter|\bsap\b",
    "SKY-LFT-01": r"\b(so|stg|skyway) lift|lift.*skyway",
    "SKY-LFT-02": r"\b(so|stg|skyway) lift|lift.*skyway",
    "SLV-FTN-01": r"weir",
    "DFL-PMP-01": r"aerator",
    "HER-PMP-01": r"chinese garden.*pump|pump.*chinese garden",
    "MDW-OGB-01": r"lg-?og-?0?4\b",
    "SGV-OGB-01": r"lg-?og-?0?3\b",
}

SPARE_SUBCATEGORIES = {  # asset type -> inventory subcategories that hold its spare parts. None for AHUs, lifts or fog
    "DB": ("DB", "Circuit Breaker", "Isolator"), "OUT": ("Plug", "Ceeform", "Switch"),  # machines: "Belt" and "Fan" hold
    "LGT": ("Lamp", "Bulb", "Driver"), "PMP": ("Pump",), "FTN": ("Pump",),               # harnesses and room fans, not AHU parts
    "OGB": ("Ceeform", "Isolator"), "CEE": ("Ceeform",),
}


def _text(record: dict) -> str:
    return " ".join(str(record.get(key) or "") for key in ("type", "remarks", "what")).lower()


def faults_for(asset: dict, faults: list[dict]) -> list[dict]:
    """Fault-log records that show this asset (or its kind of equipment) exists where the demo puts it, newest first."""
    buildings = ZONE_BUILDINGS.get(asset.get("zone_code") or "", ())
    if not buildings:
        return []
    named = ASSET_RULES.get(asset.get("asset_id") or "")
    categories, words = TYPE_RULES.get(asset.get("asset_type") or "", (set(), ""))
    if not named and not (categories or words):
        return []
    found = []
    for record in faults:
        kinds = ("fault", "event") if asset.get("asset_type") in EVENT_POWER else ("fault",)
        if record.get("building") not in buildings or record.get("kind", "fault") not in kinds:
            continue
        text = _text(record)
        if named:
            hit = re.search(named, text)
        else:
            hit = record.get("trade_category") in categories or (words and re.search(words, text))
        if hit:
            found.append(record)
    return sorted(found, key=lambda r: r.get("reported") or 0, reverse=True)


def spares_for(asset: dict, items: list[dict]) -> list[dict]:
    """Store inventory lines that are spare parts for this kind of asset, out-of-stock first."""
    wanted = SPARE_SUBCATEGORIES.get(asset.get("asset_type") or "", ())
    order = {"out": 0, "low": 1, "unknown": 2, "ok": 3}
    return sorted((item for item in items if item.get("subcategory") in wanted),
                  key=lambda item: (order.get(item.get("state"), 9), item.get("store") or "", item.get("item") or ""))


STATE_WORD = {"out": ("fault", "Out of stock"), "low": ("warn", "Below minimum"), "ok": ("ok", "In stock"),
              "unknown": ("neutral", "Quantity not recorded")}


def page_html(asset: dict, real: dict[str, Any] | None, shown: int = 8) -> str:
    """The "In the iSMM records" panels for an asset page: the faults behind it, and spares held for it."""
    from demo import ui

    if not real:
        return ui.panel("In the iSMM records", '<div class="u-empty">Real data is not configured. Set GBB_DATA_DIR to the export '
                        "folder to see the faults and spares behind this asset.</div>")
    ev = evidence(asset, real)
    where = " or ".join(ev["buildings"]) or "this zone"
    span = (f'{ev["exported_from"]:%d %b} to {ev["exported_to"]:%d %b %Y}' if ev["exported_from"] and ev["exported_to"] else "the export")
    what = "this equipment" if ev["named"] else "this kind of equipment"
    fault_rows = ui.rows([{"left": ui.date_cell(f'{x["reported"]:%d %b}') if x.get("reported") else "",
                           "main": x.get("remarks") or x.get("what") or "", "sub": " · ".join(
                               v for v in (x.get("number"), x.get("trade_category"), x.get("room")) if v)}
                          for x in ev["faults"][:shown]], f"No faults name {what} at {where}.")
    more = len(ev["faults"]) - shown
    faults = ui.panel(f'Faults on {what} at {where}: {len(ev["faults"])}', fault_rows
                      + (f'<div class="u-empty">and {more} more in the fault log.</div>' if more > 0 else ""), note=f"iSMM, {span}")
    spare_rows = ui.rows([{"main": i["item"], "sub": f'Ref. ID {i["ref"] or "not recorded"} · {i["store"]}',
                           "right": ui.pill(STATE_WORD.get(i["state"], STATE_WORD["unknown"])[0],
                                            f'{i["quantity"]:.0f} held' if i.get("quantity") is not None
                                            else STATE_WORD["unknown"][1])}
                          for i in ev["spares"][:shown]], "No matching spares in the store inventories.")
    spares = ui.panel(f'Spares held for this kind of asset: {len(ev["spares"])}', spare_rows,
                      link=("Inventories", "?view=spares"))
    return ui.grid([faults, spares], "1.3fr 1fr")


def evidence(asset: dict, real: dict[str, Any]) -> dict[str, Any]:
    faults = faults_for(asset, (real.get("faults") or {}).get("faults") or [])
    return {"buildings": ZONE_BUILDINGS.get(asset.get("zone_code") or "", ()), "named": asset.get("asset_id") in ASSET_RULES,
            "faults": faults, "spares": spares_for(asset, (real.get("inventory") or {}).get("items") or []),
            "exported_from": (real.get("faults") or {}).get("exported_from"),
            "exported_to": (real.get("faults") or {}).get("exported_to")}
