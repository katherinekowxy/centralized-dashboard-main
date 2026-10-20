# ESC-03 stoppage, Friday 18 September 2026 — Investigation inv-02

Prepared for the duty maintenance engineer, Northgate Station, Saturday 19 September 2026.
Scope: evidence in the bucket folder only (`manifest.json`, `asset_profile.md`, `sensor_readings.csv`, `vendor_alarms.csv`, `maintenance_report_2026-09-04.md`, `technician_note_2026-09-18.txt`).

---

## 1. Summary

ESC-03 (Concourse to Platform 2) tripped on a **DRIVE FAULT / SAFETY CIRCUIT OPEN** pair during the loaded evening-down run on 18 September, re-tripped twice more on restart within about six minutes, and locked out on a start-limit (`event_no` 3174–3183). A contractor technician power-cycled it, reset the lockout and returned it to service roughly 65–70 minutes after the first trip. The controller's own data shows a **HANDRAIL SPEED DEVIATION – LEFT** alarm one second after the first trip, and the left handrail had been running marginally (intermittently below the 95% pre-warning line) for days; but the same generic fault pair had already occurred, unexplained, on the two preceding evenings without that specific code, and the condition-monitoring telemetry for the actual fault instant is missing (the gateway was offline 17:20–17:59 UTC). **Safety flag:** a passenger reportedly nearly fell during the stoppage; the incident report and CCTV for this have been requested but not received, and the unit was returned to service that night without full diagnostic checks ("No time for full checks" — technician's note), with the next scheduled PM not until 02/10/2026.

## 2. Reconciled timeline (UTC)

### How the clocks were aligned

Three clocks are in play: the condition-monitoring gateway (`sensor_readings.csv`, **NTP-synchronised, UTC** — treated as the reference clock), the escalator safety controller (`vendor_alarms.csv`, **manually-set local clock, no timezone stored, last-set time unknown** per the manifest), and the technician's call-out note (**approximate local time, written from memory**).

The controller clock was reconciled against the UTC reference empirically, not assumed:

- The asset profile states the controller timer starts the unit UP at 05:00 and stops it at 01:00 (controller clock). The sensor feed's `operating_mode` switches from `stopped` to `running_up` at **exactly 03:56:00 UTC on every one of the five mornings in the dataset** (15–19 Sep, matching controller events 3133, 3141, 3153, 3168, 3193, each logged as `05:00:00`), and switches to `stopped` at **23:56:00 UTC** every night (matching the `01:00:00` timer stop). That is consistent, to the limit of 1-minute sensor sampling, with **controller time = UTC + 1h04m** (i.e. the controller clock reads about 4 minutes fast relative to true Europe/London local time / BST).
- A much tighter, independent check: the technician's isolator power-cycle is logged as `E01 POWER ON` at controller time `2026-09-18 19:03:15` (`event_no` 3184). Converting with the same +1h04m offset gives **17:59:15 UTC**, which is **5 seconds** away from the gateway's own independently-logged restart time of **17:59:20Z** ("a restart at 17:59:20Z after a supply interruption" — manifest). Two independent clocks (controller and gateway) agree to within 5 seconds on this event, which is strong confirmation of the offset.
- The technician's own approximate times corroborate the derived sequence closely (see table): "approx 15 min" for the UP test run vs. a derived 15 min 10 s; "back in service 19:30ish" vs. a derived 19:29:40 true-local.

**Confidence: high** that `controller_time − 1h04m = UTC` for the period 14–19 Sep 2026, based on five concordant daily transitions plus one five-second cross-system match. This is a derived offset, not a vendor-confirmed setting — the manifest is explicit that the controller clock is unsynchronised and its last-set time unknown, so the offset should not be assumed to hold outside this window without re-checking.

The maintenance report (04/09/2026) uses its own stated local site time and is included below only as background context; it is 11 days before the incident and not part of the fine-grained reconciliation.

### Timeline

All times UTC. "(est.)" marks a time derived from `vendor_alarms.csv` via the −1h04m offset above; sensor-sourced times are exact (`observed_at`, NTP-synchronised). Technician-note times are the writer's own approximations and are shown converted straightforwardly from local BST (local − 1h) with no other adjustment.

