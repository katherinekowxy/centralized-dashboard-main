"""Persistence, mapping and atomic CSV-import behavior."""

from pathlib import Path
from uuid import uuid4

import pytest

from demo.engine import ASSETS
from demo.imports import (
    ImportValidationError, commit_import, create_asset, expected_points,
    list_assets, list_imports, list_readings, preview_csv,
)


FIXTURE = Path(__file__).resolve().parents[1] / "data" / "examples" / "synthetic_vendor_pump.csv"
REF = "VENDOR:CHWP-06"


@pytest.fixture
def db_path():
    """Use a unique file in the workspace; the sandbox cannot enumerate OS temp."""
    db = FIXTURE.parents[1] / f"imports_test_{uuid4().hex}.sqlite3"
    yield db
    db.unlink(missing_ok=True)


def test_sixth_asset_import_persists_and_repeat_is_idempotent(db_path):
    db = db_path
    asset = create_asset("PUMP-06", "Chilled Water Pump 06", "pump", "Energy Centre / Pump Room", db)
    assert asset["asset_id"] == "PUMP-06"
    assert asset["detector_enabled"] is False
    assert {item["asset_id"] for item in list_assets(db)} == {item["asset_id"] for item in ASSETS} | {"PUMP-06"}
    content = FIXTURE.read_bytes()
    preview = preview_csv(content, "PUMP-06", REF, filename=FIXTURE.name, db_path=db)
    assert preview["errors"] == []
    assert len(preview["accepted"]) == 8
    assert preview["duplicates"] == 0
    assert list_readings("PUMP-06", db) == []
    result = commit_import(content, "PUMP-06", REF, filename=FIXTURE.name, db_path=db)
    assert result["saved"] == 8 and result["skipped"] == 0

    # New connections model an application restart.
    assert any(item["asset_id"] == "PUMP-06" for item in list_assets(db))
    readings = list_readings("PUMP-06", db)
    assert len(readings) == 8
    assert {row["point_id"] for row in readings} == set(expected_points("pump"))
    assert {row["observed_at"] for row in readings} == {
        "2026-09-22T23:00:00+00:00", "2026-09-22T23:30:00+00:00"
    }
    assert all(row["asset_id"] == "PUMP-06" and row["asset_ref"] == REF for row in readings)
    assert all(row["source"] == "vendor_csv" and row["source_file"] == FIXTURE.name for row in readings)
    assert {row["source_row"] for row in readings} == set(range(2, 10))
    assert all(row["source_hash"] == result["source_hash"] for row in readings)
    assert len(list_imports("PUMP-06", db)) == 1

    repeated = commit_import(content, "PUMP-06", REF, filename=FIXTURE.name, db_path=db)
    assert repeated["saved"] == 0 and repeated["skipped"] == 8
    assert repeated["import_id"] == result["import_id"]
    assert len(list_readings("PUMP-06", db)) == 8
    assert len(list_imports("PUMP-06", db)) == 1


def test_bad_rows_preview_then_atomic_rejection(db_path):
    db = db_path
    create_asset("PUMP-06", "Pump", "pump", "Plant", db)
    original = FIXTURE.read_text(encoding="utf-8")
    bad = original.replace("54.2,°C", "54.2,F")
    bad = bad.replace("2026-09-23T07:30:00+08:00,vibration_mm_s", "2026-09-23T07:30:00,vibration_mm_s")
    bad = bad.replace(
        "VENDOR:CHWP-06,2026-09-23T07:30:00+08:00,differential_pressure_kpa",
        "OTHER,2026-09-23T07:30:00+08:00,differential_pressure_kpa",
    )
    preview = preview_csv(bad, "PUMP-06", REF, db_path=db)
    assert {item["row"] for item in preview["errors"]} == {3, 8, 9}
    assert len(preview["accepted"]) == 5
    with pytest.raises(ImportValidationError) as caught:
        commit_import(bad, "PUMP-06", REF, db_path=db)
    assert caught.value.preview["errors"] == preview["errors"]
    assert list_readings("PUMP-06", db) == []
    assert list_imports("PUMP-06", db) == []


