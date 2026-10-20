# SignalDesk v0

SignalDesk is a local engineering monitoring portfolio demo. Its fleet cards open a dedicated information bucket for each asset: telemetry, equipment schematics, maintenance and events. It visualises **synthetic** telemetry and 90 days of CMMS fault history across five equipment types using pandas DataFrames and Plotly. `DB-01` and `PUMP-01` have evidence-based demonstration detectors. Additional assets and vendor CSV readings can be registered and saved locally.

## Run locally

From this folder, with Python 3.14 and the packages in `requirements.txt`:

```powershell
python -m streamlit run app.py --server.address=127.0.0.1 --server.port=8501 --server.headless=true --browser.gatherUsageStats=false
```

Open <http://127.0.0.1:8501>. `start.cmd` is a Windows shortcut for launching the same local demo. On systems that permit PowerShell scripts, `.\start.ps1` starts a tracked background process and `.\stop.ps1` stops it. Their logs and PID are kept in `.runtime/`.

To generate a compact replay check for every scenario:

```powershell
python replay.py
```

For a reproducible export of one scenario, run `python replay.py --scenario leakage_ramp --seed 42 --out data/replay`. The exported ground truth is separate from analysis. If packages are missing, run `python -m pip install -r requirements.txt`. The app works offline with the deterministic report. Reviewer feedback is stored locally in `data/feedback.sqlite3`. Local data and runtime files are ignored by Git.

## Demonstration path

1. Start on **Overview**: a tally and attention-first asset cards. Diagnostic dots distinguish findings, covered/current data with no finding, and unassessed or incomplete data. The neutral reference band on charts does not drive dot colours. Feed freshness, detector coverage, open work and location sit in each card's footer. Scenario and seed controls are under **Demo controls**.
2. Open an asset to explore its **Asset overview**. Rotate the equipment schematic, switch between isometric, top and side views, and toggle equipment, piping / air, electrical and sensor layers. The geometry is an illustrative synthetic schematic, not an imported CAD model, site drawing or installation reference.
3. Explore the Mechanical, Electrical and Process measurements. Their charts use one shared UTC window. Expand a measurement for a larger graph, related events and source readings. Missing channels are identified; a stale point is not presented as a healthy current measurement.
4. Inspect asset maintenance and events, or focus the shared window on a selected event. Telemetry covers about 48 hours; CMMS history covers 90 days. Older maintenance periods can correctly have no telemetry. Historical maintenance is context, not proof of a cause.
5. Open **Maintenance** for the fleet fault timeline and recurring fault categories. Open **Investigate** for current cases, source evidence, held rows and replay checks. Compare `normal`, `high_neutral`, `telemetry_dropout`, and `conflicting_context`.
6. Download a case report or record a review. Optional AI explanations require an explicit click and developer configuration; offline reports always work.
7. Try the [Pump-01 walkthrough](docs/pump-walkthrough.md): compare `pump_degradation` with `pump_load_change` to distinguish combined sensor evidence from a normal operating change.
8. Follow [Add an asset and import a vendor CSV](docs/asset-import.md) to register a sixth asset, preview a synthetic vendor file, save it, and verify persistence and duplicate prevention.
9. Open **Exploratory** for 11 external platform families: documented infrastructure, corrections to archived claims, source links and unresolved details. These references are separate from SignalDesk's **System map**, which shows its own components. Both views use the existing localhost. See the [dated research assessment](../01_Research/platform-assessment-2026-10-06/README.md) for scope and evidence limits. Keep that research directory beside the prototype when moving the app.

The demo uses synthetic fixtures; scenario truth is used only by the evaluation checks, never passed into `analyze` or the AI report call. Maintenance history is a separate synthetic dataset, not a diagnosed cause of current sensor behavior. See [dashboard design and pandas analysis](docs/dashboard-design.md), [architecture](docs/architecture.md), [data contract](docs/data-contract.md), [scenario matrix](docs/scenarios.md), [portfolio notes](docs/portfolio.md), and the [verification record](docs/verification.md).

## Developer configuration

Optional OpenAI-compatible chat completions can be configured with `DEMO_AI_BASE_URL`, `DEMO_AI_MODEL`, and `DEMO_AI_API_KEY`. Copy the names in `.env.example` into environment variables for your terminal session. The app does not read `.env` automatically. The endpoint must use HTTPS unless it is on localhost. No credentials are supplied by this repo, and no provider call is required for the demo.

```powershell
$env:DEMO_AI_BASE_URL = 'https://your-endpoint.example/v1'
$env:DEMO_AI_MODEL = 'your-model'
$env:DEMO_AI_API_KEY = 'your-key'
```

The report request uses an eight-second timeout. Detector observations, measurements, title, and evidence IDs are preserved exactly; model output can add tentative hypotheses without numbers. Invalid output returns the offline report. This validation constrains what is displayed, but cannot establish that a hypothesis is true. The offline report is labelled `deterministic`, never as AI generated.

## Verify

```powershell
python -m pytest -q
```

In this managed Windows workspace, `-p no:cacheprovider -p no:tmpdir` avoids pytest's restricted temporary and cache directories; the host may still emit a temporary-directory cleanup warning. The recorded development environment is Python 3.14.6, Streamlit 1.58.0, pandas 3.0.3, Plotly 6.8.0, and pytest 9.1.1.

This build follows the [v0 pre-build research](../02_Past_Prototypes/predictive-maintainence-legacy/Predictive%20maintainence/raw%20data/research/v0%20pre-build%20research%20and%20risks%202026-10-05.md) and the [initial project brief](../first%20things%20first.md).
