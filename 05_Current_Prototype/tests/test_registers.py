"""Asset register, fault log and event workbook adapters, and the pages that show them. Fixtures are invented here."""

import shutil
import sys
from datetime import date, datetime, time
from pathlib import Path
from uuid import uuid4

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from demo import asset_catalogue as ac
from demo.sources import ENV_VAR, registers
from site_fixture import FAKE_DB

APP = Path(__file__).resolve().parents[1] / "app.py"


def asset_row(tag, record, kind="Fault", room="Kiosk", day="2023-03-24 11:02:39", **extra):
    return {"Asset Tag Number": tag, "Description": "High Volume Low Speed Fan 1", "System Type": "Mechanical", "Asset Category": "HVLS",
            "Asset Status": "Active", "Site": "Gardens By The Bay (South)", "Building": "Children Garden", "Floor": "Level 1",
            "Room": room, "ID Type": kind, "ID": record, "Building Trade": "Mechanical", "Trade Category": "Fan", "Date": day,
            "Completed": "Yes", **extra}


def fault_row(number, reported="2025-05-01 09:00:00", completed=None, started=None, cancel=None, **extra):
    return {"Fault Number": number, "Trade": "Electrical", "Trade Category": "Lighting", "Type of Fault": "Tripped", "Impact": "Urgent",
            "Site": "Gardens By The Bay (South)", "Building": "Flower Dome", "Floor": "L1", "Room": "Hall", "Cancel Status": cancel,
            "Reported Date": reported, "Work Started Date": started, "Work Completed Date": completed, "Attended By": "Private Person",
            "Reported By": "Another Person", "End User Contact": "91234567", "Remarks": "Lights off &amp;amp; breaker tripped", **extra}


@pytest.fixture
def folder():
    root = APP.parent / "data" / f"test-reg-{uuid4().hex}"
    root.mkdir(parents=True)
    pd.DataFrame([asset_row("FA#1-0", "FID1"), asset_row("FA#1 -0", "SID2", kind="Schedule", room="Cafe"), asset_row("FA#1-0", "FID1"),
                  asset_row("unknown asset number", "FID9"), asset_row("FA#2-0", "FID3", day="not a date")]).to_excel(root / registers.ASSET_FILE, index=False)
    pd.DataFrame([fault_row("FID1", completed="2025-05-01 12:00:00"), fault_row("FID2"), fault_row("FID3", started="2025-05-02 08:00:00"),
                  fault_row("FID4", cancel="approved"), fault_row("FID2"), fault_row("FID5", reported="garbage"),
                  fault_row("FID6", reported="2025-06-02 09:00:00", completed="2025-06-01 09:00:00")]).to_excel(root / registers.FAULT_FILE, index=False)
    header = ["S/N", "Date", "Event Time", "In Charge", "Description of Events", "Location", "Power Requirement", "Power Turn On",
              "AV Equipment", "Kitchen HOTO", "Overtime for Kitchen HOTO", "Documents attachment", "Remarks"]
    def sheet(title, rows):
        return pd.DataFrame([[title] + [None] * 12, header] + rows)
    oct_rows = [[1, "06 Jan 26 - 30 Dec 26", "9am-5pm", "Private Person", "Weekly ceremony", "Ficus Room", "Yes", "No", "Yes", "No", "No", "https://x", None],
                [2, datetime(2026, 10, 21), "1800 to 2200hrs", "Someone", "Evening concert", "Meadow", "Yes", "Yes", "No", "No", "No", None, None],
                [3, "14,15 & 22 Oct 26", "8m-10pm", "Someone", "Market days", "Bayfront Plaza", "No", "No", "No", "No", "No", None, None]]
    nov_rows = [[1, "06 Jan 26 - 30 Dec 26", "9am-5pm", "Private Person", "Weekly ceremony", "Ficus Room", "Yes", "No", "Yes", "No", "No", None, None],
                [2, "31 Febtember", "9am-5pm", "Someone", "Unreadable date", "Meadow", "No", "No", "No", "No", "No", None, None]]
    with pd.ExcelWriter(root / registers.EVENT_FILE) as writer:
        sheet("Event Order for October 2026", oct_rows).to_excel(writer, sheet_name="Oct 26", header=False, index=False)
        sheet("Event Order for November 2026", nov_rows).to_excel(writer, sheet_name="Nov 26", header=False, index=False)
    yield root
    shutil.rmtree(root, ignore_errors=True)


