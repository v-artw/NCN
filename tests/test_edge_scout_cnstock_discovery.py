"""Native CNstock-compatible discovery tests without runtime CNstock imports."""

from __future__ import annotations

import numpy as np

from ashare_edge_scout.discovery import (
    compute_price_volume_base_score,
    compute_cnstock_discovery_rank,
    evaluate_discovery_pool,
)


def test_price_volume_base_score_golden_vector():
    close = np.linspace(10.0, 13.0, 80) + 0.12 * np.sin(np.arange(80) / 3.0)
    high = close + 0.25
    low = close - 0.25
    volume = np.linspace(1_000_000.0, 1_400_000.0, 80)

    assert compute_price_volume_base_score(
        high, low, close, volume, futu_bonus=3.5
    ) == 59.434696

    falling = np.linspace(13.0, 10.0, 80)
    assert compute_price_volume_base_score(
        falling + 0.2, falling - 0.2, falling, volume, futu_bonus=10.0
    ) == 0.0


def test_cnstock_pool_boundaries_are_exact_and_research_only():
    common = dict(
        base_score=82.0,
        pct_chg=2.0,
        ret_5d=4.0,
        amount_cny=100_000_000.0,
        risk_codes=(),
        config={},
    )

    strong = evaluate_discovery_pool(start_count=4, **common)
    shadow = evaluate_discovery_pool(start_count=3, **common)
    low = evaluate_discovery_pool(start_count=2, **common)
    none = evaluate_discovery_pool(start_count=1, **common)

    assert (strong.pool, strong.eligible) == ("strong_start", True)
    assert (shadow.pool, shadow.eligible) == ("profit_shadow", True)
    assert (low.pool, low.eligible) == ("low_position_discovery", True)
    assert (none.pool, none.eligible) == ("not_in_cnstock_pool", False)

    exact = evaluate_discovery_pool(start_count=3, **dict(common, base_score=75.0))
    below = evaluate_discovery_pool(start_count=3, **dict(common, base_score=74.999999))
    assert exact.eligible
    assert not below.eligible


def test_profit_shadow_and_low_position_apply_distinct_thresholds():
    common = dict(
        base_score=82.0,
        pct_chg=6.0,
        ret_5d=7.0,
        amount_cny=100_000_000.0,
        risk_codes=(),
        config={},
    )

    assert evaluate_discovery_pool(start_count=3, **common).eligible is True
    low = evaluate_discovery_pool(start_count=2, **common)
    assert low.eligible is False
    assert low.rejection_reasons == ("pct_chg_above_5", "ret_5d_above_6")


def test_pool_risk_codes_block_without_string_matching():
    decision = evaluate_discovery_pool(
        start_count=3,
        base_score=90.0,
        pct_chg=2.0,
        ret_5d=4.0,
        amount_cny=100_000_000.0,
        risk_codes=("mhpg_outflow", "overbought_risk"),
        config={},
    )
    assert decision.eligible is False
    assert decision.rejection_reasons == (
        "risk:mhpg_outflow",
        "risk:overbought_risk",
    )


def test_cnstock_rank_preserves_v4_flag_bonuses_and_no_start_count_bonus():
    pmk = {
        "pmk_feature_bonus": 6.0,
        "pmk_shape_score": 80.0,
        "pmk_trend_confirmed": True,
        "pmk_macd_confirm": True,
        "pmk_volume_breakout": True,
    }
    candle = {
        "candle_confirm_score": 8.0,
        "candle_close_location": 0.8,
        "candle_low_position_pct": 0.3,
        "candle_upper_shadow_pct": 0.1,
        "candle_bullish_reversal": True,
        "candle_bullish_continuation": True,
        "candle_box_breakout": True,
    }
    score, breakdown = compute_cnstock_discovery_rank(80.0, pmk, candle, 2.0, 3.0, 1.2)

    assert score == 113.6
    assert breakdown == "base=80.00;positive=34.10;penalty=-0.50"
