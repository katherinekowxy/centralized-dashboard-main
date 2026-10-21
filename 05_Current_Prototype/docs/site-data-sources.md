# How sources feed the site database

Dan asked for "a way to connect those api hoses into the system". This page explains how that works. It is for Dan, and later for IT and the vendors whose systems we connect.

**Status, 12 October 2026.** Nothing is connected to a real system. All data is synthetic. Two importers work today, on synthetic sample files: electrical readings from Excel, and permits to work (PTWs) from PDF. Every other source is filled by the synthetic seed (`demo/site_seed.py`).

## The rule

Sources feed the database, and everything else works from the database (Dan, 10 October 2026, `AGENTS.md` §6).

- Source systems are read only by importers or connectors, and only these write to the database.
- The dashboards read only the database, through `demo/site_db.py`.
- AI agents never call vendor or building-system APIs. In Dan's words: "i dont want the agent in the repo to go digging around their stuff through the api."

## The path

```
 Source system             Importer or connector         Checks              Database                    Dashboards
 (GBTB or vendor)          (the only writers)                                data/site.sqlite3           (read only)

 Energy meters ─ Excel ──▶ demo/ingest_excel.py    ──┐
               ─ API* ───▶ meter connector*        ──┤
 Permit system ─ PDF ────▶ demo/ingest_ptw_pdf.py  ──┼─▶ every row valid? ─▶ tables                 ─▶ site_db.py ─▶ PTW dashboard
               ─ API* ───▶ permit connector*       ──┤   yes: save all       + ingest_batches                      Asset dashboard
 CMMS, events, ─ seed ───▶ demo/site_seed.py       ──┘   no: save nothing    (file, SHA-256, time)                 Calendar overview
 contractors, assets, zones

 * Planned. Connectors run in an ingestion service outside this repository, and only that service holds credentials.
```

## Sources, today and later

| Source | What it gives us | Tables | Today | Later |
| --- | --- | --- | --- | --- |
| Electrical meters | Voltage, current, power, energy, power factor, trip state | `readings` | Excel export, `demo/ingest_excel.py` | Energy-management (EMS) or BMS API |
| Permits to work | Permits, and what each one isolates or closes | `ptws`, `ptw_impacts` | PDF, `demo/ingest_ptw_pdf.py` (synthetic template only) | Permit-system API |
| CMMS work orders | Scheduled maintenance | `work_orders` | Seed only | CMMS API or scheduled export |
| Event orders (bookings) | Events by zone, times, guest numbers | `event_orders` | Seed only | Booking-system export or API |
| Contractor register | Company names, colours, logos | `contractors` | Seed only | Register spreadsheet or procurement system |
| Assets and zones | What exists, where, and what feeds what | `assets`, `asset_aliases`, `zones` | Seed; zone outlines from `assets/maps/bay-south-zones.geojson` (mostly OpenStreetMap) | Asset register from the CMMS; zone outlines from GBTB's own site plans or GIS, if available |
| Event power | OG box and CEEform socket loads; which sockets each event uses | `readings`, `event_power` | Seed only | Sub-meters on each OG box and socket through the EMS; socket bookings from the event order or the event-sales system |
| Meeting rooms | Rooms, and who has booked them when | `rooms`, `room_bookings` | Booked in SignalDesk on the Meeting rooms tab; the seed fills a sample week | If rooms are already booked elsewhere (for example Outlook room calendars), either SignalDesk becomes the place to book, or it shows that system's bookings read-only. Writing bookings back to another system is Dan's call |

## What every import does

1. **Read** the file, or later the API response.
2. **Map identities.** Turn the source's names into ours through aliases (next section).
3. **Check every row.** One bad row refuses the whole file, and the preview lists every bad row at once.
4. **Save** in one transaction, with an `ingest_batches` row.
5. **Show.** The dashboards pick it up from the database.

Every import runs in two steps: **preview** (check only, nothing saved), then **commit** (check again, then save). The commit re-checks because the database may have changed since the preview.

**Provenance.** Every saved row carries `ingest_batch_id`. The batch row records:

| Column | Example |
| --- | --- |
| `batch_id` | `excel-20261012-001`, `pdf-20261012-002`: the source, the SGT date of receipt, and the next free number that day |
| `source_type` | `excel`, `pdf`, `api` or `seed` |
| `file_name` | `electrical-sample.xlsx` |
| `sha256` | The file's fingerprint, used to spot the same file sent twice |
| `received_at` | When it was saved (UTC) |
| `row_count` | Rows this batch wrote |

