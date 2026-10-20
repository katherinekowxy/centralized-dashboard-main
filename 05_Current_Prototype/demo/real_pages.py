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

FAULT_STATE = {"open": "Not started", "in_progress": "In progress", "completed": "Completed", "cancelled": "Cancelled"}
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
.ps-block + .ps-block {margin-top:.85rem;padding-top:.75rem;border-top:1px solid var(--gbb-line)}
.ps-block > b {display:block;margin:0 0 .35rem;font-size:13px;color:var(--gbb-ink)}
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
    for column in ("reported", "on_site", "completed"):
        frame[column] = pd.to_datetime(frame[column], errors="coerce", utc=True).dt.tz_convert("Asia/Singapore")
    if "kind" not in frame.columns:
        frame["kind"] = "fault"
    kinds = {"Faults": ["fault"], "Service requests": ["request"], "Event support": ["event"], "All records": ["fault", "request", "event"]}
    totals = {name: int(frame["kind"].isin(values).sum()) for name, values in kinds.items()}
    shown_kind = st.segmented_control("Show", list(kinds), default="Faults", key="fl_kind",
                                      format_func=lambda name: f"{name} ({totals[name]:,})") or "Faults"
    frame = frame[frame["kind"].isin(kinds[shown_kind])]
    noun = {"Faults": "faults", "Service requests": "requests", "Event support": "jobs", "All records": "records"}[shown_kind]
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
    responded = last30[last30["on_site"].notna() & ~last30["cancelled"]]
    minutes = ((responded["on_site"] - responded["reported"]).dt.total_seconds() / 60).clip(lower=0)
    median = f"{minutes.median():.0f} min" if len(minutes) else "—"
    last_day = view[view["reported"].notna() & (view["reported"].dt.date == end.date())]
    not_started, working = int((view["state"] == "open").sum()), int((view["state"] == "in_progress").sum())
    open_mask = view["state"].isin(["open", "in_progress"])
    over_30 = int((open_mask & (view["reported"] < end - timedelta(days=30))).sum())
    st.markdown(ui.kpis([
        {"label": f"Open {noun}", "value": f"{not_started + working:,}", "caption": f"{not_started} not started · {working} in progress",
         "dot": "#B42D2D" if not_started else None},
        {"label": "Open over 30 days", "value": f"{over_30:,}", "caption": f"Reported before {end - timedelta(days=30):%d %b}"},
        {"label": f"Reported {end:%d %b}", "value": f"{len(last_day):,}", "caption": f"{len(last30):,} in the last 30 days"},
        {"label": "Median time to site", "value": median, "caption": "Report to on-site, last 30 days"},
    ]), unsafe_allow_html=True)

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
        fig.update_yaxes(rangemode="tozero", title=noun.capitalize())
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

    tab_open, tab_impact, tab_report = st.tabs([f"Open {noun} ({len(open_now):,})", "Impact as recorded", "Validation report"])
    with tab_open:
        if open_now.empty:
            st.caption("None.")
        else:
            table = open_now.sort_values("reported").assign(
                Reported=lambda f: f["reported"].dt.strftime("%d %b %Y %H:%M"), State=lambda f: f["state"].map(FAULT_STATE))
            what = "what" if "what" in table.columns else "type"
            st.dataframe(table[["number", "Reported", "State", what, "building", "room", "trade", "impact", "remarks"]].rename(columns={
                "number": "Reference", what: "What", "building": "Building", "room": "Room", "trade": "Trade", "impact": "Impact (as recorded)",
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
                         {"label": "Kitchen handover", "value": sum(e["kitchen"] for e in shown), "caption": "Handover or takeover"}]), unsafe_allow_html=True)

    def line(event: dict) -> str:
        tags = [label for flag, label in ((event["power"], "Power"), (event["power_on"], "Power on"), (event["av"], "AV"),
                                          (event["kitchen"], "Kitchen")) if flag]
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


