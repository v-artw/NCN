from __future__ import annotations

from copy import deepcopy

import pytest

import ashare_edge_scout.research_rising_three as rising
from ashare_edge_scout.research_rising_three import (
    AGGREGATE,
    CALIBRATION,
    HOLDOUT,
    benchmark_regime_through_t,
    classify_t,
    evaluate_decision,
    five_close_label,
    next_five_trading_closes,
    stock_trend_through_t,
    strict_pattern_ending_at_t,
)
from ashare_edge_scout.research_v2 import summarize_counts


def _bar(open_: float, high: float, low: float, close: float, volume: float = 100.0):
    return {"open": open_, "high": high, "low": low, "close": close, "volume": volume}


def _pattern(length: int = 3):
    history = [_bar(9.5, 10.1, 9.4, 10.0, 50.0) for _ in range(19)]
    impulse = _bar(10.0, 12.1, 9.9, 11.8, 200.0)
    consolidation = [
        _bar(11.5, 11.7, 10.7, 11.2, 100.0),
        _bar(11.1, 11.4, 10.6, 11.0, 90.0),
        _bar(11.0, 11.5, 10.8, 11.2, 80.0),
        _bar(11.1, 11.4, 10.7, 11.0, 70.0),
    ][:length]
    completion = _bar(11.3, 12.7, 11.2, 12.5, 130.0)
    return history + [impulse, *consolidation, completion]


@pytest.mark.parametrize(
    ("mutation",),
    [
        (lambda bars: bars[-5].update(open=11.8),),
        (lambda bars: bars[-5].update(open=10.8),),
        (lambda bars: bars[-5].update(close=11.4),),
        (lambda bars: bars[-5].update(volume=49.0),),
    ],
)
def test_first_impulse_criteria(mutation):
    bars = _pattern(3)
    assert strict_pattern_ending_at_t(bars) == 3
    mutation(bars)
    assert strict_pattern_ending_at_t(bars) is None


@pytest.mark.parametrize(
    "mutation",
    [
        lambda bars: bars[-4].update(high=12.2),
        lambda bars: bars[-4].update(open=10.7, close=11.5),
        lambda bars: [bar.update(close=11.7) for bar in bars[-4:-1]],
        lambda bars: bars[-4].update(volume=200.0),
    ],
)
def test_consolidation_full_range_body_falling_and_volume_criteria(mutation):
    bars = _pattern(3)
    mutation(bars)
    assert strict_pattern_ending_at_t(bars) is None


@pytest.mark.parametrize(
    "mutation",
    [
        lambda bar: bar.update(open=12.5),
        lambda bar: bar.update(open=11.2),
        lambda bar: bar.update(close=11.8),
        lambda bar: bar.update(open=11.9),
        lambda bar: bar.update(close=11.8, high=12.7),
        lambda bar: bar.update(high=13.0),
        lambda bar: bar.update(volume=90.0),
        lambda bar: bar.update(volume=500.0),
    ],
)
def test_completion_open_close_body_location_shadow_and_volume_criteria(mutation):
    bars = _pattern(3)
    mutation(bars[-1])
    assert strict_pattern_ending_at_t(bars) is None


@pytest.mark.parametrize("length", [2, 3, 4])
def test_all_frozen_lengths_match(length):
    assert strict_pattern_ending_at_t(_pattern(length)) == length


def test_longest_matching_length_is_reported_once():
    bars = _pattern(4)
    bars[-5] = _bar(11.0, 11.85, 10.65, 11.7, 180.0)
    bars[-4].update(low=10.7)
    assert rising._strict_pattern_length(bars, 3)
    assert rising._strict_pattern_length(bars, 4)
    assert strict_pattern_ending_at_t(bars) == 4


def test_zero_range_volume_and_insufficient_history_are_deterministic():
    assert strict_pattern_ending_at_t([]) is None
    bars = _pattern(2)
    bars[-1]["high"] = bars[-1]["low"]
    assert strict_pattern_ending_at_t(bars) is None
    bars = _pattern(2)
    bars[-3]["high"] = bars[-3]["low"]
    assert strict_pattern_ending_at_t(bars) is None
    bars = _pattern(2)
    bars[-4]["volume"] = 0.0
    assert strict_pattern_ending_at_t(bars) is None
    bars = _pattern(2)
    bars[-1]["volume"] = 0.0
    assert strict_pattern_ending_at_t(bars) is None


def test_market_regime_is_causal_and_requires_exact_history():
    closes = [100.0 + index for index in range(25)]
    records = [{"close": close} for close in closes]
    assert benchmark_regime_through_t(records)
    changed_future = records + [{"close": 1.0}]
    assert benchmark_regime_through_t(changed_future[:-1])
    assert not benchmark_regime_through_t(records[:24])
    drawdown = deepcopy(records)
    drawdown[-1]["close"] = drawdown[-6]["close"] * 0.969
    assert not benchmark_regime_through_t(drawdown)


