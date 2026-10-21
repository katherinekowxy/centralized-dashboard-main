# Site dashboards: naming convention

**Status:** approved by Dan, 10 October 2026. Every module, table, ID and label in the site dashboards uses these names. Dan added the fourth, Meeting rooms, on 12 October 2026.

All IDs are synthetic. Gardens by the Bay has its own tag formats, but Dan chose not to use them yet. When real systems are connected, their IDs are stored as aliases, never replaced.

Dan's other decisions on 10 October:
- **Orbs:** two orbs of the state colour trace the box outline, on **Down and Warning boxes only**.
- **Cone:** one pulsing cone sits on an asset box while it has maintenance today or a permit active. The schedule details live only in the Calendar overview.
- **Sidebar:** grouped into **Site** and **Diagnostics demo**.
- **New tab:** clicking an item opens it in a new browser tab.

## Dashboards

| Sidebar name | Shows at a glance | Colour means | Click opens (new tab) |
| --- | --- | --- | --- |
| **PTW dashboard** | A street map of Bay South (OpenStreetMap). Each permit today fills its zone in the contractor's colour, with logo, work and time written on the box | Contractor (brand colour and logo) | PTW page: what is affected, electrical and physical |
| **Asset dashboard** | One box per asset, grouped by zone | Machine state (five colours below) | Asset page: electrical readings |
| **Asset schematic** | The same assets as a rough one-line diagram: each DB, by zone, with the devices it feeds tapped off a feed line. Also shows devices SignalDesk isn't connected to. An alternative to the Asset dashboard, so staff can choose (Dan, 12 October 2026) | Machine state, as on the Asset dashboard. A hollow dashed box is a device that isn't connected. A red dashed feed line means its DB is down | The same asset page. A device that isn't connected doesn't open |
| **Event power** | The OG boxes events plug into. Each panel shows the DB feeding the box, the box's total load, and a busbar to its CEEform sockets. Each socket shows its amps against its rating and what the event uses it for (Dan, 13 October 2026) | Machine-state colours with socket words: In use (green), Free (blue), Warning (orange), Tripped (red), Offline (grey). "No supply" (red dashed) means the box's DB is down | A box or socket opens the asset page; an event opens its event order |
| **Calendar overview** | Active PTWs, event orders and scheduled maintenance, by day | PTWs by contractor; events and maintenance are neutral, with an icon | The same PTW page, or the event or maintenance record |
| **Meeting rooms** | One calendar per room, side by side, one day at a time (08:00 to 19:00). Each booking shows the meeting, time and who booked it; empty space is free | One accent colour for every booking; no state or contractor colours | Nothing opens. **Book** and **Cancel a booking** open a dialog on the same page |

Each dashboard has only one colour meaning, so contractor colours and state colours never share a screen. Where they meet, for example in the list of affected assets on a PTW page, the state is shown as a word.

## Asset states

| State | Colour | Rule (deterministic, never predictive) |
| --- | --- | --- |
| Operational | green `#22C55E` | Running, data current, no fault |
| Idle | blue `#2563EB` | Powered, not running (standby, or outside operating hours) |
| Warning | orange `#F59E0B` | Running, but a fixed rule found a problem; the machine is still safe to operate |
| Down | red `#EF4444` | Tripped or faulted, or not running during operating hours when it should be |
| Offline | grey `#9CA3AF` | No data received, so the state is unknown |

**Not connected** is not a state. The device is in the asset register, but SignalDesk gets no readings from it (`assets.connected` = 0). Only the Asset schematic shows it, as a hollow dashed box saying "Not connected". Grey stays Offline: connected, but no recent data.

Every box also carries its state as a word. Green, orange and red are hard to tell apart for colour-blind viewers (validator ΔE 5.7), so the colour can't be the only signal.

## Zones (names and numbers from the official map)

