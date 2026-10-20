"""Evidence integrity and isolation checks for the external research snapshot."""

import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from demo.platform_references import load_platforms


def test_snapshot_covers_reviewed_families_and_has_resolvable_citations():
    records = load_platforms()
    assert {r["id"] for r in records} == {
        "abb", "amazon-monitron", "bently-nevada", "emerson", "ge-vernova",
        "honeywell", "rockwell", "samotics", "schneider", "siemens", "skf",
    }
    assert all(r["checked_on"] == "2026-10-06" for r in records)
    assert all(r["unknowns"] for r in records)
    for record in records:
        assert all(s["accessed"] == record["checked_on"] for s in record["sources"])


def test_dangling_citation_is_rejected(monkeypatch):
    record = load_platforms()[0]
    record["flows"][0]["steps"][0]["source_ids"] = ["missing-evidence"]
    monkeypatch.setattr(Path, "glob", lambda *_: [Path("broken.json")])
    monkeypatch.setattr(Path, "read_text", lambda *_, **__: json.dumps(record))
    with pytest.raises(ValueError, match="uncited infrastructure step"):
        load_platforms(Path("in-memory-test"))


@pytest.mark.parametrize("field,value,error", [
    ("source_ids", ["missing-evidence"], "uncited fusion assessment"),
    ("source_ids", [], "uncited fusion assessment"),
    ("status", "No fusion", "invalid fusion assessment"),
    ("inputs", [], "incomplete fusion evidence"),
    ("limits", "", "incomplete fusion evidence"),
])
def test_fusion_claim_requires_evidence_and_limits(monkeypatch, field, value, error):
    record = load_platforms()[0]
    fusion = {"status": "Documented fusion", "inputs": ["Temperature", "Vibration"],
              "assessment": "Signals assessed together.", "limits": "Vendor description only.",
              "source_ids": [record["sources"][0]["id"]]}
    fusion[field] = value
    record["flows"][0]["evidence_fusion"] = fusion
    monkeypatch.setattr(Path, "glob", lambda *_: [Path("broken.json")])
    monkeypatch.setattr(Path, "read_text", lambda *_, **__: json.dumps(record))
    with pytest.raises(ValueError, match=error):
        load_platforms(Path("in-memory-test"))
