"""PTW map from the real permit forms: markers at mapped buildings, clustering, a density layer, and exceptions.

What a number on the map means: how many permits in the current filter name that location. It is a count, not a
risk level; the forms carry no risk rating, so none is shown or implied. Markers are neutral grey for that reason.

Locations come from demo.sources.locations (the client's Power BI mapping, approximate coordinates). A permit that
names several buildings appears at each of them, but totals count it once, and buildings that share a coordinate
are one point. Permits whose location is not recognised, or whose dates cannot be read, are listed as exceptions with
their original text; nothing is placed at a guessed position.

The forms do not record affected assets, electrical isolations or downstream impact. The permit panel says so instead
of borrowing those fields from the synthetic site data.
"""

from __future__ import annotations

import html
import json
from datetime import datetime, timedelta
from typing import Any

from demo import brand
from demo.ptw_dashboard import BAY_SOUTH, LEAFLET, TILES
from demo.sources.ptw_forms import SGT, timing, unique

CLUSTER = "https://cdn.jsdelivr.net/npm/leaflet.markercluster@1.5.3/dist"
HEAT = "https://cdn.jsdelivr.net/npm/leaflet.heat@0.2.0/dist/leaflet-heat.js"
PERIODS = ("Active today", "Next 7 days", "Last 30 days", "Year to date", "All records")
APPROVAL_WORD = {key: word for key, (_, word, _) in brand.PTW_APPROVAL.items()}
TIMING_WORD = {key: word for key, (_, word, _) in brand.PTW_TIMING.items()}


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def period_window(period: str, now: datetime) -> tuple[datetime | None, datetime | None]:
    day = now.astimezone(SGT).replace(hour=0, minute=0, second=0, microsecond=0)
    return {"Active today": (now, now), "Next 7 days": (now, day + timedelta(days=8)),
            "Last 30 days": (day - timedelta(days=30), now), "Year to date": (day.replace(month=1, day=1), now),
            "All records": (None, None)}[period]


def select(records: list[dict], now: datetime, period: str = "Active today", sites: list[str] | None = None,
           forms: list[str] | None = None, approvals: list[str] | None = None, buildings: list[str] | None = None,
           text: str = "") -> list[dict]:
    """Unique permits matching every filter; a permit is in a period when its window overlaps it."""
    start, end = period_window(period, now)
    needle = text.casefold().strip()
    out = []
    for record in unique(records):
        if start is not None:
            if not record["usable_window"] or record["start"] > end or record["end"] < start:
                continue
        if sites and record["site"] not in sites:
            continue
        if forms and record["form"] not in forms:
            continue
        if approvals and record["approval"] not in approvals:
            continue
        if buildings and not set(record["buildings"]) & set(buildings):
            continue
        if needle and needle not in " ".join(str(record[key]) for key in ("ref", "company", "location_raw", "description", "work_type")).casefold():
            continue
        out.append(record)
    return sorted(out, key=lambda record: (record["start"] or datetime.max.replace(tzinfo=SGT)), reverse=True)


def window_text(record: dict) -> str:
    if not record["usable_window"]:
        if record["start"] and record["end"]:
            return f"{record['start']:%d %b %Y %H:%M} – {record['end']:%d %b %Y %H:%M} (end before start)"
        return "Dates unreadable"
    a, b = record["start"].astimezone(SGT), record["end"].astimezone(SGT)
    return f"{a:%d %b %Y %H:%M} – {b:%H:%M}" if a.date() == b.date() else f"{a:%d %b %Y %H:%M} – {b:%d %b %Y %H:%M}"


def map_points(records: list[dict], point_of: dict[str, dict], now: datetime) -> tuple[list[dict], list[dict]]:
    """(points with their permits, permits that cannot be placed). Each permit is counted once per point."""
    points: dict[str, dict] = {}
    unplaced = []
    for record in records:
        placed = {point_of[name]["point_id"]: point_of[name] for name in record["buildings"] if name in point_of}
        if not placed:
            unplaced.append(record)
            continue
        for point_id, point in placed.items():
            item = points.setdefault(point_id, {**point, "permits": []})
            item["permits"].append({"ref": record["ref"], "company": record["company"], "form": record["form"],
                                    "window": window_text(record), "timing": TIMING_WORD.get(timing(record, now), ""),
                                    "approval": APPROVAL_WORD[record["approval"]], "work": record["work_type"] or record["description"][:80]})
    out = sorted(points.values(), key=lambda point: (-len(point["permits"]), point["names"][0]))
    for point in out:
        point["count"] = len(point["permits"])
    return out, unplaced


