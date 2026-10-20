"""TV display variants for the IOC screens: one per screen, or four as a 2x2 video wall.

Each variant is a simplified, read-at-a-distance version of a page, not the operator page shrunk down: a few large
figures and short lists, no tables, no controls, nothing that needs scrolling. Sizes are in container units (cqh,
cqw), so a variant fills a whole 1920x1080 screen or one quadrant of the wall with the same proportions.

Addresses (bookmark one per screen):
- ``?display=<variant>&refresh=<seconds>&screen=<1-4>``: one variant, full screen, no navigation or editing controls.
- ``?wall=<v1>,<v2>,<v3>,<v4>&refresh=<seconds>``: four variants in a 2x2 grid (top-left, top-right, bottom-left,
  bottom-right), for a combined wall driven as one display.

Every figure comes from the module that owns it (site_overview.summary, ptw_real, the diagnostics replay); every panel
carries its data-source label. The app only renders these pages. It cannot switch, power or monitor physical TVs, and
nothing is stored on a server: a screen's configuration is its URL.
"""

from __future__ import annotations

import html
import json
from typing import Any

from demo import brand

VARIANTS = {
    "overview": "Site summary",
    "assets": "Asset operational state",
    "permits": "Permits to work today",
    "event-power": "Event power",
    "coming-up": "Coming up",
    "diagnostics": "Diagnostic findings",
}
DEFAULT_SCREENS = ("overview", "assets", "permits", "event-power")
REFRESH_CHOICES = (0, 30, 60, 120, 300, 600)  # seconds; 0 = no automatic refresh
RESOLUTIONS = {"1920x1080": (1920, 1080, "1920×1080 Full HD (16:9)"), "3840x2160": (3840, 2160, "3840×2160 4K UHD (16:9)"),
               "1366x768": (1366, 768, "1366×768 (16:9)")}  # layout target per screen; displays scale to the window


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def parse_wall(value: Any) -> list[str]:
    """Four known variant keys from a ``wall=`` value; unknown or missing quadrants fall back to the defaults."""
    keys = [part.strip() for part in str(value or "").split(",")]
    return [keys[i] if i < len(keys) and keys[i] in VARIANTS else DEFAULT_SCREENS[i] for i in range(4)]


def parse_refresh(value: Any) -> int:
    try:
        seconds = int(str(value))
    except ValueError:
        return 0
    return seconds if seconds in REFRESH_CHOICES else 0


def _time(value: Any, fmt: str = "%H:%M") -> str:
    from demo.asset_state import SGT, ts

    return ts(value).astimezone(SGT).strftime(fmt)


def _figs(items: list[tuple[Any, str]]) -> str:
    return '<div class="dp-figs">' + "".join(f'<div><b>{esc(n)}</b><span>{esc(w)}</span></div>' for n, w in items) + "</div>"


def _mark(state: str | None) -> str:
    if state is None:
        return brand.status_mark(brand.INK, "ring")
    colour, _, shape = brand.ASSET_STATE[state]
    return brand.status_mark(colour, shape)


def _list(rows: list[str], empty: str) -> str:
    return '<ul class="dp-list">' + "".join(rows) + "</ul>" if rows else f'<div class="dp-empty">{esc(empty)}</div>'


def overview(ctx: dict) -> tuple[str, str]:
    s = ctx["summary"]
    rows = [f'<li><span class="dp-w">{_mark(r["state"])}{esc(r["word"])}</span><span class="dp-t">{esc(r["what"])}'
            f'<small>{esc(r["where"])}{" · " + esc(r["why"]) if r["why"] else ""}</small></span></li>' for r in s["attention"][:5]]
    more = f'<div class="dp-more">+{len(s["attention"]) - 5} more</div>' if len(s["attention"]) > 5 else ""
    states = s["states"]
    figs = _figs([(states["down"] + states["warning"] + states["offline"], "assets Down, Warning or Offline"),
                  (s["permits"]["active"], "permits active now"),
                  (s["sockets"].get("down", 0) + s["sockets"].get("nosupply", 0), "event sockets tripped or without supply")])
    body = f'{figs}<div class="dp-sub">Needs attention now</div>{_list(rows, "Nothing needs attention.")}{more}'
    return body, navigation_source("site")


