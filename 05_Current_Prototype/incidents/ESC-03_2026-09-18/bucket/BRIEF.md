# Investigation brief: ESC-03 stoppage, Friday 18 September 2026

**Synthetic exercise.** All sites, people, equipment and data are invented.

You are assisting the duty maintenance engineer at Northgate Station. It is Saturday 19 September 2026, 08:30 local time. On Friday evening, escalator ESC-03 stopped during the peak. Station staff restarted it twice, it locked out, and a contractor technician returned it to service later that evening. Before deciding what to do next, the engineer wants an evidence-based view of what may have happened.

## Rules

- Read only the files in this folder. Do not open other folders in the workspace, search elsewhere, or look up case-specific information online. General engineering knowledge is fine.
- Treat every source as imperfect. Clocks may disagree, data may be missing, and people's notes may be wrong or incomplete.
- Do not fill gaps with assumed values. Keep what the evidence shows separate from what you infer, and say how confident you are.
- "Insufficient evidence" is an acceptable conclusion. A well-argued "cannot tell yet, and here is the check that would tell" is better than a confident guess.
- You advise the engineer; you do not decide whether the escalator stays in service. Flag any safety concern you see.

## Files

| File | What it is |
| --- | --- |
| `manifest.json` | What each source is, its clock and time basis, coverage, known gaps and file hashes |
| `asset_profile.md` | Asset register extract for ESC-03 |
| `sensor_readings.csv` | Condition-monitoring readings, long format, one sample per point per minute |
| `vendor_alarms.csv` | Export of the escalator controller's fault memory |
| `maintenance_report_2026-09-04.md` | The most recent contractor service report |
| `technician_note_2026-09-18.txt` | The technician's call-out note from Friday evening |

Use Python and pandas for the CSV files; they are too large to read by eye.

## Deliverable

A Markdown report with these sections, in this order:

1. **Summary**: three to five lines.
2. **Reconciled timeline (UTC)**: the key events from all sources on one time basis. State how you aligned the clocks and how sure you are of the alignment.
3. **Plausible causes, ranked**: for each, the mechanism in one or two sentences, the supporting evidence, the contradicting or weakening evidence, and your confidence (low, medium or high).
4. **Conflicts and data-quality issues**: where the sources disagree or cannot be trusted, and how you handled it.
5. **Missing information**: what you would want that is not in this folder, and why it matters.
6. **Next check**: the single check that best distinguishes between your leading explanations, and what each possible result would mean. Add one or two follow-up checks if needed.
7. **Conclusion**: one of "Probable cause: …", "Leading hypothesis, not confirmed: …", or "Insufficient evidence", followed by one sentence saying why.

Cite evidence specifically: an alarm's `event_no`, a reading's `reading_id` (or its point and UTC time), and short quotes from the report or the note.
