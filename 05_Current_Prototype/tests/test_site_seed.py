"""Site database and synthetic seed: the intended story at as_of, freshness, and imported rows surviving a refresh."""

from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest

from demo import site_db, site_seed
from demo.asset_state import EVENT_POWER_TYPES, asset_state, maintenance_today

AS_OF = datetime(2026, 10, 12, 6, 7, tzinfo=timezone.utc)  # 14:07 SGT; the seed floors it to 14:00


@pytest.fixture()
def db_path():
    path = Path(__file__).resolve().parents[1] / "data" / f"test-site-{uuid4().hex}.sqlite3"
    site_seed.build(path, AS_OF)
    yield path
    path.unlink(missing_ok=True)


def test_state_mix_and_story_at_as_of(db_path) -> None:
    as_of = site_db.as_of(db_path)
    assert as_of == "2026-10-12T06:00:00+00:00"
    latest = site_db.latest_readings(db_path)
    states = {asset["asset_id"]: asset_state(asset, latest.get(asset["asset_id"], {}), as_of)["state"]
              for asset in site_db.assets(db_path) if asset["connected"] and asset["asset_type"] not in EVENT_POWER_TYPES}
    assert Counter(states.values()) == {"operational": 17, "idle": 4, "down": 3, "warning": 2, "offline": 1}
    assert {aid for aid, state in states.items() if state == "down"} == {"SGV-DB-03", "SGV-OUT-01", "CFR-PMP-01"}
    impacts = site_db.impacts(active_at=as_of, path=db_path)
    work = site_db.work_orders(as_of, "2026-10-12T16:00:00+00:00", path=db_path)
    assert maintenance_today("SGV-DB-03", work, impacts, as_of) and maintenance_today("SGV-OUT-01", work, impacts, as_of)


def test_permits_events_and_a_clash(db_path) -> None:
    as_of = site_db.as_of(db_path)
    active = site_db.ptws(active_at=as_of, path=db_path)
    assert {row["zone_code"] for row in active} == {"SGV", "DFB", "SKY", "SLV", "BFP"}
    assert all(row["contractor"]["colour"].startswith("#") and row["zone"]["x0"] is not None for row in active)
    assert all(site_db.ptw(row["ptw_id"], db_path)["impacts"] for row in active)  # every active permit says what it affects
    grove = next(row for row in active if row["zone_code"] == "SGV")
    events = site_db.event_orders(grove["start_at"], grove["end_at"], db_path)
    assert any(event["zone_code"] == "SGV" for event in events)  # a reception overlaps the Grove works
    later = site_db.ptws(start=as_of, end="2026-10-12T16:00:00+00:00", path=db_path)
    assert len(later) == 7  # five active plus two starting later today (SGT)


def test_queries_accept_any_offset(db_path) -> None:
    utc_rows = site_db.ptws(start="2026-10-12T00:00:00+00:00", end="2026-10-13T00:00:00+00:00", path=db_path)
    sgt_rows = site_db.ptws(start="2026-10-12T08:00:00+08:00", end="2026-10-13T08:00:00+08:00", path=db_path)
    assert utc_rows == sgt_rows and site_db.utc("2026-10-12T08:00:00+08:00") == "2026-10-12T00:00:00+00:00"


