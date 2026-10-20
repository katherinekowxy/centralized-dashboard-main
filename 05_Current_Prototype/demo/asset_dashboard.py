"""Asset dashboard: every tracked asset, by zone, on the TV. Minimal words; numbers live on the asset page.

States (Dan, 10 October 2026): green operational, blue idle, orange warning, red down, grey offline. The TV look
(Dan, 13 October 2026; demo/site_theme.py): a healthy asset is its name and a small dot, a problem is a full-width
banner, and a pulsing cone marks maintenance today or an active permit. Clicking a row opens the asset page in a new
tab (``?asset=<id>``). Data comes only from ``demo.site_db`` (docs/site-data-contract.md).
"""

from __future__ import annotations

import html
from datetime import datetime, time, timedelta, timezone
from typing import Any

from demo import brand, site_theme
from demo.asset_state import COLOUR, EVENT_POWER_TYPES, LABEL, SEVERITY, SGT, asset_state, maintenance_today, ts

POINTS = (("voltage_v", "Voltage", "V"), ("current_a", "Current", "A"), ("power_kw", "Power", "kW"),
          ("power_factor", "Power factor", ""), ("energy_kwh", "Energy", "kWh"))
LINE, PAPER, PLOT, GRID, MUTED, INK = (brand.CHART["reading"], brand.CHART["paper"], brand.CHART["plot"], brand.CHART["grid"],
                                      brand.INK_3, brand.INK)

CONE = ('<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M10.1 2.5h3.8l5.2 16.5H4.9z" fill="#334155"/>'
        '<path d="M8.5 8.7h7l.95 3.1h-8.9zM6.8 14.3h10.4l.9 2.8H5.9z" fill="#fff"/>'
        '<rect x="2.5" y="19" width="19" height="2.6" rx="1.1" fill="#334155"/></svg>')  # slate on white, as on the TV pages

