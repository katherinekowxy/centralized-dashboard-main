"""Permit-to-work form responses (Excel exports in ``PERMIT-TO-WORK/``), mapped explicitly and validated.

Column mapping (source column -> field). Only these columns are read. Respondent names, e-mail addresses, phone
numbers, personnel and worker names, signatures and the approver's name in the form title are personal details and
are deliberately not read, shown or stored. ``Portal`` names the approver, so only the form type is kept from it.
Source file names also carry the approver's first name; they are kept because they are the provenance a person needs
to find the original row.

=============================================================  ==============  =========
Source column                                                  Field           Required
=============================================================  ==============  =========
Req. Ref.                                                      ref             yes
Portal                                                         form            no (approver name removed)
Created Date                                                   submitted_at    no
Company                                                        company         no
Location                                                       location_raw    yes
Trade                                                          trade           no
Type                                                           work_type       no
Start Date + Start Time                                        start           yes
End Date + End Time                                            end             yes
Description of Work                                            description     no
Please tick on the Relevant Job (Permit Required)              permit_jobs     no (general forms only)
Approval Status                                                approval        no (blank = no decision recorded)
(file name) "(GBB Central)" etc.                               site            no
=============================================================  ==============  =========

Times are local Singapore time in the forms. Every record keeps its original text (``source``), file and Excel row.
Rows are never dropped: problems are reported, and a row whose window or location cannot be used is listed as an
exception rather than drawn. A reference that appears more than once is reported and counted once.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from demo.sources import issue
from demo.sources.locations import Matcher

FOLDER = "PERMIT-TO-WORK"
SGT = timezone(timedelta(hours=8), "SGT")
COLUMNS = {
    "Req. Ref.": "ref", "Portal": "form", "Created Date": "submitted_at", "Company": "company", "Location": "location_raw",
    "Trade": "trade", "Type": "work_type", "Start Date": "start_date", "Start Time": "start_time", "End Date": "end_date",
    "End Time": "end_time", "Description of Work": "description",
    "Please tick on the Relevant Job (Permit Required)": "permit_jobs", "Approval Status": "approval_raw",
}
REQUIRED = ("Req. Ref.", "Location", "Start Date", "End Date")
APPROVAL = {"approve": "approved", "approved": "approved", "reject": "rejected", "rejected": "rejected"}
SITE = re.compile(r"\((GBB [A-Za-z]+)\)")


def _text(value: Any) -> str:
    import pandas as pd

    if value is None or (not isinstance(value, str) and pd.isna(value)):
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def readable(value: str) -> str:
    """Display text: HTML entities decoded (the exports double-encode "&" as "&amp;amp;"). Originals stay in ``source``."""
    import html

    for _ in range(3):
        value = html.unescape(value)
    return value


def form_name(portal: str) -> str:
    """The form type without the approver's name in brackets."""
    name = re.sub(r"\s*\([^()]*\)\s*$", "", portal).strip()
    return name.replace("PERMIT-TO-WORK", "PTW").replace("PERMIT TO WORK", "PTW").title().replace("Ptw", "PTW") or "PTW"


def _moment(date: Any, clock: str) -> datetime | None:
    """Date cell plus an optional '9:00 AM' style time, as an aware SGT datetime; None when unreadable."""
    import pandas as pd

    day = pd.to_datetime(date, errors="coerce")
    if pd.isna(day):
        return None
    at = day.to_pydatetime().replace(tzinfo=None)
    if clock:
        parsed = None
        for fmt in ("%I:%M %p", "%H:%M", "%H:%M:%S", "%I %p"):
            try:
                parsed = datetime.strptime(clock.upper(), fmt)
                break
            except ValueError:
                continue
        if parsed is None:
            return None
        at = at.replace(hour=parsed.hour, minute=parsed.minute, second=0)
    return at.replace(tzinfo=SGT)


