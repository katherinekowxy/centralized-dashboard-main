"""Shared renderer for layered system maps (SignalDesk's own map and external references).

Pure functions that return HTML strings; the caller injects ``CSS`` once and passes the
result to ``st.markdown(..., unsafe_allow_html=True)``. All text is escaped here.

A map is a list of layers ``{id, name, role, nodes}``; a node is
``{title, status, text, metric?, metric_unit?, detail?, runs_at?, links?}``.
Status is shown by border style and a word, never by colour: red and green are
reserved for diagnostic findings elsewhere in the app.
"""

from __future__ import annotations

import html
from typing import Any, Iterable

LAYER_IDS = ("ai", "diagnostics", "platform", "routing", "sources")  # top to bottom, as displayed

STATUS_LABEL = {
    "live": "Live", "manual": "Manual", "planned": "Planned",
    "documented": "Documented", "inferred": "Inferred", "not_public": "Not established",
    "not_assessed": "Not assessed",
}
STATUS_STYLE = {  # css modifier per status
    "live": "solid", "documented": "solid", "manual": "dashed", "inferred": "dashed",
    "planned": "faded", "not_public": "faded", "not_assessed": "faded",
}
RUNS_AT_LABEL = {
    "device": "On device", "edge": "Edge", "on_premises": "On site", "local": "On this machine",
    "cloud": "Cloud", "unknown": "Location not established",
}

CSS = """
.sd-map {display:flex;flex-direction:column;gap:.35rem;margin:.4rem 0 1rem}
.sd-layer {display:grid;grid-template-columns:170px 1fr;gap:.9rem;align-items:start;
  background:var(--gbb-surface-2);border:1px solid var(--gbb-line);border-radius:.8rem;padding:.75rem .9rem}
.sd-layer-label b {display:block;font-size:13px;letter-spacing:-.01em}
.sd-layer-label span {display:block;color:var(--gbb-ink-3);font-size:12px;line-height:1.35;margin-top:.15rem}
.sd-layer-nodes {display:grid;grid-template-columns:repeat(auto-fill,minmax(190px,1fr));gap:.55rem}
.sd-map-arrow {text-align:center;color:var(--gbb-ink-3);font-size:12px;line-height:1.1}
.sd-node {background:var(--gbb-surface-2);border:1px solid var(--gbb-line-strong);border-radius:.6rem;padding:.55rem .7rem;min-height:4.2rem}
.sd-node-compact {min-height:0}
.sd-map-compact .sd-layer-nodes {grid-template-columns:repeat(auto-fill,minmax(165px,1fr))}
.sd-node-compact .sd-node-head {flex-direction:column-reverse;align-items:flex-start;gap:.2rem}  /* tag above, title full width */
.sd-node-dashed {border-style:dashed}
.sd-node-faded {border-style:dotted;background:transparent;opacity:.78}
.sd-node-head {display:flex;justify-content:space-between;align-items:baseline;gap:.4rem}
.sd-node-title {font-size:12px;font-weight:650;color:var(--gbb-ink)}
.sd-node-tag {flex:none;font-size:12px;letter-spacing:.06em;text-transform:uppercase;color:var(--gbb-ink-3);
  border:1px solid var(--gbb-line-strong);border-radius:99px;padding:.02rem .42rem}
.sd-node-dashed .sd-node-tag {border-style:dashed}
.sd-node-faded .sd-node-tag {border-style:dotted}
.sd-node-metric {font-size:14px;font-weight:750;margin:.2rem 0 .05rem;font-variant-numeric:tabular-nums}
.sd-node-metric small {font-size:12px;font-weight:500;color:var(--gbb-ink-3);margin-left:.25rem}
.sd-node-text {font-size:12px;color:var(--gbb-ink-3);line-height:1.4;margin-top:.15rem}
.sd-node-where {display:inline-block;margin-top:.3rem;font-size:12px;color:var(--gbb-ink-3)}
.sd-node details {margin-top:.3rem;font-size:12px;color:var(--gbb-ink-3)}
.sd-node summary {cursor:pointer;color:var(--gbb-link)}
.sd-node details div {margin-top:.25rem;line-height:1.45}
.sd-node a {color:var(--gbb-link)}
.sd-steps {display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:.55rem;margin:.3rem 0 .5rem;counter-reset:step}
.sd-step-no {font-size:12px;letter-spacing:.06em;text-transform:uppercase;color:var(--gbb-ink-3);margin-bottom:.2rem}
.sd-compare {display:grid;grid-template-columns:140px 1fr 1fr;gap:.45rem .8rem;font-size:12px;margin:.3rem 0 1rem}
.sd-compare > div {padding:.45rem .55rem;border-radius:.5rem;background:var(--gbb-surface-2);border:1px solid var(--gbb-line);line-height:1.4}
.sd-compare .sd-compare-head {background:transparent;border:none;color:var(--gbb-ink-3);font-size:12px;text-transform:uppercase;letter-spacing:.06em;padding:0 .2rem}
.sd-compare .sd-compare-layer {font-weight:650;color:var(--gbb-ink)}
.sd-compare ul {margin:0;padding-left:1rem}
.sd-policy {display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:.6rem;margin:.2rem 0 1rem}
.sd-policy > div {background:var(--gbb-surface-2);border:1px dotted var(--gbb-line-strong);border-radius:.7rem;padding:.65rem .8rem;font-size:12px;line-height:1.45;color:var(--gbb-ink-3)}
.sd-policy b {color:var(--gbb-ink)}
.sd-policy ul {margin:.3rem 0 0;padding-left:1.05rem}
@media (max-width: 640px) {
  .sd-layer {grid-template-columns:1fr;gap:.45rem}
  .sd-map-compact .sd-layer-nodes {grid-template-columns:repeat(auto-fill,minmax(140px,1fr))}
  .sd-compare {grid-template-columns:1fr}
  .sd-compare .sd-compare-head {display:none}
}
"""


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def link(url: str, label: str) -> str:
    if not isinstance(url, str) or not url.startswith(("https://", "http://")):
        return esc(label)
    return f'<a href="{esc(url)}" target="_blank" rel="noopener noreferrer">{esc(label)}</a>'


