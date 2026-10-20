"""Conceptual, synthetic 3D equipment schematics for the five demo assets.

The geometry is handcrafted for navigation and point discovery. It is not CAD,
as-built documentation, a wiring diagram, or a statement of installed hardware.
Sensor IDs come directly from :mod:`demo.engine`'s point catalog.
"""

from __future__ import annotations

from collections import defaultdict
from math import cos, pi, sin

import plotly.graph_objects as go

from demo.engine import ASSETS, POINTS


LAYERS = ("Equipment", "Piping / air", "Electrical", "Sensors")
VIEWS = ("Isometric", "Top", "Side")

_NAVY = "#F5F6F7"  # canvas (brand.SURFACE_2); the name is historical
_BLUE = "#3F4D5A"
_BLUE_DIM = "#8A97A3"
_FLOW = "#7C3AED"  # pipes and air flow; never a status colour
_AMBER = "#A16207"  # conductors (copper), not the warning amber
_SENSOR = "#4D7C0F"
_SELECTED = "#E2124F"  # selection uses the brand pink


class _Drawing:
    """Collect polylines by layer and style to keep the Plotly figure light."""

    def __init__(self) -> None:
        self.lines: dict[tuple[str, str, int], list[tuple[float, float, float] | None]] = defaultdict(list)
        self.labels: dict[str, list[tuple[float, float, float, str]]] = defaultdict(list)
        self.sensors: dict[str, tuple[float, float, float]] = {}

    def path(self, layer: str, points: list[tuple[float, float, float]],
             color: str | None = None, width: int = 3) -> None:
        if len(points) < 2:
            return
        color = color or (_BLUE if layer == "Equipment" else _FLOW if layer == "Piping / air" else _AMBER)
        self.lines[layer, color, width].extend([*points, None])

    def label(self, layer: str, text: str, at: tuple[float, float, float]) -> None:
        self.labels[layer].append((*at, text))

    def sensor(self, point_id: str, at: tuple[float, float, float]) -> None:
        self.sensors[point_id] = at

    def box(self, x0: float, x1: float, y0: float, y1: float, z0: float, z1: float,
            color: str = _BLUE, width: int = 3) -> None:
        for y in (y0, y1):
            self.path("Equipment", [(x0, y, z0), (x1, y, z0), (x1, y, z1),
                                     (x0, y, z1), (x0, y, z0)], color, width)
        for x in (x0, x1):
            for z in (z0, z1):
                self.path("Equipment", [(x, y0, z), (x, y1, z)], color, width)

    def cylinder_x(self, x0: float, x1: float, y: float, z: float, radius: float,
                   color: str = _BLUE, width: int = 3, rings: int = 3,
                   segments: int = 28) -> None:
        for i in range(rings):
            x = x0 + (x1 - x0) * i / (rings - 1) if rings > 1 else x0
            self.path("Equipment", [(x, y + radius * cos(2 * pi * j / segments),
                                     z + radius * sin(2 * pi * j / segments))
                                    for j in range(segments + 1)], color, width)
        for j in range(0, segments, 4):
            a = 2 * pi * j / segments
            self.path("Equipment", [(x0, y + radius * cos(a), z + radius * sin(a)),
                                     (x1, y + radius * cos(a), z + radius * sin(a))], color, width)

    def arrow(self, layer: str, start: tuple[float, float, float],
              end: tuple[float, float, float], color: str | None = None,
              width: int = 5) -> None:
        self.path(layer, [start, end], color, width)
        dx, dy, dz = (end[i] - start[i] for i in range(3))
        length = (dx * dx + dy * dy + dz * dz) ** .5
        if length == 0:
            return
        ux, uy, uz = dx / length, dy / length, dz / length
        # A stable side vector for near-vertical arrows.
        sx, sy, sz = (-uy, ux, 0) if abs(uz) < .9 else (1, 0, 0)
        scale = .24
        self.path(layer, [(end[0] - ux * scale + sx * scale * .55,
                           end[1] - uy * scale + sy * scale * .55,
                           end[2] - uz * scale + sz * scale * .55), end,
                          (end[0] - ux * scale - sx * scale * .55,
                           end[1] - uy * scale - sy * scale * .55,
                           end[2] - uz * scale - sz * scale * .55)], color, width)


