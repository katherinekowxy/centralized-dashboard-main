"""Read-only, cited external research; never an input to demo diagnostics."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse


REFERENCE_DIR = Path(__file__).resolve().parents[2] / "01_Research" / "platform-assessment-2026-10-06"


def load_platforms(directory: Path = REFERENCE_DIR) -> list[dict]:
    """Load the dated research snapshot without network or database access."""
    paths = sorted(directory.glob("*.json"))
    if not paths:
        raise ValueError("The external platform research snapshot is missing.")
    records = []
    seen = set()
    for path in paths:
        record = json.loads(path.read_text(encoding="utf-8-sig"))
        for key in ("id", "name", "checked_on", "summary", "flows", "findings", "unknowns", "sources"):
            if key not in record:
                raise ValueError(f"{path.name}: missing {key}")
        if record["id"] in seen:
            raise ValueError(f"Duplicate platform: {record['id']}")
        seen.add(record["id"])
        sources = {source["id"]: source for source in record["sources"]}
        if not sources or len(sources) != len(record["sources"]):
            raise ValueError(f"{path.name}: missing or duplicate sources")
        for source in sources.values():
            if urlparse(source["url"]).scheme != "https" or not urlparse(source["url"]).netloc:
                raise ValueError(f"{path.name}: source must have an HTTPS URL")
        if not record["flows"]:
            raise ValueError(f"{path.name}: missing infrastructure paths")
        for flow in record["flows"]:
            if not flow["steps"]:
                raise ValueError(f"{path.name}: empty infrastructure path")
            fusion = flow.get("evidence_fusion")
            if fusion is not None:
                if not isinstance(fusion, dict) or fusion.get("status") not in {
                    "Documented fusion", "Multiple sensing types", "Electrical signature analysis"
                }:
                    raise ValueError(f"{path.name}: invalid fusion assessment")
                if (not isinstance(fusion.get("inputs"), list) or not fusion["inputs"]
                        or not all(isinstance(item, str) and item.strip() for item in fusion["inputs"])
                        or not all(isinstance(fusion.get(key), str) and fusion[key].strip()
                                   for key in ("assessment", "limits"))):
                    raise ValueError(f"{path.name}: incomplete fusion evidence")
                citations = fusion.get("source_ids")
                if (not isinstance(citations, list) or not citations
                        or not all(isinstance(item, str) and item in sources for item in citations)):
                    raise ValueError(f"{path.name}: uncited fusion assessment")
            for step in flow["steps"]:
                if step["layer"] not in {"sources", "routing", "platform", "diagnostics", "ai"}:
                    raise ValueError(f"{path.name}: unknown architecture layer")
                if step.get("runs_at", "unknown") not in {"device", "edge", "on_premises", "cloud", "unknown"}:
                    raise ValueError(f"{path.name}: unknown deployment location")
                if not step["source_ids"] or not set(step["source_ids"]) <= sources.keys():
                    raise ValueError(f"{path.name}: uncited infrastructure step")
        for finding in record["findings"]:
            if finding["status"] not in {"Confirmed", "Corrected", "Unverified"}:
                raise ValueError(f"{path.name}: invalid assessment status")
            if not set(finding["source_ids"]) <= sources.keys():
                raise ValueError(f"{path.name}: unknown finding source")
            if finding["status"] != "Unverified" and not finding["source_ids"]:
                raise ValueError(f"{path.name}: uncited finding")
        records.append(record)
    return sorted(records, key=lambda record: record["name"].casefold())