| UTC time | Source | Event |
| --- | --- | --- |
| 2026-09-04 21:10 – 2026-09-05 01:35 | SRC-CMMS (local, context only) | Contractor night visit (WO-55218). LH handrail found slack, adjusted to 97% (RH 100%). Brake lining 1.2 mm (replace at 1.0 mm), stopping distance 0.42 m, "recommend replacing... within two visits." Inverter cooling fan replaced (bearing noisy). Fault memory reviewed, **not cleared**. |
| 09-16 17:08:41 (est.) | SRC-CTRL `event_no` 3148/3149 | **F31 DRIVE FAULT + F02 SAFETY CIRCUIT OPEN** (controller 18:12:41), running_down. |
| 09-16 17:09:00 | SRC-CM | Step speed/current to 0; `gearbox_vibration_mm_s` spikes to **2.90 mm/s** (`reading_id` CM-ESC03-20260916T1709-VIB), `operating_mode` = `fault`. |
| 09-16 17:11:30 (est.) | SRC-CTRL 3150 | KEY START — single restart, **no re-trip**. |
| 09-17 13:22:13 (est.) | SRC-CTRL 3159/3160 | F05 EMERGENCY STOP BUTTON – LOWER LANDING + F02 (unrelated manual stop, daytime, running_down). Restarted 3 min later (3161). Included as a comparison case (see §3, §4). |
| 09-17 16:54:09 (est.) | SRC-CTRL 3162/3163 | **F31 DRIVE FAULT + F02 SAFETY CIRCUIT OPEN** (controller 17:58:09), running_down. |
| 09-17 16:54:00 | SRC-CM | Same signature: speed/current to 0, vibration spikes to **2.78 mm/s** (`reading_id` CM-ESC03-20260917T1654-VIB), mode = `fault`. |
| 09-17 16:58:11 (est.) | SRC-CTRL 3164 | KEY START — single restart, **no re-trip**. |
| **09-18 16:59:49 (est.)** | SRC-CTRL 3169 | W12 HANDRAIL SPEED LOW – LEFT (pre-warning; controller 18:03:49). |
| 09-18 16:30–17:19 | SRC-CM | `handrail_left_pct` fluctuating 93.4–96.6%, repeatedly under the 95% line (e.g. **93.4%** at 17:16:00Z, `reading_id` CM-ESC03-20260918T1716-HRL) with no further W12 logged. `handrail_right_pct` steady 99.5–100.5%. `motor_current_a` 12.4–15.5A, `supply_voltage_v` 396.7–399.2V, `gearbox_oil_temp_c` 29.3–30.2°C — all unremarkable. `passenger_flow_ppm` climbing to 80–92 persons/min (flagged `low_confidence` ≥80, likely undercounting a dense crowd). |
| 09-18 17:19:00 | SRC-CM | **Last reading before the gap.** `handrail_left_pct` 94.5% (CM-ESC03-20260918T1719-HRL), step speed 0.499 m/s, running_down. |
| 09-18 17:20–17:59 | SRC-CM | **Condition-monitoring gap — zero rows** (confirmed by query). Gateway cellular registration lost from 17:21:07Z (manifest). No telemetry for the fault itself. |
| **09-18 17:23:52 (est.)** | SRC-CTRL 3174/3175 | **F31 DRIVE FAULT + F02 SAFETY CIRCUIT OPEN** (controller 18:27:52) — the reported stoppage. |
| **09-18 17:23:53 (est.)** | SRC-CTRL 3176 | **F12 HANDRAIL SPEED DEVIATION – LEFT** (controller 18:27:53), one second later. |
| ~09-18 17:27–17:30 | SRC-CALLOUT | Station staff "restarted it 2x, kept tripping straight away" — matches the next two events exactly. |
| 09-18 17:27:08 (est.) | SRC-CTRL 3177 | KEY START (restart 1). |
| 09-18 17:27:31 (est.) | SRC-CTRL 3178/3179 | F31/F02 trip again, 23 s after restart. |
| 09-18 17:29:50 (est.) | SRC-CTRL 3180 | KEY START (restart 2). |
| 09-18 17:30:05 (est.) | SRC-CTRL 3181/3182/3183 | F31/F02 trip again + **F45 START LIMIT EXCEEDED – LOCKOUT** ("3 starts within 10 min; reset with service tool"). |
| ~17:41 local note ≈ 16:41 UTC | SRC-CALLOUT | "Called 18:41 by station control – esc out of service, 'stopped with people on it'." One passenger reportedly nearly fell; staff dealt with it ("incident report – dont have a copy"). |
| ~17:55 UTC (local "approx 18:55") | SRC-CALLOUT | Technician T-121 attends. Unit "stopped, locked out on start limit. Display showing HANDRAIL L fault." Checks LH handrail ("bit tight at lower newel, didnt adjust"), RH ok, "Brake ok. Smell of burning in machine space, prob brake after hard stop with full load on." |
| **09-18 17:59:15 (est.)** | SRC-CTRL 3184 | E01 POWER ON — technician power-cycles at the isolator. **Matches the gateway's own restart at 17:59:20Z to within 5 seconds** — the gateway outage's end is explained by this action, not an independent fault. |
| 09-18 18:00:02 (est.) | SRC-CTRL 3185 | R01 FAULT RESET (service tool). |
| 09-18 18:01:10–18:02:30 (est.) | SRC-CTRL 3186/3187 | Direction UP selected; KEY START — technician's no-load test run. |
| 09-18 18:03:00–18:17:00 | SRC-CM | Resumed telemetry: running_up, `handrail_left_pct` now stable **97.3–97.9%** (97.6% at 18:03:00Z, `reading_id` CM-ESC03-20260918T1803-HRL) — close to the technician's own "handrail L showing 98% on display." |
| 09-18 18:17:40 (est.) | SRC-CTRL 3188 | KEY STOP — end of UP test. Duration from KEY START (3187) = **15 min 10 s**, matching "Ran UP empty approx 15 min" almost exactly. |
| 09-18 18:18:10 (est.) | SRC-CTRL 3189 | Direction DOWN selected. |
| **09-18 18:29:40 (est.)** | SRC-CTRL 3190 | KEY START — **back in service, DOWN**. Matches "back in service 19:30ish" closely. `handrail_left_pct` 98.1% at 18:30:00Z (CM-ESC03-20260918T1830-HRL); flow now only 31–36 ppm (peak has eased). |
| local "off site 19:45" ≈ 18:45 UTC | SRC-CALLOUT | Technician departs, having "watched 10 min, fine." Recommends "LH handrail inspection next PM. Brake lining due anyway." |
| 09-18 18:17:40 – 09-19 00:56 | SRC-CM / SRC-CTRL | Unit runs the rest of the evening/night with no further faults logged. |