def assets(ctx: dict) -> tuple[str, str]:
    s = ctx["summary"]
    states = s["states"]
    order = ("down", "warning", "offline", "idle", "operational")
    tiles = '<div class="dp-states">' + "".join(
        f'<div class="dp-state"><b>{states[k]}</b><span>{_mark(k)}{esc(brand.ASSET_STATE[k][1])}</span></div>' for k in order) + "</div>"
    problems = [r for r in s["attention"] if r["kind"] == "Asset state"]
    rows = [f'<li class="dp-ban dp-{esc(r["state"])}"><span class="dp-w">{esc(r["word"])}</span><span class="dp-t">{esc(r["what"])}'
            f'<small>{esc(r["where"])}{" · " + esc(r["why"]) if r["why"] else ""}</small></span></li>' for r in problems[:6]]
    more = f'<div class="dp-more">+{len(problems) - 6} more on Fleet operational status</div>' if len(problems) > 6 else ""
    return tiles + _list(rows, "No asset is Down, in Warning or Offline.") + more, navigation_source("site")


def permits(ctx: dict) -> tuple[str, str]:
    real = ctx.get("real_permits")
    if real is None:
        p = ctx["summary"]["permits"]
        figs = _figs([(p["active"], "active now"), (p["later"], "start later today"),
                      (p["isolations"]["electrical"], "electrical isolations"), (p["isolations"]["physical"], "closures or restrictions")])
        where = ", ".join(p["zones"]) or "No permit is active now."
        return f'{figs}<div class="dp-sub">Active in</div><div class="dp-text">{esc(where)}</div>', navigation_source("site")
    points, counts = real["points"], real["counts"]
    figs = _figs([(counts["active"], "active now"), (counts["later"], "start later today"), (counts["unplaced"], "not placed on the map")])
    rows = [f'<li><span class="dp-n">{p["count"]}</span><span class="dp-t">{esc(" / ".join(p["names"]))}</span></li>' for p in points[:5]]
    body = (f'<div class="dp-split"><div class="dp-map" data-points="{esc(json.dumps(points, default=str))}"></div>'
            f'<div>{figs}<div class="dp-sub">Today by location</div>{_list(rows, "No permit today.")}'
            f'<div class="dp-note">Numbers are permit counts, not risk. Positions approximate.</div></div></div>')
    return body, brand.source_badge("imported").replace("Imported file", "Imported permit records · not live")


def event_power(ctx: dict) -> tuple[str, str]:
    s = ctx["summary"]
    sockets = s["sockets"]
    figs = _figs([(s["events_today"], "events booked on OG boxes"), (sockets.get("operational", 0), "sockets in use"),
                  (sockets.get("down", 0) + sockets.get("nosupply", 0), "sockets tripped or without supply"), (sockets.get("idle", 0), "sockets free")])
    problems = [r for r in s["attention"] if r["kind"] == "Event power"]
    rows = [f'<li><span class="dp-w">{_mark(r["state"])}{esc(r["word"])}</span><span class="dp-t">{esc(r["what"])}'
            f'<small>{esc(r["where"])} · {esc(r["why"])}</small></span></li>' for r in problems[:4]]
    return figs + _list(rows, "Every booked event has power."), navigation_source("site")


def coming_up(ctx: dict) -> tuple[str, str]:
    s = ctx["summary"]
    word = {"ptw": "Permit", "event": "Event", "maint": "Maintenance"}
    zones = s["zones"]
    rows = [f'<li><span class="dp-when">{esc(_time(item["start"], "%a %H:%M"))}</span><span class="dp-t">{esc(item.get("title") or item["label"])}'
            f'<small>{esc(word[item["kind"]])}{" · clash" if item["clash"] else ""} · '
            f'{esc((zones.get(item.get("zone")) or {}).get("name") or item.get("zone") or "")}</small></span></li>' for item in s["upcoming"][:6]]
    return _list(rows, "Nothing planned in the next 48 hours."), navigation_source("site")


def diagnostics(ctx: dict) -> tuple[str, str]:
    d = ctx["summary"].get("diagnostics")
    if d is None:
        return '<div class="dp-empty">The diagnostics replay is not loaded.</div>', navigation_source("replay")
    figs = _figs([(d["findings"], "detector findings to review"), (d["open_work_orders"], "work orders open or in progress"),
                  (d["quality_issues"], "data-quality issues")])
    rows = [f'<li><span class="dp-w">{_mark("down" if c["severity"] in ("critical", "high") else None)}{esc(c["severity"].title())}</span>'
            f'<span class="dp-t">{esc(c["title"])}<small>{esc(c["asset_id"])}</small></span></li>' for c in ctx.get("cases", [])[:4]]
    note = '<div class="dp-note">Replayed demonstration scenario with its own five assets; not site assets.</div>'
    return figs + _list(rows, "No detector finding in this replay.") + note, navigation_source("replay")


