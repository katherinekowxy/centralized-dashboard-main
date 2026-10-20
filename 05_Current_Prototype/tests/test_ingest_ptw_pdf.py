"""PTW PDF ingest: template SD-PTW-1 round trip, every rejection reason, the batch record and re-import rules."""

import hashlib
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import fitz
import pytest

from demo import ingest_ptw_pdf, site_db, site_seed

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "data" / "examples" / "site"
SAMPLE_1, SAMPLE_2 = SAMPLES / "PTW-2026-0901.pdf", SAMPLES / "PTW-2026-0902.pdf"
AS_OF = datetime(2026, 10, 12, 6, 0, tzinfo=timezone.utc)
NOW = AS_OF + timedelta(minutes=7)  # 14:07 SGT
BASE = {"ptw_id": "PTW-2026-0950", "zone_code": "SGV", "contractor_id": "CTR-VRD", "title": "Grove bed replanting",
        "work_type": "landscape", "start_at": "2026-10-20 08:00+08:00", "end_at": "2026-10-20 17:00+08:00",
        "impacts": [("physical", "route", "Grove south path", "restricted", "South path restricted", "-", "-")]}


def _db_file() -> Path:
    return ROOT / "data" / f"test-ingest-{uuid4().hex}.sqlite3"


@pytest.fixture(scope="module")
def seeded():
    """One seeded database for checks that save nothing."""
    path = _db_file()
    try:
        site_seed.build(path, AS_OF)
        yield path
    finally:
        path.unlink(missing_ok=True)


@pytest.fixture()
def db_path():
    path = _db_file()
    try:
        site_seed.build(path, AS_OF)
        yield path
    finally:
        path.unlink(missing_ok=True)


@pytest.fixture()
def pdf_file():
    """Write PDF bytes to a throwaway file under data/ (pytest's tmp_path is off); removed afterwards."""
    made: list[Path] = []

    def write(content: bytes | dict) -> Path:
        path = ROOT / "data" / f"test-ingest-{uuid4().hex}.pdf"
        path.write_bytes(ingest_ptw_pdf.render_pdf(content) if isinstance(content, dict) else content)
        made.append(path)
        return path

    try:
        yield write
    finally:
        for path in made:
            path.unlink(missing_ok=True)


def permit(**changes) -> dict:
    return {**BASE, **changes}


def errors(path: Path, db: Path) -> list[tuple[str, str]]:
    return [(error["field"], error["message"]) for error in ingest_ptw_pdf.preview(path, db)["errors"]]


def query(db, sql, *params) -> list[dict]:
    return site_db._all(sql, params, db)


def pdf_text(path: Path) -> str:
    with fitz.open(path) as doc:
        return "".join(page.get_text() for page in doc)


def test_samples_are_marked_synthetic() -> None:
    for path in (SAMPLE_1, SAMPLE_2):
        assert pdf_text(path).count("SYNTHETIC SAMPLE") == 2  # banner at the top, note at the foot


def test_sample_round_trip(db_path) -> None:
    preview = ingest_ptw_pdf.preview(SAMPLE_1, db_path)
    assert preview["errors"] == [] and preview["status"] == "new"
    assert preview["ptw"] == {"ptw_id": "PTW-2026-0901", "zone_code": "ACT", "contractor_id": "CTR-NWD",
                              "title": "Active Garden outlet replacement", "work_type": "electrical",
                              "start_at": "2026-10-14T01:00:00+00:00", "end_at": "2026-10-14T09:00:00+00:00",
                              "source_file": "data/examples/site/PTW-2026-0901.pdf"}
    assert site_db.ptw("PTW-2026-0901", db_path) is None  # a preview saves nothing

    result = ingest_ptw_pdf.commit(SAMPLE_1, db_path, now=NOW)
    assert result == {"batch_id": "pdf-20261012-001", "ptw_id": "PTW-2026-0901", "saved": 3, "skipped": 0, "impacts": 2,
                      "already_imported": False}
    saved = site_db.ptw("PTW-2026-0901", db_path)
    assert saved["source_file"] == "data/examples/site/PTW-2026-0901.pdf" and saved["ingest_batch_id"] == "pdf-20261012-001"
    assert saved["contractor"]["name"] == "Northwind M&E Pte Ltd" and saved["zone"]["zone_code"] == "ACT"
    assert [(i["impact_id"], i["kind"], i["target_type"], i["target_id"], i["effect"], i["summary"], i["start_at"], i["end_at"])
            for i in saved["impacts"]] == [
        ("PTW-2026-0901/1", "electrical", "asset", "ACT-OUT-01", "isolated", "Outlets isolated",
         "2026-10-14T01:00:00+00:00", "2026-10-14T09:00:00+00:00"),  # "-" takes the permit's window
        ("PTW-2026-0901/2", "physical", "route", "Active Garden east path", "closed", "East path closed",
         "2026-10-14T01:00:00+00:00", "2026-10-14T05:00:00+00:00")]
    assert query(db_path, "SELECT * FROM ingest_batches WHERE batch_id = ?", "pdf-20261012-001") == [
        {"batch_id": "pdf-20261012-001", "source_type": "pdf", "file_name": "PTW-2026-0901.pdf",
         "sha256": hashlib.sha256(SAMPLE_1.read_bytes()).hexdigest(), "received_at": "2026-10-12T06:07:00+00:00",
         "row_count": 3}]
    assert "PTW-2026-0901" in {row["ptw_id"] for row in site_db.ptws(active_at="2026-10-14T03:00:00+00:00", path=db_path)}

    second = ingest_ptw_pdf.commit(SAMPLE_2, db_path, now=NOW)
    assert (second["batch_id"], second["saved"], second["impacts"]) == ("pdf-20261012-002", 2, 1)
    [impact] = site_db.ptw("PTW-2026-0902", db_path)["impacts"]
    assert (impact["kind"], impact["target_type"], impact["target_id"], impact["effect"]) == ("physical", "zone", "MDB", "restricted")


