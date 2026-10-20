"""Exploratory view: public reference architectures of external platforms.

Data comes from ``demo.platform_references.load_platforms()`` (Codex). Each record:
``{id, name, checked_on, summary, flows: [{name, steps: [{layer, label, detail,
source_ids, runs_at?}], caveat}], findings: [{status, archived_claim, assessment,
source_ids}], unknowns: [...], sources: [{id, title, url, published, accessed}]}``.

These maps describe vendors' publicly documented architectures, never SignalDesk's.
Each documented path is shown as numbered steps in its real order, each naming its layer.
The layer-by-layer comparison with SignalDesk's System map sits in an expander, so the
grouping is never mistaken for a data path.
"""

from __future__ import annotations

import re
from typing import Any

from demo import fusion_view, map_view, system_map

ROLES = {
    "ai": "ML, generative AI and assistants",
    "diagnostics": "Rules, analytics and asset performance",
    "platform": "Data store, asset model, dashboards and workflow",
    "routing": "Gateways, connectors, protocols and ingestion",
    "sources": "Devices, sensors and source systems",
}
NAMES = {layer["id"]: layer["name"] for layer in system_map.LAYERS}


def _source_links(source_ids: list[str] | None, sources: dict[str, dict[str, Any]]) -> list[dict[str, str]]:
    links = []
    for source_id in source_ids or []:
        source = sources.get(source_id)
        if source:
            links.append({"url": source.get("url", ""), "label": source.get("title") or source_id})
    return links


def flow_steps(flow: dict[str, Any], sources: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """One documented path as nodes in its real order. Each node names its layer; location unknown unless sourced."""
    return [{"title": step.get("label"), "status": step.get("status", "documented"), "text": step.get("detail"),
             "layer_name": NAMES.get(step.get("layer"), "Layer not stated"), "runs_at": step.get("runs_at") or "unknown",
             "links": _source_links(step.get("source_ids"), sources)} for step in flow.get("steps", [])]


_EXPLICIT_ML = re.compile(r"\bML\b|(?i:machine[- ]learning|artificial intelligence)")


def uses_ml(step: dict[str, Any]) -> bool:
    """An explicit ``uses_ml`` flag wins; otherwise the cited text must say ML outright."""
    if "uses_ml" in step:
        return bool(step["uses_ml"])
    return bool(_EXPLICIT_ML.search(f"{step.get('label', '')} {step.get('detail', '')}"))


def compare_rows(platform: dict[str, Any]) -> list[dict[str, Any]]:
    """Per layer: SignalDesk's parts against this platform's documented steps.

    Vendors often document ML inside their analytics product, which the research files under
    diagnostics. The AI row then points to it, so an empty AI layer is not read as "no AI".
    """
    ours = system_map.layer_summary()
    theirs: dict[str, list[str]] = {layer_id: [] for layer_id in map_view.LAYER_IDS}
    ml_inside: list[tuple[str, str]] = []
    for flow in platform.get("flows", []):
        for step in flow.get("steps", []):
            if step.get("layer") in theirs:
                where = map_view.RUNS_AT_LABEL.get(step.get("runs_at"), "")
                text = f"{step.get('label')}" + (f" ({where.lower()})" if where else "")
                if text not in theirs[step["layer"]]:
                    theirs[step["layer"]].append(text)
                found = (str(step.get("label")), NAMES[step["layer"]])
                if step["layer"] != "ai" and uses_ml(step) and found not in ml_inside:
                    ml_inside.append(found)
    if not theirs["ai"]:
        theirs["ai"] = [f"ML inside {label} (shown under {layer})" for label, layer in ml_inside]
    return [{"layer": NAMES[layer_id], "left": ours.get(layer_id, []), "right": theirs[layer_id]}
            for layer_id in map_view.LAYER_IDS]


def render(platforms: list[dict[str, Any]]) -> None:
    import streamlit as st

    st.markdown(f"<style>{map_view.CSS}</style>", unsafe_allow_html=True)
    st.markdown('<div class="sd-section">External platform references</div>'
                '<div class="sd-muted" style="margin-bottom:.6rem">Publicly documented architectures, checked against official sources '
                'on the dates shown. <b>These maps are not SignalDesk’s architecture.</b> Anything the reviewed sources do not '
                'establish is marked that way, which is not proof that it is secret.</div>', unsafe_allow_html=True)
    if not platforms:
        st.info("No verified platform records yet.")
        return
    by_name = {platform["name"]: platform for platform in platforms}
    choice = st.selectbox("Platform", list(by_name), key="exploratory_platform")
    platform = by_name[choice]
    sources = {source["id"]: source for source in platform.get("sources", []) if source.get("id")}
    st.markdown(f'<div class="sd-muted">{map_view.esc(platform.get("summary"))} '
                f'Checked {map_view.esc(platform.get("checked_on"))}.</div>', unsafe_allow_html=True)
    flows = platform.get("flows", [])
    if flows:
        names = [flow.get("name") or f"Path {index + 1}" for index, flow in enumerate(flows)]
        chosen = st.radio("Documented path", names, horizontal=True, key=f"exploratory_path_{platform.get('id')}") if len(flows) > 1 else names[0]
        flow = flows[names.index(chosen)]
        st.markdown(f'<div class="sd-section" style="font-size:.95rem">{map_view.esc(chosen)}</div>'
                    + map_view.steps_html(flow_steps(flow, sources)), unsafe_allow_html=True)
        if flow.get("caveat"):
            st.markdown(f'<div class="sd-muted">{map_view.esc(flow["caveat"])}</div>', unsafe_allow_html=True)
        st.markdown(fusion_view.evidence_html(platform, flow), unsafe_allow_html=True)
    unknowns = platform.get("unknowns") or []
    if unknowns:
        st.markdown('<div class="sd-muted" style="margin-top:.4rem"><b>Not established by the reviewed sources:</b>'
                    '<ul style="margin:.15rem 0 0;padding-left:1.1rem">'
                    + "".join(f"<li>{map_view.esc(item)}</li>" for item in unknowns) + "</ul></div>", unsafe_allow_html=True)
    with st.expander("Compared with SignalDesk, layer by layer", expanded=False):
        st.markdown(map_view.compare_html(compare_rows(platform), "SignalDesk", platform["name"]), unsafe_allow_html=True)
        st.caption("All of this platform's documented paths are pooled per layer. SignalDesk's side is its own System map.")
    if flows:
        fusion_view.render_details(flow)
    findings = platform.get("findings") or []
    with st.expander(f"Archived claims checked ({len(findings)})", expanded=False):
        for finding in findings:
            links = " · ".join(map_view.link(item["url"], item["label"]) for item in _source_links(finding.get("source_ids"), sources))
            st.markdown(f'<div style="margin:.35rem 0;font-size:.82rem"><span class="sd-node-tag">{map_view.esc(finding.get("status"))}</span> '
                        f'<i>{map_view.esc(finding.get("archived_claim"))}</i><br>{map_view.esc(finding.get("assessment"))}'
                        f'{("<br><span class=sd-muted>" + links + "</span>") if links else ""}</div>', unsafe_allow_html=True)
    with st.expander(f"Sources ({len(sources)})", expanded=False):
        for source in sources.values():
            st.markdown(f'<div style="font-size:.8rem;margin:.25rem 0">{map_view.link(source.get("url", ""), source.get("title") or source["id"])}'
                        f' <span class="sd-muted">· published {map_view.esc(source.get("published") or "n/a")} · accessed '
                        f'{map_view.esc(source.get("accessed"))}</span></div>', unsafe_allow_html=True)
