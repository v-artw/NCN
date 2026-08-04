"""Edge Scout 综合评分测试。"""

import pytest
import numpy as np

from ashare_edge_scout.signal_scoring import (
    compute_base_quality_score,
    compute_timing_score,
    compute_risk_score,
    compute_edge_score,
    classify_tier,
    apply_hard_gates,
    score_single_stock,
)


def test_compute_base_quality_score():
    """测试基础质量分数计算。"""

    # 完美特征
    pmk_features = {
        "pmk_trend_confirmed": True,
        "pmk_shape_pattern": "Steady Climber",
        "pmk_rsi": 70,
        "pmk_atr_squeeze": True,
    }

    score = compute_base_quality_score(pmk_features)

    # 10 (trend) + 3 (Steady Climber) + 8 (RSI>60) + 6 (atr_squeeze) + 2 (data quality) = 29
    assert score > 25


def test_compute_timing_score():
    """测试时机分数计算。"""

    candle_features = {
        "candle_position_zone": "low",
        "candle_close_location": 0.5,
        "candle_confirm_score": 5.0,
    }

    score, _ = compute_timing_score(candle_features)

    # 应该有一定分数
    assert score > 0


def test_compute_risk_score():
    """测试风险分数计算。"""

    score, _ = compute_risk_score(
        signal_high=10.0,
        signal_low=9.5,
        atr14=0.3,
        close_now=10.0,
    )

    # 应该有一定分数
    assert score > 0


def test_compute_edge_score():
    """测试综合边缘分数计算。

    修复后公式：edge_score = base_quality + timing + risk（分项本身就是贡献分）。
    """

    edge = compute_edge_score(30.0, 20.0, 10.0)

    # 验证修复后公式：edge = base + timing + risk
    expected = 30.0 + 20.0 + 10.0  # 60.0
    assert abs(edge - expected) < 0.01


def test_classify_tier():
    """测试候选层级分类。"""

    assert classify_tier(75.0, True) == "watchlist"
    with pytest.raises(ValueError, match="production tier is disabled"):
        classify_tier(75.0, True, production_enabled=True)
    assert classify_tier(60.0, False) == "watchlist"
    assert classify_tier(40.0, False) == "near_miss"


def test_apply_hard_gates():
    """测试硬门槛检查。"""

    # 正常股票
    records = [
        {"date": "2026-07-24", "code": "sh.600000", "open": 10.0, "high": 11.0,
         "low": 9.0, "close": 10.5, "preclose": 10.0, "volume": 1000,
         "amount": 10000, "turn": 1.0, "tradestatus": "1", "isST": "0"}
    ] * 300

    config = {
        "universe": {"min_close_cny": 5.0, "max_close_cny": 80.0},
        "hard_gates": {"risk_distance_min": 0.025, "risk_distance_max": 0.200},
    }

    passed, failures = apply_hard_gates("sh.600000", records, config)

    assert passed  # 应该通过

    # ST 股票
    records_st = records.copy()
    records_st[-1]["isST"] = "1"

    passed, failures = apply_hard_gates("sh.600000", records_st, config)

    assert not passed
    assert "is_st_stock" in failures
