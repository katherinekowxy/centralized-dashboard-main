"""Shared page parts in one style: page head, KPI cards, panels, rows, status pills and the logo.

Pages build their HTML from these instead of their own CSS, so type sizes, spacing and colours match everywhere
(sizes come from brand.TYPE). Words are kept short: a figure, a label and at most one line of context.
"""

from __future__ import annotations

import base64
import html
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

from demo import brand

LOGO = Path(__file__).resolve().parents[1] / "assets" / "brand" / "gbb-logo.png"
PILL = {  # tinted background, text colour: statuses keep a word as well as a colour
    "ok": ("#E3F4E8", "#15803D"), "warn": ("#FFF1D1", "#9A6200"), "fault": ("#FBE5E5", "#B42D2D"),
    "off": ("#ECEEF0", "#55595C"), "info": ("#E3ECF8", "#1F5FAD"), "neutral": ("#ECEEF0", "#24272A"),
}
STATE_PILL = {"operational": "ok", "idle": "info", "warning": "warn", "down": "fault", "offline": "off"}


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value))


@lru_cache(maxsize=1)
def logo_data_uri() -> str:
    return "data:image/png;base64," + base64.b64encode(LOGO.read_bytes()).decode() if LOGO.is_file() else ""


def logo(height: int = 44) -> str:
    uri = logo_data_uri()
    return (f'<img src="{uri}" alt="Gardens by the Bay" style="height:{height}px;width:auto;display:block">' if uri
            else '<b style="font-size:16px">Gardens by the Bay</b>')


def pill(kind: str, word: str, mark: str = "") -> str:
    bg, fg = PILL.get(kind, PILL["neutral"])
    return f'<span class="u-pill" style="--bg:{bg};--fg:{fg}">{mark}{esc(word)}</span>'


def state_pill(state: str) -> str:
    colour, word, shape = brand.ASSET_STATE[state]
    return pill(STATE_PILL[state], word, brand.status_mark(colour, shape))


def head(title: str, sub: str = "", tags: Iterable[str] = ()) -> str:
    return (f'<div class="u-head"><div><h1>{esc(title)}</h1>{f"<div class=u-sub>{esc(sub)}</div>" if sub else ""}</div>'
            f'<div class="u-tags">{"".join(tags)}</div></div>')


def kpis(cards: Iterable[dict]) -> str:
    """Cards of {label, value, caption, dot (colour or None), href (or None), tag (html or "")}."""
    out = []
    for card in cards:
        dot = f'<i class="u-dot" style="background:{card["dot"]}"></i>' if card.get("dot") else card.get("tag", "")
        tag = "a" if card.get("href") else "div"
        link = f' href="{esc(card["href"])}" target="_self"' if card.get("href") else ""
        out.append(f'<{tag} class="u-kpi"{link}><div class="u-kpi-top"><span>{esc(card["label"])}</span>{dot}</div>'
                   f'<b>{esc(card["value"])}</b><small>{esc(card.get("caption", ""))}</small></{tag}>')
    return '<div class="u-kpis">' + "".join(out) + "</div>"


def panel(title: str, body: str, note: str = "", link: tuple[str, str] | None = None) -> str:
    right = f'<a href="{esc(link[1])}" target="_self">{esc(link[0])} →</a>' if link else (f"<small>{esc(note)}</small>" if note else "")
    return f'<section class="u-panel"><div class="u-panel-h"><span>{esc(title)}</span>{right}</div>{body}</section>'


def grid(panels: Iterable[str], columns: str = "1fr 1fr 1fr") -> str:
    return f'<div class="u-grid" style="grid-template-columns:{columns}">{"".join(panels)}</div>'


def rows(items: Iterable[dict], empty: str = "Nothing to show.") -> str:
    """Rows of {main, sub, left (html), right (html), href}."""
    items = list(items)
    if not items:
        return f'<div class="u-empty">{esc(empty)}</div>'
    out = []
    for item in items:
        main = esc(item["main"])
        if item.get("href"):
            main = f'<a href="{esc(item["href"])}" target="_blank" style="color:inherit;text-decoration:none">{main}</a>'
        sub = f'<small>{esc(item["sub"])}</small>' if item.get("sub") else ""
        out.append(f'<li>{item.get("left", "")}<span class="u-main"><b>{main}</b>{sub}</span>{item.get("right", "")}</li>')
    return '<ul class="u-rows">' + "".join(out) + "</ul>"


def date_cell(text: str) -> str:
    return f'<span class="u-date">{esc(text)}</span>'


def bar(parts: Iterable[tuple[int, str, str]]) -> str:
    """Stacked bar of (count, colour, label)."""
    parts = [part for part in parts if part[0]]
    total = sum(part[0] for part in parts) or 1
    return '<div class="u-bar" role="img">' + "".join(
        f'<i style="width:{n / total * 100:.2f}%;background:{c}" title="{esc(label)}: {n}"></i>' for n, c, label in parts) + "</div>"