def _base(d: _Drawing, x0: float, x1: float, y0: float, y1: float) -> None:
    d.box(x0, x1, y0, y1, -.22, 0, _BLUE_DIM, 2)
    for x in (x0 + .35, x1 - .35):
        for y in (y0 + .3, y1 - .3):
            d.path("Equipment", [(x, y, -.22), (x, y, .05)], _BLUE_DIM, 2)


def _distribution_board(d: _Drawing) -> None:
    _base(d, -2.7, 2.7, -.95, .95)
    d.box(-2.5, 2.5, -.75, .75, 0, 4.2)
    # Open-front visual: door divisions, meters and breaker bays.
    for x in (-.85, .8):
        d.path("Equipment", [(x, -.78, .1), (x, -.78, 4.08)], _BLUE, 3)
    for z in (1.05, 2.15, 3.25):
        d.path("Equipment", [(-2.45, -.8, z), (2.45, -.8, z)], _BLUE_DIM, 2)
    for x in (-1.72, -.07, 1.57):
        d.box(x - .42, x + .42, -.88, -.77, 1.32, 1.9, _BLUE_DIM, 2)
        d.box(x - .42, x + .42, -.88, -.77, 2.42, 3.0, _BLUE_DIM, 2)
    d.box(-2.14, -1.14, -.92, -.79, 3.48, 3.98, _BLUE, 2)
    d.box(-.48, .38, -.92, -.79, 3.48, 3.98, _BLUE, 2)
    d.label("Equipment", "LV BOARD", (-2.35, -.84, 4.45))
    d.label("Equipment", "RELAY", (-1.95, -1.03, 3.78))
    d.label("Equipment", "METER", (-.34, -1.03, 3.78))
    # Three phase busbars, neutral bar, and feeder branches.
    for x in (-1.15, -.73, -.31):
        d.path("Electrical", [(x, .04, 3.9), (x, .04, .55)], _AMBER, 5)
        for z in (2.68, 1.57):
            d.path("Electrical", [(x, .04, z), (x + .28, -.68, z),
                                   (x + .28, -.84, z)], _AMBER, 3)
    d.path("Electrical", [(.42, .12, 3.84), (.42, .12, .5)], _FLOW, 4)
    for x in (1.1, 1.6, 2.1):
        d.path("Electrical", [(-.31, .04, 2.68), (x, .04, 2.68),
                               (x, -.68, 2.68)], _AMBER, 3)
    d.path("Electrical", [(-3.55, .2, 4.55), (-2.1, .2, 4.55),
                           (-2.1, .2, 3.92)], _AMBER, 5)
    d.label("Electrical", "INCOMING FEED", (-3.65, .2, 4.85))
    # Cabinet ventilation, explicitly air rather than water.
    for x in (-1.7, -.9, -.1, .7, 1.5):
        d.path("Equipment", [(x, .77, 3.83), (x + .42, .77, 3.83)], _BLUE_DIM, 2)
    d.arrow("Piping / air", (2.93, -.12, .48), (2.93, -.12, 1.28), _FLOW, 3)
    d.arrow("Piping / air", (2.93, -.12, 2.75), (2.93, -.12, 3.55), _FLOW, 3)
    d.label("Piping / air", "VENTILATION AIR", (3.02, -.1, 2.2))
    for point, at in {
        "leakage_ma": (-1.6, -1.03, 3.77),
        "relay_trip": (-2.1, -1.03, 3.53),
        "phase_voltage_v": (-.1, -1.04, 3.76),
        "phase_current_a": (.32, -1.04, 3.76),
        "neutral_current_a": (.43, -.2, .78),
    }.items():
        d.sensor(point, at)


