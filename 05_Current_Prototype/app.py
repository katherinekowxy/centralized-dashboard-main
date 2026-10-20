"""SignalDesk: a local, synthetic engineering evidence demo."""

from __future__ import annotations

import hashlib
import html
import json
import csv
import io
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from demo.engine import ASSETS, POINTS, SCENARIOS, DETECTOR_ASSET_IDS, analyze, evaluate, generate_dataset
from demo.asset_data import build_asset_bucket, filter_events
from demo.imports import MAX_FILE_BYTES, ImportValidationError, commit_import, create_asset, expected_points, list_assets, list_readings, preview_csv
from demo.feedback import load_feedback, save_feedback
from demo.history import generate_history, summarize_history
from demo.reporting import build_report, report_markdown, request_ai_report
from demo.chart_scale import calm_range
from demo.schematics import asset_schematic
from demo.signals import STATUS_ORDER, asset_status, point_name, point_signals
from demo import brand, exploratory_view, navigation
from demo.platform_references import load_platforms


INK, MUTED, TEAL, AMBER, CORAL, BLUE = (brand.INK, brand.INK_3, brand.DIAGNOSTIC["ok"][0], brand.CHART["gap"],
                                        brand.DIAGNOSTIC["alert"][0], brand.CHART["reading"])
GRID, PAPER, PLOT = brand.CHART["grid"], brand.CHART["paper"], brand.CHART["plot"]
IDLE = brand.DIAGNOSTIC["idle"][0]
STATUS_COLOR = {"alert": CORAL, "warn": AMBER, "ok": TEAL, "idle": IDLE}
STATUS_WORD = {key: word for key, (_, word, _) in brand.DIAGNOSTIC.items()}
st.set_page_config(page_title="Gardens by the Bay | Facilities IOC", page_icon="◆", layout="wide")
st.markdown(brand.style() + """
<style>
.block-container {max-width:1380px;padding-top:3.6rem;padding-bottom:2rem}
.sd-head {display:flex;align-items:baseline;gap:.85rem;flex-wrap:wrap;margin:.15rem 0}
.sd-title {font-size:2rem;font-weight:750;letter-spacing:-.03em;line-height:1.08;color:var(--gbb-ink)}
.sd-badge {color:var(--gbb-ink-2);border:1.5px dashed var(--gbb-ink-3);border-radius:.35rem;padding:.12rem .55rem;font-size:.7rem;font-weight:700;letter-spacing:.06em;text-transform:uppercase}
[data-testid="stBaseButton-primary"], [data-testid="stBaseButton-primary"] p {color:#fff !important}
.sd-sub {color:var(--gbb-ink-2);font-size:.82rem;margin:.2rem 0 1rem}
.sd-section {font-size:1.08rem;font-weight:700;margin:.8rem 0 .35rem;letter-spacing:-.01em;color:var(--gbb-ink)}
.sd-muted {color:var(--gbb-ink-3);font-size:.76rem}
.sd-card {background:var(--gbb-surface);border:1px solid var(--gbb-line);border-radius:var(--gbb-radius);padding:.8rem 1rem;min-height:6rem}
.sd-card-label {color:var(--gbb-ink-3);font-size:.72rem;letter-spacing:.08em;text-transform:uppercase}
.sd-card-value {font-size:1.7rem;font-weight:750;line-height:1.2;margin:.15rem 0}
.sd-card-foot {color:var(--gbb-ink-3);font-size:.74rem}
.sd-chip {display:inline-flex;align-items:center;gap:.35rem;border:1px solid var(--gbb-line-strong);border-radius:99px;padding:.12rem .55rem;margin:.2rem .3rem .2rem 0;color:var(--gbb-ink-2);font-size:.72rem}
.sd-dot {display:inline-block;width:.62rem;height:.62rem;border-radius:50%;flex:none;vertical-align:middle}
.sd-dot-lg {width:.85rem;height:.85rem}
.sd-dot-alert {background:#B91C1C;box-shadow:0 0 0 3px rgba(185,28,28,.18)}
.sd-dot-warn {background:#B45309}
.sd-dot-ok {background:#0F766E}
.sd-dot-idle {background:transparent;border:2px solid #8A8F93}
.sd-tally {display:flex;gap:.6rem;flex-wrap:wrap;margin:.2rem 0 1rem}
.sd-tally > span {display:inline-flex;align-items:center;gap:.5rem;background:var(--gbb-surface-2);border:1px solid var(--gbb-line);border-radius:var(--gbb-radius);padding:.45rem .8rem;font-size:.86rem;color:var(--gbb-ink-2)}
.sd-tally b {font-size:1.15rem;color:var(--gbb-ink)}
.sd-asset-id {display:flex;align-items:center;gap:.55rem;font-size:1.25rem;font-weight:750;letter-spacing:-.02em}
.sd-asset-name {color:var(--gbb-ink-3);font-size:.8rem;margin:.05rem 0 .6rem 1.4rem}
.sd-headline {font-size:.95rem;font-weight:650;margin:0 0 .55rem;color:var(--gbb-ink)}
.sd-pts {display:flex;flex-wrap:wrap;gap:.3rem .9rem;margin:0 0 .75rem}
.sd-pt {display:inline-flex;align-items:center;gap:.4rem;font-size:.8rem;color:var(--gbb-ink-2)}
.sd-pt-flag {color:var(--gbb-ink);font-weight:650}
.sd-foot {color:var(--gbb-ink-3);font-size:.72rem;line-height:1.55;border-top:1px solid var(--gbb-line);padding-top:.5rem;margin-bottom:.35rem}
[class*="st-key-fleet-alert"] {border-color:#B91C1C !important;box-shadow:inset 3px 0 0 #B91C1C}
[class*="st-key-fleet-warn"] {border-color:#B45309 !important;box-shadow:inset 3px 0 0 #B45309}
.sd-tiles {display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:.6rem;margin:.2rem 0 .4rem}
.sd-tile {background:var(--gbb-surface);border:1px solid var(--gbb-line);border-radius:var(--gbb-radius);padding:.65rem .8rem}
.sd-tile-alert {border-color:#B91C1C}
.sd-tile-warn {border-color:#B45309}
.sd-tile-name {display:flex;align-items:center;gap:.4rem;font-size:.76rem;color:var(--gbb-ink-2)}
.sd-tile-value {font-size:1.45rem;font-weight:750;letter-spacing:-.02em;margin:.2rem 0 .05rem;font-variant-numeric:tabular-nums}
.sd-tile-value small {font-size:.78rem;font-weight:500;color:var(--gbb-ink-3);margin-left:.2rem}
.sd-tile-note {font-size:.72rem;color:var(--gbb-ink-3)}
.sd-legend {display:flex;flex-wrap:wrap;gap:.3rem 1rem;color:var(--gbb-ink-3);font-size:.72rem;margin:.1rem 0 .5rem}
.sd-legend span {display:inline-flex;align-items:center;gap:.35rem}
.sd-swatch {display:inline-block;width:.9rem;height:.55rem;border-radius:2px}
.sd-point {display:flex;align-items:center;gap:.45rem;font-size:.92rem;font-weight:650}
.sd-point small {font-size:.75rem;font-weight:500;color:var(--gbb-ink-3);margin-left:.15rem}
.sd-point-meta {color:var(--gbb-ink-3);font-size:.76rem;margin:.1rem 0 .3rem}
div[data-testid="stPlotlyChart"] {border:1px solid var(--gbb-line);border-radius:var(--gbb-radius);overflow:hidden}
</style>""", unsafe_allow_html=True)


def esc(value: Any) -> str:
    return html.escape(str(value if value is not None else ""))


def label(value: Any) -> str:
    return str(value or "—").replace("_", " ").title()


def section(value: str) -> None:
    st.markdown(f'<div class="sd-section">{esc(value)}</div>', unsafe_allow_html=True)


def card(name: str, value: Any, foot: str) -> None:
    st.markdown(f'<div class="sd-card"><div class="sd-card-label">{esc(name)}</div><div class="sd-card-value">{esc(value)}</div><div class="sd-card-foot">{esc(foot)}</div></div>', unsafe_allow_html=True)


def frame(rows: list[dict], columns: list[str] | None = None) -> None:
    if not rows:
        st.caption("No records in this selection.")
        return
    table = pd.DataFrame(rows)
    if columns:
        table = table[[column for column in columns if column in table.columns]]
    st.dataframe(table, hide_index=True, width="stretch")


def chart_layout(fig: go.Figure, *, height: int = 270, x_title: str = "", y_title: str = "") -> None:
    fig.update_layout(height=height, margin={"l": 38, "r": 15, "t": 22, "b": 40}, paper_bgcolor=PAPER, plot_bgcolor=PLOT,
                      font={"color": INK, "size": 12}, legend={"orientation": "h", "y": 1.18, "x": 0, "font": {"size": 11}},
                      xaxis={"title": x_title, "gridcolor": GRID}, yaxis={"title": y_title, "gridcolor": GRID},
                      hoverlabel={"bgcolor": brand.CHART["hover"], "font_color": INK, "bordercolor": brand.LINE_STRONG})


def fingerprint(dataset: dict, scenario_id: str, seed: int) -> str:
    raw = json.dumps({"scenario": scenario_id, "seed": seed, "readings": dataset.get("readings", []), "events": dataset.get("events", [])}, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]


def held_row(row: dict) -> dict:
    raw = row.get("reading")
    return {**raw, **{key: value for key, value in row.items() if key != "reading"}} if isinstance(raw, dict) else row


