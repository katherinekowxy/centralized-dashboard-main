"""One visual language for every page: Gardens by the Bay colours, type, spacing and status vocabularies.

Brand colours (20 October 2026): sampled from the official logo file supplied by the client and confirmed by the
project lead as the brand pink and grey. White is the brand background. No other brand colour has been supplied, so
everything else here is a neutral UI colour derived from the brand grey, or a status colour with a fixed meaning.

Rules
- Pink is identity, never status: the header rule, the selected navigation item, primary buttons, focus and selection.
  A pink element never means "fault"; problem states use their own colour, a word and a shape.
- Each concept keeps its own vocabulary (below). Operational asset state, diagnostic findings, work-order status, PTW
  status and data-source status are never collapsed into one red/amber/green scale.
- Colour is never the only signal: every status has a word, and states that share a hue family differ in shape.
- Text colours meet WCAG AA (4.5:1) on white; status marks meet 3:1 (tests/test_brand.py checks the numbers).
- The brand typeface has not been supplied, so pages use the operating system's UI font. Swap ``FONT`` when it is.
"""

from __future__ import annotations

from typing import Any

# Brand (sampled from the supplied logo; confirmed 20 October 2026)
PINK, GREY, WHITE = "#E2124F", "#55595C", "#FFFFFF"

# Neutral UI colours derived from the brand grey: not brand colours in their own right
INK = "#24272A"        # headings and primary text (15.0:1 on white)
INK_2 = GREY           # secondary text (7.0:1)
INK_3 = "#686C70"      # captions and axis labels (5.3:1)
LINE = "#DCDEE0"       # hairlines and card borders
LINE_STRONG = "#B9BDC0"
SURFACE = WHITE
SURFACE_2 = "#F5F6F7"  # quiet panels and table zebra
SURFACE_3 = "#ECEEF0"  # tracks and empty bars
PINK_DARK = "#B80E40"  # pink text on white (6.6:1) or on the pink tint (5.6:1)
PINK_TINT = "#FCE8EE"  # selected background
LINK = "#1F5FAD"

FONT = '"Segoe UI", system-ui, -apple-system, "Helvetica Neue", Arial, sans-serif'
MONO_NUMBERS = "font-variant-numeric:tabular-nums"

# Status vocabularies: (colour, word, shape). Shapes are drawn by ``status_mark``.
ASSET_STATE = {  # operational state of a site asset (demo/asset_state.py)
    "operational": ("#15803D", "Operational", "dot"),
    "idle": ("#2563EB", "Idle", "ring"),
    "warning": ("#B45309", "Warning", "triangle"),
    "down": ("#B91C1C", "Down", "square"),
    "offline": ("#6B7280", "Offline", "dash"),
}
DIAGNOSTIC = {  # rule-based detector findings in the diagnostics workbench (demo/signals.py)
    "alert": ("#B91C1C", "Detector finding", "dot"),
    "ok": ("#0F766E", "Checked, no finding", "dot"),
    "idle": ("#8A8F93", "Not assessed or no data", "ring"),
}
WORK_ORDER = {  # CMMS work-order status: neutral on purpose, it is a workflow state, not a health verdict
    "open": (INK, "Open", "ring"),
    "in_progress": ("#2563EB", "In progress", "half"),
    "closed": ("#8A8F93", "Closed", "dot"),
}
PTW_TIMING = {  # permit to work: when it applies, never how risky it is
    "active": (INK, "Active now", "dot"),
    "later": (INK_2, "Later today", "ring"),
    "ended": (INK_3, "Ended", "dash"),
}
PTW_APPROVAL = {  # the approver's decision on the permit form; a separate question from timing
    "approved": (INK, "Approved", "square"),
    "pending": (INK_2, "No decision recorded", "half"),
    "rejected": (INK_3, "Rejected", "dash"),
}
DATA_SOURCE = {  # where a number comes from; drawn as a border style plus a word, never as a status colour
    "live": ("solid", "Live feed"),
    "imported": ("solid", "Imported file"),
    "synthetic": ("dashed", "Demo / synthetic data"),
    "manual": ("dashed", "Manual process"),
    "planned": ("dotted", "Planned, not built"),
}

# Charts: data series colours (categorical, ordered for contrast against white) and semantic overlays
SERIES = ("#1F5FAD", "#55595C", "#0F766E", "#7C3AED", "#B45309", "#0E7490")
CHART = {"paper": WHITE, "plot": WHITE, "grid": "#E6E8EA", "axis": INK_3, "ink": INK, "hover": WHITE,
         "reading": "#1F5FAD", "band": "#8A8F93", "event": "#1F5FAD", "case": "#B91C1C", "gap": "#B45309",
         "closed": "#0F766E", "idle": "#8A8F93"}

SPACE = {"xs": ".25rem", "s": ".5rem", "m": "1rem", "l": "1.5rem", "xl": "2.5rem"}
RADIUS = ".5rem"

