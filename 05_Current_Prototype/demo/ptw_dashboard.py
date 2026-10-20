"""PTW dashboard: today's permits on a street map of Bay South, each zone filled in its contractor's colour.

Design (Dan, 10 and 12 October 2026): a box appears on the zone with works today, coloured in the contractor's
colour, with the contractor's logo, the work and its duration written on the box itself, so nobody has to hover.
The map is OpenStreetMap ("the attraction map is hard to read"); zone outlines come from OpenStreetMap too
(``assets/maps/bay-south-zones.geojson``). Google Maps needs an API key from Gardens by the Bay IT and would replace
only the tile layer. Clicking opens the PTW page in a new tab (``?ptw=<id>``): what is affected, electrical and
physical. Contractor colours live only here and in the calendar; machine states are words on this page.
Data comes only from ``demo.site_db``.
"""

from __future__ import annotations

import html
import json
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any

from demo.asset_state import LABEL, SGT, asset_state, ts

LEAFLET = "https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet"
TILES = ("https://tile.openstreetmap.org/{z}/{x}/{y}.png",
         '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank">OpenStreetMap</a> contributors')
BAY_SOUTH = [[1.2762, 103.8597], [1.2862, 103.8702]]  # Bay South park outline (OpenStreetMap relation 10231144)
MAP_HEIGHT, FOCUS_HEIGHT = 600, 380

BOLT = ('<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M13 2 4 14h7l-1 8 9-12h-7z" fill="currentColor"/></svg>')
BARRIER = ('<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="2" y="7" width="20" height="6" rx="1" fill="currentColor"/>'
           '<path d="M5 13v8M19 13v8" stroke="currentColor" stroke-width="2"/></svg>')

CSS = """
.sp-top {display:flex;flex-wrap:wrap;align-items:center;gap:.5rem .9rem;margin:0 0 .6rem}
.sp-count {display:inline-flex;align-items:center;gap:.45rem;background:var(--gbb-surface-2);border:1px solid var(--gbb-line);border-radius:.6rem;
  padding:.5rem .9rem;font-size:1.05rem;color:var(--gbb-ink-2)}
.sp-count b {font-size:1.45rem;color:var(--gbb-ink)}
.sp-who {display:inline-flex;align-items:center;gap:.4rem;font-size:1rem;color:var(--gbb-ink-2)}
.sp-logo {display:inline-grid;place-items:center;flex:none;width:1.7em;height:1.7em;border-radius:50%;background:var(--c);
  color:var(--ink);font-size:.72em;font-weight:800;letter-spacing:-.02em;box-shadow:0 0 0 2px rgba(255,255,255,.85)}
.sp-logo svg {width:100%;height:100%;border-radius:50%}
.sp-list {display:none;margin:.7rem 0 0}
.sp-list a {display:flex;align-items:center;gap:.55rem;padding:.5rem .6rem;border:1px solid var(--gbb-line);border-left:4px solid var(--c);
  border-radius:.55rem;margin:0 0 .4rem;color:var(--gbb-ink) !important;text-decoration:none !important;font-size:1.05rem}
.sp-list small {color:var(--gbb-ink-2);font-size:1rem;margin-left:auto;font-variant-numeric:tabular-nums}
.sp-note {font-size:.9rem;color:var(--gbb-ink-3);margin-top:.5rem}
.sp-head {display:flex;align-items:center;gap:.7rem;margin:.2rem 0 .3rem;padding-left:.7rem;border-left:5px solid var(--c)}
.sp-head .sp-logo {font-size:1.5rem}
.sp-head h3 {margin:0;padding:0;font-size:1.35rem}
.sp-meta {font-size:.82rem;color:var(--gbb-ink-3);margin:.15rem 0 .8rem .7rem}
.sp-meta b {color:var(--gbb-ink)}
.sp-impacts {display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:.65rem;margin:.3rem 0 .8rem}
.sp-impact {background:var(--gbb-surface-2);border:1px solid var(--gbb-line);border-radius:.7rem;padding:.7rem .85rem}
.sp-impact-head {display:flex;align-items:center;gap:.45rem;font-size:.72rem;letter-spacing:.06em;text-transform:uppercase;color:var(--gbb-ink-3)}
.sp-impact-head svg {width:1.1rem;height:1.1rem;color:var(--gbb-ink)}
.sp-impact b {display:block;font-size:1.15rem;margin:.25rem 0 .15rem;color:var(--gbb-ink)}
.sp-impact span {font-size:.8rem;color:var(--gbb-ink-2)}
.sp-impact ul {margin:.35rem 0 0;padding-left:1.05rem;font-size:.8rem;color:var(--gbb-ink-2)}
.sp-section {font-size:1rem;font-weight:700;margin:.6rem 0 .35rem}
@media (max-width: 640px) {.sp-list {display:block}}
"""


