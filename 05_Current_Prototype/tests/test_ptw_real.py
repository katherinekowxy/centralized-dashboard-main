"""Real permit forms: explicit mapping, validation without silent drops, Power BI location matching, honest map counts.

The workbooks here are small invented fixtures written by the test; no client data is used.
"""

import shutil
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from demo import ptw_real
from demo.sources import ENV_VAR, locations, ptw_forms

APP = Path(__file__).resolve().parents[1] / "app.py"
NOW = datetime(2026, 10, 20, 10, 0, tzinfo=ptw_forms.SGT)
BUILDINGS = [("Flower Dome", 1.2843, 103.8642), ("Cloud Forest", 1.2839, 103.8658), ("GBHQ", 1.2788, 103.8652),
             ("BMS Room", 1.2788, 103.8652), ("Arrival Area", 1.2801, 103.8656), ("Canopy Hub", 1.2824, 103.8608),
             ("Lost Garden", None, None)]


def permit(ref, location, start="2026-10-20", end="2026-10-20", start_time="8:00 AM", end_time="6:00 PM", approval="Approve", **extra):
    return {"Req. Ref.": ref, "Portal": "PERMIT TO WORK (GENERAL) (Approver Person)", "Respondent": "Private Person",
            "Email": "private@example.com", "Company": "Example Works Pte Ltd", "Location": location, "Trade": "Electrical;",
            "Type": "Other : Cable pulling", "Start Date": start, "Start Time": start_time, "End Date": end, "End Time": end_time,
            "Description of Work": "Test work", "Approval Status": approval, **extra}


@pytest.fixture
def folder():
    root = APP.parent / "data" / f"test-gbb-{uuid4().hex}"
    (root / "PERMIT-TO-WORK").mkdir(parents=True)
    pd.DataFrame([{"Building": b, "Latitude": lat, "Longitude": lon, "Verified": "No"} for b, lat, lon in BUILDINGS]).to_excel(
        root / "Building Location.xlsx", sheet_name="Building Location", index=False)
    rows = [permit("GBC/1/PTW00001", "Flower Dome"),
            permit("GBC/1/PTW00002", "GBB - FD", start="2026-10-21", end="2026-10-22"),
            permit("GBC/1/PTW00003", "HQ Office, BMS Room and Arrival shelter", Company="Liang &amp;amp; How Pte Ltd"),
            permit("GBC/1/PTW00004", "18 Marina Gardens Drive, Singapore 018953"),
            permit("GBC/1/PTW00005", "Cloud Forest", start="2026-10-21", end="2026-10-19"),
            permit("GBC/1/PTW00006", "Canopy", start_time="25:99", approval=""),
            permit("GBC/1/PTW00001", "Flower Dome"),
            permit("", "Lost Garden", approval="Maybe")]
    pd.DataFrame(rows).to_excel(root / "PERMIT-TO-WORK" / "PERMIT TO WORK (GENERAL) (Approver) Responses (GBB Central).xlsx", index=False)
    pd.DataFrame([{"Ref": "x"}]).to_excel(root / "PERMIT-TO-WORK" / "broken export (GBB East).xlsx", index=False)
    yield root
    shutil.rmtree(root, ignore_errors=True)


def loaded(folder):
    buildings, problems = locations.load_buildings(folder)
    return ptw_forms.load(folder, locations.Matcher(locations.load_aliases(), buildings)), buildings, problems


def test_power_bi_aliases_and_text_matching() -> None:
    matcher = locations.Matcher(locations.load_aliases(), {name: {} for name, _, _ in BUILDINGS})
    assert matcher.match("Flower Dome") == {"buildings": ["Flower Dome"], "method": "exact", "leftover": []}
    assert matcher.match("GBB - FD")["buildings"] == ["Flower Dome"]  # alias from the report's table
    assert matcher.match("Canopy")["buildings"] == ["Canopy Hub"]
    several = matcher.match("Canopy Hub , Arrival Shelter and HQ Office")
    assert several["method"] == "text" and set(several["buildings"]) == {"Canopy Hub", "Arrival Area", "GBHQ"}
    assert "shelter" in several["leftover"]  # unrecognised words are reported, not hidden
    assert matcher.match("Scented walk &amp;amp; boardwalk")["leftover"]  # double-encoded entities are decoded
    assert matcher.match("71 Ubi Crescent #06-09")["method"] == "none"
    assert matcher.match("")["method"] == "none"


