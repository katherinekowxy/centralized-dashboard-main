"""Permits to work (PTWs) from PDF into the site database: one fixed synthetic template, SD-PTW-1.

The real Gardens by the Bay PTW layout is unknown, so this reads only the synthetic template drawn by
``render_pdf`` (docs/site-data-sources.md says what a parser for real permits would need). Text is read with
pdfplumber; scanned permits without a text layer are refused, because this importer does no OCR.

Template SD-PTW-1 (A4, one page, read top to bottom)
    SYNTHETIC SAMPLE banner                      ignored by the parser
    PERMIT TO WORK
    SignalDesk permit-to-work template SD-PTW-1  required: identifies the template
    Permit number:  PTW-YYYY-NNNN
    Zone code:      zone_code from the zones table
    Contractor ID:  contractor_id from the contractors table
    Title:          6 words or fewer
    Work type:      electrical, mechanical, civil, hot_work, height or landscape
    Start:          ISO time with a UTC offset, e.g. 2026-10-14 21:00+08:00
    End:            the same, after Start
    Affected (one line per impact)
    <hint line>                                   ignored
    Kind | Target type | Target ID | Effect | Summary | Start | End
    electrical | asset | SGV-DB-01 | isolated | DB-01 isolated | - | -
    ...one line per impact; Start and End may be "-" (the permit's own window)
    End of permit SD-PTW-1                        required: proves the text was read to the end

Impact rules: ``electrical`` impacts target an ``asset`` and are ``isolated`` or ``down``; ``physical`` impacts target
an ``asset``, ``zone`` or ``route`` (free text) and are ``closed`` or ``restricted``. An asset or zone target must
exist. An impact window must sit inside the permit window. Summaries are 6 words or fewer.

Saving mirrors ``demo/ingest_excel.py``: ``preview`` saves nothing; ``commit`` checks again in one transaction and
refuses the file on any error. A permit number that already exists is refused, unless it came from this very file
(same SHA-256), in which case it is skipped. A saved permit records a batch ``pdf-YYYYMMDD-NNN`` and keeps the PDF's
path in ``source_file``.
"""

from __future__ import annotations

import hashlib
import io
import re
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path
from typing import Any

import pdfplumber

from demo import site_db
from demo.ingest_excel import aware_now, next_batch_id, offset_time

SOURCE_TYPE = "pdf"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
MAX_FILE_BYTES = 10_000_000
TEMPLATE_ID = "SD-PTW-1"
TEMPLATE_MARK = f"SignalDesk permit-to-work template {TEMPLATE_ID}"
FOOTER = f"End of permit {TEMPLATE_ID}"
BANNER = "SYNTHETIC SAMPLE - fictional permit, not a Gardens by the Bay document"
AFFECTED = "Affected (one line per impact)"
AFFECTED_HINT = "Start and End: '-' means the permit's own window. Times need a UTC offset, e.g. +08:00 for SGT."
IMPACT_HEADER = ("Kind", "Target type", "Target ID", "Effect", "Summary", "Start", "End")
FIELDS = (  # permit key, label on the form
    ("ptw_id", "Permit number"), ("zone_code", "Zone code"), ("contractor_id", "Contractor ID"), ("title", "Title"),
    ("work_type", "Work type"), ("start_at", "Start"), ("end_at", "End"),
)
WORK_TYPES = ("electrical", "mechanical", "civil", "hot_work", "height", "landscape")
EFFECTS = {"electrical": ("isolated", "down"), "physical": ("closed", "restricted")}
TARGETS = {"electrical": ("asset",), "physical": ("asset", "zone", "route")}
MAX_WORDS = 6
MAX_ROUTE_CHARS = 60
_PTW_ID = re.compile(r"PTW-\d{4}-\d{4}\Z")
_FIELD = re.compile(r"(?P<label>[A-Za-z ]+?):\s*(?P<value>.*)\Z")


class PtwImportError(ValueError):
    """The permit was refused; ``preview`` holds every error. Nothing was saved."""

    def __init__(self, preview: dict[str, Any]):
        self.preview = preview
        super().__init__(f"PTW import refused with {len(preview['errors'])} error(s); nothing was saved")