def _db(db: Any) -> Any:
    if db is None:
        from demo import site_db as db
    return db


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def ink_for(colour: str) -> str:
    """Black or white text, whichever reads better on the contractor's colour."""
    try:
        r, g, b = (int(colour.lstrip("#")[i:i + 2], 16) / 255 for i in (0, 2, 4))
    except ValueError:
        return "#ffffff"
    lin = [c / 12.92 if c <= .04045 else ((c + .055) / 1.055) ** 2.4 for c in (r, g, b)]
    return "#0b1524" if .2126 * lin[0] + .7152 * lin[1] + .0722 * lin[2] > .32 else "#ffffff"


def monogram(name: str) -> str:
    words = [word for word in str(name or "?").replace("&", " ").split() if word[:1].isalnum()]
    return (words[0][:1] + words[1][:1] if len(words) > 1 else words[0][:2] if words else "?").upper()


def logo_html(contractor: dict) -> str:
    colour = contractor.get("colour") or "#94a3b8"
    inner = contractor.get("logo_svg") or esc(monogram(contractor.get("name") or contractor.get("short_name")))
    return f'<span class="sp-logo" style="--c:{esc(colour)};--ink:{ink_for(colour)}" title="{esc(contractor.get("name"))}">{inner}</span>'


def window_text(start: Any, end: Any) -> str:
    """08:00–17:00 on one day; 10 Oct–14 Oct across days (SGT)."""
    a, b = ts(start).astimezone(SGT), ts(end).astimezone(SGT)
    return f"{a:%H:%M}–{b:%H:%M}" if a.date() == b.date() else f"{a:%d %b %H:%M} → {b:%d %b %H:%M}"


def short_window(start: Any, end: Any) -> str:
    a, b = ts(start).astimezone(SGT), ts(end).astimezone(SGT)
    return f"{a:%H:%M}–{b:%H:%M}" if a.date() == b.date() else f"{a:%d %b}–{b:%d %b}"


def today_window(as_of: Any) -> tuple[str, str]:
    day = ts(as_of).astimezone(SGT).date()
    start = datetime.combine(day, time.min, SGT).astimezone(timezone.utc)
    return start.isoformat(), (start + timedelta(days=1)).isoformat()


def todays_permits(db: Any) -> dict[str, Any]:
    """Permits overlapping today (SGT), active ones first; each knows whether it is on now."""
    as_of = db.as_of()
    start, end = today_window(as_of)
    now = ts(as_of)
    rows = []
    for ptw in db.ptws(start=start, end=end):
        ptw = {**ptw, "active": ts(ptw["start_at"]) <= now < ts(ptw["end_at"])}
        rows.append(ptw)
    rows.sort(key=lambda row: (not row["active"], row["start_at"], row["ptw_id"]))
    return {"as_of": as_of, "rows": rows, "zones": {zone["zone_code"]: zone for zone in db.zones()}}


def geo_bounds(geometry: dict, pad: float = 0.0) -> list[list[float]]:
    """[[south, west], [north, east]] of a GeoJSON Polygon or MultiPolygon, padded by ``pad`` degrees."""
    polygons = geometry["coordinates"] if geometry["type"] == "MultiPolygon" else [geometry["coordinates"]]
    points = [point for polygon in polygons for ring in polygon for point in ring]
    lons, lats = [point[0] for point in points], [point[1] for point in points]
    return [[min(lats) - pad, min(lons) - pad], [max(lats) + pad, max(lons) + pad]]


