# Dashboard design and pandas analysis

The October 2026 refresh applies the requested data visualisation approach: prepare tidy pandas DataFrames, calculate explicit measures, and use charts to answer a small number of questions. Detailed source records remain available for investigation.

## Questions and charts

| Question | Visual | Measure |
| --- | --- | --- |
| What is happening to this signal? | Time-series line | Accepted sensor value, with its unit and UTC time |
| Is maintenance demand changing? | Weekly columns | Corrective work orders reported and closed per calendar week |
| Which faults recur? | Ranked horizontal bars | Work-order count by fault type |
| When did faults occur across the fleet? | Asset-by-date timeline | One marker per reported work order, coloured by current work-order status |
| What work needs attention? | Filtered maintenance register | Open and in-progress work orders, with priority and dates |

Telemetry covers the approximately 48-hour replay. CMMS history covers the preceding 90 days. They share an asset identity and replay cutoff, but the historical faults are separate synthetic records and do not establish the cause of a current telemetry case.

The history contains 28 corrective work orders: 23 closed and five open or in progress. Repeated examples cover earth leakage, relay trips, AHU filter restriction, fan belt wear, bearing vibration, pump seal leaks, and chiller cooling performance. Dates shift with the replay cutoff; this is a repeatable demonstration history, not an imported site log.

## Data preparation

- Create DataFrames from the accepted telemetry and synthetic work orders.
- Parse dates with UTC awareness; filter by asset before calculating the displayed history measures.
- Group fault categories and weekly dates, fill empty weeks with zero, and sort categories by frequency.
- Count weekly closures for the same orders reported within the 90-day window. First and last calendar weeks may be partial.
- Calculate resolution time only for closed work orders. Open work has no completed repair duration.
- Sum recorded downtime for closed work orders. This is recorded incident downtime, not measured fleet unavailability or an availability percentage.
- Keep missing telemetry visible as a gap. Do not interpolate missing evidence into an apparently continuous healthy trend.

## Visual hierarchy

Overview is built for a few seconds of reading and has no graphs. Asset cards are sorted attention-first. Each card has a status dot, a one-line headline and measurement indicators. Feed state, open jobs, detector coverage, location and operating mode sit in a muted footer. Under Dan's diagnostic-only direction recorded by Claude, red means a detector finding or trip, green means detector-covered/current data with no finding, and hollow grey means not assessed or incomplete data. A coloured dot is accompanied by text.

The neutral chart reference band (`demo/signals.py`) is the 5th–95th percentile of the first 24 hours of accepted readings in the same operating mode as the latest reading. It is descriptive and does not drive diagnostic status colours. DB-01 and PUMP-01 have explicit demonstration detectors; added assets remain unassessed until commissioned separately.

Asset overview is where numbers and graphs appear. It opens with the asset's status and headline, then latest-reading tiles (value, unit, usual band) beside a compact equipment schematic whose sensor markers use the same status colours. Mechanical, Electrical and Process tabs show a two-column grid of trend charts with value and time axes, the shaded usual band, work/permit and detector-case markers, and a status-coloured latest point. A shared UTC window aligns the plots, and event focus brings an incident or work period into the same window. Charts show gaps rather than interpolate across missing intervals. Source records, schematic controls and data caveats are behind expanders. Data freshness is assessed against the replay cutoff, independently from the chart's historical window and independently from detector alerts.

The equipment view uses handcrafted Plotly 3D geometry with equipment, piping / air, electrical and sensor layers. Top, side and isometric views provide orientation; users can rotate and zoom. Sensor markers refer to registered point IDs. A fan shows an air path, and the distribution board has electrical connections; neither is assigned invented water piping. All geometry is illustrative and not to scale. Actual CAD/BIM geometry and verified site connections are not supplied by this demo.

Maintenance opens with the fleet fault timeline and category ranking; detailed work-order records are collapsed. Investigate opens on each case with a chart of the affected measurement and the case window shaded; the case note, source evidence, review form and technical checks are collapsed. Use direct titles, units, short captions, zero-based count bars, restrained colour, and hover details.

Timeline markers show report dates. Their colours show status at the replay cutoff; they do not show historical status at each earlier date or encode outage duration. Work-order hover details include the recorded closure and resolution where available.

**Colour and scale rules (7 October 2026).**
- Teal is reserved for the green "checked, no finding" dot. The UI accent (selected items, tabs, primary button) is the neutral-information blue, and schematic pipes and air flow are violet.
- Schematic markers that are not sensors are diamonds, never circles, so they can't be read as status dots. For colour-blind viewers, the pale-blue equipment outline is close to teal, so shape carries the difference.
- Trend y-axes (`demo/chart_scale.py`) keep healthy noise small:
  - magnitudes (A, mA, kW, L/s, kPa, mm/s) start at zero;
  - voltage gets at least ±10 % of the reading;
  - temperature gets at least a 10 °C window.
  Real excursions still fill the chart.
- Chart legends are HTML above the chart, never drawn inside it.

No MTBF, predictive accuracy, or fleet health score is calculated from this short synthetic pack. See the [pump walkthrough](pump-walkthrough.md) for its combined-signal rule and [asset import workflow](asset-import.md) for persistent, sourced CSV observations.

## System map and Exploratory

**System map.** This view shows SignalDesk's own backend as five layers, AI on top: sources, routing, central platform, diagnostics, AI. Data flows upwards, and each arrow says what crosses it.
- Every part is a compact card: status tag, title and, for live parts, a number. Its description sits under Details. Cards are four per row on desktop and two on phones.
- Live parts show a number from the current session, for example readings accepted and held, aliases, assets, findings, and red, green and grey counts.
- Status is shown by border style plus a word: Live (solid), Manual (dashed), Planned (dotted and faded). It is never shown by colour, because red and green mean diagnostic findings elsewhere.
- Planned parts show their specification, never invented numbers.
- The caption says live monitoring is the end state; today the numbers come from a replay. A planned "Live feeds" card shows it on the map.
- Below the map, the "Dot and escalation rules" panel states who may turn a dot red and how cloud escalation works. Fixed rules (live) and live status checks (planned; code, not AI) may. AI never does: it is advisory and diagnostic, not predictive.
- A footer says that everything runs in one local process.
- The content lives in `demo/system_map.py`.

**Exploratory.** This view shows publicly documented architectures of external platforms, researched by Codex.
- One platform and one documented path at a time, shown as numbered step cards in their real order. Each card names its layer and where it runs, or "Location not established".
- Unknowns are worded "Not established by the reviewed sources", because missing documentation does not prove secrecy.
- The layer-by-layer comparison with SignalDesk sits in an expander, so the grouping is never read as a data path.
- Archived-claim checks and sources are in expanders too.

Both views use the shared, Streamlit-free renderer `demo/map_view.py` and the same layer ids, so a vendor path can be compared with SignalDesk layer by layer.