def safety_meetings(toolbox: dict, today: date) -> None:
    """Tool-box meetings only; permit records are shown on the separate Permit Map page."""
    import pandas as pd
    import plotly.graph_objects as go
    import streamlit as st

    from demo import ui

    meetings = toolbox["meetings"]
    if not meetings:
        st.info("No tool-box meeting records were found in the configured exports.")
        return

    controls = st.columns([1, 1.4, 1.4, 1.4])
    sites = sorted({meeting["site"] or "Site not recorded" for meeting in meetings})
    companies = sorted({meeting["company"] or "Company not recorded" for meeting in meetings})
    activities = sorted({meeting["activity"] for meeting in meetings if meeting["activity"]})
    chosen_sites = controls[0].multiselect("Site", sites, key="tb_sites", placeholder="All sites")
    chosen_companies = controls[1].multiselect("Company", companies, key="tb_companies", placeholder="All companies")
    chosen_activities = controls[2].multiselect("Activity", activities, key="tb_activities", placeholder="All activities")
    selected_dates = controls[3].date_input("Meeting date range", value=(today - timedelta(days=6), today), key="tb_dates")
    if isinstance(selected_dates, (tuple, list)):
        date_start = selected_dates[0] if selected_dates else today
        date_end = selected_dates[-1] if len(selected_dates) > 1 else date_start
    else:
        date_start = date_end = selected_dates

    shown = [meeting for meeting in meetings if date_start <= meeting["at"].date() <= date_end
             and (not chosen_sites or (meeting["site"] or "Site not recorded") in chosen_sites)
             and (not chosen_companies or (meeting["company"] or "Company not recorded") in chosen_companies)
             and (not chosen_activities or meeting["activity"] in chosen_activities)]
    attendee_values = [meeting["attendees"] for meeting in shown if meeting["attendees"] and meeting["attendees"] > 0]
    stats = [
        {"label": "Meetings", "value": f"{len(shown):,}", "caption": f"{date_start:%d %b %Y} – {date_end:%d %b %Y}"},
        {"label": "Companies", "value": len({meeting["company"] for meeting in shown if meeting["company"]}),
         "caption": "In the selected period"},
        {"label": "Sites", "value": len({meeting["site"] for meeting in shown if meeting["site"]}),
         "caption": "In the selected period"},
    ]
    if attendee_values:
        stats.append({"label": "Attendees recorded", "value": f"{sum(attendee_values):,.0f}", "caption": "Positive counts only"})
    st.markdown(ui.kpis(stats), unsafe_allow_html=True)

    left, right = st.columns([1.6, 1])
    with left:
        st.markdown('<div class="u-sec">Meeting records</div>', unsafe_allow_html=True)
        table = pd.DataFrame([{"Date": meeting["at"].strftime("%d %b %Y %H:%M"),
                               "Site": meeting["site"] or "Site not recorded",
                               "Company": meeting["company"] or "Company not recorded",
                               "Activity": meeting["activity"] or "Not recorded",
                               "Attendees": f"{meeting['attendees']:.0f}" if meeting["attendees"] and meeting["attendees"] > 0 else "—"}
                              for meeting in sorted(shown, key=lambda item: item["at"], reverse=True)])
        st.dataframe(table, hide_index=True, width="stretch", height=420)
    with right:
        st.markdown('<div class="u-sec">Meetings by company</div>', unsafe_allow_html=True)
        counts = pd.Series([meeting["company"] or "Company not recorded" for meeting in shown]).value_counts().sort_values()
        if counts.empty:
            st.caption("No meetings match these filters.")
        else:
            figure = go.Figure(go.Bar(x=counts.values, y=counts.index, orientation="h", marker_color=brand.SERIES[0],
                                      hovertemplate="%{y}: %{x} meetings<extra></extra>"))
            figure.update_layout(**brand.plotly_layout(height=max(240, 100 + 34 * len(counts)),
                                                       margin={"l": 10, "r": 15, "t": 10, "b": 30}, showlegend=False))
            figure.update_xaxes(title="Meetings", rangemode="tozero")
            st.plotly_chart(figure, width="stretch", config={"displaylogo": False})
    with st.expander("Validation report", expanded=False):
        _issues(st, toolbox["issues"], "toolbox-meetings")


