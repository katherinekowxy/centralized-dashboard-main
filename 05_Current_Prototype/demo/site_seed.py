"""Synthetic site data for Bay South (docs/site-data-contract.md). Readings, states, permits and events are invented.

Which equipment each place has follows the iSMM fault log, 1 Aug to 20 Oct 2026 (21 October 2026): an asset is listed
only where faults were raised against that kind of equipment in that building, and is named by its iSMM tag where the
fault remarks give one (CD-AHU-07, AHU-CM-10, CM-F-L1, CD-F-L1, LG-OG-3, LG-OG-4). Chillers are not listed: their
faults are logged at the Energy Centre, which is not on the map. demo/sources/asset_evidence.py shows the matching
records on each asset page.

Times are relative to ``as_of`` (the real clock, rounded down to 15 minutes), so "today" always has work on it.
The story at ``as_of``: Supertree Grove DB-03 is isolated under a permit and the CO5 supply is down (red, with cones);
the Cloud Forest waterfall pump has tripped unexpectedly (red, no permit); an air handler runs on high voltage and the
Dragonfly Lake aerator pump over its rated current (orange); the Chinese Garden pump meter has stopped reporting
(grey); evening lights are idle by day. A reception overlaps the Grove works, so the calendar shows a clash. Two meeting rooms carry a week of bookings.
"""

from __future__ import annotations

import json
import math
import random
import sqlite3
from datetime import datetime, time, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

from demo import site_db
from demo.asset_state import SGT, in_operating_hours

ZONES_JSON = Path(__file__).resolve().parents[1] / "assets" / "maps" / "bay-south-zones.json"
ZONES_GEOJSON = ZONES_JSON.with_suffix(".geojson")  # real-world outlines, mostly from OpenStreetMap
SEED = 7
SEED_VERSION = "6"  # bump when the seed gains tables or rows, so an older file is rebuilt once
STEP = timedelta(minutes=15)
HISTORY = timedelta(days=7)

CONTRACTORS = [  # fictional; colours checked with the dataviz validator against the map
    ("CTR-NWD", "Northwind M&E Pte Ltd", "Northwind", "#8B5CF6"),
    ("CTR-HLX", "Helix Civil Works", "Helix", "#EC4899"),
    ("CTR-VRD", "Verdant Landscapes", "Verdant", "#06B6D4"),
    ("CTR-SKL", "Skyline Lifts & Access", "Skyline", "#FACC15"),
    ("CTR-ARC", "Arctic Cooling Services", "Arctic", "#F8FAFC"),
    ("CTR-TMB", "Timberline Building Works", "Timberline", "#9A3412"),
]

UNCONNECTED = [  # in the register, but SignalDesk gets no readings from them: asset_id, name, zone, type, fed_from
    ("FDM-DB-01", "Flower Dome DB 1", "FDM", "DB", None),
    ("CFR-DB-01", "Cloud Forest DB 1", "CFR", "DB", None),
    ("SKY-DB-01", "Skyway DB", "SKY", "DB", None),
    ("ACT-DB-01", "Active Garden DB", "ACT", "DB", None),
    ("MDW-DB-01", "Meadow DB", "MDW", "DB", None),
    ("DFL-DB-01", "Dragonfly Lake DB", "DFL", "DB", None),
    ("HER-DB-01", "Heritage Gardens DB", "HER", "DB", None),
    ("GLD-DB-01", "Golden Garden DB", "GLD", "DB", None),  # no fault names it; assumed, as the spike lights it feeds are in the log
    ("SGV-LGT-02", "Path lights", "SGV", "LGT", "SGV-DB-01"),
    ("ENT-LGT-01", "Entrance lights", "ENT", "LGT", "ENT-DB-01"),
    ("ENT-OUT-01", "Ticketing outlets", "ENT", "OUT", "ENT-DB-01"),
    ("CHG-LGT-01", "Treehouse lights", "CHG", "LGT", "CHG-DB-01"),
    ("BFP-LGT-01", "Plaza lights", "BFP", "LGT", "BFP-DB-01"),
]

OG_BOXES = [  # outdoor power boxes for events: box_id, name, zone, fed from, incomer A, CEEform sockets as (rated A, phases)
    ("MDW-OGB-01", "LG-OG-4", "MDW", "MDW-DB-01", 200, [(63, 3), (63, 3), (32, 3), (16, 1), (16, 1)]),
    ("MDW-OGB-02", "Meadow OG box 2", "MDW", "MDW-DB-01", 125, [(32, 3), (32, 3), (16, 1), (16, 1), (16, 1)]),
    ("ACT-OGB-01", "Active Garden OG box", "ACT", "ACT-DB-01", 100, [(32, 3), (16, 1), (16, 1), (16, 1)]),
    ("SGV-OGB-01", "LG-OG-3", "SGV", "SGV-DB-03", 100, [(32, 3), (32, 3), (16, 1), (16, 1)]),
    ("BFP-OGB-01", "Plaza OG box", "BFP", "BFP-DB-01", 125, [(63, 3), (32, 3), (16, 1), (16, 1)]),
]

