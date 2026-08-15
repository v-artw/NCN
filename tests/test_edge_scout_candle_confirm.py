"""Edge Scout 蜡烛确认测试。"""

import pytest
import numpy as np

from ashare_edge_scout.candle_confirm import compute_candle_confirmation_features
from ashare_edge_scout.candle_timing import evaluate_t_day_setup


def test_compute_candle_confirmation_features_short_series():
    """测试短序列直接返回空特征。"""

    empty_features = {
        "candle_position_zone": "N/A",
        "candle_low_position_pct": 1.0,
        "candle_close_location": 0.0,
        "candle_volume_confirm": False,
        "candle_volume_ratio_20": 0.0,
        "candle_upper_shadow_pct": 1.0,
        "candle_long_upper_shadow_risk": True,
        "candle_bullish_reversal": False,
        "candle_bullish_continuation": False,
        "candle_box_breakout": False,
        "candle_confirm_score": 0.0,
        "candle_confirm_reason": "insufficient_data",
    }

    result = compute_candle_confirmation_features(
        open_=[10.0, 11.0],
        high=[11.0, 12.0],
        low=[9.0, 10.0],
        close=[10.5, 11.5],
    )

    for key in empty_features:
        assert result[key] == empty_features[key]


def test_compute_candle_confirmation_features_normal():
    """测试正常序列处理。"""

    np.random.seed(42)
    n = 60
    open_ = 100.0 + np.cumsum(np.random.randn(n) * 0.3)
    high = open_ + np.abs(np.random.randn(n)) * 0.2
    low = open_ - np.abs(np.random.randn(n)) * 0.2
    close = low + np.random.randn(n) * 0.1
    volume = np.abs(np.random.randn(n) * 1000) + 500

    result = compute_candle_confirmation_features(open_, high, low, close, volume)

    assert "candle_position_zone" in result
    assert "candle_low_position_pct" in result
    assert "candle_close_location" in result
    assert "candle_confirm_score" in result
    assert "candle_confirm_reason" in result

    # 分数应该在 0-10 之间
    assert 0 <= result["candle_confirm_score"] <= 10


def test_t_day_setup_requires_enabled_pattern_on_signal_bar():
    """Price trend alone must not become a valid candlestick setup."""

    closes = [10.0 + i * 0.05 for i in range(61)]
    records = []
    for index, close in enumerate(closes):
        high = close + 0.1
        if index == 55:
            high = close * 1.06
        records.append({
            "open": close - 0.05,
            "high": high,
            "low": close - 0.1,
            "close": close,
            "volume": 1000.0,
        })

    config = {
        "research_market_regime": {"enforcement": "none"},
        "setup": {
            "trend": {
                "fast_ma": 20,
                "slow_ma": 60,
                "min_return_20d": 0.03,
                "max_return_20d": 0.30,
            },
            "pullback": {
                "high_lookback": 10,
                "min_drawdown_from_high": 0.03,
                "max_drawdown_from_high": 0.10,
                "min_low_to_ma60_ratio": 0.98,
            },
        },
    }
    no_pattern = {"hammer": [False] * len(records)}
    with_pattern = {"hammer": [False] * (len(records) - 1) + [True]}

    rejected = evaluate_t_day_setup(records, config, no_pattern)
    admitted = evaluate_t_day_setup(records, config, with_pattern)

    assert rejected.valid is False
    assert "no_enabled_bullish_pattern_on_t" in rejected.failed_conditions
    assert admitted.valid is True
    assert admitted.reason == "valid_setup"
    assert admitted.matched_patterns == ("hammer",)