CSS = """
.sa-bar {display:flex;flex-wrap:wrap;align-items:center;gap:.5rem 1.4rem;margin:0 0 .8rem}
.sa-tally {display:flex;flex-wrap:wrap;gap:.6rem}
.sa-tally span {display:inline-flex;align-items:center;gap:.5rem;background:var(--gbb-surface-2);border:1px solid var(--gbb-line);
  border-radius:.7rem;padding:.5rem .9rem;font-size:1.05rem;color:var(--gbb-ink-2)}
.sa-tally b {font-size:1.45rem;color:var(--gbb-ink)}
.sa-zones {column-width:19rem;column-gap:.9rem}  /* zones flow down columns across the full width */
.sa-group {display:inline-block;width:100%;box-sizing:border-box;break-inside:avoid;margin:0 0 .9rem;border:2px solid var(--gbb-line-strong);
  border-radius:1.1rem;background:var(--gbb-surface);padding:.6rem .75rem .75rem}
.sa-zone {display:flex;flex-wrap:wrap;align-items:center;gap:.3rem 1rem;margin:0 0 .55rem;font-size:1.35rem;font-weight:800;
  line-height:1.2;color:var(--gbb-ink)}
.sa-zone em {display:inline-flex;align-items:center;gap:.4rem;font-style:normal;font-size:1.05rem;font-weight:800;color:var(--gbb-ink)}
.sa-grid {display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:.5rem}
.sa-box {position:relative;display:flex;flex-direction:column;gap:.1rem;padding:.55rem .7rem .5rem;border-radius:12px;
  min-height:3.8rem;background:color-mix(in srgb, var(--c) 13%, var(--gbb-surface));
  border:2px solid color-mix(in srgb, var(--c) 80%, transparent);color:var(--gbb-ink) !important;text-decoration:none !important}
.sa-box:hover {border-color:var(--c);background:color-mix(in srgb, var(--c) 20%, var(--gbb-surface))}
.sa-name {font-weight:750;font-size:1.12rem;line-height:1.2;color:var(--gbb-ink);word-break:normal;overflow-wrap:normal;text-wrap:balance}
.sa-box:has(.sa-cone) .sa-name {padding-right:1.4rem}  /* room for the cone only where there is one */
.sa-id {font-size:.82rem;color:var(--gbb-ink-3);font-variant-numeric:tabular-nums}
.sa-state {margin-top:auto;padding-top:.3rem;display:inline-flex;align-items:center;gap:.4rem;font-size:1rem;font-weight:750;color:var(--gbb-ink)}
.sa-dot {display:inline-block;flex:none;width:.8rem;height:.8rem;border-radius:50%;background:var(--c)}
.sa-orb {display:none}
@supports (offset-path: inset(0 round 12px)) {
  .sa-orb {display:block;position:absolute;left:0;top:0;width:9px;height:9px;border-radius:50%;pointer-events:none;
    background:var(--c);box-shadow:0 0 6px 2px var(--c),0 0 16px 5px color-mix(in srgb, var(--c) 50%, transparent);
    offset-path:inset(0 round 12px);offset-rotate:0deg;animation:sa-orbit 3.2s linear infinite}
  .sa-orb + .sa-orb {animation-delay:-1.6s}
}
@keyframes sa-orbit {from {offset-distance:0%} to {offset-distance:100%}}
.sa-cone {position:absolute;top:-.7rem;right:-.55rem;width:1.9rem;height:1.9rem;filter:drop-shadow(0 0 2px rgba(255,255,255,.9));
  animation:sa-pulse 1.6s ease-in-out infinite}
@keyframes sa-pulse {0%,100% {transform:scale(1);opacity:1} 50% {transform:scale(1.15);opacity:.6}}
.sa-legend {display:flex;flex-wrap:wrap;gap:.4rem 1.2rem;margin:0;font-size:.95rem;color:var(--gbb-ink-2)}
.sa-legend span {display:inline-flex;align-items:center;gap:.4rem}
.sa-legend .sa-cone {position:static;width:1.2rem;height:1.2rem;animation:none}
.sa-note {font-size:.9rem;color:var(--gbb-ink-3)}
.sa-head {display:flex;align-items:center;gap:.7rem;font-size:2.4rem;font-weight:800;margin:.2rem 0 .3rem;color:var(--gbb-ink)}
.sa-head .sa-dot {width:1.4rem;height:1.4rem}
.sa-chips {display:flex;flex-wrap:wrap;gap:.5rem;margin:.6rem 0 .3rem}
.sa-chip {display:inline-flex;align-items:center;gap:.5rem;border:2px solid var(--gbb-line);border-radius:99px;padding:.3rem .8rem;
  font-size:1.05rem;color:var(--gbb-ink)}
.sa-chip .sa-cone {position:static;width:1.4rem;height:1.4rem;animation:none}
.sa-tiles {display:grid;grid-template-columns:repeat(auto-fill,minmax(11rem,1fr));gap:.8rem;margin:.8rem 0 1rem}
.sa-tile {background:var(--gbb-surface-2);border:2px solid var(--gbb-line);border-radius:1rem;padding:.9rem 1.1rem}
.sa-tile small {display:block;font-size:1rem;font-weight:800;letter-spacing:.06em;text-transform:uppercase;color:var(--gbb-ink-3)}
.sa-tile b {font-size:2.2rem;color:var(--gbb-ink);font-variant-numeric:tabular-nums}
.sa-tile i {font-style:normal;font-size:1.1rem;color:var(--gbb-ink-2);margin-left:.3rem}
@media (prefers-reduced-motion: reduce) {.sa-orb, .sa-cone {animation:none}}
@media (max-width: 640px) {.sa-zones {columns:1}}
"""


def _db(db: Any) -> Any:
    if db is None:
        from demo import site_db as db
    return db


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def number(value: Any) -> str:
    value = float(value)
    return f"{value:,.0f}" if abs(value) >= 1000 else f"{value:.3g}"


def sgt(value: Any, fmt: str = "%H:%M") -> str:
    return ts(value).astimezone(SGT).strftime(fmt)


def today_window(as_of: Any) -> tuple[str, str]:
    """Start and end of today in SGT, as UTC ISO strings for site_db queries."""
    day = ts(as_of).astimezone(SGT).date()
    start = datetime.combine(day, time.min, SGT).astimezone(timezone.utc)
    return start.isoformat(), (start + timedelta(days=1)).isoformat()