SOCKET_USE = {  # event title -> the sockets it books: (socket, what it powers, share of the socket's rating it draws)
    "Music festival": [("MDW-CEE-01", "Stage", .7), ("MDW-CEE-02", "Stage lighting", .65), ("MDW-CEE-03", "Sound", .5),
                       ("MDW-CEE-04", "Artist tent", .4), ("MDW-CEE-05", "Food truck", .75), ("MDW-CEE-06", "Food trucks", .7),
                       ("MDW-CEE-07", "Bar", .5), ("MDW-CEE-08", "Info booth", .15), ("MDW-CEE-09", "Hand-wash", .3)],
    "Weekend market": [("MDW-CEE-06", "Stalls", .6), ("MDW-CEE-08", "Stall lighting", .5), ("MDW-CEE-10", "Info booth", .15)],
    "Pop-up market": [("ACT-CEE-02", "Food stalls", .85), ("ACT-CEE-03", "Coffee cart", .7), ("ACT-CEE-04", "Stall lighting", .45)],
    "Corporate reception": [("SGV-CEE-01", "Catering", .6), ("SGV-CEE-02", "AV and lighting", .55), ("SGV-CEE-03", "Bar", .5),
                            ("SGV-CEE-04", "Registration", .2)],
    "Light show rehearsal": [("SGV-CEE-02", "Show control", .3)],
    "Product launch": [("BFP-CEE-01", "Stage", .6), ("BFP-CEE-02", "AV", .45), ("BFP-CEE-03", "Catering", .6)],
}
SETUP = timedelta(hours=1)  # a booked socket draws a third of its load during the hour before the event


def sockets() -> list[tuple]:
    """Every CEEform socket as (socket_id, name, zone, box_id, rated A, phases), numbered per zone."""
    rows, count = [], {}
    for box_id, name, zone, _, _, box_sockets in OG_BOXES:
        for n, (rated, phases) in enumerate(box_sockets, start=1):
            count[zone] = count.get(zone, 0) + 1
            rows.append((f"{zone}-CEE-{count[zone]:02d}", f"{name} · socket {n}", zone, box_id, rated, phases))
    return rows


ROOMS = [  # room_id, name, seats; fictional names, "2 for now" (Dan, 12 October 2026)
    ("MR-01", "Orchid Room", 12),
    ("MR-02", "Fern Room", 6),
]

ROOM_DAYS = [  # one list per day from as_of's date, cycled; (room, start, end, meeting, booked by) in SGT; teams, not people
    [("MR-01", "09:00", "09:30", "Daily operations huddle", "Facilities"),
     ("MR-01", "10:30", "12:00", "Permit coordination", "Engineering"),
     ("MR-01", "14:00", "15:30", "AHU service: vendor meeting", "Engineering"),
     ("MR-01", "16:00", "17:00", "Weekend market briefing", "Event Sales"),
     ("MR-02", "09:30", "10:00", "Interview", "HR"),
     ("MR-02", "11:00", "11:30", "Contractor induction", "Facilities"),
     ("MR-02", "13:00", "14:30", "Budget review", "Finance"),
     ("MR-02", "17:00", "18:00", "Works look-ahead", "Engineering")],
    [("MR-01", "09:00", "09:30", "Daily operations huddle", "Facilities"),
     ("MR-01", "11:00", "12:30", "Horticulture planning", "Horticulture"),
     ("MR-01", "15:00", "16:00", "Safety committee", "Safety"),
     ("MR-02", "10:00", "11:00", "Supplier call", "Procurement"),
     ("MR-02", "14:00", "15:00", "Interview", "HR")],
    [("MR-01", "09:00", "09:30", "Daily operations huddle", "Facilities"),
     ("MR-01", "13:00", "17:00", "Training: lock-out tag-out", "Engineering"),
     ("MR-02", "09:30", "10:30", "Event order review", "Event Sales"),
     ("MR-02", "15:30", "16:30", "Lift contract review", "Facilities")],
    [("MR-01", "09:00", "09:30", "Daily operations huddle", "Facilities"),
     ("MR-01", "10:00", "11:00", "VIP tour planning", "Corporate Affairs"),
     ("MR-02", "11:30", "12:30", "Energy report", "Engineering"),
     ("MR-02", "16:00", "17:00", "Team meeting", "Horticulture")],
]

