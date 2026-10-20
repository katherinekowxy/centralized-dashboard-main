"""Site look for the 55-inch TV: GBTB's report colours on white, big type, colour only where something needs attention.

Dan, 13 October 2026, approving the redesign: the screen is "55 inch tv", the colour scheme is GBTB's Aging Faults
report (plum on white, sampled: plum #420C52, mid purple #663B73, cyan #7DD0E4 for charts), "healthy assets one
small green dot in the corner", "idle also one blue dot", "keep the maintainence cones", "for warning and faulty,
red banner is fine" (Warning keeps its amber so the two stay apart), "reduce the number of boxes but make sure the
assets are segregated properly". Zones are separated by a plum header bar and white space, not by borders.

Status colours are Dan's (asset_state.COLOUR), deepened only where white needs it: the green dot is #16A34A (#22C55E
is 2.3:1 on white, below the 3:1 a small graphic needs) and the red banner #DC2626 (white text 4.8:1). Amber and grey
banners carry dark text. Pilot: the Asset dashboard and Asset schematic; the other tabs follow once Dan approves.
"""

from __future__ import annotations

import html
from typing import Any

PLUM, PLUM_2, LILAC, CYAN = "#420C52", "#663B73", "#E3DBE5", "#7DD0E4"
INK, INK_2, LINE, ZEBRA = "#1A1A1A", "#4A4A4A", "#D9D4DB", "#F3F2F3"
DOT = {"operational": "#16A34A", "idle": "#2563EB"}
BANNER = {"down": ("#DC2626", "#FFFFFF", "Down"), "warning": ("#F59E0B", "#1A1A1A", "Warning"),
          "offline": ("#9CA3AF", "#1A1A1A", "Offline")}
NO_SUPPLY = "nosupply"
CARD_MARK = {"down": "#EF4444", "warning": "#F59E0B", "offline": "#9CA3AF", "idle": "#60A5FA", "operational": "#4ADE80"}

CONE = ('<svg class="tv-cone" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="11.2" fill="#fff" stroke="#334155" stroke-width="1.4"/>'
        '<path d="M10.6 4.6h2.8l3.9 12.6H6.7z" fill="#334155"/><path d="M9.7 8.1h4.6l.75 2.4H8.95zM8.4 12.3h7.2l.75 2.4H7.65z" fill="#fff"/>'
        '<rect x="5" y="17.2" width="14" height="2.2" rx=".8" fill="#334155"/></svg>')