def test_stock_trend_is_causal_and_uses_strict_slopes():
    records = [{"close": 10.0 + index * 0.03} for index in range(65)]
    assert stock_trend_through_t(records)
    assert stock_trend_through_t(records + [{"close": 1.0}][:-1])
    assert not stock_trend_through_t(records[:64])
    flat = [{"close": 10.0} for _ in range(65)]
    assert not stock_trend_through_t(flat)


def test_detection_and_label_do_not_read_future_bars():
    through_t = _pattern(3)
    all_bars = through_t + [_bar(1, 1, 1, 1) for _ in range(5)]
    assert strict_pattern_ending_at_t(all_bars[:len(through_t)]) == 3
    all_bars[-1]["close"] = 1000
    assert strict_pattern_ending_at_t(all_bars[:len(through_t)]) == 3


def test_exact_five_close_label_boundaries():
    assert five_close_label(100.0, [97.0, 100.0, 103.0, 100.0, 100.0])
    assert not five_close_label(100.0, [96.999, 104.0, 100.0, 100.0, 100.0])
    with pytest.raises(ValueError):
        five_close_label(100.0, [103.0] * 4)


def test_next_five_trading_closes_skip_suspension_rows():
    records = [
        {"close": 100.0, "tradestatus": "1"},
        {"close": 100.0, "tradestatus": "0"},
        {"close": 101.0, "tradestatus": "1"},
        {"close": 102.0, "tradestatus": "1"},
        {"close": 103.0, "tradestatus": "1"},
        {"close": 104.0, "tradestatus": "1"},
        {"close": 105.0, "tradestatus": "1"},
    ]

    assert next_five_trading_closes(records, 0) == [101.0, 102.0, 103.0, 104.0, 105.0]
    assert next_five_trading_closes(records[:-1], 0) is None


def test_production_gate_is_invoked_through_t_and_required(monkeypatch):
    calls = []

    def gate(code, records, config):
        calls.append((code, records, config))
        return False, ["blocked"]

    monkeypatch.setattr(rising, "apply_hard_gates", gate)
    stock = [{"close": 10.0 + index * 0.02} for index in range(65)]
    benchmark = [{"close": 100.0 + index} for index in range(25)]
    result = classify_t("sh.600000", stock, benchmark, {})
    assert len(calls) == 1
    assert calls[0][1] is stock
    assert not result["trend_context_baseline"]
    assert not result["strict_pattern"]


def _decision_summaries(
    *, baseline_rate=0.50, pattern_rate=0.70, period_n=300, annual_n=60, aggregate_rate=None
):
    aggregate_rate = pattern_rate if aggregate_rate is None else aggregate_rate
    baseline = {
        CALIBRATION: summarize_counts(1000, round(1000 * baseline_rate)),
        HOLDOUT: summarize_counts(1000, round(1000 * baseline_rate)),
        AGGREGATE: summarize_counts(2000, round(2000 * baseline_rate)),
    }
    pattern = {
        CALIBRATION: summarize_counts(period_n, round(period_n * pattern_rate)),
        HOLDOUT: summarize_counts(period_n, round(period_n * pattern_rate)),
        AGGREGATE: summarize_counts(period_n * 2, round(period_n * 2 * aggregate_rate)),
    }
    for year in range(2021, 2027):
        baseline[f"year_{year}"] = summarize_counts(200, round(200 * baseline_rate))
        pattern[f"year_{year}"] = summarize_counts(annual_n, round(annual_n * pattern_rate))
    return {"trend_context_baseline": baseline, "strict_pattern": pattern}


def test_decision_passes_all_frozen_thresholds():
    result = evaluate_decision(_decision_summaries())
    assert result["passed"]
    assert result["failure_codes"] == []


@pytest.mark.parametrize(
    ("summaries", "code"),
    [
        (_decision_summaries(pattern_rate=0.50), f"{CALIBRATION}:precision_lift_not_positive"),
        (_decision_summaries(aggregate_rate=0.529), f"{AGGREGATE}:precision_lift_below_0.03"),
        (_decision_summaries(pattern_rate=0.54), f"{CALIBRATION}:relative_fpr_reduction_below_0.10"),
        (_decision_summaries(period_n=149), f"{CALIBRATION}:pattern_n_below_150"),
        (_decision_summaries(annual_n=49), "year_2021:pattern_n_below_50"),
        (
            _decision_summaries(baseline_rate=0.65, pattern_rate=0.70, period_n=150),
            f"{CALIBRATION}:pattern_wilson_lower_below_baseline_precision",
        ),
    ],
)
def test_decision_reports_each_failure_category(summaries, code):
    result = evaluate_decision(summaries)
    assert not result["passed"]
    assert code in result["failure_codes"]
