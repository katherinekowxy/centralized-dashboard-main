# IOC redesign (October 2026): what changed, and what is still open

## Information architecture

`demo/navigation.py` defines six areas, plus "Other tools" for meeting-room booking. Every page has a bookmarkable address, `?view=<key>`, and a header that states three things: its area, where its numbers come from, and which status vocabulary it uses.

| Area | Pages |
| --- | --- |
| Site Overview | Site overview |
| Site Map & PTW | PTW map |
| Asset Health & Engineering | Asset overview, Fleet operational status, Electrical distribution, Diagnostic findings, Engineering measurements |
| Faults & Investigations | Work orders & fault trends, Fault log (iSMM export), Investigation queue |
| Operations & Planning | Event power, Operational calendar |
| Administration & Integrations | Asset register & data import, Display management, Platform architecture, External platform research |

Every original page is kept. The old "Site" and "Diagnostics demo" labels are gone. Each page now names its data source instead:

- **Site operations data:** synthetic.
- **Diagnostics replay:** a synthetic scenario with its own five assets.
- **Imported files:** real, read-only exports.
- **External reference material:** not integrated.

The new-tab detail links (`?ptw=`, `?asset=`, `?eo=`, `?wo=`) behave as before.

## Status vocabularies

`demo/brand.py` keeps each concept separate. No page combines them into one red/amber/green scale.

| Concept | Words | Where |
| --- | --- | --- |
| Operational asset state | Operational, Idle, Warning, Down, Offline | Site assets |
| Diagnostic finding | Detector finding, Checked with no finding, Not assessed | Replay assets |
| Engineering measurement | Values with units, gaps shown as gaps | Engineering measurements |
| Work-order status | Open, In progress, Closed, Completed, Cancelled | Work orders, Fault log |
| PTW timing / approval | Active now, Later today, Ended / Approved, No decision recorded, Rejected | PTW map |
| Data source | Live, Imported, Demo / synthetic, Manual, Planned (border style plus a word) | Page headers, Architecture |
| Planned versus manual | Live (solid), Manual (dashed), Planned (dotted) | Platform architecture |

Brand pink (`#E2124F`) is identity only: the header rule, the selected navigation item, primary buttons, focus and selection. It never marks a status. Every status has a word, and states that share a hue family also differ in shape. Text is at least 4.5:1 on white, which `tests/test_brand.py` checks.

## Brand

- **Colours:** pink `#E2124F`, grey `#55595C` and white, sampled from the supplied logo file and confirmed by the project lead on 20 October 2026. No official brand guide was supplied.
- **Typeface:** the brand typeface is unknown, so pages use the system UI font (`brand.FONT`).
- **Logo:** the logo image is not embedded. The repository is set up for a public portfolio, and permission to publish the logo has not been confirmed. The sidebar shows a text wordmark instead.

## Screens

Display management assigns six simplified TV variants to four screen addresses (`?display=`) and to one 2×2 wall address (`?wall=`); see the README. Its limits:

- **Presets:** kept only in addresses. Nothing is stored on a server.
- **No TV control:** no remote control of the TVs, no pushing a new layout to screens that are already open, and no heartbeats.
- **Network:** the start scripts bind to `127.0.0.1`, so the TV browsers on other machines cannot reach the app until IT agrees to serve it on the network. The app has no sign-in.

## Verification

- **Automated:** `python -m pytest -q -p no:cacheprovider` passes 276 tests (20 October 2026). They include new tests for brand contrast, navigation, the overview, the asset catalogue, displays, permit-form matching and the register, fault and event adapters. Real-data tests use small invented workbooks; no client data is in the test suite.
- **Manual:** every page was opened in a browser at 1600×900, and the TV displays at 1920×1080. Real data came from the client's export folder.
- **Not tested:**
  - on a physical 55-inch TV;
  - in a TV's built-in browser (the displays use CSS container units, so they need a browser from 2023 or later);
  - with screen readers;
  - with more than one person using the app at once.
