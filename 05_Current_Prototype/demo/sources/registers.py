"""Asset register, fault log and event orders from the GBB Excel exports: explicit column maps, originals kept,
problems reported rather than dropped. Read-only; nothing is written anywhere.

Asset register (``Asset history.xlsx``): one row per asset and associated record. Columns, all optional except the
tag: Asset Tag Number*, Description, System Type, Asset Category, Asset Status, Site, Building, Floor, Room,
ID Type, ID, Building Trade, Trade Category, Date, Completed. These describe assets and their fault or schedule
records; they carry no sensor readings and no health score, so none is shown.

Fault log (``fault.xlsx``, iSMM export): Fault Number*, Trade, Trade Category, Type of Fault, Impact, Site, Building,
Floor, Room, Cancel Status, Reported Date*, Fault Acknowledged Date, Responded on Site Date, Work Started Date,
Work Completed Date, Remarks. Not read: Attended By, Reported By, End User Name, End User Contact (personal details)
and Action(s) Taken (free text that names staff). "Open" means open when the file was exported.

Event orders (``Description of Events 2026.xlsx``): one sheet per month with a title row above the header. Columns:
Date*, Event Time, Description of Events*, Location, Power Requirement, Power Turn On, AV Equipment, Kitchen HOTO,
Overtime for Kitchen HOTO, Remarks. Not read: In Charge (names) and Documents attachment (SharePoint links). The
same recurring event is repeated on every monthly sheet; repeats are reported and counted once.
"""

from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any

from demo.sources import issue
from demo.sources.ptw_forms import SGT, _text, readable

ASSET_FILE, FAULT_FILE, EVENT_FILE = "Asset history.xlsx", "fault.xlsx", "Description of Events 2026.xlsx"
ASSET_COLUMNS = ("Asset Tag Number", "Description", "System Type", "Asset Category", "Asset Status", "Site", "Building",
                 "Floor", "Room", "ID Type", "ID", "Building Trade", "Trade Category", "Date", "Completed")
FAULT_COLUMNS = ("Fault Number", "Trade", "Trade Category", "Type of Fault", "Impact", "Site", "Building", "Floor", "Room",
                 "Cancel Status", "Reported Date", "Fault Acknowledged Date", "Responded on Site Date", "Work Started Date",
                 "Work Completed Date", "Remarks", "Company")
EVENT_COLUMNS = ("Date", "Event Time", "Description of Events", "Location", "Power Requirement", "Power Turn On",
                 "AV Equipment", "Kitchen HOTO", "Overtime for Kitchen HOTO", "Remarks")
GAP_DAYS = 28  # a site this size reports faults daily; four weeks without one means missing data
NO_TAG = re.compile(r"unknown|^n/?a$|^-+$|^$", re.I)


def _when(value: Any) -> datetime | None:
    import pandas as pd

    at = pd.to_datetime(value, errors="coerce")
    return None if pd.isna(at) else at.to_pydatetime().replace(tzinfo=SGT)


def _missing(frame, columns: tuple[str, ...], required: tuple[str, ...], file: str) -> tuple[list[dict], bool]:
    absent = [column for column in columns if column not in frame.columns]
    problems = [issue("missing_column", f"Optional column missing: {column}", file=file, field=column) for column in absent
                if column not in required]
    fatal = [column for column in required if column not in frame.columns]
    if fatal:
        problems.append(issue("missing_column", f"Required column(s) missing: {', '.join(fatal)}; file not used", file=file))
    return problems, bool(fatal)


