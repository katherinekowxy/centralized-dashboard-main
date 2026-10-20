"""Y-axis ranges for trend charts: normal noise reads as calm, real excursions still stand out.

Autoscaling stretches any wobble to fill the chart, so a healthy 229-231 V supply looked as
dramatic as a fault. Magnitudes (currents, power, flow, pressure, vibration) are drawn from a
true zero; voltage and temperature, where zero is meaningless, get a minimum window instead.
"""

from __future__ import annotations

from typing import Iterable

ZERO_BASED_UNITS = {"A", "mA", "kW", "L/s", "kPa", "mm/s"}
TEMPERATURE_UNITS = {"°C", "degC", "C", "℃"}
VOLTAGE_SHARE = 0.10   # ±10 % of the reading, the order of a supply tolerance
TEMPERATURE_HALF = 5.0  # a 10 °C window: sensor noise of a degree stays small
PAD = 1.08


def calm_range(values: Iterable[float], unit: str, band: tuple[float, float] | None = None) -> list[float] | None:
    """Return ``[low, high]`` for the y-axis, or None to leave Plotly's autoscale (unknown units, states)."""
    data = sorted(float(value) for value in [*values, *(band or ())] if value == value)  # drop NaN
    if not data:
        return None
    low, high = data[0], data[-1]
    if unit in ZERO_BASED_UNITS:
        return [0.0, high * PAD or 1.0] if low >= 0 else None
    if unit == "V":
        min_half = abs(data[len(data) // 2]) * VOLTAGE_SHARE
    elif unit in TEMPERATURE_UNITS:
        min_half = TEMPERATURE_HALF
    else:
        return None
    middle, half = (low + high) / 2, max(min_half, (high - low) / 2 * PAD)
    return [middle - half, middle + half]