def test_same_file_is_skipped_but_another_file_with_that_number_is_refused(db_path, pdf_file) -> None:
    first = ingest_ptw_pdf.commit(SAMPLE_1, db_path, now=NOW)
    again = ingest_ptw_pdf.commit(SAMPLE_1, db_path, now=NOW + timedelta(hours=1))
    assert (again["batch_id"], again["saved"], again["skipped"], again["already_imported"]) == (first["batch_id"], 0, 3, True)
    assert ingest_ptw_pdf.preview(SAMPLE_1, db_path)["status"] == "already_imported"
    assert len(query(db_path, "SELECT * FROM ingest_batches WHERE source_type = 'pdf'")) == 1

    edited = pdf_file(permit(ptw_id="PTW-2026-0901", zone_code="ACT", title="Active Garden outlet swap"))
    assert ("Permit number", "PTW-2026-0901 already exists (batch pdf-20261012-001); a different file cannot replace it") \
        in errors(edited, db_path)
    with pytest.raises(ingest_ptw_pdf.PtwImportError):
        ingest_ptw_pdf.commit(edited, db_path, now=NOW)
    assert site_db.ptw("PTW-2026-0901", db_path)["title"] == "Active Garden outlet replacement"

    seed_number = pdf_file(permit(ptw_id="PTW-2026-0142"))  # a seed permit: never replaced by a file
    assert any("already exists (batch seed-20261012-001)" in message for _, message in errors(seed_number, db_path))


def test_imported_permit_survives_seed_rebuild(db_path) -> None:
    ingest_ptw_pdf.commit(SAMPLE_1, db_path, now=NOW)
    before = site_db.ptw("PTW-2026-0901", db_path)
    site_seed.build(db_path, AS_OF + timedelta(days=1))
    assert site_db.ptw("PTW-2026-0901", db_path) == before and len(before["impacts"]) == 2
    assert ingest_ptw_pdf.commit(SAMPLE_1, db_path, now=NOW)["already_imported"]


