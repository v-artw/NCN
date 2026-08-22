"""Pure research classifiers for strict rising-three-methods Stage 1."""

from __future__ import annotations

import math
import statistics
from collections.abc import Mapping, Sequence
from typing import Any

from .research_v2 import summarize_counts
from .signals.signal_scoring import apply_hard_gates


CALIBRATION = "calibration_2021_2024"
HOLDOUT = "holdout_2025_2026"
AGGREGATE = "aggregate_2021_2026"
DECISION_PERIODS = (CALIBRATION, HOLDOUT)
YEARS = tuple(range(2021, 2027))


def _finite_values(records: Sequence[Mapping[str, Any]], field: str) -> list[float] | None:
    try:
        values = [float(record[field]) for record in records]
    except (KeyError, TypeError, ValueError):
        return None
    return values if all(math.isfinite(value) for value in values) else None


def benchmark_regime_through_t(records_through_t: Sequence[Mapping[str, Any]]) -> bool:
    """Apply the frozen benchmark regime using observations through T only."""

    if len(records_through_t) < 25:
        return False
    closes = _finite_values(records_through_t[-25:], "close")
    if closes is None or closes[-6] <= 0:
        return False
    sma20_t = sum(closes[-20:]) / 20.0
    sma20_t_minus_5 = sum(closes[-25:-5]) / 20.0
    return bool(
        closes[-1] > sma20_t
        and sma20_t >= sma20_t_minus_5
        and closes[-1] / closes[-6] - 1.0 >= -0.03
    )


def stock_trend_through_t(records_through_t: Sequence[Mapping[str, Any]]) -> bool:
    """Apply the frozen individual-stock trend using observations through T only."""

    if len(records_through_t) < 65:
        return False
    closes = _finite_values(records_through_t[-65:], "close")
    if closes is None or closes[-21] <= 0:
        return False
    sma20_t = sum(closes[-20:]) / 20.0
    sma60_t = sum(closes[-60:]) / 60.0
    sma20_t_minus_5 = sum(closes[-25:-5]) / 20.0
    sma60_t_minus_5 = sum(closes[-65:-5]) / 60.0
    return bool(
        closes[-1] > sma20_t > sma60_t
        and sma20_t > sma20_t_minus_5
        and sma60_t > sma60_t_minus_5
        and 0.05 <= closes[-1] / closes[-21] - 1.0 <= 0.25
    )


def _strict_pattern_length(
    records_through_t: Sequence[Mapping[str, Any]], consolidation_length: int
) -> bool:
    pattern_length = consolidation_length + 2
    if consolidation_length not in (2, 3, 4) or len(records_through_t) < pattern_length + 19:
        return False
    try:
        bars = records_through_t[-pattern_length:]
        impulse = bars[0]
        consolidation = bars[1:-1]
        completion = bars[-1]
        values = {
            field: [float(bar[field]) for bar in bars]
            for field in ("open", "high", "low", "close", "volume")
        }
        impulse_index = len(records_through_t) - pattern_length
        impulse_window = records_through_t[impulse_index - 19:impulse_index + 1]
        impulse_volumes = [float(bar["volume"]) for bar in impulse_window]
        t_volumes = [float(bar["volume"]) for bar in records_through_t[-20:]]
    except (KeyError, TypeError, ValueError):
        return False
    numeric = [value for field_values in values.values() for value in field_values]
    if not all(math.isfinite(value) for value in numeric + impulse_volumes + t_volumes):
        return False
    if any(volume < 0 for volume in impulse_volumes + t_volumes):
        return False
    if any(
        float(bar["high"]) <= float(bar["low"]) or float(bar["volume"]) <= 0
        for bar in bars
    ):
        return False

    impulse_range = float(impulse["high"]) - float(impulse["low"])
    impulse_body = abs(float(impulse["close"]) - float(impulse["open"]))
    impulse_volume = float(impulse["volume"])
    if not (
        float(impulse["close"]) > float(impulse["open"])
        and impulse_body >= 0.55 * impulse_range
        and (float(impulse["close"]) - float(impulse["low"])) / impulse_range >= 0.75
        and impulse_volume >= sum(impulse_volumes) / 20.0
    ):
        return False

    falling_closes = 0
    previous = impulse
    for candle in consolidation:
        if not (
            float(candle["high"]) <= float(impulse["high"])
            and float(candle["low"]) >= float(impulse["low"])
            and abs(float(candle["close"]) - float(candle["open"])) <= 0.40 * impulse_body
            and float(candle["volume"]) < impulse_volume
        ):
            return False
        falling_closes += int(float(candle["close"]) <= float(previous["close"]))
        previous = candle
    median_volume = float(statistics.median(float(candle["volume"]) for candle in consolidation))
    if falling_closes * 2 < consolidation_length or not median_volume < impulse_volume:
        return False

    completion_range = float(completion["high"]) - float(completion["low"])
    completion_open = float(completion["open"])
    completion_close = float(completion["close"])
    completion_volume = float(completion["volume"])
    completion_body = abs(completion_close - completion_open)
    upper_shadow = float(completion["high"]) - max(completion_open, completion_close)
    return bool(
        completion_close > completion_open
        and completion_open > float(consolidation[-1]["close"])
        and completion_close > float(impulse["close"])
        and completion_body >= 0.55 * completion_range
        and (completion_close - float(completion["low"])) / completion_range >= 0.65
        and upper_shadow <= 0.20 * completion_range
        and completion_volume > median_volume
        and completion_volume <= 2.8 * (sum(t_volumes) / 20.0)
    )


