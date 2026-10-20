"""iSMM exports with a title row ("Permit to Work 2026-10-20 16:02:07") above the header: permits, tool-box meetings
and store inventories. Read-only, explicit column maps, problems reported rather than dropped.

Permits (``PTW/*.xlsx``): Permit to Work ID*, Site, Company, Trade(s), Type, Start Date*, End Date*, Submitted Date,
Approved Date, Remarks. Not read: Submitted By, Approved By, Portal ID and Portal Name (the approver's name). The
export has no building or location column, so these permits cannot be placed on the map.

Tool-box meetings (``Tool Box Meeting/*.xlsx``): Tool Box Meeting ID*, Site, Company, Activities, No. of Attendees,
Conducted Date*. Not read: Conducted By.

Inventories (``Assets/*.xlsx``, one file per store): Description*, Category, Subcategory, Ref. ID, Quantity, Threshold,
Location, Remarks. A line is "below minimum" when Quantity is below Threshold; a blank or unreadable quantity is
reported, never counted as zero.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path
from typing import Any

from demo.sources import issue
from demo.sources.ptw_forms import SGT, _text, readable

TITLE = re.compile(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}(?::\d{2})?)")
TYPE_WORD = {"Other": "General"}  # iSMM files general permits as "Other"; the raw value is kept as type_raw
SPECIAL_TYPES = ("Height", "Excavation", "Lifting", "Confined Space", "Hot Work", "Tunneling", "Demolition", "Piling")


def read_titled(path: Path) -> tuple[Any, datetime | None]:
    """The table under an iSMM title row, and the export time written in that title."""
    import pandas as pd

    raw = pd.read_excel(path, header=None, dtype=object)
    title = _text(raw.iloc[0, 0]) if len(raw) else ""
    header = next((i for i in range(min(6, len(raw))) if raw.iloc[i].notna().sum() >= 3), 0)
    frame = raw.iloc[header + 1:].copy()
    frame.columns = [_text(column) for column in raw.iloc[header]]
    frame = frame.loc[:, [column for column in frame.columns if column]].dropna(how="all")
    frame.index = frame.index + 1  # Excel row numbers
    stamp = TITLE.search(title)
    exported = datetime.strptime(stamp.group(1)[:16], "%Y-%m-%d %H:%M").replace(tzinfo=SGT) if stamp else None
    return frame, exported


def _when(value: Any) -> datetime | None:
    import pandas as pd

    at = pd.to_datetime(value, errors="coerce")
    return None if pd.isna(at) else at.to_pydatetime().replace(tzinfo=SGT)


def _files(folder: Path, sub: str) -> list[Path]:
    return sorted(path for path in (folder / sub).glob("*.xlsx") if not path.name.startswith("~$")) if (folder / sub).is_dir() else []


def _site(name: str) -> str:
    match = re.search(r"\(([^()]*(?:South|Central|East)[^()]*)\)", name)
    return match.group(1) if match else ""


def load_permits(folder: Path) -> dict[str, Any]:
    files, problems, permits, seen, exported = _files(folder, "PTW"), [], [], set(), []
    if not files:
        problems.append(issue("missing_file", "No permit exports in PTW/", file="PTW"))
    for path in files:
        frame, stamp = read_titled(path)
        exported.append(stamp)
        missing = [c for c in ("Permit to Work ID", "Start Date", "End Date") if c not in frame.columns]
        if missing:
            problems.append(issue("missing_column", f"Required column(s) missing: {', '.join(missing)}; file not used", file=path.name))
            continue
        for row_no, row in frame.iterrows():
            ref = _text(row.get("Permit to Work ID"))
            if not ref:
                problems.append(issue("blank_value", "Permit to Work ID is blank", file=path.name, row=row_no, field="Permit to Work ID"))
                continue
            if ref in seen:
                problems.append(issue("duplicate_row", "Permit repeated; counted once", file=path.name, row=row_no, ref=ref))
                continue
            seen.add(ref)
            start, end = _when(row.get("Start Date")), _when(row.get("End Date"))
            if start is None or end is None:
                problems.append(issue("invalid_value", "Start or end date could not be read", file=path.name, row=row_no, ref=ref))
            elif end < start:
                problems.append(issue("end_before_start", "End before start", file=path.name, row=row_no, ref=ref))
            permits.append({"ref": ref, "site": _text(row.get("Site")) or _site(path.name), "company": readable(_text(row.get("Company"))),
                            "trades": _text(row.get("Trade(s)")), "type": TYPE_WORD.get(_text(row.get("Type")) or "Other", _text(row.get("Type"))),
                            "type_raw": _text(row.get("Type")),
                            "start": start.date() if start else None, "end": end.date() if end else None,
                            "approved": _when(row.get("Approved Date")), "remarks": readable(_text(row.get("Remarks"))),
                            "source_file": path.name, "source_row": row_no})
    return {"permits": permits, "issues": problems, "exported": max([s for s in exported if s], default=None)}


def permits_on(permits: list[dict], first: date, last: date) -> list[dict]:
    return [p for p in permits if p["start"] and p["end"] and p["end"] >= p["start"] and p["start"] <= last and p["end"] >= first]


def load_toolbox(folder: Path) -> dict[str, Any]:
    files, problems, meetings, exported = _files(folder, "Tool Box Meeting"), [], [], []
    if not files:
        problems.append(issue("missing_file", "No tool-box meeting exports", file="Tool Box Meeting"))
    for path in files:
        frame, stamp = read_titled(path)
        exported.append(stamp)
        if "Conducted Date" not in frame.columns:
            problems.append(issue("missing_column", "Conducted Date missing; file not used", file=path.name))
            continue
        for row_no, row in frame.iterrows():
            when = _when(row.get("Conducted Date"))
            if when is None:
                problems.append(issue("invalid_value", "Conducted Date could not be read", file=path.name, row=row_no))
                continue
            attendees = pd_number(row.get("No. of Attendees"))
            meetings.append({"ref": _text(row.get("Tool Box Meeting ID")), "site": _text(row.get("Site")) or _site(path.name),
                             "company": readable(_text(row.get("Company"))), "activity": readable(_text(row.get("Activities"))),
                             "attendees": attendees, "at": when, "source_file": path.name, "source_row": row_no})
    return {"meetings": meetings, "issues": problems, "exported": max([s for s in exported if s], default=None)}


def pd_number(value: Any) -> float | None:
    import pandas as pd

    number = pd.to_numeric(value, errors="coerce")
    return None if pd.isna(number) else float(number)


def load_inventory(folder: Path) -> dict[str, Any]:
    files, problems, items, exported = _files(folder, "Assets"), [], [], []
    if not files:
        problems.append(issue("missing_file", "No inventory exports in Assets/", file="Assets"))
    for path in files:
        frame, stamp = read_titled(path)
        exported.append(stamp)
        if "Description" not in frame.columns:
            problems.append(issue("missing_column", "Description missing; file not used", file=path.name))
            continue
        store = re.sub(r"\s*\(Inventory\)\s*$", "", path.stem).strip()
        for row_no, row in frame.iterrows():
            name = readable(_text(row.get("Description")))
            if not name:
                continue
            quantity, threshold = pd_number(row.get("Quantity")), pd_number(row.get("Threshold"))
            if quantity is None:
                problems.append(issue("invalid_value", "Quantity blank or unreadable; not counted as zero", file=path.name, row=row_no,
                                      field="Quantity", value=row.get("Quantity"), ref=name[:60]))
            items.append({"store": store, "item": name, "category": _text(row.get("Category")) or "Not recorded",
                          "subcategory": _text(row.get("Subcategory")), "ref": _text(row.get("Ref. ID")), "quantity": quantity,
                          "threshold": threshold, "remarks": readable(_text(row.get("Remarks"))), "source_file": path.name,
                          "source_row": row_no})
    for item in items:
        q, t = item["quantity"], item["threshold"]
        item["state"] = ("unknown" if q is None else "out" if q <= 0 else "low" if t is not None and q < t else "ok")
    return {"items": items, "issues": problems, "exported": max([s for s in exported if s], default=None)}
