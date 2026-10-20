# SignalDesk

SignalDesk is a prototype monitoring dashboard for the Bay South gardens. It brings permits to work, asset status, event power, schedules and meeting rooms into one place, sized for a wall-mounted TV. It is an independent prototype, not an official Gardens by the Bay system, and **all of its data is synthetic**.

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
| Site Map & PTW | PTW map (`ptw-map`) | Today's permits on a street map; click a permit for what it isolates or closes | Site |
| Asset Health & Engineering | Fleet operational status (`asset-status`) | Operational state of every site asset by zone | Site |
| | Electrical distribution (`electrical`) | Distribution boards and the devices downstream of a problem | Site |
| | Diagnostic findings (`diagnostics`) | Rule-based detector findings for the monitored demonstration assets | Replay |
| | Engineering measurements (`asset-engineering`) | Earth leakage, trips, voltage, current and process trends for one asset; illustrative 3D schematic | Replay |
| Faults & Investigations | Work orders & fault trends (`work-orders`) | 90-day CMMS history, recurring faults, work-order status | Replay |
| | Investigation queue (`investigations`) | Detector cases, evidence, reviews, data quality, exports | Replay |
| Operations & Planning | Event power (`event-power`) | OG boxes, CEEform sockets and simulated event loads | Site |
| | Operational calendar (`calendar`) | This week's permits, events and maintenance, with clashes marked | Site |
| Other tools | Meeting-room booking (`rooms`) | Two room calendars with booking and cancelling | Site |
| Administration & Integrations | Asset register & data import (`assets-import`) | Register an asset and validate a vendor CSV | Replay |
| | Platform architecture (`architecture`) | How data reaches the application, live versus planned | Replay |
| | External platform research (`research`) | Vendor reference material; none of it is integrated | Reference |

**Site** pages read the synthetic site database. **Replay** pages read a replayed synthetic sensor scenario with its own five demonstration assets ([05_Current_Prototype/README.md](05_Current_Prototype/README.md) walks through it). The two datasets do not share asset IDs, so they are kept on separate pages. Every page uses one light design with Gardens by the Bay colours (`05_Current_Prototype/demo/brand.py`).

## Tests

```bash
cd 05_Current_Prototype
python -m pytest -q -p no:cacheprovider
```

## Good to know

- **Synthetic data.** Every asset, reading, permit, contractor, event and booking is invented. Map tiles and zone outlines are © OpenStreetMap contributors (see `05_Current_Prototype/assets/maps/SOURCE.md`).
- **Runs on one machine.** It calls nothing outside except the map tiles and the map library. It has no logins.
- **Optional AI.** An AI explanation of a case can be switched on with the settings in `05_Current_Prototype/.env.example`. Without them, the offline report is used.
- **Where the data flows from** (Excel and PDF importers today, APIs later): [05_Current_Prototype/docs/site-data-sources.md](05_Current_Prototype/docs/site-data-sources.md).

## Layout

| Path | Contents |
| --- | --- |
| `05_Current_Prototype/` | The app (`app.py`, `demo/`), tests, docs and synthetic sample files |
| `01_Research/platform-assessment-2026-10-06/` | A dated snapshot of public vendor research, read by the Diagnostics demo's Exploratory page |
