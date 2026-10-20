# Bay South map

**12 October 2026:** the PTW dashboard now uses OpenStreetMap, because Dan found the attraction map hard to read. Zone outlines are in `bay-south-zones.geojson`: 17 come from OpenStreetMap (© OpenStreetMap contributors, ODbL) and 7 are estimated by Claude and marked `approximate`. The map tiles load from tile.openstreetmap.org at view time. Google Maps would need a Google Maps Platform API key from Gardens by the Bay IT, and would replace only the tile layer. The official map below is kept for reference but is no longer shown.

- File: `05_Current_Prototype/static/maps/gbtb-bay-south-2026-02-15.jpg` (2599 × 1772 px), served by Streamlit at `app/static/maps/`. A 1300 px copy (`…-1300.jpg`) is for phones.
- Zone boxes: `bay-south-zones.json` in this folder, measured on the full-size image.
- Source: Gardens by the Bay, "Gardens Map", https://www.gardensbythebay.com.sg/en/plan-your-visit/gardens-map.html (download "GB-Map-15-02-2026.jpg"), retrieved 10 October 2026.
- SHA-256: `382aa696fc7fa38f1596997d79cf484d49edd59b8295b482e7fd79e5c10737e4`
- © Gardens by the Bay. Used internally by Gardens by the Bay staff (Dan) for this demo. Do not publish or include in a public portfolio without permission.
- It is the only real (non-synthetic) data in the site dashboards.
