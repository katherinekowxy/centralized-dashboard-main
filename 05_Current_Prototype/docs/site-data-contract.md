# Site dashboards: data contract

Written by Claude (orchestrator) on 10 October 2026 for Claude and Codex. Names follow [site-naming.md](site-naming.md). The data flow is source files (later APIs) → ingest → database → dashboards (`AGENTS.md` §6). Everything is synthetic except the map.

## Time

- **Storage:** UTC, as ISO 8601 with offset.
- **Display:** Singapore time, labelled "SGT".
- **"Now":** the dashboards use `site_meta.as_of`, never the wall clock. The seed sets `as_of` to the real current time, rounded down to 15 minutes, so "today" always has work on it. Meeting rooms is the exception: a booking is for real time, so it uses the wall clock.
- **Freshness:** at start-up the app calls `site_seed.ensure_fresh(max_age_hours=6)`. If the data is older than that, or was made by an older seed (`site_meta.seed_version`), it regenerates (deterministic seed), so a demo the next morning is never all Offline.
- **Labelling:** every dashboard says "Synthetic data · generated HH:MM SGT".

## Database: `data/site.sqlite3`

| Table | Columns (key first) |
| --- | --- |
| `site_meta` | `key`, `value`. Keys: `as_of`, `generated_at`, `seed`, `seed_version` |
| `zones` | `zone_code`, `name`, `map_no` (null if unnumbered), `kind` (`garden`, `conservatory`, `bridge`, `lake`, `plaza` or `structure`), `x0`, `y0`, `x1`, `y1` (box in map pixels). Loaded from `assets/maps/bay-south-zones.json` (Claude) |
| `contractors` | `contractor_id`, `name`, `short_name`, `colour` (hex), `logo_svg` (null means the dashboard draws a monogram) |
| `assets` | `asset_id`, `name`, `zone_code`, `asset_type`, `criticality` (`high`, `medium` or `low`), `fed_from` (parent `asset_id` on the electrical side, for example outlets fed from a DB; null otherwise), `rated_current_a`, `idle_current_a` (below this the asset counts as not running), `operating_hours` (`HH:MM-HH:MM` SGT, `24h`, or `on demand` for OG boxes and sockets: no load is Idle, never Down), `connected` (1 when SignalDesk receives its readings; 0 for a device in the register only, which has no state), `phases` (1 or 3; set for OG boxes and sockets), `ingest_batch_id` |
| `readings` | `asset_id`, `point_id`, `observed_at`, `value`, `unit`, `ingest_batch_id`. Key is (`asset_id`, `point_id`, `observed_at`). Points: `voltage_v`, `current_a`, `power_kw`, `energy_kwh`, `power_factor`, `trip_state` (0 or 1). 15-minute cadence, 7 days up to `as_of` |
| `ptws` | `ptw_id`, `zone_code`, `contractor_id`, `title` (6 words or fewer), `work_type` (`electrical`, `mechanical`, `civil`, `hot_work`, `height` or `landscape`), `start_at`, `end_at`, `source_file` (path to its PDF, null if none), `ingest_batch_id` |
| `ptw_impacts` | `impact_id` (`<ptw_id>/<n>`), `ptw_id`, `kind` (`electrical` or `physical`), `target_type` (`asset`, `zone` or `route`), `target_id`, `effect` (`isolated`, `down`, `closed` or `restricted`), `summary` (6 words or fewer, for example "3 outlets down"), `start_at`, `end_at` |
| `event_orders` | `eo_id`, `zone_code`, `title`, `start_at`, `end_at`, `organiser`, `expected_guests` (nullable), `ingest_batch_id` |
| `work_orders` | `wo_id`, `asset_id`, `title`, `scheduled_start`, `scheduled_end`, `status` (`scheduled`, `in_progress` or `done`), `ptw_id` (nullable), `ingest_batch_id` |
| `ingest_batches` | `batch_id`, `source_type` (`excel`, `pdf`, `api` or `seed`), `file_name`, `sha256`, `received_at`, `row_count` |
| `event_power` | `eo_id`, `asset_id` (a CEEform socket), `use` (what the event powers from it, for example "Stage lighting"), `ingest_batch_id`. Key is (`eo_id`, `asset_id`) |
| `rooms` | `room_id`, `name`, `seats`, `location` (nullable). Two fictional rooms for now |
| `room_bookings` | `booking_id`, `room_id`, `title`, `booked_by` (a name or team), `start_at`, `end_at`, `source` (`signaldesk` or `seed`; later a calendar system), `created_at`, `cancelled_at` (null while booked; a cancelled row is kept), `ingest_batch_id` (seed rows only) |