ASSETS = [  # asset_id, name, zone, type, criticality, fed_from, rated A, idle A, operating hours (SGT); see the module docstring
    ("FDM-AHU-01", "AHU CD-AHU-07", "FDM", "AHU", "high", "FDM-DB-01", 45, 2, "24h"),
    ("FDM-AHU-02", "Air handler 2", "FDM", "AHU", "high", "FDM-DB-01", 45, 2, "24h"),
    ("FDM-PMP-01", "Flower field pump", "FDM", "PMP", "medium", "FDM-DB-01", 22, 1, "08:00-21:00"),
    ("FDM-LFT-01", "Lift CD-F-L1", "FDM", "LFT", "medium", "FDM-DB-01", 20, 1, "09:00-21:00"),
    ("CFR-AHU-01", "AHU-CM-10", "CFR", "AHU", "high", "CFR-DB-01", 45, 2, "24h"),
    ("CFR-MST-01", "Fog machine 2", "CFR", "MST", "medium", "CFR-DB-01", 12, .5, "08:00-21:00"),
    ("CFR-PMP-01", "Waterfall pump", "CFR", "PMP", "medium", "CFR-DB-01", 25, 1, "09:00-21:00"),
    ("CFR-LFT-01", "Lift CM-F-L1", "CFR", "LFT", "medium", "CFR-DB-01", 20, 1, "09:00-21:00"),
    ("SGV-DB-01", "Grove DB 1", "SGV", "DB", "high", None, 250, 2, "24h"),
    ("SGV-DB-03", "Grove DB 3", "SGV", "DB", "high", None, 200, 1, "24h"),
    ("SGV-OUT-01", "CO5 supply", "SGV", "OUT", "low", "SGV-DB-03", 32, .5, "08:00-23:00"),
    ("SGV-LGT-01", "Supertree lights", "SGV", "LGT", "medium", "SGV-DB-01", 60, 1, "19:00-02:00"),
    ("SGV-PMP-01", "Supertree filter pump", "SGV", "PMP", "medium", "SGV-DB-01", 15, 1, "24h"),
    ("SKY-LFT-01", "Skyway lift 1", "SKY", "LFT", "medium", "SKY-DB-01", 20, 1, "09:00-21:00"),
    ("SKY-LFT-02", "Skyway lift 2", "SKY", "LFT", "medium", "SKY-DB-01", 20, 1, "09:00-21:00"),
    ("SLV-DB-01", "Silver Garden DB", "SLV", "DB", "medium", None, 125, 1, "24h"),
    ("SLV-FTN-01", "Water weir pump", "SLV", "FTN", "low", "SLV-DB-01", 15, .5, "09:00-21:00"),
    ("SLV-LGT-01", "Garden lights", "SLV", "LGT", "low", "SLV-DB-01", 25, .5, "19:00-02:00"),
    ("GLD-LGT-01", "Golden Garden spike lights", "GLD", "LGT", "medium", "GLD-DB-01", 40, 1, "19:00-02:00"),
    ("CHG-DB-01", "Children's Garden DB", "CHG", "DB", "medium", None, 100, 1, "24h"),
    ("BFP-DB-01", "Plaza DB", "BFP", "DB", "medium", None, 160, 1, "24h"),
    ("BFP-OUT-01", "Plaza outlets", "BFP", "OUT", "low", "BFP-DB-01", 32, .5, "08:00-23:00"),
    ("ENT-DB-01", "Entrance DB", "ENT", "DB", "medium", None, 125, 1, "24h"),
    ("ACT-OUT-01", "Active Garden outlets", "ACT", "OUT", "low", "ACT-DB-01", 32, .5, "07:00-22:00"),
    ("MDW-LGT-01", "Meadow lights", "MDW", "LGT", "low", "MDW-DB-01", 30, .5, "19:00-23:00"),
    ("DFL-PMP-01", "Aerator pump", "DFL", "PMP", "medium", "DFL-DB-01", 30, 2, "24h"),
    ("HER-PMP-01", "Chinese Garden pump", "HER", "PMP", "low", "HER-DB-01", 15, 1, "24h"),
]


def floor_quarter(moment: datetime) -> datetime:
    moment = moment.astimezone(timezone.utc).replace(second=0, microsecond=0)
    return moment - timedelta(minutes=moment.minute % 15)


def floor_hour(moment: datetime) -> datetime:
    return moment.replace(minute=0, second=0, microsecond=0)


def sgt_day(as_of: datetime, days: int, hhmm: str) -> datetime:
    """A wall-clock time in SGT, ``days`` after as_of's SGT date, as UTC."""
    day = as_of.astimezone(SGT).date() + timedelta(days=days)
    return datetime.combine(day, time.fromisoformat(hhmm), SGT).astimezone(timezone.utc)


def iso(moment: datetime) -> str:
    return site_db.utc(moment)


