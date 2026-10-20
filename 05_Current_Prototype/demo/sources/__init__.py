"""Read-only adapters for real Gardens by the Bay files (Excel exports), kept apart from the synthetic data.

Each adapter maps source columns explicitly, keeps the original values next to the cleaned ones, and returns a
validation report instead of dropping rows it cannot use. Nothing here writes to a database or calls a service.
Records from these adapters are labelled "imported", never "live", and are never mixed with synthetic records.

The folder holding the files is set with the ``GBB_DATA_DIR`` environment variable, so real data (which contains
personal details) stays outside this repository. When it is unset, pages show that real data is not configured.
"""

from __future__ import annotations

import os
from pathlib import Path

ENV_VAR = "GBB_DATA_DIR"


def data_dir() -> Path | None:
    """The configured folder of real files, or None when it is unset or missing."""
    value = os.environ.get(ENV_VAR, "").strip().strip('"')
    if not value:
        return None
    path = Path(value).expanduser()
    return path if path.is_dir() else None


def issue(kind: str, detail: str, *, file: str = "", row: int | None = None, field: str = "", value: object = None,
          ref: str = "") -> dict:
    """One validation finding. ``row`` is the spreadsheet row number as a person would see it in Excel."""
    return {"issue": kind, "detail": detail, "file": file, "row": row, "field": field,
            "value": "" if value is None else str(value), "ref": ref}