@pytest.mark.parametrize("changes, field, expected", [
    ({"zone_code": None}, "Zone code", "is missing"),
    ({"title": ""}, "Title", "is missing"),
    ({"ptw_id": "PTW-26-0950"}, "Permit number", "'PTW-26-0950' is not in the form PTW-YYYY-NNNN"),
    ({"zone_code": "XYZ"}, "Zone code", "unknown zone 'XYZ'"),
    ({"contractor_id": "CTR-ZZZ"}, "Contractor ID", "unknown contractor 'CTR-ZZZ'"),
    ({"title": "Replant the whole north bed of the grove"}, "Title", "has 8 words; the limit is 6"),
    ({"work_type": "painting"}, "Work type", "'painting' is not one of"),
    ({"start_at": "2026-10-20 08:00"}, "Start", "has no UTC offset"),
    ({"end_at": "20 Oct 2026 17:00"}, "End", "is not an ISO 8601 time"),
    ({"end_at": "2026-10-20 07:00+08:00"}, "End", "must be after Start"),
    ({"impacts": []}, "Affected", "lists no impacts"),
    ({"impacts": [("physical", "asset", "SGV-XXX-99", "closed", "Bed closed", "-", "-")]}, "Affected line 1", "unknown asset 'SGV-XXX-99'"),
    ({"impacts": [("physical", "zone", "ZZZ", "closed", "Zone closed", "-", "-")]}, "Affected line 1", "unknown zone 'ZZZ'"),
    ({"impacts": [("physical", "route", "Grove south path", "closed", "South path closed for the whole day", "-", "-")]},
     "Affected line 1", "summary has 7 words; the limit is 6"),
    ({"impacts": [("physical", "route", "Grove south path", "closed", "-", "-", "-")]}, "Affected line 1", "summary is empty"),
    ({"impacts": [("chemical", "asset", "SGV-DB-01", "isolated", "DB-01 isolated", "-", "-")]}, "Affected line 1", "is not electrical or physical"),
    ({"impacts": [("electrical", "asset", "SGV-DB-01", "closed", "DB-01 closed", "-", "-")]}, "Affected line 1", "effect 'closed' does not fit"),
    ({"impacts": [("electrical", "zone", "SGV", "isolated", "Grove isolated", "-", "-")]}, "Affected line 1", "target type 'zone' does not fit"),
    ({"impacts": [("physical", "route", "Grove south path", "closed", "Path closed", "2026-10-20 07:00+08:00", "-")]},
     "Affected line 1", "must sit inside the permit's Start and End"),
    ({"impacts": [("physical", "route", "Grove south path", "closed", "Path closed", "2026-10-20 12:00+08:00",
                   "2026-10-20 10:00+08:00")]}, "Affected line 1", "impact end must be after its start"),
    ({"impacts": [("physical", "route", "Grove south path", "closed", "Path closed", "2026-10-20 10:00", "-")]},
     "Affected line 1", "impact start '2026-10-20 10:00' has no UTC offset"),
    ({"impacts": ["physical | zone | SGV"]}, "Affected line 1", "has 3 fields; expected 7"),
    ({"impacts": [BASE["impacts"][0], BASE["impacts"][0]]}, "Affected line 2", "the same target is listed twice"),
])
def test_each_rejection_reason(seeded, pdf_file, changes, field, expected) -> None:
    content = permit(**changes)
    content = {key: value for key, value in content.items() if value is not None}  # None: leave the line out
    found = errors(pdf_file(content), seeded)
    assert any(f == field and expected in message for f, message in found), found


def test_valid_test_permit_passes(seeded, pdf_file) -> None:
    preview = ingest_ptw_pdf.preview(pdf_file(BASE), seeded)
    assert preview["errors"] == [] and preview["impacts"][0]["impact_id"] == "PTW-2026-0950/1"


def test_refused_permit_saves_nothing(db_path, pdf_file) -> None:
    bad = pdf_file(permit(zone_code="XYZ"))
    with pytest.raises(ingest_ptw_pdf.PtwImportError) as refused:
        ingest_ptw_pdf.commit(bad, db_path, now=NOW)
    assert refused.value.preview["errors"] == [{"field": "Zone code", "message": "unknown zone 'XYZ'"}]
    assert site_db.ptw("PTW-2026-0950", db_path) is None
    assert not query(db_path, "SELECT * FROM ingest_batches WHERE source_type = 'pdf'")


def _other_pdf(*lines: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    for n, line in enumerate(lines):
        page.insert_text((50, 80 + 16 * n), line, fontsize=10)
    data = doc.tobytes()
    doc.close()
    return data


@pytest.mark.parametrize("make, expected", [
    (lambda: SAMPLE_1.read_bytes()[: len(SAMPLE_1.read_bytes()) // 2], "Not a readable PDF"),        # truncated download
    (lambda: b"%PDF-1.7\n" + bytes(range(256)) * 8, "Not a readable PDF"),                          # corrupted body
    (lambda: b"permit_number,zone\nPTW-2026-0950,SGV\n", "Not a PDF file"),                          # a CSV renamed .pdf
    (lambda: _other_pdf("PERMIT TO WORK", "Permit No. 12345", "Location: Flower Dome"), "Unknown template"),
    (lambda: _other_pdf(), "no text layer"),                                                         # a blank scan
    (lambda: _other_pdf(ingest_ptw_pdf.TEMPLATE_MARK, "Permit number: PTW-2026-0950"), "may be cut off"),
])
def test_corrupt_or_unknown_pdfs_give_a_clear_error(seeded, pdf_file, make, expected) -> None:
    path = pdf_file(make())
    preview = ingest_ptw_pdf.preview(path, seeded)
    assert preview["ptw"] is None and any(expected in error["message"] for error in preview["errors"]), preview["errors"]
    with pytest.raises(ingest_ptw_pdf.PtwImportError):
        ingest_ptw_pdf.commit(path, seeded, now=NOW)
    assert not query(seeded, "SELECT * FROM ingest_batches WHERE source_type = 'pdf'")