def board(db: Any = None, include_event_power: bool = False) -> dict[str, Any]:
    """Every asset with its state, reason and maintenance today; ordered problems first. OG boxes and their sockets live
    on the Event power tab, so the dashboard leaves them out; the asset page includes them."""
    db = _db(db)
    as_of = db.as_of()
    latest = db.latest_readings()
    start, end = today_window(as_of)
    work, impacts = db.work_orders(start, end), db.impacts(active_at=as_of)
    rows = []
    for asset in db.assets():
        if not asset.get("connected", 1):  # no readings, so no state: only the Asset schematic shows it
            continue
        if asset.get("asset_type") in EVENT_POWER_TYPES and not include_event_power:
            continue
        state = asset_state(asset, latest.get(asset["asset_id"], {}), as_of)
        rows.append({**asset, **state, "maintenance": maintenance_today(asset["asset_id"], work, impacts, as_of)})
    rows.sort(key=lambda row: (SEVERITY.index(row["state"]), row["asset_id"]))
    return {"as_of": as_of, "rows": rows, "zones": {zone["zone_code"]: zone for zone in db.zones()}}


def reason_for(row: dict[str, Any]) -> str:
    """A few words on a problem row. A permit isolation says so, which reads better than "not running"."""
    for item in row.get("maintenance") or []:
        effect = {"isolated": "Isolated", "down": "Off"}.get(str(item.get("effect")))
        if effect and row["state"] == "down":
            return f"{effect} under permit until {sgt(item['end_at'])}"
    return str(row.get("reason") or "")


def row_html(row: dict[str, Any], parent: bool = False) -> str:
    return site_theme.row_html(row.get("name") or row["asset_id"], row["state"], href=f"?asset={row['asset_id']}",
                               reason=reason_for(row) if row["state"] in site_theme.BANNER else "", cone=bool(row.get("maintenance")),
                               title=f"{row.get('name')} ({row['asset_id']}) · {LABEL.get(row['state'], '')}: {row.get('reason') or ''}",
                               parent=parent)


def problems_note(rows: list[dict[str, Any]]) -> str:
    return " · ".join(f"{count} {LABEL[state]}" for state in ("down", "warning", "offline")
                      if (count := sum(row["state"] == state for row in rows)))


def overview_html(data: dict[str, Any]) -> str:
    """The TV overview: report-style header and counts, then one column block per zone, problem zones and rows first.
    Healthy assets are a name and a small dot; problems are banners; a cone marks maintenance or a permit today."""
    rows = data["rows"]
    cards = site_theme.cards_html([(LABEL[state], sum(row["state"] == state for row in rows), site_theme.CARD_MARK[state])
                                   for state in ("down", "warning", "offline", "idle", "operational")])
    header = site_theme.header_html("Fleet operational status", sgt(data["as_of"], "%d %b %Y, %H:%M"), cards, site_theme.key_html())
    grouped: dict[str, list[dict]] = {}
    for row in rows:  # rows arrive problems first
        grouped.setdefault(row["zone_code"], []).append(row)
    order = sorted(grouped, key=lambda code: (min(SEVERITY.index(row["state"]) for row in grouped[code]),
                                              data["zones"].get(code, {}).get("name") or code))
    zones = "".join(site_theme.zone_html(data["zones"].get(code, {}).get("name") or code,
                                         "".join(row_html(row) for row in grouped[code]), problems_note(grouped[code]))
                    for code in order)
    return f'<div class="tv">{header}<div class="tv-zones" style="--col:15rem">{zones}</div></div>'


def render(db: Any = None) -> None:
    import streamlit as st

    st.markdown(site_theme.style() + overview_html(board(db)), unsafe_allow_html=True)


