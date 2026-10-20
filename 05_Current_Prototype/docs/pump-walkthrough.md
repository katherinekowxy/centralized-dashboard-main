# Pump-01 demonstration

## Three-minute walkthrough

1. In **Demo controls**, select **Pump condition trend** (`pump_degradation`) and seed `42`, then run the replay. Open `PUMP-01` from the fleet.
2. Focus the pump condition event. Compare the Mechanical vibration and bearing-temperature charts with Electrical motor current using the same time window.
3. The seed-42 qualifying window is **22 September 2026, 13:30–15:00 UTC**. Four aligned readings per signal rise above the comparable baseline. The case cites those readings and baseline records.
4. Open the case and review its observations, the CMMS investigation, and the offline case note. `WO-PUMP-401` is reported at 15:00 UTC; its presence supplies context, not a diagnosis. Record a reviewer disposition if desired.
5. Switch to **Pump load change** (`pump_load_change`). Motor current and differential pressure increase, but the three-signal condition rule stays clear. A reading outside the neutral reference band is not itself a detector finding.

The final replay state can be standby. The retained condition case describes an earlier observed running window; it does not assert that the pump is currently failing or that a particular component caused the pattern.

## Demo rule

Each of the three channels needs a running-mode baseline in the pump's first 24 hours: at least 20 observations, 10 hours of span, and 80% coverage at the expected cadence.

| Channel | Threshold above which all four aligned readings must lie | Minimum net rise across the window |
| --- | --- | --- |
| Vibration | Greater of median + 1.3 mm/s or 1.5 × median | 0.7 mm/s |
| Bearing temperature | Greater of median + 6 °C or 1.10 × median | 2 °C |
| Motor current | Greater of median + 4 A or 1.10 × median | 1 A |

Samples must share timestamps and running mode, with no gap greater than 45 minutes between aligned samples. The fixture has 30-minute measurements. Missing, quarantined, isolated, or unrelated-asset readings cannot supply the required combined evidence.

These are Codex implementation choices for a synthetic demonstration. They are not commissioned engineering limits or a validated bearing-fault diagnosis. Only one qualifying pump episode is reported per replay.

## Display range versus condition detection

The chart's neutral reference band is the 5th–95th percentile from the first 24 hours in the same operating mode. Normal observations can occasionally fall outside that band. Following Dan's diagnostic-only direction recorded by Claude on the coordination board, the band does not drive status-dot alarms: red means a detector finding or trip, green means covered and current data with no finding, and hollow grey means unassessed or incomplete. The dot is not a forecast.

The condition rule above uses sustained combined evidence and its own stated thresholds. Scenario truth is only used for evaluation and never passed into analysis.