def test_overlapping_files_skip_same_value_and_reject_conflict(db_path):
    db = db_path
    create_asset("PUMP-06", "Pump", "pump", "Plant", db)
    original = FIXTURE.read_text(encoding="utf-8")
    commit_import(original, "PUMP-06", REF, db_path=db)
    subset = "\n".join(original.splitlines()[:3]) + "\n"
    assert preview_csv(subset, "PUMP-06", REF, db_path=db)["duplicates"] == 2
    result = commit_import(subset, "PUMP-06", REF, db_path=db)
    assert result["saved"] == 0 and result["skipped"] == 2
    assert len(list_readings("PUMP-06", db)) == 8
    conflicting = subset.replace("36.4,A", "40.0,A")
    errors = preview_csv(conflicting, "PUMP-06", REF, db_path=db)["errors"]
    assert errors == [{"row": 2, "message": "Conflicting reading already exists at this asset, point and timestamp"}]
    with pytest.raises(ImportValidationError):
        commit_import(conflicting, "PUMP-06", REF, db_path=db)
    assert len(list_readings("PUMP-06", db)) == 8


def test_asset_ids_and_templates_are_constrained(db_path):
    db = db_path
    with pytest.raises(ValueError):
        create_asset("BMS:CHWP01", "Pump", "pump", "Plant", db)
    with pytest.raises(ValueError):
        create_asset("PUMP-01", "Pump", "pump", "Plant", db)
    with pytest.raises(ValueError):
        create_asset("PLANT-01", "Pump", "pump", "Plant", db)
    with pytest.raises(ValueError):
        create_asset("PUMP-06", "Pump", "unknown", "Plant", db)
    create_asset("PUMP-06", "Pump", "pump", "Plant", db)
    with pytest.raises(ValueError):
        create_asset("PUMP-06", "Another", "pump", "Plant", db)


def test_equipment_reference_has_one_persistent_canonical_owner(db_path):
    db = db_path
    create_asset("PUMP-06", "Pump 06", "pump", "Plant", db)
    create_asset("PUMP-07", "Pump 07", "pump", "Plant", db)
    content = FIXTURE.read_bytes()
    commit_import(content, "PUMP-06", REF, db_path=db)
    conflicting = preview_csv(content, "PUMP-07", REF, db_path=db)
    assert conflicting["errors"] == [{"row": 0, "message": "Equipment reference is already mapped to another asset"}]
    with pytest.raises(ImportValidationError):
        commit_import(content, "PUMP-07", REF, db_path=db)
    assert list_readings("PUMP-07", db) == []
    assert len(list_imports(db_path=db)) == 1

    # Built-in IDs and aliases cannot be routed to a different asset.
    builtin = preview_csv(content, "PUMP-07", "PUMP-01", db_path=db)
    assert builtin["errors"][0]["row"] == 0
    alias = preview_csv(content, "PUMP-07", "BMS:CHWP01", db_path=db)
    assert alias["errors"][0]["row"] == 0


def test_invalid_import_does_not_reserve_vendor_reference(db_path):
    db = db_path
    create_asset("PUMP-06", "Pump 06", "pump", "Plant", db)
    create_asset("PUMP-07", "Pump 07", "pump", "Plant", db)
    content = FIXTURE.read_text(encoding="utf-8")
    bad = content.replace("36.4,A", "36.4,kW")
    with pytest.raises(ImportValidationError):
        commit_import(bad, "PUMP-06", REF, db_path=db)
    assert preview_csv(content, "PUMP-07", REF, db_path=db)["errors"] == []
    result = commit_import(content, "PUMP-07", REF, db_path=db)
    assert result["saved"] == 8