| Code | Zone | Map no. |
| --- | --- | --- |
| `GLD` | Golden Garden | 1 |
| `CNP` | The Canopy | 2 |
| `FDM` | Flower Dome | 3 |
| `CFR` | Cloud Forest | 4 |
| `FCK` | Floral Clock | 5 |
| `SGV` | Supertree Grove | 6 |
| `SKY` | OCBC Skyway | 7 |
| `SOB` | Supertree Observatory | 8 |
| `WOP` | World of Plants | 9–14 |
| `HER` | Heritage Gardens | 15–18 |
| `MDW` | The Meadow | 20 |
| `SRN` | Serene Garden | 21 |
| `CHG` | Far East Organization Children's Garden | 23 |
| `CYN` | The Canyon | 24 |
| `SLV` | Silver Garden | 25 |
| `FFN` | Floral Fantasy | 26 |
| `ACT` | Active Garden | 27 |
| `KFW` | Kingfisher Wetlands | 28 |
| `DFB` | Dragonfly Bridge | n/a |
| `MDB` | Meadow Bridge | n/a |
| `DFL` | Dragonfly Lake | n/a |
| `BFP` | Bayfront Plaza | n/a |
| `ENT` | Main Entrance | n/a |

Zone positions on the map are pixel boxes in `assets/maps/bay-south-zones.json`, measured on `static/maps/gbtb-bay-south-2026-02-15.jpg`.

## IDs

| Thing | Format | Example |
| --- | --- | --- |
| Asset | `<ZONE>-<TYPE>-<NN>` | `FDM-AHU-01` (Flower Dome air handler CD-AHU-07) |
| Asset type | `CHL` chiller, `AHU` air handler, `PMP` pump, `DB` distribution board, `OUT` outlet group, `LGT` lighting, `LFT` lift, `MST` misting, `FTN` fountain, `OGB` OG box (outdoor power box for events), `CEE` CEEform socket | |
| CEEform socket | `<ZONE>-CEE-<NN>`, numbered per zone; named `<OG box> · socket <n>` and shown as S1 to S5 on its box | `MDW-CEE-07` (Meadow OG box 2 · socket 2) |
| Electrical point | snake_case with unit, as in the existing demo | `voltage_v`, `current_a`, `power_kw`, `energy_kwh`, `power_factor` |
| Permit to work | `PTW-YYYY-NNNN` | `PTW-2026-0142` |
| PTW impact | `<PTW>/<n>` | `PTW-2026-0142/1` |
| Event order | `EO-YYYY-NNNN` | `EO-2026-0031` |
| Scheduled maintenance | `WO-YYYY-NNNN` | `WO-2026-0457` |
| Contractor | `CTR-<3 letters>`, with a fictional name, colour and monogram logo for now | `CTR-NWD` Northwind M&E |
| Ingest batch | `<source>-<YYYYMMDD>-<NNN>` | `excel-20261010-001`, `pdf-20261010-004` |
| Meeting room | `MR-NN`, with a fictional name for now | `MR-01` Orchid Room |
| Room booking | `RB-NNNN` | `RB-0034` |

The existing replay demo keeps its own IDs (`DB-01`, `CMMS-0028`); they are a separate synthetic dataset.

## Database and files

- One SQLite database: `data/site.sqlite3`. Its tables are `zones`, `assets`, `contractors`, `ptws`, `ptw_impacts`, `event_orders`, `work_orders`, `readings`, `ingest_batches`, `event_power`, `rooms` and `room_bookings`.
- Every row that came from a source keeps its `ingest_batch_id`. The batch records the file name, SHA-256, source type (`excel`, `pdf` or `api`) and receipt time.
- The dashboards read only the database. Sources write only through the ingest layer (see `AGENTS.md` §6). The one exception is Meeting rooms, which writes bookings through `site_db.book_room` and `site_db.cancel_booking`.

| Purpose | Path |
| --- | --- |
| Database access | `demo/site_db.py` |
| Synthetic seed | `demo/site_seed.py` |
| Ingest: electrical Excel | `demo/ingest_excel.py` |
| Ingest: PTW PDF | `demo/ingest_ptw_pdf.py` |
| PTW dashboard | `demo/ptw_dashboard.py` |
| Asset dashboard | `demo/asset_dashboard.py` |
| Asset schematic | `demo/asset_schematic.py` |
| Event power | `demo/event_power.py` |
| Calendar overview | `demo/calendar_overview.py` |
| Meeting rooms | `demo/room_booking.py` |
| Map image (served) | `static/maps/` |
| Zone boxes and map source note | `assets/maps/` |
| How sources connect | `docs/site-data-sources.md` |

## Sidebar

- **Site:** PTW dashboard, Asset dashboard, Asset schematic, Event power, Calendar overview, Meeting rooms.
- **Diagnostics demo:** the existing seven pages. The grouping keeps "Asset overview" (the replay demo) apart from "Asset dashboard".