# The template, drawn (used by data/examples/site/make_samples.py and the tests)

def render_pdf(permit: dict[str, Any], *, banner: str | None = BANNER) -> bytes:
    """Draw a permit on template SD-PTW-1 and return the PDF bytes. Nothing is validated, so tests can draw bad
    permits: a missing key leaves its line out, and an impact may be a list of fields or one raw text line."""
    import fitz  # PyMuPDF: only needed to make samples, not to import them

    doc = fitz.open()
    page = doc.new_page(width=595, height=842)  # A4 portrait
    left, right, ink, grey = 50, 545, (0.1, 0.1, 0.12), (0.4, 0.4, 0.45)

    def text(y: float, value: str, size: float = 10, font: str = "helv", x: float = left, color=ink) -> None:
        width = right - x
        while size > 5 and fitz.get_text_length(value, fontname=font, fontsize=size) > width:
            size -= 0.25  # shrink a long line rather than let it run off the page
        page.insert_text((x, y), value, fontsize=size, fontname=font, color=color)

    if banner:
        page.draw_rect(fitz.Rect(left - 10, 28, right + 10, 54), color=None, fill=(0.62, 0.11, 0.11))
        text(45, banner, 10, "hebo", left, (1, 1, 1))
    text(86, "PERMIT TO WORK", 16, "hebo")
    text(102, TEMPLATE_MARK, 8, "helv", left, grey)
    y = 130
    page.draw_rect(fitz.Rect(left - 6, y - 14, right + 6, y + 18 * len(FIELDS) - 8), color=(0.75, 0.75, 0.78), width=0.6)
    for key, label in FIELDS:
        if key in permit:
            text(y, f"{label}:", 10, "hebo")
            text(y, str(permit[key]), 10, "helv", 170)
        y += 18
    y += 14
    text(y, AFFECTED, 11, "hebo")
    text(y + 13, AFFECTED_HINT, 7.5, "helv", left, grey)
    y += 32
    text(y, " | ".join(IMPACT_HEADER), 8, "hebo")
    page.draw_line((left, y + 4), (right, y + 4), color=(0.75, 0.75, 0.78), width=0.6)
    for impact in permit.get("impacts", []):
        y += 14
        text(y, impact if isinstance(impact, str) else " | ".join("-" if v in (None, "") else str(v) for v in impact), 8)
    text(y + 26, FOOTER, 8, "helv", left, grey)
    if banner:
        text(812, "SYNTHETIC SAMPLE - made by data/examples/site/make_samples.py for SignalDesk; not a real permit.",
             7.5, "helv", left, grey)
    doc.set_metadata({"title": f"SYNTHETIC SAMPLE {permit.get('ptw_id', 'permit')}", "author": "SignalDesk (synthetic)",
                      "subject": f"Synthetic permit to work, template {TEMPLATE_ID}", "creator": "SignalDesk make_samples.py",
                      "producer": "PyMuPDF", "creationDate": "D:20261012000000Z", "modDate": "D:20261012000000Z"})
    data = doc.tobytes(garbage=3, deflate=True, no_new_id=True)
    doc.close()
    return data


# Reading

def _lines(raw: bytes) -> list[str]:
    with pdfplumber.open(io.BytesIO(raw)) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)
    return [line.strip() for line in text.splitlines() if line.strip()]


def _words(text: str) -> int:
    return len(text.split())


