# INC-ESC03-20260918: blind AI-assisted investigation (v1 demonstration)

**Synthetic exercise.** Northgate Station, ESC-03 and every record here are invented.

SignalDesk step 1 brings an asset's information together in one place. This demonstration tests step 2: given that centralised evidence, can an AI help an engineer piece together what happened when equipment breaks down?

An escalator broke down on a busy Friday evening. The breakdown was generated with a known cause, which is **sealed outside this repository**. Fresh AI investigators receive only the evidence bucket, with no access to the cause or to this conversation, and are asked for plausible causes, supporting and contradicting evidence, missing information, and the next check that would distinguish between them. "Insufficient evidence" is an acceptable conclusion.

## Layout

| Path | Contents | Who reads it |
| --- | --- | --- |
| `bucket/` | The evidence package and `BRIEF.md` | Investigators: this folder only |
| `investigations/` | One report per blind investigator, unedited | Humans, after the run |
| `README.md` | This file | Humans |

The bucket deliberately contains imperfect evidence:
- sensor readings with a gap around the incident;
- controller alarms on an unsynchronised clock;
- a maintenance report that may or may not be relevant;
- a technician's note that is vague and partly contradictory.

## Running another blind investigation

Open a fresh chat (Claude Code or Codex) in this workspace and paste:

> Read `05_Current_Prototype/incidents/ESC-03_2026-09-18/bucket/BRIEF.md` and carry out the investigation it describes. Read only files inside that `bucket` folder. Write your report to `05_Current_Prototype/incidents/ESC-03_2026-09-18/investigations/<your-name>.md`.

Do not tell the investigator anything else about the incident.

## Integrity

The answer key, scoring rubric and generator were written before any investigation and are kept outside the repository. Their SHA-256 hashes, recorded here before the first run, let anyone check later that they were not changed after seeing the investigators' answers:

| Sealed file | SHA-256 |
| --- | --- |
| `answer_key.md` | `db7d011838aed5581c003b41b94e0d1dc4cae98b58985102b3f4f9a1b9ee5288` |
| `rubric.md` | `ce3e35f6148ee5a118136c06e50ad85f7dcac6b6a55a154c51314879052bc6e2` |
| `generate_bucket.py` | `fa19b87f7db6956aa3580afde97682e05804de0472be8dd1379dc9ed66caf956` |

Each bucket file's own hash is in `bucket/manifest.json`.

## Results: first blind run (5 October 2026)

| Report | Investigator | Conclusion type | Score against the sealed rubric |
| --- | --- | --- | --- |
| [inv-01](investigations/inv-01.md) | Claude Opus subagent, fresh context | Leading hypothesis, not confirmed | 20 / 20 |
| [inv-02](investigations/inv-02.md) | Claude Sonnet subagent, fresh context | Leading hypothesis, not confirmed | 14 / 20 |

- Each investigator worked independently for about 24 minutes and saw only `bucket/`.
- The reports are unedited.
- The detailed scoring is sealed with the answer key, so these results don't spoil later blind runs.
- **Verification limit:** both investigators report reading only the bucket, and both cite only bucket evidence, but file access could not be independently audited.

## Metadata for later API routing (not implemented)

The real product may route evidence in through vendor APIs instead of file exports. The manifest already records, for each source, what that routing would need: `source_id`, `system`, `interface`, `retrieved_at` and `retrieved_by`, `time_basis` (clock, timezone, synchronisation), `cadence`, `columns` and point catalogue, `coverage`, `known_issues` and `sha256`, plus the asset's aliases in each system (`NGS-ESC-03`, `ESC03`, `ESC-03`). No routing is built here.
