# Portfolio walkthrough and limits

SignalDesk demonstrates an end-to-end engineering workflow: identify a physical asset from source telemetry, check its data, compare the right operating context, relate CMMS/PTW events, form a case with evidence IDs, prepare a cautious report, and capture reviewer feedback. The distribution board and pump have demonstration detectors. The other equipment and imported assets show how the shared schema accepts varied sources with explicit coverage limits.

For a short walkthrough:

1. Start with the fleet cards in **Overview**. Open PUMP-01 to explore its equipment, piping and electrical schematic, then compare mechanical, electrical and process measurements over a shared UTC window.
2. Focus on an asset event and expand a measurement to inspect its source records. Contrast current telemetry freshness with detector coverage; a fresh non-DB asset is still not assessed by condition rules. Inspect maintenance history and open work within the same asset bucket.
3. In **Maintenance**, compare the separate 90-day work-order charts and inspect a completed repair and an unresolved order. Explain the pandas workflow: UTC parsing, asset filtering, weekly grouping with empty-week zero fill, and ranked fault counts. Report-to-close time is elapsed workflow time; recorded downtime is a different measure.
4. Open **Investigate** for the current leakage case, source evidence, offline report, and reviewer decision. Use `telemetry_dropout` or `messy_ingestion` to show missing or held evidence.

The [dashboard design note](dashboard-design.md) records the chart choices. The equipment view demonstrates navigation and sensor context with illustrative geometry, not a surveyed model or verified site layout. Optional AI explanations still require explicit configuration and a click.

Two additional portfolio demonstrations are the [pump fault/control walkthrough](pump-walkthrough.md) and [persistent sixth-asset import](asset-import.md). The latter shows identity mapping, validation feedback, source provenance and idempotent saving across restarts without code changes.

All telemetry, events, assets, and replay outcomes are synthetic. The scenario checks establish simulation conformance to a designed pack. They do not measure real predictive validity, real-site recall, false alarms per asset-day, lead time, sensor coverage, residual useful life, or return on investment. Thresholds and assumptions would need commissioning data, point mappings, clock checks, source quality, and a shadow evaluation before operational use. Recommendations do not control equipment, approve permits, or create work orders.

The design draws on [pre-build research and archived pilot lessons](../../02_Past_Prototypes/predictive-maintainence-legacy/Predictive%20maintainence/raw%20data/research/v0%20pre-build%20research%20and%20risks%202026-10-05.md).