def _ahu(d: _Drawing) -> None:
    _base(d, -4.65, 4.65, -1.55, 1.55)
    d.box(-4.4, 4.4, -1.25, 1.25, .12, 2.85)
    for x in (-2.75, -.55, 1.85):
        d.path("Equipment", [(x, -1.26, .12), (x, -1.26, 2.85),
                               (x, 1.26, 2.85), (x, 1.26, .12)], _BLUE_DIM, 2)
    # Filter bank, finned coil, and housed supply fan.
    for z in (.55, .95, 1.35, 1.75, 2.15, 2.55):
        d.path("Equipment", [(-3.55, -1.29, z), (-3.1, -1.29, z + .18)], _BLUE_DIM, 2)
    for x in (-1.95, -1.6, -1.25, -.9):
        d.path("Equipment", [(x, -1.3, .4), (x, -1.3, 2.58)], _BLUE, 2)
    d.cylinder_x(2.25, 3.05, 0, 1.48, .9, _BLUE, 3)
    for a in range(0, 360, 60):
        t = a * pi / 180
        d.path("Equipment", [(3.07, 0, 1.48),
                               (3.08, .7 * cos(t), 1.48 + .7 * sin(t)),
                               (3.08, .84 * cos(t + .32), 1.48 + .84 * sin(t + .32))], _BLUE, 3)
    d.label("Equipment", "FILTER", (-3.95, -1.38, 3.05))
    d.label("Equipment", "COIL", (-1.9, -1.38, 3.05))
    d.label("Equipment", "SUPPLY FAN", (2.1, -1.38, 3.05))
    # Duct air movement and the coil's two short water connections.
    for z in (1.0, 1.95):
        d.arrow("Piping / air", (-5.05, 0, z), (-3.72, 0, z), _FLOW)
        d.arrow("Piping / air", (3.65, 0, z), (5.05, 0, z), _FLOW)
    d.path("Piping / air", [(-1.75, 1.28, .5), (-1.75, 2.15, .5),
                            (-2.35, 2.15, .5)], _FLOW, 5)
    d.path("Piping / air", [(-1.05, 1.28, 2.35), (-1.05, 2.15, 2.35),
                            (-.45, 2.15, 2.35)], _FLOW, 5)
    d.label("Piping / air", "RETURN AIR", (-5.05, .3, 2.48))
    d.label("Piping / air", "SUPPLY AIR", (3.78, .3, 2.48))
    d.path("Electrical", [(2.6, 2.2, -.08), (2.6, 1.35, -.08),
                           (2.6, 1.35, 1.4)], _AMBER, 5)
    d.label("Electrical", "FAN MOTOR FEED", (2.55, 2.25, .15))
    for point, at in {
        "return_temp_c": (-4.76, -.4, 2.14),
        "supply_temp_c": (4.73, -.4, 2.14),
        "fan_current_a": (2.6, 1.4, 1.43),
    }.items():
        d.sensor(point, at)


def _fan(d: _Drawing) -> None:
    _base(d, -3.25, 3.25, -1.65, 1.65)
    d.cylinder_x(-1.35, 1.35, 0, 1.62, 1.28, _BLUE, 4, 4)
    d.cylinder_x(1.65, 2.65, 0, 1.62, .56, _BLUE, 3, 3)
    d.path("Equipment", [(1.36, 0, 1.62), (1.7, 0, 1.62)], _BLUE, 5)
    # Rotor hub and six swept blades, visible through the near opening.
    d.cylinder_x(-.45, -.35, 0, 1.62, .22, _BLUE, 3, 2)
    for i in range(6):
        t = i * pi / 3
        d.path("Equipment", [(-.48, .18 * cos(t), 1.62 + .18 * sin(t)),
                               (-.48, .62 * cos(t + .22), 1.62 + .62 * sin(t + .22)),
                               (-.48, 1.05 * cos(t + .5), 1.62 + 1.05 * sin(t + .5))], _BLUE, 5)
    for x in (-.9, .95):
        d.path("Equipment", [(x, -.9, .46), (x, -.9, .02)], _BLUE_DIM, 3)
        d.path("Equipment", [(x, .9, .46), (x, .9, .02)], _BLUE_DIM, 3)
    d.label("Equipment", "AXIAL FAN", (-1.2, -1.4, 3.17))
    d.label("Equipment", "MOTOR", (1.85, -1.0, 2.55))
    for z in (1.16, 1.62, 2.08):
        d.arrow("Piping / air", (-3.5, 0, z), (-2.1, 0, z), _FLOW, 4)
        d.arrow("Piping / air", (2.7, 0, z), (4.15, 0, z), _FLOW, 4)
    d.label("Piping / air", "EXHAUST AIR", (2.7, .25, 2.85))
    d.path("Electrical", [(3.25, 1.75, -.05), (2.23, 1.75, -.05),
                           (2.23, .5, 1.62)], _AMBER, 5)
    d.label("Electrical", "MOTOR FEED", (3.15, 1.85, .2))
    for point, at in {
        "motor_current_a": (2.25, .65, 1.72),
        "bearing_temp_c": (1.5, -.18, 1.64),
        "vibration_mm_s": (.95, -1.03, .67),
    }.items():
        d.sensor(point, at)