def label_html(ptw: dict) -> str:
    """What sits on the box: logo, the work, and its time. Active: solid contractor colour; later today: dashed."""
    contractor = ptw.get("contractor") or {}
    colour = contractor.get("colour") or "#94a3b8"
    ink = ink_for(colour)
    mark = contractor.get("logo_svg") or esc(monogram(contractor.get("name") or contractor.get("short_name")))
    when = (short_window(ptw["start_at"], ptw["end_at"]) if ptw["active"]
            else f'from {ts(ptw["start_at"]).astimezone(SGT):%H:%M}')
    if ptw["active"]:
        return (f'<div style="--c:{esc(colour)};--ink:{ink}"><span class="lg" style="color:{esc(colour)};background:#fff">{mark}</span>'
                f'<span><b>{esc(ptw.get("title"))}</b><small>{esc(when)}</small></span></div>')
    return (f'<div class="later" style="--c:{esc(colour)}"><span class="lg" style="background:{esc(colour)};color:{ink}">{mark}</span>'
            f'<span><b>{esc(ptw.get("title"))}</b><small>{esc(when)}</small></span></div>')


def map_features(rows: list[dict], zones: dict[str, dict]) -> list[dict]:
    """One feature per permit with a zone outline: the filled shape, its label and its link."""
    out = []
    for ptw in rows:
        zone = zones.get(ptw["zone_code"]) or ptw.get("zone") or {}
        if not zone.get("geometry"):
            continue
        colour = (ptw.get("contractor") or {}).get("colour") or "#94a3b8"
        out.append({"id": ptw["ptw_id"], "href": f'?ptw={ptw["ptw_id"]}', "geometry": json.loads(zone["geometry"]),
                    "lat": zone["lat"], "lon": zone["lon"], "label": label_html(ptw),
                    "tip": f'{ptw["ptw_id"]} · {zone.get("name") or ptw["zone_code"]} · {window_text(ptw["start_at"], ptw["end_at"])} SGT',
                    "style": {"color": colour, "weight": 3, "fillColor": colour, "fillOpacity": .5 if ptw["active"] else .12,
                              "dashArray": None if ptw["active"] else "6 6"}})
    return out


MAP_TEMPLATE = """<!doctype html><html><head><meta charset="utf-8"><link rel="stylesheet" href="__LEAFLET__.css">
<style>
html,body,#map{height:100%;margin:0;background:#F5F6F7;font-family:"Segoe UI",system-ui,-apple-system,Arial,sans-serif}
#map{border-radius:8px;border:1px solid #DCDEE0}
.pin>div{transform:translate(-50%,-50%);display:inline-flex;align-items:center;gap:6px;padding:4px 10px 4px 4px;border-radius:10px;
  background:var(--c);color:var(--ink);border:2px solid #fff;box-shadow:0 1px 4px rgba(36,39,42,.35);white-space:nowrap;cursor:pointer;
  font-size:15px;line-height:1.15;font-weight:700}
.pin>div.later{background:rgba(255,255,255,.94);color:#0b1524;border:2px dashed var(--c)}
.pin .lg{display:inline-grid;place-items:center;flex:none;width:30px;height:30px;border-radius:50%;font-size:12px;font-weight:800}
.pin .lg svg{width:100%;height:100%;border-radius:50%}
.pin b{display:block} .pin small{display:block;font-size:14px;font-weight:700;font-variant-numeric:tabular-nums}
.offline{color:#55595C;padding:2rem;font-size:14px}
</style></head><body><div id="map"></div>
<script src="__LEAFLET__.js"></script>
<script>
const D = __PAYLOAD__;
if (!window.L) {
  document.getElementById('map').innerHTML = '<p class="offline">The map needs an internet connection (OpenStreetMap). The permits are listed below.</p>';
} else {
  const map = L.map('map', {scrollWheelZoom: false, zoomSnap: 0.25});
  L.tileLayer(D.tiles, {maxZoom: 19, attribution: D.attribution}).addTo(map);
  map.fitBounds(D.bounds, {padding: [6, 6]});
  const base = (() => { try { return window.parent.location.href.split('?')[0]; } catch (e) { return (document.referrer || '/').split('?')[0]; } })();
  const go = href => window.open(base + href, '_blank');
  D.features.forEach(f => L.geoJSON(f.geometry, {style: f.style}).on('click', () => go(f.href)).addTo(map));
  const pins = D.features.map(f => {
    const pin = L.marker([f.lat, f.lon], {icon: L.divIcon({className: 'pin', html: f.label, iconSize: null}), title: f.tip, riseOnHover: true});
    return pin.on('click', () => go(f.href)).addTo(map);
  });
  const spread = () => {
    const labels = pins.map(pin => pin.getElement().firstElementChild);
    labels.forEach(label => label.style.marginTop = '0px');
    labels.sort((a, b) => a.getBoundingClientRect().top - b.getBoundingClientRect().top);
    for (let i = 1; i < labels.length; i++) for (let j = 0; j < i; j++) {
      const a = labels[j].getBoundingClientRect(), b = labels[i].getBoundingClientRect();
      if (a.left < b.right && b.left < a.right && a.top < b.bottom && b.top < a.bottom)
        labels[i].style.marginTop = (parseFloat(labels[i].style.marginTop) + a.bottom - b.top + 4) + 'px';
    }
  };
  map.on('zoomend moveend', spread);
  setTimeout(spread, 60);
}
</script></body></html>"""