CSS = f"""
html {{font-size:20px}}  /* a 55-inch TV seen from 2-3 m: nothing on these pages is smaller than 20 px */
.stApp, [data-testid="stHeader"], [data-testid="stMain"] {{background:#FFFFFF !important}}
.sd-head {{display:none}}  /* the page draws a report-style header instead */
.block-container {{padding-top:1.4rem !important}}
.tv {{color:{INK};font-family:"Segoe UI",system-ui,-apple-system,"Helvetica Neue",Arial,sans-serif}}
.tv-top {{display:flex;flex-wrap:wrap;align-items:flex-end;justify-content:space-between;gap:.8rem 2rem;margin:0 0 .5rem}}
.tv-brand {{font-size:1rem;font-weight:700;color:{PLUM};letter-spacing:.02em}}
.tv-title {{font-size:2.4rem;font-weight:800;line-height:1.05;color:{INK};padding-bottom:.25rem;border-bottom:3px solid {LINE}}}
.tv-updated {{font-size:1rem;color:{INK_2};margin-top:.35rem}}
.tv-meta {{font-size:1rem;color:{INK_2};margin:0 0 1rem;display:flex;flex-wrap:wrap;align-items:center;gap:.3rem 1.3rem}}
.tv-meta span {{display:inline-flex;align-items:center;gap:.35rem}}
.tv-key {{display:inline-block;width:1.1rem;height:.75rem;background:var(--b)}}
.tv-cards {{display:flex;flex-wrap:wrap;gap:.6rem;margin-left:auto}}
.tv-card {{min-width:6.8rem;padding:.4rem .9rem .45rem;background:{PLUM};color:#fff}}
.tv-card small {{display:flex;align-items:center;gap:.4rem;font-size:1rem;color:{LILAC};white-space:nowrap}}
.tv-card small i {{display:inline-block;width:.75rem;height:.75rem;border-radius:50%;background:var(--m)}}
.tv-card b {{display:block;font-size:2.2rem;font-weight:700;line-height:1.1;font-variant-numeric:tabular-nums}}
.tv-zones {{column-width:var(--col,15rem);column-gap:1.4rem}}
.tv-zone {{display:inline-block;width:100%;break-inside:avoid;margin:0 0 1.2rem}}
.tv-zh {{display:flex;align-items:center;justify-content:space-between;gap:.6rem;padding:.35rem .7rem;background:{PLUM};color:#fff;
  font-size:1.2rem;font-weight:700;line-height:1.25}}
.tv-zh em {{flex:none;font-style:normal;font-size:1rem;font-weight:700;color:{LILAC}}}
.tv-row {{position:relative;display:flex;align-items:center;justify-content:space-between;gap:.5rem;min-height:2.1rem;padding:.2rem .7rem;
  border-bottom:1px solid {LINE};font-size:1.15rem;line-height:1.2;color:{INK} !important;text-decoration:none !important}}
.tv-list > .tv-row:nth-of-type(even) {{background:{ZEBRA}}}
.tv-row:hover {{background:{LILAC} !important}}
.tv-name {{min-width:0;word-break:normal;overflow-wrap:normal}}
.tv-end {{display:inline-flex;align-items:center;gap:.4rem;flex:none}}
.tv-dot {{display:inline-block;width:.7rem;height:.7rem;border-radius:50%;background:var(--d)}}
.tv-ban {{background:var(--b) !important;color:var(--t) !important;font-weight:700;border-bottom-color:#fff}}
.tv-ban .tv-name b {{margin-right:.5rem;font-weight:800;letter-spacing:.03em;text-transform:uppercase}}
.tv-ban .tv-name small {{display:block;font-size:1.05rem;font-weight:600;opacity:.95}}
.tv-ban.tv-nosupply {{background:#FFFFFF !important;color:#B91C1C !important;box-shadow:inset .45rem 0 0 #DC2626;padding-left:1.05rem}}
.tv-parent {{font-size:1.25rem;font-weight:700}}
.tv-nc {{font-size:1rem;font-weight:600;color:{INK_2}}}
.tv-feeds {{margin:0 0 0 1rem;padding:0 0 0 .55rem;border-left:3px solid #B9B2BD}}
.tv-feeds.tv-dead {{border-left:3px dashed #DC2626}}
.tv-branch + .tv-branch, .tv-branch + .tv-row, .tv-row + .tv-branch {{margin-top:.5rem}}
.tv-cone {{width:1.5rem;height:1.5rem;flex:none;animation:tv-pulse 1.8s ease-in-out infinite}}
@keyframes tv-pulse {{0%,100% {{transform:scale(1)}} 50% {{transform:scale(1.14)}}}}
.tv-note {{display:inline-flex;align-items:center;gap:.5rem;font-size:1.15rem;font-weight:600;color:{INK};margin:.3rem 0 0}}
.tv-clear {{padding:2.5rem 1rem;text-align:center;font-size:2.4rem;font-weight:800;color:{INK}}}
.tv-clear small {{display:block;margin-top:.6rem;font-size:1.1rem;font-weight:600;color:{INK_2}}}
@media (prefers-reduced-motion: reduce) {{.tv-cone {{animation:none}}}}
@media (max-width: 640px) {{.tv-zones {{columns:1}} .tv-cards {{margin-left:0}}}}
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


def header_html(title: str, updated: str, cards: str, key: str = "") -> str:
    """Title and data time on the left and count cards on the right, as in GBTB's reports; the key on a line below."""
    return (f'<div class="tv-top"><div><div class="tv-brand">SignalDesk · Bay South</div><div class="tv-title">{esc(title)}</div>'
            f'<div class="tv-updated">Data updated {esc(updated)} SGT · synthetic</div></div>{cards}</div>'
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
