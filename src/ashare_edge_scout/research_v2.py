"""Research-only evaluation primitives for the NCN v2 support-reclaim study."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

from .signals.candle_timing import evaluate_t_day_setup
from .signals.candles import detect_bullish_patterns
from .signals.indicators import sma
from .signals.signal_scoring import apply_hard_gates


PATTERN_PRIORITY = ("hammer", "bullish_engulfing", "piercing", "morning_star")
CONFIRMED_STATES = frozenset(("confirmed_hold", "confirmed_strong"))
PERIODS = {
    "calibration_2021_2024": (2021, 2024),
    "holdout_2025_2026": (2025, 2026),
}
SUPPORT_REASON_CODES = (
    "prior_20_bar_swing_low",
    "sma20_t_minus_1",
    "sma60_t_minus_1",
)


def has_pre_t_local_decline(records_through_t: Sequence[Mapping[str, Any]]) -> bool:
    """Test the fixed decline using only T-4 through T-1 closes.

    The three closes immediately before T are T-3, T-2, and T-1. The first
    condition compares T-1 with T-3. The lower-close count compares T-3 with
    T-4, T-2 with T-3, and T-1 with T-2.
    """

    if len(records_through_t) < 5:
        return False
    closes = [float(record["close"]) for record in records_through_t[-5:-1]]
    return closes[3] < closes[1] and sum(
        closes[index] < closes[index - 1] for index in range(1, 4)
    ) >= 2


def major_trend_context(records_through_t: Sequence[Mapping[str, Any]]) -> bool:
    """Apply the fixed T trend context without the legacy location filter."""

    if len(records_through_t) < 65:
        return False
    closes = [float(record["close"]) for record in records_through_t]
    ma20 = sma(closes, 20)
    ma60 = sma(closes, 60)
    index = len(closes) - 1
    return bool(
        ma20[index] is not None
        and ma60[index] is not None
        and ma20[index - 5] is not None
        and closes[index] > ma20[index] > ma60[index]
        and ma20[index] >= ma20[index - 5]
        and 0.03 <= closes[index] / closes[index - 20] - 1.0 <= 0.30
    )


def pre_t_support_levels(records_through_t: Sequence[Mapping[str, Any]]) -> dict[str, float]:
    """Compute fixed support levels strictly before T.

    Changed-polarity resistance is intentionally omitted because the
    preregistration does not uniquely define its subsequent breakout window.
    """

    if len(records_through_t) < 61:
        return {}
    pre_t = records_through_t[:-1]
    closes = [float(record["close"]) for record in pre_t]
    ma20 = sma(closes, 20)[-1]
    ma60 = sma(closes, 60)[-1]
    levels = {"prior_20_bar_swing_low": min(float(record["low"]) for record in pre_t[-20:])}
    if ma20 is not None:
        levels["sma20_t_minus_1"] = float(ma20)
    if ma60 is not None:
        levels["sma60_t_minus_1"] = float(ma60)
    return levels


def reclaimed_supports(
    records_through_t: Sequence[Mapping[str, Any]],
    support_levels: Mapping[str, float] | None = None,
) -> dict[str, float]:
    """Return pre-T supports touched and reclaimed by T."""

    if not records_through_t:
        return {}
    levels = dict(
        pre_t_support_levels(records_through_t)
        if support_levels is None
        else support_levels
    )
    low_t = float(records_through_t[-1]["low"])
    close_t = float(records_through_t[-1]["close"])
    return {
        reason: level
        for reason, level in levels.items()
        if low_t <= level * 1.01 and close_t >= level
    }


def evaluate_t_candidates(
    code: str,
    records_through_t: Sequence[Mapping[str, Any]],
    config: Mapping[str, Any],
    candle_patterns: Mapping[str, Sequence[bool]] | None = None,
) -> dict[str, Any]:
    """Classify legacy and support-reclaim candidates using information through T."""

    patterns = candle_patterns or detect_bullish_patterns(records_through_t)
    matched = tuple(
        name for name in PATTERN_PRIORITY if patterns.get(name) and bool(patterns[name][-1])
    )
    gate_passed, gate_failures = apply_hard_gates(code, records_through_t, config)
    legacy = evaluate_t_day_setup(records_through_t, config, patterns)
    trend = major_trend_context(records_through_t)
    decline = has_pre_t_local_decline(records_through_t)
    levels = pre_t_support_levels(records_through_t)
    reclaimed = reclaimed_supports(records_through_t, levels)
    support_reclaim_t = bool(gate_passed and trend and decline and reclaimed and matched)
    return {
        "universe_eligible": gate_passed,
        "hard_gate_failures": tuple(gate_failures),
        "legacy_setup": bool(gate_passed and legacy.valid),
        "legacy_failed_conditions": legacy.failed_conditions,
        "major_trend_context": trend,
        "pre_t_local_decline": decline,
        "support_levels": levels,
        "reclaimed_supports": reclaimed,
        "support_reason_codes": tuple(reclaimed),
        "matched_patterns": matched,
        "support_reclaim_t": support_reclaim_t,
    }


def classify_t1_confirmation(
    records_through_t: Sequence[Mapping[str, Any]],
    t1_bar: Mapping[str, Any],
    matched_patterns: Sequence[str],
    reclaimed: Mapping[str, float],
) -> dict[str, Any]:
    """Classify T+1 from T and earlier geometry; later bars are not accepted."""

    if not records_through_t or not matched_patterns or not reclaimed:
        return {"state": "unconfirmed", "pattern": None, "reason": "missing_t_candidate_inputs"}
    t = records_through_t[-1]
    close_t1 = float(t1_bar["close"])
    high_t = float(t["high"])
    results: list[dict[str, Any]] = []
    for pattern in PATTERN_PRIORITY:
        if pattern not in matched_patterns:
            continue
        if pattern == "hammer":
            for support_reason, support_value in reclaimed.items():
                support = float(support_value)
                hold = close_t1 > float(t["close"]) and close_t1 >= support
                failed = close_t1 < min(float(t["low"]), support)
                if hold and close_t1 > high_t:
                    state = "confirmed_strong"
                    reason = "hammer_hold_and_close_above_t_high"
                elif hold:
                    state = "confirmed_hold"
                    reason = "hammer_hold"
                elif failed:
                    state = "failed"
                    reason = "hammer_close_below_failure_level"
                else:
                    state = "unconfirmed"
                    reason = "hammer_neither_confirmed_nor_failed"
                results.append({
                    "state": state,
                    "pattern": pattern,
                    "reason": reason,
                    "hold_threshold": float(t["close"]),
                    "pattern_low": float(t["low"]),
                    "support": support,
                    "support_reason": support_reason,
                })
            continue
        elif pattern in ("bullish_engulfing", "piercing"):
            if len(records_through_t) < 2:
                continue
            bars = records_through_t[-2:]
            body_low = min(min(float(bar["open"]), float(bar["close"])) for bar in bars)
            body_high = max(max(float(bar["open"]), float(bar["close"])) for bar in bars)
            threshold = (body_low + body_high) / 2.0
            pattern_low = min(float(bar["low"]) for bar in bars)
            hold = close_t1 >= threshold and close_t1 >= pattern_low
            failed = close_t1 < pattern_low
        else:
            if len(records_through_t) < 3:
                continue
            bars = records_through_t[-3:]
            pattern_low = min(float(bar["low"]) for bar in bars)
            threshold = float(t["close"])
            hold = close_t1 >= threshold and close_t1 >= pattern_low
            failed = close_t1 < pattern_low

        if hold and close_t1 > high_t:
            state = "confirmed_strong"
            reason = f"{pattern}_hold_and_close_above_t_high"
        elif hold:
            state = "confirmed_hold"
            reason = f"{pattern}_hold"
        elif failed:
            state = "failed"
            reason = f"{pattern}_close_below_failure_level"
        else:
            state = "unconfirmed"
            reason = f"{pattern}_neither_confirmed_nor_failed"
        results.append({
            "state": state,
            "pattern": pattern,
            "reason": reason,
            "hold_threshold": threshold,
            "pattern_low": pattern_low,
            "support": None,
            "support_reason": None,
        })

    rank = {"confirmed_strong": 3, "confirmed_hold": 2, "unconfirmed": 1, "failed": 0}
    if not results:
        return {"state": "unconfirmed", "pattern": None, "reason": "no_classifiable_pattern"}
    return max(results, key=lambda result: rank[result["state"]])


def five_close_label(reference_close: float, future_closes: Sequence[float]) -> bool:
    """Apply the fixed +3% hit and -3% floor label to exactly five closes."""

    if reference_close <= 0 or len(future_closes) != 5:
        raise ValueError("label requires a positive reference and exactly five future closes")
    values = [float(value) for value in future_closes]
    return max(values) >= reference_close * 1.03 and min(values) >= reference_close * 0.97


def t_day_label(records: Sequence[Mapping[str, Any]], t_index: int) -> bool:
    """Label T from stock-bar closes T+1 through T+5 relative to T close."""

    future = records[t_index + 1:t_index + 6]
    return five_close_label(float(records[t_index]["close"]), [float(bar["close"]) for bar in future])


def post_confirmation_label(records: Sequence[Mapping[str, Any]], t_index: int) -> bool:
    """Label confirmation from T+2 through T+6 relative to T+1 close."""

    future = records[t_index + 2:t_index + 7]
    return five_close_label(float(records[t_index + 1]["close"]), [float(bar["close"]) for bar in future])


def wilson_interval(hits: int, observations: int, z: float = 1.96) -> tuple[float | None, float | None]:
    if observations == 0:
        return None, None
    rate = hits / observations
    denominator = 1.0 + z * z / observations
    centre = rate + z * z / (2.0 * observations)
    margin = z * math.sqrt(rate * (1.0 - rate) / observations + z * z / (4.0 * observations**2))
    return (centre - margin) / denominator, (centre + margin) / denominator


def summarize_counts(observations: int, hits: int) -> dict[str, Any]:
    false_positives = observations - hits
    lower, upper = wilson_interval(hits, observations)
    return {
        "n": observations,
        "hits": hits,
        "false_positives": false_positives,
        "fpr": false_positives / observations if observations else None,
        "precision": hits / observations if observations else None,
        "wilson_lower_95": lower,
        "wilson_upper_95": upper,
    }


def evaluate_decision(
    summaries: Mapping[str, Mapping[str, Mapping[str, Any]]],
    *,
    min_fpr_reduction: float = 0.20,
    min_retention: float = 0.40,
    min_observations: int = 300,
) -> dict[str, Any]:
    """Apply all conservative Stage 1 gates on the leakage-aligned horizon."""

    baseline_name = "legacy_setup_post_confirmation_horizon"
    confirmed_name = "support_reclaim_confirmed_post_confirmation_horizon"
    failures: list[str] = []
    comparisons: dict[str, Any] = {}
    for period in PERIODS:
        baseline = summaries[baseline_name][period]
        confirmed = summaries[confirmed_name][period]
        baseline_n = int(baseline["n"])
        confirmed_n = int(confirmed["n"])
        retention = confirmed_n / baseline_n if baseline_n else 0.0
        baseline_fpr = baseline["fpr"]
        confirmed_fpr = confirmed["fpr"]
        fpr_reduction = (
            (baseline_fpr - confirmed_fpr) / baseline_fpr
            if baseline_fpr not in (None, 0) and confirmed_fpr is not None
            else 0.0
        )
        precision_lift = (
            confirmed["precision"] - baseline["precision"]
            if confirmed["precision"] is not None and baseline["precision"] is not None
            else 0.0
        )
        wilson_change = (
            confirmed["wilson_lower_95"] - baseline["wilson_lower_95"]
            if confirmed["wilson_lower_95"] is not None and baseline["wilson_lower_95"] is not None
            else float("-inf")
        )
        comparisons[period] = {
            "relative_fpr_reduction": fpr_reduction,
            "candidate_retention": retention,
            "precision_lift": precision_lift,
            "wilson_lower_change": wilson_change,
        }
        if confirmed_n < min_observations:
            failures.append(f"{period}:confirmed_n_below_{min_observations}")
        if fpr_reduction < min_fpr_reduction:
            failures.append(f"{period}:fpr_reduction_below_{min_fpr_reduction:.2f}")
        if retention < min_retention:
            failures.append(f"{period}:candidate_retention_below_{min_retention:.2f}")
        if precision_lift <= 0:
            failures.append(f"{period}:precision_lift_not_positive")
        if wilson_change < 0:
            failures.append(f"{period}:wilson_lower_deteriorated")
    return {"passed": not failures, "failure_reasons": failures, "comparisons": comparisons}