def source_path(path: Path) -> str:
    """The PDF's path as stored in ``source_file``: relative to the prototype folder when inside it."""
    path = path.resolve()
    try:
        return path.relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _parse(lines: list[str]) -> tuple[dict[str, str] | None, list[tuple[int, str]], list[dict[str, str]]]:
    """Template fields (None for an unknown template), numbered impact lines, and layout errors."""
    errors: list[dict[str, str]] = []
    folded = [line.casefold() for line in lines]
    if TEMPLATE_MARK.casefold() not in folded:
        return None, [], [{"field": "Template", "message": f"Unknown template: this importer reads only the SignalDesk "
                                                            f"synthetic permit template {TEMPLATE_ID}"}]
    start = folded.index(TEMPLATE_MARK.casefold()) + 1
    try:
        affected = folded.index(AFFECTED.casefold(), start)
    except ValueError:
        affected = None
        errors.append({"field": "Affected", "message": f"The '{AFFECTED}' section is missing"})
    footer = folded.index(FOOTER.casefold()) if FOOTER.casefold() in folded else None
    if footer is None:
        errors.append({"field": "Template", "message": f"The closing line '{FOOTER}' is missing; the text may be cut off"})

    fields: dict[str, str] = {}
    labels = {label.casefold(): key for key, label in FIELDS}
    for line in lines[start:affected if affected is not None else footer]:
        match = _FIELD.match(line)
        key = labels.get(match["label"].strip().casefold()) if match else None
        if key is None:
            continue  # not a template field (free text is ignored)
        if key in fields:
            errors.append({"field": dict(FIELDS)[key], "message": "appears twice"})
        fields[key] = match["value"].strip()

    impacts: list[tuple[int, str]] = []
    if affected is not None:
        body = lines[affected + 1:footer] if footer is not None and footer > affected else lines[affected + 1:]
        header = [i for i, line in enumerate(body) if [cell.strip().casefold() for cell in line.split("|")]
                  == [name.casefold() for name in IMPACT_HEADER]]
        if not header:
            errors.append({"field": "Affected", "message": "The column line 'Kind | Target type | ... | End' is missing"})
        else:
            impacts = list(enumerate(body[header[0] + 1:], start=1))
    return fields, impacts, errors