def permit_site_map(permits: dict, today: date) -> None:
    """Show iSMM permits on a site-level map without inventing building locations."""
    import pandas as pd
    import streamlit as st
    import streamlit.components.v1 as components

    from demo import ptw_real, ui
    from demo.sources.ismm import permits_on

    records = permits["permits"]
    if not records:
        st.info("No iSMM permit records were found in the PTW folder.")
        return
    periods = ("Active today", "Next 7 days", "Next 30 days", "All permits")
    controls = st.columns([1, 1.5])
    period = controls[0].segmented_control("Window", periods, default="Active today", key="ptw_register_period") or periods[0]
    sites = sorted({record["site"] or "Site not recorded" for record in records})
    chosen_sites = controls[1].multiselect("Site", sites, key="ptw_register_sites", placeholder="All sites")
    horizon = {"Active today": 0, "Next 7 days": 7, "Next 30 days": 30}.get(period)
    shown = records if horizon is None else permits_on(records, today, today + timedelta(days=horizon))
    if chosen_sites:
        shown = [record for record in shown if (record["site"] or "Site not recorded") in chosen_sites]

    points, unplaced = ptw_real.site_map_points(shown)
    site_counts = pd.Series([record["site"] or "Site not recorded" for record in shown]).value_counts().sort_values()
    st.markdown(ui.kpis([
        {"label": "Permits", "value": f"{len(shown):,}", "caption": period},
        {"label": "Sites shown", "value": len(points), "caption": "Site-area markers"},
        {"label": "Permits without a map location", "value": len(unplaced), "caption": "Site not shown on map"},
        {"label": "Companies", "value": len({record["company"] for record in shown if record["company"]}),
         "caption": "In the selected window"},
    ]), unsafe_allow_html=True)
    st.info("Permits are shown by site: the iSMM permit export does not record the exact work location.")
    left, right = st.columns([2.2, 1])
    with left:
        if points:
            components.html(ptw_real.map_page(points), height=560)
            st.caption("Marker numbers show permits for each site area. © OpenStreetMap contributors.")
        else:
            st.info("No selected permits have a public site coordinate to map.")
    with right:
        site_rows = [{"main": site, "sub": "Site area" if any(p["names"] == [site] for p in points) else "Not shown on map",
                      "right": ui.pill("neutral", str(int(count)))} for site, count in site_counts.items()]
        st.markdown(ui.panel("Permit counts by site", ui.rows(site_rows, "No permits match this selection.")), unsafe_allow_html=True)
        if unplaced:
            st.markdown(ui.panel("Sites not shown on map", ui.rows([{"main": record["site"] or "Site not recorded",
                                                         "sub": f"{record['ref']} · {record['company'] or 'Company not recorded'}",
                                                         "right": ui.pill("neutral", record["type"])} for record in unplaced[:8]],
                                                        f"{len(unplaced)} permits have no map location.")), unsafe_allow_html=True)

    table = pd.DataFrame([{"Permit": record["ref"], "Site": record["site"] or "Site not recorded",
                           "Company": record["company"], "Type": record["type"], "Trade": record["trades"],
                           "Start": record["start"].strftime("%d %b %Y") if record["start"] else "",
                           "End": record["end"].strftime("%d %b %Y") if record["end"] else ""} for record in shown])
    st.dataframe(table, hide_index=True, width="stretch", height=360)
    with st.expander("Validation report", expanded=False):
        _issues(st, permits["issues"], "ptw-site-register")


