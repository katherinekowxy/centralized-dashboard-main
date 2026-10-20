"""Exploratory view renderer against Codex's platform-record contract (fixture data)."""

import json

from streamlit.testing.v1 import AppTest

from demo import exploratory_view

FIXTURE = {
    "id": "example-vendor", "name": "Example Vendor Platform", "checked_on": "2026-10-06",
    "summary": "Fixture record for renderer tests.",
    "flows": [{
        "name": "Cloud path",
        "steps": [
            {"layer": "sources", "label": "Wireless vibration sensor", "detail": "Battery sensor.", "source_ids": ["s1"], "runs_at": "device"},
            {"layer": "routing", "label": "Edge gateway", "detail": "Protocol bridge.", "source_ids": ["s1"], "runs_at": "edge"},
            {"layer": "platform", "label": "Cloud data store", "detail": "", "source_ids": ["s2"], "runs_at": "cloud"},
            {"layer": "ai", "label": "Fault classifier", "detail": "ML model.", "source_ids": ["s2"], "runs_at": "cloud"},
            {"layer": "mystery", "label": "Undocumented service", "detail": "", "source_ids": []},
        ],
        "caveat": "Alternative paths are shown separately.",
    }],
    "findings": [{"status": "Corrected", "archived_claim": "Runs fully on site.", "assessment": "Public docs show a cloud path.",
                  "source_ids": ["s2"]}],
    "unknowns": ["Model training data"],
    "sources": [{"id": "s1", "title": "Sensor datasheet", "url": "https://example.com/s1", "published": "2025-01-01", "accessed": "2026-10-06"},
                {"id": "s2", "title": "Architecture page", "url": "https://example.com/s2", "published": None, "accessed": "2026-10-06"}],
}


def test_steps_keep_the_documented_order_and_name_their_layer() -> None:
    sources = {source["id"]: source for source in FIXTURE["sources"]}
    steps = exploratory_view.flow_steps(FIXTURE["flows"][0], sources)
    assert [step["title"] for step in steps] == ["Wireless vibration sensor", "Edge gateway", "Cloud data store",
                                                 "Fault classifier", "Undocumented service"]
    assert [step["layer_name"] for step in steps] == ["Sources", "Routing", "Central platform", "AI", "Layer not stated"]
    assert steps[1]["links"][0]["url"] == "https://example.com/s1"
    assert steps[4]["runs_at"] == "unknown"  # location is never guessed
    assert all(step["status"] == "documented" for step in steps)


def test_comparison_puts_signaldesk_next_to_the_platform_for_every_layer() -> None:
    rows = exploratory_view.compare_rows(FIXTURE)
    assert [row["layer"] for row in rows] == ["AI", "Diagnostics", "Central platform", "Routing", "Sources"]
    ai = rows[0]
    assert any("Cloud model" in item for item in ai["left"])
    assert ai["right"] == ["Fault classifier (cloud)"]
    assert next(row for row in rows if row["layer"] == "Diagnostics")["right"] == []


def test_render_shows_disclaimer_comparison_and_details_without_errors() -> None:
    script = (
        "import json\n"
        "from demo import exploratory_view\n"
        f"exploratory_view.render([json.loads({json.dumps(json.dumps(FIXTURE))})])\n"
    )
    at = AppTest.from_string(script, default_timeout=30).run()
    assert not at.exception
    markup = "\n".join(item.value for item in at.markdown)
    assert "not SignalDesk" in markup and "Not established by the reviewed sources" in markup
    assert "Step 2 · Routing" in markup and "Edge gateway" in markup
    assert [expander.label for expander in at.expander] == ["Compared with SignalDesk, layer by layer",
                                                           "Diagnostic fusion: definitions and SignalDesk today",
                                                           "Archived claims checked (1)", "Sources (2)"]
    assert at.selectbox[0].label == "Platform"
    assert not at.radio  # a single documented path needs no path picker


def test_render_handles_no_records_yet() -> None:
    at = AppTest.from_string("from demo import exploratory_view\nexploratory_view.render([])\n", default_timeout=30).run()
    assert not at.exception
    assert any("No verified platform records" in item.value for item in at.info)


def test_one_path_at_a_time_when_a_platform_has_several() -> None:
    two_paths = {**FIXTURE, "flows": [FIXTURE["flows"][0], {**FIXTURE["flows"][0], "name": "On-site path",
                                                           "steps": [{"layer": "routing", "label": "Local historian link", "source_ids": ["s1"]}]}]}
    script = ("import json\nfrom demo import exploratory_view\n"
              f"exploratory_view.render([json.loads({json.dumps(json.dumps(two_paths))})])\n")
    at = AppTest.from_string(script, default_timeout=30).run()
    assert not at.exception
    assert at.radio[0].label == "Documented path" and at.radio[0].options == ["Cloud path", "On-site path"]
    path_line = next(item.value for item in at.markdown if 'class="sd-steps"' in item.value)
    assert "Edge gateway" in path_line and "Local historian link" not in path_line  # comparison pools paths; this line does not
    at.radio[0].set_value("On-site path").run()
    path_line = next(item.value for item in at.markdown if 'class="sd-steps"' in item.value)
    assert "Local historian link" in path_line and "Edge gateway" not in path_line
    assert any("Location not established" in item.value for item in at.markdown)


def test_ai_row_points_to_ml_documented_inside_analytics() -> None:
    record = {**FIXTURE, "flows": [{"name": "p", "steps": [
        {"layer": "diagnostics", "label": "Analytics service", "detail": "ML models detect abnormal conditions.", "source_ids": []},
        {"layer": "diagnostics", "label": "Rules engine", "detail": "Thresholds raise alerts.", "source_ids": []},
        {"layer": "diagnostics", "label": "Tagged model", "detail": "Plain text.", "uses_ml": True, "source_ids": []},
        {"layer": "diagnostics", "label": "Says ML but flagged off", "detail": "ML", "uses_ml": False, "source_ids": []}]}]}
    ai_row = exploratory_view.compare_rows(record)[0]
    assert ai_row["layer"] == "AI"
    assert ai_row["right"] == ["ML inside Analytics service (shown under Diagnostics)",
                               "ML inside Tagged model (shown under Diagnostics)"]
    # A platform that documents an AI-layer step keeps it as-is.
    assert exploratory_view.compare_rows(FIXTURE)[0]["right"] == ["Fault classifier (cloud)"]

