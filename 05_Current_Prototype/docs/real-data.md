# Real data: adapters, column maps and limits

The app reads the client's Excel exports **read-only**, from a folder outside this repository. Set the folder with the `GBB_DATA_DIR` environment variable, or start the app with `.\start.ps1 -DataDir <folder>`. When the variable is unset, every page that needs real files says so. The synthetic demo data stays available either way.

All adapters live in `demo/sources/` and follow the same rules:

- **Explicit column maps.** Only the columns listed below are read.
- **Originals kept.** Each record carries its source file, its Excel row number, and the original text of every mapped column.
- **Nothing dropped silently.** Unusable rows are kept and listed in a validation report on the page, which can be downloaded as CSV.
- **Imported, not live.** Imported records are labelled "Imported … · not live" and are never mixed into synthetic counts.
- **No invented values.** A missing reading, coordinate or date is shown as unavailable.
- **No personal details.** Names, phone numbers, e-mail addresses and document links are not read.
- **No new storage.** There is no database, API or service. Files are cached in memory for ten minutes, or until they change.

## Validation issues

| Issue | Meaning |
| --- | --- |
| Missing file / Missing column | A file or a required column is absent. An optional column that is absent is reported but does not stop the file being read. |
| Blank required value | A required cell is empty. The row is kept. |
| Value could not be read | A date, time or code could not be parsed. The original text is shown. |
| End before start / Completed before reported | The window cannot be used. The record is listed as an exception. |
| Repeated row / Duplicate reference | Counted once. The repeat is listed. |
| Location not recognised / partly recognised | No known building, or some words left over (see PTW locations). |
| Value tidied | A harmless clean-up, such as removing spaces inside an asset tag. |
| Please check | Read as written, but probably a typo, such as listed days out of order. |
| Gap in the export | Four weeks or more with no fault reported. This is treated as missing data and never charted as zero. |

## Permits to work: `PERMIT-TO-WORK/*.xlsx` (`ptw_forms.py`)

| Field | Source column(s) | Required? | Notes |
| --- | --- | --- | --- |
| Reference | `Req. Ref.` | Yes | |
| Location | `Location` | Yes | Matched to buildings (below) |
| Start | `Start Date` + `Start Time` | Yes | Read as SGT |
| End | `End Date` + `End Time` | Yes | Read as SGT |
| Form type | `Portal` | No | The approver's name is removed |
| Other details | `Created Date`, `Company`, `Trade`, `Type`, `Description of Work`, `Please tick on the Relevant Job (Permit Required)`, `Approval Status` | No | A blank approval is shown as "No decision recorded" |
| Site | the file name, e.g. "(GBB Central)" | No | |

Not read: respondent, e-mail, phone numbers, personnel, sub-contractor contacts, worker names, signatures. Source file names still contain an approver's first name. They are kept because they are what a person needs to find the original row.

**Locations** (`locations.py`) are matched in three steps:

1. An exact match against the client's Power BI alias table (`assets/maps/ptw_location_aliases.csv`, 57 rows) and the building names.
2. Otherwise, whole-word matches inside multi-place text, longest name first.
3. Otherwise, the permit is listed as an exception.

Coordinates come from `Building Location.xlsx` and are all marked `Verified = No`. Buildings that share a coordinate are merged into one map point, so a permit is counted once there. A permit naming several buildings appears at each of them, but the totals count it once. Figures on 20 October 2026: 309 permits; 247 matched exactly, 53 matched by text, 9 not placed (Power BI also shows 9 "Not mapped").

The forms do **not** record affected assets, electrical isolations or downstream impact. Those fields belong to the synthetic site demo only. For imported permits they are shown as unavailable.

## Asset register: `Asset history.xlsx` (`registers.load_assets`)

- **Columns read:** Asset Tag Number (required), Description, System Type, Asset Category, Asset Status, Site, Building, Floor, Room, ID Type, ID, Building Trade, Trade Category, Date, Completed.
- **Shape:** each row is an asset plus one associated fault or schedule record, so records are grouped by tag.
- **Unusable tags:** a missing or "unknown" tag is reported and left out.
- **Conflicting locations:** when the same tag is recorded at several buildings or rooms, every location is shown.
- **No readings:** the register holds no readings or health scores. Asset overview therefore shows operational state, diagnostic findings and measurements as unavailable for these assets.
- **Category mapping:** `HVLS` maps to Fans. Other categories keep their own name.
- **Link to faults:** record IDs (`FID…`) are matched against the fault log.

## Fault log: `fault.xlsx` (`registers.load_faults`)

- **Columns read:** Fault Number (required), Reported Date (required), Trade, Trade Category, Type of Fault, Impact, Site, Building, Floor, Room, Cancel Status, Fault Acknowledged Date, Responded on Site Date, Work Started Date, Work Completed Date, Remarks.
- **Not read:** Attended By, Reported By, End User Name, End User Contact, Action(s) Taken.
- **State** is worked out as follows:
  - Cancelled: `Cancel Status = approved`.
  - Completed: has a completion date.
  - In progress: has a start date but no completion.
  - Open: everything else.
- **"Open" means open at the end of the export**, not now. The export on 20 October 2026 covers 1 Jan 2023 to 2 Jun 2025, with no records between 1 Jan 2024 and 2 Jan 2025. That gap is shaded on the chart and listed in the report.
- **Impact** mixes urgency (Urgent, Critical) with extent (Localised to room, Whole Building). It is shown exactly as recorded and is never treated as a severity or risk score.

## Event orders: `Description of Events 2026.xlsx` (`registers.load_events`)

- **Sheets:** there is one sheet per month, with a title row above the `S/N` header row.
- **Columns read:** Date (required), Description of Events (required), Event Time, Location, Power Requirement, Power Turn On, AV Equipment, Kitchen HOTO, Overtime for Kitchen HOTO, Remarks.
- **Not read:** In Charge, Documents attachment.
- **Dates** may be date cells, `20/9/2026` (day first), ranges such as `08 Jul 26-10 Jul 26` or `03 Aug - 23 Oct'26`, or day lists such as `14,15,21 & 22 Mar 26` or `10, 11, 31 Jan 26 & 01 Feb 26`. A range does not say which days inside it are used, so long ranges appear under "Running throughout".
- **Times** may be written like `9am-5pm`, `7.45pm-11.30pm`, `1800 to 2200hrs` or `530am-930pm`.
- **Repeats:** recurring events repeated on every monthly sheet are counted once.
- **Figures on 20 October 2026:** 279 distinct events, all dated. One time could not be read (`8m-10pm`), and two day lists are flagged for checking.

## Not yet connected

- **Other workbooks.** `PTW.xlsx` (iSMM schedules), the contractor lists, `List of adhoc work.xlsx` and `smart_asset_prototype.zip` are not read by any page yet.
- **Synthetic-only figures.** The Site overview and the TV displays still use the synthetic site data for asset state, event power and the calendar. The only exception is the permits display, which uses imported permits when they are configured.
- **No live sensor feed.** No such feed exists, so no page shows real measurements.
