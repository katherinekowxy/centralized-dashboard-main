# Verification record

Development environment: Windows, Python 3.14.6, Streamlit 1.58.0, pandas 3.0.3, Plotly 6.8.0, pytest 9.1.1. These are the exact versions pinned in `requirements.txt` for the four installed packages. The engine, reporting, feedback, and replay helper otherwise use Python's standard library.

Run from `05_Current_Prototype`:

```powershell
python -m pytest -q
python replay.py
```

On 5 October 2026, the full integration suite passed **39/39** tests in 2.73 seconds. It covers all twelve scenario outcomes, replay determinism and truth separation, exact routing, malformed and missing readings, timestamp and unit validation, event windows, replay cutoff, report fallback and evidence validation, local feedback persistence, and four Streamlit AppTest flows. The scenario checks also passed for all twelve fixtures. The app answered a local health request at `127.0.0.1:8501`.

After the dashboard and CMMS history refresh on the same date, the full suite passed **47/47** tests in 4.44 seconds. This includes seven Streamlit AppTest flows and five history checks: chart/navigation behavior, asset and status filters, missing telemetry displayed through the full replay window, old-session migration, held source records, report/feedback behavior, history chronology, exact 90-day cutoff, zero-filled weekly totals, and exclusion of future closures. Plotly figure data and axes were inspected through AppTest. All twelve scenario replays still passed their 79 checks.

The subsequent simplification passed **47/47** tests in 4.40 seconds. Overview is constrained to three counts and two charts; simulation controls and work-order records start collapsed. The Maintenance timeline shows all 28 orders by default and six when filtered to DB-01. Plotly checks cover marker counts, status-at-cutoff legend, asset filtering, and missing telemetry. The running process was confirmed to serve this project's `app.py` on localhost.

The managed sandbox blocks pytest's default temporary and cache directories. When running there, the equivalent suite passed using `python -m pytest -q -p no:cacheprovider -p no:tmpdir`. This is an execution environment constraint, not an application failure.

A browser screenshot was unavailable because the computer-use environment exposed no browser and its in-app browser returned `Browser unavailable`. Streamlit's AppTest exercised the interface controls and reruns without a browser. No live AI provider request was made; HTTP success and failure paths use stub responses in tests.

These tests establish behavior on synthetic scenarios and local UI logic. They do not establish field detection accuracy or visual appearance in a real browser.

The asset-bucket and schematic update on 5 October 2026 passed **60/60** tests in 14.52 seconds using the managed-sandbox command above. Coverage includes five fleet-to-asset navigation paths, per-asset sensor and source isolation, shared six-hour chart axes, old work-order focus with empty telemetry, partial relay dropout despite fresh meter readings, missing values versus valid zero readings, backward-cutoff work-order visibility, malformed events, all schematic views, sensor highlighting and electrical-only layer filtering. Existing detector, history, reporting and review tests remain passing.

The local Streamlit service responded `ok` at `http://127.0.0.1:8501/_stcore/health`. Browser inventory was empty and opening the in-app browser returned `Browser is not available: iab`; verification therefore used Streamlit AppTest and Plotly figure construction/serialization rather than a browser screenshot. Python emitted the existing sandbox temporary-directory cleanup warning after the passing test run; pytest exited successfully.

After the final navigation adjustment (asset-specific default measurement tab and persistent selected asset), the **13/13 UI tests** passed again in 9.39 seconds. No engine or data-layer changes followed the full 60-test pass.

## Pump, diagnostic display and persistent import — 5 October 2026

The combined implementation passed **87/87 tests in 30.96 seconds** using `python -m pytest -q -p no:cacheprovider -p no:tmpdir`. All **14 scenarios / 94 replay checks** also passed. Added coverage includes the pump fault/load-control pair, per-asset baseline isolation, insufficient-evidence abstention, persistent custom assets, transactional imports, invalid rows, vendor-reference ownership, overlap/conflict handling, and diagnostic red/green/hollow-grey display behavior. UI tests use isolated registry databases.

The live acceptance used the app's Add asset and Save import controls through AppTest, mocking only the browser uploader transport with the supplied CSV bytes. It created `PUMP-02` with eight readings from `synthetic_vendor_pump.csv` mapped from `VENDOR:CHWP-06`. SignalDesk on port 8501 was then restarted. A new Python process and fresh app session verified:

- Six registered assets, including `PUMP-02`.
- Eight readings with unchanged reading IDs, filename and SHA-256 source hash.
- The asset page displays the imported snapshot and source records.
- Repeating the same import saves zero and skips eight records; one import batch remains.
- The pump condition case renders in Investigate.

Local acceptance records are in `.runtime/import-acceptance-before.json` and `.runtime/import-acceptance-after.json`; these runtime artifacts are ignored by Git. The restarted service returned `ok` from its health endpoint.

Claude reported a browser check of all five views and DB-01, PUMP-01 and AHU-01 on a separate 8502 server, subsequently stopped. See the [coordination board](../../docs/AGENT_COORDINATION.md). Codex did not have a browser available; the desktop file-picker interaction was not exercised by AppTest. No live AI request was made.