def display_bucket(run: dict, asset_id: str) -> dict:
    return build_asset_bucket(run, asset_id, asset_catalog=asset_by_id, point_catalog=point_catalog)


def replay(scenario_id: str, seed: int) -> None:
    dataset = generate_dataset(scenario_id, seed)
    analysis = analyze(dataset["readings"], dataset["events"])
    as_of = analysis["metrics"]["as_of"]
    st.session_state["replay"] = {"scenario_id": scenario_id, "seed": seed, "dataset": dataset, "analysis": analysis,
                                  "checks": evaluate(dataset, analysis), "fingerprint": fingerprint(dataset, scenario_id, seed),
                                  "history": generate_history(as_of), "as_of": as_of}
    st.session_state["reports"] = {}


def evidence_rows(case: dict, dataset: dict, analysis: dict) -> tuple[list[dict], list[dict]]:
    ids = set(case.get("evidence_ids") or [])
    readings = {}
    for source in (dataset.get("readings", []), [held_row(row) for row in analysis.get("quarantine", [])], analysis.get("accepted", [])):
        for row in source:
            if row.get("reading_id") in ids:
                readings[row["reading_id"]] = row
    return list(readings.values()), [row for row in dataset.get("events", []) if row.get("event_id") in ids]


def report_panel(case: dict, run: dict) -> None:
    key = case["case_id"]
    reports = st.session_state.setdefault("reports", {})
    report = reports.get(key) or build_report(case)
    st.caption(f"Explanation: {label(report.get('mode', 'deterministic'))}" + (f" · {report['reason']}" if report.get("reason") else ""))
    with st.expander("Case note", expanded=False):
        for heading, field in (("Observations", "observations"), ("Hypotheses to check", "hypotheses"), ("Recommended checks", "recommended_checks"), ("Limits", "limitations")):
            if report.get(field):
                st.markdown(f"**{heading}**")
                for item in report[field]:
                    st.markdown(f"- {item}")
    a, b = st.columns([1, 2])
    with a:
        st.download_button("Download case note", report_markdown(case, report), file_name=f"signaldesk-{key}-{run['fingerprint']}.md", mime="text/markdown", key=f"download-{key}")
    with b:
        if case.get("ai_eligible"):
            if st.button("Request AI explanation", key=f"ai-{key}"):
                reports[key] = request_ai_report(case)
                st.rerun()
        else:
            st.caption("AI unavailable: " + str(case.get("ai_gate_reason") or "Evidence gate not met."))


def evidence_chart(case: dict, run: dict, readings: list[dict]) -> None:
    points = pd.Series([row.get("point_id") for row in readings]).dropna()
    asset_id = case.get("asset_id")
    if points.empty or asset_id not in asset_by_id:
        return
    point_id = points.mode().iloc[0]
    bucket = display_bucket(run, asset_id)
    if point_id not in bucket["points"]:
        return
    signal = next(row for row in point_signals(bucket).to_dict("records") if row["point_id"] == point_id)
    start, end = utc(run["dataset"]["metadata"]["start_at"]), utc(run["as_of"])
    case_event = [{"event_id": case["case_id"], "event_type": "detector_case", "start_at": case.get("start_at"),
                   "end_at": case.get("end_at") or case.get("start_at"), "source": "analysis"}]
    fig, count = trend_figure(bucket, point_id, start, end, case_event, signal=signal, height=230)
    if count:
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
        st.markdown(f'<div class="sd-legend"><span><span class="sd-swatch" style="background:{CORAL};opacity:.4"></span>Case window</span>'
                    f'<span><span class="sd-swatch" style="background:{MUTED};opacity:.35"></span>Typical range (first 24 h)</span>'
                    f'<span>{dot(signal["status"])}Latest {signal_value(signal)}</span></div>', unsafe_allow_html=True)


def case_panel(case: dict, run: dict) -> None:
    status = SEVERITY_STATUS.get(str(case.get("severity")), "idle")
    with st.container(border=True, key=f"fleet-{status}-case-{case['case_id']}"):
        st.markdown(f'<div class="sd-asset-id" style="font-size:1.1rem">{dot(status, True)}{esc(case.get("title", case["case_id"]))}</div>'
                    f'<div class="sd-asset-name">{esc(label(case.get("severity")))} · {esc(label(case.get("category")))} · '
                    f'{esc(case.get("asset_id", "Unlinked"))} · from {esc(fmt_time(case.get("start_at")))}</div>', unsafe_allow_html=True)
        st.write(case.get("summary", ""))
        readings, events = evidence_rows(case, run["dataset"], run["analysis"])
        evidence_chart(case, run, readings)
        report_panel(case, run)
        with st.expander("Source evidence", expanded=False):
            st.caption(f"{case['case_id']} · IDs: " + (", ".join(map(str, case.get("evidence_ids") or [])) or "No linked IDs"))
            if readings:
                frame(readings, ["reading_id", "asset_ref", "point_id", "observed_at", "value", "unit", "quality", "source"])
            if events:
                frame(events, ["event_id", "event_type", "status", "start_at", "end_at", "title"])
        with st.expander("Record a review", expanded=False):
            with st.form(f"feedback-{case['case_id']}"):
                disposition = st.selectbox("Disposition", ["needs_review", "confirmed", "false_alarm"], format_func=label, key=f"decision-{case['case_id']}")
                reviewer_note = st.text_input("Note (optional)", key=f"note-{case['case_id']}")
                submitted = st.form_submit_button("Save review")
            if submitted:
                save_feedback(case["case_id"], disposition, reviewer_note, context={"scenario_id": run["scenario_id"], "seed": run["seed"], "replay_fingerprint": run["fingerprint"]})
                st.success("Review saved with replay context.")


def telemetry_chart(asset_id: str, analysis: dict, events: list[dict], start_at: str, end_at: str) -> None:
    table = pd.DataFrame([row for row in analysis.get("accepted", []) if row.get("asset_id", row.get("asset_ref")) == asset_id])
    if table.empty or "point_id" not in table:
        st.info("No accepted readings for this asset.")
        return
    points = sorted(table["point_id"].dropna().astype(str).unique().tolist())
    if not points:
        st.info("No plottable point for this asset.")
        return
    default = "leakage_ma" if asset_id == "DB-01" and "leakage_ma" in points else points[0]
    point = st.selectbox("Telemetry point", points, index=points.index(default), key=f"point-{asset_id}", format_func=label)
    selected = table[table["point_id"].astype(str) == point].copy()
    selected["observed_at"] = pd.to_datetime(selected["observed_at"], utc=True, errors="coerce")
    selected["value"] = pd.to_numeric(selected["value"], errors="coerce")
    selected = selected.dropna(subset=["observed_at", "value"]).sort_values("observed_at")
    if selected.empty:
        st.info("No numeric accepted readings for this point.")
        return
    unit = str(selected["unit"].iloc[0]) if "unit" in selected else ""
    cadence = int(POINTS.get(asset_id, {}).get(point, {}).get("cadence_s", 600))
    selected["segment"] = selected["observed_at"].diff().dt.total_seconds().gt(cadence * 1.5).cumsum()
    fig = go.Figure()
    for index, (_, segment) in enumerate(selected.groupby("segment", sort=True)):
        fig.add_trace(go.Scatter(x=segment["observed_at"], y=segment["value"], mode="lines+markers",
                                 line={"color": TEAL, "width": 2}, marker={"size": 3}, customdata=segment["reading_id"],
                                 name="Accepted readings", showlegend=index == 0,
                                 hovertemplate="%{x|%d %b %H:%M} UTC<br>%{y:.3g} " + html.escape(unit) + "<br>%{customdata}<extra></extra>"))
    has_case = False
    for case in analysis.get("cases", []):
        if case.get("asset_id") == asset_id and case.get("category") in {"condition", "trip"}:
            at = pd.to_datetime(case.get("start_at"), utc=True, errors="coerce")
            if pd.notna(at):
                fig.add_vline(x=at, line_color=CORAL, line_dash="dash", line_width=1.5)
                has_case = True
    has_event = False
    for event in events:
        if event.get("asset_id") == asset_id:
            start = pd.to_datetime(event.get("start_at"), utc=True, errors="coerce")
            end = pd.to_datetime(event.get("end_at"), utc=True, errors="coerce")
            if pd.notna(start) and pd.notna(end):
                fig.add_vrect(x0=start, x1=end, fillcolor=BLUE, opacity=.12, line_width=0)
                has_event = True
    window_start = pd.to_datetime(start_at, utc=True)
    window_end = pd.to_datetime(end_at, utc=True)
    last_observed = selected["observed_at"].max()
    has_gap = False
    for index in selected.index[selected["segment"].diff().fillna(0).gt(0)]:
        position = selected.index.get_loc(index)
        previous = selected.iloc[position - 1]["observed_at"]
        current = selected.iloc[position]["observed_at"]
        fig.add_vrect(x0=previous + pd.Timedelta(seconds=cadence), x1=current,
                      fillcolor=AMBER, opacity=.12, line_width=0)
        has_gap = True
    if window_end - last_observed > pd.Timedelta(seconds=cadence * 1.5):
        fig.add_vrect(x0=last_observed + pd.Timedelta(seconds=cadence), x1=window_end,
                      fillcolor=AMBER, opacity=.12, line_width=0)
        has_gap = True
    if has_gap:
        fig.add_trace(go.Scatter(x=[], y=[], mode="markers", marker={"symbol": "square", "color": AMBER, "size": 9}, name="No data"))
    if has_event:
        fig.add_trace(go.Scatter(x=[], y=[], mode="markers", marker={"symbol": "square", "color": BLUE, "size": 9}, name="Replay event"))
    if has_case:
        fig.add_trace(go.Scatter(x=[], y=[], mode="lines", line={"color": CORAL, "dash": "dash"}, name="Detector case"))
    chart_layout(fig, height=310, x_title="Observed (UTC)", y_title=f"{label(point)} ({unit})" if unit else label(point))
    fig.update_xaxes(range=[window_start, window_end])
    st.plotly_chart(fig, width="stretch", config={"displaylogo": False})
    st.caption(f"48 h UTC · {len(selected)} accepted samples")


