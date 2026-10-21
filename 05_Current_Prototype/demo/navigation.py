"""Information architecture: six areas, one entry per page, and what each page's status means.

Every page says where its numbers come from (``source``) and which status vocabulary it shows (``status``), so the
operational asset state, diagnostic findings, engineering measurements, work-order status, PTW status and data-source
status are never mistaken for one another. Pages are addressed by a stable ``key`` that also appears in the URL
(``?view=<key>``), so any page can be bookmarked or put on a display.

The site pages read the synthetic site database (demo/site_db.py). The diagnostics pages read a replayed synthetic
scenario (demo/engine.py) with its own five demonstration assets. The two datasets do not share asset IDs, so pages
from different sources are kept apart rather than merged.
"""

from __future__ import annotations

from dataclasses import dataclass

SITE, REPLAY, MIXED, IMPORTED, REFERENCE, NONE = "site", "replay", "mixed", "imported", "reference", "none"
SOURCE_LABEL = {
    SITE: "Site operations data · demo / synthetic",
    REPLAY: "Diagnostics replay · demo / synthetic scenario",
    MIXED: "Site operations + diagnostics replay · demo / synthetic",
    IMPORTED: "Imported files · not live",
    REFERENCE: "External reference material · not integrated",
    NONE: "",
}


@dataclass(frozen=True)
class Page:
    key: str
    label: str
    area: str
    source: str
    status: str            # the one status vocabulary this page shows, in words
    summary: str           # one line: the question the page answers
    module: str = ""       # site module rendered by this page, if any
    replay_page: str = ""  # name used inside the diagnostics workbench, if any
    secondary: bool = False
    client: bool = False   # shown in the client view; the rest are internal, engineering or demo pages


AREAS = ("Site Overview", "Permits & Safety", "Asset Health & Engineering", "Faults & Investigations",
         "Operations & Planning", "Administration & Integrations")

PAGES = (
    Page("overview", "Site overview", "Site Overview", MIXED, "Summary across the areas below; each figure keeps its own meaning",
         "What needs attention across the site right now?", client=True),
    Page("ptw-map", "PTW map", "Permits & Safety", SITE, "PTW timing: active now or later today. Not a risk rating",
         "Where are permits to work today, and what do they isolate or close?", module="ptw_dashboard", client=True),
    Page("permits", "Tool-box meetings", "Permits & Safety", IMPORTED, "Safety briefings held by date, site and contractor",
         "Which tool-box meetings were recorded, and when?", client=True),
    Page("spares", "Inventories", "Asset Health & Engineering", IMPORTED, "Stock against each item's minimum: out, below minimum, OK",
         "Which items are available, low or out of stock?", client=True),
    Page("smart-assets", "Smart asset sample", "Asset Health & Engineering", REPLAY,
         "Synthetic prototype telemetry; illustrative thresholds, not live site data",
         "How do sample motor readings and events change over time?", client=True),
    Page("assets", "Asset overview", "Asset Health & Engineering", MIXED,
         "Operational state (site assets) and diagnostic findings (replay assets), in separate columns",
         "Which assets exist in each category, and which need attention in their own terms?"),
    Page("asset-status", "Asset status", "Asset Health & Engineering", SITE,
         "Operational asset state: Running, Idle, Warning, Down, Offline",
         "Which equipment does each location hold, and which boards and devices are down?", module="asset_dashboard"),
    Page("diagnostics", "Diagnostics", "Asset Health & Engineering", REPLAY,
         "Diagnostic findings: detector finding, checked with no finding, not assessed",
         "Which monitored assets have a rule-based detector finding?", replay_page="Overview"),
    Page("asset-engineering", "Measurements", "Asset Health & Engineering", REPLAY,
         "Engineering measurements with units, and the diagnostic finding for each channel",
         "What do earth leakage, trips, voltage, current and process readings show for one asset?",
         replay_page="Asset overview"),
    Page("work-orders", "Work orders", "Faults & Investigations", REPLAY,
         "Work-order status: Open, In progress, Closed",
         "Which faults recur, and what corrective work is open?", replay_page="Maintenance"),
    Page("fault-log", "Faults & requests", "Faults & Investigations", IMPORTED,
         "Fault state as at the export: Open, In progress, Completed, Cancelled. Impact as recorded, not a severity",
         "Which faults are open now, and how fast are they handled?", client=True),
    Page("investigations", "Investigations", "Faults & Investigations", REPLAY,
         "Detector cases with evidence, review decisions, data-quality issues and provenance",
         "Which cases need review, and what is the evidence?", replay_page="Investigate"),
    Page("event-power", "Event power", "Operations & Planning", SITE, "Socket state: In use, Free, Warning, Tripped, No supply",
         "Which event sockets are in use, and is any event without power?", module="event_power", client=True),
    Page("calendar", "Events calendar", "Operations & Planning", SITE,
         "Imported event orders, or the demo's planned permits, events and maintenance with clashes marked",
         "What is planned this week, and where do permits and events overlap?", module="calendar_overview", client=True),
    Page("rooms", "Room booking", "Operations & Planning", SITE, "Room availability: In use or Free",
         "Book or cancel a meeting room.", module="room_booking", secondary=True),
    Page("assets-import", "Data import", "Administration & Integrations", REPLAY,
         "Import validation: ready, duplicate, error",
         "Register an asset and validate a vendor CSV before saving it.", replay_page="Data import"),
    Page("displays", "Screens", "Administration & Integrations", MIXED,
         "Which display each 55-inch screen shows, and the address for each screen and for the 2x2 wall",
         "Assign displays to the four screens, preview them and open presentation mode."),
    Page("demo-workspace", "Display wall", "Administration & Integrations", NONE,
         "Arrange four live page previews for a 2×2 display wall",
         "Which four pages should appear on the display wall?", client=True),
    Page("architecture", "Platform architecture", "Administration & Integrations", REPLAY,
         "Data-source status: Live, Manual, Planned (border style, not colour)",
         "How does data reach this application, and what is planned?", replay_page="System map"),
    Page("research", "Platform research", "Administration & Integrations", REFERENCE,
         "Reference material only; none of these platforms is integrated",
         "How do external monitoring platforms document their architecture?", replay_page="Exploratory"),
)

PAGE = {page.key: page for page in PAGES}
DEFAULT = "overview"
BY_REPLAY_PAGE = {page.replay_page: page.key for page in PAGES if page.replay_page}
REPLAY_PAGES = tuple(BY_REPLAY_PAGE)


ALIASES = {"electrical": "asset-status"}  # Electrical is now a view inside Asset status


def resolve(key: object) -> str:
    """A known page key, or the landing page for anything else (an old or mistyped bookmark)."""
    key = ALIASES.get(key, key) if isinstance(key, str) else key
    return key if isinstance(key, str) and key in PAGE else DEFAULT


def area_pages(area: str, secondary: bool = False, client_only: bool = False) -> list[Page]:
    return [page for page in PAGES if page.area == area and page.secondary == secondary and (page.client or not client_only)]