def _story(as_of: datetime) -> dict[str, Any]:
    """Permits, impacts, events and work orders: the scenario the dashboards show."""
    now = floor_hour(as_of)
    p = {  # permit windows relative to now, so five are always active and one or two start later today
        "grove": (now - timedelta(hours=4), now + timedelta(hours=5)),
        "bridge": (sgt_day(as_of, -1, "22:00"), sgt_day(as_of, 2, "18:00")),
        "skyway": (now - timedelta(hours=1), now + timedelta(hours=4)),
        "silver": (now - timedelta(hours=2), now + timedelta(hours=5)),
        "plaza": (now - timedelta(hours=3), now + timedelta(hours=3)),
        "chiller": (now + timedelta(hours=2), now + timedelta(hours=6)),
        "pump": (now + timedelta(hours=1), now + timedelta(hours=3)),
    }
    ptws = [
        ("grove", "SGV", "CTR-NWD", "DB-03 replacement", "electrical"),
        ("bridge", "DFB", "CTR-HLX", "Deck resurfacing", "civil"),
        ("skyway", "SKY", "CTR-SKL", "Skyway lift inspection", "height"),
        ("silver", "SLV", "CTR-VRD", "Planting refresh", "landscape"),
        ("plaza", "BFP", "CTR-TMB", "Canopy repair", "civil"),
        ("chiller", "FDM", "CTR-ARC", "CD-AHU-07 service", "mechanical"),
        ("pump", "CFR", "CTR-NWD", "Pump trip investigation", "electrical"),
    ]
    # past and future permits for the calendar (days offset, start, end, zone, contractor, title, type)
    extra = [(-6, "09:00", "17:00", "CFR", "CTR-ARC", "AHU coil clean", "mechanical"),
             (-4, "08:00", "12:00", "GLD", "CTR-NWD", "Lighting driver swap", "electrical"),
             (-3, "21:00", "23:59", "SGV", "CTR-SKL", "Supertree canopy check", "height"),
             (-2, "07:00", "15:00", "MDW", "CTR-VRD", "Turf renovation", "landscape"),
             (1, "09:00", "17:00", "CFR", "CTR-ARC", "AHU-CM-10 filter change", "mechanical"),
             (2, "08:00", "16:00", "ACT", "CTR-TMB", "Play surface repair", "civil"),
             (3, "22:00", "23:59", "SGV", "CTR-NWD", "Lighting control upgrade", "electrical"),
             (4, "09:00", "13:00", "SKY", "CTR-SKL", "Skyway lift 1 inspection", "height"),
             (6, "08:00", "18:00", "FCK", "CTR-VRD", "Floral Clock replanting", "landscape"),
             (9, "09:00", "17:00", "FDM", "CTR-ARC", "Air handler 2 quarterly service", "mechanical")]
    year = as_of.astimezone(SGT).year
    rows, ids = [], {}
    for number, (key, zone, contractor, title, kind) in enumerate(ptws, start=142):
        ids[key] = f"PTW-{year}-{number:04d}"
        start, end = p[key]
        rows.append({"ptw_id": ids[key], "zone_code": zone, "contractor_id": contractor, "title": title, "work_type": kind,
                     "start_at": iso(start), "end_at": iso(end)})
    for number, (days, start, end, zone, contractor, title, kind) in enumerate(extra, start=160):
        rows.append({"ptw_id": f"PTW-{year}-{number:04d}", "zone_code": zone, "contractor_id": contractor, "title": title,
                     "work_type": kind, "start_at": iso(sgt_day(as_of, days, start)), "end_at": iso(sgt_day(as_of, days, end))})

    def impact(key: str, n: int, kind: str, target_type: str, target: str, effect: str, summary: str, window=None) -> dict:
        start, end = window or p[key]
        return {"impact_id": f"{ids[key]}/{n}", "ptw_id": ids[key], "kind": kind, "target_type": target_type,
                "target_id": target, "effect": effect, "summary": summary, "start_at": iso(start), "end_at": iso(end)}

    sky_close = (p["skyway"][0] + timedelta(hours=1), p["skyway"][0] + timedelta(hours=3))
    impacts = [
        impact("grove", 1, "electrical", "asset", "SGV-DB-03", "isolated", "DB-03 isolated"),
        impact("grove", 2, "electrical", "asset", "SGV-OUT-01", "down", "CO5 supply off"),
        impact("bridge", 1, "physical", "zone", "DFB", "closed", "Bridge closed"),
        impact("skyway", 1, "physical", "zone", "SKY", "closed", "Skyway closed", sky_close),
        impact("silver", 1, "physical", "route", "Silver Garden east path", "restricted", "East path restricted"),
        impact("plaza", 1, "physical", "route", "Plaza canopy walkway", "closed", "Canopy walkway closed"),
        impact("chiller", 1, "electrical", "asset", "FDM-AHU-01", "isolated", "CD-AHU-07 isolated"),
        impact("pump", 1, "electrical", "asset", "CFR-PMP-01", "isolated", "Pump isolated for testing"),
    ]
    grove_end = p["grove"][1]
    events = [  # eo_id, zone, title, start, end, organiser, guests
        ("SGV", "Corporate reception", grove_end - timedelta(hours=2), grove_end + timedelta(hours=2), "Event Sales", 180),
        ("FDM", "Floral display opening", sgt_day(as_of, 1, "10:00"), sgt_day(as_of, 1, "12:00"), "Horticulture", 120),
        ("MDW", "Weekend market", sgt_day(as_of, 2, "09:00"), sgt_day(as_of, 2, "21:00"), "Event Sales", 2500),
        ("CFR", "VIP tour", sgt_day(as_of, 3, "15:00"), sgt_day(as_of, 3, "16:00"), "Corporate Affairs", 15),
        ("SLV", "Wedding photoshoot", sgt_day(as_of, 1, "07:00"), sgt_day(as_of, 1, "09:00"), "Event Sales", 20),
        ("ACT", "School group visit", sgt_day(as_of, 5, "09:30"), sgt_day(as_of, 5, "12:00"), "Education", 80),
        ("BFP", "Product launch", sgt_day(as_of, 6, "19:00"), sgt_day(as_of, 6, "22:00"), "Event Sales", 300),
        ("SGV", "Light show rehearsal", sgt_day(as_of, 4, "20:00"), sgt_day(as_of, 4, "23:00"), "Programmes", None),
        ("CHG", "Birthday party", sgt_day(as_of, -2, "10:00"), sgt_day(as_of, -2, "13:00"), "Event Sales", 40),
        ("MDW", "Music festival", now - timedelta(hours=3), now + timedelta(hours=5), "Programmes", 3000),  # on now: live loads
        ("ACT", "Pop-up market", now - timedelta(hours=2), now + timedelta(hours=3), "Event Sales", 400),
    ]
    event_rows = [{"eo_id": f"EO-{year}-{number:04d}", "zone_code": zone, "title": title, "start_at": iso(start),
                   "end_at": iso(end), "organiser": organiser, "expected_guests": guests}
                  for number, (zone, title, start, end, organiser, guests) in enumerate(events, start=31)]
    work = [  # asset, title, start, end, status, linked permit key
        ("SGV-DB-03", "Replace DB-03 incomer", *p["grove"], "in_progress", "grove"),
        ("FDM-AHU-01", "CD-AHU-07 quarterly service", *p["chiller"], "scheduled", "chiller"),
        ("CFR-PMP-01", "Investigate pump trip", *p["pump"], "scheduled", "pump"),
        ("FDM-AHU-01", "Filter change", sgt_day(as_of, -5, "09:00"), sgt_day(as_of, -5, "11:00"), "done", None),
        ("CFR-AHU-01", "Coil clean", sgt_day(as_of, -6, "09:00"), sgt_day(as_of, -6, "17:00"), "done", None),
        ("GLD-LGT-01", "Driver replacement", sgt_day(as_of, -4, "08:00"), sgt_day(as_of, -4, "12:00"), "done", None),
        ("SKY-LFT-01", "Monthly lift inspection", sgt_day(as_of, 4, "09:00"), sgt_day(as_of, 4, "13:00"), "scheduled", None),
        ("CFR-LFT-01", "Monthly lift inspection", sgt_day(as_of, 1, "09:00"), sgt_day(as_of, 1, "17:00"), "scheduled", None),
        ("FDM-LFT-01", "Door sensor check", sgt_day(as_of, 2, "07:00"), sgt_day(as_of, 2, "08:00"), "scheduled", None),
        ("SLV-FTN-01", "Weir screen clean", sgt_day(as_of, 3, "08:00"), sgt_day(as_of, 3, "09:00"), "scheduled", None),
        ("DFL-PMP-01", "Aerator cable insulation test", sgt_day(as_of, 5, "08:00"), sgt_day(as_of, 5, "16:00"), "scheduled", None),
        ("ENT-DB-01", "Thermographic survey", sgt_day(as_of, 6, "06:00"), sgt_day(as_of, 6, "08:00"), "scheduled", None),
        ("FDM-PMP-01", "Quarterly service", sgt_day(as_of, 9, "09:00"), sgt_day(as_of, 9, "17:00"), "scheduled", None),
        ("CFR-MST-01", "Nozzle descale", sgt_day(as_of, -1, "07:00"), sgt_day(as_of, -1, "08:00"), "done", None),
        ("SGV-LGT-01", "Lighting control upgrade", sgt_day(as_of, 3, "22:00"), sgt_day(as_of, 3, "23:59"), "scheduled", None),
    ]
    work_rows = [{"wo_id": f"WO-{year}-{number:04d}", "asset_id": asset, "title": title, "scheduled_start": iso(start),
                  "scheduled_end": iso(end), "status": status, "ptw_id": ids.get(key) if key else None}
                 for number, (asset, title, start, end, status, key) in enumerate(work, start=457)]
    return {"ptws": rows, "ptw_impacts": impacts, "event_orders": event_rows, "work_orders": work_rows,
            "isolations": {"SGV-DB-03": p["grove"], "SGV-OUT-01": p["grove"], "FDM-AHU-01": p["chiller"], "CFR-PMP-01": p["pump"]}}


