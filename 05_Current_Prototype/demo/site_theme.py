"""Site look for the 55-inch TV: Gardens by the Bay grey and pink on white, big type, colour only where something
needs attention.

Dan, 13 October 2026, approving the redesign: the screen is "55 inch tv", "healthy assets one small green dot in the
corner", "idle also one blue dot", "keep the maintainence cones", "for warning and faulty, red banner is fine"
(Warning keeps its amber so the two stay apart), "reduce the number of boxes but make sure the assets are segregated
properly". Zones are separated by a header bar and white space, not by borders.

20 October 2026: the interim plum palette (from the Aging Faults report) is replaced by the brand tokens in
demo/brand.py. Header bars are brand grey with white text (7.1:1); pink is reserved for identity, never status.

Status colours are Dan's (asset_state.COLOUR), deepened only where white needs it (brand.ASSET_STATE): the green dot
is #15803D and the red banner #B91C1C (white text 6.5:1). Amber and grey banners carry dark text.
"""

from __future__ import annotations

import html
from typing import Any

from demo import brand

PLUM, PLUM_2, LILAC = brand.GREY, brand.INK_2, "#E4E6E8"  # names kept for callers: header bar, its text tint
INK, INK_2, LINE, ZEBRA = brand.INK, brand.INK_2, brand.LINE, brand.SURFACE_2
DOT = {"operational": brand.ASSET_STATE["operational"][0], "idle": brand.ASSET_STATE["idle"][0]}
BANNER = {"down": (brand.ASSET_STATE["down"][0], "#FFFFFF", "Down"), "warning": ("#F59E0B", brand.INK, "Warning"),
          "offline": ("#9CA3AF", brand.INK, "Offline")}
NO_SUPPLY = "nosupply"
CARD_MARK = {"down": "#EF4444", "warning": "#F59E0B", "offline": "#9CA3AF", "idle": "#60A5FA", "operational": "#4ADE80"}

CONE = ('<svg class="tv-cone" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="11.2" fill="#fff" stroke="#334155" stroke-width="1.4"/>'
        '<path d="M10.6 4.6h2.8l3.9 12.6H6.7z" fill="#334155"/><path d="M9.7 8.1h4.6l.75 2.4H8.95zM8.4 12.3h7.2l.75 2.4H7.65z" fill="#fff"/>'
        '<rect x="5" y="17.2" width="14" height="2.2" rx=".8" fill="#334155"/></svg>')

CSS = f"""
.sd-head {{display:none}}
.tv {{color:{INK};font-family:var(--gbb-font)}}
.tv-top {{margin:0 0 12px}}
.tv-brand {{font-size:13px;font-weight:700;color:{brand.PINK_DARK};letter-spacing:.02em}}
.tv-title {{font-size:var(--t-title);font-weight:700;line-height:1.15;color:{INK}}}
.tv-updated {{font-size:var(--t-caption);color:var(--gbb-ink-3);margin:2px 0 10px}}
.tv-meta {{font-size:var(--t-small);color:{INK_2};margin:0 0 14px;display:flex;flex-wrap:wrap;align-items:center;gap:6px 18px}}
.tv-meta span {{display:inline-flex;align-items:center;gap:6px}}
.tv-key {{display:inline-block;width:14px;height:10px;border-radius:2px;background:var(--b)}}
.tv-cards {{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:12px}}
.tv-card {{background:var(--gbb-surface);border:1px solid var(--gbb-line);border-radius:var(--gbb-radius);box-shadow:var(--gbb-shadow);padding:12px 14px}}
.tv-card small {{display:flex;align-items:center;gap:6px;font-size:var(--t-small);font-weight:600;color:var(--gbb-ink-2);white-space:nowrap}}
.tv-card small i {{display:inline-block;width:9px;height:9px;border-radius:50%;background:var(--m)}}
.tv-card b {{display:block;font-size:var(--t-figure);font-weight:700;line-height:1.1;margin-top:4px;font-variant-numeric:tabular-nums}}
.tv-zones {{column-width:var(--col,17rem);column-gap:14px}}
.tv-zone {{display:inline-block;width:100%;break-inside:avoid;margin:0 0 14px;background:var(--gbb-surface);border:1px solid var(--gbb-line);
  border-radius:var(--gbb-radius);box-shadow:var(--gbb-shadow);overflow:hidden}}
.tv-zh {{display:flex;align-items:center;justify-content:space-between;gap:8px;padding:9px 12px;background:var(--gbb-surface-2);color:{INK};
  font-size:var(--t-body);font-weight:700;border-bottom:1px solid var(--gbb-line)}}
.tv-zh em {{flex:none;font-style:normal;font-size:var(--t-caption);font-weight:700;color:var(--gbb-ink-3)}}
.tv-row {{position:relative;display:flex;align-items:center;justify-content:space-between;gap:8px;min-height:34px;padding:6px 12px;
  border-top:1px solid {LINE};font-size:var(--t-body);line-height:1.3;color:{INK} !important;text-decoration:none !important}}
.tv-list > .tv-row:first-child {{border-top:none}}
.tv-row:hover {{background:var(--gbb-surface-2) !important}}
.tv-name {{min-width:0}}
.tv-end {{display:inline-flex;align-items:center;gap:6px;flex:none}}
.tv-dot {{display:inline-block;width:9px;height:9px;border-radius:50%;background:var(--d)}}
.tv-ban {{background:var(--b) !important;color:var(--t) !important;font-weight:600;border-top-color:transparent}}
.tv-ban .tv-name b {{margin-right:6px;font-size:var(--t-caption);font-weight:800;letter-spacing:.04em;text-transform:uppercase}}
.tv-ban .tv-name small {{display:block;font-size:var(--t-caption);font-weight:500;opacity:.95}}
.tv-ban.tv-nosupply {{background:#FFFFFF !important;color:#B91C1C !important;box-shadow:inset 4px 0 0 #DC2626;padding-left:16px}}
.tv-parent {{font-weight:700}}
.tv-nc {{font-size:var(--t-caption);font-weight:600;color:var(--gbb-ink-3)}}
.tv-feeds {{margin:0 0 0 12px;padding:0 0 0 8px;border-left:2px solid {brand.LINE_STRONG}}}
.tv-feeds.tv-dead {{border-left:2px dashed #DC2626}}
.tv-branch + .tv-branch, .tv-branch + .tv-row, .tv-row + .tv-branch {{margin-top:6px}}
.tv-cone {{width:20px;height:20px;flex:none}}
.tv-note {{display:inline-flex;align-items:center;gap:6px;font-size:var(--t-small);color:var(--gbb-ink-2);margin:4px 0 0}}
.tv-clear {{padding:28px 12px;text-align:center;font-size:var(--t-subhead);font-weight:700;color:{INK}}}
.tv-clear small {{display:block;margin-top:6px;font-size:var(--t-small);font-weight:500;color:var(--gbb-ink-3)}}
@media (max-width: 640px) {{.tv-zones {{columns:1}}}}
"""


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def style() -> str:
    return f"<style>{CSS}</style>"