def test_ensure_fresh_rebuilds_only_when_stale_and_keeps_imported_rows(db_path) -> None:
    connection = site_db.connect(db_path)
    with connection:  # commits; closing() below releases the file on Windows
        site_db.insert(connection, "ingest_batches", [{"batch_id": "excel-20261012-001", "source_type": "excel",
                                                       "file_name": "meters.xlsx", "sha256": "x", "received_at": site_db.utc(AS_OF), "row_count": 1}])
        site_db.insert(connection, "readings", [{"asset_id": "FDM-AHU-01", "point_id": "voltage_v", "observed_at": "2026-10-01T00:07:00+00:00",
                                                 "value": 231.0, "unit": "V", "ingest_batch_id": "excel-20261012-001"}])
    connection.close()
    assert site_seed.ensure_fresh(6, db_path, now=AS_OF + timedelta(hours=2)) == "2026-10-12T06:00:00+00:00"  # still fresh
    assert site_seed.ensure_fresh(6, db_path, now=AS_OF + timedelta(hours=7)) == "2026-10-12T13:00:00+00:00"  # rebuilt
    kept = site_db.readings("FDM-AHU-01", "2026-10-01T00:00:00+00:00", "2026-10-01T00:10:00+00:00", db_path)
    assert [row["ingest_batch_id"] for row in kept] == ["excel-20261012-001"]
    assert len({row["ingest_batch_id"] for row in site_db.ptws(path=db_path)}) == 1  # one seed batch, no duplicates


def test_night_build_has_no_errors() -> None:
    path = Path(__file__).resolve().parents[1] / "data" / f"test-site-{uuid4().hex}.sqlite3"
    try:
        as_of = site_seed.build(path, datetime(2026, 10, 12, 15, 30, tzinfo=timezone.utc))  # 23:30 SGT
        latest = site_db.latest_readings(path)
        states = Counter(asset_state(a, latest.get(a["asset_id"], {}), as_of)["state"] for a in site_db.assets(path) if a["connected"] and a["asset_type"] not in EVENT_POWER_TYPES)
        assert states["idle"] > 4 and states["offline"] == 1  # day-only assets rest at night
    finally:
        path.unlink(missing_ok=True)


def test_a_reading_after_now_is_never_the_latest(db_path) -> None:
    before = site_db.latest_readings(db_path)["FDM-AHU-01"]["voltage_v"]
    connection = site_db.connect(db_path)
    with connection:
        site_db.insert(connection, "readings", [{"asset_id": "FDM-AHU-01", "point_id": "voltage_v",
                                                 "observed_at": "2026-10-12T06:15:00+00:00", "value": 299.0, "unit": "V",
                                                 "ingest_batch_id": None}])
    connection.close()
    assert site_db.latest_readings(db_path)["FDM-AHU-01"]["voltage_v"] == before


def test_every_connected_device_hangs_off_a_db_and_unconnected_devices_have_no_readings(db_path) -> None:
    every = {asset["asset_id"]: asset for asset in site_db.assets(db_path)}
    assert all(every[row["fed_from"]]["asset_type"] == {"CEE": "OGB", "OGB": "DB"}[row["asset_type"]]
               for row in every.values() if row["asset_type"] in EVENT_POWER_TYPES)  # socket -> OG box -> DB
    assets = {aid: asset for aid, asset in every.items() if asset["asset_type"] not in EVENT_POWER_TYPES}
    unconnected = {aid for aid, asset in assets.items() if not asset["connected"]}
    assert len(unconnected) == len(site_seed.UNCONNECTED) and len(assets) - len(unconnected) == len(site_seed.ASSETS)
    assert all(assets[asset["fed_from"]]["asset_type"] == "DB" for asset in assets.values() if asset["asset_type"] != "DB")
    assert not unconnected & set(site_db.latest_readings(db_path))


def test_a_rebuild_drops_seed_assets_the_seed_no_longer_lists(db_path) -> None:
    connection = site_db.connect(db_path)
    batch = next(row[0] for row in connection.execute("SELECT batch_id FROM ingest_batches WHERE source_type = 'seed'"))
    with connection:
        site_db.insert(connection, "assets", [{"asset_id": "OLD-PMP-01", "name": "Retired pump", "zone_code": "SGV", "asset_type": "PMP",
                                               "connected": 1, "ingest_batch_id": batch}])
    connection.close()
    site_seed.build(db_path, AS_OF)
    assert "OLD-PMP-01" not in {asset["asset_id"] for asset in site_db.assets(db_path)}
