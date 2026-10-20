# SignalDesk

SignalDesk is a prototype facilities Integrated Operations Centre (IOC) for Gardens by the Bay. It brings permits to work, asset status, faults, event power, schedules and meeting rooms into one place, for operators and for four 55-inch wall screens. It is a prototype, not a production system. Its built-in data is **synthetic** and labelled as such on every page. When a folder of the client's Excel exports is configured, some pages read those files read-only and label them as imported (see [Real data](#real-data-read-only)). [docs/ioc-redesign.md](05_Current_Prototype/docs/ioc-redesign.md) summarises the October 2026 redesign and what is still open.

## Run it

You need Python (developed and tested on 3.14) and an internet connection for the map tiles.

```bash
cd 05_Current_Prototype
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Then open <http://localhost:8501>. On Windows, `05_Current_Prototype\start.cmd` does the same. The first page load builds the synthetic site database in `05_Current_Prototype/data/site.sqlite3`, which takes a few seconds. After that it rebuilds by itself whenever the data is more than six hours old, so "today" always has work on it.

## What to look at

The sidebar groups every page into six areas (`05_Current_Prototype/demo/navigation.py`). Each page has its own address, `?view=<key>`, so you can bookmark it. Every page header names its data source and which kind of status it shows.

| Area | Page (`?view=`) | Shows | Data |
| --- | --- | --- | --- |
| Site Overview | Site overview (`overview`) | What needs attention now, asset operational state, permits, event power, diagnostics replay findings, what is coming up, and data sources; each figure comes from the page that owns it | Site + replay |
| Site Map & PTW | PTW map (`ptw-map`) | **Imported permit records** from the real permit forms on the client's Power BI location mapping (markers, clusters, density layer, filters, exception list, validation report), or the synthetic site demo with each permit's isolations and closures | Imported or Site |
| Asset Health & Engineering | Asset overview (`assets`) | Every asset from both datasets under shared categories (chillers, AHUs, distribution boards and others), with category, source and attention filters; operational state and diagnostic findings stay in separate columns | Site + replay |
| | Fleet operational status (`asset-status`) | Operational state of every site asset by zone | Site |
| | Electrical distribution (`electrical`) | Distribution boards and the devices downstream of a problem | Site |
| | Diagnostic findings (`diagnostics`) | Rule-based detector findings for the monitored demonstration assets | Replay |
| | Engineering measurements (`asset-engineering`) | Earth leakage, trips, voltage, current and process trends for one asset; illustrative 3D schematic | Replay |
| Faults & Investigations | Work orders & fault trends (`work-orders`) | 90-day CMMS history, recurring faults, work-order status | Replay |
| | Fault log (`fault-log`) | The real iSMM fault export: states as at the export, weekly reported and completed (gaps shaded), open faults by building, Impact as recorded, validation report | Imported |
| | Investigation queue (`investigations`) | Detector cases, evidence, reviews, data quality, exports | Replay |
| Operations & Planning | Event power (`event-power`) | OG boxes, CEEform sockets and simulated event loads | Site |
| | Operational calendar (`calendar`) | **Imported event orders** from the event workbook by day, with power and kitchen needs, or the synthetic week of permits, events and maintenance with clashes marked | Imported or Site |
| Other tools | Meeting-room booking (`rooms`) | Two room calendars with booking and cancelling | Site |
| Administration & Integrations | Display management (`displays`) | Assign displays to the four screens, preview each screen and the 2×2 wall, and copy their addresses | Site + replay |
| | Asset register & data import (`assets-import`) | Register an asset and validate a vendor CSV | Replay |
| | Platform architecture (`architecture`) | How data reaches the application, live versus planned | Replay |
| | External platform research (`research`) | Vendor reference material; none of it is integrated | Reference |

**Site** pages read the synthetic site database. **Replay** pages read a replayed synthetic sensor scenario with its own five demonstration assets ([05_Current_Prototype/README.md](05_Current_Prototype/README.md) walks through it). The two datasets do not share asset IDs, so they are kept on separate pages. Every page uses one light design with Gardens by the Bay colours (`05_Current_Prototype/demo/brand.py`).

## Four screens and the 2×2 video wall

Open **Display management** to choose what each 55-inch screen shows. The choices are Site summary, Asset operational state, Permits to work today, Event power, Coming up and Diagnostic findings. Each screen then gets its own address to open full screen in that TV's browser:

- one screen: `http://<host>:8501/?display=assets&screen=2&refresh=60`
- the combined wall, driven as one display: `http://<host>:8501/?wall=overview,assets,permits,event-power&refresh=60` (top left, top right, bottom left, bottom right)

Presentation mode hides the navigation and every control. Hover over the top-right corner for a link back to Display management. The displays are simplified versions of the operator pages, sized for 1920×1080 and laid out in proportional units, so the same address also works on a single quadrant or at other 16:9 resolutions.

**What this version cannot do.** A layout is kept only in addresses: Display management writes its assignments into its own address, so bookmark it to keep a preset. Nothing is stored on a server. The app cannot switch, power or monitor the physical TVs, push a new layout to screens that are already open, or report a screen as offline. That needs display-management infrastructure that does not exist today.

**Reaching the TVs.** The start scripts bind to `127.0.0.1`, so only a browser on the same computer can open these addresses. For the TV browsers to reach the app from other machines, it must be served on the network (`--server.address`). The app has no sign-in, so agree that with IT first.

## Real data (read-only)

The PTW map can read the real permit-form exports. Point the app at the folder holding `PERMIT-TO-WORK/` and `Building Location.xlsx` before starting it:

```powershell
cd 05_Current_Prototype
.\start.ps1 -DataDir "C:\Users\you\BI Report Dataset\GBB"
```

or set the environment variable `GBB_DATA_DIR` to that folder. The files stay where they are. They are read when a page loads (and cached for ten minutes), never copied into this repository, and never written. Personal details on the forms (names, phone numbers, e-mail addresses) are not read. Imported records are labelled "imported, not live" and are never mixed with synthetic records. Location matching uses the client's Power BI alias table (`05_Current_Prototype/assets/maps/ptw_location_aliases.csv`). Building coordinates come from `Building Location.xlsx` and are approximate until verified there. Asset overview also lists the real asset register, the Fault log reads the iSMM fault export, and the Operational calendar reads the event workbook. [05_Current_Prototype/docs/real-data.md](05_Current_Prototype/docs/real-data.md) lists every column read, what is deliberately not read, the validation rules and the limits.

## Tests

```bash
cd 05_Current_Prototype
python -m pytest -q -p no:cacheprovider
```

## Good to know

- **Synthetic data.** Every built-in asset, reading, permit, contractor, event and booking is invented and labelled as demo data. Imported files are labelled separately and never mixed in. Map tiles and zone outlines are © OpenStreetMap contributors (see `05_Current_Prototype/assets/maps/SOURCE.md`).
- **Runs on one machine.** It calls nothing outside except the map tiles and the map library. It has no logins.
- **Optional AI.** An AI explanation of a case can be switched on with the settings in `05_Current_Prototype/.env.example`. Without them, the offline report is used.
- **Where the data flows from** (Excel and PDF importers today, APIs later): [05_Current_Prototype/docs/site-data-sources.md](05_Current_Prototype/docs/site-data-sources.md).

## Layout

| Path | Contents |
| --- | --- |
| `05_Current_Prototype/` | The app (`app.py`, `demo/`), tests, docs and synthetic sample files |
| `01_Research/platform-assessment-2026-10-06/` | A dated snapshot of public vendor research, read by the Diagnostics demo's Exploratory page |
