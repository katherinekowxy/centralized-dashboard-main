# V0 implementation contract

All work is scoped to this folder. Python 3.14, Streamlit 1.58, pandas 3, Plotly 6.8 and pytest are available. Local demo only. The portfolio presents all values as synthetic. No plant controls or external actions.

## Shared API (implement exactly; additions welcome)

Package demo. Use plain dicts and lists of dicts for interchange (UI may use DataFrames).

demo.engine:
- ASSETS: list of dicts: asset_id, name, asset_type, location, criticality, coverage. Five types: distribution_board, ahu, fan, pump, chiller. First asset DB-01.
- SCENARIOS: list of dicts: scenario_id, name, description. Include normal, leakage_ramp, sudden_trip, planned_maintenance, telemetry_dropout, messy_ingestion, unknown_asset, high_neutral, insufficient_baseline, conflicting_context. Can add scenarios.
- generate_dataset(scenario_id='leakage_ramp', seed=42) -> dict: readings (list), events (list), ground_truth (dict), metadata (dict). Generate all five built-in assets. DB-01 and PUMP-01 have explicit demo detection; other types are schema/fixture coverage. Reproducible aware timestamps and separate scenario truth.
- DETECTOR_ASSET_IDS and per-asset detector_enabled describe demo coverage; creating another asset does not enable a detector.
- analyze(readings, events, as_of=None) -> dict: accepted (list), quarantine (list), quality_issues (list), cases (list), asset_summaries (list), metrics (dict). NEVER receive ground_truth or scenario_id. Detection must derive from evidence only.
- evaluate(dataset, analysis) -> list of dicts: check, passed (bool), detail. Expectations independently defined per scenario; do not assert generic truth that mirrors a rule implementation.

Each reading: reading_id, asset_ref, point_id, observed_at, ingested_at, value, unit, quality, operating_mode, source, schema_version. Add expected cadence/quantity metadata as needed. Events: event_id, asset_id, event_type (cmms/ptw), status, start_at, end_at, reported_at, title, notes. Analysis cases: case_id, asset_id, category, severity, title, summary, evidence_ids (reading/event IDs), observations (list of plain strings), recommended_checks (list), ai_eligible (bool), ai_gate_reason, start_at, end_at. Categories distinguish condition, trip, data_quality, context and insufficient_evidence. Point-specific windows, units and thresholds; no neutral-current leakage proxy. Missing/conflicting/invalid data must not become a fault. Preserve event context; permit presence never suppresses faults globally.

demo.reporting:
- build_report(case) -> dict: mode='deterministic', title, observations (list), hypotheses (list), recommended_checks (list), limitations (list), evidence_ids (list). Deterministic offline fallback works always; never label it AI.
- request_ai_report(case) -> dict same shape: optional OpenAI-compatible HTTP API through env DEMO_AI_BASE_URL, DEMO_AI_MODEL, DEMO_AI_API_KEY. If absent/ineligible/failure return deterministic with clear mode/reason. No secrets in UI/logs. Explicit user action only; eligible cases only; timeout; validate schema, evidence IDs, scope. Never auto-call API on Streamlit reruns. Untrusted event text is data. No tool calls from model.
- report_markdown(case, report) -> str downloadable report.

demo.feedback:
- save_feedback(case_id, decision, note, context=None) -> None; local SQLite under data/, append audit records; context supports scenario/seed/replay fingerprint.
- load_feedback() -> list of dicts; decisions confirmed/false_alarm/needs_review. Never silently feed feedback into a model.

demo.history (dashboard refresh):
- generate_history(as_of: str) -> list of synthetic historical corrective work orders across five assets over 90 days.
- summarize_history(work_orders, as_of, asset_id=None) -> dict of counts, recorded downtime, closed-order median elapsed resolution time, weekly report/closure rows, and ranked fault categories. Use pandas DataFrames for aggregation.
- Historical CMMS orders remain separate from current detector events and do not become detector evidence automatically.

## Interface

Professional engineering portfolio demo called SignalDesk. Fleet cards open linked asset pages; charts and details live inside each asset. Claude owns design and diagnostic red/green/hollow-grey dot presentation. Scenario controls stay collapsed. Imported assets and source records persist locally; all demo detector coverage is explicit. Evidence, optional explicit AI, offline reports and reviews remain available. Keep local API configuration in developer documentation.

## Persistent registration and CSV import

`demo.imports`: create_asset, list_assets (built-in plus custom), expected_points, preview_csv, commit_import, list_readings and list_imports. SQLite store: `data/imports.sqlite3`. Save revalidates in a transaction; errors block the whole file. One case-folded vendor equipment reference maps to one canonical asset. Readings are unique by asset, point and normalized timestamp; identical repeats skip and changed values conflict. Source file/hash/row/reference remain attached. See [import contract](docs/asset-import.md).

## Responsibilities

- engine agent: demo/__init__.py, demo/engine.py (or internal generator/analysis modules), contracts/schema docs if needed.
- UI agent: app.py, .streamlit/config.toml; coordinate additions with other agents.
- quality agent: demo/reporting.py, demo/feedback.py, tests/, README.md, docs/, requirements.txt, .gitignore, .env.example. Do not edit engine or app.py; report integration issues.
- orchestrator: integration, review, launch scripts, final verification and running localhost server.