BUILDERS = {"overview": overview, "assets": assets, "permits": permits, "event-power": event_power,
            "coming-up": coming_up, "diagnostics": diagnostics}


def navigation_source(kind: str) -> str:
    from demo.navigation import SOURCE_LABEL

    return brand.demo_badge(SOURCE_LABEL[kind])


def panel(key: str, ctx: dict) -> str:
    try:
        body, source = BUILDERS[key](ctx)
    except Exception as exc:  # one failing panel never blanks the whole wall
        body, source = f'<div class="dp-empty">This panel could not be drawn: {esc(type(exc).__name__)}</div>', ""
    return (f'<section class="dp" data-variant="{esc(key)}"><header class="dp-h"><h1>{esc(VARIANTS[key])}</h1>{source}</header>'
            f'<div class="dp-b">{body}</div></section>')


CSS = """
*{box-sizing:border-box}
html,body{margin:0;height:100%;background:#fff;color:%INK%;font-family:%FONT%;overflow:hidden}
.wall{display:grid;height:100vh;width:100vw;gap:0}
.wall.one{grid-template:1fr/1fr}
.wall.four{grid-template:1fr 1fr/1fr 1fr}
.dp{container-type:size;position:relative;overflow:hidden;padding:4cqh 3.2cqw 7cqh;border:0 solid %LINE%}
.wall.four .dp:nth-child(1),.wall.four .dp:nth-child(2){border-bottom-width:2px}
.wall.four .dp:nth-child(1),.wall.four .dp:nth-child(3){border-right-width:2px}
.dp-h{display:flex;align-items:center;justify-content:space-between;gap:2cqw;margin:0 0 3cqh;padding:0 0 1.6cqh;border-bottom:.5cqh solid %INK%}
.dp-h h1{margin:0;font-size:6.2cqh;font-weight:800;letter-spacing:-.02em;line-height:1.05}
.dp-h .gbb-demo,.dp-h .gbb-source{font-size:2.3cqh;padding:.4cqh 1cqw;border-width:.25cqh}
.dp-figs{display:flex;gap:3cqw;margin:0 0 3cqh}
.dp-figs div{flex:1}
.dp-figs b{display:block;font-size:13cqh;font-weight:800;line-height:1;font-variant-numeric:tabular-nums}
.dp-figs span{display:block;font-size:3cqh;line-height:1.2;color:%INK2%;margin-top:.8cqh}
.dp-sub{font-size:2.8cqh;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:%INK3%;margin:0 0 1cqh}
.dp-text{font-size:4cqh;line-height:1.3}
.dp-list{list-style:none;margin:0;padding:0}
.dp-list li{display:flex;align-items:baseline;gap:2cqw;padding:1.3cqh 0;border-bottom:1px solid %LINE%;font-size:3.8cqh;line-height:1.15}
.dp-w{flex:none;width:20cqw;display:inline-flex;align-items:center;gap:1cqw;font-weight:800}
.dp-w .gbb-mark{width:2.6cqh;height:2.6cqh}
.dp-t{min-width:0;font-weight:650;overflow:hidden;text-overflow:ellipsis}
.dp-t small{display:block;font-weight:500;font-size:2.7cqh;color:%INK2%;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.dp-n{flex:none;width:7cqw;font-size:5cqh;font-weight:800;text-align:right;font-variant-numeric:tabular-nums}
.dp-when{flex:none;width:16cqw;font-weight:800;font-variant-numeric:tabular-nums}
.dp-ban{padding:1.3cqh 1.5cqw !important;margin:0 0 .8cqh;border:none !important;color:#fff}
.dp-ban small{color:inherit;opacity:.92}
.dp-down{background:%DOWN%}.dp-warning{background:#F59E0B;color:%INK%}.dp-offline{background:#9CA3AF;color:%INK%}
.dp-states{display:grid;grid-template-columns:repeat(5,1fr);gap:1.4cqw;margin:0 0 3cqh}
.dp-state b{display:block;font-size:11cqh;font-weight:800;line-height:1;font-variant-numeric:tabular-nums}
.dp-state span{display:flex;align-items:center;gap:.8cqw;font-size:3cqh;color:%INK2%;margin-top:.8cqh}
.dp-state .gbb-mark{width:2.4cqh;height:2.4cqh}
.dp-split{display:grid;grid-template-columns:1.3fr 1fr;gap:3cqw;height:78cqh}
.dp-split .dp-figs b{font-size:10cqh}
.dp-map{height:100%;border:1px solid %LINE%;border-radius:6px}
.dp-empty{font-size:4.2cqh;color:%INK2%;padding:3cqh 0}
.dp-more,.dp-note{font-size:2.6cqh;color:%INK3%;margin-top:1.5cqh}
.dp-foot{position:absolute;left:3.2cqw;right:3.2cqw;bottom:2.2cqh;display:flex;justify-content:space-between;font-size:2.4cqh;color:%INK3%}
.gbb-demo{display:inline-flex;align-items:center;border:1.5px dashed %INK2%;border-radius:.35em;color:%INK2%;font-weight:700;letter-spacing:.06em;text-transform:uppercase;white-space:nowrap}
.gbb-source{display:inline-flex;align-items:center;border:1.5px var(--b) %INK3%;border-radius:.35em;color:%INK2%;font-weight:650;white-space:nowrap}
.gbb-mark{display:inline-block;flex:none;vertical-align:middle}
.pt{display:grid;place-items:center;border-radius:50%;background:%GREY%;color:#fff;font-weight:700;border:2px dashed #fff;box-shadow:0 1px 4px rgba(36,39,42,.4)}
"""

