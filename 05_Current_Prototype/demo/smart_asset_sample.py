"""Visualise the explicitly synthetic smart-asset prototype bundled with the local IOC dataset."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from demo import brand

FILES = {
    "assets": "data/asset_master.csv",
    "readings": "data/sensor_readings.csv",
    "events": "data/faults_events.csv",
    "maintenance": "data/maintenance_logs.csv",
    "thresholds": "data/thresholds.csv",
}
REQUIRED = {
    "assets": {"asset_id", "asset_name", "equipment_type", "reference_speed_rpm", "rated_current_a", "sensors_installed"},
    "readings": {"asset_id", "timestamp", "sensor_type", "value", "unit"},
    "events": {"asset_id", "timestamp", "event_type", "event_status"},
    "maintenance": {"asset_id", "maintenance_date", "work_type", "work_status"},
    "thresholds": {"parameter", "unit", "warning", "alarm"},
}
SENSORS = (
    ("speed", "Speed", "rpm"),
    ("temperature", "Temperature", "degC"),
    ("vibration", "Vibration", "mm/s"),
    ("current", "Current", "A"),
)


def load_bundle(archive_path: str | Path) -> dict[str, pd.DataFrame]:
    """Read only the known CSV files from the sample archive and validate their minimum schemas."""
    bundle = {}
    with ZipFile(archive_path) as archive:
        for key, member in FILES.items():
            try:
                frame = pd.read_csv(BytesIO(archive.read(member)))
            except KeyError as exc:
                raise ValueError(f"Sample archive is missing {member}.") from exc
            missing = REQUIRED[key] - set(frame.columns)
            if missing:
                raise ValueError(f"{member} is missing required columns: {', '.join(sorted(missing))}.")
            bundle[key] = frame

    bundle["readings"]["timestamp"] = pd.to_datetime(bundle["readings"]["timestamp"], errors="coerce", utc=True).dt.tz_convert("Asia/Singapore")
    bundle["readings"]["value"] = pd.to_numeric(bundle["readings"]["value"], errors="coerce")
    bundle["events"]["timestamp"] = pd.to_datetime(bundle["events"]["timestamp"], errors="coerce", utc=True).dt.tz_convert("Asia/Singapore")
    bundle["maintenance"]["maintenance_date"] = pd.to_datetime(bundle["maintenance"]["maintenance_date"], errors="coerce")
    return bundle


@st.cache_data(ttl=600, show_spinner="Reading sample asset data...")
def _cached_bundle(archive_path: str, modified_ns: int) -> dict[str, pd.DataFrame]:
    return load_bundle(archive_path)


def _thresholds_for(sensor: str, asset: pd.Series, thresholds: pd.DataFrame) -> list[tuple[float, str]]:
    """Return sample reference lines converted to the measurement's plotted unit."""
    if sensor in {"temperature", "vibration"}:
        key = "temperature" if sensor == "temperature" else "vibration"
        row = thresholds.loc[thresholds["parameter"] == key]
        if row.empty:
            return []
        return [(float(row.iloc[0][level]), label) for level, label in (("warning", "Warning"), ("alarm", "Alarm"))
                if pd.notna(row.iloc[0][level])]
    if sensor == "speed":
        reference = pd.to_numeric(asset.get("reference_speed_rpm"), errors="coerce")
        row = thresholds.loc[thresholds["parameter"] == "speed_deviation"]
        if pd.isna(reference) or row.empty:
            return []
        warning, alarm = float(row.iloc[0]["warning"]), float(row.iloc[0]["alarm"])
        return [(reference * (1 - warning / 100), "Warning -"), (reference * (1 + warning / 100), "Warning +"),
                (reference * (1 - alarm / 100), "Alarm -"), (reference * (1 + alarm / 100), "Alarm +")]
    if sensor == "current":
        rated = pd.to_numeric(asset.get("rated_current_a"), errors="coerce")
        row = thresholds.loc[thresholds["parameter"] == "current_pct"]
        if pd.isna(rated) or row.empty:
            return []
        return [(rated * float(row.iloc[0][level]) / 100, f"{label} ({row.iloc[0][level]}% rated)")
                for level, label in (("warning", "Warning"), ("alarm", "Alarm")) if pd.notna(row.iloc[0][level])]
    return []