## Read API: `demo/site_db.py` (Codex)

Plain functions return `list[dict]` or `dict`, with times as ISO strings. Dashboards use only these, never SQL.

```python
connect(path=None) -> sqlite3.Connection
as_of() -> str
zones() -> list[dict]
contractors() -> list[dict]
assets() -> list[dict]
latest_readings() -> dict[str, dict[str, dict]]          # asset_id -> point_id -> {value, unit, observed_at}
readings(asset_id, start, end) -> list[dict]
ptws(active_at=None, start=None, end=None) -> list[dict] # active at an instant, or overlapping a window; joined with contractor and zone
ptw(ptw_id) -> dict | None                                # plus "impacts": [...]
impacts(active_at=None) -> list[dict]
work_orders(start, end, asset_id=None) -> list[dict]
event_orders(start, end) -> list[dict]
event_power(start=None, end=None) -> list[dict]          # socket bookings of events overlapping a window, with each event's title and times
rooms() -> list[dict]
room_bookings(start, end, room_id=None) -> list[dict]       # overlapping a window, cancelled ones left out
book_room(room_id, start, end, title, booked_by) -> dict    # raises BookingClash (a ValueError) if the room is taken
cancel_booking(booking_id) -> bool
```

`book_room` and `cancel_booking` are the only writes from a dashboard. The clash check and the insert share one write lock, so two people can't book the same slot. A reseed keeps bookings made in SignalDesk and drops any seed booking that would clash with one.

## Asset state: `demo/asset_state.py` (Claude)

A pure function of the asset record, its latest readings and `as_of`. Rules, applied in this order:

| State | Rule |
| --- | --- |
| Offline | No reading in the last 30 minutes |
| Down | `trip_state` = 1, or current below `idle_current_a` during `operating_hours` |
| Warning | Running, and one of: voltage outside 216–253 V (230 V −6 %/+10 %), current above `rated_current_a`, or power factor below 0.80 |
| Idle | Current below `idle_current_a` outside operating hours |
| Operational | Running, and no warning rule applies |

**Cone:** shown when the asset has a work order today (SGT) that isn't `done`, or is the target of an active PTW impact. The colour still shows the state, so an isolated asset is red with a cone.

**Orbs:** on Down and Warning boxes only.

## Seed: `demo/site_seed.py` (Codex)

Deterministic. The synthetic data must be plausible for Bay South:
- **About 30 assets across 10 or more zones:** conservatory chillers and air handlers (FDM, CFR), Cloud Forest misting, Supertree lighting and distribution boards with outlet groups (SGV), Skyway lifts (SKY), lake pumps (DFL, KFW), Silver Garden fountain and DB (SLV), plaza DB and outlets (BFP).
- **State mix at `as_of`:** about 22 Operational, 3 Idle, 2 Warning, 2 Down (one tripped, one isolated by a PTW) and 1 Offline.
- **6 contractors:** clearly fictional names, distinct colours and monograms.
- **PTWs:** 4–6 active now, including:
  - SGV electrical: "DB-03 isolated", with an impact of "3 outlets down" on the outlet group fed from that DB;
  - a physical closure, such as Dragonfly Bridge closed from one time to another.

  Add more over the past and next 14 days for the calendar, and every active PTW gets at least one impact.