MAP_TEMPLATE = """<!doctype html><html><head><meta charset="utf-8">
<link rel="stylesheet" href="__LEAFLET__.css"><link rel="stylesheet" href="__CLUSTER__/MarkerCluster.css">
<style>
html,body,#map{height:100%;margin:0;background:#F5F6F7;font-family:"Segoe UI",system-ui,-apple-system,Arial,sans-serif}
#map{border:1px solid #DCDEE0;border-radius:8px}
.pt{display:grid;place-items:center;border-radius:50%;background:#55595C;color:#fff;font-weight:700;border:2px solid #fff;
  box-shadow:0 1px 4px rgba(36,39,42,.4);font-variant-numeric:tabular-nums}
.pt.approx{border-style:dashed}
.cl{display:grid;place-items:center;border-radius:50%;background:#24272A;color:#fff;font-weight:800;border:3px solid #fff;
  box-shadow:0 1px 5px rgba(36,39,42,.45)}
.leaflet-popup-content{margin:10px 12px;font-size:13px;line-height:1.35;color:#24272A;max-height:260px;overflow:auto}
.leaflet-popup-content b{font-size:14px}
.leaflet-popup-content ul{margin:6px 0 0;padding-left:16px}
.leaflet-popup-content small{color:#55595C}
.offline{color:#55595C;padding:2rem;font-size:14px}
</style></head><body><div id="map"></div>
<script src="__LEAFLET__.js"></script><script src="__CLUSTER__/leaflet.markercluster.js"></script><script src="__HEAT__"></script>
<script>
const D = __PAYLOAD__;
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
if (!window.L) {
  document.getElementById('map').innerHTML = '<p class="offline">The map needs an internet connection (OpenStreetMap). The permits are listed below.</p>';
} else {
  const map = L.map('map', {scrollWheelZoom: false, zoomSnap: 0.25});
  L.tileLayer(D.tiles, {maxZoom: 19, attribution: D.attribution}).addTo(map);
  const size = n => Math.round(24 + 5 * Math.sqrt(n));
  const markers = L.markerClusterGroup ? L.markerClusterGroup({showCoverageOnHover: false, maxClusterRadius: 38,
    iconCreateFunction: c => { const n = new Set(c.getAllChildMarkers().flatMap(m => m.options.refs)).size, s = size(n) + 6;
      return L.divIcon({className: '', html: `<div class="cl" style="width:${s}px;height:${s}px" title="${n} distinct permits in this cluster">${n}</div>`, iconSize: [s, s]}); }})
    : L.layerGroup();
  D.points.forEach(p => {
    const s = size(p.count);
    const icon = L.divIcon({className: '', iconSize: [s, s], html: `<div class="pt${p.verified ? '' : ' approx'}" style="width:${s}px;height:${s}px">${p.count}</div>`});
    const list = p.permits.slice(0, 25).map(x => `<li><b>${esc(x.ref)}</b> · ${esc(x.company)}<br><small>${esc(x.window)} · ${esc(x.timing)} · ${esc(x.approval)}</small><br>${esc(x.work)}</li>`).join('');
    const more = p.permits.length > 25 ? `<div><small>${p.permits.length - 25} more in the permit list below.</small></div>` : '';
    const where = esc(p.names.join(' / '));
    const note = p.verified ? '' : '<br><small>Approximate coordinates (not verified)</small>';
    L.marker([p.lat, p.lon], {icon, count: p.count, refs: p.permits.map(x => x.ref), title: `${p.names.join(' / ')}: ${p.count} permit(s)`})
      .bindPopup(`<b>${where}</b><br><small>${p.count} permit(s) in this selection${note}</small><ul>${list}</ul>${more}`, {maxWidth: 360})
      .addTo(markers);
  });
  markers.addTo(map);
  const overlays = {'Permit markers (clustered)': markers};
  if (L.heatLayer && D.points.length) {
    const top = Math.max(...D.points.map(p => p.count));
    overlays['Permit density (count of permits)'] = L.heatLayer(D.points.map(p => [p.lat, p.lon, p.count / top]), {radius: 34, blur: 26, maxZoom: 18, minOpacity: .25,
      gradient: {0.25: '#C7D8EE', 0.55: '#7FA6D6', 0.8: '#3F78BE', 1: '#1F5FAD'}}  // one hue: more permits, never 'danger');
  }
  L.control.layers(null, overlays, {collapsed: false}).addTo(map);
  const bounds = D.points.length ? L.latLngBounds(D.points.map(p => [p.lat, p.lon])).pad(0.25) : L.latLngBounds(D.fallback);
  map.fitBounds(bounds, {maxZoom: 17});
}
</script></body></html>"""


def map_page(points: list[dict]) -> str:
    payload = json.dumps({"points": points, "tiles": TILES[0], "attribution": TILES[1], "fallback": BAY_SOUTH}, default=str)
    return (MAP_TEMPLATE.replace("__LEAFLET__", LEAFLET).replace("__CLUSTER__", CLUSTER).replace("__HEAT__", HEAT)
            .replace("__PAYLOAD__", payload.replace("</", "<\\/")))


