"""Path-specific evidence of sensor fusion, alongside external platform maps."""

from __future__ import annotations

from typing import Any

from demo import map_view


def evidence_html(platform: dict[str, Any], flow: dict[str, Any]) -> str:
    """Render only the selected path's claims; a missing review is not a verdict."""
    evidence = flow.get("evidence_fusion") or {}
    outcome = evidence.get("status")
    status = {"Documented fusion": "documented", "Multiple sensing types": "not_public",
              "Electrical signature analysis": "documented"}.get(outcome, "not_assessed")
    title = "Electrical signature analysis" if outcome == "Electrical signature analysis" else "Diagnostic fusion"
    assessment = evidence.get("assessment") or "Diagnostic fusion not assessed in this review."
    inputs = evidence.get("inputs") or []
    sources = {source["id"]: source for source in platform.get("sources", [])}
    links = [{"url": sources[item].get("url", ""), "label": sources[item].get("title") or item}
             for item in evidence.get("source_ids", []) if item in sources]
    return (
        '<div class="sd-section" style="font-size:13px">Diagnostic fusion on this path</div>'
        '<div class="sd-fusion">'
        + map_view.node_html({"title": title, "status": status,
                              "text": ("Inputs: " + " · ".join(inputs) + ". " if inputs else "") + assessment,
                              "detail": "Evidence limits: " + (evidence.get("limits") or
                                  "Diagnostic fusion has not been assessed for this path; this is not evidence that the platform lacks it."),
                              "links": links}) + '</div>'
    )


def render_details(flow: dict[str, Any]) -> None:
    """Keep general definitions and the current demo's scope collapsed."""
    import streamlit as st

    with st.expander("Diagnostic fusion: definitions and SignalDesk today", expanded=False):
        st.markdown(
            "Commercial multi-sensor diagnostic fusion exists. A list of sensors alone does not establish it.\n\n"
            "- **Multiple measurements:** vibration, temperature and current displayed separately.\n"
            "- **Diagnostic fusion:** assess relationships between measurements. For an **illustrative PUMP-01 example**, "
            "ask whether vibration and temperature remain unusual after accounting for motor load and speed. "
            "This describes a design concept, not an implemented SignalDesk algorithm.\n"
            "- **Context integration:** use maintenance history, operating mode and recent repairs to interpret a finding."
        )
        st.markdown(
            "**SignalDesk today**\n\n"
            "- A synthetic scenario replay applies aligned running-mode rules to vibration, bearing temperature and motor current.\n"
            "- A separate scenario demonstrates a load change. These demo heuristics do not perform load/speed normalization.\n"
            "- Missing baseline or aligned evidence prevents a pump condition finding. Conflicting evidence does not establish a cause; maintenance context can accompany findings.\n"
            "- AI explanations are optional and advisory. AI never changes a diagnostic dot."
        )