- **Event orders:** about 8 over 14 days. At least one overlaps an active PTW in the same zone, so the calendar can show a clash.
- **Work orders:** about 15 over 14 days, 2–3 of them today, some linked to PTWs.
- **Feeds:** every device hangs off a DB through `fed_from`, for the Asset schematic. Seven DBs and eight end devices are in the register but not connected (`site_seed.UNCONNECTED`); they have no readings.
- **Event power:** five OG boxes (`OG_BOXES`), each with 4–5 CEEform sockets (`OGB` and `CEE` assets). Events book sockets (`SOCKET_USE`). Loads follow those bookings, a third of full in the hour before each event. Two events run now: a Music festival at The Meadow and a Pop-up market at Active Garden. Story: the festival bar socket has tripped; the market's food stalls draw 110 % of their 16 A socket; the Grove OG box hangs off the isolated Grove DB 3, so it has no supply when the Corporate reception's setup starts. OG boxes and sockets stay off the Asset dashboard and Asset schematic.
- **Readings:** consistent with the intended states. For example, the isolated asset reads about 0 A from the PTW start, and the Offline asset's readings stop 2 hours before `as_of`.

## Ingest (Codex)

The demo database is filled by the seed. These two importers prove the real path, using synthetic sample files in `data/examples/site/`.

- **`ingest_excel.py`:** reads an electrical `.xlsx` export with columns `meter_ref`, `timestamp`, `point`, `value` and `unit`.
  - Timestamps need an offset; `meter_ref` maps to an `asset_id` through an alias table.
  - A file with any bad row is refused, as with the existing CSV import.
  - The file is recorded as an `ingest_batch`.
- **`ingest_ptw_pdf.py`:** parses a synthetic PTW PDF made from one fixed template, writing `ptws` and `ptw_impacts` and keeping the PDF path in `source_file`.
  - The real Gardens by the Bay PTW layout is unknown, so the README explains what a real parser would need. A redacted sample from Dan would be the first step.
- Libraries `openpyxl`, `pypdf`, `pdfplumber` and `PyMuPDF` are installed but not pinned. Pin whatever you use in `requirements.txt`.

## Dashboard modules and routing

- Each dashboard module exposes `render()` and reads only `site_db`.
- **Detail pages:** `?ptw=<ptw_id>` opens the PTW page and `?asset=<asset_id>` opens the asset page, each in a new tab.
- **Sidebar:** grouped into **Site** and **Diagnostics demo**.
- Claude owns `app.py` navigation and routing for this work and will wire `calendar_overview.render()`.

## Calendar overview: design brief (Codex builds)

The goal is information at a glance with minimal words; details appear on click.
- **Default view:** this week, Monday to Sunday, with a "today" marker.
  - One row per zone that has anything on.
  - Bars span each item's start to end.
  - Filters for week and item type sit in one row above the grid.
- **PTW bars:** outlined in the contractor's colour, with its monogram or logo, and the PTW number only.
- **Event bars:** neutral white outline with a star icon. **Maintenance bars:** neutral grey with a cone icon. Never use the five state colours here.
- **Clash marker:** where a PTW and an event overlap in the same zone, show a small "Clash" chip on both bars. This is the most useful thing the calendar can show.
- **Click:** opens the PTW page (`?ptw=`), or the event or work-order record, in a new tab.
- **Phones:** a list by day, the same items in time order.
- **Tests:** week boundaries in SGT, clash detection, and empty weeks.

## Ownership

| Owner | Files |
| --- | --- |
| Claude (reassigned from Codex by Dan, 12 October 2026: "handover codex share to you") | `demo/site_db.py`, `demo/site_seed.py`, `demo/calendar_overview.py`; through one subagent, `demo/ingest_excel.py`, `demo/ingest_ptw_pdf.py`, `data/examples/site/`, `docs/site-data-sources.md`; their tests |
| Claude | `assets/maps/bay-south-zones.json`, `demo/asset_state.py`, `demo/ptw_dashboard.py`, `demo/asset_dashboard.py`, `demo/asset_schematic.py`, `demo/event_power.py`, `demo/room_booking.py`, `app.py` navigation and routing, their tests, visual review |

**Calendar as built:** days are columns and each item is a labelled chip in its day; multi-day items span their days. This replaced an hour-proportional layout whose bars were too narrow to read. Detail tabs are `?eo=<id>` for an event order and `?wo=<id>` for a work order.

Until `site_db` lands, Claude builds against a small fixture with the same shapes.