def _chart(rows: list[dict], point: str, title: str, unit: str):
    import pandas as pd
    import plotly.graph_objects as go

    from demo.chart_scale import calm_range

    frame = pd.DataFrame(rows)
    frame = frame[frame["point_id"].eq(point)].copy() if not frame.empty else frame
    fig = go.Figure()
    if not frame.empty:
        frame["at"] = pd.to_datetime(frame["observed_at"], utc=True).dt.tz_convert("Asia/Singapore")
        fig.add_trace(go.Scatter(x=frame["at"], y=frame["value"], mode="lines", line={"color": LINE, "width": 2},
                                 hovertemplate="%{x|%d %b %H:%M} SGT<br><b>%{y:.3g} " + unit + "</b><extra></extra>"))
        y_range = [0, 1.05] if point == "power_factor" else calm_range(frame["value"], unit)
        if y_range:
            fig.update_yaxes(range=y_range)
    fig.update_layout(height=250, margin={"l": 56, "r": 14, "t": 40, "b": 36}, paper_bgcolor=PAPER, plot_bgcolor=PLOT,
                      showlegend=False, font={"color": INK, "size": 14},
                      title={"text": f"{title}{f' ({unit})' if unit else ''}", "font": {"size": 18}, "x": .01})
    fig.update_xaxes(showgrid=False, linecolor=GRID, tickformat="%H:%M\n%d %b")
    fig.update_yaxes(gridcolor=GRID, zeroline=False, nticks=5)
    return fig


def render_asset_page(asset_id: str, db: Any = None) -> None:
    """Opened in a new tab from a box: state, why, maintenance, latest electrical readings and 24 h trends."""
    import streamlit as st

    db = _db(db)
    st.markdown(f"<style>{CSS}</style>", unsafe_allow_html=True)
    data = board(db, include_event_power=True)
    row = next((item for item in data["rows"] if item["asset_id"] == asset_id), None)
    if row is None:
        known = next((item for item in db.assets() if item["asset_id"] == asset_id), None)
        if known is not None:
            st.markdown(f'<div class="sa-head">{esc(known.get("name"))}</div>'
                        '<div class="sa-chips"><span class="sa-chip">Not connected: SignalDesk gets no readings from it</span></div>',
                        unsafe_allow_html=True)
        else:
            st.error(f"No asset {asset_id} in the site database.")
        return
    zone = data["zones"].get(row["zone_code"], {}).get("name") or row["zone_code"]
    chips = "".join(
        f'<span class="sa-chip"><span class="sa-cone">{CONE}</span>'
        f'{esc(item.get("wo_id") or item.get("ptw_id"))} · {esc(item.get("title") or item.get("summary"))}</span>'
        for item in row["maintenance"])
    st.markdown(f'<div class="sa-head" style="--c:{COLOUR[row["state"]]}"><i class="sa-dot"></i>{esc(row.get("name"))}</div>'
                f'<div class="sa-note">{esc(asset_id)} · {esc(zone)} · <b style="color:var(--gbb-ink)">{LABEL[row["state"]]}</b>: '
                f'{esc(row["reason"])}</div>' + (f'<div class="sa-chips">{chips}</div>' if chips else ""), unsafe_allow_html=True)
    latest = db.latest_readings().get(asset_id, {})
    tiles = "".join(f'<div class="sa-tile"><small>{name}</small><b>{number(latest[point]["value"])}</b><i>{unit}</i></div>'
                    for point, name, unit in POINTS if point in latest and latest[point].get("value") is not None)
    st.markdown(f'<div class="sa-tiles">{tiles}</div>', unsafe_allow_html=True)
    end = ts(data["as_of"])
    rows = db.readings(asset_id, (end - timedelta(hours=24)).isoformat(), end.isoformat())
    charts = [point for point in POINTS if point[0] != "energy_kwh"]
    for index in range(0, len(charts), 2):
        columns = st.columns(2)
        for column, (point, name, unit) in zip(columns, charts[index:index + 2]):
            with column:
                st.plotly_chart(_chart(rows, point, name, unit), width="stretch", config={"displayModeBar": False})
    st.markdown(f'<div class="sa-note">Synthetic electrical feed · last 24 h to {sgt(data["as_of"], "%d %b %H:%M")} SGT</div>',
                unsafe_allow_html=True)
