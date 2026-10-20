# External platform assessment — 6 October 2026

## Assessment

The archived notes are useful for finding product families, but **are not reliable as a current technical catalogue without corrections**. They mix product generations, company ownership, marketing assertions and inferred implementation details. Some mistakes predate the archive rather than representing recent changes.

This assessment checks the infrastructure and major product claims in [the catalogue](../md-folder-research/vendor-product-catalogue.md) and [the eight-vendor landscape](../md-folder-research/vendor-landscape-eight-majors.md). Original notes are preserved. Read this dated assessment alongside them.

## Coverage

| Reference family | Paths assessed | Evidence and claim assessment |
| --- | --- | --- |
| ABB | Smart Sensor, Genix APM, drive-embedded ESA | [Record](abb.json) |
| SKF | Wireless collection and online monitoring | [Record](skf.json) |
| Siemens | CONNECT 400, SM 1281, Senseye | [Record](siemens.json) |
| Emerson | AMS 9420 and Wireless Vibration Monitor | [Record](emerson.json) |
| GE Vernova | SmartSignal and APM Health | [Record](ge-vernova.json) |
| Rockwell | GuardianAI and Augury / Fiix workflow | [Record](rockwell.json) |
| Schneider | Thermal monitoring / Asset Advisor and AVEVA | [Record](schneider.json) |
| Honeywell | Versatilis / Experion EHM and Forge | [Record](honeywell.json) |
| Bently Nevada | 3500 and Orbit 60 with System 1 | [Record](bently-nevada.json) |
| Samotics | SAM4 electrical monitoring | [Record](samotics.json) |
| Amazon Monitron | Documented legacy-access architecture | [Record](amazon-monitron.json) |

The eight main vendor families are covered, with three additional references needed to resolve important archive claims. Incidental mentions such as Tractian, AssetWatch, Fluke, WEG, Schaeffler, C3.ai, Uptake, Seeq and Falkonry are **not individually audited here**. The PM-route PDFs are not a completed second catalogue audit. Prices, local office addresses, career advice, market share, ROI and performance numbers have not been comprehensively revalidated.

## Material corrections

