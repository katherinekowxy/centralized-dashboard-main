"""Client view: iSMM records are split into faults, service requests and event support once, and every page that shows
a figure uses the same split and window, so the overview tallies with the pages it links to. Fixtures are invented."""

from datetime import date, datetime, timedelta

from demo import overview_v2
from demo.sources import registers
from demo.sources.ptw_forms import SGT

AS_AT = datetime(2026, 10, 20, 15, 0, tzinfo=SGT)


def record(number, trade, category="", kind_of="", state="completed", hours_ago=2, on_site_min=10, building="Flower Dome"):
    reported = AS_AT - timedelta(hours=hours_ago)
    row = {"number": number, "trade": trade, "trade_category": category, "type": kind_of, "building": building, "room": "",
           "reported": reported, "on_site": reported + timedelta(minutes=on_site_min) if on_site_min is not None else None,
           "started": reported if state in ("in_progress", "completed") else None, "completed": reported if state == "completed" else None,
           "cancelled": state == "cancelled", "state": state, "remarks": "", "impact": "Non-Urgent", "site": "Gardens By The Bay (South)"}
    row["kind"] = registers.record_kind(trade)
    row["what"] = registers.describe(row)
    return row


RECORDS = [
    record("F1", "Electrical", "Column Light", "Not Working", state="open"),
    record("F2", "Mechanical", "Pump", "Other: Leaking", state="in_progress", hours_ago=24 * 40, on_site_min=30),
    record("F3", "Building", "Door Lock", "Misaligned", on_site_min=20),
    record("R1", "Request", "Services", "Open/Close Bollard", state="in_progress", on_site_min=2),
    record("R2", "Request", "Services", "Other: Escort", on_site_min=1),
    record("E1", "Events", "Power Handover", "Other: Handover", hours_ago=30),
    record("E2", "Events", "Event Handover/Takeover", "Power handover at FFH", hours_ago=50),
    record("E3", "Events", "AV Handover/Takeover", "AV takeover", hours_ago=10),
]


def data(records=RECORDS):
    return {"faults": {"faults": records, "exported_to": AS_AT}, "permits": {"permits": [], "exported": AS_AT},
            "toolbox": {"meetings": [], "exported": AS_AT}, "inventory": {"items": [], "exported": AS_AT}, "events": {"events": []}}


def test_every_record_is_exactly_one_kind_and_reads_in_plain_words() -> None:
    kinds = [r["kind"] for r in RECORDS]
    assert kinds.count("fault") + kinds.count("request") + kinds.count("event") == len(RECORDS)
    assert (kinds.count("fault"), kinds.count("request"), kinds.count("event")) == (3, 2, 3)
    assert RECORDS[1]["what"] == "Pump · Leaking"  # "Other:" removed, category first
    assert RECORDS[3]["what"] == "Open/Close Bollard"  # generic "Services" category dropped


def test_power_handovers_use_one_rule() -> None:
    assert [r["number"] for r in RECORDS if registers.is_power_job(r)] == ["E1", "E2"]
    assert not registers.is_power_job(record("F9", "Electrical", "Power Supply", "Tripped"))  # a fault, not event support


def test_overview_counts_faults_only_and_splits_today() -> None:
    ctx = overview_v2.real_context(data(), AS_AT)
    f = ctx["faults"]
    assert (f["open"], f["in_progress"], f["over_30"]) == (1, 1, 1)  # requests in progress are not open faults
    assert sum(f["today"].values()) == sum(r["reported"].date() == AS_AT.date() for r in RECORDS)
    assert f["today"]["request"] == 2 and f["week_split"]["event"] == 3
    assert f["median"] == "15 min"  # faults in the last 30 days only (10 and 20 min); requests (1-2 min) are excluded
    assert [x["number"] for x in ctx["power_jobs"]] == ["E1", "E2"]
    html = overview_v2.page_html({"real": ctx, "summary": {}, "now": AS_AT, "today": AS_AT.date()})
    assert ">2</b><small>1 being worked on · 1 open over 30 days" in html
    assert "Data as at: Faults 20 Oct 15:00" in overview_v2.sources_line(ctx)


def test_permit_type_other_reads_as_general() -> None:
    from demo.sources import ismm

    assert ismm.TYPE_WORD["Other"] == "General"
    assert overview_v2.site_short("Gardens By The Bay (East)") == "GBB East"
