# Add an asset and import a vendor CSV

This first import workflow uses a local SQLite registry and a small, explicit CSV contract. Registered assets and imported observations survive app and Python restarts in `data/imports.sqlite3`.

## Walkthrough

1. Open **Data import** and add an asset with a unique canonical ID, name, equipment type and location. For example: `PUMP-02`, `Chilled Water Pump 02`, type `pump`, location `Energy Centre / Pump Room`.
2. Select the new asset and upload [synthetic_vendor_pump.csv](../data/examples/synthetic_vendor_pump.csv). Map its equipment reference `VENDOR:CHWP-06` explicitly to your canonical asset.
3. Preview the import. Review accepted readings, duplicate counts and row errors. Nothing is saved until **Save import** is selected. Any validation error blocks the whole import.
4. Open the asset's existing overview. Its graphs and source records come from the imported snapshot. Source filename, file hash, CSV row and equipment reference are retained.
5. Restart the app and reopen the asset. Upload the same file again: the save should add zero observations and report the existing readings as skipped.

Imported assets have uncommissioned detector coverage. Registering another pump does not automatically deploy the Pump-01 demonstration rule to it. Imported snapshots remain distinct from the generated scenario replay.

## CSV contract

| Column | Requirement |
| --- | --- |
| `equipment_ref` | Exact vendor reference selected in the mapping; one equipment reference per file |
| `timestamp` | ISO 8601 with an explicit timezone, converted to UTC |
| `point` | A point ID from the selected equipment type's template |
| `value` | Finite numeric value within that point's ingestion bounds |
| `unit` | Exact expected unit, including case; no implicit conversion |
| `operating_mode` | Optional lowercase mode name; missing mode becomes `unknown` |

The pump template supports `motor_current_a` in A, `bearing_temp_c` in °C, `vibration_mm_s` in mm/s, and `differential_pressure_kpa` in kPa. The importer accepts UTF-8 CSV files up to 2,000,000 bytes and 10,000 data rows.

The same asset, point and normalized observation timestamp identifies one logical reading. An identical repeated reading is skipped, including overlap from another file. A changed value, unit or operating mode at that identity is a conflict; the importer rejects the transaction rather than overwriting the earlier record. Save revalidates the file inside the transaction, so an earlier preview cannot bypass those checks.

## Scope

This version supports five equipment-type templates and the fixed vendor columns above. Arbitrary column mapping, unit conversion, live connectors, imported CMMS records, asset editing/deletion and automatic detector commissioning are outside this first build. Keep the SQLite file to retain the registered data; it is excluded from Git.