- **SAM GUARD is a SAMSON / Precognize product**, not a Siemens platform. [SAMSON acquisition announcement](https://www.samsongroup.com/en/news/in-focus/details/news/press-releases/visual-processes/)
- **Baker Instruments moved from SKF to Megger in 2018.** [Megger announcement](https://www.megger.com/en/et-online/october-2018/megger-welcomes-baker-instruments-to-the-family%21)
- **AspenTech became wholly owned by Emerson in March 2025.** The older majority-owned description is outdated. [AspenTech acquisition information](https://www.aspentech.com/en/acquisition/emerson)
- **AMS 9420 and AMS Wireless Vibration Monitor are distinct products.** The records map their paths separately. [Emerson Wireless Vibration Monitor](https://www.emerson.com/en/automation-systems/asset-performance-management/machinery-health-management/ams-wireless-vibration-monitor)
- **API 670 protection is not exclusive to Bently Nevada.** Emerson explicitly offers compliant machinery protection. [Emerson machinery protection](https://www.emerson.com/en/automation-systems/asset-performance-management/machinery-health-management/machinery-protection-systems)
- **The blanket exclusion of fixed-speed motors from ESA is incorrect.** Samotics documents direct-on-line, soft-starter and VFD configurations. [Samotics motor control types](https://help.samotics.com/en/articles/238385-motor-control-type)
- **Amazon Monitron is closed to new customers**, effective 31 October 2024. Existing-customer continuation is a different availability claim. [AWS documentation history](https://docs.aws.amazon.com/Monitron/latest/user-guide/doc-history.html)

Exact algorithm names, assumed cloud/datastore choices and universal deployment claims are often unverified. Each record retains these limitations rather than inventing missing infrastructure.

## How to read the maps

Open **SignalDesk → Exploratory** on the existing localhost. Select a platform and a documented path. Sources, corrections and unknowns sit behind expandable details. **System map** is the separate view of SignalDesk itself.

These are public product-level architecture summaries, not engineering installation drawings, reverse-engineered internal services or working SignalDesk integrations. Alternative product paths do not imply interoperability, mandatory dependencies or a single purchased stack. A displayed path preserves its documented sequence; a layer label categorises a component rather than defining execution order. Presentation/workflow nodes may appear under `platform` without asserting a database.

- **Confirmed:** a reviewed official source supports the stated product-level claim.
- **Corrected:** evidence contradicts or materially narrows the archived claim.
- **Unverified:** the reviewed sources do not establish the claim; this is not proof it is false.

Official sources establish what a vendor documents, not independent validation of reliability, accuracy, compliance or availability in every region. `checked_on` and `accessed` mean reviewed on that date. An older manual still available online is not proof of current orderability or the latest firmware. Publication dates are retained when known; absent dates remain “Not stated”. Deployment remains `unknown` where the cited material is insufficient.

## Maintenance and implementation

The JSON records are the single content source for Exploratory. They contain claim-level references and source publication/access dates. The app reads them locally without fetching vendor sites or sending asset data. `demo/platform_references.py` checks identity, layer values and citation integrity. Keep this research directory alongside `05_Current_Prototype` when moving the demo.

Dan requested the research assessment, separation from SignalDesk architecture and same-app Exploratory location. Codex coordinated three Sol research agents and implemented the loader/routing; Claude owns the map presentation and the separate SignalDesk System map. See the repository coordination board for verification and handoffs.

## Initial verification — 6 October 2026

- Snapshot: 11 reference families, 22 paths, 49 assessed claims (19 confirmed, 21 corrected, 9 unverified), 52 unique official source URLs.
- Final ordered-card version: `python -m pytest -q -p no:cacheprovider -p no:tmpdir` — **100 passed in 14.77 seconds**, exit 0. The run used elevated sandbox permissions because Streamlit's UI test fixtures create temporary Python scripts. Earlier temporary-directory and test-selector failures were resolved.
- AppTest opens System map, visits all 11 vendor selections, checks that Exploratory has no synthetic badge or replay controls, and returns to Overview. The test registry is isolated from the operator's persisted assets/readings.
- Twenty-four local links in this assessment and the prototype README resolve.
- The final renderer was loaded by restarting verified SignalDesk processes on the existing port 8501; PID 30060, health `ok` at 10:37 Singapore time.
- Live desktop/phone browser review has been handed to Claude and is **pending at this handoff**. Codex's browser tool reported no available browser. Automated rendering checks above do not substitute for that visual review; later results belong on the coordination board.

## Fusion correction — 6 October 2026

Dan requested a rework that distinguishes collecting multiple measurements, combining them in a diagnosis, and adding operating or maintenance context. Two Codex subagents reviewed primary sources and built a path-specific evidence panel; Claude reviewed placement and proposed binding it directly to the renderer's selected flow. The evidence card sits beneath that path, with path-specific limitations and sources under Details. General definitions and four short SignalDesk scope bullets sit in a separate collapsed expander. Claude's screenshot review also led to neutral outcome tags and border styles and consistent diagnostic-fusion terminology.

- **SmartSignal:** documented multivariate analysis and combined diagnostic evidence. [GE webinar](https://www.gevernova.com/software/resources/webinar/smartsignal-aws-advanced-asset-maintenance-webinar)
- **Augury:** documented cross-signal confirmation; the capability is attributed to Augury, not GuardianAI or every Fiix configuration. [Augury explanation](https://www.augury.com/use-cases/asset-condition-monitoring/condition-monitoring-for-industrial-rotating-equipment/)
- **Versatilis:** multiple sensing types confirmed; the reviewed evidence does not establish automated cross-sensor fusion. The supplied brochure could not be fetched by the review tool; accessible official product documentation supports the bounded claim. [Honeywell transmitter](https://process.honeywell.com/us/en/products/field-instruments/iot-sensor-solutions/equipment-health-monitoring-hvt/honeywell-versatilis-transmitter)
- **SAM4:** electrical signatures can provide indirect evidence of mechanical and process faults; this is not a claim of vibration/temperature sensor fusion. [Samotics explanation](https://samotics.com/how-it-works)

Other paths say fusion was not assessed in this review, rather than claiming it is absent. The loader requires cited evidence, inputs and limitations for every fusion assessment. Four paths have explicit assessments; the snapshot now has 55 unique source URLs, with the original 11 families and 22 paths retained. The additional AVEVA brochure explicitly supports the ML tag on its Predictive Analytics step; this does not establish fusion on every AVEVA deployment.

The PUMP-01 load/speed example is explicitly illustrative. Today's synthetic demo uses aligned running-mode rules and a separate load-change scenario; it does not normalize for load and speed. Commercial fusion already exists. SignalDesk's design focus is traceable evidence, missing/conflicting signals and explaining findings. No detector or AI/dot authority changed in this rework.

### Fusion rework verification

- Required full suite: `python -m pytest -q -p no:cacheprovider -p no:tmpdir` - **112 passed in 15.05s**, exit 0. Streamlit temporary test scripts required elevated access; the initial sandbox failures were file-permission errors.
- Final code restarted on the existing 8501 service via `start.ps1`: PID **18452**, health **ok**. No second server or operator-data writes.
- Seven live-server WebSocket/protobuf UI checks passed across the four revised families and sibling unassessed paths: correct outcomes/borders, one card directly below the path, collapsed source links, no UI exceptions.
- Claude reviewed an earlier rendering at desktop and phone widths (GE and Honeywell at 1440 pixels; GE at 390), reporting no overflow or exceptions. His placement/readability suggestions were adopted. Final browser-pixel review is pending; Codex's Windows browser control stopped because URL policy enforcement was unsupported. The live-server checks verify content and behavior, not pixels.

### Claude follow-up completion

The remaining path-limit placement and four-bullet scope suggestions are implemented. AVEVA Predictive Analytics now has a cited ML tag, supported by its [official brochure](https://www.aveva.com/content/dam/aveva/documents/perspectives/brochures/Brochure_PredictiveAnalytics.pdf.coredownload.inline.pdf). Full suite: **112 passed in 15.10s**. Restarted 8501: **PID 24448**, health **ok**; nine live-server UI page/path checks passed. Final screenshot verification remains unavailable through Codex's browser tools and open on the coordination board.
