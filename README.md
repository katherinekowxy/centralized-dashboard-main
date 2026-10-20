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

The sidebar has two areas.

**Site** is the newer work:

| Tab | Shows |
| --- | --- |
| PTW dashboard | Today's permits to work on a street map. Each zone is filled in its contractor's colour; click a permit for what it isolates or closes. |
| Asset dashboard | Every asset by zone, in the TV design: a small dot when healthy, a banner when Down, Warning or Offline, and a cone for maintenance. |
| Asset schematic | Distribution boards, showing only the devices that need attention under their parent DB. |
| Event power | OG boxes with their CEEform sockets and live (simulated) event loads. |
| Calendar overview | This week's permits, event orders and maintenance, with clashes marked. |
| Meeting rooms | Two room calendars side by side, with booking and cancelling. |

Every page uses one light design with Gardens by the Bay colours (`05_Current_Prototype/demo/brand.py`).

**Diagnostics demo** is the earlier prototype: replayed sensor scenarios, rule-based diagnostic dots, asset pages, maintenance history and an evidence review. [05_Current_Prototype/README.md](05_Current_Prototype/README.md) walks through it.

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
