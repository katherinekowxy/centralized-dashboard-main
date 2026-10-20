from __future__ import annotations

from zipfile import ZipFile

import pandas as pd

from demo.smart_asset_sample import load_bundle


def test_load_bundle_reads_sensor_csvs_from_archive(tmp_path) -> None:
    path = tmp_path / "sample.zip"
    tables = {
        "data/asset_master.csv": pd.DataFrame([{
            "asset_id": "SAM-1", "asset_name": "Sample pump", "equipment_type": "Pump", "reference_speed_rpm": 3000,
            "rated_current_a": 10, "sensors_installed": "speed;current",
        }]),
        "data/sensor_readings.csv": pd.DataFrame([
            {"asset_id": "SAM-1", "timestamp": "2026-10-01T00:00:00+08:00", "sensor_type": "speed", "value": 2990, "unit": "rpm"},
            {"asset_id": "SAM-1", "timestamp": "2026-10-01T01:00:00+08:00", "sensor_type": "speed", "value": 2980, "unit": "rpm"},
        ]),
        "data/faults_events.csv": pd.DataFrame([{
            "asset_id": "SAM-1", "timestamp": "2026-10-01T01:00:00+08:00", "event_type": "Potential anomaly", "event_status": "Open",
        }]),
        "data/maintenance_logs.csv": pd.DataFrame([{
            "asset_id": "SAM-1", "maintenance_date": "2026-10-01", "work_type": "Inspection", "work_status": "Scheduled",
        }]),
        "data/thresholds.csv": pd.DataFrame([{"parameter": "speed_deviation", "unit": "%", "warning": 5, "alarm": 10}]),
    }
    with ZipFile(path, "w") as archive:
        for name, frame in tables.items():
            archive.writestr(name, frame.to_csv(index=False))

    bundle = load_bundle(path)

    assert bundle["assets"].loc[0, "asset_id"] == "SAM-1"
    assert len(bundle["readings"]) == 2
    assert str(bundle["readings"].loc[0, "timestamp"].tz) == "Asia/Singapore"
    assert bundle["events"].loc[0, "event_type"] == "Potential anomaly"
    assert bundle["maintenance"].loc[0, "work_status"] == "Scheduled"