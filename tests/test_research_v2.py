from __future__ import annotations

from copy import deepcopy

import pytest

from ashare_edge_scout.research_v2 import (
    classify_t1_confirmation,
    evaluate_decision,
    five_close_label,
    has_pre_t_local_decline,
    post_confirmation_label,
    pre_t_support_levels,
    reclaimed_supports,
    summarize_counts,
)


def _bar(close: float, *, open_: float | None = None, high: float | None = None, low: float | None = None):
    return {
        "open": close if open_ is None else open_,
        "high": close + 0.5 if high is None else high,
        "low": close - 0.5 if low is None else low,
        "close": close,
    }


def test_local_decline_uses_t_minus_4_through_t_minus_1_only():
    records = [_bar(value) for value in (20, 14, 13, 13.5, 12, 99)]
    assert has_pre_t_local_decline(records)
    changed_t = deepcopy(records)
    changed_t[-1]["close"] = 1
    assert has_pre_t_local_decline(changed_t)
    records[-2]["close"] = 15
    assert not has_pre_t_local_decline(records)


def test_support_levels_exclude_all_t_values_and_reclaim_is_single_candidate_condition():
    records = [_bar(10 + index * 0.01, low=9 + index * 0.01) for index in range(61)]
    records[-1] = _bar(1000, high=2000, low=0.01)
    levels = pre_t_support_levels(records)
    assert levels["prior_20_bar_swing_low"] == pytest.approx(9.40)
    assert max(levels.values()) < 20

    support = {"one": 10.0, "two": 10.1}
    reclaimed = reclaimed_supports([_bar(10.2, low=10.05)], support)
    assert reclaimed == support
    assert bool(reclaimed)
    assert not reclaimed_supports([_bar(9.9, low=9.8)], support)


@pytest.mark.parametrize(
    ("pattern", "history", "hold_close", "strong_close", "failed_close"),
    [
        ("hammer", [_bar(10, high=10.8, low=9.5)], 10.5, 11.0, 9.4),
        (
            "bullish_engulfing",
            [_bar(10, open_=11, high=11.2, low=9.8), _bar(10.8, open_=9.8, high=11, low=9.6)],
            10.5,
            11.1,
            9.5,
        ),
        (
            "piercing",
            [_bar(10, open_=11, high=11.2, low=9.8), _bar(10.6, open_=9.7, high=10.9, low=9.5)],
            10.4,
            11.0,
            9.4,
        ),
        (
            "morning_star",
            [_bar(11, low=10.5), _bar(10, low=9.5), _bar(10.8, high=11, low=9.8)],
            10.8,
            11.1,
            9.4,
        ),
    ],
)
def test_pattern_specific_confirmation_hold_strong_and_failure(
    pattern, history, hold_close, strong_close, failed_close
):
    support = {"prior_20_bar_swing_low": 9.7}
    hold = classify_t1_confirmation(history, _bar(hold_close), [pattern], support)
    strong = classify_t1_confirmation(history, _bar(strong_close), [pattern], support)
    failed = classify_t1_confirmation(history, _bar(failed_close), [pattern], support)
    assert hold["state"] == "confirmed_hold"
    assert strong["state"] == "confirmed_strong"
    assert failed["state"] == "failed"
    assert hold["pattern"] == pattern


def test_confirmation_priority_and_no_t_plus_2_input():
    history = [_bar(10, open_=11, high=11.2, low=9.8), _bar(10.8, open_=9.8, high=11, low=9.6)]
    result = classify_t1_confirmation(
        history,
        _bar(10.5),
        ["hammer", "bullish_engulfing"],
        {"prior_20_bar_swing_low": 9.7},
    )
    assert result["state"] == "confirmed_hold"
    assert result["pattern"] == "bullish_engulfing"


def test_hammer_can_hold_any_reclaimed_support_and_reports_which_one():
    result = classify_t1_confirmation(
        [_bar(10, high=10.8, low=9.5)],
        _bar(10.2),
        ["hammer"],
        {"lower_support": 9.7, "higher_support": 10.4},
    )
    assert result["state"] == "confirmed_hold"
    assert result["support_reason"] == "lower_support"


def test_confirmed_label_starts_at_t_plus_2_and_references_t_plus_1():
    records = [_bar(value) for value in (100, 200, 194, 206, 200, 200, 200)]
    assert post_confirmation_label(records, 0)
    records[2]["close"] = 193
    assert not post_confirmation_label(records, 0)
    assert five_close_label(200, [194, 206, 200, 200, 200])


def _decision_summaries(
    baseline_rates=(0.50, 0.50), confirmed_rates=(0.65, 0.65), baseline_n=1000, confirmed_n=500
):
    periods = ("calibration_2021_2024", "holdout_2025_2026")
    baseline = {
        period: summarize_counts(baseline_n, round(baseline_n * rate))
        for period, rate in zip(periods, baseline_rates, strict=True)
    }
    confirmed = {
        period: summarize_counts(confirmed_n, round(confirmed_n * rate))
        for period, rate in zip(periods, confirmed_rates, strict=True)
    }
    return {
        "legacy_setup_post_confirmation_horizon": baseline,
        "support_reclaim_confirmed_post_confirmation_horizon": confirmed,
    }


def test_decision_passes_only_when_every_period_passes_every_gate():
    decision = evaluate_decision(_decision_summaries())
    assert decision["passed"]
    assert decision["failure_reasons"] == []


@pytest.mark.parametrize(
    ("summaries", "reason_fragment"),
    [
        (_decision_summaries(confirmed_n=299), "confirmed_n_below_300"),
        (_decision_summaries(confirmed_n=399), "candidate_retention_below_0.40"),
        (_decision_summaries(confirmed_rates=(0.55, 0.55)), "fpr_reduction_below_0.20"),
        (_decision_summaries(confirmed_rates=(0.50, 0.65)), "precision_lift_not_positive"),
        (_decision_summaries(baseline_n=10000, confirmed_n=500, confirmed_rates=(0.53, 0.65)), "wilson_lower_deteriorated"),
    ],
)
def test_decision_reports_each_failed_gate(summaries, reason_fragment):
    decision = evaluate_decision(summaries)
    assert not decision["passed"]
    assert any(reason_fragment in reason for reason in decision["failure_reasons"])