def map_page(features: list[dict], bounds: list[list[float]] | None = None) -> str:
    """A self-contained Leaflet page (for ``components.html``): OpenStreetMap tiles, filled zones, labels on the boxes.
    Labels that would cover each other are nudged apart after every zoom."""
    if bounds is None and features:  # frame today's zones rather than the whole park, so the boxes are big enough to read
        corners = [geo_bounds(feature["geometry"]) for feature in features]
        bounds = [[min(c[0][0] for c in corners) - .0004, min(c[0][1] for c in corners) - .0004],
                  [max(c[1][0] for c in corners) + .0004, max(c[1][1] for c in corners) + .0004]]
    payload = json.dumps({"features": features, "bounds": bounds or BAY_SOUTH, "tiles": TILES[0], "attribution": TILES[1]})
    return MAP_TEMPLATE.replace("__LEAFLET__", LEAFLET).replace("__PAYLOAD__", payload.replace("</", "<\\/"))


def summary_html(data: dict[str, Any]) -> str:
    active = [row for row in data["rows"] if row["active"]]
    later = len(data["rows"]) - len(active)
    contractors = {row["contractor_id"]: row.get("contractor") or {} for row in data["rows"]}
    counts = f'<span class="sp-count"><b>{len(active)}</b>active now</span>'
    if later:
        counts += f'<span class="sp-count"><b>{later}</b>later today</span>'
    who = "".join(f'<span class="sp-who">{logo_html(item)}{esc(item.get("short_name") or item.get("name"))}</span>'
                  for item in contractors.values())
    note = f'<span class="sp-note" style="margin:0 0 0 auto">Synthetic · as of {ts(data["as_of"]).astimezone(SGT):%d %b %H:%M} SGT</span>'
    return f'<div class="sp-top">{counts}{who}{note}</div>'


def list_html(data: dict[str, Any]) -> str:
    """Shown on phones, where the map is small: the same permits as a list."""
    rows = "".join(f'<a href="?ptw={esc(row["ptw_id"])}" target="_blank" style="--c:{esc((row.get("contractor") or {}).get("colour") or "#94a3b8")}">'
                   f'{logo_html(row.get("contractor") or {})}{esc(data["zones"].get(row["zone_code"], {}).get("name") or row["zone_code"])}'
                   f'<small>{esc(short_window(row["start_at"], row["end_at"]))}</small></a>' for row in data["rows"])
    return f'<div class="sp-list">{rows}</div>'


def render(db: Any = None) -> None:
    import streamlit as st

    db = _db(db)
    data = todays_permits(db)
    st.markdown(f"<style>{CSS}</style>", unsafe_allow_html=True)
    if not data["rows"]:
        st.info("No permits to work today.")
    import streamlit.components.v1 as components

    # the map fills the rest of the screen, so the dashboard needs no scrolling
    st.markdown('<style>iframe[data-testid="stIFrame"] {height:calc(100vh - 13rem) !important;min-height:420px}</style>'
                + summary_html(data), unsafe_allow_html=True)
    components.html(map_page(map_features(data["rows"], data["zones"])), height=MAP_HEIGHT)
    st.markdown(list_html(data), unsafe_allow_html=True)  # phones only; the map credits OpenStreetMap in its corner