def _bookings(as_of: datetime, batch: str) -> list[dict]:
    """A week of meeting room bookings from as_of's date; weekends keep only the morning huddle and one meeting."""
    rows = []
    for days in range(7):
        plan = ROOM_DAYS[days % len(ROOM_DAYS)]
        if sgt_day(as_of, days, "12:00").astimezone(SGT).weekday() >= 5:
            plan = plan[:1] + [row for row in plan if row[0] == "MR-02"][:1]
        for room, start, end, title, team in plan:
            rows.append({"booking_id": f"RB-{len(rows) + 1:04d}", "room_id": room, "title": title, "booked_by": team,
                         "start_at": iso(sgt_day(as_of, days, start)), "end_at": iso(sgt_day(as_of, days, end)), "source": "seed",
                         "created_at": iso(sgt_day(as_of, -3, "09:00")), "cancelled_at": None, "ingest_batch_id": batch})
    return rows


def _readings(as_of: datetime, isolations: dict[str, tuple], rng: random.Random, batch: str) -> list[dict]:
    """Seven days of 15-minute electrical readings consistent with each asset's intended state at as_of."""
    rows = []
    trip_at = as_of - timedelta(minutes=50)            # CFR-PMP-01 trips unexpectedly
    offline_from = as_of - timedelta(hours=2)          # HER-PMP-01 meter stops reporting
    steps = int(HISTORY / STEP)
    for asset_id, _, _, _, _, _, rated, idle, hours in ASSETS:
        energy = rng.uniform(15_000, 90_000)
        phase = rng.uniform(0, 2 * math.pi)
        for step in range(steps, -1, -1):
            at = as_of - step * STEP
            if asset_id == "HER-PMP-01" and at > offline_from:
                continue
            start, end = isolations.get(asset_id, (None, None))
            isolated = start is not None and start <= at < end
            tripped = asset_id == "CFR-PMP-01" and at >= trip_at
            running = in_operating_hours(hours, at) and not isolated and not tripped
            hour = at.astimezone(SGT).hour + at.astimezone(SGT).minute / 60
            load = .55 + .15 * math.sin(2 * math.pi * (hour - 9) / 24 + phase / 6) + rng.gauss(0, .025)
            amps = rated * max(.2, load) if running else (0.0 if isolated or tripped else idle * .15)
            if asset_id == "DFL-PMP-01" and at > as_of - timedelta(hours=2):
                amps = rated * 1.12 + rng.gauss(0, .3)     # over rated current: Warning
            volts = 0.0 if isolated else 230 + rng.gauss(0, .8)
            if asset_id == "FDM-AHU-02" and at > as_of - timedelta(hours=3):
                volts = 258 + rng.gauss(0, .5)              # high supply voltage: Warning
            pf = min(.99, .91 + rng.gauss(0, .015)) if amps > idle else 0.0
            kw = math.sqrt(3) * volts * amps * pf / 1000
            energy += kw * .25
            for point, value, unit in (("voltage_v", volts, "V"), ("current_a", amps, "A"), ("power_kw", kw, "kW"),
                                       ("energy_kwh", energy, "kWh"), ("power_factor", pf, ""),
                                       ("trip_state", 1.0 if tripped else 0.0, "state")):
                rows.append({"asset_id": asset_id, "point_id": point, "observed_at": iso(at), "value": round(value, 3),
                             "unit": unit, "ingest_batch_id": batch})
    return rows