Total time from first trip (17:23:52 est.) to back-in-service (18:29:40 est.) ≈ **1 h 06 min**.

## 3. Plausible causes, ranked

### Rank 1 — Left handrail speed deviation (friction-drive slip, worst under loaded descent) opened the safety circuit — Confidence: Medium

**Mechanism:** handrails are friction-wheel-driven off the main drive shaft (`asset_profile.md`); the left handrail monitor (pre-warning <95% of step speed, stop on "a larger sustained deviation") appears to have been running marginally for days and crossed its stop threshold during the loaded, down-direction evening run.

**Supporting evidence:**
- `event_no` 3176, **F12 HANDRAIL SPEED DEVIATION – LEFT**, logged one second after the first trip.
- Technician's note: display "showing HANDRAIL L fault" on arrival; he "Checked LH handrail - bit tight at lower newel."
- Maintenance report (04/09), item 3: LH handrail was found **slack** and had just been adjusted to 97% two weeks earlier — a component with a recent history of not holding its set point (slack on 04/09, "tight" on 18/09).
- Recurring LEFT-handrail pre-warnings nearly every day 15–18 Sep (`event_no` 3134, 3142, 3143, 3147, 3154, 3155, 3165, 3169).
- `handrail_left_pct` measured 93.4–96.6% through the hour before the fault, repeatedly under 95% (e.g. 93.4% at 17:16:00Z).
- After the reset, `handrail_left_pct` recovered to a stable 97.3–98.1%, both empty (UP test) and lightly loaded (DOWN) — i.e. the deviation was most pronounced specifically during the heavier, down-direction running that preceded the fault.
- Comparison case: the one clearly *external* safety trip in the log (`event_no` 3159 F05 EMERGENCY STOP + 3160 F02, 17 Sep) logged its own specific code **without** an accompanying F31 DRIVE FAULT. All five evening F31+F02 trips, by contrast, look drive-train-related — consistent with the shaft-coupled handrail monitor rather than a simple external device.

**Contradicting/weakening evidence:**
- F12 was logged on only 1 of the 5 total F31/F02 trips that week — not on 16 or 17 Sep's single trips, nor on the 18th's 2nd/3rd retrips.
- `handrail_left_pct` immediately before each of the three evenings' *first* trips was similar (≈94.5–95.2%) — the 18th's reading was not obviously worse than the 16th's or 17th's.
- The exact value at the instant of the actual trip (17:23:52–53 UTC) falls **inside the sensor gap** — this is inferred from the surrounding minutes, not observed directly.

