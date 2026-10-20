"""Fusion claims remain attached to the selected documented path."""

import copy
import json

from streamlit.testing.v1 import AppTest

from demo import fusion_view


PLATFORMS = [{
    "id": "example", "name": "Example platform", "unknowns": ["Some unreviewed feature"], "sources": [
        {"id": "fusion", "title": "Fusion source", "url": "https://example.com/fusion"},
        {"id": "sensing", "title": "Sensing source", "url": "https://example.com/sensing"}],
    "flows": [
        {"name": "Correlated model", "caveat": "Model path caveat", "steps": [
            {"layer": "diagnostics", "label": "Correlated model step"}], "evidence_fusion": {
            "status": "Documented fusion", "inputs": ["Vibration", "Temperature", "Load"],
            "assessment": "Models correlate measurements.", "limits": "Model internals not established.", "source_ids": ["fusion"]}},
        {"name": "Transmitter path", "steps": [
            {"layer": "sources", "label": "Transmitter step"}], "evidence_fusion": {
            "status": "Multiple sensing types", "inputs": ["Vibration", "Acoustics", "Temperature"],
            "assessment": "Sensing types confirmed; automated fusion not established.",
            "limits": "The Honeywell brochure does not establish automated model fusion.", "source_ids": ["sensing"]}},
        {"name": "Unreviewed path"}]},
    {"id": "second", "name": "Second platform", "flows": [{"name": "Other path"}]}]


def _app() -> AppTest:
    return AppTest.from_string(
        "import json\nfrom demo import exploratory_view\n"
        f"platforms = json.loads({json.dumps(json.dumps(PLATFORMS))})\n"
        "exploratory_view.render(platforms)\n", default_timeout=30).run()


def test_switching_path_changes_evidence_and_sources_without_inheriting_fusion() -> None:
    at = _app()
    assert not at.exception
    card = next(item.value for item in at.markdown if 'class="sd-fusion"' in item.value)
    assert 'class="sd-node sd-node-solid"' in card and '>Documented</span>' in card
    assert "https://example.com/fusion" in card
    assert card.index('<details><summary>Details</summary>') < card.index('https://example.com/fusion') < card.index('</details>')
    assert card.index('<details>') < card.index('Model internals not established.') < card.index('</details>')
    markup = [item.value for item in at.markdown]
    assert next(i for i, value in enumerate(markup) if "Model path caveat" in value) < markup.index(card)
    assert markup.index(card) < next(i for i, value in enumerate(markup) if "Not established by the reviewed sources" in value)
    at.radio[0].set_value("Transmitter path").run()
    assert not at.exception
    card = next(item.value for item in at.markdown if 'class="sd-fusion"' in item.value)
    assert 'class="sd-node sd-node-faded"' in card and '>Not established</span>' in card
    assert "Multiple measurements confirmed" not in card  # the tag gives the verdict; the text does not repeat it
    assert "https://example.com/sensing" in card
    assert "The Honeywell brochure does not establish automated model fusion." in card
    assert "Model internals not established." not in card
    assert '>Documented</span>' not in card and "https://example.com/fusion" not in card
    at.radio[0].set_value("Unreviewed path").run()
    card = next(item.value for item in at.markdown if 'class="sd-fusion"' in item.value)
    assert "Diagnostic fusion not assessed in this review" in card
    assert 'class="sd-node sd-node-faded"' in card and '>Not assessed</span>' in card
    assert '>Documented</span>' not in card and "https://example.com/sensing" not in card
    assert "not evidence that the platform lacks it" in "\n".join(item.value for item in at.markdown)


def test_panel_follows_actual_platform_selector() -> None:
    at = _app()
    at.selectbox[0].set_value("Second platform").run()
    assert not at.exception
    cards = [item.value for item in at.markdown if 'class="sd-fusion"' in item.value]
    assert len(cards) == 1
    assert "Diagnostic fusion on this path" in cards[0]
    assert "Other path" not in cards[0]  # the path name is already displayed above
    assert "Diagnostic fusion not assessed in this review" in cards[0]
    assert '>Documented</span>' not in cards[0]


def test_details_keep_illustration_separate_from_current_demo_and_are_collapsed() -> None:
    at = _app()
    assert not at.exception
    assert at.expander[0].label == "Compared with SignalDesk, layer by layer"
    assert at.expander[1].label == "Diagnostic fusion: definitions and SignalDesk today"
    assert not at.expander[1].proto.expanded
    text = "\n".join(item.value for item in at.markdown)
    assert "illustrative PUMP-01 example" in text
    assert "not an implemented SignalDesk algorithm" in text
    assert "do not perform load/speed normalization" in text
    assert "synthetic scenario replay" in text
    assert "AI never changes a diagnostic dot" in text


def test_claims_and_source_links_are_escaped() -> None:
    platform = copy.deepcopy(PLATFORMS[0])
    platform["sources"][0].update(title='<img src=x onerror=alert(1)>', url='javascript:alert(1)')
    flow = platform["flows"][0]
    flow["name"] = '<script>bad()</script>'
    flow["evidence_fusion"]["assessment"] = '<script>bad()</script><img src=x>'
    markup = fusion_view.evidence_html(platform, flow)
    assert "<script>" not in markup and "<img " not in markup
    assert "&lt;script&gt;" in markup and "&lt;img " in markup
    assert "javascript:" not in markup


def test_electrical_signature_analysis_is_not_labelled_documented_fusion() -> None:
    flow = {"evidence_fusion": {"status": "Electrical signature analysis",
            "inputs": ["Current", "Voltage"],
            "assessment": "Electrical signatures can reveal mechanical faults."}}
    card = fusion_view.evidence_html({}, flow)
    assert '<span class="sd-node-title">Electrical signature analysis</span>' in card
    assert '>Documented</span>' in card and 'sd-node-solid' in card
    assert "Electrical signatures can reveal mechanical faults" in card
    assert '<span class="sd-node-title">Diagnostic fusion</span>' not in card
