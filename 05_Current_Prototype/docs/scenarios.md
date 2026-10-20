# Replay and acceptance matrix

The scenario pack uses a fixed seed for repeatability. Ground truth is kept outside the detector call. The checks below describe expected outcomes at the product boundary, not particular implementation rules.

| Scenario | Expected demonstration | False conclusion to avoid |
| --- | --- | --- |
| `normal` | Ordinary running and standby behavior across five assets. | Critical board fault from a healthy cycle. |
| `leakage_ramp` | Sustained board relay trend with cited readings and an eligible explanation. | Treating neutral current as leakage. |
| `sudden_trip` | Trip evidence and human checks. | Claiming a root cause from the trip bit alone. |
| `planned_maintenance` | CMMS/PTW overlap visible with asset and time. | Erasing a concurrent fault or treating PTW as approval to work. |
| `telemetry_dropout` | Missing or stale feed identified as data quality. | Filling a gap as healthy or diagnosing a fault from it. |
| `messy_ingestion` | Invalid or duplicate records held with reasons. | Quiet repair, zero substitution, or fault from held rows. |
| `unknown_asset` | Unroutable reference held for review. | Partial-name match to a known asset. |
| `high_neutral` | High load-dependent neutral current contextualized. | Calling it an earth-leakage ramp. |
| `insufficient_baseline` | Insufficient comparable evidence acknowledged. | Anomaly score presented as confident. |
| `conflicting_context` | Simultaneous maintenance context and fault evidence retained. | Global suppression by a permit or work order. |
| `startup_transient` | A brief startup excursion stays outside the running-mode leakage rule. | Treating a startup transient as sustained deterioration. |
| `isolated_zero` | One zero relay reading without a trip indication produces no trip case. | Treating a single zero measurement as proof of a trip. |
| `pump_degradation` | Sustained concurrent pump vibration, bearing-temperature and motor-current rise with cited readings and CMMS context. | Claiming a specific component fault or using unrelated-asset evidence. |
| `pump_load_change` | Motor-current and pressure increase without a qualifying three-signal condition case. | Treating every load change as a mechanical defect. |

Test quality includes routing ambiguity, injected source text, timestamp and unit errors, absent values, and separation of truth labels from analysis. Feedback and report tests use temporary local state and stub HTTP responses; they make no live provider request.