def load_assets(folder: Path) -> dict[str, Any]:
    """Assets (one per tag) with their associated records, and the problems found."""
    import pandas as pd

    path = folder / ASSET_FILE
    if not path.is_file():
        return {"assets": [], "issues": [issue("missing_file", f"{ASSET_FILE} not found", file=ASSET_FILE)], "modified": None}
    frame = pd.read_excel(path, dtype=object)
    problems, fatal = _missing(frame, ASSET_COLUMNS, ("Asset Tag Number",), ASSET_FILE)
    assets: dict[str, dict] = {}
    seen_rows: set[tuple] = set()
    if not fatal:
        for index, row in frame.iterrows():
            excel_row = int(index) + 2
            source = {column: _text(row.get(column)) for column in ASSET_COLUMNS if column in frame.columns}
            if not any(source.values()):
                continue
            tag_raw = source["Asset Tag Number"]
            tag = re.sub(r"\s+", "", tag_raw)
            if NO_TAG.search(tag_raw.strip()):
                problems.append(issue("invalid_value", "No usable asset tag; record kept in the report only", file=ASSET_FILE,
                                      row=excel_row, field="Asset Tag Number", value=tag_raw))
                continue
            if tag != tag_raw:
                problems.append(issue("tidied_value", "Spaces removed from the asset tag", file=ASSET_FILE, row=excel_row,
                                      field="Asset Tag Number", value=tag_raw))
            key = tuple(source.values())
            if key in seen_rows:
                problems.append(issue("duplicate_row", "Identical row repeated; counted once", file=ASSET_FILE, row=excel_row, ref=tag))
                continue
            seen_rows.add(key)
            when = _when(row.get("Date"))
            if source.get("Date") and when is None:
                problems.append(issue("invalid_value", "Date could not be read", file=ASSET_FILE, row=excel_row, field="Date",
                                      value=source["Date"], ref=tag))
            asset = assets.setdefault(tag, {"tag": tag, "description": readable(source.get("Description", "")),
                                            "category": source.get("Asset Category", ""), "system": source.get("System Type", ""),
                                            "status": source.get("Asset Status", ""), "site": source.get("Site", ""),
                                            "building": source.get("Building", ""), "floor": source.get("Floor", ""),
                                            "room": source.get("Room", ""), "records": [], "source_rows": []})
            asset["records"].append({"id_type": source.get("ID Type", ""), "id": source.get("ID", ""), "date": when,
                                     "trade": source.get("Building Trade", ""), "trade_category": source.get("Trade Category", ""),
                                     "completed": source.get("Completed", "")})
            asset["source_rows"].append(excel_row)
            asset.setdefault("places", set()).add(f"{source.get('Building', '')} / {source.get('Room', '')}")
    for asset in assets.values():  # the same tag recorded at another building or room is shown, not resolved
        asset["other_locations"] = sorted(asset.pop("places") - {f"{asset['building']} / {asset['room']}"})
    modified = datetime.fromtimestamp(path.stat().st_mtime, SGT)
    return {"assets": list(assets.values()), "issues": problems, "modified": modified}


KIND_WORD = {"fault": "Fault", "request": "Service request", "event": "Event support"}
KIND_PLURAL = {"fault": "faults", "request": "service requests", "event": "event support jobs"}


def record_kind(trade: str) -> str:
    """iSMM's fault log also holds service requests (open a bollard, escort a vendor) and event support (space, AV,
    kitchen and power handovers). They are counted apart so a busy event week never reads as a wave of breakdowns."""
    value = (trade or "").strip().casefold()
    return "request" if value == "request" else "event" if value == "events" else "fault"


def is_power_job(record: dict) -> bool:
    """An event support job about power: its category or its description mentions power (for example "Power Handover", or
    "Event Handover/Takeover" described as "Power handover at FFH"). One rule for every page."""
    return record.get("kind") == "event" and "power" in f"{record.get('trade_category') or ''} {record.get('type') or ''}".casefold()


def describe(fault: dict) -> str:
    """What the record is about in plain words: '<trade category> · <type>', with iSMM's 'Other:' prefix removed."""
    kind_of = re.sub(r"^\s*other\s*:\s*", "", fault.get("type") or "", flags=re.I).strip()
    category = (fault.get("trade_category") or "").strip()
    if category.casefold() in {"services", ""}:
        return kind_of[:1].upper() + kind_of[1:] if kind_of else (fault.get("trade") or "Not recorded")
    return f"{category} · {kind_of}" if kind_of and kind_of.casefold() not in category.casefold() else category


