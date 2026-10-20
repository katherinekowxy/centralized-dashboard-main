# Data contract

The public Python API is defined in [IMPLEMENTATION_CONTRACT.md](../IMPLEMENTATION_CONTRACT.md). Interchange values are plain dictionaries and lists of dictionaries; the UI may convert them to data frames for display.

| Object | Identity and timing | Key fields | Meaning |
| --- | --- | --- | --- |
| Asset | `asset_id` | `name`, `asset_type`, `location`, `criticality`, `coverage` | One canonical physical equipment item. |
| Reading | `reading_id`, `asset_ref`, `point_id`, `observed_at`, `ingested_at` | `value`, `unit`, `quality`, `operating_mode`, `source`, `schema_version` | Source observation, with observation time distinct from arrival time. |
| Event | `event_id`, `asset_id`, `start_at`, `end_at`, `reported_at` | `event_type`, `status`, `title`, `notes` | Time bounded CMMS or PTW context. Reporting time may lag occurrence. |
| Case | `case_id`, `asset_id`, `start_at`, `end_at` | `category`, `severity`, `title`, `summary`, `evidence_ids`, `observations`, `recommended_checks`, `ai_eligible`, `ai_gate_reason` | A traceable triage output. Equipment findings use accepted evidence; quality findings may cite held source records. |
| Report | case reference via caller | `mode`, `title`, `observations`, `hypotheses`, `recommended_checks`, `limitations`, `evidence_ids` | `mode` is `deterministic` or `ai`. A fallback also carries `reason`. |
| Feedback | `id`, `created_at`, `case_id` | `decision`, `note`, `context` | Local append-only reviewer judgment; decisions are `confirmed`, `false_alarm`, `needs_review`. |
| Historical work order | `work_order_id`, `asset_id`, `reported_at`, `closed_at` | `fault_type`, `title`, `priority`, `status`, `downtime_hours`, `resolution` | Separate synthetic corrective-work history. Closure and resolution exist only for completed work. |
| Imported reading | `reading_id`, `asset_id`, `point_id`, `observed_at`, `ingested_at`, `import_id` | Reading fields plus `source_file`, `source_hash`, `source_row`, `source_equipment_ref` | Persisted CSV observation, displayed with provenance and excluded from generated detector input. |
| Vendor mapping | Case-folded `equipment_ref` | `asset_id` | One vendor equipment reference has one canonical asset owner. Conflicting remaps are rejected. |

The analysis output separates `accepted`, `quarantine`, `quality_issues`, `cases`, `asset_summaries`, and `metrics`. A quality problem is an outcome in its own right. `ground_truth` and scenario metadata belong to generation/evaluation; they never enter `analyze` or the report request. Synthetic values may be physically plausible yet do not represent a commissioned sensor or validated site threshold.

`demo.history.generate_history(as_of)` produces repeatable work orders relative to the replay cutoff. `summarize_history(work_orders, as_of, asset_id=None)` calculates a 90-day summary using pandas. `total_faults` is a work-order count, `open_faults` includes open and in-progress orders, and `median_resolution_hours` measures elapsed report-to-close time for completed orders. `weekly` contains zero-filled Monday UTC buckets with reports (`faults`) and closures (`closed`); boundary weeks can be partial. `by_fault` ranks work-order counts by category. These measures describe the selected reported-work cohort, not every closure or outage in a real CMMS system.
