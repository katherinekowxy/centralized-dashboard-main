"""Pages for the imported iSMM fault log and the event-order workbook (demo/sources/registers.py).

Both are file exports, so every figure is "as at the export", never "now", and every page says when the export ends.
The fault log's Impact field is shown exactly as recorded: it mixes urgency (Urgent, Critical) with extent
(Localised to room, Whole Building), so it is not turned into a severity or risk scale. Work-order states use the
work-order vocabulary (Open, In progress, Completed, Cancelled), never the asset-state colours.
"""

from __future__ import annotations

import html
from datetime import date, datetime, timedelta
from typing import Any

from demo import brand

FAULT_STATE = {"open": "Open", "in_progress": "In progress", "completed": "Completed", "cancelled": "Cancelled"}
ISSUE_WORD = {"blank_value": "Blank required value", "invalid_value": "Value could not be read", "duplicate_row": "Repeated row",
              "end_before_start": "Completed before reported", "missing_column": "Missing column", "missing_file": "Missing file",
              "tidied_value": "Value tidied", "check_value": "Please check", "coverage_gap": "Gap in the export"}
CSS = """
.rx-figs {display:flex;flex-wrap:wrap;gap:.4rem 2rem;margin:.2rem 0 1rem}
.rx-fig b {display:block;font-size:18px;font-weight:750;line-height:1.1;font-variant-numeric:tabular-nums}
.rx-fig span {font-size:13px;color:var(--gbb-ink-2)}
.rx-note {font-size:12px;color:var(--gbb-ink-2);margin:.2rem 0 .8rem;line-height:1.45}
.rx-day {font-size:13px;font-weight:700;color:var(--gbb-ink-2);margin:16px 0 6px}
.rx-ev {display:grid;grid-template-columns:7rem minmax(0,1fr) auto;gap:2px 14px;padding:10px 14px;background:var(--gbb-surface);
  border:1px solid var(--gbb-line);border-radius:var(--gbb-radius);margin:0 0 6px;font-size:14px}
.rx-ev b {font-weight:600}
.rx-ev small {display:block;color:var(--gbb-ink-3);font-size:12px}
.rx-tags {display:flex;gap:6px;flex-wrap:wrap;justify-content:flex-end;align-items:center}
.rx-tag {font-size:12px;font-weight:700;padding:2px 8px;border-radius:99px;background:var(--gbb-surface-3);color:var(--gbb-ink-2);white-space:nowrap}
"""


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def _issues(st, problems: list[dict], label: str) -> None:
    import pandas as pd

    if not problems:
        st.caption("No problems found.")
        return
    counts = pd.Series([ISSUE_WORD.get(item["issue"], item["issue"]) for item in problems]).value_counts()
    st.dataframe(counts.rename_axis("Issue").reset_index(name="Rows"), hide_index=True)
    report = pd.DataFrame(problems)[["issue", "detail", "ref", "field", "value", "file", "row"]]
    st.dataframe(report, hide_index=True, width="stretch", height=260)
    st.download_button("Download validation report (CSV)", report.to_csv(index=False), file_name=f"{label}-validation-report.csv",
                       mime="text/csv", key=f"dl-{label}")