def load(folder: Path, matcher: Matcher) -> dict[str, Any]:
    """Every permit in the export folder, with its matched buildings, and a validation report."""
    import pandas as pd

    source_dir = folder / FOLDER
    files = sorted(source_dir.glob("*.xlsx")) if source_dir.is_dir() else []
    records: list[dict] = []
    problems: list[dict] = []
    if not files:
        problems.append(issue("missing_file", f"No .xlsx files in {FOLDER}/", file=FOLDER))
    seen: dict[str, dict] = {}
    for path in files:
        try:
            frame = pd.read_excel(path, dtype=object)
        except Exception as exc:  # an unreadable workbook is reported, never fatal
            problems.append(issue("unreadable_file", f"Could not read: {exc}", file=path.name))
            continue
        absent = [column for column in REQUIRED if column not in frame.columns]
        if absent:
            problems.append(issue("missing_column", f"Required column(s) missing: {', '.join(absent)}; file skipped", file=path.name))
            continue
        site = (SITE.search(path.name).group(1) if SITE.search(path.name) else "")
        for index, row in frame.iterrows():
            excel_row = int(index) + 2
            source = {column: _text(row.get(column)) for column in COLUMNS if column in frame.columns and column != "Portal"}
            ref = source.get("Req. Ref.", "")
            if not any(source.values()):
                continue  # an empty spreadsheet row carries nothing to report
            record = {"ref": ref, "form": form_name(_text(row.get("Portal"))), "company": readable(source.get("Company", "")),
                      "location_raw": readable(source.get("Location", "")), "trade": source.get("Trade", "").rstrip(";").replace(";", ", "),
                      "work_type": re.sub(r"^Other\s*:\s*", "", source.get("Type", "")), "description": readable(source.get("Description of Work", "")),
                      "permit_jobs": source.get("Please tick on the Relevant Job (Permit Required)", "").rstrip(";").replace(";", ", "),
                      "site": site, "source_file": path.name, "source_row": excel_row, "source": source, "issues": []}
            for column in REQUIRED:
                if not source.get(column):
                    record["issues"].append(issue("blank_value", f"{column} is blank", file=path.name, row=excel_row, field=column, ref=ref))
            record["start"] = _moment(row.get("Start Date"), source.get("Start Time", ""))
            record["end"] = _moment(row.get("End Date"), source.get("End Time", ""))
            for field, column in (("start", "Start Date"), ("end", "End Date")):
                if source.get(column) and record[field] is None:
                    record["issues"].append(issue("invalid_value", f"{column} or its time could not be read", file=path.name,
                                                  row=excel_row, field=column, value=f"{source.get(column)} {source.get(column.replace('Date', 'Time'), '')}", ref=ref))
            if record["start"] and record["end"] and record["end"] < record["start"]:
                record["issues"].append(issue("end_before_start", "End is before start; the window cannot be used", file=path.name,
                                              row=excel_row, field="End Date", value=f"{record['start']:%d %b %Y %H:%M} → {record['end']:%d %b %Y %H:%M}", ref=ref))
            raw_approval = source.get("Approval Status", "")
            record["approval"] = APPROVAL.get(raw_approval.casefold(), "pending" if not raw_approval else "unrecognised")
            if record["approval"] == "unrecognised":
                record["issues"].append(issue("invalid_value", "Approval status not recognised; treated as no decision",
                                              file=path.name, row=excel_row, field="Approval Status", value=raw_approval, ref=ref))
                record["approval"] = "pending"
            match = matcher.match(record["location_raw"])
            record.update(buildings=match["buildings"], match=match["method"], leftover=match["leftover"])
            if record["location_raw"] and match["method"] == "none":
                record["issues"].append(issue("unknown_location", "No known building in the location text", file=path.name,
                                              row=excel_row, field="Location", value=record["location_raw"], ref=ref))
            elif match["leftover"]:
                record["issues"].append(issue("partial_location", "Part of the location text was not recognised: " + "; ".join(match["leftover"]),
                                              file=path.name, row=excel_row, field="Location", value=record["location_raw"], ref=ref))
            record["usable_window"] = bool(record["start"] and record["end"] and record["end"] >= record["start"])
            if ref and ref in seen:
                record["duplicate_of"] = f"{seen[ref]['source_file']} row {seen[ref]['source_row']}"
                record["issues"].append(issue("duplicate_row", f"Reference already read from {record['duplicate_of']}; counted once",
                                              file=path.name, row=excel_row, field="Req. Ref.", value=ref, ref=ref))
            elif ref:
                seen[ref] = record
            records.append(record)
    for record in records:
        problems.extend(record["issues"])
    modified = max((datetime.fromtimestamp(path.stat().st_mtime, SGT) for path in files), default=None)
    return {"records": records, "issues": problems, "files": [path.name for path in files], "modified": modified}


def timing(record: dict, now: datetime) -> str:
    """'active', 'later' or 'ended' relative to ``now`` (brand.PTW_TIMING), or '' when the window is unusable."""
    if not record["usable_window"]:
        return ""
    if record["end"] < now:
        return "ended"
    return "active" if record["start"] <= now else "later"


def unique(records: list[dict]) -> list[dict]:
    """One record per reference: duplicates are reported in the validation list but counted once."""
    return [record for record in records if not record.get("duplicate_of")]