def _pump(d: _Drawing) -> None:
    _base(d, -3.65, 3.65, -1.9, 1.9)
    d.cylinder_x(-2.8, -.45, 0, 1.2, .78, _BLUE, 3, 4)
    for x in (-2.45, -2.1, -1.75, -1.4, -1.05):
        d.cylinder_x(x, x, 0, 1.2, .83, _BLUE_DIM, 2, 1)
    d.cylinder_x(-.42, .25, 0, 1.2, .29, _BLUE, 3, 2)
    # Pump casing: impeller eye, volute rings and expanding spiral.
    d.cylinder_x(.27, 1.08, 0, 1.2, 1.02, _BLUE, 4, 3)
    d.cylinder_x(1.09, 1.18, 0, 1.2, .38, _BLUE, 3, 2)
    d.path("Equipment", [(1.2, (.2 + .78 * j / 45) * cos(j * 4.3 * pi / 45),
                           1.2 + (.2 + .78 * j / 45) * sin(j * 4.3 * pi / 45))
                          for j in range(46)], _BLUE_DIM, 2)
    d.box(-2.45, -1.0, -.75, .75, .02, .3, _BLUE_DIM, 2)
    d.box(.38, 1.15, -.8, .8, .02, .3, _BLUE_DIM, 2)
    d.label("Equipment", "MOTOR", (-2.7, -.95, 2.3))
    d.label("Equipment", "VOLUTE CASING", (.2, -1.2, 2.75))
    # Suction enters from the front; discharge rises from the casing.
    d.path("Piping / air", [(1.1, -2.85, 1.2), (1.1, -.9, 1.2)], _FLOW, 6)
    for y in (-2.5, -1.15):
        d.path("Piping / air", [(1.1 + .42 * cos(2 * pi * j / 24), y,
                                 1.2 + .42 * sin(2 * pi * j / 24)) for j in range(25)], _FLOW, 2)
    d.path("Piping / air", [(.68, .35, 2.12), (.68, .35, 3.38),
                            (2.85, .35, 3.38)], _FLOW, 6)
    d.arrow("Piping / air", (2.02, .35, 3.38), (2.78, .35, 3.38), _FLOW, 4)
    d.label("Piping / air", "SUCTION", (1.24, -3.05, 1.5))
    d.label("Piping / air", "DISCHARGE", (2.05, .5, 3.75))
    d.path("Electrical", [(-3.6, 1.82, -.02), (-1.75, 1.82, -.02),
                           (-1.75, .72, 1.25)], _AMBER, 5)
    d.label("Electrical", "MOTOR FEED", (-3.45, 2.0, .3))
    for point, at in {
        "motor_current_a": (-1.75, .86, 1.33),
        "bearing_temp_c": (-.25, -.35, 1.32),
        "vibration_mm_s": (.72, -.88, .44),
        "differential_pressure_kpa": (1.65, .35, 3.38),
    }.items():
        d.sensor(point, at)