def _mark(colour: str | None) -> str:
    return f'<i style="--m:{colour}"></i>' if colour else ""


def cards_html(cards: list[tuple[str, int, str | None]]) -> str:
    """Report-style count cards: (label, number, status colour of the small mark or None)."""
    return '<div class="tv-cards">' + "".join(
        f'<div class="tv-card"><small>{_mark(mark)}{esc(label)}</small><b>{value}</b></div>'
        for label, value, mark in cards) + "</div>"


def header_html(title: str, updated: str, cards: str, key: str = "", brand_line: bool = False) -> str:
    """Title and data time on the left and count cards on the right, as in GBTB's reports; the key on a line below.
    ``brand_line`` adds the site name above the title, for screens that show no navigation (wall displays)."""
    brand_html = '<div class="tv-brand">Gardens by the Bay · Facilities IOC</div>' if brand_line else ""
    return (f'<div class="tv-top"><div>{brand_html}{f"<div class=tv-title>{esc(title)}</div>" if title else ""}'
            f'<div class="tv-updated">Updated {esc(updated)} SGT · demo data</div></div>{cards}</div>'
            + (f'<div class="tv-meta">{key}</div>' if key else ""))


def key_html(states: tuple[str, ...] = ("operational", "idle", "down", "warning", "offline"), cone: bool = True,
             no_supply: bool = False) -> str:
    """The key, in the order the eye meets things: dots, then banners, then the cone."""
    parts = []
    for state in states:
        if state in DOT:
            parts.append(f'<span><i class="tv-dot" style="--d:{DOT[state]}"></i>{"Running" if state == "operational" else "Idle"}</span>')
        else:
            parts.append(f'<span><i class="tv-key" style="--b:{BANNER[state][0]}"></i>{BANNER[state][2]}</span>')
    if no_supply:
        parts.append('<span><i class="tv-key" style="--b:#fff;box-shadow:inset .3rem 0 0 #DC2626;outline:1px solid #DC2626"></i>No supply</span>')
    if cone:
        parts.append(f"<span>{CONE}Maintenance or permit today</span>")
    return "".join(parts)


def row_html(name: str, state: str, href: str | None = None, reason: str = "", cone: bool = False, title: str = "",
             parent: bool = False) -> str:
    """One asset as a list row. Healthy: the name and a small dot in the corner. Down, Warning, Offline and No supply:
    a full-width banner with the state word and the reason. Not connected: the name and those words, quietly. A cone at
    the end while it has maintenance or a permit. ``parent`` sets a DB's row a little heavier than the devices under it."""
    end = CONE if cone else ""
    tag, link = ("a", f' href="{esc(href)}" target="_blank"') if href else ("div", "")
    heavy = " tv-parent" if parent else ""
    if state in DOT or state == "unconnected":
        mark = f'<i class="tv-dot" style="--d:{DOT[state]}"></i>' if state in DOT else '<span class="tv-nc">Not connected</span>'
        return (f'<{tag} class="tv-row{heavy}"{link} title="{esc(title)}"><span class="tv-name">{esc(name)}</span>'
                f'<span class="tv-end">{end}{mark}</span></{tag}>')
    if state == NO_SUPPLY:
        colours, word, extra = ("#FFFFFF", "#B91C1C"), "No supply", " tv-nosupply"
    else:
        colours, word, extra = BANNER[state][:2], BANNER[state][2], ""
    detail = f"<small>{esc(reason)}</small>" if reason else ""
    return (f'<{tag} class="tv-row tv-ban{extra}{heavy}" style="--b:{colours[0]};--t:{colours[1]}"{link} title="{esc(title)}">'
            f'<span class="tv-name"><b>{word}</b>{esc(name)}{detail}</span><span class="tv-end">{end}</span></{tag}>')


def zone_html(name: str, rows: str, note: str = "") -> str:
    return (f'<div class="tv-zone"><div class="tv-zh"><span>{esc(name)}</span>{f"<em>{esc(note)}</em>" if note else ""}</div>'
            f'<div class="tv-list">{rows}</div></div>')