def fault_log(data: dict) -> None:
    """Fault log page: what was open at the export, how reporting and completion moved, and where faults cluster."""
    import pandas as pd
    import plotly.graph_objects as go
    import streamlit as st

    st.markdown(f"<style>{CSS}</style>", unsafe_allow_html=True)
    faults = data["faults"]
    if not faults:
        st.info("The fault log could not be read. See the validation report below.")
        _issues(st, data["issues"], "faults")
        return
    from demo import ui

    end, start = data["exported_to"], data["exported_from"]
    frame = pd.DataFrame(faults)
    a, b, c, d = st.columns([1.2, 1.4, 1.4, 1.4])
    with a:
        sites = st.multiselect("Site", sorted(frame["site"].dropna().unique()), key="fl_sites", placeholder="All sites")
    with b:
        buildings = st.multiselect("Building", sorted(frame["building"].unique()), key="fl_buildings", placeholder="All buildings")
    with c:
        trades = st.multiselect("Trade", sorted(t for t in frame["trade"].unique() if t), key="fl_trades", placeholder="All trades")
    with d:
        impacts = st.multiselect("Impact (as recorded)", sorted(frame["impact"].unique()), key="fl_impacts", placeholder="Any impact")
    view = frame
    for column, chosen in (("site", sites), ("building", buildings), ("trade", trades), ("impact", impacts)):
        if chosen:
            view = view[view[column].isin(chosen)]
    last30 = view[view["reported"].notna() & (view["reported"] > end - timedelta(days=30))]
    st.markdown(ui.kpis([{"label": "Open", "value": f'{int((view["state"] == "open").sum()):,}', "caption": f"As at {end:%d %b %Y}"},
                         {"label": "In progress", "value": f'{int((view["state"] == "in_progress").sum()):,}', "caption": f"As at {end:%d %b %Y}"},
                         {"label": "Reported, last 30 days", "value": f"{len(last30):,}", "caption": "Of the export"},
                         {"label": "All faults", "value": f"{len(view):,}", "caption": f"{start:%b %Y} to {end:%b %Y}"}]), unsafe_allow_html=True)

    left, right = st.columns([1.6, 1], gap="medium")
    with left:
        st.markdown('<div class="u-sec">Reported and completed per week</div>', unsafe_allow_html=True)
        weeks = pd.period_range(start.replace(tzinfo=None), end.replace(tzinfo=None), freq="W").start_time
        weekly = pd.DataFrame({"reported": view["reported"].dropna().dt.tz_localize(None).dt.to_period("W").dt.start_time.value_counts(),
                               "completed": view["completed"].dropna().dt.tz_localize(None).dt.to_period("W").dt.start_time.value_counts()}
                              ).reindex(weeks).fillna(0)
        for a, b in data.get("gaps", []):  # weeks inside an export hole are unknown, not zero: the line breaks there
            weekly.loc[(weekly.index > a.replace(tzinfo=None)) & (weekly.index < b.replace(tzinfo=None) - pd.Timedelta(days=6))] = None
        fig = go.Figure()
        for column, name, colour in (("reported", "Reported", brand.SERIES[0]), ("completed", "Completed", brand.SERIES[1])):
            fig.add_trace(go.Scatter(x=weekly.index, y=weekly[column], mode="lines", name=name, line={"color": colour, "width": 1.6},
                                     connectgaps=False, hovertemplate="Week of %{x|%d %b %Y}<br>%{y:.0f} " + name.lower() + "<extra></extra>"))
        for a, b in data.get("gaps", []):
            fig.add_vrect(x0=a.replace(tzinfo=None), x1=b.replace(tzinfo=None), fillcolor=brand.SURFACE_3, opacity=.8, line_width=0, layer="below",
                          annotation_text="No records in the export", annotation_position="top left", annotation_font_color=brand.INK_3)
        fig.update_layout(**brand.plotly_layout(height=300, margin={"l": 40, "r": 10, "t": 30, "b": 30}))
        fig.update_yaxes(rangemode="tozero", title="Faults")
        st.plotly_chart(fig, width="stretch", config={"displaylogo": False})
        gap_text = "; ".join(f"{a:%d %b %Y} to {b:%d %b %Y}" for a, b in data.get("gaps", []))
        if gap_text:
            st.caption(f"Shaded: no records {gap_text} (missing from the export).")
    with right:
        st.markdown('<div class="u-sec">Open by building</div>', unsafe_allow_html=True)
        open_now = view[view["state"].isin(["open", "in_progress"])]
        ranked = open_now["building"].value_counts().head(10).sort_values()
        if ranked.empty:
            st.caption("Nothing open in this selection.")
        else:
            fig = go.Figure(go.Bar(x=ranked.values, y=ranked.index, orientation="h", marker_color=brand.SERIES[1],
                                   hovertemplate="%{y}: %{x} faults<extra></extra>"))
            fig.update_layout(**brand.plotly_layout(height=300, margin={"l": 10, "r": 10, "t": 10, "b": 30}))
            fig.update_xaxes(rangemode="tozero", dtick=max(1, int(ranked.max() // 5)))
            st.plotly_chart(fig, width="stretch", config={"displaylogo": False})

    tab_open, tab_impact, tab_report = st.tabs([f"Open at export ({len(open_now):,})", "Impact as recorded", "Validation report"])
    with tab_open:
        if open_now.empty:
            st.caption("None.")
        else:
            table = open_now.sort_values("reported", ascending=False).assign(
                Reported=lambda f: f["reported"].dt.strftime("%d %b %Y %H:%M"), State=lambda f: f["state"].map(FAULT_STATE),
                Age=lambda f: ((end - f["reported"]).dt.days).astype("Int64").astype(str) + " d at export")
            st.dataframe(table[["number", "Reported", "State", "Age", "building", "room", "trade", "type", "impact", "remarks"]].rename(columns={
                "number": "Fault", "building": "Building", "room": "Room", "trade": "Trade", "type": "Type of fault", "impact": "Impact (as recorded)",
                "remarks": "Remarks"}), hide_index=True, width="stretch", height=360)
    with tab_impact:
        st.caption("As recorded in iSMM. Mixes urgency and extent, so it is not a severity scale.")
        st.dataframe(view["impact"].value_counts().rename_axis("Impact (as recorded)").reset_index(name="Faults"), hide_index=True)
    with tab_report:
        _issues(st, data["issues"], "faults")


WINDOWS = ("This week", "Next week", "Next 4 weeks", "This month", "Whole workbook")


def _window(choice: str, today: date) -> tuple[date, date]:
    monday = today - timedelta(days=today.weekday())
    if choice == "This week":
        return monday, monday + timedelta(days=6)
    if choice == "Next week":
        return monday + timedelta(days=7), monday + timedelta(days=13)
    if choice == "Next 4 weeks":
        return today, today + timedelta(days=27)
    if choice == "This month":
        first = today.replace(day=1)
        return first, (first + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    return date(1900, 1, 1), date(2999, 12, 31)


def event_orders(data: dict, today: date) -> None:
    """Imported event orders for a chosen window, by day; events written as long ranges are listed separately."""
    import streamlit as st

    from demo.sources.registers import events_on

    st.markdown(f"<style>{CSS}</style>", unsafe_allow_html=True)
    from demo import ui

    events = data["events"]
    a, b = st.columns([2, 1])
    with a:
        choice = st.segmented_control("Period", WINDOWS, default="This week", key="ev_window") or "This week"
    with b:
        power_only = st.toggle("Needs power only", key="ev_power")
    first, last = _window(choice, today)
    shown = [e for e in events_on(events, first, last) if not power_only or e["power"] or e["power_on"]]
    long_running = [e for e in shown if e["days"] is None and (e["last_day"] - e["first_day"]).days > 13]
    dated = [e for e in shown if e not in long_running]
    st.markdown(ui.kpis([{"label": "Event orders", "value": len(shown), "caption": choice},
                         {"label": "Need power", "value": sum(e["power"] for e in shown), "caption": "Power requirement"},
                         {"label": "Power to turn on", "value": sum(e["power_on"] for e in shown), "caption": "Power turn on"},
                         {"label": "Kitchen handover", "value": sum(e["kitchen"] for e in shown), "caption": "Kitchen HOTO"}]), unsafe_allow_html=True)

    def line(event: dict) -> str:
        tags = [label for flag, label in ((event["power"], "Power"), (event["power_on"], "Power on"), (event["av"], "AV"),
                                          (event["kitchen"], "Kitchen HOTO")) if flag]
        when = event["time_text"] or "Time not given"
        return (f'<div class="rx-ev"><span>{esc(when)}<small>{esc(event["date_text"])}</small></span>'
                f'<span><b>{esc(event["title"])}</b><small>{esc(event["location"]) or "Location not given"}</small></span>'
                f'<span class="rx-tags">{"".join(f"<span class=rx-tag>{esc(t)}</span>" for t in tags)}</span></div>')

    if choice == "Whole workbook":
        days = sorted({e["first_day"] for e in dated})
    else:
        days = [first + timedelta(days=i) for i in range((last - first).days + 1)]
    body = []
    for day in days:
        todays = events_on(dated, day, day)
        if todays:
            body.append(f'<div class="rx-day">{day:%A %d %B %Y}{" · today" if day == today else ""}</div>' + "".join(line(e) for e in todays))
    if body:
        st.markdown("".join(body), unsafe_allow_html=True)
    else:
        st.caption("No dated event orders in this period.")
    if long_running:
        with st.expander(f"Running throughout this period ({len(long_running)})", expanded=False):
            st.markdown("".join(line(e) for e in long_running), unsafe_allow_html=True)
    with st.expander("Validation report", expanded=False):
        _issues(st, data["issues"], "events")