PAGE_CSS = """
.pp-head {display:flex;align-items:center;gap:1rem;margin:.3rem 0 .5rem}
.pp-head .sp-logo {font-size:2.1rem;box-shadow:0 0 0 3px #fff,0 0 0 4px var(--gbb-line-strong)}
.pp-title {font-size:2.7rem;font-weight:800;line-height:1.08;color:var(--gbb-ink);letter-spacing:-.01em}
.pp-status {display:inline-flex;align-items:center;gap:.6rem;font-size:1.5rem;font-weight:800;padding:.35rem 1.1rem;
  border-radius:99px;border:3px solid var(--c);color:var(--gbb-ink);margin:.3rem 0 1.2rem;letter-spacing:.03em}
.pp-status i {display:inline-block;width:.9rem;height:.9rem;border-radius:50%;background:var(--c)}
.pp-status.pp-live i {animation:pp-pulse 1.6s ease-in-out infinite}
@keyframes pp-pulse {50% {opacity:.3}}
.pp-facts {display:grid;grid-template-columns:repeat(auto-fit,minmax(16rem,1fr));gap:1rem;margin:0 0 1.2rem}
.pp-fact {background:var(--gbb-surface-2);border:2px solid var(--gbb-line);border-radius:1rem;padding:1rem 1.25rem}
.pp-fact small {display:block;font-size:1.05rem;font-weight:800;letter-spacing:.08em;text-transform:uppercase;color:var(--gbb-ink-3)}
.pp-fact b {display:flex;align-items:center;gap:.6rem;font-size:2.1rem;line-height:1.15;color:var(--gbb-ink);margin-top:.35rem}
.pp-fact b .sp-logo {font-size:1.05rem}
.pp-fact span {display:block;font-size:1.3rem;color:var(--gbb-ink-2);margin-top:.3rem}
.pp-section {font-size:1.7rem;font-weight:800;margin:1.3rem 0 .7rem;color:var(--gbb-ink)}
.pp-impacts {display:grid;grid-template-columns:repeat(auto-fit,minmax(20rem,1fr));gap:1rem}
.pp-impact {background:var(--gbb-surface-2);border:2px solid var(--gbb-line);border-left:10px solid var(--c);border-radius:1rem;padding:1.1rem 1.3rem}
.pp-kind {display:flex;align-items:center;gap:.5rem;font-size:1.05rem;font-weight:800;letter-spacing:.08em;text-transform:uppercase;color:var(--gbb-ink-3)}
.pp-kind svg {width:1.5rem;height:1.5rem;color:var(--gbb-ink)}
.pp-impact b {display:block;font-size:2.1rem;line-height:1.15;color:var(--gbb-ink);margin:.4rem 0 .3rem}
.pp-impact span {display:block;font-size:1.3rem;color:var(--gbb-ink-2)}
.pp-impact ul {margin:.5rem 0 0;padding-left:1.4rem;font-size:1.3rem;color:var(--gbb-ink-2)}
.pp-foot {font-size:1.05rem;color:var(--gbb-ink-3);margin-top:1.2rem}
@media (max-width: 640px) {.pp-title {font-size:2rem} .pp-fact b, .pp-impact b {font-size:1.7rem}}
@media (prefers-reduced-motion: reduce) {.pp-status i {animation:none}}
"""


def when_fact(start: Any, end: Any, as_of: Any) -> tuple[str, str]:
    """Big line and small line for WHEN: the hours on one day, or the dates across days (SGT)."""
    a, b, today = ts(start).astimezone(SGT), ts(end).astimezone(SGT), ts(as_of).astimezone(SGT).date()
    if a.date() == b.date():
        return f"{a:%H:%M} – {b:%H:%M}", "Today" if a.date() == today else f"{a:%a %d %b}"
    return f"{a:%d %b} → {b:%d %b}", f"{a:%H:%M} → {b:%H:%M}"