def weekly_chart(work_orders: list[dict], as_of: str, asset_id: str | None = None) -> None:
    weekly = pd.DataFrame(summarize_history(work_orders, as_of, asset_id=asset_id)["weekly"])
    if weekly.empty:
        st.caption("No historical work orders in this selection.")
        return
    weekly["week"] = pd.to_datetime(weekly["week"], utc=True)
    fig = go.Figure()
    for field, name, color in (("faults", "Reported", BLUE), ("closed", "Closed", TEAL)):
        fig.add_trace(go.Bar(x=weekly["week"], y=weekly[field], marker_color=color, name=name,
                             hovertemplate="Week of %{x|%d %b}<br>%{y} " + name.lower() + " work orders<extra></extra>"))
    chart_layout(fig, height=310, x_title="Week starting (UTC)", y_title="Work orders")
    fig.update_layout(barmode="group")
    fig.update_yaxes(rangemode="tozero", dtick=1)
    fig.update_xaxes(tickformat="%d %b", dtick="M1")
    st.plotly_chart(fig, width="stretch", config={"displaylogo": False})


def fault_chart(work_orders: list[dict], as_of: str, asset_id: str | None = None) -> None:
    ranked = pd.DataFrame(summarize_history(work_orders, as_of, asset_id=asset_id)["by_fault"])
    if ranked.empty:
        st.caption("No historical fault types in this selection.")
        return
    ranked = ranked.sort_values(["faults", "fault_type"], ascending=[True, False])
    fig = go.Figure(go.Bar(x=ranked["faults"], y=ranked["fault_type"].map(label), orientation="h",
                           marker_color=BLUE, customdata=ranked["downtime_hours"],
                           hovertemplate="%{y}<br>%{x} work orders · %{customdata:.1f} h recorded downtime (closed only)<extra></extra>"))
    chart_layout(fig, x_title="Work orders", height=max(245, 42 * len(ranked) + 90))
    fig.update_xaxes(rangemode="tozero", dtick=1)
    fig.update_yaxes(title="")
    st.plotly_chart(fig, width="stretch", config={"displaylogo": False})


def history_timeline(work_orders: list[dict], as_of: str, asset_id: str | None = None) -> None:
    table = pd.DataFrame(work_orders)
    table["reported_at"] = pd.to_datetime(table["reported_at"], utc=True)
    cutoff = pd.Timestamp(as_of)
    table = table[table["reported_at"].between(cutoff - pd.Timedelta(days=90), cutoff)].copy()
    if asset_id is not None:
        table = table[table["asset_id"].eq(asset_id)]
    if table.empty:
        st.caption("No work orders in this selection.")
        return
    table["closed_at"] = pd.to_datetime(table["closed_at"], utc=True)
    observed_closed = table["status"].eq("closed") & table["closed_at"].between(table["reported_at"], cutoff)
    table["status_at_cutoff"] = "open"
    table.loc[table["status"].eq("in_progress"), "status_at_cutoff"] = "in_progress"
    table.loc[observed_closed, "status_at_cutoff"] = "closed"
    table["closed_display"] = table["closed_at"].dt.strftime("Closed %d %b %Y %H:%M UTC").where(observed_closed, "Closure pending")
    table["resolution_display"] = table["resolution"].where(observed_closed, "Pending")
    fig = go.Figure()
    for status, color in (("open", INK), ("in_progress", BLUE), ("closed", IDLE)):
        rows = table[table["status_at_cutoff"].eq(status)]
        if rows.empty:
            continue
        details = rows[["work_order_id", "fault_type", "title", "closed_display", "resolution_display"]].to_numpy()
        fig.add_trace(go.Scatter(
            x=rows["reported_at"], y=rows["asset_id"], mode="markers", name=label(status),
            marker={"color": color, "size": 11, "line": {"color": PAPER, "width": 1}}, customdata=details,
            hovertemplate="<b>%{customdata[0]}</b> · %{customdata[1]}<br>%{customdata[2]}<br>Reported %{x|%d %b %Y %H:%M} UTC<br>%{customdata[3]}<br>%{customdata[4]}<extra></extra>",
        ))
    chart_layout(fig, height=320, x_title="Reported (UTC)", y_title="")
    fig.update_layout(showlegend=False, margin={"t": 12})  # the HTML legend above never covers a row of dots
    fig.update_xaxes(range=[pd.Timestamp(as_of) - pd.Timedelta(days=90), pd.Timestamp(as_of)], tickformat="%d %b")
    fig.update_yaxes(categoryorder="array", categoryarray=[asset["asset_id"] for asset in ASSETS][::-1])
    names = {"open": ("Open", INK), "in_progress": ("In progress", BLUE), "closed": ("Closed", IDLE)}
    st.markdown('<div class="sd-legend"><span>Status at cutoff:</span>' + "".join(
        f'<span><span class="sd-dot" style="background:{color}"></span>{name}</span>'
        for status, (name, color) in names.items() if table["status_at_cutoff"].eq(status).any()) + "</div>",
        unsafe_allow_html=True)
    st.plotly_chart(fig, width="stretch", config={"displaylogo": False})


def maintenance_page(run: dict) -> None:
    work_orders = run["history"]
    section("CMMS history · 90 days")
    history_asset = st.selectbox("History asset", ["All assets", *[item["asset_id"] for item in ASSETS]], key="history_asset")
    selected_asset = None if history_asset == "All assets" else history_asset
    summary = summarize_history(work_orders, run["as_of"], asset_id=selected_asset)
    st.markdown('<div class="sd-tally">'
                f'<span><b>{summary["open_faults"]}</b> open or in progress</span>'
                f'<span><b>{summary["total_faults"]}</b> work orders in 90 days</span>'
                f'<span><b>{summary["downtime_hours"]:.1f} h</b> recorded downtime</span></div>', unsafe_allow_html=True)
    table = pd.DataFrame(work_orders)
    table = table[pd.to_datetime(table["reported_at"], utc=True).le(pd.Timestamp(run["as_of"]))]
    tiles = []
    for asset in ASSETS:
        rows = table[table["asset_id"].eq(asset["asset_id"])]
        if selected_asset and asset["asset_id"] != selected_asset:
            continue
        open_rows = rows[rows["status"].isin(["open", "in_progress"])]
        top = rows["fault_type"].mode()
        tiles.append(f'<div class="sd-tile">'
                     f'<div class="sd-tile-name">{esc(asset["asset_id"])}</div>'
                     f'<div class="sd-tile-value">{len(open_rows)}<small>open</small></div>'
                     f'<div class="sd-tile-note">{len(rows)} in 90 d · most often {esc(label(top.iloc[0]) if not top.empty else "—")}</div></div>')
    st.markdown('<div class="sd-tiles">' + "".join(tiles) + "</div>", unsafe_allow_html=True)
    left, right = st.columns([1.65, 1])
    with left:
        section("Fault timeline")
        history_timeline(work_orders, run["as_of"], selected_asset)
    with right:
        section("Most frequent faults")
        fault_chart(work_orders, run["as_of"], selected_asset)
    st.markdown('<div class="sd-muted">Each dot is one reported work order, coloured by status at the replay cutoff. '
                'Synthetic CMMS history, separate from the telemetry replay and not detector evidence.</div>', unsafe_allow_html=True)
    with st.expander("Work orders", expanded=False):
        status = st.selectbox("Table status", ["All statuses", "open", "in_progress", "closed"], format_func=label, key="history_status")
        visible = [row for row in work_orders if (selected_asset is None or row["asset_id"] == selected_asset) and (status == "All statuses" or row["status"] == status)]
        st.download_button("Download CMMS history CSV", pd.DataFrame(work_orders).to_csv(index=False),
                           file_name=f"signaldesk-cmms-{run['fingerprint']}.csv", mime="text/csv")
        if not visible:
            st.info("No work orders match these filters.")
            return
        table = pd.DataFrame(visible).sort_values("reported_at", ascending=False)
        display = table[["work_order_id", "asset_id", "fault_type", "priority", "status", "reported_at", "downtime_hours"]].copy()
        display["reported_at"] = pd.to_datetime(display["reported_at"], utc=True).dt.strftime("%d %b %Y")
        display["downtime_hours"] = display["downtime_hours"].where(display["status"] == "closed", None)
        display = display.rename(columns={"work_order_id": "Order", "asset_id": "Asset", "fault_type": "Fault", "priority": "Priority", "status": "Status", "reported_at": "Reported UTC", "downtime_hours": "Downtime h"})
        st.dataframe(display, hide_index=True, width="stretch", height=280)
        order_id = st.selectbox("Work order detail", table["work_order_id"].tolist(), key="selected_order")
        order = next(row for row in visible if row["work_order_id"] == order_id)
        with st.expander(f"{order_id} · {order['title']}", expanded=False):
            st.caption(f"{order['asset_id']} · {label(order['status'])} · reported {order['reported_at']} UTC")
            st.write(order.get("resolution") or "Resolution pending.")
            if order.get("closed_at"):
                st.caption(f"Closed {order['closed_at']} UTC · recorded downtime {order['downtime_hours']:.1f} h")