def strict_pattern_ending_at_t(records_through_t: Sequence[Mapping[str, Any]]) -> int | None:
    """Return the longest matching consolidation length, counting T once."""

    for consolidation_length in (4, 3, 2):
        if _strict_pattern_length(records_through_t, consolidation_length):
            return consolidation_length
    return None


def five_close_label(reference_close: float, future_closes: Sequence[float]) -> bool:
    """Apply the frozen label to exactly T+1 through T+5 closes."""

    if not math.isfinite(float(reference_close)) or reference_close <= 0 or len(future_closes) != 5:
        raise ValueError("label requires a positive finite reference and exactly five future closes")
    values = [float(value) for value in future_closes]
    if not all(math.isfinite(value) for value in values):
        raise ValueError("future closes must be finite")
    return max(values) >= reference_close * 1.03 and min(values) >= reference_close * 0.97


def next_five_trading_closes(
    records: Sequence[Mapping[str, Any]], t_index: int
) -> list[float] | None:
    """Return the next five tradable closes, excluding suspension rows."""

    closes: list[float] = []
    for record in records[t_index + 1:]:
        if str(record.get("tradestatus", "1")) != "1":
            continue
        try:
            close = float(record["close"])
        except (KeyError, TypeError, ValueError):
            return None
        if not math.isfinite(close):
            return None
        closes.append(close)
        if len(closes) == 5:
            return closes
    return None


def classify_t(
    code: str,
    records_through_t: Sequence[Mapping[str, Any]],
    benchmark_records_through_t: Sequence[Mapping[str, Any]],
    config: Mapping[str, Any],
    *,
    benchmark_regime: bool | None = None,
) -> dict[str, Any]:
    """Classify baseline and strict-pattern eligibility at T."""

    gate_passed, gate_failures = apply_hard_gates(code, records_through_t, config)
    market = (
        benchmark_regime_through_t(benchmark_records_through_t)
        if benchmark_regime is None
        else bool(benchmark_regime)
    )
    trend = stock_trend_through_t(records_through_t)
    baseline = bool(gate_passed and market and trend)
    pattern_length = strict_pattern_ending_at_t(records_through_t) if baseline else None
    return {
        "gate_passed": gate_passed,
        "gate_failures": tuple(gate_failures),
        "market_regime": market,
        "stock_trend": trend,
        "trend_context_baseline": baseline,
        "strict_pattern": bool(baseline and pattern_length is not None),
        "consolidation_length": pattern_length,
    }


def evaluate_decision(
    summaries: Mapping[str, Mapping[str, Mapping[str, Any]]]
) -> dict[str, Any]:
    """Apply every frozen Stage 1 success threshold with stable failure codes."""

    baseline = summaries["trend_context_baseline"]
    pattern = summaries["strict_pattern"]
    failures: list[str] = []
    comparisons: dict[str, Any] = {}
    for period in DECISION_PERIODS:
        base = baseline[period]
        candidate = pattern[period]
        precision_lift = (
            candidate["precision"] - base["precision"]
            if candidate["precision"] is not None and base["precision"] is not None
            else None
        )
        relative_fpr_reduction = (
            (base["fpr"] - candidate["fpr"]) / base["fpr"]
            if base["fpr"] not in (None, 0) and candidate["fpr"] is not None
            else None
        )
        comparisons[period] = {
            "precision_lift": precision_lift,
            "relative_fpr_reduction": relative_fpr_reduction,
            "pattern_wilson_lower_minus_baseline_precision": (
                candidate["wilson_lower_95"] - base["precision"]
                if candidate["wilson_lower_95"] is not None and base["precision"] is not None
                else None
            ),
        }
        if precision_lift is None or precision_lift <= 0:
            failures.append(f"{period}:precision_lift_not_positive")
        if relative_fpr_reduction is None or relative_fpr_reduction < 0.10:
            failures.append(f"{period}:relative_fpr_reduction_below_0.10")
        if int(candidate["n"]) < 150:
            failures.append(f"{period}:pattern_n_below_150")
        if (
            candidate["wilson_lower_95"] is None
            or base["precision"] is None
            or candidate["wilson_lower_95"] < base["precision"]
        ):
            failures.append(f"{period}:pattern_wilson_lower_below_baseline_precision")

    aggregate_lift = (
        pattern[AGGREGATE]["precision"] - baseline[AGGREGATE]["precision"]
        if pattern[AGGREGATE]["precision"] is not None
        and baseline[AGGREGATE]["precision"] is not None
        else None
    )
    comparisons[AGGREGATE] = {"precision_lift": aggregate_lift}
    if aggregate_lift is None or aggregate_lift < 0.03:
        failures.append(f"{AGGREGATE}:precision_lift_below_0.03")
    for year in range(2021, 2026):
        if int(pattern[f"year_{year}"]["n"]) < 50:
            failures.append(f"year_{year}:pattern_n_below_50")
    return {"passed": not failures, "failure_codes": failures, "comparisons": comparisons}


def empty_summaries() -> dict[str, dict[str, dict[str, Any]]]:
    """Return the complete frozen report shape with zero observations."""

    keys = (*DECISION_PERIODS, AGGREGATE, *(f"year_{year}" for year in YEARS))
    return {
        strategy: {key: summarize_counts(0, 0) for key in keys}
        for strategy in ("trend_context_baseline", "strict_pattern")
    }