### Rank 2 — Recurring drive/safety-circuit fault tied to loaded, down-direction (regenerative) running, specific origin undetermined — Confidence: Medium

**Mechanism:** the inverter has a dynamic braking resistor (`asset_profile.md`) used when the loaded step band runs downhill (motor acting as brake/generator). A developing fault anywhere in that energy-dissipation path, or any inverter protection function specific to regenerative operation, would manifest only during loaded descent.

**Supporting evidence:** all 5 F31 DRIVE FAULT + F02 SAFETY CIRCUIT OPEN events in the log (16, 17, 18×3 Sep) occurred while `operating_mode` was `running_down`; **none** occurred `running_up`, even though running_up carried the week's highest recorded current (28.33A at 2026-09-18 07:07:00Z) and flow (104 persons/min, same timestamp) — absolute load/current alone does not explain an evening-only, down-only pattern.

**Contradicting/weakening evidence:** direction and time-of-day are perfectly confounded by ESC-03's fixed daily schedule (up only 05:00–13:00, down only 13:00–01:00), so this dataset cannot separate a "down-direction" effect from a generic "evening" effect. No DC-bus, braking-resistor, or motor-winding temperature point is monitored, so this is a pattern-level inference from direction and general drive engineering, not a measured electrical anomaly. May overlap with, rather than compete against, Rank 1.

### Rank 3 — Hard-stop mechanical/thermal stress (brake drag or heat) as a compounding factor, not the initiator — Confidence: Low-medium as contributing; low as root cause

**Mechanism:** whichever fault initiated the trip, the loaded step band had to be brought to rest suddenly; repeated hard stops/restarts under load could heat the service brake.

**Supporting evidence:** technician's note, "Smell of burning in machine space, prob brake after hard stop with full load on"; independently-confirmed hard-stop signature — `gearbox_vibration_mm_s` spikes to 2.90 mm/s (16 Sep) and 2.78 mm/s (17 Sep) in the exact one-minute sample where the unit stops (no equivalent sample exists for the 18th — it's in the gap); maintenance report flags brake lining at 1.2 mm, replace at 1.0 mm, "recommend replacing... within two visits."

**Contradicting/weakening evidence:** technician explicitly checked and found "Brake ok," and hedges the burning-smell diagnosis with "prob" — his own words, not a confirmed finding; "No time for full checks"; no brake-temperature telemetry exists anywhere in the monitored point set; stopping distance was within limits at the last service (0.42 m of 0.20–1.00 m); no brake-specific fault code appears anywhere in the 64-event memory.

### Rank 4 — Coincidental, unrelated gateway/cellular or supply disturbance — Confidence: Low

**Mechanism:** the gateway's cellular dropout (17:21:07Z) occurred only ~2 min 45 s before the first fault — possibly coincidental, possibly a symptom of a shared disturbance.

**Supporting evidence:** temporal proximity only.

**Contradicting evidence:** the last `supply_voltage_v` reading before the gap (397.1V at 17:19:00Z) was normal, no dip; the gateway's eventual *restart* (17:59:20Z) is independently and precisely explained by the technician's deliberate isolator power-cycle (5-second match) — so at least the end of the outage has nothing to do with a mystery fault; the manifest documents the cellular loss and the "supply interruption" restart as two separate known issues.

## 4. Conflicts and data-quality issues

- **Controller clock** is unsynchronised, manually set, last-set time unknown (manifest). Reconciled empirically to ≈ UTC + 1h04m (§2) — treated as derived, not vendor-confirmed, and specific to this 14–19 Sep window.
- **Condition-monitoring gap, 2026-09-18 ~17:20–17:59Z** (confirmed: zero sensor rows in that window). This removes *all* telemetry for the actual fault instant and both immediate re-trips — the single most damaging gap for this investigation, since it falls exactly inside the critical ~7-minute fault window.
- **W12 pre-warning appears to under-log actual excursions**: between the last logged W12 (16:59:49 UTC est.) and the fault (17:23:52 UTC est.), sensor data shows `handrail_left_pct` below 95% in at least 8 separate one-minute samples (e.g. 93.4% at 17:16:00Z), yet no further W12 was recorded. Absence of a logged pre-warning in this log should not be read as "value was fine" — the alarm text log under-represents what the raw telemetry shows.
- **F12 inconsistency**: the specific handrail-deviation code was logged on only 1 of 5 F31/F02 trip events this week. We cannot tell from the data alone whether the other four had a different trigger or whether this is normal debounce/latching behaviour the vendor manual would explain (not included in this bucket).
- Known **duplicate-batch** issue (16 Sep 10:55–11:00Z uploaded twice, confirmed present) and **firmware-update gap** (17 Sep 01:06–01:24Z) are both outside the incident window and did not affect this analysis.
- `passenger_flow_ppm` ≥ 80 is flagged `low_confidence` (manifest: undercounts in dense crowds) — the 80–92 ppm readings before the fault are a lower bound on actual crowding, not a precise count.
- **Technician note times are explicitly approximate** ("ish", written up from a notebook after the visit). Treated throughout as corroboration rather than as the primary clock. In every case checked, they matched the controller-derived, offset-corrected timeline to within a few minutes, which is itself a useful cross-check that increases confidence in both sources.
- **Station incident report and CCTV** (requested 2026-09-19 08:10 local, not received per manifest) mean the "passenger nearly fell" detail cannot be independently verified, timed, or located to a specific landing from anything in this bucket.