def test_asset_register_groups_records_by_tag_and_reports_problems(folder) -> None:
    data = registers.load_assets(folder)
    tags = {asset["tag"]: asset for asset in data["assets"]}
    assert set(tags) == {"FA#1-0", "FA#2-0"}  # spaces tidied, unknown tag kept out, identical row counted once
    assert len(tags["FA#1-0"]["records"]) == 2 and tags["FA#1-0"]["other_locations"] == ["Children Garden / Cafe"]
    kinds = {item["issue"] for item in data["issues"]}
    assert {"tidied_value", "invalid_value", "duplicate_row"} <= kinds
    rows = ac.register_rows(data["assets"], {"FID1"})
    first = next(row for row in rows if row["asset_id"] == "FA#1-0")
    assert first["category"] == "Fans" and first["linked_faults"] == 1 and first["state"] is None
    assert first["operational"] == first["finding"] == "No readings" and "Unavailable" in first["measurements"]


def test_fault_log_states_and_validation_without_personal_details(folder) -> None:
    data = registers.load_faults(folder)
    by_number = {fault["number"]: fault for fault in data["faults"]}
    assert len(data["faults"]) == 6  # the repeated FID2 is counted once
    assert [by_number[n]["state"] for n in ("FID1", "FID2", "FID3", "FID4")] == ["completed", "open", "in_progress", "cancelled"]
    assert by_number["FID5"]["reported"] is None and by_number["FID1"]["remarks"] == "Lights off & breaker tripped"
    assert {"duplicate_row", "invalid_value", "end_before_start"} <= {item["issue"] for item in data["issues"]}
    assert "Private Person" not in str(data) and "91234567" not in str(data)
    assert data["exported_to"].date() == date(2025, 6, 2)
    assert len(data["gaps"]) == 1 and "coverage_gap" in {item["issue"] for item in data["issues"]}  # 2 May to 2 Jun: a hole, not zero faults


def test_event_dates_and_times_are_parsed_or_reported(folder) -> None:
    assert registers.parse_dates("10, 11, 31 Jan 26 & 01 Feb 26", 2026)["days"] == [date(2026, 1, 10), date(2026, 1, 11), date(2026, 1, 31), date(2026, 2, 1)]
    assert registers.parse_dates("03 Aug - 23 Oct'26", 2026) == {"first": date(2026, 8, 3), "last": date(2026, 10, 23), "days": None}
    assert registers.parse_dates("26 Dec 25-30 Mar 26", 2026)["first"] == date(2025, 12, 26)
    assert registers.parse_dates("13-14 Apl 26", 2026)["days"] == [date(2026, 4, 13), date(2026, 4, 14)]
    assert registers.parse_dates("20/9/2026", 2026)["days"] == [date(2026, 9, 20)]
    assert registers.parse_dates("31 Febtember", 2026) is None
    assert registers.parse_times("7.45pm-11.30pm") == (time(19, 45), time(23, 30)) and registers.parse_times("8am-23:59pm") == (time(8), time(23, 59))
    data = registers.load_events(folder)
    titles = [event["title"] for event in data["events"]]
    assert titles.count("Weekly ceremony") == 1 and len(titles) == 4  # the repeat on the November sheet is counted once
    assert not any("Private Person" in str(event) or "https://" in str(event) for event in data["events"])
    issues = {(item["issue"], item["field"]) for item in data["issues"]}
    assert {("duplicate_row", ""), ("invalid_value", "Date"), ("invalid_value", "Event Time")} <= issues
    week = registers.events_on(data["events"], date(2026, 10, 19), date(2026, 10, 25))
    assert {event["title"] for event in week} == {"Weekly ceremony", "Evening concert", "Market days"}  # 22 Oct is listed
    assert {event["title"] for event in registers.events_on(data["events"], date(2026, 10, 16), date(2026, 10, 18))} == {"Weekly ceremony"}