def _chiller(d: _Drawing) -> None:
    _base(d, -4.15, 4.15, -2.05, 2.05)
    # Two horizontal heat exchanger shells and a compressor above them.
    d.cylinder_x(-3.35, 3.35, -1.02, 1.0, .67, _BLUE, 3, 5)
    d.cylinder_x(-3.35, 3.35, 1.02, 1.0, .67, _BLUE, 3, 5)
    d.cylinder_x(-1.05, 1.25, 0, 2.43, .66, _BLUE, 4, 4)
    for x in (-2.75, 2.75):
        for y in (-1.02, 1.02):
            d.path("Equipment", [(x, y - .57, .48), (x, y - .57, .02),
                                   (x, y + .57, .02), (x, y + .57, .48)], _BLUE_DIM, 2)
    d.path("Equipment", [(-1.05, 0, 2.43), (-1.6, 0, 2.43)], _BLUE, 4)
    d.box(2.45, 3.55, -2.18, -1.6, .12, 2.5, _BLUE, 2)
    for z in (.48, .86, 1.24, 1.62):
        d.path("Equipment", [(2.62, -2.2, z), (3.38, -2.2, z)], _BLUE_DIM, 2)
    d.label("Equipment", "COMPRESSOR", (-1.1, -.8, 3.42))
    d.label("Equipment", "EVAPORATOR", (-2.5, -1.95, 1.85))
    d.label("Equipment", "CONDENSER", (-2.5, .4, 1.85))
    d.label("Equipment", "CONTROL CABINET", (2.35, -2.45, 2.8))
    # Chilled-water headers: two distinct ports on the evaporator shell.
    d.path("Piping / air", [(-4.7, -1.0, 1.0), (-3.38, -1.0, 1.0)], _FLOW, 6)
    d.path("Piping / air", [(3.35, -1.0, 1.0), (4.7, -1.0, 1.0)], _FLOW, 6)
    d.arrow("Piping / air", (-4.55, -1.0, 1.0), (-3.65, -1.0, 1.0), _FLOW, 4)
    d.arrow("Piping / air", (3.65, -1.0, 1.0), (4.55, -1.0, 1.0), _FLOW, 4)
    # Conceptual refrigerant connection between shells and compressor.
    d.path("Piping / air", [(-2.05, -1.02, 1.65), (-2.05, -1.02, 2.38),
                            (-1.12, -1.02, 2.38)], _FLOW, 3)
    d.path("Piping / air", [(1.25, .34, 2.55), (1.75, 1.02, 2.55),
                            (1.75, 1.02, 1.66)], _FLOW, 3)
    d.label("Piping / air", "CHW RETURN", (-4.75, -1.15, 1.55))
    d.label("Piping / air", "CHW SUPPLY", (3.52, -1.15, 1.55))
    d.path("Electrical", [(4.75, -2.1, .28), (3.5, -2.1, .28),
                           (3.5, -2.1, 1.0)], _AMBER, 5)
    d.path("Electrical", [(2.65, -1.6, 2.05), (1.8, -.2, 2.05),
                           (1.25, -.2, 2.05)], _AMBER, 4)
    d.label("Electrical", "POWER FEED", (4.02, -2.25, .6))
    for point, at in {
        "power_kw": (3.55, -2.28, 1.82),
        "supply_temp_c": (4.05, -1.0, 1.13),
        "return_temp_c": (-4.05, -1.0, 1.13),
        "flow_l_s": (-3.55, -1.0, 1.13),
    }.items():
        d.sensor(point, at)


_DRAW = {
    "DB-01": _distribution_board,
    "AHU-01": _ahu,
    "FAN-01": _fan,
    "PUMP-01": _pump,
    "CHILLER-01": _chiller,
}


