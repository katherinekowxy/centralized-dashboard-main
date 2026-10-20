"""Equipment layer and sensor identity checks for interactive asset diagrams."""

import json

from demo.engine import POINTS
from demo.schematics import asset_schematic


def test_sensor_selection_maps_to_catalogue_and_layer_filter_survives_serialization():
    for asset_id, points in POINTS.items():
        selected = next(iter(points))
        for view in ("Isometric", "Top", "Side"):
            spec = json.loads(asset_schematic(asset_id, view=view, selected_point=selected).to_json())
            assert all(trace["meta"]["asset_id"] == asset_id for trace in spec["data"])
            sensor = next(trace for trace in spec["data"] if trace["meta"]["layer"] == "Sensors")
            assert set(sensor["customdata"]) == set(points)
            sizes = dict(zip(sensor["customdata"], sensor["marker"]["size"]))
            assert sizes[selected] > max(value for point, value in sizes.items() if point != selected)
        electrical = asset_schematic(asset_id, layers=["Electrical"])
        assert electrical.data
        assert all(trace.meta["layer"] == "Electrical" for trace in electrical.data)
        assert len(asset_schematic(asset_id, layers=[]).data) == 0