def test_buildings_without_coordinates_are_reported_not_guessed(folder) -> None:
    buildings, problems = locations.load_buildings(folder)
    assert buildings["Lost Garden"]["lat"] is None
    assert any(item["issue"] == "invalid_value" and "Lost Garden" not in item["value"] for item in problems)
    shared = locations.points(buildings)
    assert shared["GBHQ"]["point_id"] == shared["BMS Room"]["point_id"] and shared["GBHQ"]["names"] == ["BMS Room", "GBHQ"]
    assert "Lost Garden" not in shared


def test_forms_are_mapped_explicitly_and_problems_are_reported_not_dropped(folder) -> None:
    permits, _, _ = loaded(folder)
    records = permits["records"]
    assert len(records) == 8  # every non-empty row is kept
    kinds = {item["issue"] for item in permits["issues"]}
    assert {"missing_column", "blank_value", "invalid_value", "end_before_start", "duplicate_row", "unknown_location", "partial_location"} <= kinds
    first = records[0]
    assert first["form"] == "PTW (General)" and first["site"] == "GBB Central" and first["trade"] == "Electrical"
    assert first["start"].hour == 8 and first["end"].hour == 18 and first["start"].tzinfo is ptw_forms.SGT
    assert "Respondent" not in first["source"] and "Email" not in first["source"] and "Portal" not in first["source"]
    assert "Approver Person" not in str(first)
    assert first["source"]["Location"] == "Flower Dome"  # the original value travels with the record
    assert [r["approval"] for r in records if r["ref"] == "GBC/1/PTW00006"] == ["pending"]  # blank = no decision recorded
    assert len(ptw_forms.unique(records)) == 7  # the repeated reference is counted once
    third = next(r for r in records if r["ref"] == "GBC/1/PTW00003")
    assert third["company"] == "Liang & How Pte Ltd" and third["source"]["Company"] == "Liang &amp;amp; How Pte Ltd"


def test_map_counts_permits_once_per_point_and_lists_exceptions(folder) -> None:
    permits, buildings, _ = loaded(folder)
    shown = ptw_real.select(permits["records"], NOW, "All")
    points, unplaced = ptw_real.map_points(shown, locations.points(buildings), NOW)
    hq = next(point for point in points if "GBHQ" in point["names"])
    assert [p["ref"] for p in hq["permits"]].count("GBC/1/PTW00003") == 1  # GBHQ and BMS Room share a coordinate
    assert any("Arrival Area" in point["names"] and point["count"] == 1 for point in points)
    assert {r["ref"] for r in unplaced} >= {"GBC/1/PTW00004", ""}  # unknown address and an unmapped building
    today = ptw_real.select(permits["records"], NOW, "Today")
    assert {r["ref"] for r in today} == {"GBC/1/PTW00001", "GBC/1/PTW00003", "GBC/1/PTW00004", ""}
    # excluded: tomorrow's permit (00002), the inverted window (00005) and the unreadable start time (00006)
    page = ptw_real.map_page(points).lower()
    assert "risk" not in page.replace("not a risk", "") and "distinct permits" in page


def test_page_reads_the_configured_folder_and_says_when_it_is_not_set(folder, monkeypatch) -> None:
    monkeypatch.setenv(ENV_VAR, str(folder))
    at = AppTest.from_file(str(APP), default_timeout=90)
    at.query_params["view"] = "ptw-map"
    at.run()
    assert not at.exception
    markup = "\n".join(item.value for item in at.markdown)
    assert "Imported · not live" in markup and "Not on the map" in markup
    next(control for control in at.button_group if control.key == "rp_period").set_value("All").run()
    assert not at.exception
    assert "<span>Permits</span></div><b>7</b>" in "\n".join(item.value for item in at.markdown)
    monkeypatch.delenv(ENV_VAR)
    bare = AppTest.from_file(str(APP), default_timeout=90)
    bare.query_params["view"] = "ptw-map"
    bare.run()
    assert not bare.exception
    assert next(control for control in bare.button_group if control.key == "ptw_source").value == "Demo site"