def load_faults(folder: Path, path: Path | None = None) -> dict[str, Any]:
    """Every fault in the iSMM export with its lifecycle times, and the problems found. Cancelled faults are kept.
    ``path`` picks a specific export (the newest ``fault*.xlsx``); otherwise ``fault.xlsx`` in ``folder`` is read."""
    import pandas as pd

    path = path or folder / FAULT_FILE
    FAULT_FILE_NAME = path.name
    if not path.is_file():
        return {"faults": [], "issues": [issue("missing_file", f"{FAULT_FILE_NAME} not found", file=FAULT_FILE_NAME)], "modified": None,
                "exported_to": None, "exported_from": None, "gaps": []}
    frame = pd.read_excel(path, dtype=object, usecols=lambda column: column in FAULT_COLUMNS)
    problems, fatal = _missing(frame, FAULT_COLUMNS, ("Fault Number", "Reported Date"), FAULT_FILE)
    faults, seen = [], set()
    stamps = {}
    for column in ("Reported Date", "Fault Acknowledged Date", "Responded on Site Date", "Work Started Date", "Work Completed Date"):
        if column in frame.columns:  # one vectorised parse per column; the originals stay in the frame for the report
            parsed = pd.to_datetime(frame[column], errors="coerce")
            stamps[column] = [None if pd.isna(at) else at.to_pydatetime().replace(tzinfo=SGT) for at in parsed]
    def stamp(column: str, index: int) -> datetime | None:
        return stamps[column][index] if column in stamps else None
    if not fatal:
        for index, row in enumerate(frame.to_dict("records")):
            excel_row = index + 2
            number = _text(row.get("Fault Number"))
            reported = stamp("Reported Date", index)
            if not number:
                problems.append(issue("blank_value", "Fault Number is blank", file=FAULT_FILE_NAME, row=excel_row, field="Fault Number"))
            elif number in seen:
                problems.append(issue("duplicate_row", "Fault number repeated; counted once", file=FAULT_FILE_NAME, row=excel_row, ref=number))
                continue
            seen.add(number)
            if reported is None:
                problems.append(issue("invalid_value", "Reported Date could not be read; fault left out of trends", file=FAULT_FILE_NAME,
                                      row=excel_row, field="Reported Date", value=row.get("Reported Date"), ref=number))
            completed = stamp("Work Completed Date", index)
            if completed and reported and completed < reported:
                problems.append(issue("end_before_start", "Completed before reported", file=FAULT_FILE_NAME, row=excel_row,
                                      field="Work Completed Date", ref=number))
            cancel = _text(row.get("Cancel Status")).casefold()
            faults.append({"number": number, "trade": _text(row.get("Trade")), "trade_category": _text(row.get("Trade Category")),
                           "type": readable(_text(row.get("Type of Fault"))), "impact": _text(row.get("Impact")) or "Not recorded",
                           "site": _text(row.get("Site")), "building": _text(row.get("Building")) or "Not recorded",
                           "floor": _text(row.get("Floor")), "room": _text(row.get("Room")), "reported": reported,
                           "acknowledged": stamp("Fault Acknowledged Date", index), "on_site": stamp("Responded on Site Date", index),
                           "started": stamp("Work Started Date", index), "completed": completed,
                           "cancelled": cancel == "approved", "cancel_status": cancel,
                           "remarks": readable(_text(row.get("Remarks"))), "company": _text(row.get("Company")),
                           "source_row": excel_row, "source_file": FAULT_FILE_NAME})
    for fault in faults:
        fault["state"] = ("cancelled" if fault["cancelled"] else "completed" if fault["completed"]
                          else "in_progress" if fault["started"] else "open")
        fault["kind"] = record_kind(fault["trade"])
        fault["what"] = describe(fault)
    stamps = sorted(fault["reported"] for fault in faults if fault["reported"])
    gaps = [(a, b) for a, b in zip(stamps, stamps[1:]) if b - a >= timedelta(days=GAP_DAYS)]
    for a, b in gaps:  # a hole in the export, not a quiet period: reported so it is never charted as zero faults
        problems.append(issue("coverage_gap", f"No fault reported between {a:%d %b %Y} and {b:%d %b %Y}; the export appears to be missing this period",
                              file=FAULT_FILE_NAME, field="Reported Date"))
    return {"faults": faults, "issues": problems, "modified": datetime.fromtimestamp(path.stat().st_mtime, SGT),
            "exported_to": stamps[-1] if stamps else None, "exported_from": stamps[0] if stamps else None, "gaps": gaps}


MONTHS = {m: i for i, m in enumerate(("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"), 1)}
MONTHS["apl"] = 4  # a spelling used on the April sheet
DASHES = str.maketrans({"–": "-", "—": "-", "’": "'", "�": "-"})


def _month(word: str) -> int | None:
    return MONTHS.get(word[:3].lower()) if word.isalpha() and len(word) >= 3 else None