A PTW also keeps the path of its PDF in `ptws.source_file`, so the original can be opened from the record.

## Identity: aliases

Each source has its own names for things. We keep our IDs ([site-naming.md](site-naming.md)) and store each source's name as an **alias**.

| Their name (`alias`) | Our asset (`asset_id`) | Source (`system`) |
| --- | --- | --- |
| `EMS-FDMAHU01` | `FDM-AHU-01` | Energy meters (synthetic) |

- An unknown name is refused. It is never guessed, and never creates a new asset.
- Connecting a new meter means adding one alias row.
- Matching ignores upper and lower case. If one name points at two assets, it is refused.
- Permits name zones and contractors by our codes today. Real permits will probably say "Flower Dome" or a company name, so they will need the same alias idea for zones and contractors. That table does not exist yet.

## Time

- **Stored** in UTC, for example `2026-10-14T01:00:00+00:00`.
- **Shown** in Singapore time, labelled "SGT" (UTC+8, with no daylight saving).
- **Every incoming time must state its offset**, for example `2026-10-14T09:00:00+08:00`. Without one, the file is refused. A wrong guess would shift a reading by 8 hours without anyone noticing.
- **Excel date cells are refused**, because an .xlsx date carries no time zone. Timestamps go in as text.
- If a real export writes SGT times without an offset, that source's connector adds `+08:00` as a written rule for that source. The importer never guesses.
- "Now" on the dashboards is `site_meta.as_of`, never the wall clock. Today that is the seed's time; see [site-data-contract.md](site-data-contract.md).

## Duplicates and re-imports

| Case | Result |
| --- | --- |
| The same file again (same SHA-256) | Nothing new is saved, and the earlier batch ID comes back |
| A reading already saved, with the same value | Skipped and counted |
| A reading already saved by another file, with a different value | The file is refused as a conflict; a correction needs a deliberate fix |
| A reading at the same time as a seed reading | The imported value replaces the seed's. Demo only: the seed stands in for real data. |
| The same reading twice in one file | The second copy is skipped; if the two values differ, the file is refused |
| A permit number that already exists, from the same file | Skipped |
| A permit number that already exists, from another file or the seed | Refused |
| The seed refresh (every 6 hours) | Keeps every imported row, and never overwrites an imported reading |

## What gets a file refused

### Electrical Excel (`demo/ingest_excel.py`)

**Layout.** The importer reads the sheet named `readings`, or the first sheet if there isn't one. It looks for a header row with exactly `meter_ref`, `timestamp`, `point`, `value` and `unit` (any order and case) in the first 10 rows. Title lines above the header are ignored.

| Rule | Refused when |
| --- | --- |
| File | It is empty, not a readable .xlsx (a CSV renamed .xlsx, say), over 20 MB, or over 100,000 rows |
| Columns | A column is missing, repeated or extra, or a value sits under a blank heading |
| `meter_ref` | It is empty, or not an alias in `asset_aliases` |
| `timestamp` | It has no offset, is an Excel date cell or a number, isn't ISO 8601, is before 2000, or is more than 15 minutes in the future (usually a wrong offset) |
| `point` and `unit` | `voltage_v` V, `current_a` A, `power_kw` kW, `energy_kwh` kWh, `power_factor` (unit empty), `trip_state` `state`. Anything else is refused, and so is `KW` for `kW`. |
| `value` | It is empty, text, TRUE/FALSE or not finite, or outside its range: voltage 0–300 V (phase), current 0–5,000 A, power 0–5,000 kW, energy 0–1,000,000,000 kWh, power factor 0–1, trip state exactly 0 or 1 |
| Conflicts | Same meter, point and time as a reading from another file, or as another row in this file, with a different value |

Each bad row gets one message listing all of its problems. Row numbers are Excel's own.

### Permit PDF (`demo/ingest_ptw_pdf.py`)

The importer reads only the synthetic template **SD-PTW-1**, which is drawn by `ingest_ptw_pdf.render_pdf`:

