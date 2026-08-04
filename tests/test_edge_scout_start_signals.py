"""CNstock-inspired start-signal and discovery-tier tests."""

from __future__ import annotations

import numpy as np

from ashare_edge_scout.signal_scoring import classify_discovery_tier, compute_discovery_score
from ashare_edge_scout.start_signals import compute_start_signals


def test_start_signals_short_history_is_stable():
    result = compute_start_signals([11.0] * 20, [9.0] * 20, [10.0] * 20)

    assert result.count == 0
    assert result.names == ()
    assert result.reasons == ("insufficient_start_signal_history",)


def test_start_signals_are_deterministic_and_bounded():
    close = 10.0 + np.sin(np.linspace(0.0, 8.0, 120)) + np.linspace(0.0, 2.0, 120)
    high = close + 0.2
    low = close - 0.2

    first = compute_start_signals(high, low, close)
    second = compute_start_signals(high, low, close)

    assert first == second
    assert 0 <= first.count <= 5
    assert len(first.names) == first.count


def test_discovery_tiers_match_cnstock_style_lifecycle():
    assert classify_discovery_tier(5) == "strong_start"
    assert classify_discovery_tier(4) == "strong_start"
    assert classify_discovery_tier(3) == "profit_shadow"
    assert classify_discovery_tier(2) == "early_low_position"
    assert classify_discovery_tier(1) == "general_observation"


def test_discovery_score_rewards_start_count_without_changing_production_tier():
    pmk = {"pmk_feature_bonus": 6.0, "pmk_shape_score": 80.0}
    candle = {
        "candle_confirm_score": 8.0,
        "candle_close_location": 0.8,
        "candle_low_position_pct": 0.3,
        "candle_upper_shadow_pct": 0.1,
    }

    low, _ = compute_discovery_score(30.0, pmk, candle, 1, 2.0, 3.0, 1.2)
    high, breakdown = compute_discovery_score(30.0, pmk, candle, 4, 2.0, 3.0, 1.2)

    assert high > low
    assert "start=32.00" in breakdown
