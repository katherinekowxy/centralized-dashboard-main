# Gardens by the Bay · Integrated Operations Centre (prototype)

A prototype operations dashboard for Gardens by the Bay facilities management. It shows the day at a glance: open faults and how fast they are reached, contractors on site under permit, tool-box (safety) meetings, spare parts that are out of stock, and power for events. It is built for a desk screen and for 55-inch wall displays.

It is a **prototype, not a production system**. It reads copies of the iSMM Excel exports. It is not connected to iSMM or to any live system, and every page says when its data was exported.

## Run it

You need Python 3.14 and an internet connection for the map tiles and fonts.

```bash
cd 05_Current_Prototype
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Then open <http://localhost:8501>. On Windows, `05_Current_Prototype\start.cmd` does the same.

### Add the real data

The real exports are **not in this repository**: they contain names and phone numbers. Get the `GBB IOC Datasets` folder from the shared drive, then start the app with it:

```powershell
cd 05_Current_Prototype
.\start.ps1 -DataDir "C:\path\to\GBB IOC Datasets"
```

or set the environment variable `GBB_DATA_DIR` to that folder before `python -m streamlit run app.py`. The files are read, never changed or copied. Without the folder the app still runs, showing demo data, and every page labels it as such.

The folder should contain:

| File or folder | Used for |
| --- | --- |
| `faults_<from>_<to>.xlsx` | Faults, service requests and event support jobs (the newest file is used) |
| `PTW/` | Permits to work, one export per site |
| `Tool Box Meeting/` | Tool-box (safety) meetings |
| `Assets/` | Store inventories, one export per store |
| `smart_asset_prototype.zip` | The smart-asset sample (synthetic) |

## What the client sees

The sidebar opens on the client pages. Every page header carries a tag saying where its numbers come from: **Imported · not live** for the iSMM exports, **Demo** for invented data.

| Page | What it answers | Data |
| --- | --- | --- |
| Site overview | What needs attention today: open faults, new jobs, time to site, permits, tool-box meetings, stock-outs, event power | iSMM exports |
| Permit map | Which contractors are working under a permit, by site | iSMM permits |
| Tool-box meetings | Which safety briefings were held, by company and date | iSMM tool-box meetings |
| Inventories | Which spares are out of stock or below their minimum, by store | iSMM inventories |
| Smart asset sample | How sensor readings and alerts could look for motors and pumps | **Synthetic sample** |
| Faults & requests | Which faults are open, for how long, and how fast they are reached | iSMM faults |
| Event power | Recent power handovers for events, and the outdoor power boxes | iSMM handovers; **demo** socket loads |
| Events calendar | Event support jobs (space, AV, kitchen and power handovers) by day | iSMM faults |
| Display wall | Four pages arranged for a 2×2 wall of screens | Same as the pages shown |

**Show internal & demo pages**, at the bottom of the sidebar, adds the engineering workbench and administration pages. They use invented data, so they are hidden from the client by default: Asset overview, Asset status, Electrical, Diagnostics, Measurements, Work orders, Investigations, Data import, Screens, Platform architecture, Platform research and Room booking.

### How the numbers are counted

- **Faults are counted apart from requests.** iSMM's fault export also holds service requests (opening bollards and doors, escorts) and event support jobs (space, AV, kitchen and power handovers). Each record is counted as exactly one of the three, and every page uses the same rule, so the overview matches the pages it links to.
- **Open** means not started or in progress at the time of the export. **Time to site** is the median time from report to someone on site, for faults reported in the last 30 days.
- **Permits active today** are permits whose dates include today. The iSMM permit export has no building column, so the map shows permits by site, not by exact work location.
- **Out of stock** means quantity 0; **below minimum** means under the threshold set in iSMM.
- **Upcoming events** need the event order workbook, which is not in the data folder, so Event power shows recent handovers and says so.
- **Each export has its own time.** Every page names the time its data was exported. None of it is live.

[05_Current_Prototype/docs/real-data.md](05_Current_Prototype/docs/real-data.md) lists every column read, what is deliberately not read, and the validation rules.

## Wall screens

Display wall arranges four pages for a 2×2 wall. Screens (an internal page) gives each 55-inch screen its own address. For example, `http://<host>:8501/?display=assets&screen=2&refresh=60` shows one display, and `?wall=overview,assets,permits,event-power` shows the whole wall. Presentation mode hides the sidebar and every control.

The start scripts only accept connections from the same computer (`127.0.0.1`). To show the app on TVs elsewhere, it must be served on the network with `--server.address`. The app has no sign-in, so agree that with IT first. The app cannot switch on, control or monitor the TVs themselves.

## Tests

```bash
cd 05_Current_Prototype
python -m pytest -q -p no:cacheprovider
```

## Good to know

- **Restart after code changes.** A running server keeps the code it has already loaded, so restart it after pulling an update.
- **Brand.** Logo and colours are Gardens by the Bay's own (pink `#E2124F`, grey `#55595C`). The logo is the client's; keep this repository private unless they agree otherwise.
- **Map.** Map tiles and outlines are © OpenStreetMap contributors (`05_Current_Prototype/assets/maps/SOURCE.md`).
- **Optional AI.** An AI explanation on the Investigations page can be switched on with the settings in `05_Current_Prototype/.env.example`. Without them, a built-in offline report is used.
- **More detail.** [docs/ioc-redesign.md](05_Current_Prototype/docs/ioc-redesign.md) covers the design decisions and [05_Current_Prototype/README.md](05_Current_Prototype/README.md) walks through the engineering workbench.

## Layout

| Path | Contents |
| --- | --- |
| `05_Current_Prototype/` | The app (`app.py`, `demo/`), tests, docs and synthetic sample files |
| `05_Current_Prototype/demo/sources/` | Readers for the iSMM exports |
| `01_Research/platform-assessment-2026-10-06/` | Public vendor research, shown on the Platform research page |