def _evaluate(connection: sqlite3.Connection, raw: bytes, path: Path) -> dict[str, Any]:
    result: dict[str, Any] = {"ptw": None, "impacts": [], "errors": [], "sha256": hashlib.sha256(raw).hexdigest(),
                              "file_name": path.name, "source_file": source_path(path), "status": None}
    errors = result["errors"]

    def error(field: str, message: str) -> None:
        errors.append({"field": field, "message": message})

    if len(raw) > MAX_FILE_BYTES:
        error("File", f"The file is larger than {MAX_FILE_BYTES // 1_000_000} MB")
        return result
    if b"%PDF-" not in raw[:1024]:
        error("File", "Not a PDF file")
        return result
    try:
        lines = _lines(raw)
    except Exception as exc:  # pdfplumber wraps pdfminer's syntax and EOF errors; any of them means unreadable
        error("File", f"Not a readable PDF ({exc})")
        return result
    if not lines:
        error("File", "The PDF has no text layer (a scan?); this importer does not do OCR")
        return result
    fields, lines_in, layout = _parse(lines)
    errors.extend(layout)
    if fields is None:
        return result

    for key, label in FIELDS:
        if not fields.get(key):
            error(label, "is missing")
    ptw_id = fields.get("ptw_id", "")
    if ptw_id and not _PTW_ID.match(ptw_id):
        error("Permit number", f"'{ptw_id}' is not in the form PTW-YYYY-NNNN")
    zone = fields.get("zone_code", "")
    zones = {row[0] for row in connection.execute("SELECT zone_code FROM zones")}
    if not zones:
        error("Database", "The site database has no zones yet; build it first (python -m demo.site_seed)")
    elif zone and zone not in zones:
        error("Zone code", f"unknown zone '{zone}'")
    contractor = fields.get("contractor_id", "")
    if contractor and not connection.execute("SELECT 1 FROM contractors WHERE contractor_id = ?", (contractor,)).fetchone():
        error("Contractor ID", f"unknown contractor '{contractor}'")
    title = fields.get("title", "")
    if title and _words(title) > MAX_WORDS:
        error("Title", f"has {_words(title)} words; the limit is {MAX_WORDS}")
    work_type = fields.get("work_type", "")
    if work_type and work_type not in WORK_TYPES:
        error("Work type", f"'{work_type}' is not one of {', '.join(WORK_TYPES)}")
    window: dict[str, datetime] = {}
    for key, label in (("start_at", "Start"), ("end_at", "End")):
        if fields.get(key):
            try:
                window[key] = offset_time(fields[key], label)
            except ValueError as exc:
                error(label, str(exc))
    if len(window) == 2 and window["end_at"] <= window["start_at"]:
        error("End", "must be after Start")

    assets = {row[0] for row in connection.execute("SELECT asset_id FROM assets")}
    if not lines_in and not any(item["field"] == "Affected" for item in errors):
        error("Affected", "lists no impacts; a permit must say what it affects")
    seen: set[tuple[str, str, str]] = set()
    for number, line in lines_in:
        where = f"Affected line {number}"
        cells = [cell.strip() for cell in line.split("|")]
        if len(cells) != len(IMPACT_HEADER):
            error(where, f"has {len(cells)} fields; expected {len(IMPACT_HEADER)} separated by '|' ({line})")
            continue
        kind, target_type, target_id, effect, summary, start, end = cells
        before = len(errors)
        if kind not in EFFECTS:
            error(where, f"kind '{kind}' is not electrical or physical")
        else:
            if effect not in EFFECTS[kind]:
                error(where, f"effect '{effect}' does not fit a {kind} impact; use {' or '.join(EFFECTS[kind])}")
            if target_type not in TARGETS[kind]:
                error(where, f"target type '{target_type}' does not fit a {kind} impact; use {' or '.join(TARGETS[kind])}")
        if not target_id or target_id == "-":
            error(where, "target ID is empty")
        elif target_type == "asset" and target_id not in assets:
            error(where, f"unknown asset '{target_id}'")
        elif target_type == "zone" and target_id not in zones:
            error(where, f"unknown zone '{target_id}'")
        elif target_type == "route" and len(target_id) > MAX_ROUTE_CHARS:
            error(where, f"route name is longer than {MAX_ROUTE_CHARS} characters")
        if not summary or summary == "-":
            error(where, "summary is empty")
        elif _words(summary) > MAX_WORDS:
            error(where, f"summary has {_words(summary)} words; the limit is {MAX_WORDS}")
        own: dict[str, datetime] = {}
        for key, label, value in (("start_at", "start", start), ("end_at", "end", end)):
            if value not in ("", "-"):
                try:
                    own[key] = offset_time(value, f"impact {label}")
                except ValueError as exc:
                    error(where, str(exc))
            elif key in window:
                own[key] = window[key]
        if len(own) == 2 and own["end_at"] <= own["start_at"]:
            error(where, "impact end must be after its start")
        elif len(own) == 2 and len(window) == 2 and (own["start_at"] < window["start_at"] or own["end_at"] > window["end_at"]):
            error(where, "impact window must sit inside the permit's Start and End")
        if (kind, target_type, target_id) in seen:
            error(where, "the same target is listed twice for this kind of impact")
        seen.add((kind, target_type, target_id))
        if len(errors) == before and len(own) == 2:
            result["impacts"].append({"impact_id": f"{ptw_id}/{number}", "ptw_id": ptw_id, "kind": kind,
                                      "target_type": target_type, "target_id": target_id, "effect": effect,
                                      "summary": summary, "start_at": site_db.utc(own["start_at"]),
                                      "end_at": site_db.utc(own["end_at"])})

    if ptw_id and _PTW_ID.match(ptw_id):
        existing = connection.execute("""SELECT p.ingest_batch_id, b.sha256 FROM ptws p
                                         LEFT JOIN ingest_batches b ON b.batch_id = p.ingest_batch_id
                                         WHERE p.ptw_id = ?""", (ptw_id,)).fetchone()
        if existing is not None:
            if existing["sha256"] == result["sha256"]:
                result["status"] = "already_imported"
                result["batch_id"] = existing["ingest_batch_id"]
            else:
                error("Permit number", f"{ptw_id} already exists (batch {existing['ingest_batch_id']}); a different "
                                       "file cannot replace it")
    if not errors:
        result["status"] = result["status"] or "new"
        result["ptw"] = {"ptw_id": ptw_id, "zone_code": zone, "contractor_id": contractor, "title": title,
                         "work_type": work_type, "start_at": site_db.utc(window["start_at"]),
                         "end_at": site_db.utc(window["end_at"]), "source_file": result["source_file"]}
    return result


