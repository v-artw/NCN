"""Edge Scout 综合评分测试。"""

import pytest
import numpy as np
from types import SimpleNamespace

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


def test_timing_score_uses_confirmed_t1_and_bounds_futu_evidence():
    candle_features = {
        "candle_position_zone": "low",
        "candle_close_location": 0.5,
        "candle_confirm_score": 5.0,
    }

    base, _ = compute_timing_score(candle_features)
    confirmed, breakdown = compute_timing_score(
        candle_features,
        t1_observation=SimpleNamespace(confirmed=True),
        futu_bonus=100.0,
    )

    assert confirmed == 33.0
    assert confirmed > base
    assert "t1_price_volume_confirmed" in breakdown
    assert "futu=6.0" in breakdown


def test_unconfirmed_t1_does_not_receive_confirmation_points():
    candle_features = {
        "candle_position_zone": "low",
        "candle_close_location": 0.5,
        "candle_confirm_score": 5.0,
    }

    base, _ = compute_timing_score(candle_features)
    unconfirmed, _ = compute_timing_score(
        candle_features,
        t1_observation=SimpleNamespace(confirmed=False),
    )

    assert unconfirmed == base


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


def test_futu_and_candle_risks_reduce_but_do_not_invert_risk_score():
    base, _ = compute_risk_score(10.0, 9.5, 0.3, 10.0)
    penalized, breakdown = compute_risk_score(
        10.0,
        9.5,
        0.3,
        10.0,
        risk_codes=("clear_signal", "bearish_candle_risk", "clear_signal"),
    )

    assert penalized == 2.0
    assert penalized < base
    assert "bearish_candle_risk" in breakdown


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


def _gate_records(*, amount=120_000_000.0, tradestatus="1", is_st="0", close=10.0, preclose=10.0):
    return [
        {
            "date": f"2026-01-{index + 1:02d}",
            "code": "sh.600000",
            "open": 10.0,
            "high": max(close, 10.1),
            "low": 9.9,
            "close": close,
            "preclose": preclose,
            "volume": 10_000_000,
            "amount": amount,
            "turn": 1.0,
            "tradestatus": tradestatus,
            "isST": is_st,
        }
        for index in range(300)
    ]


def _gate_config(**overrides):
    universe = {
        "include_prefixes": ["sh.600"],
        "exclude_st": True,
        "min_listing_days": 252,
        "min_close_cny": 5.0,
        "max_close_cny": 80.0,
        "min_adv20_cny": 100_000_000.0,
        "min_trading_days_60": 55,
        "block_limit_up_entries": True,
        "block_suspensions": True,
    }
    universe.update(overrides)
    return {"universe": universe}


@pytest.mark.parametrize(
    ("records", "failure"),
    [
        (_gate_records(amount=50_000_000.0), "adv20_too_low"),
        (_gate_records(tradestatus="0"), "suspended_on_signal_date"),
        (_gate_records(close=10.0, preclose=9.0), "near_limit_up_on_signal_date"),
    ],
)
def test_configured_universe_gates_have_stable_rejection_reasons(records, failure):
    passed, failures = apply_hard_gates("sh.600000", records, _gate_config())

    assert not passed
    assert failure in failures


def test_trading_day_gate_counts_recent_60_rows():
    records = _gate_records()
    for record in records[-7:]:
        record["tradestatus"] = "0"
    records[-1]["tradestatus"] = "1"

    passed, failures = apply_hard_gates("sh.600000", records, _gate_config())

    assert not passed
    assert "insufficient_trading_days_60" in failures


def test_universe_boolean_gates_respect_config_switches():
    records = _gate_records(tradestatus="0", is_st="1", close=10.0, preclose=9.0)

    passed, failures = apply_hard_gates(
        "sh.600000",
        records,
        _gate_config(
            exclude_st=False,
            block_suspensions=False,
            block_limit_up_entries=False,
            min_trading_days_60=0,
            min_adv20_cny=0,
        ),
    )

    assert passed
    assert failures == []