def _year(text: str | None, default: int) -> int:
    if not text:
        return default
    value = int(text)
    return value + 2000 if value < 100 else value


def _range(text: str, default_year: int) -> dict | None:
    """'08 Jul 26 - 10 Jul 26', "03 Aug - 23 Oct'26": two dates, each with a month name."""
    halves = re.split(r"\s*-\s*(?=\d{1,2}\s*[A-Za-z]{3})", text)
    if len(halves) != 2:
        return None
    ends = []
    for half in halves:
        match = re.fullmatch(r"\s*(\d{1,2})\s*([A-Za-z]+)\s*(\d{2,4})?\s*", half.replace("'", " "))
        if not match or not _month(match.group(2)):
            return None
        ends.append((int(match.group(1)), _month(match.group(2)), match.group(3)))
    last_year = _year(ends[1][2], default_year)
    first = date(_year(ends[0][2], last_year), ends[0][1], ends[0][0])
    last = date(last_year, ends[1][1], ends[1][0])
    if last < first and not ends[0][2]:
        first = first.replace(year=first.year - 1)
    return {"first": first, "last": last, "days": None} if last >= first else None


def _listed(text: str, default_year: int) -> dict | None:
    """'14,15,21 & 22 Mar 26', '13-14 Apl 26', '9&10 Jun 26', '10, 11, 31 Jan 26 & 01 Feb 26': every listed day."""
    tokens = re.findall(r"\d{1,2}\s*-\s*\d{1,2}|\d+|[A-Za-z]+", text.replace("'", " ").replace(".", ","))
    groups, pending, index = [], [], 0
    while index < len(tokens):
        token = tokens[index]
        if token.isalpha():
            month = _month(token)
            if month is None:
                if token.lower() not in {"and", "to"}:
                    return None
            else:
                year = None
                following = tokens[index + 1] if index + 1 < len(tokens) else ""
                if following.isdigit() and len(following) in (2, 4):  # days come before the month, so this is the year
                    year, index = following, index + 1
                groups.append((pending, month, year))
                pending = []
        else:
            pending.append(token)
        index += 1
    if pending or not groups or not all(numbers for numbers, _, _ in groups):
        return None
    known = next((year for _, _, year in groups if year), None)
    days = []
    for numbers, month, year in groups:
        y = _year(year or known, default_year)
        for item in numbers:
            if "-" in item:
                a, b = (int(x) for x in item.split("-"))
                days += [date(y, month, d) for d in range(a, b + 1)]
            else:
                days.append(date(y, month, int(item)))
    ordered = days == sorted(days)
    days = sorted(set(days))
    return {"first": days[0], "last": days[-1], "days": days, "in_order": ordered}


def parse_dates(value: Any, default_year: int) -> dict | None:
    """When an event runs, from the forms' free text: ``{"first", "last", "days"}``. ``days`` lists each day when the
    text lists days; it is None for a written range, which may cover a year of weekly bookings without saying which
    days. Handles date cells, '20/9/2026' (day first), ranges, and day lists. None when the text cannot be read."""
    if isinstance(value, (datetime, date)):
        day = value.date() if isinstance(value, datetime) else value
        return {"first": day, "last": day, "days": [day]}
    text = _text(value).translate(DASHES)
    if not text:
        return None
    try:
        numeric = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{2,4})", text)
        if numeric:
            day = date(_year(numeric.group(3), default_year), int(numeric.group(2)), int(numeric.group(1)))
            return {"first": day, "last": day, "days": [day]}
        return _range(text, default_year) or _listed(text, default_year)
    except ValueError:
        return None


def parse_times(value: Any) -> tuple[time, time] | None:
    """'9am-5pm', '9:30am-1:30pm', '7.45pm-11.30pm', '1800 to 2200hrs', '530am-930pm'. A clock without am/pm takes
    the other clock's; an hour above 12 is read as 24-hour time whatever suffix follows it."""
    text = _text(value).translate(DASHES).lower().replace("hrs", "").replace(" to ", "-").replace(" ", "")
    pieces = text.split("-")
    if len(pieces) != 2:
        return None
    pattern = re.compile(r"(\d{1,2}?)[:.]?(\d{2})?(am|pm)?")
    a, b = pattern.fullmatch(pieces[0]), pattern.fullmatch(pieces[1])
    if not a or not b or not a.group(1) or not b.group(1):
        return None

    def to_time(match, suffix):
        hour, minute = int(match.group(1)), int(match.group(2) or 0)
        if minute > 59 or hour > 23:
            raise ValueError
        if hour <= 12 and suffix:
            hour = hour % 12 + (12 if suffix == "pm" else 0)
        return time(hour, minute)

    try:
        return to_time(a, a.group(3) or b.group(3)), to_time(b, b.group(3))
    except ValueError:
        return None


