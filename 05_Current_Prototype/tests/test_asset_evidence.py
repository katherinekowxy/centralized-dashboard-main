"""Real records behind a demo asset: faults in its building for its kind of equipment, and spares held for it.
The records here are invented; no client data is used."""

from datetime import datetime

from demo import site_seed
from demo.sources import asset_evidence as ae

FAULTS = [
    {"number": "F1", "building": "Flower Dome", "trade_category": "Miniature Circuit Breaker", "remarks": "CD -AHU-07 Trip alarm",
     "kind": "fault", "reported": datetime(2026, 8, 7)},
    {"number": "F2", "building": "Flower Dome", "trade_category": "Pump", "remarks": "FD flower field area - to check water pump",
     "kind": "fault", "reported": datetime(2026, 9, 25)},
    {"number": "F3", "building": "Heritage Gardens", "trade_category": "LED Lights", "remarks": "Chinese garden arch light not working",
     "kind": "fault", "reported": datetime(2026, 9, 20)},
    {"number": "F4", "building": "Meadow", "trade_category": "Power Handover", "remarks": "Power handover at meadow carpark",
     "kind": "event", "reported": datetime(2026, 10, 15)},
    {"number": "F5", "building": "Cloud Forest", "trade_category": "Pump", "remarks": "Waterfall pump not working",
     "kind": "request", "reported": datetime(2026, 10, 1)},
]
ITEMS = [{"item": "MCB 16 AMP", "subcategory": "Circuit Breaker", "ref": "GB-E-0099", "store": "South", "quantity": 7.0, "state": "ok"},
         {"item": "JET PUMP", "subcategory": "Pump", "ref": "IFM-AH-110", "store": "AH10", "quantity": 0.0, "state": "out"}]


def test_a_named_asset_counts_only_remarks_that_name_it() -> None:
    assert [f["number"] for f in ae.faults_for({"asset_id": "FDM-AHU-01", "zone_code": "FDM", "asset_type": "AHU"}, FAULTS)] == ["F1"]
    assert [f["number"] for f in ae.faults_for({"asset_id": "FDM-PMP-01", "zone_code": "FDM", "asset_type": "PMP"}, FAULTS)] == ["F2"]
    assert not ae.faults_for({"asset_id": "HER-PMP-01", "zone_code": "HER", "asset_type": "PMP"}, FAULTS)  # a light, not the pump


def test_a_db_is_shown_by_breaker_faults_and_only_jobs_that_are_faults_count() -> None:
    assert [f["number"] for f in ae.faults_for({"asset_id": "FDM-DB-01", "zone_code": "FDM", "asset_type": "DB"}, FAULTS)] == ["F1"]
    assert not ae.faults_for({"asset_id": "CFR-PMP-01", "zone_code": "CFR", "asset_type": "PMP"}, FAULTS)  # a service request
    assert ae.faults_for({"asset_id": "MDW-OGB-02", "zone_code": "MDW", "asset_type": "OGB"}, FAULTS)  # event power handovers count


def test_spares_are_matched_by_kind_out_of_stock_first() -> None:
    assert [i["ref"] for i in ae.spares_for({"asset_type": "PMP"}, ITEMS)] == ["IFM-AH-110"]
    assert [i["ref"] for i in ae.spares_for({"asset_type": "DB"}, ITEMS)] == ["GB-E-0099"]


def test_every_named_rule_belongs_to_a_seeded_asset() -> None:
    seeded = {row[0] for row in site_seed.ASSETS} | {row[0] for row in site_seed.OG_BOXES}
    assert set(ae.ASSET_RULES) <= seeded
    assert all(row[2] in ae.ZONE_BUILDINGS for row in site_seed.ASSETS)  # every connected asset can be checked


def test_page_says_when_real_data_is_missing() -> None:
    assert "not configured" in ae.page_html({"asset_id": "FDM-AHU-01", "zone_code": "FDM", "asset_type": "AHU"}, None)