```
 SYNTHETIC SAMPLE banner                          ignored
 PERMIT TO WORK
 SignalDesk permit-to-work template SD-PTW-1      required: names the template
 Permit number:  PTW-2026-0901
 Zone code:      ACT
 Contractor ID:  CTR-NWD
 Title:          Active Garden outlet replacement
 Work type:      electrical
 Start:          2026-10-14 09:00+08:00
 End:            2026-10-14 17:00+08:00
 Affected (one line per impact)
 Kind | Target type | Target ID | Effect | Summary | Start | End
 electrical | asset | ACT-OUT-01 | isolated | Outlets isolated | - | -
 physical | route | Active Garden east path | closed | East path closed | 2026-10-14 09:00+08:00 | 2026-10-14 13:00+08:00
 End of permit SD-PTW-1                           required: proves the text was read to the end
```

A `-` for an impact's Start or End means the permit's own window.

| Rule | Refused when |
| --- | --- |
| File | It is not a PDF, is damaged or cut short, is over 10 MB, or has no text layer (a scan: this importer does no OCR) |
| Template | The SD-PTW-1 line, the Affected section, its column line or the closing line is missing |
| Permit number | It is missing or not `PTW-YYYY-NNNN`, or it already exists from another file or the seed |
| Zone, contractor | The code is not in `zones` or `contractors` |
| Title | It is missing or longer than 6 words |
| Work type | It is not `electrical`, `mechanical`, `civil`, `hot_work`, `height` or `landscape` |
| Start, End | Either has no offset or isn't ISO 8601, or End is not after Start |
| Impacts | There are none, or a line hasn't got 7 fields separated by `\|` |
| Each impact | `electrical` must target an `asset` and be `isolated` or `down`. `physical` targets an `asset`, `zone` or `route` (free text, up to 60 characters) and is `closed` or `restricted`. An asset or zone must exist. The summary must be 1–6 words. The window must sit inside the permit's. The same target can't be listed twice. |

## When data stops: Offline

- On the Asset dashboard, an asset is **Offline** (grey) when it has no reading in the 30 minutes before "now". Grey means the state is unknown, not that the asset is broken.
- Today "now" is the seed's time, and the seed rebuilds after 6 hours, so the demo never goes stale on its own.
- With live feeds, "now" becomes the clock. A meter feed that stops then turns its assets grey after 30 minutes.
- **Suggested, not built:** a "last received" time for each source, taken from `ingest_batches.received_at`. A stopped feed would then show as one clear message, not as many grey boxes. Permits and events don't go Offline, but an old "last received" time would show that their feed has stopped.

## Future APIs: what we need from each vendor or IT

### Push or pull

| | Pull (we ask) | Push (they send) |
| --- | --- | --- |
| How | Our ingestion service calls their API on a timer | Their system calls our endpoint (a webhook) when something changes |
| Good for | Regular readings; systems that can't send | Changes that matter at once: a permit issued, extended or closed |
| Network | Outbound only, which firewalls usually allow | Needs an inbound endpoint that IT exposes and protects |
| If it fails | The next poll catches up | Events can be lost, so add a nightly pull to reconcile |

### Per source

| Source | Suggested | Cadence | Maps to |
| --- | --- | --- | --- |
| EMS or BMS meters | Pull | Every 15 minutes, matching the meters | `readings`, through `asset_aliases` |
| Permit system | Push, plus a nightly pull | When a permit is issued, changed or closed | `ptws`, `ptw_impacts` |
| CMMS work orders | Pull | Hourly | `work_orders` |
| Event bookings | Pull | Hourly or daily | `event_orders` |
| Contractor register | Pull | Daily, or when it changes | `contractors` |
| Asset register | Pull | Daily, or when it changes | `assets`, `asset_aliases` |
| Room calendars, if used | Pull | Every few minutes, so a room never shows free when it isn't | `room_bookings` |

### Checklist for each API

| We need | Why |
| --- | --- |
| Endpoint and API documentation | To know what to call and what comes back |
| Authentication method, set up for the ingestion service by IT | Credentials never enter this repository |
| A read-only account, scoped to the data we need | So that we can read and never change anything |
| Cadence, rate limits, or webhook events | To set the polling interval, or which events to subscribe to |
| Field mapping to our tables, with example responses | To write the connector: their tag to our alias, their time to UTC with an offset |
| How they mark a change or a cancellation | Permits get extended and cancelled; readings get corrected |
| A test sandbox with fake data | To build and test without touching live systems |
| A named contact | For outages and changes to the API |

## Security boundary

