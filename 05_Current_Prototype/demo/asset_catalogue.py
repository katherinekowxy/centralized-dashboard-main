"""Asset overview: every asset from every source in one filterable list, without merging their data models.

Sources stay separate and labelled:
- Site operations (demo/site_db.py): operational state from electrical readings (Operational, Idle, Warning, Down,
  Offline), or "Not monitored" for registered assets with no readings. No detector runs on these assets.
- Diagnostics replay (demo/engine.py and demo/imports.py): rule-based diagnostic findings for five demonstration
  assets plus any registered through Data import. The replay reports no operational state.

So each row has two status columns, and a source that does not report one shows why the cell is empty instead of a
borrowed value. Categories are a display grouping of each source's own asset type; the original type is kept.
"""

from __future__ import annotations

from typing import Any

from demo.asset_state import LABEL

CATEGORIES = ("Chillers", "Air handling units", "Distribution boards", "Pumps", "Fans", "Lifts", "Lighting", "Outlets",
              "Misting", "Event power")
SITE_TYPE = {"CHL": "Chillers", "AHU": "Air handling units", "DB": "Distribution boards", "PMP": "Pumps", "FTN": "Pumps",
             "LFT": "Lifts", "LGT": "Lighting", "OUT": "Outlets", "MST": "Misting", "OGB": "Event power", "CEE": "Event power"}
REPLAY_TYPE = {"chiller": "Chillers", "ahu": "Air handling units", "distribution_board": "Distribution boards",
               "pump": "Pumps", "fan": "Fans"}
SITE, REPLAY = "Site operations", "Diagnostics replay"
SITE_POINTS = "Voltage, current, power, power factor, energy"
NOT_REPORTED = {SITE: "No detector on site data", REPLAY: "Not reported by the replay"}
FINDING_WORD = {"alert": "Detector finding", "ok": "Checked, no finding", "idle": "Not assessed"}


def category(source: str, asset_type: str) -> str:
    table = SITE_TYPE if source == SITE else REPLAY_TYPE
    return table.get(str(asset_type), "Other")


def site_rows(db: Any) -> list[dict]:
    """Every asset in the site register: monitored ones with their operational state, the rest as not monitored."""
    from demo.asset_dashboard import board, reason_for

    data = board(db, include_event_power=True)
    zones = data["zones"]
    seen = set()
    rows = []
    for row in data["rows"]:
        seen.add(row["asset_id"])
        rows.append({"source": SITE, "asset_id": row["asset_id"], "name": row.get("name") or row["asset_id"],
                     "category": category(SITE, row.get("asset_type")), "type": row.get("asset_type"),
                     "location": (zones.get(row.get("zone_code")) or {}).get("name") or row.get("zone_code") or "",
                     "state": row["state"], "operational": LABEL[row["state"]],
                     "reason": reason_for(row) if row["state"] in ("down", "warning", "offline") else "",
                     "finding": NOT_REPORTED[SITE], "finding_key": None, "measurements": SITE_POINTS,
                     "work": "Maintenance or permit today" if row.get("maintenance") else "", "criticality": row.get("criticality") or "",
                     "href": f"?asset={row['asset_id']}"})
    for asset in db.assets():
        if asset["asset_id"] in seen:
            continue
        rows.append({"source": SITE, "asset_id": asset["asset_id"], "name": asset.get("name") or asset["asset_id"],
                     "category": category(SITE, asset.get("asset_type")), "type": asset.get("asset_type"),
                     "location": (zones.get(asset.get("zone_code")) or {}).get("name") or asset.get("zone_code") or "",
                     "state": "unmonitored", "operational": "Not monitored", "reason": "In the register; no readings received",
                     "finding": NOT_REPORTED[SITE], "finding_key": None, "measurements": "None",
                     "work": "", "criticality": asset.get("criticality") or "", "href": f"?asset={asset['asset_id']}"})
    return rows


def replay_row(asset: dict, status: str, headline: str, points: list[str], open_jobs: int, freshness: str) -> dict:
    """One diagnostics-replay asset, from values the workbench already computes (demo.signals.asset_status)."""
    return {"source": REPLAY, "asset_id": asset["asset_id"], "name": asset.get("name") or asset["asset_id"],
            "category": category(REPLAY, asset.get("asset_type")), "type": asset.get("asset_type"),
            "location": asset.get("location") or "", "state": None, "operational": NOT_REPORTED[REPLAY], "reason": headline,
            "finding": FINDING_WORD.get(status, status), "finding_key": status,
            "measurements": ", ".join(points) if points else "None", "work": f"{open_jobs} open work order{'s' if open_jobs != 1 else ''}" if open_jobs else "",
            "criticality": asset.get("criticality") or "", "feed": freshness, "href": None}


def needs_attention(row: dict) -> bool:
    """A problem in the row's own terms: a problem operational state (site) or a detector finding (replay)."""
    return row["state"] in ("down", "warning", "offline") or row["finding_key"] == "alert"


def select(rows: list[dict], categories: list[str] | None = None, sources: list[str] | None = None,
           attention_only: bool = False, text: str = "") -> list[dict]:
    needle = text.casefold().strip()
    out = [row for row in rows
           if (not categories or row["category"] in categories) and (not sources or row["source"] in sources)
           and (not attention_only or needs_attention(row))
           and (not needle or needle in f"{row['asset_id']} {row['name']} {row['location']}".casefold())]
    order = {"down": 0, "warning": 1, "offline": 2}
    return sorted(out, key=lambda row: (0 if needs_attention(row) else 1, order.get(row["state"], 3),
                                        CATEGORIES.index(row["category"]) if row["category"] in CATEGORIES else 99, row["asset_id"]))


def category_counts(rows: list[dict]) -> list[dict]:
    """Per category present: total, by source, and how many need attention in their own terms."""
    present = [name for name in (*CATEGORIES, "Other") if any(row["category"] == name for row in rows)]
    return [{"category": name, "total": sum(row["category"] == name for row in rows),
             "site": sum(row["category"] == name and row["source"] == SITE for row in rows),
             "replay": sum(row["category"] == name and row["source"] == REPLAY for row in rows),
             "attention": sum(row["category"] == name and needs_attention(row) for row in rows)} for name in present]