MAP_JS = """
if (window.L) document.querySelectorAll('.dp-map').forEach(el => {
  const pts = JSON.parse(el.dataset.points || '[]');
  const map = L.map(el, {zoomControl: false, attributionControl: true, dragging: false, scrollWheelZoom: false, doubleClickZoom: false});
  L.tileLayer('%TILES%', {maxZoom: 19, attribution: '&copy; OpenStreetMap contributors'}).addTo(map);
  pts.forEach(p => { const s = Math.round(26 + 6 * Math.sqrt(p.count));
    L.marker([p.lat, p.lon], {icon: L.divIcon({className: '', iconSize: [s, s], html: `<div class="pt" style="width:${s}px;height:${s}px">${p.count}</div>`})}).addTo(map); });
  map.fitBounds(pts.length ? L.latLngBounds(pts.map(p => [p.lat, p.lon])).pad(.3) : %FALLBACK%, {maxZoom: 17});
});
"""


def document(keys: list[str], ctx: dict, refresh: int = 0) -> str:
    """A complete page for one screen (one key) or the 2x2 wall (four keys)."""
    from demo.ptw_dashboard import BAY_SOUTH, LEAFLET, TILES

    css = CSS
    for token, value in {"%INK%": brand.INK, "%INK2%": brand.INK_2, "%INK3%": brand.INK_3, "%LINE%": brand.LINE,
                         "%FONT%": brand.FONT, "%GREY%": brand.GREY, "%DOWN%": brand.ASSET_STATE["down"][0]}.items():
        css = css.replace(token, value)
    as_of = _time(ctx["summary"]["as_of"], "%d %b %H:%M")
    foot = (f'<div class="dp-foot"><span>Gardens by the Bay · Facilities IOC</span><span>Site data {esc(as_of)} SGT'
            + (f" · refreshes every {refresh} s" if refresh else "") + ' · <span class="clock"></span></span></div>')
    panels = "".join(panel(key, ctx).replace("</section>", foot + "</section>") for key in keys)
    uses_map = 'class="dp-map"' in panels
    head = f'<link rel="stylesheet" href="{LEAFLET}.css">' if uses_map else ""
    script = (f'<script src="{LEAFLET}.js"></script><script>{MAP_JS.replace("%TILES%", TILES[0]).replace("%FALLBACK%", json.dumps(BAY_SOUTH))}</script>'
              if uses_map else "")
    clock = ("<script>const tick=()=>document.querySelectorAll('.clock').forEach(e=>e.textContent=new Date().toLocaleTimeString('en-SG',"
             "{timeZone:'Asia/Singapore',hour:'2-digit',minute:'2-digit'})+' SGT now');tick();setInterval(tick,15000);</script>")
    return (f'<!doctype html><html><head><meta charset="utf-8">{head}<style>{css}</style></head><body>'
            f'<div class="wall {"one" if len(keys) == 1 else "four"}">{panels}</div>{script}{clock}</body></html>')