def asset_schematic(asset_id: str, layers: list[str] | None = None,
                    view: str = "Isometric", selected_point: str | None = None,
                    point_colors: dict[str, str] | None = None, height: int = 520,
                    show_labels: bool = True) -> go.Figure:
    """Return a rotatable schematic with layer control and catalogued point markers.

    ``selected_point`` highlights and labels one sensor; other names stay in hover
    so close sensors do not overprint. ``point_colors`` optionally colours each
    sensor marker (e.g. by display status). With ``show_labels=False`` part names
    become small hover markers instead of printed text, for compact views.
    The selectable layer names are in :data:`LAYERS` and camera names in
    :data:`VIEWS`. This function has no telemetry or session state.
    """
    if asset_id not in _DRAW:
        raise ValueError(f"Unknown asset: {asset_id}")
    if view not in VIEWS:
        raise ValueError(f"Unknown schematic view: {view}")
    active = set(LAYERS if layers is None else layers)
    invalid = active - set(LAYERS)
    if invalid:
        raise ValueError(f"Unknown schematic layer(s): {', '.join(sorted(invalid))}")
    drawing = _Drawing()
    _DRAW[asset_id](drawing)
    if set(drawing.sensors) != set(POINTS[asset_id]):
        raise RuntimeError(f"Schematic point mapping out of sync for {asset_id}")

    fig = go.Figure()
    for (layer, color, width), coords in drawing.lines.items():
        if layer not in active:
            continue
        fig.add_trace(go.Scatter3d(
            x=[p[0] if p else None for p in coords],
            y=[p[1] if p else None for p in coords],
            z=[p[2] if p else None for p in coords],
            mode="lines", line=dict(color=color, width=width),
            hoverinfo="skip", showlegend=False, name=layer,
            meta=dict(layer=layer, asset_id=asset_id),
        ))
    for layer, entries in drawing.labels.items():
        if layer not in active:
            continue
        color = _BLUE if layer == "Equipment" else _FLOW if layer == "Piping / air" else _AMBER
        fig.add_trace(go.Scatter3d(
            x=[e[0] for e in entries], y=[e[1] for e in entries],
            z=[e[2] for e in entries], text=[e[3] for e in entries],
            mode="text" if show_labels else "markers", textfont=dict(color=color, size=11),
            marker=dict(size=4, color=color, opacity=.7, symbol="diamond"),  # never a circle: circles are status dots
            hoverinfo="skip" if show_labels else "text", showlegend=False, name=layer,
            meta=dict(layer=layer, asset_id=asset_id),
        ))
    if "Sensors" in active:
        points = list(POINTS[asset_id])
        fig.add_trace(go.Scatter3d(
            x=[drawing.sensors[p][0] for p in points],
            y=[drawing.sensors[p][1] for p in points],
            z=[drawing.sensors[p][2] for p in points],
            mode="markers+text", text=[p.replace("_", " ").upper() if p == selected_point else "" for p in points],
            customdata=points, textposition="top center",
            textfont=dict(color="#24272A", size=11),
            marker=dict(size=[12 if p == selected_point else 7 for p in points],
                        color=[(point_colors or {}).get(p) or (_SELECTED if p == selected_point else _SENSOR) for p in points],
                        symbol="circle", line=dict(color=_NAVY, width=1)),
            hovertemplate="<b>%{customdata}</b><br>" + asset_id + "<extra></extra>",
            showlegend=False, name="Sensors",
            meta=dict(layer="Sensors", asset_id=asset_id),
        ))
    camera = {
        "Isometric": dict(eye=dict(x=1.55, y=-1.75, z=1.15)),
        "Top": dict(eye=dict(x=.02, y=.02, z=2.5), up=dict(x=0, y=1, z=0)),
        "Side": dict(eye=dict(x=.02, y=-2.5, z=.28)),
    }[view]
    asset_name = next(a["name"] for a in ASSETS if a["asset_id"] == asset_id)
    fig.update_layout(
        paper_bgcolor=_NAVY, plot_bgcolor=_NAVY,
        margin=dict(l=0, r=0, t=45, b=0), height=height,
        title=dict(text=f"{asset_name}  ·  ILLUSTRATIVE SCHEMATIC, NOT A CAD / BIM OR INSTALLATION DRAWING",
                   font=dict(color="#24272A", size=14), x=.02, y=.98),
        scene=dict(
            bgcolor=_NAVY, camera=camera, dragmode="orbit", aspectmode="data",
            xaxis=dict(visible=False, showbackground=False),
            yaxis=dict(visible=False, showbackground=False),
            zaxis=dict(visible=False, showbackground=False),
        ),
        uirevision=f"{asset_id}:{view}",
        font=dict(family="Segoe UI, Arial, sans-serif", color="#24272A"),
    )
    return fig