def investigate_page(run: dict, asset_id: str) -> None:
    analysis, dataset = run["analysis"], run["dataset"]
    cases = [case for case in analysis.get("cases", []) if case.get("asset_id") == asset_id]
    section(f"Case queue · {len(cases)}")
    if cases:
        for case in sorted(cases, key=lambda case: STATUS_ORDER[SEVERITY_STATUS.get(str(case.get("severity")), "idle")]):
            case_panel(case, run)
    else:
        st.info("No detector cases for this asset in this replay.")
    with st.expander("Reviewer decisions", expanded=False):
        frame(load_feedback(), ["created_at", "case_id", "decision", "note", "context"])
    with st.expander("Data quality", expanded=False):
        st.caption(f"{len(analysis.get('accepted', []))} accepted · {len(analysis.get('quarantine', []))} held · all assets")
        frame(analysis.get("quality_issues", []))
        st.markdown("**Held source rows**")
        frame([held_row(row) for row in analysis.get("quarantine", [])], ["reading_id", "asset_ref", "point_id", "observed_at", "value", "unit", "quality", "reason", "issue_type"])
    with st.expander("Replay checks and exports", expanded=False):
        checks = run["checks"]
        st.caption(f"{sum(bool(check.get('passed')) for check in checks)} / {len(checks)} fixture checks passed · synthetic expectations only")
        frame(checks, ["check", "passed", "detail"])
        provenance = {"scenario_id": run["scenario_id"], "seed": run["seed"], "fingerprint": run["fingerprint"]}
        provenance.update({key: value for key, value in dataset.get("metadata", {}).items() if key != "point_catalog"})
        st.json(provenance)
        cols = st.columns(4)
        with cols[0]:
            st.download_button("Telemetry CSV", pd.DataFrame(dataset.get("readings", [])).to_csv(index=False), file_name=f"signaldesk-readings-{run['fingerprint']}.csv", mime="text/csv")
        with cols[1]:
            st.download_button("Replay events CSV", pd.DataFrame(dataset.get("events", [])).to_csv(index=False), file_name=f"signaldesk-events-{run['fingerprint']}.csv", mime="text/csv")
        with cols[2]:
            st.download_button("CMMS history CSV", pd.DataFrame(run["history"]).to_csv(index=False), file_name=f"signaldesk-cmms-{run['fingerprint']}.csv", mime="text/csv")
        with cols[3]:
            st.download_button("Evaluation JSON", json.dumps({"provenance": provenance, "checks": checks}, indent=2, default=str), file_name=f"signaldesk-evaluation-{run['fingerprint']}.json", mime="application/json")


FLEET_ORDER = ("PUMP-01", "AHU-01", "FAN-01", "CHILLER-01", "DB-01")
SCHEMATIC_LAYERS = ("Equipment", "Piping / air", "Electrical", "Sensors")
WINDOW_OPTIONS = ("Last 6 hours", "Last 24 hours", "Full replay (48 hours)", "90 days", "Focus selected event")


def navigate(page: str, asset_id: str | None = None) -> None:
    """Button callback: open a diagnostics workbench page (by its workbench name) before the sidebar is drawn."""
    st.session_state["nav"] = navigation.BY_REPLAY_PAGE[page]
    if asset_id is not None:
        st.session_state["selected_asset"] = asset_id
        st.session_state["asset_picker"] = asset_id


def change_asset() -> None:
    st.session_state["selected_asset"] = st.session_state["asset_picker"]


def focus_selected_event(asset_id: str) -> None:
    if st.session_state.get(f"asset-event-{asset_id}") != "No focus":
        st.session_state[f"asset-window-{asset_id}"] = "Focus selected event"
    elif st.session_state.get(f"asset-window-{asset_id}") == "Focus selected event":
        st.session_state[f"asset-window-{asset_id}"] = "Full replay (48 hours)"


def utc(value: Any) -> pd.Timestamp:
    return pd.to_datetime(value, utc=True)


def fmt_time(value: Any) -> str:
    at = pd.to_datetime(value, utc=True, errors="coerce")
    return at.strftime("%d %b %Y %H:%M UTC") if pd.notna(at) else "Unavailable"


def point_label(point_id: str) -> str:
    return point_name(point_id)


def dot(status: str, large: bool = False) -> str:
    return f'<span class="sd-dot {"sd-dot-lg " if large else ""}sd-dot-{status}" title="{STATUS_WORD.get(status, status)}"></span>'


def signal_value(signal: Any) -> str:
    get = signal.get if isinstance(signal, dict) else lambda key: getattr(signal, key)
    if get("unit") == "state" and get("status") == "alert":
        return "Tripped"
    return fmt_value(get("latest"), get("unit"))


def fmt_value(value: Any, unit: str = "") -> str:
    number = pd.to_numeric(value, errors="coerce")
    if pd.isna(number):
        return "—"
    if unit == "state":
        return "Tripped" if number >= 1 else "No trip"
    text = f"{number:,.0f}" if abs(number) >= 100 else f"{number:.3g}" if abs(number) >= 1 else f"{number:.2f}"
    return f"{text}<small>{esc(unit)}</small>" if unit else text


def detector_text(bucket: dict) -> str:
    if bucket["asset"]["asset_id"] not in DETECTOR_ASSET_IDS:
        return "Detector not assessed"
    condition = bucket["condition_label"]
    return condition if condition.startswith("Detector") else f"Detector: {condition.lower()}"


FEED_STATUS = {"fresh": "ok", "partial": "idle", "stale": "idle", "missing": "idle"}
SEVERITY_STATUS = {"critical": "alert", "high": "alert", "warning": "idle", "info": "idle"}


