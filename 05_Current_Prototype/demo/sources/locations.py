"""Building locations for permits: the client's Power BI mapping, applied to free-text permit locations.

Sources
- Aliases: ``assets/maps/ptw_location_aliases.csv``, exported from the report's ``PTW Location Alias`` table.
- Coordinates: ``Building Location.xlsx`` in the data folder (the report's ``PTW Zone`` source). All are marked
  ``Verified = No``. A building without valid coordinates is never given substitute ones; its permits are listed as
  exceptions instead.

Matching, in order
1. ``exact``: the whole location text, tidied (HTML entities decoded, case and spacing ignored, a leading
   "GBB - " style prefix removed), equals an alias.
2. ``text``: one or more aliases appear inside the text as whole words (a trailing plural "s" is allowed), longest
   alias first so "Canopy Hub" wins over "Canopy". A form listing several places maps to several buildings.
3. ``none``: nothing matched; the permit goes to the exception list with its original text.
Words left over after a ``text`` match are reported, so partly recognised locations are visible too.

Several buildings can share one coordinate (for example GBHQ and BMS Room). ``points`` merges them into one map
point, so a permit naming both is drawn and counted once there.
"""

from __future__ import annotations

import csv
import html
import re
from pathlib import Path
from typing import Any

from demo.sources import issue

ALIASES_CSV = Path(__file__).resolve().parents[2] / "assets" / "maps" / "ptw_location_aliases.csv"
BUILDINGS_FILE = "Building Location.xlsx"
PREFIX = re.compile(r"^(gbb|gbtb|gardens by the bay)\s*[-–:]\s*", re.I)
STOPWORDS = {"and", "include", "including", "the", "at", "of", "to", "for", "with", "level", "office", "room", "area",
             "@", "&", "+", "-", "works", "work"}


def tidy(text: Any) -> str:
    """Case-folded, entity-decoded, single-spaced text with a leading site prefix removed."""
    value = "" if text is None else str(text)
    for _ in range(3):  # exports contain double-encoded entities such as "&amp;amp;"
        value = html.unescape(value)
    value = re.sub(r"\s+", " ", value).strip()
    return PREFIX.sub("", value).casefold().strip()


def load_aliases(path: Path = ALIASES_CSV) -> dict[str, str]:
    with path.open(encoding="utf-8", newline="") as handle:
        return {tidy(row["alias"]): row["building"].strip() for row in csv.DictReader(handle) if row.get("alias")}


def load_buildings(folder: Path) -> tuple[dict[str, dict], list[dict]]:
    """Buildings with coordinates from ``Building Location.xlsx``, and the problems found reading it."""
    import pandas as pd

    path = folder / BUILDINGS_FILE
    problems: list[dict] = []
    if not path.is_file():
        return {}, [issue("missing_file", f"{BUILDINGS_FILE} not found; no permit can be placed on the map", file=BUILDINGS_FILE)]
    frame = pd.read_excel(path, sheet_name="Building Location", dtype=object)
    missing = [column for column in ("Building", "Latitude", "Longitude") if column not in frame.columns]
    if missing:
        return {}, [issue("missing_column", f"Missing column(s): {', '.join(missing)}", file=BUILDINGS_FILE)]
    buildings: dict[str, dict] = {}
    for index, row in frame.iterrows():
        name = str(row["Building"]).strip() if pd.notna(row["Building"]) else ""
        excel_row = int(index) + 2
        if not name:
            problems.append(issue("blank_value", "Building name is blank", file=BUILDINGS_FILE, row=excel_row, field="Building"))
            continue
        lat, lon = pd.to_numeric(row["Latitude"], errors="coerce"), pd.to_numeric(row["Longitude"], errors="coerce")
        valid = pd.notna(lat) and pd.notna(lon) and 1.0 < lat < 1.6 and 103.5 < lon < 104.2  # within Singapore
        if not valid:
            problems.append(issue("invalid_value", "Coordinates missing or outside Singapore; building not placed",
                                  file=BUILDINGS_FILE, row=excel_row, field="Latitude/Longitude",
                                  value=f"{row['Latitude']}, {row['Longitude']}"))
        if name in buildings:
            problems.append(issue("duplicate_row", "Building listed twice; the first row is used", file=BUILDINGS_FILE,
                                  row=excel_row, field="Building", value=name))
            continue
        verified = str(row.get("Verified", "")).strip().casefold() == "yes"
        buildings[name] = {"building": name, "lat": float(lat) if valid else None, "lon": float(lon) if valid else None,
                           "verified": verified, "source_row": excel_row}
    return buildings, problems


class Matcher:
    """Matches permit location text to building names using the alias table plus the building names themselves."""

    def __init__(self, aliases: dict[str, str], buildings: dict[str, dict]):
        names = {tidy(name): name for name in buildings}
        self.lookup = {**names, **aliases}
        self.patterns = [(re.compile(rf"(?<![\w-]){re.escape(alias)}s?(?![\w-])"), building)
                         for alias, building in sorted(self.lookup.items(), key=lambda item: -len(item[0]))]

    def match(self, raw: Any) -> dict[str, Any]:
        text = tidy(raw)
        if not text:
            return {"buildings": [], "method": "none", "leftover": []}
        if text in self.lookup:
            return {"buildings": [self.lookup[text]], "method": "exact", "leftover": []}
        taken = [False] * len(text)
        found: list[str] = []
        for pattern, building in self.patterns:
            for hit in pattern.finditer(text):
                if any(taken[hit.start():hit.end()]):
                    continue
                taken[hit.start():hit.end()] = [True] * (hit.end() - hit.start())
                if building not in found:
                    found.append(building)
        rest = "".join(" " if used else char for char, used in zip(text, taken))
        leftover = [part.strip(" .()") for part in re.split(r"[,/;+&]|\band\b|\s-\s", rest)]
        leftover = [part for part in leftover if part and not set(part.split()) <= STOPWORDS and re.search(r"[a-z0-9]", part)]
        return {"buildings": found, "method": "text" if found else "none", "leftover": leftover}


def points(buildings: dict[str, dict]) -> dict[str, dict]:
    """Map points keyed by building: buildings that share a coordinate share one point id and name list."""
    by_coord: dict[tuple[float, float], list[str]] = {}
    for name, item in buildings.items():
        if item["lat"] is not None:
            by_coord.setdefault((round(item["lat"], 6), round(item["lon"], 6)), []).append(name)
    out = {}
    for (lat, lon), names in by_coord.items():
        point = {"point_id": f"{lat:.6f},{lon:.6f}", "lat": lat, "lon": lon, "names": sorted(names),
                 "verified": all(buildings[name]["verified"] for name in names)}
        for name in names:
            out[name] = point
    return out