def load_events(folder: Path) -> dict[str, Any]:
    """Event orders from every monthly sheet, repeats counted once, with dates and times parsed where possible."""
    import pandas as pd

    path = folder / EVENT_FILE
    if not path.is_file():
        return {"events": [], "issues": [issue("missing_file", f"{EVENT_FILE} not found", file=EVENT_FILE)], "modified": None}
    with pd.ExcelFile(path) as book:  # closed straight away, so the workbook is never left locked for its owner
        sheets = {name: book.parse(name, header=None, dtype=object) for name in book.sheet_names}
    problems, events, seen = [], [], {}
    for sheet, raw in sheets.items():
        header_rows = raw.index[raw.iloc[:, 0].astype(str).str.strip().eq("S/N")]
        if not len(header_rows):
            problems.append(issue("missing_column", "No 'S/N' header row found; sheet not used", file=f"{EVENT_FILE} [{sheet}]"))
            continue
        top = int(header_rows[0])
        body = raw.iloc[top + 1:].copy()
        body.columns = [_text(column) for column in raw.iloc[top]]
        file = f"{EVENT_FILE} [{sheet}]"
        sheet_problems, fatal = _missing(body, EVENT_COLUMNS, ("Date", "Description of Events"), file)
        problems += sheet_problems
        if fatal:
            continue
        title_year = re.search(r"(20\d{2})", _text(raw.iloc[0, 0]))
        default_year = int(title_year.group(1)) if title_year else 2026
        for index, row in body.iterrows():
            excel_row = int(index) + 1
            source = {column: _text(row.get(column)) for column in EVENT_COLUMNS if column in body.columns}
            if not source.get("Description of Events"):
                continue
            title = readable(source["Description of Events"])
            key = (re.sub(r"\W+", " ", title.casefold()).strip(), re.sub(r"\W+", "", source.get("Date", "").casefold()),
                   re.sub(r"\W+", " ", source.get("Location", "").casefold()).strip())
            if key in seen:
                problems.append(issue("duplicate_row", f"Also listed on sheet {seen[key]}; counted once", file=file, row=excel_row, ref=title[:60]))
                continue
            seen[key] = sheet
            days = parse_dates(row.get("Date"), default_year)
            hours = parse_times(row.get("Event Time"))
            if days is None:
                problems.append(issue("invalid_value", "Date could not be read; event listed without a date", file=file, row=excel_row,
                                      field="Date", value=source.get("Date"), ref=title[:60]))
            if days and days.get("in_order") is False:
                problems.append(issue("check_value", "Listed days are not in order (possible typo); read as written", file=file,
                                      row=excel_row, field="Date", value=source.get("Date"), ref=title[:60]))
            if source.get("Event Time") and hours is None:
                problems.append(issue("invalid_value", "Event time could not be read; whole days used", file=file, row=excel_row,
                                      field="Event Time", value=source.get("Event Time"), ref=title[:60]))
            yes = lambda column: _text(source.get(column)).strip().casefold() in {"yes", "y"}
            events.append({"title": title, "location": readable(source.get("Location", "")), "date_text": source.get("Date", ""),
                           "time_text": source.get("Event Time", ""), "first_day": days["first"] if days else None,
                           "last_day": days["last"] if days else None, "days": days["days"] if days else None, "start_time": hours[0] if hours else None,
                           "end_time": hours[1] if hours else None, "power": yes("Power Requirement"), "power_on": yes("Power Turn On"),
                           "av": yes("AV Equipment"), "kitchen": yes("Kitchen HOTO"), "sheet": sheet, "source_row": excel_row,
                           "source": source})
    return {"events": events, "issues": problems, "modified": datetime.fromtimestamp(path.stat().st_mtime, SGT)}