def _event_readings(as_of: datetime, events: list[dict], isolations: dict[str, tuple], rng: random.Random,
                    batch: str) -> list[dict]:
    """15-minute loads on each CEEform socket from the events booked on it, and each OG box's total on its worst phase.
    A box whose DB is isolated has no supply. Story at as_of: the festival bar socket tripped 40 minutes ago, and the
    market's food stalls draw more than their 16 A socket is rated for."""
    by_title = {row["title"]: row for row in events}
    windows: dict[str, list[tuple]] = {}
    for title, uses in SOCKET_USE.items():
        for socket_id, _, share in uses:
            windows.setdefault(socket_id, []).append((datetime.fromisoformat(by_title[title]["start_at"]),
                                                      datetime.fromisoformat(by_title[title]["end_at"]), share))
    all_sockets = sockets()
    wobble = {row[0]: rng.uniform(0, 2 * math.pi) for row in all_sockets}
    energy = {asset_id: rng.uniform(2_000, 9_000) for asset_id in [row[0] for row in all_sockets] + [box[0] for box in OG_BOXES]}
    trip_at, over_from = as_of - timedelta(minutes=40), as_of - timedelta(minutes=90)
    rows = []

    def emit(asset_id: str, at: datetime, volts: float, amps: float, kw: float, pf: float, tripped: bool) -> None:
        energy[asset_id] += kw * .25
        for point, value, unit in (("voltage_v", volts, "V"), ("current_a", amps, "A"), ("power_kw", kw, "kW"),
                                   ("energy_kwh", energy[asset_id], "kWh"), ("power_factor", pf, ""),
                                   ("trip_state", 1.0 if tripped else 0.0, "state")):
            rows.append({"asset_id": asset_id, "point_id": point, "observed_at": iso(at), "value": round(value, 3),
                         "unit": unit, "ingest_batch_id": batch})

    for step in range(int(HISTORY / STEP), -1, -1):
        at = as_of - step * STEP
        hour = at.astimezone(SGT).hour + at.astimezone(SGT).minute / 60
        for box_id, _, _, feeder, _, _ in OG_BOXES:
            start, end = isolations.get(feeder, (None, None))
            dead = start is not None and start <= at < end
            volts = 0.0 if dead else 230 + rng.gauss(0, .8)
            per_phase, total_kw, single = [0.0, 0.0, 0.0], 0.0, 0
            for socket_id, _, _, box, rated, phases in all_sockets:
                if box != box_id:
                    continue
                share = 0.0
                for begin, finish, full in windows.get(socket_id, []):
                    if begin <= at < finish:
                        share = max(share, full * (.88 + .12 * math.sin(hour * 1.3 + wobble[socket_id])) + rng.gauss(0, .015))
                    elif begin - SETUP <= at < begin:
                        share = max(share, full / 3)
                tripped = socket_id == "MDW-CEE-07" and at >= trip_at
                amps = 0.0 if dead or tripped else rated * max(0.0, share)
                if socket_id == "ACT-CEE-02" and at >= over_from and amps:
                    amps = rated * 1.1 + rng.gauss(0, .15)   # over its 16 A rating: Warning
                pf = min(.99, .9 + rng.gauss(0, .02)) if amps > .5 else 0.0
                kw = (3 if phases == 3 else 1) * volts * amps * pf / 1000
                emit(socket_id, at, volts, amps, kw, pf, tripped)
                if phases == 3:
                    per_phase = [value + amps for value in per_phase]
                else:  # single-phase sockets are spread across L1, L2 and L3
                    per_phase[single % 3] += amps
                    single += 1
                total_kw += kw
            amps = max(per_phase)
            emit(box_id, at, volts, amps, total_kw, .92 if amps > 1 else 0.0, False)
    return rows


