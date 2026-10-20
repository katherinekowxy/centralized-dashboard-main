"""SignalDesk's own system map: what feeds the platform, what runs on it, what is planned.

Statuses: ``live`` runs in this demo; ``manual`` is done outside the app (for example
the blind incident investigations); ``planned`` is specified but not built. Live nodes
carry counts from the current session. Policy text records Dan's decisions of
6 October 2026 on dot authority and cloud escalation.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from demo.engine import DETECTOR_ASSET_IDS, POINTS

LAYERS = [  # displayed top to bottom; data flows upwards
    {"id": "ai", "name": "AI", "role": "Explains and investigates. Advisory only: AI never changes a dot."},
    {"id": "diagnostics", "name": "Diagnostics", "role": "Rules that decide the status dots."},
    {"id": "platform", "name": "Central platform", "role": "One registry; one information bucket per asset."},
    {"id": "routing", "name": "Routing", "role": "Every record checked, matched to one asset and timed in UTC."},
    {"id": "sources", "name": "Sources", "role": "Where the information comes from."},
]

ARROWS = {  # label on the arrow beneath each layer, i.e. what flows up into it
    "ai": "one case and its evidence IDs (incident buckets are read by hand)",
    "diagnostics": "detectors run on the whole replay in one pass; dots then read each asset bucket",
    "platform": "accepted replay rows; failing rows held with a reason",
    "routing": "a replayed scenario and vendor CSV files (exports are filed into incident buckets by hand; API routing planned)",
}

SENSOR_FAMILIES = {
    "Electrical sensors": {"earth_leakage_current", "trip_state", "phase_voltage", "phase_current", "neutral_current",
                           "motor_current", "electrical_power"},
    "Temperature sensors": {"bearing_temperature", "supply_air_temperature", "return_air_temperature",
                            "chilled_water_supply_temperature", "chilled_water_return_temperature"},
    "Vibration sensors": {"vibration_velocity_overall"},
    "Pressure and flow": {"differential_pressure", "water_flow"},
}

DOT_AUTHORITY = [
    {"who": "Fixed rules", "status": "live",
     "rule": "A detector finding, or a protection relay reporting a trip in the last 24 h (read directly from the relay, also on "
             "imported assets). Red means a problem was found; the machine may still be safe to operate. The only path to red today."},
    {"who": "Live status checks", "status": "planned",
     "rule": "Code, not AI. Turns a dot red when a reading passes a safety parameter, or the asset is down during operational hours."},
    {"who": "AI: case explanation, incident investigation, local model, cloud model", "status": "live, manual and planned",
     "rule": "Advisory only, and diagnostic, not predictive (not enough data). They write notes and reports for an engineer; "
             "they never change a dot."},
]

ESCALATION = {
    "triggers": ["A red finding on a high-criticality asset",
                 "The local model concludes “insufficient evidence”, or its sources conflict",
                 "A pattern the local model has not seen before"],
    "sends": "The related evidence bucket only, with its IDs and source metadata. Never the whole database.",
    "approval": "An engineer approves every escalation (for now).",
    "returns": "An advisory report into the investigation queue.",
}

RUNTIME = ("One Python process (Streamlit) on this machine, with SQLite files in data/. Telemetry is a replayed 48-hour synthetic "
           "scenario analysed in one pass, so “current” means the end of the replay; this is not live monitoring yet. "
           "No outside calls unless case explanation is configured. Cloud escalation is planned and approval-gated.")


def _point_families() -> dict[str, str]:
    """point_id -> sensor family. Point ids map to one quantity family across assets."""
    return {point_id: name for points in POINTS.values() for point_id, spec in points.items()
            for name, quantities in SENSOR_FAMILIES.items() if spec.get("quantity") in quantities}


def _family_points() -> dict[str, list[str]]:
    families: dict[str, list[str]] = {name: [] for name in SENSOR_FAMILIES}
    for asset_id, points in POINTS.items():
        for point_id, spec in points.items():
            for name, quantities in SENSOR_FAMILIES.items():
                if spec.get("quantity") in quantities:
                    families[name].append(f"{asset_id} {point_id}")
    return families


def _n(value: int) -> str:
    return f"{value:,}"


def build(run: dict[str, Any] | None = None, facts: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Return the layered map. Without ``run``/``facts`` the nodes carry no live counts."""
    facts = facts or {}
    dataset = (run or {}).get("dataset", {})
    analysis = (run or {}).get("analysis", {})
    readings = dataset.get("readings", [])
    events = dataset.get("events", [])
    live = run is not None

    families = _point_families()
    per_family = Counter(families.get(str(row.get("point_id"))) for row in readings if isinstance(row, dict))
    family_points = _family_points()
    event_types = Counter(str(row.get("event_type")) for row in events if isinstance(row, dict))
    cases = analysis.get("cases", [])
    findings = [case for case in cases if case.get("category") in {"condition", "trip"}]
    assets = facts.get("assets", [])
    imports = facts.get("imports", [])
    imported = facts.get("imported_readings", [])
    dots = facts.get("dot_counts", {})
    incidents = facts.get("incidents", [])
    reports = sum(len(item.get("reports", [])) for item in incidents)
    aliases = sum(len(asset.get("aliases", [])) for asset in assets)
    vendor_refs = len({str(row.get("equipment_ref", "")).casefold() for row in imports if row.get("equipment_ref")})

    def metric(value: Any, unit: str) -> dict[str, Any]:
        return {"metric": value, "metric_unit": unit} if live else {}

    sources = [
        *({"title": name, "status": "live", "runs_at": "local",
           "text": f"Synthetic replay: {len(family_points[name])} points across the fleet.",
           "detail": "Points: " + ", ".join(family_points[name]), **metric(_n(per_family.get(name, 0)), "readings")}
          for name in SENSOR_FAMILIES),
        {"title": "CMMS work orders", "status": "live", "runs_at": "local",
         "text": "Synthetic 90-day corrective history, plus work orders in the replay.",
         "detail": "Historical orders stay separate from detector evidence.",
         **metric(_n(len((run or {}).get("history", []))), f"orders · {event_types.get('cmms', 0)} in replay")},
        {"title": "Permits to work", "status": "live", "runs_at": "local",
         "text": "Time-bounded context. A permit never suppresses a fault.",
         **metric(_n(event_types.get("ptw", 0)), "in replay")},
        {"title": "Vendor CSV import", "status": "live", "runs_at": "local",
         "text": "Preview every row, then save; a file with any bad row is refused. Shown with provenance, not yet analysed by detectors.",
         **metric(_n(len(imported)), f"readings · {len(imports)} file{'s' if len(imports) != 1 else ''}")},
        {"title": "Controller alarms", "status": "manual",
         "text": "Fault-memory exports, used in incident buckets. Not polled live."},
        {"title": "Reports and technician notes", "status": "manual",
         "text": "Service reports and call-out notes, attached to incident buckets as documents."},
        {"title": "Live feeds", "status": "planned",
         "text": "The end state: every source feeds in continuously through API routing, replacing the replay."},
    ]
    routing = [
        {"title": "Check and hold", "status": "live", "runs_at": "local",
         "text": "Schema, units, plausibility bounds, quality flags and timezone-aware times. Failing replay rows are held with a reason, never repaired.",
         **metric(_n(len(analysis.get("accepted", []))), f"accepted · {len(analysis.get('quarantine', []))} held")},
        {"title": "Match to one asset", "status": "live", "runs_at": "local",
         "text": "Source aliases and vendor equipment references map to one canonical asset ID. Conflicting remaps are rejected.",
         **metric(_n(aliases + vendor_refs), "aliases and vendor refs")},
        {"title": "Time in UTC", "status": "live", "runs_at": "local",
         "text": "Every reading keeps observed and ingested times. A timestamp without a timezone is rejected."},
        {"title": "Provenance", "status": "live", "runs_at": "local",
         "text": "Each imported reading keeps its file, row and SHA-256."},
        {"title": "API routing from source metadata", "status": "planned",
         "text": "Each source declares system, interface, clock, cadence and asset aliases, as in the incident manifest. A router uses that to file records into the right bucket."},
    ]
    platform = [
        {"title": "Asset registry", "status": "live", "runs_at": "local",
         "text": "Built-in assets plus assets added through Data import.",
         **metric(_n(len(assets)), "assets")},
        {"title": "Asset buckets", "status": "live", "runs_at": "local",
         "text": "One per asset: readings, events, work orders and cases on one timeline. Imported assets hold their CSV readings only.",
         **metric(_n(len(assets)), "buckets")},
        {"title": "Local stores", "status": "live", "runs_at": "local",
         "text": "SQLite: imported assets and readings; engineer review decisions.",
         **metric(_n(facts.get("feedback_count", 0)), "reviews saved")},
        {"title": "Incident buckets", "status": "manual",
         "text": "Frozen evidence for one breakdown. A manifest records each source’s clock basis and hash; clocks are aligned by the investigator.",
         **metric(_n(len(incidents)), "incident" + ("s" if len(incidents) != 1 else ""))},
    ]
    diagnostics = [
        {"title": "Detectors", "status": "live", "runs_at": "local",
         "text": f"Deterministic rules on {', '.join(sorted(DETECTOR_ASSET_IDS))}. Other assets are not assessed.",
         **metric(_n(len(findings)), "findings in this replay")},
        {"title": "Data-quality checks", "status": "live", "runs_at": "local",
         "text": "Gaps, stale feeds, late or conflicting rows. A quality problem is reported, never treated as a fault.",
         **metric(_n(len(analysis.get("quality_issues", []))), "issues in this replay")},
        {"title": "Status dots", "status": "live", "runs_at": "local",
         "text": "Red = detector finding or relay trip. Green = checked, no finding. Grey = not assessed, or data missing, stale or failing checks.",
         **metric(f"{dots.get('alert', 0)} · {dots.get('ok', 0)} · {dots.get('idle', 0)}", "red · green · grey")},
        {"title": "Live status checks", "status": "planned",
         "text": "Code, not AI. Red when a reading passes a safety parameter, or the asset is down during operational hours.",
         "detail": "Needs the live feeds, a safety parameter for each point and each asset's operational hours. Diagnostic, not predictive."},
    ]
    ai = [
        {"title": "Case explanation", "status": "live", "runs_at": facts.get("ai_location") or "local",
         "text": "On request only, for eligible equipment cases. Falls back to the offline report.",
         "detail": "The model may only add tentative hypotheses. Observations, numbers and evidence IDs stay deterministic; a reply containing a number falls back to the offline report.",
         **metric("Configured" if facts.get("ai_configured") else "Offline", "")},
        {"title": "Incident investigation", "status": "manual",
         "text": "Fresh AI investigators read one incident bucket and return plausible causes, evidence, gaps and the next check.",
         **metric(_n(reports), "reports")},
        {"title": "Local model: hourly diagnostics", "status": "planned", "runs_at": "on_premises",
         "text": "Reads each asset bucket every hour and writes advisory notes for review.",
         "detail": "Advisory only: it never changes a dot. It can propose an escalation to the cloud model; the rules are below the map."},
        {"title": "Cloud model", "status": "planned", "runs_at": "cloud",
         "text": "Takes escalated cases. Receives the related evidence bucket only, after an engineer approves.",
         "detail": "Triggers: " + "; ".join(item[0].lower() + item[1:] for item in ESCALATION["triggers"]) + "."},
        {"title": "Engineer review", "status": "live", "runs_at": "local",
         "text": "Engineers record review decisions with replay context. Approving escalations is planned.",
         **metric(_n(facts.get("feedback_count", 0)), "reviews")},
    ]
    nodes = {"sources": sources, "routing": routing, "platform": platform, "diagnostics": diagnostics, "ai": ai}
    return [{**layer, "nodes": nodes[layer["id"]]} for layer in LAYERS]


def layer_summary() -> dict[str, list[str]]:
    """Short per-layer lines (title and status) for side-by-side comparisons."""
    return {layer["id"]: [f"{node['title']} ({node['status']})" for node in layer["nodes"]] for layer in build()}