def events_on(events: list[dict], first: date, last: date) -> list[dict]:
    """Events on any day in [first, last]: a listed day inside it, or a written range that overlaps it. Long ranges
    (such as a year of weekly bookings) are included because the forms do not say which days inside them are used."""
    return [event for event in events if event["first_day"] and (
        any(first <= day <= last for day in event["days"]) if event["days"] is not None
        else event["first_day"] <= last and event["last_day"] >= first)]


SCHEDULE_FILE = "PTW.xlsx"
SCHEDULE_COLUMNS = ("Schedule ID", "Trade", "Trade Category", "Strategic Partner", "Frequency", "Description", "Scope", "Site",
                    "Building", "Floor", "Room", "Start Date", "End Date", "Exclude", "Work Started Date", "Work Completed Date",
                    "Cancel Approved Date")
TIME_PREFIX = re.compile(r"^\s*\[([^\]]*)\]\s*")


def load_schedules(folder: Path) -> dict[str, Any]:
    """iSMM contractor-work schedules (``PTW.xlsx``): what is planned where and when. Columns read are SCHEDULE_COLUMNS
    (Schedule ID, Start Date and End Date required). Not read: who started, attended, acknowledged or cancelled work.
    The time window written at the start of a description ("[9am - 6pm] ...") is split out as the time text."""
    import pandas as pd

    path = folder / SCHEDULE_FILE
    if not path.is_file():
        return {"schedules": [], "issues": [issue("missing_file", f"{SCHEDULE_FILE} not found", file=SCHEDULE_FILE)], "modified": None}
    frame = pd.read_excel(path, dtype=object, usecols=lambda column: column in SCHEDULE_COLUMNS)
    problems, fatal = _missing(frame, SCHEDULE_COLUMNS, ("Schedule ID", "Start Date", "End Date"), SCHEDULE_FILE)
    schedules, seen = [], set()
    if not fatal:
        for index, row in enumerate(frame.to_dict("records")):
            excel_row = index + 2
            sid = _text(row.get("Schedule ID"))
            if not sid:
                problems.append(issue("blank_value", "Schedule ID is blank", file=SCHEDULE_FILE, row=excel_row, field="Schedule ID"))
            elif sid in seen:
                problems.append(issue("duplicate_row", "Schedule repeated; counted once", file=SCHEDULE_FILE, row=excel_row, ref=sid))
                continue
            seen.add(sid)
            start, end = _when(row.get("Start Date")), _when(row.get("End Date"))
            if start is None or end is None:
                problems.append(issue("invalid_value", "Start or end date could not be read", file=SCHEDULE_FILE, row=excel_row,
                                      field="Start Date/End Date", ref=sid))
            elif end < start:
                problems.append(issue("end_before_start", "End before start", file=SCHEDULE_FILE, row=excel_row, field="End Date", ref=sid))
            text = readable(_text(row.get("Description")))
            match = TIME_PREFIX.match(text)
            state = ("cancelled" if _when(row.get("Cancel Approved Date")) else "completed" if _when(row.get("Work Completed Date"))
                     else "started" if _when(row.get("Work Started Date")) else "scheduled")
            schedules.append({"id": sid, "trade": _text(row.get("Trade")), "category": _text(row.get("Trade Category")),
                              "company": _text(row.get("Strategic Partner")), "frequency": _text(row.get("Frequency")),
                              "title": TIME_PREFIX.sub("", text) if match else text, "time_text": match.group(1).strip() if match else "",
                              "scope": _text(row.get("Scope")), "site": _text(row.get("Site")), "building": _text(row.get("Building")),
                              "room": _text(row.get("Room")), "start": start.date() if start else None, "end": end.date() if end else None,
                              "excluded_days": _text(row.get("Exclude")), "state": state, "source_row": excel_row})
    return {"schedules": schedules, "issues": problems, "modified": datetime.fromtimestamp(path.stat().st_mtime, SGT)}


def schedules_on(schedules: list[dict], first: date, last: date) -> list[dict]:
    """Schedules whose window overlaps [first, last], leaving out cancelled ones. The export's Exclude column is not
    applied: on the one weekly schedule it names the same weekdays the event workbook says the event runs, so its
    meaning is unclear. Pages show its text instead of guessing."""
    return [item for item in schedules if item["state"] != "cancelled" and item["start"] and item["end"]
            and item["start"] <= last and item["end"] >= first]