## 5. Missing information

- **Vendor fault-code manual / full code definitions** for F02, F31, F12, F45 — needed to know definitively what else (besides handrail deviation) can raise a generic F31+F02 pair, and whether repeat trips within one lockout episode are expected to (not) re-log a specific cause code. Not included per manifest known_issues.
- **Inverter's own internal diagnostic/fault log**, if one exists separately from the safety controller's 64-event memory — would show a specific drive-internal code (overcurrent, DC-bus overvoltage, thermal, etc.) rather than the generic "DRIVE FAULT" text, and could directly confirm or rule out Rank 2.
- **Brake temperature, inverter heatsink/DC-bus, or motor-winding temperature telemetry** — none of these points are monitored, so neither the burning-smell hypothesis nor the regenerative-fault hypothesis can be checked against data.
- **The actual buffered readings for 17:20–17:59Z on 18 Sep**, if recoverable from the gateway's local storage before being overwritten — the manifest states the unsent buffer "was discarded," but it may be worth confirming with the vendor/integrator whether it is still retrievable.
- **The outstanding station incident report and CCTV** for the near-fall — matters for passenger-safety follow-up independent of the technical root cause, and could supply an independent timestamp.
- **Whether other station equipment on the same electrical supply or cellular coverage** showed any disturbance around 17:20–17:24Z on 18 Sep, to properly assess (or dismiss) Rank 4.
- **A direct, loaded, down-direction inspection of the LH handrail** — watching the live percentage under representative passenger load — to test the load-dependence pattern seen in the data under controlled, observed conditions.

## 6. Next check

**Single best check:** Retrieve and inspect the frequency inverter's own internal fault history (if it keeps one separately from the safety controller's short-text memory) for the five F31/F02 timestamps — 16 Sep 17:08:41, 17 Sep 16:54:09, and 18 Sep 17:23:52 / 17:27:31 / 17:30:05 (all UTC, est.; add 1h04m for the inverter's local display if it shares the controller's clock).

- If the inverter log shows nothing but a generic "external enable / run-permissive removed" at each of these times → the drive itself saw no internal problem and was simply told to stop by the safety circuit. This supports **Rank 1** (handrail-driven trip) and weighs against Rank 2.
- If the inverter log shows a specific internal fault (DC-bus overvoltage, overcurrent, braking-resistor/thermal) at each time, especially one tied to regenerative operation → this supports **Rank 2** over Rank 1.
- If the internal logs differ between the 16th/17th events and the 18th's first trip → the three evenings do not share one cause, and both mechanisms (or something else) may be in play independently.

**Follow-up checks if the above is inconclusive:**
1. Physically test the LH handrail speed under a representative passenger load in the DOWN direction (watching the display or live condition-monitoring feed), to see whether the deviation reproduces.
2. Chase the outstanding station incident report and CCTV to independently corroborate the sequence and assess the passenger-safety severity of the near-fall.

## 7. Conclusion

**Leading hypothesis, not confirmed:** an intermittent left-handrail speed deviation, most pronounced during loaded down-direction running, most plausibly opened the safety circuit and caused the 18 September drive fault and lockout — because the controller logged a specific HANDRAIL SPEED DEVIATION – LEFT alarm and a matching display message at the first trip, and the left handrail had a documented history of running marginally, but the telemetry for the fault instant itself is missing, the same generic fault pair occurred unexplained on two prior evenings without that specific code, and an inverter/braking-circuit fault under loaded descent remains a credible, unexcluded alternative.