- **Credentials live only in the ingestion service**, which IT runs outside this repository. They are never in the repo, its config files, environment files or any AI prompt.
- **Read-only accounts.** SignalDesk never writes back to a source system. It has no plant controls and takes no external actions (`AGENTS.md` §6).
- **One way in.** The ingestion service saves only through the same checks as the importers. A connector that skips them is a bug.
- **Agents never call vendor or building-system APIs.** Dan: "i dont want the agent in the repo to go digging around their stuff through the api."
- **The dashboards read only the database.** The one write is a meeting room booking, saved in SignalDesk's own database, never in a source system.
- **Keep only the fields we use.** Names and phone numbers of permit signatories stay in the permit system. We store the permit, its contractor company and what it affects. A room booking stores only the name or team typed by the person booking.

## Parsing real PTW PDFs: what we would need

The real Gardens by the Bay permit layout is unknown, so the importer reads only the synthetic SD-PTW-1 template. A real parser needs:

1. **Redacted samples.** Three to five real permits for each form in use, with names, phone numbers and signatures blacked out. Include a long one, an extended or amended one, and a cancelled one.
2. **Generated or scanned?** A PDF made by a permit system has text that can be read reliably. A scanned paper form needs OCR, which makes mistakes, so every permit would need checking by a person.
3. **Where each field lives:** permit number, location, contractor, description, work type, validity start and end, the isolation list, and any closures.
4. **How location is written** (free text or a code), so that we can build a location-to-zone alias table.
5. **How isolations are written** (equipment tags or descriptions), so that they map to asset aliases.
6. **The time format.** Real permits probably print SGT without an offset. The parser for that form would add `+08:00` as a written rule.
7. **Layout varies by template.** Each form, and each revision of a form, needs its own parser profile. An unknown layout is refused, never guessed.

A data export or API from the permit system would be more reliable than any PDF parser, and should be asked about first.

## How to run the importers today

From `05_Current_Prototype`:

```
python data/examples/site/make_samples.py              # rebuild the four sample files (byte-identical each time)
python -m demo.site_seed                                # build or refresh data/site.sqlite3 (the app also does this at start-up)

python -m demo.ingest_excel data/examples/site/electrical-sample.xlsx            # preview: nothing saved
python -m demo.ingest_excel data/examples/site/electrical-sample.xlsx --commit   # save
python -m demo.ingest_excel data/examples/site/electrical-bad-sample.xlsx        # shows the three refused rows

python -m demo.ingest_ptw_pdf data/examples/site/PTW-2026-0901.pdf               # preview
python -m demo.ingest_ptw_pdf data/examples/site/PTW-2026-0901.pdf --commit      # save
```

- `--db PATH` uses another database. A new one needs building first, for example `python -c "from demo import site_seed; site_seed.build('data/scratch.sqlite3')"`, so that the aliases, zones and contractors exist.
- Saving into `data/site.sqlite3` puts the sample permits (14–16 October 2026) on the live dashboards.
- Keep a PDF where it is after importing, because its path is stored.

From Python, for example for an upload screen:

```python
from demo import ingest_excel, ingest_ptw_pdf

check = ingest_excel.preview(uploaded_file)            # path, bytes, or a Streamlit upload
# check["rows"], check["errors"] ({"row", "message"}), check["total_rows"]
saved = ingest_excel.commit(uploaded_file, "meters.xlsx")  # {"batch_id", "saved", "skipped", ...}, or raises ExcelImportError

check = ingest_ptw_pdf.preview("path/to/PTW.pdf")      # {"ptw", "impacts", "errors": [{"field", "message"}], "status"}
saved = ingest_ptw_pdf.commit("path/to/PTW.pdf")       # {"batch_id", "ptw_id", "saved", "skipped", ...}, or raises PtwImportError
```

## Files

| File | What it is |
| --- | --- |
| `demo/ingest_excel.py` | Electrical Excel importer, plus the time and batch-number rules shared by both importers |
| `demo/ingest_ptw_pdf.py` | PTW PDF importer, and the SD-PTW-1 template drawer used for the samples |
| `data/examples/site/make_samples.py` | Builds the sample files below |
| `data/examples/site/electrical-sample.xlsx` | 2 hours of 15-minute readings for three seed assets (9 October 2026, 08:00–10:00 SGT) |
| `data/examples/site/electrical-bad-sample.xlsx` | A naive timestamp, an unknown meter and a power factor of 1.4: refused |
| `data/examples/site/PTW-2026-0901.pdf` | An electrical isolation of an asset, plus a path closure |
| `data/examples/site/PTW-2026-0902.pdf` | One physical restriction, on Meadow Bridge |
| `tests/test_ingest_excel.py`, `tests/test_ingest_ptw_pdf.py` | Every rule above, tested |