def spares(inventory: dict) -> None:
    """Store inventories: what is out of stock or below its minimum, by store and category."""
    import pandas as pd
    import streamlit as st

    from demo import ui

    items = inventory["items"]
    if not items:
        st.info("No inventory exports found.")
        return
    sites = sorted({i["store"] for i in items})
    c1, c2, c3 = st.columns([1.2, 1.2, 1.6])
    chosen = c1.multiselect("Site", sites, key="sp_stores", placeholder="All sites")
    cats = c2.multiselect("Category", sorted({i["category"] for i in items}), key="sp_cats", placeholder="All categories")
    text = c3.text_input("Search", key="sp_text", placeholder="Item or reference")
    view = [i for i in items if (not chosen or i["store"] in chosen) and (not cats or i["category"] in cats)
            and (not text or text.casefold() in f"{i['item']} {i['ref']}".casefold())]
    out = [i for i in view if i["state"] == "out"]
    low = [i for i in view if i["state"] == "low"]
    st.markdown(ui.kpis([
        {"label": "Items tracked", "value": f"{len(view):,}", "caption": f"Across {len(chosen) or len(sites)} sites"},
        {"label": "Out of stock", "value": len(out), "caption": "Quantity 0", "dot": "#B42D2D" if out else None},
        {"label": "Below minimum", "value": len(low), "caption": "Under the set threshold", "dot": "#E3A21A" if low else None},
        {"label": "Healthy", "value": sum(i["state"] == "ok" for i in view), "caption": "At or above minimum"},
    ]), unsafe_allow_html=True)
    attention = sorted(out + low, key=lambda i: (i["state"] != "out", -((i["threshold"] or 0) - (i["quantity"] or 0)), i["item"]))
    rows = ui.rows([{"main": i["item"], "sub": f"{i['store']} · {i['category']}{' · ' + i['subcategory'] if i['subcategory'] else ''}",
                     "right": ui.pill("fault" if i["state"] == "out" else "warn",
                                      f"{i['quantity']:.0f} of min {i['threshold']:.0f}" if i["threshold"] is not None else f"{i['quantity']:.0f} left")}
                    for i in attention[:12]], "Nothing out of stock or below minimum.")
    frame = pd.DataFrame(view)
    summary = (frame.assign(flag=frame["state"].isin(["out", "low"])).groupby("store")
               .agg(lines=("item", "size"), short=("flag", "sum")).sort_values("short", ascending=False))
    site_rows = ui.rows([{"main": site, "sub": f"{int(r.lines)} items tracked",
                           "right": ui.pill("warn" if r.short else "ok", f"{int(r.short)} to reorder" if r.short else "All stocked")}
                          for site, r in summary.iterrows()])
    st.markdown(ui.grid([ui.panel("To reorder", rows, note=f"{len(attention)} items"), ui.panel("By site", site_rows)], "1.6fr 1fr"),
                unsafe_allow_html=True)
    with st.expander("All items and validation report", expanded=False):
        state = {"out": "Out of stock", "low": "Below minimum", "ok": "OK", "unknown": "Quantity unknown"}
        st.dataframe(pd.DataFrame([{"Site": i["store"], "Item": i["item"], "Ref.": i["ref"], "Category": i["category"],
                                    "Subcategory": i["subcategory"], "Quantity": i["quantity"], "Minimum": i["threshold"],
                                    "Status": state[i["state"]], "Remarks": i["remarks"]} for i in view]),
                     hide_index=True, width="stretch", height=360)
        _issues(st, inventory["issues"], "inventory")


def event_support(faults: dict) -> None:
    """Event support jobs from iSMM (space, AV, kitchen and power handovers), by day: the real record of event activity
    when no event booking workbook is available. Past and today only; iSMM records jobs when they happen."""
    import streamlit as st

    from demo import ui
    from demo.sources.registers import is_power_job

    st.markdown(f"<style>{CSS}</style>", unsafe_allow_html=True)
    as_at = faults.get("exported_to")
    jobs = sorted([x for x in faults["faults"] if x.get("kind") == "event" and x["reported"]], key=lambda x: x["reported"], reverse=True)
    if not jobs or as_at is None:
        st.info("No event support jobs in the iSMM export.")
        return
    days = st.segmented_control("Period", (7, 14, 30), default=7, key="es_days", format_func=lambda d: f"Last {d} days") or 7
    shown = [x for x in jobs if x["reported"] > as_at - timedelta(days=days)]
    venues = {x["building"] for x in shown if x["building"] and x["building"] != "Not recorded"}
    st.markdown(ui.kpis([
        {"label": "Event support jobs", "value": len(shown), "caption": f"Last {days} days, to {as_at:%d %b}"},
        {"label": "Venues", "value": len(venues), "caption": "With at least one job"},
        {"label": "Power handovers", "value": sum(is_power_job(x) for x in shown), "caption": f"Last {days} days"},
        {"label": "Still open", "value": sum(x["state"] in ("open", "in_progress") for x in shown), "caption": "Not completed"},
    ]), unsafe_allow_html=True)
    body = []
    for day in sorted({x["reported"].date() for x in shown}, reverse=True):
        todays = [x for x in shown if x["reported"].date() == day]
        body.append(f'<div class="rx-day">{day:%A %d %B %Y} · {len(todays)} jobs</div>' + "".join(
            f'<div class="rx-ev"><span>{x["reported"]:%H:%M}<small>{esc(x["building"])}</small></span>'
            f'<span><b>{esc(x["what"])}</b><small>{esc(x["remarks"][:110])}</small></span>'
            f'<span class="rx-tags"><span class="rx-tag">{esc(FAULT_STATE[x["state"]])}</span></span></div>' for x in todays))
    st.markdown("".join(body), unsafe_allow_html=True)