def render_ptw_page(ptw_id: str, db: Any = None) -> None:
    """Opened from a box. Built for older eyes: few words, the important ones big, nothing hidden."""
    import streamlit as st

    db = _db(db)
    st.markdown(f"<style>{CSS}{PAGE_CSS}</style>", unsafe_allow_html=True)
    ptw = db.ptw(ptw_id)
    if ptw is None:
        st.error(f"No permit {ptw_id} in the site database.")
        return
    contractor, as_of = ptw.get("contractor") or {}, db.as_of()
    colour = contractor.get("colour") or "#94a3b8"
    zones = {zone["zone_code"]: zone for zone in db.zones()}
    zone = zones.get(ptw["zone_code"], {})
    now, start, end = ts(as_of), ts(ptw["start_at"]), ts(ptw["end_at"])
    active = start <= now < end
    status = ("ACTIVE NOW" if active else f"STARTS {start.astimezone(SGT):%H:%M}" if now < start and start.astimezone(SGT).date() == now.astimezone(SGT).date()
              else f"STARTS {start.astimezone(SGT):%a %d %b}".upper() if now < start else "FINISHED")
    big, small = when_fact(ptw["start_at"], ptw["end_at"], as_of)
    linked = [row for row in db.work_orders(ptw["start_at"], ptw["end_at"]) if row.get("ptw_id") == ptw_id]
    facts = [("When", big, small), ("Where", esc(zone.get("name") or ptw["zone_code"]), ""),
             ("Who", f'{logo_html(contractor)}{esc(contractor.get("short_name") or contractor.get("name"))}',
              esc(str(ptw.get("work_type") or "").replace("_", " ").capitalize() + " works"))]
    facts += [("Work order", esc(row["wo_id"]), esc(row.get("title"))) for row in linked]
    st.markdown(f'<div class="pp-head" style="--c:{esc(colour)}">{logo_html(contractor)}<div class="pp-title">{esc(ptw.get("title"))}</div></div>'
                f'<div class="pp-status{" pp-live" if active else ""}" style="--c:{esc(colour)}"><i></i>{esc(status)}</div>'
                '<div class="pp-facts">' + "".join(f'<div class="pp-fact"><small>{name}</small><b>{value}</b>'
                                                   + (f"<span>{note}</span>" if note else "") + "</div>" for name, value, note in facts)
                + "</div>", unsafe_allow_html=True)

    assets = {asset["asset_id"]: asset for asset in db.assets()}
    latest = db.latest_readings()

    def word(item: dict) -> str:  # state as a word: colours on this page mean contractors, not machine states
        if not item.get("connected", 1):
            return "Not connected"
        if str(item.get("operating_hours") or "").lower() == "on demand":  # an OG box: no load is normal, so say why
            return "No supply" if item.get("fed_from") in isolated else LABEL[asset_state(item, latest.get(item["asset_id"], {}), as_of)["state"]]
        return LABEL[asset_state(item, latest.get(item["asset_id"], {}), as_of)["state"]]

    isolated = {impact.get("target_id") for impact in ptw.get("impacts", []) if impact.get("effect") == "isolated"}
    cards = []
    for impact in ptw.get("impacts", []):
        icon, label = (BOLT, "Electrical") if impact.get("kind") == "electrical" else (BARRIER, "Physical")
        target = impact.get("target_id")
        listed = ""
        if impact.get("target_type") == "asset" and target in assets:
            where = f'{esc(assets[target].get("name"))} · {word(assets[target])}'
            fed = [item for item in assets.values() if item.get("fed_from") == target]
            listed = "".join(f"<li>{esc(item.get('name'))} · {word(item)}</li>" for item in fed)
            listed = f"<ul><li style='list-style:none;margin-left:-1.4rem'>Also off:</li>{listed}</ul>" if listed else ""
        else:
            where = esc(zones.get(target, {}).get("name") or target)
        if (impact.get("start_at"), impact.get("end_at")) != (ptw["start_at"], ptw["end_at"]):
            only, note = when_fact(impact["start_at"], impact["end_at"], as_of)
            where += f" · {esc(only)} only"
        cards.append(f'<div class="pp-impact" style="--c:{esc(colour)}"><div class="pp-kind">{icon}{label}</div>'
                     f'<b>{esc(impact.get("summary"))}</b><span>{where}</span>{listed}</div>')
    st.markdown('<div class="pp-section">What is affected</div>'
                + (f'<div class="pp-impacts">{"".join(cards)}</div>' if cards else '<div class="pp-fact"><b>Nothing recorded</b></div>'),
                unsafe_allow_html=True)
    if zone.get("geometry"):
        import streamlit.components.v1 as components

        st.markdown('<div class="pp-section">On the map</div>', unsafe_allow_html=True)
        components.html(map_page(map_features([{**ptw, "active": active}], zones), geo_bounds(json.loads(zone["geometry"]), pad=.0012)),
                        height=FOCUS_HEIGHT)
    source = Path(ptw["source_file"]).name if ptw.get("source_file") else "Synthetic record"
    st.markdown(f'<div class="pp-foot">Permit {esc(ptw_id)} · {esc(source)} · map © OpenStreetMap contributors</div>',
                unsafe_allow_html=True)
