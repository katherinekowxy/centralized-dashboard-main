# ESC-03 stoppage, Friday 18 September 2026: investigation report (inv-01)

**Basis.** This report uses only the files in `bucket/`: `BRIEF.md`, `manifest.json`, `asset_profile.md`, `sensor_readings.csv`, `vendor_alarms.csv`, `maintenance_report_2026-09-04.md` and `technician_note_2026-09-18.txt`. The SHA-256 hashes of the four hashed sources match the manifest. Record counts also match: 37,976 readings and 64 alarms.

**Conventions.**
- Times are UTC unless marked BST (UTC+1).
- Alarms are cited as `#event_no`.
- Readings are cited by `reading_id`, or by point and UTC minute.
- "Flow" is `passenger_flow_ppm` (persons/min at the upper landing).
- "HRL" and "HRR" are `handrail_left_pct` and `handrail_right_pct`.
- "MCUR" is `motor_current_a`.

---

## 1. Summary

- At **17:23:42 UTC (18:23 BST)**, ESC-03 stopped while running DOWN at the evening peak. The controller logged **F31 DRIVE FAULT** first (#3174, with F02 #3175). The left-handrail fault F12 (#3176) came **one second later**. Staff restarted it twice, and both restarts tripped on F31 again, after 23 s and 15 s (#3178, #3181). The second trip set the F45 lockout (#3183).
- The same F31 trip happened at the DOWN evening peak on 16 and 17 Sept (#3148, #3162). It never happened at the busier UP morning peaks, even though those draw almost twice the motor current (up to 28.3 A against 15.5 A) and show a *slower* left handrail (down to 92.6 %). The motor-current pattern shows the drive is regenerating at evening DOWN peaks.
- **Leading hypothesis (not confirmed):** the inverter trips when it has to absorb regenerated energy under heavy DOWN load; the braking resistor or chopper path is the suspect. The handrail F12 is more likely a consequence of the hard stop than its cause. The inverter's own fault code has not been read, and the monitoring data for 17:20 to 17:59 UTC were lost.
- **Safety:** nothing was repaired on Friday, and the unit has not run DOWN under heavy load since the reset, so another hard stop with descending passengers is credible. There are two separate concerns:
  - The left handrail runs slow and gets slower under load.
  - The brake had 1.2 mm of lining on 4 Sept and has made at least six recorded fault stops since (five drive faults and one emergency stop), at least three of them while running DOWN with heavy load. There is also an unexplained burning smell.

---

## 2. Reconciled timeline (UTC)

### 2.1 How the clocks were aligned

| Source | Time basis | Treatment |
| --- | --- | --- |
| Condition monitoring (`sensor_readings.csv`) | UTC, gateway clock NTP-synchronised | Used as the reference |
| Controller fault memory (`vendor_alarms.csv`) | Local clock, no timezone stored, set manually, not NTP | Offset derived from the CM data (below) |
| Technician note | "Technician's own approximate local times" | Read as BST and checked against controller events |
| Maintenance report | Local site time, dd/mm/yyyy | Read as BST |

**Method.**
- Some controller events must change the running state. These are timer start and stop (A01, A02), key start and stop (K01, K02) and fault stops (F31, F05).
- For each one, I found the last gateway `operating_mode` sample in the old state and the first sample in the new state. The event has to fall between them, which bounds the offset.
- All **23** such events with CM coverage, from 16 to 19 Sept, fit **one constant offset: UTC = controller time − 1 h 04 min 10 s**.
  - The intersection of all the bounds is 1:04:09 to 1:04:11.
  - The tightest pair is F31 #3162 and K01 #3164 on 17 Sept. Leaving them out still gives 1:04:00 to 1:04:13.
  - Each day's bounds contain 1:04:10, so no drift is detectable over the four days.
  - The likely explanation is that the controller is set to BST and runs about 4 min 10 s fast. As a result, its "05:00" timer start happens at 04:55:50 BST.

**Independent cross-checks.**
- E01 POWER ON (#3184) converts to 17:59:05 UTC. The manifest records a gateway restart "at 17:59:20Z after a supply interruption". That is 15 s later, which is consistent with the gateway booting after the technician's "Power cycled at isolator". The gateway is powered from the controller's auxiliary supply.
- For 7 of the 8 W12 pre-warnings with CM coverage, the next HRL minute sample after the UTC-converted time is below 95 %. The eighth is exactly 95.0.
- Every time in the technician's note that can be checked agrees with the controller to within about 1 to 2 minutes when read as BST. For example, "Ran UP empty approx 15 min" matches 18:02:20 to 18:17:30, and "back in service 19:30ish" matches K01 at 18:29:30 UTC (19:29:30 BST).

**Confidence.**
- **High** for controller events, to within about ±10 s. That bound assumes the gateway's mode sample reflects the state at the minute mark; a few seconds of polling latency would widen it slightly.
- **Medium** for the technician's times, to within about ±5 min.

### 2.2 Timeline

| UTC | Source | Event |
| --- | --- | --- |
| 04/09 21:10 to 05/09 01:35 | Report NVT-SR-26-0904-03 | Monthly PM.<br>Left handrail "slack ... tension adjusted ... left 97 %, right 100 %".<br>"inverter cooling fan replaced ... Cabinet vacuumed, filters replaced. Terminals visually checked".<br>Brake "1.2 mm lining remaining (replace at 1.0 mm)".<br>Fault memory "F50 ×1 (comb), W03 ×2 since last visit" (no F31, no W12). |
| 14/09 15:26:34 | #3130 K01 | Earliest retained event, an off-schedule KEY START. The stop before it has been overwritten. |
| 15/09 07:03:02 | #3134 W12 | Left handrail speed low (AM, UP). No evening W12 or F31 that day; no CM data. |
| 16/09 06:30:46, 07:16:42 | #3142, #3143 W12; CM | AM UP peak: flow up to 90/min, MCUR up to 25.77 A (`CM-ESC03-20260916T0716-MCUR`), HRL down to 93.7 %. **No trip.** |
| 16/09 16:21:40 | #3147 W12 | PM DOWN peak building. Highest load of the evening at 16:22: 90/min, 15.09 A. |
| **16/09 17:08:31** | **#3148 F31, #3149 F02** | DOWN. Minute before: flow 76, MCUR 13.80 A, HRL 95.2 %, VOLT 398.3 V (`CM-ESC03-20260916T1708-*`). Stop-minute VIB 2.90 mm/s (`…T1709-VIB`). |
| 16/09 17:11:20 | #3150 K01 | Restart after 2 min 49 s. Ran for the rest of the peak (flow up to 79/min). |
| 17/09 07:22 | CM | AM UP peak: flow 104/min, **MCUR 28.26 A**, **HRL 92.6 %** (`CM-ESC03-20260917T0722-*`); W12 #3154, #3155. **No trip.** |
| 17/09 13:22:03 | #3159 F05, #3160 F02 | Emergency stop at lower landing. **No F31 logged.** Stop-minute VIB 2.83 (`CM-ESC03-20260917T1323-VIB`). Restart at 13:25:30 (#3161). |
| **17/09 16:53:59** | **#3162 F31, #3163 F02** | DOWN. Minute before: flow 78, MCUR 13.74 A, HRL 95.2 %, VOLT 397.7 V (`CM-ESC03-20260917T1653-*`). Stop-minute VIB 2.78. |
| 17/09 16:58:01 | #3164 K01 | Restart after 4 min 02 s straight into heavy load (76/min at 16:59). **No repeat trip**, even though the evening's highest DOWN load came later (85/min, 14.76 A at 17:22, `CM-ESC03-20260917T1722-*`). |
| 18/09 03:55:50 | #3168 A01 | Timer start, UP. |
| 18/09 07:07 | CM | AM UP peak: flow 104/min, **MCUR 28.33 A**, HRL 92.9 % (`CM-ESC03-20260918T0707-*`); W12 #3169 at 06:59:39. **No trip.** |
| 18/09 11:59:37 to 12:01:19 | #3170 to #3172 | Staff reverse to DOWN. |
| 18/09 from about 15:26 | CM | The 10-minute mean DOWN flow stays above the balance point of about 45/min, so the drive is regenerating (see H1). |
| 18/09 16:59:43 | #3173 W12 | HRL 94.4 % at 17:00. |
| 18/09 17:00 to 17:19 | CM | Heaviest evening load of the week.<br>Flow 79 to 92/min, mostly `low_confidence`, so possibly undercounted.<br>MCUR up to **15.50 A** and HRL down to **93.4 %** (`CM-ESC03-20260918T1716-MCUR`, `-HRL`).<br>Last sample at 17:19: flow 84, MCUR 14.32 A, GBT 30.2 °C, VOLT 397.1 V. |
| 18/09 17:20:16 | CM ingest | Last batch uploaded (17:15 to 17:19). |
| 18/09 17:21:07 | Manifest | Gateway loses cellular registration. It keeps running and buffering; it does not restart. |
| **18/09 17:23:42** | **#3174 F31, #3175 F02** | **Drive fault, safety circuit open. The escalator stops hard while running DOWN with passengers** ("stopped with people on it"). |
| 18/09 17:23:43 | #3176 F12 | "HANDRAIL SPEED DEVIATION - LEFT", detail "monitor". |
| 18/09 17:26:58, 17:27:21 | #3177 K01; #3178 F31, #3179 F02 | Staff restart 1. Drive fault after **23 s**. |
| 18/09 17:29:40, 17:29:55 | #3180 K01; #3181 F31, #3182 F02, #3183 F45 | Staff restart 2. Drive fault after **15 s**, then lockout. A passenger "nearly fell" during one of the three stops; which one is not recorded. |
| 18/09 about 17:41 | Note | "Called 18:41 by station control". |
| 18/09 about 17:55 | Note | "Attended approx 18:55".<br>"Display showing HANDRAIL L fault".<br>"LH handrail - bit tight at lower newel, didnt adjust".<br>"Brake ok. Smell of burning in machine space, prob brake". |
| 18/09 17:59:05 | #3184 E01 | Power on after isolator power cycle. |
| 18/09 17:59:20 | Manifest | Gateway restarts. The unsent buffer for 17:20 to 17:59 is **discarded**. |
| 18/09 17:59:52 | #3185 R01 | Lockout reset with the service tool. |
| 18/09 18:02:20 to 18:17:30 | #3187, #3188; CM | UP empty test run: flow 0, MCUR 13.8 to 14.7 A, HRL 97.3 to 97.9 % (e.g. `CM-ESC03-20260918T1810-HRL` = 97.6). This matches "handrail L showing 98%". |
| 18/09 18:29:30 | #3190 K01 | Back in service DOWN ("19:30ish"). Flow 23 to 39/min while it was "watched 10 min". |
| 18/09 about 18:45 | Note | "Off site 19:45". |
| 18/09 18:30 to 23:55 | CM | DOWN service. Maximum flow **44/min** (`CM-ESC03-20260918T1856-FLOW`), which is around the regeneration balance point. **No heavy DOWN load since the reset.** No events. |
| 18/09 23:55:50; 19/09 03:55:50 | #3191 A02; #3193 A01 | Timer stop, then timer start UP. CM is normal up to 07:00 (flow up to 34/min). |

---

## 3. Plausible causes, ranked

### H1. The inverter trips while regenerating under heavy DOWN load, because the braking-energy path cannot absorb the energy (confidence: medium)

**Mechanism.** Above roughly 45 to 55 persons/min going DOWN, the passengers' weight drives the step band and the motor becomes a generator. The inverter must dump that energy into its dynamic braking resistor ("frequency inverter (2019) with a dynamic braking resistor, both in the upper machine space"). If the resistor, chopper, wiring or braking settings cannot absorb it, the drive trips on DC-link overvoltage or braking overload. That gives F31, the safety circuit opens (F02), and the brake drops at full speed.

**Supporting evidence.**
- **Every** F31 (#3148, #3162, #3174, #3178, #3181) happened while running DOWN in the evening peak, between 16:53 and 17:30 UTC. Each came after roughly 1.5 to 2 h of sustained DOWN flow above the balance point: about 96, 90 and 118 min. There were none in UP and none off-peak.
- **The drive is regenerating in exactly those conditions.** This is inferred, because the current sensor measures magnitude only:
  - In UP, MCUR rises steadily with flow, from 14.56 A at 0 to 5/min to 27.91 A at 95 to 110/min (r = 0.99).
  - In DOWN, MCUR is V-shaped: 13.97 A at 0 to 5/min, a minimum of 13.04 A at 35 to 55/min, then 14.87 A at 85 to 95/min.
  - The minimum is the balance point. Above it, the motor is braking a load that is pulling it along.
  - A rough estimate puts the energy fed back at several kW for one to two hours. This uses general physics and is not measured: about 40 people on a 7.2 m rise at 0.5 m/s, minus friction.
- **Higher current and heat in UP never caused a trip.** The morning UP peaks put roughly twice the current through the inverter and motor (28.33 A at `CM-ESC03-20260918T0707-MCUR`) and make the gearbox hotter (37.8 °C against about 30 °C), with no trip. That argues against overcurrent, mechanical overload and general inverter overheating, and points to something that only happens during regeneration.
- **F31 is not a side effect of any stop.** The emergency stop at 13:22:03 on 17 Sept (#3159) opened the safety circuit without any F31, so F31 is a drive-originated fault, not something logged whenever the circuit opens.
- **18 Sept was the most extreme day, and the only one where restarts re-tripped.** It had the heaviest evening flow (up to 92/min, likely undercounted), the highest DOWN current (15.50 A) and the longest regeneration. It was the only day on which restarts re-tripped, after 23 s and 15 s. That fits a loaded DOWN restart, which needs full regenerative braking straight away.
- **Nothing tripped after the reset because nothing regenerated much.** After the reset the unit ran UP empty and then DOWN at 44/min or less, near the balance point, so there was little regeneration and no trip. "Watched 10 min, fine" therefore did not test the failing condition.
- **Lighter evenings had no trips.** The evenings of 14 Sept (after 15:26 UTC) and 15 Sept had no F31 and no evening W12. W12 only appears at about 75/min or more, so those evenings were probably lighter. This is weak support: there are no CM data for those evenings.
- **There is a plausible source for the smell.** The braking resistor would be at its hottest after two hours of regeneration, so it is a credible source of the "Smell of burning in machine space", as an alternative to the technician's "prob brake".
- **There is a possible change point.** The drive cabinet was worked on 14 days earlier ("Cabinet vacuumed ... Terminals visually checked"), and the 4 Sept fault-memory review did not list F31. This is not proven: the controller history between 5 and 14 Sept has been overwritten.

**Contradicting or weakening evidence.**
- F31 is a generic controller code. The vendor descriptions are "not included", and the inverter's own fault code (overvoltage or something else) is not in the bucket. The mechanism is inferred, not observed.
- Trips did not happen at the minutes of highest load:
  - On 16 Sept the peak load (90/min, 15.09 A at 16:22) came 46 min before the trip.
  - On 17 Sept the restart ran straight into 76/min, and the evening's highest DOWN load (85/min at 17:22) followed without a repeat trip.

  So this is not a simple instantaneous threshold. It suggests either a cumulative (thermal) element or an intermittent component, such as a loose or overheating connection. Three days of data cannot separate these.
- Nothing in the monitoring measures DC-link voltage, braking-resistor temperature or inverter temperature.

**Confidence: medium.** The evidence strongly supports a drive-originated, DOWN-and-load-dependent trip. That the braking path specifically is at fault is an inference waiting for the inverter log.

### H2. The inverter overheats because cooling is inadequate after the 4 Sept fan replacement (confidence: low)

**Mechanism.** The replacement "fan, 24 V DC 120 mm" might be wrong, reversed or not running, or the airflow might be restricted. The heatsink then overheats and the drive trips with F31 after long running.

**Supporting evidence.**
- The fan was replaced and the filters changed on 4 Sept.
- The trips come late in long peaks.
- There is a burning smell.

**Contradicting evidence.**
- Inverter losses scale with output current. The current is 1.6 to 1.9 times higher at the morning UP peaks (22 to 28 A for about 2 h) than at the evening trips (13.7 to 14.8 A), yet there were no morning trips.
- Restarts after only 2 min 49 s (16 Sept) and 4 min (17 Sept) held for the rest of the peak. A heatsink over-temperature would not normally clear that fast.

**What would keep it in play.** H2 cannot be excluded if the evening machine-space temperature is much higher than in the morning (there are no ambient or heatsink data), or if the braking chopper shares the fan-cooled heatsink. In that second case, H2 merges with H1.

### H3. The left handrail initiated the stop, as the technician concluded (confidence as the initiating cause: low; confidence that the handrail defect exists: high)

**Mechanism.** The left handrail slips under passenger load until the handrail monitor trips (F12), which stops the escalator.

**Supporting evidence.**
- "Display showing HANDRAIL L fault".
- F12 #3176 was logged in the incident.
- W12 pre-warnings appear at every peak (#3134 to #3173).
- HRL falls by about 0.035 percentage points per person/min and reached 93.4 % shortly before the gap (`CM-ESC03-20260918T1716-HRL`).
- The handrail had a history: on 4 Sept "it was slack ... tension adjusted", and on 18 Sept it was "bit tight at lower newel".

**Contradicting evidence.**
- **Order of events.** F31 and F02 were logged at 17:23:42 and F12 at 17:23:43, so the drive fault was recorded first.
- **Most trips had no handrail fault.** The two restart trips (#3178, #3181) and the 16 and 17 Sept trips (#3148, #3162) were all F31 **without** F12.
- **The handrail is worse in the mornings, which never tripped.** The slip is the same in UP and DOWN for the same flow, and it is **worse** at the morning UP peaks: 92.6 % at `CM-ESC03-20260917T0722-HRL` and 92.9 % on 18 Sept, with 23 to 32 minutes per morning below 95 %. Yet no morning had an F12 or F31.
- **Handrail drag is unlikely to cause a drive fault.** The handrail is friction-driven from the main drive shaft, so binding makes it slip rather than overload the drive. During DOWN regeneration, extra drag would reduce the braking duty, not increase it.
- **The handrail behaved as normal after the reset.** HRL was 97.1 to 98.1 % at light load, the same as its usual 97.6 % no-load level on every day from 15 to 19 Sept. There is no sign of a new handrail failure.
- **The usual stop threshold is far from what was measured.** If the monitor follows the common EN 115-1 setting (a deviation of more than −15 % for more than 15 s; general knowledge, vendor setting unknown), the minute data never came close.

**Likely reading of F12.** The F12 was most plausibly caused by the deceleration of an already-slipping handrail during the brake stop. This cannot be confirmed without the vendor's logic.

### H4. A supply disturbance (dip or phase loss) trips the inverter (confidence: low)

**Supporting evidence.**
- Supply voltage runs 3 to 5 V lower at evening peaks (minimum 396.3 V, `CM-ESC03-20260917T1746-VOLT`) than at other times (400 to 402 V).
- The loss of cellular registration at 17:21:07, 2.5 min before the first trip, is unexplained.
- One-minute samples cannot capture sub-second dips, and the 18 Sept window is missing.

**Contradicting evidence.**
- There was no voltage anomaly in the minute before either the 16 or the 17 Sept trip (398.3 V and 397.7 V).
- The gateway runs on the controller's auxiliary supply and did not restart between 17:21 and 17:59, so there was no supply interruption.
- The trips follow direction and load rather than time of day alone, and a mains dip would also hit the UP mornings.

### H5. Mechanical drag or overload (brake not fully releasing, handrail binding, step band or gearbox) causes an overcurrent trip (confidence: low)

**Supporting evidence.**
- The "Smell of burning" could come from a dragging brake.
- The brake lining was worn (1.2 mm).

**Contradicting evidence.**
- The current at the trips (13.7 to 14.8 A) is far below the 28 A the drive carries every morning.
- The following were steady from day to day between 15 and 19 Sept, and unchanged after the reset:
  - no-load MCUR (about 15.0 A in UP, about 13.7 A in DOWN)
  - no-load vibration (about 1.36 mm/s)
  - no-load HRL (97.6 %)
  - HRR (about 100 %)
- Step speed stayed between 0.496 and 0.504 m/s whenever running.
- Gearbox oil peaked at 37.8 °C and running vibration at 1.91 mm/s.

---

## 4. Conflicts and data-quality issues

| # | Issue | How I handled it |
| --- | --- | --- |
| 1 | The controller clock is unsynchronised and has no timezone. It runs about +4 min 10 s ahead of BST. | Used the derived offset (section 2.1). Human times are matched to it, not to the controller's display. |
| 2 | The technician saw "Display showing HANDRAIL L fault", but the fault memory shows F31 first in every trip, F12 only once (1 s after F31), and F45 as the last event before the visit. | Treated the fault memory as the record of order. The display's selection logic (first fault, priority or latest) is not documented. The technician's diagnosis and the "LH handrail inspection next PM" recommendation came from the display, and the drive fault was not investigated ("No time for full checks"). |
| 3 | "Smell of burning ... prob brake" is the technician's inference. | Kept open. The brake, braking resistor and cabinet terminals are all candidates. |
| 4 | "Brake ok" conflicts with a 1.2 mm lining on 4 Sept and at least six recorded fault stops since (F31 ×5, F05 ×1). | Treated as an unmeasured impression; there is no stopping-distance or lining figure for 18 Sept. |
| 5 | The left handrail was "slack" on 4 Sept but "bit tight at lower newel" on 18 Sept. | Not resolved. Both describe a handrail that is not running correctly. CM shows a constant 97.6 % at no load from 15 to 19 Sept, which matches "left 97 %" after the 4 Sept adjustment. The adjustment never brought it to step speed (EN 115-1 tolerance is 0 to +2 %; general knowledge). |
| 6 | F45 says "3 starts within 10 min", but only two key starts are logged (#3177, #3180). There were three F31 trips within 6 min 13 s. | The counting rule is undocumented and does not affect the cause. |
| 7 | The manifest's gateway "restart ... after a supply interruption" at 17:59:20. | This is the technician's isolator power cycle (E01 at 17:59:05), not a separate supply event. |
| 8 | The CM gap from 17:20 to 17:59 on 18 Sept covers the whole stop, both restarts and the lockout. The data existed in the gateway buffer but were discarded at the power cycle. | The incident window is unobserved. I relied on the controller log, the data before and after the gap, and the two earlier F31 trips, which the CM data do cover. |
| 9 | There is a CM gap on 17 Sept from 01:06 to 01:24 (firmware update). | No impact: the unit was stopped overnight. |
| 10 | Batch 16/09 10:55 to 10:59 was uploaded twice (40 duplicate `reading_id`, identical content). | Deduplicated: one copy of each kept. |
| 11 | The people counter undercounts at 80/min or more. All 136 such readings are `low_confidence`. | Treated as lower bounds. MCUR served as an independent load indicator. |
| 12 | The motor current sensor measures magnitude only (inverter output side). | The direction of power flow (regeneration) is inferred from the V-shaped DOWN curve, not measured. |
| 13 | Readings are one instantaneous sample per minute, and VIB is a one-minute RMS. | They cannot show sub-second events (DC-link voltage, dips, current spikes). The stop-minute VIB spike only shows that a stop was hard: about 2.8 to 2.9 for F31 and F05, against 0.5 to 0.9 for key and timer stops. |
| 14 | The fault memory holds only 64 events. | History before 14/09 16:30:44 (controller time) is lost, including whatever stopped the unit before #3130. On 4 Sept the memory probably covered only about 8 to 10 days, so "since last visit" may not cover the whole month. |
| 15 | W03 "LUBRICATION RESERVOIR LOW" (#3135) appeared on 15 Sept, 11 days after "reservoir topped up". | Unrelated to the stop; flagged for the next PM. |
| 16 | Left and right are defined by the contractor convention; the controller's convention is not documented. | The data are consistent with the two agreeing (the controller's "left" reads 97 %, as the contractor reported), but this is not proven. |
| 17 | The gearbox oil cooled from 30.2 to 25.6 °C across the gap. A night-time cooling fit predicts 24.0 to 24.4 °C. | Consistent with the unit standing still for most of the gap and a slightly warmer evening ambient. It cannot narrow down the stop time. |

---

## 5. Missing information

| Missing | Why it matters |
| --- | --- |
| **Inverter's own fault history and parameter set** (fault codes, time stamps, stored DC-link voltage, current and heatsink temperature, braking-resistor settings) | F31 is generic. This is what separates H1, H2, H4 and H5 (see section 6). |
| Vendor descriptions for F31, F12, W12 and F45, plus the display logic | Would show whether F12 can be set by a brake stop, what the stop threshold and timer are, what F31 covers, and why the display showed "HANDRAIL L". |
| CM data for 17:20 to 17:59 on 18 Sept (discarded) | Would show load, current and handrail speed at the first trip and the restarts. Ask whether any gateway log survives. |
| Station incident report and CCTV of both landings (requested 19/09 08:10, not received) | Would show crowd density at 17:23:42, whether people were on the steps during the restarts, and which stop caused the near-fall. The CCTV clock offset needs to be fixed against a known event, such as the steps stopping at 17:23:42 UTC. |
| Station-control log and staff account | Would show who restarted the escalator and how, whether it was cleared first, and what the display showed after each trip. |
| Braking-resistor rating and as-found condition; details of the 4 Sept cabinet work (fan part, airflow direction, which terminals were "visually checked") | Tests H1 and H2 directly and checks the possible change point. |
| Fault memory or CM history before 14 Sept, and CM data for the evening of 15 Sept | Would show when F31 first appeared (before or after 4 Sept), what stopped the unit before #3130, and the load on an evening without a trip. |
| Brake lining thickness and loaded DOWN stopping distance after the incident | Safety: verifies the brake after several heavy-load brake stops. |
| Machine-space ambient temperature and inverter heatsink temperature | Needed to judge H2. |
| Sub-second power-quality data, and whether other station equipment tripped at 17:23:42 | Needed to exclude H4. |
| Event or crowd forecast for the coming days | Shows how soon the unit will next run DOWN under heavy load. |

---

## 6. Next check

**Read the inverter's own fault history before anything else is power-cycled or reset.** Use the drive keypad or PC tool to save:
- the fault type for each trip
- any stored values (DC-link voltage, output current, heatsink temperature, braking-resistor overload state)
- the full parameter set

Look for five trips. In UTC they should be near 16/09 17:08:31, 17/09 16:53:59 and 18/09 17:23:42, 17:27:21 and 17:29:55. The drive's own clock may differ, so match them by pattern: two single trips on consecutive evenings, then three within 6 min 13 s.

| Result | What it means |
| --- | --- |
| DC-link overvoltage, braking-resistor overload or chopper fault (on all five) | **Supports H1.** Measure the resistor against its nameplate and drive setting, test insulation, check the chopper, and thermally image and torque-check the terminals. Look for heat damage, which may be the source of the smell. Avoid heavy DOWN loading until fixed. |
| Heatsink or inverter overtemperature | **Supports H2.** Check that the new fan runs, its airflow direction and polarity, and the filters. Find out why the higher-current mornings do not trip, for example whether the braking chopper shares the heatsink. |
| Overcurrent, motor overload or torque limit | **Supports H5.** Check brake release (air gap, release monitoring), the handrail drive and the step band. |
| Undervoltage, phase loss or mains fault | **Supports H4.** Fit a power-quality logger at the isolator, and ask whether other station equipment, such as the second Platform 2 escalator, tripped at the same moment. |
| No fault stored, or only "external" or safe-torque-off | F31 is being generated on the controller side. Get vendor support to interpret F31 and F12; H3 regains weight. |
| Different codes on different days | There is more than one problem. Treat 18 Sept separately. |

**Follow-up checks.**
1. **Statically test the braking resistor and chopper, and find the source of the burning smell.** Check resistance, insulation, terminals and any discoloration, and look at the brake lining for glazing. This tests H1 directly even if the drive log is missing or has been cleared.
2. **Obtain the incident report, the CCTV and the station-control log.** Use them to establish the load at each trip, whether passengers were on the steps when staff restarted it, and which stop caused the near-fall. Anchor the CCTV clock to the 17:23:42 UTC stop.

**Safety flags for the duty engineer.** The decision on service is yours; these are concerns, not a ruling.
- **The likely trigger is still present and untested.** Friday's action was a power cycle and reset. Since then the unit has run only UP or at DOWN flows of 44/min or less, never in the condition that tripped it on three evenings in a row. It is due to be reversed to DOWN at about 13:00 controller time (about 11:56 UTC) today. A repeat would be another emergency-type stop with a full load of descending passengers, and the last one coincided with a near-fall. Options to weigh include no DOWN running at peak load, or keeping it out of service, until the inverter log and braking-path checks are done.
- **Brake.** "Recommend replacing the lining within two visits" was written at 1.2 mm on 4 Sept. Since then there have been at least six recorded fault stops (F31 ×5, F05 ×1), at least three of them under heavy DOWN load (#3148, #3162, #3174), and nothing has been measured. Verify the lining and the loaded DOWN stopping distance before heavy DOWN service.
- **Burning smell.** The source has not been identified. An overheating resistor or terminal is also a fire risk.
- **Left handrail.** It runs about 2.4 % slow at no load and 5 to 7 % slow at peaks, outside the usual 0 to +2 % tolerance, and it is worse in UP. A handrail that lags the steps is a fall risk. The technician deferred it to the next PM on 02/10; you may want it done sooner. Confirm that the controller's "left" is the same handrail as the contractor's left.
- **Restart practice.** Two restarts after a drive fault, apparently with passengers present, each ended in another hard stop within 15 to 23 s. Consider an instruction to clear the escalator and not restart after F31 without a competent check. Also avoid power-cycling equipment before its data are retrieved, because that is how the 18 Sept CM data were lost.

---

## 7. Conclusion

**Leading hypothesis, not confirmed: each stoppage started with the inverter tripping (F31) while it was regenerating under heavy DOWN load, most likely because the braking-energy path (braking resistor, chopper, connections or settings) could not absorb the energy. The left-handrail F12 was most likely a consequence of the hard stop, and the handrail's chronic slip is a separate defect.** All five F31 trips happened in DOWN at the evening peaks, and none at the higher-current, worse-handrail UP mornings, which argues strongly against the handrail and against general overload. However, the inverter's own fault code, which would confirm the mechanism, has not been read, and the monitoring data for the incident window were lost.
