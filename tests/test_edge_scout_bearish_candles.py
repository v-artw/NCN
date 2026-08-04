"""Book-derived bearish candlestick warnings remain contextual and research-only."""

from __future__ import annotations

from ashare_edge_scout.candles import detect_bearish_risk_patterns


def _bar(open_: float, high: float, low: float, close: float) -> dict[str, float]:
    return {"open": open_, "high": high, "low": low, "close": close}


def test_hanging_man_requires_a_prior_rise():
    rising = [
        _bar(9.8, 10.1, 9.7, 10.0),
        _bar(10.0, 10.5, 9.9, 10.4),
        _bar(10.4, 10.9, 10.3, 10.8),
        _bar(10.8, 11.3, 10.7, 11.2),
        _bar(11.15, 11.20, 10.5, 11.05),
    ]
    falling = [
        _bar(11.2, 11.3, 10.9, 11.0),
        _bar(11.0, 11.1, 10.6, 10.7),
        _bar(10.7, 10.8, 10.3, 10.4),
        _bar(10.4, 10.5, 10.0, 10.1),
        _bar(10.15, 10.25, 9.5, 10.05),
    ]

    assert detect_bearish_risk_patterns(rising)["hanging_man"][-1] is True
    assert detect_bearish_risk_patterns(falling)["hanging_man"][-1] is False


def test_shooting_star_detects_upper_rejection_after_rise():
    bars = [
        _bar(9.8, 10.1, 9.7, 10.0),
        _bar(10.0, 10.5, 9.9, 10.4),
        _bar(10.4, 10.9, 10.3, 10.8),
        _bar(10.8, 11.3, 10.7, 11.2),
        _bar(11.15, 11.9, 11.10, 11.25),
    ]

    assert detect_bearish_risk_patterns(bars)["shooting_star"][-1] is True


def test_bearish_engulfing_requires_body_engulfment_after_rise():
    bars = [
        _bar(9.8, 10.1, 9.7, 10.0),
        _bar(10.0, 10.5, 9.9, 10.4),
        _bar(10.4, 10.9, 10.3, 10.8),
        _bar(10.8, 11.4, 10.7, 11.3),
        _bar(11.4, 11.5, 10.6, 10.7),
    ]

    assert detect_bearish_risk_patterns(bars)["bearish_engulfing"][-1] is True


def test_dark_cloud_cover_closes_below_prior_body_midpoint():
    bars = [
        _bar(9.8, 10.1, 9.7, 10.0),
        _bar(10.0, 10.5, 9.9, 10.4),
        _bar(10.4, 10.9, 10.3, 10.8),
        _bar(10.8, 11.5, 10.7, 11.4),
        _bar(11.45, 11.6, 10.95, 11.0),
    ]

    assert detect_bearish_risk_patterns(bars)["dark_cloud_cover"][-1] is True


def test_evening_star_requires_star_gap_and_deep_bearish_close():
    bars = [
        _bar(9.8, 10.1, 9.7, 10.0),
        _bar(10.0, 10.5, 9.9, 10.4),
        _bar(10.4, 10.9, 10.3, 10.8),
        _bar(10.8, 11.6, 10.7, 11.5),
        _bar(11.7, 11.9, 11.65, 11.75),
        _bar(11.6, 11.65, 10.9, 11.0),
    ]

    assert detect_bearish_risk_patterns(bars)["evening_star"][-1] is True
