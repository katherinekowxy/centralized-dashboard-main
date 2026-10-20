"""System map: honest statuses, live counts, Dan's AI rules, and safe rendering."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from demo import map_view, system_map
from demo.engine import analyze, generate_dataset
from demo.history import generate_history

APP = Path(__file__).resolve().parents[1] / "app.py"


def _run(scenario: str = "leakage_ramp") -> dict:
    dataset = generate_dataset(scenario, 42)
    analysis = analyze(dataset["readings"], dataset["events"])
    return {"dataset": dataset, "analysis": analysis, "history": generate_history(analysis["metrics"]["as_of"]),
            "as_of": analysis["metrics"]["as_of"]}


def _nodes(layers: list[dict]) -> list[dict]:
    return [node for layer in layers for node in layer["nodes"]]


def test_layers_are_displayed_ai_on_top_and_use_known_statuses() -> None:
    layers = system_map.build()
    assert [layer["id"] for layer in layers] == list(map_view.LAYER_IDS)
    assert {node["status"] for node in _nodes(layers)} <= {"live", "manual", "planned"}
    assert all("metric" not in node for node in _nodes(layers))  # no session, no numbers


def test_live_counts_come_from_the_session_and_planned_parts_have_none() -> None:
    run = _run()
    layers = system_map.build(run, {"assets": [], "imports": [], "imported_readings": [], "feedback_count": 0,
                                    "dot_counts": {"alert": 1, "ok": 1, "idle": 3}, "incidents": []})
    nodes = {node["title"]: node for node in _nodes(layers)}
    families = [name for name in system_map.SENSOR_FAMILIES]
    total = sum(int(nodes[name]["metric"].replace(",", "")) for name in families)
    assert total == len(run["dataset"]["readings"])  # every replay reading lands in one sensor family
    assert nodes["Check and hold"]["metric"] == f"{len(run['analysis']['accepted']):,}"
    for node in _nodes(layers):
        if node["status"] == "planned":
            assert node.get("metric") is None


def test_ai_rules_record_dans_decisions() -> None:
    # Dan: the "machine-learning models" are "not ai, just code that tracks the live status".
    checks = next(item for item in system_map.DOT_AUTHORITY if item["who"] == "Live status checks")
    assert checks["status"] == "planned" and "not AI" in checks["rule"]
    assert "safety parameter" in checks["rule"] and "operational hours" in checks["rule"]
    advisory = next(item for item in system_map.DOT_AUTHORITY if "cloud model" in item["who"])
    assert "local model" in advisory["who"] and "never change a dot" in advisory["rule"]
    assert "safe to operate" in next(item for item in system_map.DOT_AUTHORITY if item["who"] == "Fixed rules")["rule"]
    layers = {layer["id"]: layer["nodes"] for layer in system_map.build()}
    ai_text = " ".join(f"{node.get('text', '')} {node.get('detail', '')}" for node in layers["ai"])
    assert "turn a dot red" not in ai_text and "never changes a dot" in ai_text  # no AI part claims red authority
    assert any(node["title"] == "Live status checks" and node["status"] == "planned" for node in layers["diagnostics"])
    assert "related evidence bucket only" in system_map.ESCALATION["sends"].lower()
    assert "approves every escalation" in system_map.ESCALATION["approval"]
    assert len(system_map.ESCALATION["triggers"]) == 3


def test_renderer_escapes_text_and_only_links_web_urls() -> None:
    html = map_view.node_html({"title": "<script>x</script>", "status": "planned", "text": "a & b",
                               "links": [{"url": "javascript:alert(1)", "label": "bad"}, {"url": "https://example.com/a", "label": "ok"}]})
    assert "<script>" not in html and "&lt;script&gt;" in html and "a &amp; b" in html
    assert 'href="javascript' not in html and 'href="https://example.com/a"' in html
    assert "sd-node-faded" in html  # planned is shown by border style, not colour


def test_compact_cards_keep_the_description_behind_details() -> None:
    node = {"title": "Check and hold", "status": "live", "metric": "12", "text": "Schema & units.", "detail": "More."}
    head, details = map_view.node_html(node, compact=True).split("<details>", 1)
    assert "Check and hold" in head and "12" in head and "Schema" not in head  # title, status and number only
    assert "Schema &amp; units." in details and "More." in details
    assert "Schema" in map_view.node_html(node).split("<details>")[0]  # other maps keep their text visible


def test_system_map_tab_renders_when_navigation_is_wired() -> None:
    at = AppTest.from_file(str(APP), default_timeout=60)
    at.query_params["all"] = "1"
    at.run()
    at.button(key="nav-architecture").click().run()
    assert not at.exception
    markup = "\n".join(item.value for item in at.markdown)
    for layer in system_map.LAYERS:
        assert layer["name"] in markup
    assert "Who may turn a dot red" in markup and "Planned" in markup


def test_map_claims_only_what_the_code_does() -> None:
    # Corrections from the independent fact-check of 6 October 2026.
    nodes = {node["title"]: node for layer in system_map.build() for node in layer["nodes"]}
    assert "not yet analysed" in nodes["Vendor CSV import"]["text"]          # imports bypass analyze()
    assert "aligned" not in nodes["Time in UTC"]["text"]                       # no clock-alignment code
    assert "aligned by the investigator" in nodes["Incident buckets"]["text"]  # that work is manual
    assert "cadence" not in nodes["Check and hold"]["text"]                    # cadence never holds a row
    assert "planned" in nodes["Engineer review"]["text"].lower()               # escalation approval not built
    mixed = next(item for item in system_map.DOT_AUTHORITY if "cloud model" in item["who"])
    assert mixed["status"] == "live, manual and planned"
    assert "not live monitoring" in system_map.RUNTIME
    assert "end state" in nodes["Live feeds"]["text"] and nodes["Live feeds"]["status"] == "planned"