def node_html(node: dict[str, Any], compact: bool = False) -> str:
    """One card. ``compact`` shows only title, status, number and location; the description moves into Details."""
    status = node.get("status", "live")
    style = STATUS_STYLE.get(status, "solid")
    parts = [f'<div class="sd-node sd-node-{style}{" sd-node-compact" if compact else ""}">',
             f'<div class="sd-node-head"><span class="sd-node-title">{esc(node.get("title"))}</span>'
             f'<span class="sd-node-tag">{esc(STATUS_LABEL.get(status, status))}</span></div>']
    if node.get("metric") not in (None, ""):
        unit = f'<small>{esc(node.get("metric_unit"))}</small>' if node.get("metric_unit") else ""
        parts.append(f'<div class="sd-node-metric">{esc(node["metric"])}{unit}</div>')
    if node.get("text") and not compact:
        parts.append(f'<div class="sd-node-text">{esc(node["text"])}</div>')
    if node.get("runs_at") and node["runs_at"] != "local":  # "on this machine" is stated once in the page footer
        parts.append(f'<span class="sd-node-where">{esc(RUNS_AT_LABEL.get(node["runs_at"], node["runs_at"]))}</span>')
    hidden = [item for item in (node.get("text") if compact else None, node.get("detail")) if item]
    links = node.get("links") or []
    if hidden or links:
        body = "<br>".join(esc(item) for item in hidden)
        if links:
            body += ("<br>" if body else "") + " · ".join(link(item.get("url"), item.get("label") or item.get("url")) for item in links)
        parts.append(f"<details><summary>Details</summary><div>{body}</div></details>")
    parts.append("</div>")
    return "".join(parts)


def layers_html(layers: Iterable[dict[str, Any]], arrows: dict[str, str] | None = None, compact: bool = False) -> str:
    """Render layers top to bottom; ``arrows[layer_id]`` labels the arrow beneath that layer."""
    arrows = arrows or {}
    out = [f'<div class="sd-map{" sd-map-compact" if compact else ""}">']
    rendered = [layer for layer in layers if layer.get("nodes")]
    for index, layer in enumerate(rendered):
        out.append('<div class="sd-layer">'
                   f'<div class="sd-layer-label"><b>{esc(layer.get("name"))}</b><span>{esc(layer.get("role"))}</span></div>'
                   f'<div class="sd-layer-nodes">{"".join(node_html(node, compact) for node in layer["nodes"])}</div></div>')
        if index < len(rendered) - 1:
            label = arrows.get(layer.get("id"), "")  # what flows up into the layer above this arrow
            out.append(f'<div class="sd-map-arrow">▲{(" " + esc(label)) if label else ""}</div>')
    out.append("</div>")
    return "".join(out)


def steps_html(nodes: Iterable[dict[str, Any]]) -> str:
    """One documented path as numbered cards in their real order; each card names its layer."""
    cards = []
    for number, node in enumerate(nodes, start=1):
        card = node_html(node)
        badge = f'<div class="sd-step-no">Step {number} · {esc(node.get("layer_name") or "Layer not stated")}</div>'
        cards.append(card.replace('<div class="sd-node-head">', badge + '<div class="sd-node-head">', 1))
    return '<div class="sd-steps">' + "".join(cards) + "</div>"


def compare_html(rows: Iterable[dict[str, Any]], left: str, right: str) -> str:
    """Side-by-side per layer: ``rows`` = ``[{layer, left: [str], right: [str]}]``."""
    out = ['<div class="sd-compare">', '<div class="sd-compare-head">Layer</div>',
           f'<div class="sd-compare-head">{esc(left)}</div>', f'<div class="sd-compare-head">{esc(right)}</div>']
    for row in rows:
        def cell(items: list[str], name: str) -> str:
            if not items:
                return f'<div><span style="color:var(--gbb-ink-3)">{esc(name)}: nothing in the reviewed sources</span></div>'
            return f'<div><ul>{"".join(f"<li>{esc(item)}</li>" for item in items)}</ul></div>'
        out.append(f'<div class="sd-compare-layer">{esc(row["layer"])}</div>')
        out.append(cell(row.get("left", []), left))
        out.append(cell(row.get("right", []), right))
    out.append("</div>")
    return "".join(out)
