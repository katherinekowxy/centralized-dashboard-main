"""Asset status by location: equipment comes from the inventory lines (with Ref. ID); states are demo and stable.
Fixtures are invented."""

from demo import asset_inventory


def item(store, sub, name, ref, category="Electrical", quantity=1.0):
    return {"store": store, "item": name, "category": category, "subcategory": sub, "ref": ref, "quantity": quantity}


ITEMS = [item("GBB-AH10", "Isolator", "16A isolator", f"IFM-{n}") for n in range(6)] + [
    item("Gardens By The Bay (South)", "DB", "Lighting DB", "GB-E-0001"),
    item("Gardens By The Bay (South)", "Pump", "Sump pump", "GB-M-0002", category="Mechanical"),
    item("Gardens By The Bay (South)", "Circuit Breaker", "MCB 2P 20A", "GB-E-0003"),
    item("GBB-Meadow", "Transformer", "Current transformer", "GB-MS-0012"),
    item("GBB-Meadow", "Pump", "Irrigation pump", "GB-MS-0053", category="Mechanical"),
    item("GBB-Meadow", "Lamp", "LED lamp", "GB-E-0500"),        # consumable: not equipment
    item("GBB-EC11", "Lockset", "Door lockset", "GB-B-0001", category="Building"),
]


def test_only_equipment_lines_count_and_keep_their_ref_id() -> None:
    rows = asset_inventory.equipment(ITEMS)
    assert len(rows) == 11
    assert {row["type"] for row in rows} <= set(asset_inventory.EQUIPMENT)
    assert {row["location"] for row in rows} == {"GBB-AH10", "GBB South", "GBB-Meadow"}
    assert all(row["ref"] for row in rows)


def test_demo_states_are_fixed_and_counted_once() -> None:
    first, again = asset_inventory.equipment(ITEMS), asset_inventory.equipment(list(reversed(ITEMS)))
    assert {(r["ref"], r["state"]) for r in first} == {(r["ref"], r["state"]) for r in again}
    tally = asset_inventory.counts(first)
    assert (tally["down"], tally["warning"], tally["offline"]) == (3, 5, 2) and sum(tally.values()) == len(first)


def test_board_shows_problems_with_ref_and_says_states_are_demo() -> None:
    rows = asset_inventory.equipment(ITEMS)
    markup = asset_inventory.board_html(rows, None)
    problem = next(row for row in rows if row["state"] == "down")
    assert f"Ref. {problem['ref']}" in markup and "(demo)" in markup and "states are demo" in markup
    assert "GBB South" in markup and "Gardens By The Bay (South)" not in markup
