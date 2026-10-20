"""Trend y-ranges: healthy noise stays small, real rises still fill the chart."""

from demo.chart_scale import calm_range


def test_healthy_voltage_noise_uses_a_tolerance_window() -> None:
    low, high = calm_range([229.0, 230.6, 229.4, 231.0], "V")
    assert high - low >= 45  # about ±10 %, so a 2 V wobble uses under a twentieth of the chart
    assert low < 229.0 and high > 231.0


def test_magnitudes_start_at_zero_and_a_real_rise_still_fills_the_chart() -> None:
    low, high = calm_range([20.0, 21.5, 19.8, 102.0], "mA")
    assert low == 0 and 102 <= high <= 102 * 1.1
    assert calm_range([0.0, 0.0], "A") == [0.0, 1.0]  # a stopped motor still gets a valid axis


def test_temperatures_get_a_ten_degree_window_that_includes_the_band() -> None:
    low, high = calm_range([41.0, 42.0], "°C", band=(40.5, 43.0))
    assert high - low == 10.0 and low <= 40.5 and high >= 43.0
    low, high = calm_range([40.0, 70.0], "°C")
    assert low < 40.0 and high > 70.0  # a real 30 °C rise is never clipped


def test_unknown_units_and_states_keep_autoscale() -> None:
    assert calm_range([0, 1], "state") is None
    assert calm_range([1.0, 2.0], "widgets") is None
    assert calm_range([], "V") is None
    assert calm_range([float("nan")], "V") is None