def test_pages_use_the_files_when_configured_and_say_so_when_not(folder, monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "demo.site_db", FAKE_DB)
    monkeypatch.setenv(ENV_VAR, str(folder))
    faults = AppTest.from_file(str(APP), default_timeout=90)
    faults.query_params["view"] = "fault-log"
    faults.run()
    assert not faults.exception and len(faults.get("plotly_chart")) == 2
    fault_table = next(frame.value for frame in faults.dataframe if "Reported" in frame.value.columns)
    assert "Age" not in fault_table.columns
    calendar = AppTest.from_file(str(APP), default_timeout=90)
    calendar.query_params["view"] = "calendar"
    calendar.run()
    assert not calendar.exception and calendar.button_group(key="calendar_source").value == "Real events"
    assets = AppTest.from_file(str(APP), default_timeout=90)
    assets.query_params["view"] = "assets"
    assets.run()
    assert not assets.exception and ac.REGISTER in set(assets.dataframe[0].value["Source"])
    monkeypatch.delenv(ENV_VAR)
    bare = AppTest.from_file(str(APP), default_timeout=90)
    bare.query_params["view"] = "fault-log"
    bare.run()
    assert not bare.exception and "not configured" in bare.info[0].value


def test_meetings_page_slicers_filter_rows_and_suppress_zero_attendee_label(folder, monkeypatch) -> None:
    from datetime import timedelta

    from demo.sources.ptw_forms import SGT

    today = datetime.now(SGT).date()
    permit_folder = folder / "PTW"
    permit_folder.mkdir()
    permit_headers = ["Permit to Work ID", "Site", "Company", "Trade(s)", "Type", "Start Date", "End Date"]
    permit_rows = [
        ["PTW-1", "South", "Alpha Works", "Electrical", "Hot Work", today, today + timedelta(days=2)],
        ["PTW-2", "East", "Beta Services", "Mechanical", "Other", today, today + timedelta(days=1)],
    ]
    pd.DataFrame([["Permit to Work 2026-10-20 16:02:07"] + [None] * 6, permit_headers, *permit_rows]).to_excel(
        permit_folder / "permits.xlsx", header=False, index=False)
    toolbox_folder = folder / "Tool Box Meeting"
    toolbox_folder.mkdir()
    toolbox_headers = ["Tool Box Meeting ID", "Site", "Company", "Activities", "No. of Attendees", "Conducted Date"]
    toolbox_rows = [
        ["TB-1", "South", "Alpha Works", "Electrical isolation", 4, datetime.combine(today, time(9))],
        ["TB-2", "East", "Beta Services", "Daily safety briefing", 0, datetime.combine(today, time(10))],
    ]
    pd.DataFrame([["Tool Box Meeting 2026-10-20 15:54:40"] + [None] * 5, toolbox_headers, *toolbox_rows]).to_excel(
        toolbox_folder / "meetings.xlsx", header=False, index=False)

    monkeypatch.setenv(ENV_VAR, str(folder))
    at = AppTest.from_file(str(APP), default_timeout=90)
    at.query_params["view"] = "permits"
    at.run()

    assert not at.exception
    assert {widget.label for widget in at.multiselect} == {"Site", "Company", "Activity"}
    assert [widget.label for widget in at.date_input] == ["Meeting date range"]
    assert len(at.dataframe) == 1
    table = at.dataframe[0].value
    assert set(table["Company"]) == {"Alpha Works", "Beta Services"}
    assert table["Date"].str.contains(f"{today:%d %b %Y}").all()
    assert "0 attending" not in "\n".join(item.value for item in at.markdown)
    assert not any("Permit type" == widget.label for widget in at.multiselect)
    assert not any("Permits active today" in item.value for item in at.markdown)

    at.multiselect(key="tb_companies").set_value(["Alpha Works"]).run()
    assert not at.exception
    assert set(at.dataframe[0].value["Company"]) == {"Alpha Works"}


def test_inventory_page_uses_site_and_inventory_labels(folder, monkeypatch) -> None:
    inventory_folder = folder / "Assets"
    inventory_folder.mkdir()
    columns = ["Description", "Category", "Subcategory", "Ref. ID", "Quantity", "Threshold", "Location", "Remarks"]
    row = ["LED lamp", "Electrical", "Lamp", "LED-1", 0, 5, "South Store", ""]
    pd.DataFrame([["Inventories 2026-10-20 15:44:45"] + [None] * (len(columns) - 1), columns, row]).to_excel(
        inventory_folder / "South (Inventory).xlsx", header=False, index=False)
    monkeypatch.setenv(ENV_VAR, str(folder))

    at = AppTest.from_file(str(APP), default_timeout=90)
    at.query_params["view"] = "spares"
    at.run()

    assert not at.exception
    assert at.button(key="nav-spares").label == "Inventories"
    assert {widget.label for widget in at.multiselect} == {"Site", "Category"}