def render(archive_path: str | Path) -> None:
    """Render an isolated sample-data dashboard with separate, unit-labelled sensor plots."""
    try:
        path = Path(archive_path)
        bundle = _cached_bundle(str(path), path.stat().st_mtime_ns)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        st.error(f"Could not read the smart-asset sample: {exc}")
        return

    assets = bundle["assets"].dropna(subset=["asset_id"]).drop_duplicates("asset_id").sort_values("asset_id")
    if assets.empty:
        st.info("The sample archive contains no assets.")
        return
    asset_by_id = assets.set_index("asset_id")
    asset_ids = list(asset_by_id.index)
    preferred = "SAM-CHWP-002" if "SAM-CHWP-002" in asset_ids else asset_ids[0]
    asset_id = st.selectbox("Sample asset", asset_ids, index=asset_ids.index(preferred),
                            format_func=lambda key: f"{key} · {asset_by_id.loc[key, 'asset_name']}")
    asset = asset_by_id.loc[asset_id]
    period = st.segmented_control("Reading window", ("24 hours", "7 days", "30 days"), default="30 days") or "30 days"
    days = {"24 hours": 1, "7 days": 7, "30 days": 30}[period]
    readings = bundle["readings"]
    asset_readings = readings.loc[(readings["asset_id"] == asset_id) & readings["timestamp"].notna()]
    if not asset_readings.empty:
        end = asset_readings["timestamp"].max()
        visible = asset_readings.loc[asset_readings["timestamp"] >= end - pd.Timedelta(days=days)].sort_values("timestamp")
    else:
        end = None
        visible = asset_readings

    latest = visible.sort_values("timestamp").groupby("sensor_type", as_index=False).tail(1).set_index("sensor_type") if not visible.empty else pd.DataFrame()
    metric_cols = st.columns(4)
    for col, (sensor, label, unit) in zip(metric_cols, SENSORS):
        value = latest.loc[sensor, "value"] if sensor in latest.index else None
        col.metric(label, f"{value:,.2f} {unit}" if pd.notna(value) else "Not available")
    if end is not None:
        st.caption(f"Synthetic sample · latest selected-asset reading {end:%d %b %Y %H:%M} SGT · not live or connected to site equipment")
    st.caption("Thresholds are illustrative prototype values, not approved operating limits or alarm settings.")

    fig = make_subplots(rows=2, cols=2, subplot_titles=[label for _, label, _ in SENSORS], shared_xaxes=True,
                        vertical_spacing=0.14, horizontal_spacing=0.1)
    thresholds = bundle["thresholds"]
    for index, (sensor, label, unit) in enumerate(SENSORS):
        row, col = divmod(index, 2)
        row += 1
        col += 1
        series = visible.loc[visible["sensor_type"] == sensor]
        if series.empty:
            fig.add_annotation(text="No sample readings", x=0.5, y=0.5, xref=f"x{index + 1} domain" if index else "x domain",
                               yref=f"y{index + 1} domain" if index else "y domain", showarrow=False, font={"color": brand.INK_3})
        else:
            fig.add_trace(go.Scatter(x=series["timestamp"], y=series["value"], mode="lines", name=label,
                                     line={"color": brand.SERIES[index], "width": 1.6},
                                     hovertemplate=f"%{{x|%d %b %H:%M}}<br>%{{y:.2f}} {unit}<extra></extra>"), row=row, col=col)
        for value, threshold_label in _thresholds_for(sensor, asset, thresholds):
            fig.add_hline(y=value, row=row, col=col, line_dash="dot" if "Warning" in threshold_label else "dash",
                          line_color=brand.CHART["gap"], opacity=0.8,
                          annotation_text=threshold_label, annotation_position="top left", annotation_font_size=10)
        fig.update_yaxes(title_text=unit, row=row, col=col, rangemode="tozero" if sensor in {"temperature", "vibration", "current"} else None)
    fig.update_layout(**brand.plotly_layout(height=620, margin={"l": 45, "r": 25, "t": 55, "b": 35}, showlegend=False))
    fig.update_xaxes(matches="x")
    st.plotly_chart(fig, width="stretch", config={"displaylogo": False})

    events = bundle["events"].loc[bundle["events"]["asset_id"] == asset_id].sort_values("timestamp", ascending=False)
    maintenance = bundle["maintenance"].loc[bundle["maintenance"]["asset_id"] == asset_id].sort_values("maintenance_date", ascending=False)
    left, right = st.columns(2)
    with left:
        st.markdown('<div class="sd-section">Sample events</div>', unsafe_allow_html=True)
        columns = [name for name in ("timestamp", "event_type", "severity", "related_sensor", "event_status", "recommended_action") if name in events.columns]
        st.dataframe(events[columns].head(20), hide_index=True, width="stretch", height=300)
    with right:
        st.markdown('<div class="sd-section">Sample maintenance</div>', unsafe_allow_html=True)
        columns = [name for name in ("maintenance_date", "work_type", "description", "work_status", "next_maintenance_date") if name in maintenance.columns]
        st.dataframe(maintenance[columns].head(20), hide_index=True, width="stretch", height=300)