@lru_cache(maxsize=1)
def _outlines() -> dict[str, dict]:
    return {item["properties"]["zone_code"]: item for item in json.loads(ZONES_GEOJSON.read_text(encoding="utf-8"))["features"]}


def _geo(zone_code: str) -> dict[str, Any]:
    """The zone's outline (GeoJSON geometry), label point and where the outline came from."""
    feature = _outlines().get(zone_code)
    if feature is None:
        return {"geometry": None, "lat": None, "lon": None, "geo_source": None}
    lon, lat = feature["properties"]["label"]
    return {"geometry": json.dumps(feature["geometry"]), "lat": lat, "lon": lon, "geo_source": feature["properties"]["source"]}


def generate(as_of: datetime, seed: int = SEED) -> dict[str, list[dict]]:
    as_of = floor_quarter(as_of)
    rng = random.Random(seed)
    batch = f"seed-{as_of.astimezone(SGT):%Y%m%d}-001"
    zones = json.loads(ZONES_JSON.read_text(encoding="utf-8"))["zones"]
    story = _story(as_of)
    data = {
        "site_meta": [{"key": "as_of", "value": iso(as_of)}, {"key": "generated_at", "value": iso(datetime.now(timezone.utc))},
                      {"key": "seed", "value": str(seed)}, {"key": "seed_version", "value": SEED_VERSION}],
        "ingest_batches": [{"batch_id": batch, "source_type": "seed", "file_name": "demo/site_seed.py", "sha256": None,
                            "received_at": iso(as_of), "row_count": 0}],
        "zones": [{"zone_code": zone["zone_code"], "name": zone["name"], "map_no": zone.get("map_no"), "kind": zone.get("kind"),
                   **dict(zip(("x0", "y0", "x1", "y1"), zone["box"])), **_geo(zone["zone_code"])} for zone in zones],
        "contractors": [{"contractor_id": cid, "name": name, "short_name": short, "colour": colour, "logo_svg": None}
                        for cid, name, short, colour in CONTRACTORS],
        "assets": [{"asset_id": aid, "name": name, "zone_code": zone, "asset_type": kind, "criticality": crit, "fed_from": fed,
                    "rated_current_a": rated, "idle_current_a": idle, "operating_hours": hours, "connected": 1, "phases": None,
                    "ingest_batch_id": batch}
                   for aid, name, zone, kind, crit, fed, rated, idle, hours in ASSETS]
                  + [{"asset_id": box_id, "name": name, "zone_code": zone, "asset_type": "OGB", "criticality": "medium", "fed_from": feeder,
                      "rated_current_a": incomer, "idle_current_a": 1.0, "operating_hours": "on demand", "connected": 1, "phases": 3,
                      "ingest_batch_id": batch} for box_id, name, zone, feeder, incomer, _ in OG_BOXES]
                  + [{"asset_id": sid, "name": name, "zone_code": zone, "asset_type": "CEE", "criticality": "low", "fed_from": box_id,
                      "rated_current_a": rated, "idle_current_a": .5, "operating_hours": "on demand", "connected": 1, "phases": phases,
                      "ingest_batch_id": batch} for sid, name, zone, box_id, rated, phases in sockets()]
                  + [{"asset_id": aid, "name": name, "zone_code": zone, "asset_type": kind, "criticality": None, "fed_from": fed,
                      "rated_current_a": None, "idle_current_a": None, "operating_hours": None, "connected": 0, "phases": None,
                      "ingest_batch_id": batch}
                     for aid, name, zone, kind, fed in UNCONNECTED],
        "asset_aliases": [{"alias": f"EMS-{aid.replace('-', '')}", "asset_id": aid, "system": "Energy meters (synthetic)"}
                          for aid in [row[0] for row in ASSETS] + [box[0] for box in OG_BOXES] + [row[0] for row in sockets()]],
        "ptws": [{**row, "source_file": None, "ingest_batch_id": batch} for row in story["ptws"]],
        "ptw_impacts": story["ptw_impacts"],
        "event_orders": [{**row, "ingest_batch_id": batch} for row in story["event_orders"]],
        "work_orders": [{**row, "ingest_batch_id": batch} for row in story["work_orders"]],
        "readings": _readings(as_of, story["isolations"], rng, batch)
                    + _event_readings(as_of, story["event_orders"], story["isolations"], rng, batch),
        "event_power": [{"eo_id": next(row["eo_id"] for row in story["event_orders"] if row["title"] == title), "asset_id": socket_id,
                         "use": use, "ingest_batch_id": batch} for title, uses in SOCKET_USE.items() for socket_id, use, _ in uses],
        "rooms": [{"room_id": room, "name": name, "seats": seats, "location": None} for room, name, seats in ROOMS],
        "room_bookings": _bookings(as_of, batch),
    }
    data["ingest_batches"][0]["row_count"] = sum(len(rows) for table, rows in data.items() if table not in {"site_meta", "ingest_batches"})
    return data