def point_rows(bucket: dict, point_id: str, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    rows = [row for row in bucket.get("readings", []) if row.get("point_id") == point_id]
    table = pd.DataFrame(rows)
    if table.empty:
        return table
    table["observed_at"] = pd.to_datetime(table["observed_at"], utc=True, errors="coerce")
    table["value"] = pd.to_numeric(table["value"], errors="coerce")
    return table[table["observed_at"].between(start, end) & table["value"].notna()].sort_values("observed_at")


def marker_items(bucket: dict) -> list[dict]:
    return list(bucket.get("events", []))


def shared_window(run: dict, choice: str, focus: dict | None) -> tuple[pd.Timestamp, pd.Timestamp]:
    end = utc(run["as_of"])
    replay_start = utc(run["dataset"]["metadata"]["start_at"])
    if choice == "Full imported range":
        return replay_start, end
    if choice == "90 days":
        return end - pd.Timedelta(days=90), end
    if choice == "Last 6 hours":
        return end - pd.Timedelta(hours=6), end
    if choice == "Last 24 hours":
        return end - pd.Timedelta(hours=24), end
    if choice == "Focus selected event" and focus:
        at = pd.to_datetime(focus.get("start_at"), utc=True, errors="coerce")
        until = pd.to_datetime(focus.get("end_at"), utc=True, errors="coerce")
        if pd.notna(at):
            if pd.isna(until) or until < at:
                until = at
            return at - pd.Timedelta(hours=3), until + pd.Timedelta(hours=3)
    return replay_start, end


def trend_figure(bucket: dict, point_id: str, start: pd.Timestamp, end: pd.Timestamp,
                 events: list[dict], *, signal: dict | None = None, height: int = 210) -> tuple[go.Figure, int]:
    """One point's accepted readings with its usual band and the latest reading coloured by status."""
    table = point_rows(bucket, point_id, start, end)
    unit = signal["unit"] if signal else str(bucket["points"][point_id].get("unit") or "")
    fig = go.Figure()
    band = (signal["low"], signal["high"]) if signal and pd.notna(signal.get("low")) and signal["high"] > signal["low"] else None
    if band:
        fig.add_hrect(y0=band[0], y1=band[1], fillcolor=MUTED, opacity=.14, line_width=0, layer="below")
    for event in filter_events(events, start.isoformat(), end.isoformat()):
        if event.get("source") == "accepted_telemetry":
            continue  # Mode changes are already visible in the reading itself.
        at = pd.to_datetime(event.get("start_at"), utc=True, errors="coerce")
        until = pd.to_datetime(event.get("end_at"), utc=True, errors="coerce")
        if pd.isna(at):
            continue
        color = CORAL if event.get("event_type") == "detector_case" else BLUE
        if event.get("event_type") == "work_order":
            if at >= start:
                fig.add_vline(x=at, line_color=BLUE, line_dash="dot", line_width=1)
        elif pd.notna(until) and until > at:
            fig.add_vrect(x0=max(at, start), x1=min(until, end), fillcolor=color, opacity=.24 if color == CORAL else .10, line_width=0, layer="below")
        else:
            fig.add_vline(x=max(at, start), line_color=color, line_dash="dot", line_width=1)
    if not table.empty:
        cadence = int(bucket.get("point_specs", {}).get(point_id, {}).get("cadence_s", 1800))
        table = table.copy()
        table["segment"] = table["observed_at"].diff().dt.total_seconds().gt(cadence * 1.5).cumsum()
        for _, segment in table.groupby("segment", sort=True):
            fig.add_trace(go.Scatter(
                x=segment["observed_at"], y=segment["value"], mode="lines", line={"color": BLUE, "width": 2},
                customdata=segment["reading_id"] if "reading_id" in segment else None, name=point_label(point_id),
                hovertemplate="%{x|%d %b %H:%M} UTC<br><b>%{y:.3g} " + html.escape(unit) + "</b><br>%{customdata}<extra></extra>"))
        last = table.iloc[-1]
        fig.add_trace(go.Scatter(
            x=[last["observed_at"]], y=[last["value"]], mode="markers", hoverinfo="skip", name="Latest",
            marker={"size": 10, "color": STATUS_COLOR.get(signal["status"] if signal else "ok", TEAL), "line": {"color": PAPER, "width": 2}}))
    chart_layout(fig, height=height, y_title=f"{point_label(point_id)} ({unit})" if unit else point_label(point_id))
    fig.update_layout(showlegend=False, margin={"l": 54, "r": 14, "t": 12, "b": 34}, font={"size": 11})
    fig.update_xaxes(range=[start, end], title=None, showgrid=False, linecolor=GRID, tickformat="%H:%M\n%d %b", nticks=7)
    fig.update_yaxes(nticks=5, zeroline=False, title_font={"size": 11, "color": MUTED})
    y_range = calm_range(table["value"] if not table.empty else [], unit, band)
    if y_range:
        fig.update_yaxes(range=y_range)
    if unit == "state":
        fig.update_yaxes(range=[-.15, 1.15], tickvals=[0, 1], ticktext=["No trip", "Trip"], title=None)
    return fig, len(table)


def fleet_page(run: dict) -> None:
    fleet = []
    fleet_order = [*FLEET_ORDER, *(aid for aid in asset_by_id if aid not in FLEET_ORDER)]
    for aid in fleet_order:
        bucket = display_bucket(run, aid)
        signals = point_signals(bucket)
        fleet.append((aid, bucket, signals, asset_status(bucket, signals)))
    fleet.sort(key=lambda item: (item[3]["rank"], fleet_order.index(item[0])))
    counts = {status: sum(item[3]["status"] == status for item in fleet) for status in ("alert", "ok", "idle")}
    st.markdown('<div class="sd-tally">'
                f'<span>{dot("alert", True)}<b>{counts["alert"]}</b> need attention</span>'
                f'<span>{dot("ok", True)}<b>{counts["ok"]}</b> checked, no finding</span>'
                f'<span>{dot("idle", True)}<b>{counts["idle"]}</b> not assessed or no data</span></div>', unsafe_allow_html=True)
    for start in range(0, len(fleet), 3):
        for col, (aid, bucket, signals, state) in zip(st.columns(3), fleet[start:start + 3]):
            asset = bucket["asset"]
            open_jobs = sum(row.get("status") in {"open", "in_progress"} for row in bucket.get("work_orders", []))
            points = "".join(
                f'<span class="sd-pt{" sd-pt-flag" if row.status == "alert" else ""}" title="{esc(row.note)}">{dot(row.status)}'
                f'{esc(row.name)}{" · " + esc(row.note[:1].lower() + row.note[1:]) if row.status == "alert" else ""}</span>'
                for row in sorted(signals.itertuples(), key=lambda row: STATUS_ORDER[row.status]))
            detector = detector_text(bucket)
            with col:
                with st.container(border=True, key=f"fleet-{state['status']}-{aid}"):
                    st.markdown(
                        f'<div class="sd-asset-id">{dot(state["status"], True)}{esc(aid)}</div>'
                        f'<div class="sd-asset-name">{esc(asset["name"])}</div>'
                        f'<div class="sd-headline">{esc(state["headline"])}</div>'
                        f'<div class="sd-pts">{points}</div>'
                        f'<div class="sd-foot">{dot(FEED_STATUS.get(bucket["freshness"], "idle"))} Feed {esc(bucket["freshness"])} · '
                        f'Open jobs {open_jobs} · {esc(detector)}<br>{esc(asset["location"])} · {esc(bucket["operating_state"])}</div>',
                        unsafe_allow_html=True)
                    st.button(f"Open {aid}", key=f"open-asset-{aid}", width="stretch", on_click=navigate, args=("Asset overview", aid))
    st.markdown(f'<div class="sd-legend" style="margin-top:.8rem">'
                f'<span>{dot("alert")} Detector finding or trip</span><span>{dot("ok")} Detector checked, no finding</span>'
                f'<span>{dot("idle")} Not assessed, or data incomplete</span></div>'
                '<div class="sd-muted">Dots are diagnostic: red means a detector finding or relay trip, never just an unusual reading, '
                'and the machine may still be safe to operate. Only assets with a detector can be green. Synthetic data.</div>', unsafe_allow_html=True)


def reading_tiles(signals: pd.DataFrame) -> str:
    tiles = []
    for row in sorted(signals.itertuples(), key=lambda row: STATUS_ORDER[row.status]):
        tiles.append(f'<div class="sd-tile sd-tile-{row.status}"><div class="sd-tile-name">{dot(row.status)}{esc(row.name)}</div>'
                     f'<div class="sd-tile-value">{signal_value(row)}</div>'
                     f'<div class="sd-tile-note">{esc(row.note)}</div></div>')
    return '<div class="sd-tiles">' + "".join(tiles) + "</div>"


def asset_page(run: dict, asset_id: str) -> None:
    bucket = display_bucket(run, asset_id)
    asset = bucket["asset"]
    items = marker_items(bucket)
    signals = point_signals(bucket)
    state = asset_status(bucket, signals)
    by_point = {row["point_id"]: row for row in signals.to_dict("records")}
    current_cases = [case for case in bucket["cases"] if case.get("category") in {"condition", "trip"}]
    open_jobs = [row for row in bucket["work_orders"] if row.get("status") in {"open", "in_progress"}]
    detector_status = "alert" if current_cases else "idle" if asset_id not in DETECTOR_ASSET_IDS else FEED_STATUS.get(bucket["freshness"], "idle")

    head, action = st.columns([3, 1], vertical_alignment="center")
    with head:
        st.markdown(f'<div class="sd-asset-id" style="font-size:1.45rem">{dot(state["status"], True)}{esc(asset_id)} '
                    f'<span style="color:{MUTED};font-size:.95rem;font-weight:500">{esc(asset["name"])}</span></div>'
                    f'<div class="sd-headline" style="margin:.35rem 0 .3rem 1.4rem">{esc(state["headline"])}</div>'
                    f'<div style="margin-left:1.4rem">'
                    f'<span class="sd-chip">{dot(FEED_STATUS.get(bucket["freshness"], "idle"))}Feed {esc(bucket["freshness"])}</span>'
                    f'<span class="sd-chip">{dot(detector_status)}{esc(detector_text(bucket))}</span>'
                    f'<span class="sd-chip">Open jobs {len(open_jobs)}</span>'
                    f'<span class="sd-chip">Operating: {esc(bucket["operating_state"])}</span></div>', unsafe_allow_html=True)
    with action:
        if bucket["cases"]:
            st.button("Investigate cases", key="asset-investigate", width="stretch", type="primary" if current_cases else "secondary",
                      on_click=navigate, args=("Investigate", asset_id))

    left, right = st.columns([1.5, 1], gap="medium")
    with left:
        section("Latest readings")
        st.markdown(reading_tiles(signals), unsafe_allow_html=True)
        if asset_id not in POINTS:
            if bucket["readings"]:
                st.caption(f"Imported snapshot · as of {fmt_time(bucket['as_of'])}. CSV observations are synthetic and have no commissioned detector.")
            else:
                st.caption("No imported readings yet. This asset has no commissioned detector.")
    with right:
        section("Equipment schematic")
        if asset_id not in POINTS:
            st.info("Schematic unavailable for this registered asset. Its CSV channels and source records appear below.")
        else:
            view = st.session_state.get("schematic_view", "Isometric")
            sensor = st.session_state.get(f"schematic_sensor_{asset_id}", "All sensors")
            layers = st.session_state.get("schematic_layers", list(SCHEMATIC_LAYERS))
            colors = {pid: STATUS_COLOR[row["status"]] for pid, row in by_point.items()}
            fig = asset_schematic(asset_id, layers=layers, view=view, selected_point=None if sensor == "All sensors" else sensor,
                                  point_colors=colors, height=330, show_labels=st.session_state.get("schematic_labels", False))
            fig.update_layout(title=None, margin={"l": 0, "r": 0, "t": 0, "b": 0})
            st.plotly_chart(fig, width="stretch", config={"displaylogo": False})
            st.caption("Illustrative 3D schematic: not to scale, and not a CAD, BIM or installation drawing.")
            with st.expander("Schematic controls", expanded=False):
                st.selectbox("Schematic view", ("Isometric", "Top", "Side"), key="schematic_view")
                st.selectbox("Highlight sensor", ["All sensors", *bucket["points"].keys()], key=f"schematic_sensor_{asset_id}",
                             format_func=lambda p: p if p == "All sensors" else point_label(p))
                st.multiselect("Schematic layers", SCHEMATIC_LAYERS, default=list(SCHEMATIC_LAYERS), key="schematic_layers")
                st.toggle("Show labels", key="schematic_labels")

    focus_options = {"No focus": None}
    for item in sorted(items, key=lambda row: str(row.get("start_at") or ""), reverse=True):
        key = f"{item.get('event_id')} · {item.get('title', '')}"
        if key and key not in focus_options:
            focus_options[key] = item
    section("Trends")
    custom_asset = asset_id not in POINTS
    view_run = run
    if custom_asset:
        imported_start = min((row["observed_at"] for row in bucket["readings"]), default=bucket["as_of"])
        view_run = {**run, "as_of": bucket["as_of"], "dataset": {"metadata": {"start_at": imported_start}}}
    control_a, control_b = st.columns([1, 1.2])
    with control_a:
        window_key = f"asset-window-{asset_id}"
        if window_key not in st.session_state:
            st.session_state[window_key] = "Full imported range" if custom_asset else "Full replay (48 hours)"
        choices = ("Full imported range", *WINDOW_OPTIONS) if custom_asset else WINDOW_OPTIONS
        choice = st.selectbox("Shared time range", choices, key=window_key)
    with control_b:
        selected_event = st.selectbox("Focus fault / event", list(focus_options), key=f"asset-event-{asset_id}", on_change=focus_selected_event, args=(asset_id,))
    start, end = shared_window(view_run, choice, focus_options.get(selected_event))
    visible_events = filter_events(items, start.isoformat(), end.isoformat())
    if not custom_asset and end < utc(run["dataset"]["metadata"]["start_at"]):
        st.info("This window predates the 48 h telemetry replay. Signal charts are intentionally empty; historical CMMS records remain visible.")
    st.markdown(f'<div class="sd-legend"><span><span class="sd-swatch" style="background:{BLUE};height:2px"></span>Reading</span>'
                f'<span><span class="sd-swatch" style="background:{MUTED};opacity:.35"></span>Typical range (first 24 h)</span>'
                f'<span><span class="sd-swatch" style="background:{BLUE};opacity:.3"></span>Work / permit</span>'
                f'<span><span class="sd-swatch" style="background:{CORAL};opacity:.4"></span>Detector case</span>'
                f'<span>{esc(fmt_time(start))} → {esc(fmt_time(end))}</span></div>', unsafe_allow_html=True)

    first_tab = {"DB-01": "Electrical", "AHU-01": "Process", "CHILLER-01": "Process",
                 "FAN-01": "Mechanical", "PUMP-01": "Mechanical"}.get(asset_id, next(iter((item["section"] for item in bucket["points"].values())), "Process"))
    tabs = st.tabs(["Mechanical", "Electrical", "Process", "Maintenance history", "Events"],
                   default=first_tab, key=f"asset-tabs-{asset_id}")
    for tab, section_name in zip(tabs[:3], ("Mechanical", "Electrical", "Process")):
        with tab:
            points = [pid for pid, data in bucket["points"].items() if data.get("section") == section_name]
            if not points:
                st.info("No registered channels in this section. Measurements are unavailable.")
            points.sort(key=lambda pid: STATUS_ORDER[by_point[pid]["status"]])
            for pair in range(0, len(points), 2):
                for col, point_id in zip(st.columns(2), points[pair:pair + 2]):
                    signal = by_point[point_id]
                    with col, st.container(border=True):
                        st.markdown(f'<div class="sd-point">{dot(signal["status"])}{esc(signal["name"])}'
                                    f'<span style="margin-left:auto;font-variant-numeric:tabular-nums">{signal_value(signal)}</span></div>'
                                    f'<div class="sd-point-meta">{esc(signal["note"])} · {esc(signal["freshness"])} · last {esc(fmt_time(signal["observed_at"]))}</div>',
                                    unsafe_allow_html=True)
                        detail, count = trend_figure(bucket, point_id, start, end, items, signal=signal)
                        st.plotly_chart(detail, width="stretch", config={"displayModeBar": False})
                        if not count:
                            st.caption("No accepted readings in this UTC window. No values have been filled in.")
                        with st.expander("Records and events", expanded=False):
                            st.caption("Events are asset context; they do not establish a cause for this channel.")
                            frame(visible_events, ["event_id", "source", "event_type", "start_at", "end_at", "status", "title"])
                            source = point_rows(bucket, point_id, start, end)
                            frame(source.to_dict("records") if not source.empty else [],
                                  ["reading_id", "observed_at", "value", "unit", "quality", "source", "source_file", "source_row", "source_equipment_ref"])

    imported_for_asset = [row for row in run.get("imported_readings", []) if row.get("asset_id") == asset_id]
    if imported_for_asset:
        section("Imported records")
        st.caption("Synthetic vendor CSV · stored separately from the generated replay. Source file, row and hash travel with each reading.")
        frame(imported_for_asset, ["reading_id", "point_id", "observed_at", "value", "unit", "source", "source_file", "source_row", "source_equipment_ref", "source_hash"])

    with tabs[3]:
        section("Maintenance history")
        st.caption("Synthetic corrective work orders that overlap the shared UTC window; historical CMMS is separate from detector evidence. An open order may have been reported before this window.")
        visible_order_ids = {item.get("source_id") for item in visible_events if item.get("event_type") == "work_order"}
        orders = [row for row in bucket["work_orders"] if row.get("work_order_id") in visible_order_ids]
        orders.sort(key=lambda row: row["reported_at"], reverse=True)
        frame(orders, ["work_order_id", "fault_type", "priority", "status", "reported_at", "closed_at", "downtime_hours", "title"])
        if orders:
            selected_order = st.selectbox("Work order source record", [row["work_order_id"] for row in orders], key=f"asset-order-{asset_id}")
            with st.expander("Selected work order detail", expanded=False):
                st.json(next(row for row in orders if row["work_order_id"] == selected_order))
        st.button("Open maintenance dashboard", key="asset-maintenance", on_click=navigate, args=("Maintenance",), width="stretch")
    with tabs[4]:
        section("Events and findings")
        st.caption("Replay events, detector cases, and CMMS history overlapping the shared UTC window.")
        frame(visible_events, ["event_id", "source", "event_type", "start_at", "end_at", "status", "title"])
        if visible_events:
            by_id = {item["event_id"]: item for item in visible_events}
            event_id = st.selectbox("Event source record", list(by_id), key=f"asset-event-record-{asset_id}")
            with st.expander("Selected event detail", expanded=False):
                st.caption(f"Source {by_id[event_id].get('source')} · ID {by_id[event_id].get('source_id')}")
                st.json(by_id[event_id].get("record", {}))
        if asset_id in DETECTOR_ASSET_IDS:
            st.button("Open evidence and reviews", key="asset-evidence", on_click=navigate, args=("Investigate", asset_id), width="stretch")

    with st.expander("About this data", expanded=False):
        st.caption("Feed status uses the observation snapshot cutoff; the chart window changes historical context, not current freshness. "
                   "The shaded band is the typical range: the 5th–95th percentile of the first 24 h of readings in the same operating mode. "
                   "It is context only and never changes a dot; dots change only when a detector rule fires.")
        if asset_id not in DETECTOR_ASSET_IDS:
            st.caption("Detector coverage is not assessed for this asset. Zero current cases is not a health verdict.")
        st.caption(f"{asset['location']} · {label(asset['criticality'])} criticality · {asset['coverage']}.")
        if asset_id in POINTS:
            st.caption("The schematic is synthetic and not to scale; it is not a site drawing.")


def data_import_page() -> None:
    section("Add asset")
    st.caption("Register a canonical asset before mapping a synthetic vendor CSV to it. Point channels follow the selected equipment type.")
    with st.form("add-asset"):
        asset_id = st.text_input("Canonical ID", placeholder="PUMP-03")
        name = st.text_input("Asset name")
        asset_type = st.selectbox("Asset type", sorted({asset["asset_type"] for asset in ASSETS}), format_func=lambda value: "AHU" if value == "ahu" else label(value))
        location = st.text_input("Location")
        add = st.form_submit_button("Add asset")
    if add:
        try:
            created = create_asset(asset_id.strip(), name, asset_type, location)
        except ValueError as exc:
            st.error(str(exc))
        else:
            st.session_state["import_asset_picker"] = created["asset_id"]
            st.success(f"Added {created['asset_id']} · {created['name']}.")
            st.rerun()

    section("Import vendor CSV")
    st.caption("CSV columns: equipment_ref, timestamp, point, value, unit; operating_mode is optional. Timestamps need a timezone offset. Preview every row before saving.")
    sample = Path(__file__).resolve().parent / "data" / "examples" / "synthetic_vendor_pump.csv"
    st.download_button("Download sample pump CSV", sample.read_bytes(), file_name=sample.name, mime="text/csv")
    target_id = st.selectbox("Map to asset", list(asset_by_id), key="import_asset_picker",
                             format_func=lambda aid: f"{aid} · {asset_by_id[aid]['name']}")
    specs = expected_points(asset_by_id[target_id]["asset_type"])
    st.caption("Accepted points and units: " + ", ".join(f"{point} ({spec['unit']})" for point, spec in specs.items()))
    upload = st.file_uploader("Synthetic vendor CSV", type="csv", key="vendor_csv")
    if upload is None:
        return
    if upload.size > MAX_FILE_BYTES:
        st.error(f"CSV exceeds the {MAX_FILE_BYTES:,} byte limit.")
        return
    content = upload.getvalue()
    try:
        reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig"), newline=""))
        references = sorted({str(row.get("equipment_ref") or "").strip() for row in reader if row.get("equipment_ref")})
    except (UnicodeDecodeError, csv.Error):
        references = []
    if len(references) == 1:
        st.caption(f"Vendor equipment reference: {references[0]}")
        equipment_ref = references[0]
    else:
        if len(references) > 1:
            st.warning("This file contains multiple equipment references. This first importer maps one reference per file; other rows will appear as errors.")
        equipment_ref = st.text_input("Vendor equipment reference", value=references[0] if references else "")
    try:
        preview = preview_csv(content, target_id, equipment_ref, filename=upload.name)
    except (ValueError, TypeError) as exc:
        st.error(str(exc))
        return
    st.markdown(f"**Preview:** {preview['total_rows']} rows · {len(preview['accepted'])} ready · {preview['duplicates']} already saved · {len(preview['errors'])} errors")
    if preview["errors"]:
        frame(preview["errors"], ["row", "message"])
    if preview["accepted"]:
        frame(preview["accepted"], ["source_row", "asset_id", "asset_ref", "point_id", "observed_at", "value", "unit", "source_file"])
    if st.button("Save import", type="primary", disabled=bool(preview["errors"] or preview["total_rows"] == 0), key="save-vendor-import"):
        try:
            result = commit_import(content, target_id, equipment_ref, filename=upload.name)
        except ImportValidationError as exc:
            st.error("The source changed before save. Review these errors and preview again.")
            frame(exc.preview["errors"], ["row", "message"])
        except ValueError as exc:
            st.error(str(exc))
        else:
            st.success(f"Saved {result['saved']} readings for {target_id}; skipped {result['skipped']} duplicates.")
            st.button("Open asset page", on_click=navigate, args=("Asset overview", target_id))


def fleet_dot_counts(run: dict) -> dict[str, int]:
    counts = {"alert": 0, "ok": 0, "idle": 0}
    for aid in asset_by_id:
        bucket = display_bucket(run, aid)
        counts[asset_status(bucket, point_signals(bucket))["status"]] += 1
    return counts


def incident_runs() -> list[dict]:
    root = Path(__file__).resolve().parent / "incidents"
    if not root.is_dir():
        return []
    return [{"id": folder.name, "reports": sorted(path.name for path in (folder / "investigations").glob("*.md"))}
            for folder in sorted(root.iterdir()) if (folder / "bucket").is_dir()]


def system_map_page(run: dict) -> None:
    import os
    from urllib.parse import urlparse
    from demo import map_view, system_map
    from demo.imports import list_imports

    st.markdown(f"<style>{map_view.CSS}</style>", unsafe_allow_html=True)
    section("System map")
    st.markdown('<div class="sd-muted" style="margin-bottom:.5rem">How information reaches SignalDesk and what runs on top. '
                'The end state is live monitoring; today the numbers come from a replayed scenario and local data files.</div>', unsafe_allow_html=True)
    ai_configured = all(os.getenv(name, "").strip() for name in ("DEMO_AI_BASE_URL", "DEMO_AI_MODEL", "DEMO_AI_API_KEY"))
    ai_host = urlparse(os.getenv("DEMO_AI_BASE_URL", "")).hostname or ""
    facts = {"assets": list(asset_by_id.values()), "imports": list_imports(), "imported_readings": run.get("imported_readings", []),
             "feedback_count": len(load_feedback()), "dot_counts": fleet_dot_counts(run), "incidents": incident_runs(),
             "ai_configured": ai_configured,
             "ai_location": (None if not ai_configured else "local" if ai_host in {"localhost", "127.0.0.1", "::1"} else "cloud")}
    st.markdown('<div class="sd-legend"><span><span class="sd-node-tag">Live</span> runs in this demo</span>'
                '<span><span class="sd-node-tag" style="border-style:dashed">Manual</span> done outside the app</span>'
                '<span><span class="sd-node-tag" style="border-style:dotted">Planned</span> specified, not built</span></div>',
                unsafe_allow_html=True)
    st.markdown(map_view.layers_html(system_map.build(run, facts), system_map.ARROWS, compact=True), unsafe_allow_html=True)
    section("Dot and escalation rules")
    authority = "".join(f'<li><b>{esc(item["who"])}</b> ({esc(item["status"])}): {esc(item["rule"])}</li>' for item in system_map.DOT_AUTHORITY)
    escalation = system_map.ESCALATION
    st.markdown('<div class="sd-policy">'
                f'<div><b>Who may turn a dot red</b><ul>{authority}</ul></div>'
                f'<div><b>Escalation to the cloud model (planned)</b><ul>'
                f'<li><b>When</b> any of these happens:<ul>{"".join(f"<li>{esc(item)}</li>" for item in escalation["triggers"])}</ul></li>'
                f'<li><b>What is sent:</b> {esc(escalation["sends"])}</li>'
                f'<li><b>Approval:</b> {esc(escalation["approval"])}</li>'
                f'<li><b>What comes back:</b> {esc(escalation["returns"])}</li></ul></div></div>'
                f'<div class="sd-muted">{esc(system_map.RUNTIME)}</div>', unsafe_allow_html=True)


def site_module(name: str):
    """A site module, or None until it lands, so the app stays runnable while Claude and Codex build in parallel."""
    import importlib
    try:
        return importlib.import_module(f"demo.{name}")
    except ModuleNotFoundError as exc:
        if exc.name == f"demo.{name}":
            return None
        raise


def site_db():
    """The site database (docs/site-data-contract.md), regenerated when stale so "today" always has work on it."""
    db = site_module("site_db")
    if db is not None and getattr(db, "__name__", "") == "demo.site_db":
        seed = site_module("site_seed")
        if seed is not None:
            seed.ensure_fresh(max_age_hours=6)
    return db


SITE_CSS = """
html {font-size:18px}  /* Site pages are read by older staff (Dan, 12 October 2026): every rem is 12.5 % bigger */
.block-container {max-width:none !important;padding:2.6rem 1.6rem 1rem !important}  /* the whole screen, little scrolling */
.sd-head {margin:0 0 .5rem}
.sd-page {font-size:1.35rem;font-weight:750;color:var(--gbb-ink);margin-left:.2rem}
"""

SHELL_CSS = """
.ioc-brand {display:flex;align-items:center;gap:.55rem;margin:0 0 .4rem;padding:0 0 .7rem;border-bottom:1px solid var(--gbb-line)}
.ioc-brand i {flex:none;width:.35rem;height:2.2rem;border-radius:2px;background:var(--gbb-pink)}
.ioc-brand b {display:block;font-size:16px;font-weight:750;color:var(--gbb-ink);line-height:1.15}
.ioc-brand small {display:block;font-size:12.5px;color:var(--gbb-ink-2)}
.ioc-area {font-size:11.5px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:var(--gbb-ink-3);margin:0;padding:18px 0 6px 10px}
.st-key-ioc-nav, .st-key-ioc-nav [data-testid="stVerticalBlock"] {gap:.05rem !important}
.st-key-ioc-nav [data-testid="stMarkdownContainer"] {margin-bottom:0 !important}
[class*="st-key-nav-"] button {width:100%;justify-content:flex-start !important;min-height:32px;padding:4px 10px !important;border-radius:6px}
[class*="st-key-nav-"] button > div {justify-content:flex-start;width:100%}
[class*="st-key-nav-"] [data-testid="stBaseButton-tertiary"]:hover {background:var(--gbb-surface-3)}
[class*="st-key-nav-"] button p {font-size:14.5px;text-align:left}
[class*="st-key-nav-"] [data-testid="stBaseButton-primary"] {background:var(--gbb-pink-tint) !important;border:none !important;
  box-shadow:inset 3px 0 0 var(--gbb-pink)}
[class*="st-key-nav-"] [data-testid="stBaseButton-primary"] p {color:var(--gbb-pink-dark) !important;font-weight:700}
.ioc-head {margin:0 0 .9rem;padding:0 0 .6rem;border-bottom:1px solid var(--gbb-line)}
.ioc-crumb {font-size:.74rem;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:var(--gbb-ink-3)}
.ioc-title {font-size:1.75rem;font-weight:750;letter-spacing:-.02em;line-height:1.15;color:var(--gbb-ink);margin:.1rem 0 .35rem}
.ioc-meta {display:flex;flex-wrap:wrap;align-items:center;gap:.35rem .8rem;font-size:.8rem;color:var(--gbb-ink-2)}
.ioc-meta em {font-style:normal;color:var(--gbb-ink-3)}
.ioc-dir {display:grid;grid-template-columns:repeat(auto-fill,minmax(21rem,1fr));gap:1rem 1.4rem;margin:.4rem 0 1rem}
.ioc-dir h3 {font-size:1rem !important;font-weight:750;margin:0 0 .35rem !important;padding:0 !important;color:var(--gbb-ink)}
.ioc-dir ul {list-style:none;margin:0;padding:0}
.ioc-dir li {margin:0 0 .45rem;font-size:.86rem;line-height:1.35;color:var(--gbb-ink-2)}
.ioc-dir li a {font-weight:650;text-decoration:none}
.ioc-dir li span {display:block;font-size:.76rem;color:var(--gbb-ink-3)}
"""


def source_badge(page: navigation.Page) -> str:
    if page.source == navigation.REFERENCE:
        return '<span class="gbb-source" style="--b:dotted">External reference · not integrated</span>'
    return brand.demo_badge(navigation.SOURCE_LABEL[page.source]) if page.source != navigation.NONE else ""


def page_header(page: navigation.Page, title: bool = True) -> None:
    """Where you are, where the numbers come from, and which status vocabulary this page uses."""
    st.markdown(f'<div class="ioc-head"><div class="ioc-crumb">{esc(page.area)}</div>'
                + (f'<div class="ioc-title">{esc(page.label)}</div>' if title else "")
                + f'<div class="ioc-meta">{source_badge(page)}<span><em>Shows:</em> {esc(page.status)}</span></div></div>',
                unsafe_allow_html=True)


def site_header(name: str) -> None:
    """Header of a detail page opened in its own tab (?ptw=, ?asset=, ?eo=, ?wo=)."""
    st.markdown(f"<style>{SITE_CSS}{SHELL_CSS}</style>", unsafe_allow_html=True)
    st.markdown(f'<div class="ioc-head"><div class="ioc-crumb">Gardens by the Bay · Facilities IOC</div>'
                f'<div class="ioc-title">{esc(name)}</div>'
                f'<div class="ioc-meta">{brand.demo_badge(navigation.SOURCE_LABEL[navigation.SITE])}</div></div>',
                unsafe_allow_html=True)


OWN_TITLE = {"asset_dashboard", "asset_schematic"}  # these draw their own TV-scale title and counts


def site_page(page: navigation.Page) -> None:
    st.markdown(f"<style>{SITE_CSS}</style>", unsafe_allow_html=True)
    page_header(page, title=page.module not in OWN_TITLE)
    db, module = site_db(), site_module(page.module)
    if db is None or module is None:
        st.info(f"{page.label} is unavailable: {'the site database' if db is None else 'its module'} could not be loaded.")
        return
    module.render(db)


def overview_page() -> None:
    """Landing page: what needs attention, then one panel per kind of fact, each linking to the page that owns it."""
    from demo import site_overview

    page_header(navigation.PAGE["overview"])
    db = site_db()
    if db is None:
        st.info("The site database could not be loaded.")
        return
    if "replay" not in st.session_state or not {"history", "as_of"}.issubset(st.session_state["replay"]):
        replay("leakage_ramp" if "leakage_ramp" in scenario_by_id else SCENARIOS[0]["scenario_id"], 42)
    st.markdown(site_overview.page_html(site_overview.summary(db, st.session_state["replay"])), unsafe_allow_html=True)
    with st.expander("Where to find what", expanded=False):
        areas = []
        for area in navigation.AREAS[1:]:
            items = "".join(f'<li><a href="?view={page.key}" target="_self">{esc(page.label)}</a> · {esc(page.summary)}'
                            f'<span>{esc(page.status)}</span></li>'
                            for page in [*navigation.area_pages(area), *navigation.area_pages(area, secondary=True)])
            areas.append(f'<div><h3>{esc(area)}</h3><ul>{items}</ul></div>')
        st.markdown(f'<div class="ioc-dir">{"".join(areas)}</div>', unsafe_allow_html=True)


SITE_DETAILS = {  # query parameter -> (header, module, page renderer); each opens in its own tab
    "ptw": ("Permit", "ptw_dashboard", "render_ptw_page"),
    "asset": ("Asset", "asset_dashboard", "render_asset_page"),
    "eo": ("Event order", "calendar_overview", "render_event_page"),
    "wo": ("Work order", "calendar_overview", "render_work_order_page"),
}


def site_detail(kind: str, record_id: str) -> None:
    """Opened in a new tab from a box or a calendar bar."""
    header, module_name, renderer = SITE_DETAILS[kind]
    site_header(f"{header} {record_id}")
    db, module = site_db(), site_module(module_name)
    if db is None or module is None:
        st.info("The site database is not ready yet.")
    else:
        getattr(module, renderer)(record_id, db)


def open_page(key: str) -> None:
    """Navigation button callback."""
    st.session_state["nav"] = key


def current_page() -> navigation.Page:
    """The page in session state, following ?view= on a fresh load or when the URL is changed by hand."""
    asked = st.query_params.get("view")
    if "nav" not in st.session_state:
        st.session_state["nav"] = navigation.resolve(asked)
    elif asked in navigation.PAGE and asked != st.session_state.get("nav_applied"):
        st.session_state["nav"] = asked
    key = navigation.resolve(st.session_state["nav"])
    st.session_state["nav"] = st.session_state["nav_applied"] = key
    if st.query_params.get("view") != key:
        st.query_params["view"] = key
    return navigation.PAGE[key]


def nav_button(page: navigation.Page, current: navigation.Page) -> None:
    st.button(page.label, key=f"nav-{page.key}", width="stretch", on_click=open_page, args=(page.key,),
              type="primary" if page.key == current.key else "tertiary")


def sidebar_nav(current: navigation.Page) -> None:
    st.markdown('<div class="ioc-brand"><i></i><div><b>Gardens by the Bay</b><small>Facilities IOC</small></div></div>',
                unsafe_allow_html=True)
    with st.container(key="ioc-nav"):
        for area in navigation.AREAS:
            st.markdown(f'<div class="ioc-area">{esc(area)}</div>', unsafe_allow_html=True)
            for page in navigation.area_pages(area):
                nav_button(page, current)
        st.markdown('<div class="ioc-area">Other tools</div>', unsafe_allow_html=True)
        for page in navigation.PAGES:
            if page.secondary:
                nav_button(page, current)


scenario_by_id = {item["scenario_id"]: item for item in SCENARIOS}
asset_by_id = {item["asset_id"]: item for item in list_assets()}
point_catalog = {aid: expected_points(asset["asset_type"]) for aid, asset in asset_by_id.items()}

detail = next((kind for kind in SITE_DETAILS if st.query_params.get(kind)), None)
if detail:
    site_detail(detail, st.query_params[detail])
    st.stop()

current = current_page()
st.markdown(f"<style>{SHELL_CSS}</style>", unsafe_allow_html=True)
with st.sidebar:
    sidebar_nav(current)
if current.module:
    site_page(current)
    st.stop()
if not current.replay_page:
    overview_page()
    st.stop()

# Diagnostics workbench: one replayed synthetic scenario shared by the replay-backed pages.
page = current.replay_page
if "replay" not in st.session_state or not {"history", "as_of"}.issubset(st.session_state["replay"]):
    replay("leakage_ramp" if "leakage_ramp" in scenario_by_id else SCENARIOS[0]["scenario_id"], 42)

with st.sidebar:
    selected_asset = st.session_state.get("selected_asset", "DB-01")
    scenario_id, seed = st.session_state["replay"]["scenario_id"], st.session_state["replay"]["seed"]
    if page != "Exploratory":
        st.markdown('<div class="ioc-area">Diagnostics replay</div>', unsafe_allow_html=True)
    if page in {"Asset overview", "Investigate"}:
        if st.session_state.get("asset_picker") != selected_asset:
            st.session_state["asset_picker"] = selected_asset
        selected_asset = st.selectbox("Asset", list(asset_by_id), key="asset_picker", on_change=change_asset)
    if page != "Exploratory":
        with st.expander("Demo controls", expanded=False):
            scenario_id = st.selectbox("Scenario", list(scenario_by_id), index=list(scenario_by_id).index(st.session_state["replay"]["scenario_id"]), format_func=lambda value: scenario_by_id[value]["name"])
            seed = st.number_input("Seed", min_value=0, max_value=2_147_483_647, value=int(st.session_state["replay"]["seed"]), step=1)
            if st.button("Run replay", type="primary", width="stretch"):
                replay(scenario_id, int(seed))

run = {**st.session_state["replay"], "imported_readings": [row for aid in asset_by_id for row in list_readings(aid)]}
dataset, analysis = run["dataset"], run["analysis"]
page_header(current)
replay_start = pd.Timestamp(dataset["metadata"]["start_at"])
replay_end = pd.Timestamp(dataset["metadata"]["end_at"])
if page == "Asset overview" and selected_asset not in POINTS:
    own_imports = [row for row in run["imported_readings"] if row["asset_id"] == selected_asset]
    snapshot = f"imported snapshot as of {fmt_time(max(row['observed_at'] for row in own_imports))}" if own_imports else "no imported records yet"
    subtitle = f"{asset_by_id[selected_asset]['name']} · {snapshot} · synthetic vendor CSV"
elif page == "Data import":
    subtitle = "Register an asset and preview a synthetic vendor CSV before saving"
elif page == "Exploratory":
    subtitle = "External platform research · reviewed 6 October 2026"
elif page == "System map":
    subtitle = "Current components and explicitly labelled plans"
else:
    subtitle = f'{scenario_by_id[run["scenario_id"]]["name"]} · replay {replay_start:%d %b}–{replay_end:%d %b %Y} UTC · CMMS through {pd.Timestamp(run["as_of"]).strftime("%d %b %Y")}'
st.markdown(f'<div class="sd-sub">{esc(subtitle)}</div>', unsafe_allow_html=True)
if scenario_id != run["scenario_id"] or int(seed) != run["seed"]:
    st.warning("Replay settings changed. Select Run replay to update the displayed results.")

if page == "Overview":
    fleet_page(run)
elif page == "Asset overview":
    asset_page(run, selected_asset)
elif page == "Maintenance":
    maintenance_page(run)
elif page == "Data import":
    data_import_page()
elif page == "System map":
    system_map_page(run)
elif page == "Exploratory":
    try:
        platforms = load_platforms()
    except (ValueError, OSError) as exc:
        st.error(f"External reference snapshot could not be loaded: {exc}")
    else:
        exploratory_view.render(platforms)
else:
    investigate_page(run, selected_asset)