CSS = """
.rp-figs {display:flex;flex-wrap:wrap;gap:.4rem 1.6rem;margin:.2rem 0 .8rem}
.rp-fig b {font-size:1.6rem;font-weight:750;font-variant-numeric:tabular-nums;margin-right:.35rem}
.rp-fig span {font-size:.88rem;color:var(--gbb-ink-2)}
.rp-note {font-size:.8rem;color:var(--gbb-ink-3);margin:.3rem 0 .6rem;line-height:1.45}
.rp-loc {list-style:none;margin:0;padding:0;max-height:560px;overflow:auto}
.rp-loc li {display:flex;justify-content:space-between;gap:.6rem;padding:.38rem 0;border-bottom:1px solid var(--gbb-line);font-size:.9rem}
.rp-loc b {font-variant-numeric:tabular-nums}
.rp-loc small {display:block;color:var(--gbb-ink-3);font-size:.76rem}
.rp-detail {display:grid;grid-template-columns:repeat(auto-fill,minmax(15rem,1fr));gap:.8rem 1.2rem;margin:.4rem 0 .8rem}
.rp-detail div small {display:block;font-size:.72rem;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:var(--gbb-ink-3)}
.rp-detail div span {font-size:.95rem}
.rp-missing {border:1.5px dashed var(--gbb-line-strong);border-radius:var(--gbb-radius);padding:.6rem .8rem;font-size:.86rem;color:var(--gbb-ink-2)}
"""

ISSUE_WORD = {"unknown_location": "Location not recognised", "partial_location": "Location partly recognised",
              "blank_value": "Blank required value", "invalid_value": "Value could not be read",
              "end_before_start": "End before start", "duplicate_row": "Duplicate reference",
              "missing_column": "Missing column", "missing_file": "Missing file", "unreadable_file": "Unreadable file"}