REFERENCE = ("zones", "contractors", "assets", "asset_aliases", "rooms")   # replaced by key on every build
SEEDED = ("readings", "work_orders", "event_orders", "ptws", "room_bookings", "event_power")  # removed by seed batch, then reinserted


def build(path: Path | str | None = None, as_of: datetime | None = None, seed: int = SEED) -> str:
    """Refresh the seed's rows in one transaction. Rows from imported files (Excel, PDF) and rooms booked in SignalDesk
    are kept: a refresh never wipes them, a seed reading never overwrites an imported one at the same time, and a seed
    booking that would clash with a kept booking is left out."""
    data = generate(as_of or datetime.now(timezone.utc), seed)
    path = Path(path or site_db.DEFAULT_DB)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = site_db.connect(path)
    try:
        connection.execute("PRAGMA foreign_keys = OFF")
        with connection:
            old = [row[0] for row in connection.execute("SELECT batch_id FROM ingest_batches WHERE source_type = 'seed'")]
            for batch in old:
                connection.execute("DELETE FROM ptw_impacts WHERE ptw_id IN (SELECT ptw_id FROM ptws WHERE ingest_batch_id = ?)", (batch,))
                for table in SEEDED:
                    connection.execute(f"DELETE FROM {table} WHERE ingest_batch_id = ?", (batch,))
                connection.execute("DELETE FROM ingest_batches WHERE batch_id = ?", (batch,))
            kept = connection.execute("SELECT room_id, start_at, end_at FROM room_bookings WHERE cancelled_at IS NULL").fetchall()
            data["room_bookings"] = [row for row in data["room_bookings"] if not any(
                room == row["room_id"] and start < row["end_at"] and row["start_at"] < end for room, start, end in kept)]
            connection.execute("DELETE FROM site_meta")
            site_db.insert(connection, "site_meta", data["site_meta"])
            site_db.insert(connection, "ingest_batches", data["ingest_batches"])
            for table in REFERENCE:
                site_db.insert(connection, table, data[table], mode="replace")
            listed = [row["asset_id"] for row in data["assets"]]  # drop seed assets the seed no longer lists, unless imported readings use them
            marks = ",".join("?" * len(listed))
            gone = [row[0] for row in connection.execute(
                f"SELECT asset_id FROM assets WHERE ingest_batch_id LIKE 'seed-%' AND asset_id NOT IN ({marks}) "
                "AND asset_id NOT IN (SELECT asset_id FROM readings)", listed)]
            for table in ("asset_aliases", "work_orders", "event_power", "assets"):
                connection.executemany(f"DELETE FROM {table} WHERE asset_id = ?", [(aid,) for aid in gone])
            for table in (*SEEDED, "ptw_impacts"):
                site_db.insert(connection, table, data[table], mode="ignore")
    finally:
        connection.close()
    return data["site_meta"][0]["value"]


def ensure_fresh(max_age_hours: float = 6, path: Path | str | None = None, now: datetime | None = None) -> str:
    """Regenerate when the data is missing, older than ``max_age_hours`` or from an older seed, so a demo never opens on
    stale works or without a newer table's rows."""
    now = now or datetime.now(timezone.utc)
    try:
        current, version = site_db.meta("as_of", path), site_db.meta("seed_version", path)
    except sqlite3.Error:  # unreadable file: rebuild it
        current = version = None
    if current is None or version != SEED_VERSION or now - datetime.fromisoformat(current) > timedelta(hours=max_age_hours):
        return build(path, now)
    return current


if __name__ == "__main__":
    print("site data as of", build())
