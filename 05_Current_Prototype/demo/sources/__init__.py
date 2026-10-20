"""Read-only adapters for real Gardens by the Bay files (Excel exports), kept apart from the synthetic data.

Each adapter maps source columns explicitly, keeps the original values next to the cleaned ones, and returns a
validation report instead of dropping rows it cannot use. Nothing here writes to a database or calls a service.
Records from these adapters are labelled "imported", never "live", and are never mixed with synthetic records.

The folders holding the files are set with the ``GBB_DATA_DIR`` environment variable, so real data (which contains
personal details) stays outside this repository. Several folders can be listed, separated by ";": the first is
searched first, so a newer export there replaces an older one elsewhere. When unset, pages say real data is not
configured.
"""

from __future__ import annotations

import os
from pathlib import Path

ENV_VAR = "GBB_DATA_DIR"


def data_dirs() -> list[Path]:
    """Every configured folder that exists, in priority order."""
    parts = [part.strip().strip('"') for part in os.environ.get(ENV_VAR, "").split(";")]
    return [Path(part).expanduser() for part in parts if part and Path(part).expanduser().is_dir()]


def data_dir() -> Path | None:
    """The first configured folder, or None when none is set or found."""
    dirs = data_dirs()
    return dirs[0] if dirs else None


def folder_with(relative: str) -> Path | None:
    """The first configured folder containing ``relative`` (a file or a subfolder)."""
    return next((folder for folder in data_dirs() if (folder / relative).exists()), None)


def newest(pattern: str) -> Path | None:
    """The most recently modified file matching ``pattern`` (for example "fault*.xlsx") in any configured folder."""
    found = [path for folder in data_dirs() for path in folder.glob(pattern) if path.is_file() and not path.name.startswith("~$")]
    return max(found, key=lambda path: path.stat().st_mtime) if found else None


def issue(kind: str, detail: str, *, file: str = "", row: int | None = None, field: str = "", value: object = None,
          ref: str = "") -> dict:
    """One validation finding. ``row`` is the spreadsheet row number as a person would see it in Excel."""
    return {"issue": kind, "detail": detail, "file": file, "row": row, "field": field,
            "value": "" if value is None else str(value), "ref": ref}