def render(folder, load_data) -> None:
    """The PTW map page for imported permit forms. ``load_data(folder)`` returns (permits, buildings, problems)."""
    import pandas as pd
    import streamlit as st
    import streamlit.components.v1 as components

    from demo.sources.locations import points as building_points

    permits, buildings, building_problems = load_data(str(folder))
    records = permits["records"]
    now = datetime.now(SGT)
    point_of = building_points(buildings)
    st.markdown(f"<style>{CSS}</style>", unsafe_allow_html=True)
    modified = permits["modified"].strftime("%d %b %Y %H:%M") if permits["modified"] else "unknown"
    st.markdown(f'<div class="rp-note">{len(permits["files"])} Excel exports from the permit forms, '
                f'files last modified {modified} SGT. Read when this page loads; not a live feed. Times are as written on the forms (SGT).</div>',
                unsafe_allow_html=True)

    all_unique = unique(records)
    c1, c2, c3, c4 = st.columns([1.5, 1, 1.4, 1])
    with c1:
        period = st.segmented_control("Period", PERIODS, default="Active today", key="rp_period") or "Active today"
    with c2:
        sites = st.multiselect("Site", sorted({r["site"] for r in all_unique if r["site"]}), key="rp_sites", placeholder="All sites")
    with c3:
        forms = st.multiselect("Form type", sorted({r["form"] for r in all_unique}), key="rp_forms", placeholder="All forms")
    with c4:
        approvals = st.multiselect("Approval", list(APPROVAL_WORD), format_func=APPROVAL_WORD.get, key="rp_approval", placeholder="Any decision")
    c5, c6 = st.columns([2, 1.4])
    with c5:
        chosen = st.multiselect("Location", sorted(buildings), key="rp_buildings", placeholder="All mapped locations")
    with c6:
        text = st.text_input("Search reference, company or work", key="rp_text")
    shown = select(records, now, period, sites, forms, approvals, chosen, text)
    points, unplaced = map_points(shown, point_of, now)
    states = [timing(record, now) for record in shown]
    figs = [(len(shown), "permits in this selection"), (states.count("active"), "active now"),
            (states.count("later"), "start later"), (len(shown) - len(unplaced), "placed on the map"),
            (len(unplaced), "not placed (see exceptions)")]
    st.markdown('<div class="rp-figs">' + "".join(f'<span class="rp-fig"><b>{n}</b><span>{esc(w)}</span></span>' for n, w in figs) + "</div>",
                unsafe_allow_html=True)

    left, right = st.columns([2.6, 1], gap="medium")
    with left:
        components.html(map_page(points), height=560)
        st.markdown('<div class="rp-note">The number on a marker is how many permits in this selection name that location: a count, '
                    'not a risk level. Dashed rings mark coordinates that are approximate (all are, until verified in Building Location.xlsx). '
                    'A permit naming several buildings appears at each; the totals above count it once.</div>', unsafe_allow_html=True)
    with right:
        st.markdown('<div class="sd-section">Permits by location</div>', unsafe_allow_html=True)
        if points:
            st.markdown('<ul class="rp-loc">' + "".join(
                f'<li><span>{esc(" / ".join(point["names"]))}<small>{"approximate position" if not point["verified"] else "verified position"}</small></span>'
                f'<b>{point["count"]}</b></li>' for point in points) + "</ul>", unsafe_allow_html=True)
        else:
            st.caption("No permit in this selection can be placed on the map.")

    tab_list, tab_exceptions, tab_report = st.tabs([f"Permits ({len(shown)})", f"Location exceptions ({len(unplaced)})", "Validation report"])
    with tab_list:
        if not shown:
            st.info("No permits match these filters. Try a longer period.")
        else:
            table = pd.DataFrame([{"Reference": r["ref"], "Window (SGT)": window_text(r), "Timing": TIMING_WORD.get(timing(r, now), "—"),
                                   "Approval": APPROVAL_WORD[r["approval"]], "Company": r["company"], "Location (as written)": r["location_raw"],
                                   "Mapped to": ", ".join(r["buildings"]) or "—", "Form": r["form"], "Site": r["site"]} for r in shown])
            picked = st.dataframe(table, hide_index=True, width="stretch", height=320, on_select="rerun", selection_mode="single-row", key="rp_table")
            rows = picked.selection.rows if picked and picked.selection else []
            if rows:
                permit_panel(shown[rows[0]], now)
            else:
                st.caption("Select a row to see the permit.")
    with tab_exceptions:
        st.caption("Permits in this selection that cannot be placed: the location text names no known building, or the dates cannot be read. "
                   "Their original text is kept as written.")
        if unplaced:
            st.dataframe(pd.DataFrame([{"Reference": r["ref"], "Location (as written)": r["location_raw"], "Window (SGT)": window_text(r),
                                        "Company": r["company"], "File": r["source_file"], "Row": r["source_row"]} for r in unplaced]),
                         hide_index=True, width="stretch")
        else:
            st.caption("None in this selection.")
        partial = [r for r in shown if r["match"] == "text" and r["leftover"]]
        if partial:
            st.markdown(f"**Partly recognised ({len(partial)})**: placed at the buildings found; the rest of the text is shown for checking.")
            st.dataframe(pd.DataFrame([{"Reference": r["ref"], "Mapped to": ", ".join(r["buildings"]), "Not recognised": "; ".join(r["leftover"]),
                                        "Location (as written)": r["location_raw"]} for r in partial]), hide_index=True, width="stretch")
    with tab_report:
        issues = building_problems + permits["issues"]
        counts = pd.Series([ISSUE_WORD.get(item["issue"], item["issue"]) for item in issues]).value_counts()
        st.caption(f"All {len(records)} rows read from {len(permits['files'])} files and the building list, before filters. "
                   "Rows with problems are kept and listed here; none is dropped silently.")
        if issues:
            st.dataframe(counts.rename_axis("Issue").reset_index(name="Rows"), hide_index=True)
            report = pd.DataFrame(issues)[["issue", "detail", "ref", "field", "value", "file", "row"]]
            st.dataframe(report, hide_index=True, width="stretch", height=260)
            st.download_button("Download validation report (CSV)", report.to_csv(index=False), file_name="ptw-validation-report.csv", mime="text/csv")
        else:
            st.caption("No problems found.")


def permit_panel(record: dict, now: datetime) -> None:
    import streamlit as st

    fields = [("Reference", record["ref"]), ("Window (SGT)", window_text(record)),
              ("Timing", TIMING_WORD.get(timing(record, now), "Dates unreadable")), ("Approval", APPROVAL_WORD[record["approval"]]),
              ("Company", record["company"] or "Not recorded"), ("Location as written", record["location_raw"] or "Not recorded"),
              ("Mapped to", ", ".join(record["buildings"]) or "No known building"), ("Form", record["form"]),
              ("Site", record["site"] or "Not recorded"), ("Trade", record["trade"] or "Not recorded"),
              ("Type of work", record["work_type"] or "Not recorded"), ("Job types ticked", record["permit_jobs"] or "Not on this form")]
    st.markdown('<div class="rp-detail">' + "".join(f'<div><small>{esc(k)}</small><span>{esc(v)}</span></div>' for k, v in fields) + "</div>",
                unsafe_allow_html=True)
    if record["description"]:
        st.markdown(f"**Description of work:** {esc(record['description'])}")
    st.markdown('<div class="rp-missing">Not recorded on these forms: affected assets, electrical isolations and downstream impact. '
                'They are unavailable for imported permits rather than estimated.</div>', unsafe_allow_html=True)
    with st.expander("Original values and source", expanded=False):
        st.caption(f"{record['source_file']}, row {record['source_row']}. Personal details on the form are not read.")
        st.json(record["source"])