def preview(pdf_path: Path | str, db_path: Path | str | None = None) -> dict[str, Any]:
    """Check a permit PDF without saving anything.

    Returns ``ptw`` (the permit row, or None when there are errors), ``impacts``, ``errors``
    (``{"field": ..., "message": ...}``), ``sha256``, ``file_name``, ``source_file`` and ``status``
    (``new`` or ``already_imported``; None when refused).
    """
    path = Path(pdf_path)
    raw = path.read_bytes()
    with closing(site_db.connect(db_path)) as connection:
        return _evaluate(connection, raw, path)


def commit(pdf_path: Path | str, db_path: Path | str | None = None, *, now: datetime | None = None) -> dict[str, Any]:
    """Check again and save the permit and its impacts in one transaction, or raise ``PtwImportError``.

    Returns ``batch_id``, ``ptw_id``, ``saved`` and ``skipped`` (rows: the permit plus its impacts), ``impacts``
    (impact count) and ``already_imported``.
    """
    path = Path(pdf_path)
    raw = path.read_bytes()
    now = aware_now(now)
    connection = site_db.connect(db_path)
    try:
        connection.execute("BEGIN IMMEDIATE")
        result = _evaluate(connection, raw, path)
        if result["errors"]:
            raise PtwImportError(result)
        rows = 1 + len(result["impacts"])
        if result["status"] == "already_imported":
            connection.rollback()
            return {"batch_id": result["batch_id"], "ptw_id": result["ptw"]["ptw_id"], "saved": 0, "skipped": rows,
                    "impacts": len(result["impacts"]), "already_imported": True}
        batch_id = next_batch_id(connection, SOURCE_TYPE, now)
        site_db.insert(connection, "ingest_batches", [{"batch_id": batch_id, "source_type": SOURCE_TYPE,
                                                       "file_name": result["file_name"], "sha256": result["sha256"],
                                                       "received_at": site_db.utc(now), "row_count": rows}])
        site_db.insert(connection, "ptws", [{**result["ptw"], "ingest_batch_id": batch_id}])
        site_db.insert(connection, "ptw_impacts", result["impacts"])
        connection.commit()
    except BaseException:
        connection.rollback()
        raise
    finally:
        connection.close()
    return {"batch_id": batch_id, "ptw_id": result["ptw"]["ptw_id"], "saved": rows, "skipped": 0,
            "impacts": len(result["impacts"]), "already_imported": False}


def main(argv: list[str] | None = None) -> int:
    """``python -m demo.ingest_ptw_pdf FILE.pdf [--db PATH] [--commit]``: preview, or save with ``--commit``."""
    import argparse

    parser = argparse.ArgumentParser(description=f"Check a permit PDF (template {TEMPLATE_ID}), and save it with --commit.")
    parser.add_argument("file", help="the permit PDF; keep it where it is, because its path is stored")
    parser.add_argument("--db", help="site database (default data/site.sqlite3)")
    parser.add_argument("--commit", action="store_true", help="save the permit; without it nothing is saved")
    args = parser.parse_args(argv)
    if args.commit:
        try:
            saved = commit(args.file, args.db)
        except PtwImportError as exc:
            result = exc.preview
        else:
            verb = "already imported" if saved["already_imported"] else "saved"
            print(f"{saved['ptw_id']} {verb} with {saved['impacts']} impact(s), batch {saved['batch_id']}")
            return 0
    else:
        result = preview(args.file, args.db)
    if result["ptw"]:
        permit = result["ptw"]
        print(f"{permit['ptw_id']} | {permit['zone_code']} | {permit['contractor_id']} | {permit['title']} | "
              f"{permit['start_at']} to {permit['end_at']} (UTC) | {len(result['impacts'])} impact(s) | {result['status']}")
    for error in result["errors"]:
        print(f"  {error['field']}: {error['message']}")
    if result["errors"]:
        print("Refused: nothing was saved.")
    elif not args.commit:
        print("Preview only; add --commit to save.")
    return 1 if result["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