CSS = f"""
:root {{
  --gbb-pink:{PINK}; --gbb-pink-dark:{PINK_DARK}; --gbb-pink-tint:{PINK_TINT}; --gbb-grey:{GREY}; --gbb-white:{WHITE};
  --gbb-ink:{INK}; --gbb-ink-2:{INK_2}; --gbb-ink-3:{INK_3}; --gbb-line:{LINE}; --gbb-line-strong:{LINE_STRONG};
  --gbb-surface:{SURFACE}; --gbb-surface-2:{SURFACE_2}; --gbb-surface-3:{SURFACE_3}; --gbb-link:{LINK};
  --gbb-radius:{RADIUS}; --gbb-font:{FONT};
}}
html, body, .stApp {{font-family:var(--gbb-font)}}
.stApp, [data-testid="stHeader"], [data-testid="stMain"] {{background:var(--gbb-surface) !important;color:var(--gbb-ink)}}
[data-testid="stSidebar"] {{background:var(--gbb-surface-2);border-right:1px solid var(--gbb-line)}}
[data-testid="stHeader"] {{box-shadow:inset 0 3px 0 var(--gbb-pink)}}
a {{color:var(--gbb-link)}}
:focus-visible {{outline:3px solid var(--gbb-pink) !important;outline-offset:2px}}
.gbb-demo {{display:inline-flex;align-items:center;gap:.35rem;padding:.1rem .55rem;border:1.5px dashed var(--gbb-ink-2);
  border-radius:.35rem;color:var(--gbb-ink-2);font-size:.72rem;font-weight:700;letter-spacing:.06em;text-transform:uppercase;
  white-space:nowrap}}
.gbb-source {{display:inline-flex;align-items:center;gap:.35rem;padding:.1rem .55rem;border:1.5px var(--b) var(--gbb-ink-3);
  border-radius:.35rem;color:var(--gbb-ink-2);font-size:.72rem;font-weight:650;white-space:nowrap}}
.gbb-mark {{display:inline-block;flex:none;width:.7rem;height:.7rem;vertical-align:middle}}
"""

_SHAPES = {
    "dot": '<circle cx="6" cy="6" r="5" fill="{c}"/>',
    "ring": '<circle cx="6" cy="6" r="4.2" fill="none" stroke="{c}" stroke-width="1.8"/>',
    "half": '<circle cx="6" cy="6" r="4.2" fill="none" stroke="{c}" stroke-width="1.8"/><path d="M6 1.8a4.2 4.2 0 0 1 0 8.4z" fill="{c}"/>',
    "triangle": '<path d="M6 1 11.2 10.6H.8z" fill="{c}"/>',
    "square": '<rect x="1.2" y="1.2" width="9.6" height="9.6" rx="1" fill="{c}"/>',
    "dash": '<rect x="1" y="4.6" width="10" height="2.8" rx="1" fill="{c}"/>',
}


def esc(value: Any) -> str:
    import html
    return html.escape("" if value is None else str(value))


def style() -> str:
    return f"<style>{CSS}</style>"


def status_mark(colour: str, shape: str, label: str = "") -> str:
    """A small inline SVG whose shape, not only its colour, tells states apart."""
    body = _SHAPES.get(shape, _SHAPES["dot"]).format(c=colour)
    title = f'<title>{esc(label)}</title>' if label else ""
    return (f'<svg class="gbb-mark" viewBox="0 0 12 12" role="img" aria-label="{esc(label)}">{title}{body}</svg>'
            if label else f'<svg class="gbb-mark" viewBox="0 0 12 12" aria-hidden="true">{body}</svg>')


def status_html(vocabulary: dict[str, tuple[str, str, str]], key: str) -> str:
    """Mark plus word for one status from one vocabulary, e.g. ``status_html(ASSET_STATE, "down")``."""
    colour, word, shape = vocabulary[key]
    return f'<span style="display:inline-flex;align-items:center;gap:.35rem">{status_mark(colour, shape)}{esc(word)}</span>'


def demo_badge(text: str = "Demo / synthetic data") -> str:
    """The label every synthetic figure carries. Dashed, grey and worded: it never looks like a live feed."""
    return f'<span class="gbb-demo" title="Generated for demonstration; not a site record">{esc(text)}</span>'


def source_badge(kind: str) -> str:
    border, word = DATA_SOURCE[kind]
    return f'<span class="gbb-source" style="--b:{border}">{esc(word)}</span>'


def contrast(foreground: str, background: str = WHITE) -> float:
    """WCAG 2 contrast ratio of two #RRGGBB colours."""
    def luminance(colour: str) -> float:
        r, g, b = (int(colour.lstrip("#")[i:i + 2], 16) / 255 for i in (0, 2, 4))
        lin = [c / 12.92 if c <= .04045 else ((c + .055) / 1.055) ** 2.4 for c in (r, g, b)]
        return .2126 * lin[0] + .7152 * lin[1] + .0722 * lin[2]
    a, b = sorted((luminance(foreground), luminance(background)), reverse=True)
    return (a + .05) / (b + .05)


def plotly_layout(**overrides: Any) -> dict[str, Any]:
    """Base Plotly layout in the house style: white canvas, quiet grid, ink text, legend above the plot."""
    layout = {"paper_bgcolor": CHART["paper"], "plot_bgcolor": CHART["plot"],
              "font": {"family": FONT, "color": INK, "size": 12}, "colorway": list(SERIES),
              "legend": {"orientation": "h", "y": 1.18, "x": 0, "font": {"size": 11}},
              "xaxis": {"gridcolor": CHART["grid"], "linecolor": LINE_STRONG, "tickfont": {"color": INK_3}},
              "yaxis": {"gridcolor": CHART["grid"], "linecolor": LINE_STRONG, "tickfont": {"color": INK_3}},
              "hoverlabel": {"bgcolor": CHART["hover"], "font_color": INK, "bordercolor": LINE_STRONG}}
    layout.update(overrides)
    return layout
