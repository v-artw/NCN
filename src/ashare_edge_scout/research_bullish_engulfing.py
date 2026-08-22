"""Research-only bullish-engulfing confirmation classifier."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

import pandas as pd

from .research_precision70 import nonoverlapping_origins, production_gate_mask
from .research_v2 import summarize_counts


PERIODS = {"selection_2023_2024": (2023, 2024), "audit_2025_2026": (2025, 2026)}


def _finite(values: Sequence[Any]) -> list[float] | None:
    try:
        result = [float(value) for value in values]
    except (TypeError, ValueError):
        return None
    return result if all(math.isfinite(value) for value in result) else None


def _sma(values: Sequence[float], length: int) -> float | None:
    if len(values) < length:
        return None
    return sum(values[-length:]) / length


def context_at_t(records: Sequence[Mapping[str, Any]], index: int) -> bool:
    if index < 65:
        return False
    rows = records[: index + 1]
    closes = _finite([row.get("close") for row in rows])
    volumes = _finite([row.get("volume") for row in rows])
    if closes is None or volumes is None or len(rows) < 21:
        return False
    sma20 = _sma(closes, 20)
    sma60 = _sma(closes, 60)
    prior20 = _sma(closes[:-5], 20)
    prior60 = _sma(closes[:-5], 60)
    if None in (sma20, sma60, prior20, prior60) or closes[-21] <= 0:
        return False
    low = float(rows[-1]["low"])
    return bool(
        closes[-1] > sma20 > sma60
        and sma20 > prior20
        and sma60 > prior60
        and 0.03 <= closes[-1] / closes[-21] - 1.0 <= 0.30
        and low <= sma20 * 1.01
        and closes[-1] >= sma20
        and str(rows[-2].get("tradestatus", "0")) == "1"
        and volumes[-2] < float(pd.Series(volumes[-22:-2]).median())
    )


def engulfing_at_t(records: Sequence[Mapping[str, Any]], index: int) -> bool:
    if index < 65 or not context_at_t(records, index):
        return False
    previous, current = records[index - 1], records[index]
    if str(current.get("tradestatus", "0")) != "1":
        return False
    values = _finite(
        [previous.get(key) for key in ("open", "high", "low", "close", "volume")]
        + [current.get(key) for key in ("open", "high", "low", "close", "volume")]
    )
    if values is None or previous["volume"] <= 0 or current["volume"] <= 0:
        return False
    po, ph, pl, pc, pv, co, ch, cl, cc, cv = values
    previous_range = ph - pl
    previous_body = po - pc
    current_range = ch - cl
    current_body = cc - co
    volume_median = float(pd.Series([float(row["volume"]) for row in records[index - 21:index - 1]]).median())
    if previous_range <= 0 or current_range <= 0:
        return False
    return bool(
        pc < po
        and previous_body / previous_range >= 0.35
        and cc > co
        and current_body >= 1.10 * previous_body
        and co <= pc
        and cc >= po
        and cv > pv
        and cv >= volume_median
    )


def confirmed_at_t(records: Sequence[Mapping[str, Any]], index: int) -> bool:
    if index + 1 >= len(records) or not engulfing_at_t(records, index):
        return False
    current, next_row = records[index], records[index + 1]
    if str(next_row.get("tradestatus", "0")) != "1":
        return False
    return float(next_row["close"]) > float(current["close"]) and float(next_row["close"]) >= float(current["low"])


def matured_label(records: Sequence[Mapping[str, Any]], index: int) -> bool | None:
    """Label T+2..T+6 relative to the confirmed T+1 close."""
    if index + 6 >= len(records):
        return None
    future = [records[position] for position in range(index + 2, index + 7) if str(records[position].get("tradestatus", "0")) == "1"]
    if len(future) != 5:
        return None
    reference = float(records[index + 1]["close"])
    closes = _finite([row.get("close") for row in future])
    if closes is None or reference <= 0:
        return None
    return max(closes) >= reference * 1.03 and min(closes) >= reference * 0.97


def evaluate_decision(primary: Mapping[str, Any], all_origin: Mapping[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    for period, years in (("selection_2023_2024", (2023, 2024)), ("audit_2025_2026", (2025, 2026))):
        metric = primary[period]
        if metric["n"] < 300:
            failures.append(f"{period}:n_below_300")
        if period == "selection_2023_2024" and metric["signal_dates"] < 120:
            failures.append(f"{period}:signal_dates_below_120")
        if period == "selection_2023_2024" and metric["codes"] < 50:
            failures.append(f"{period}:codes_below_50")
        for year in years:
            minimum = 25 if year == 2026 else 50
            if primary[f"year_{year}"]["n"] < minimum:
                failures.append(f"year_{year}:n_below_{minimum}")
            if primary[f"year_{year}"]["precision_lift"] is None or primary[f"year_{year}"]["precision_lift"] <= 0:
                failures.append(f"year_{year}:lift_not_positive")
        if metric["precision_lift"] is None or metric["precision_lift"] < 0.03:
            failures.append(f"{period}:aggregate_lift_below_0.03")
        if metric["wilson_lower_95"] is None or metric["same_date_baseline"]["precision"] is None or metric["wilson_lower_95"] <= metric["same_date_baseline"]["precision"]:
            failures.append(f"{period}:wilson_lower_not_above_baseline")
        if all_origin[period]["precision_lift"] is None or all_origin[period]["precision_lift"] <= 0:
            failures.append(f"{period}:all_origin_lift_not_positive")
    return {"passed": not failures, "failure_codes": failures}


def _summary(rows: pd.DataFrame) -> dict[str, Any]:
    result = summarize_counts(len(rows), int(rows["label"].astype(bool).sum()))
    result["signal_dates"] = int(rows["date"].nunique())
    result["codes"] = int(rows["code"].nunique())
    return result


def aggregate(rows: pd.DataFrame) -> tuple[dict[str, Any], dict[str, Any]]:
    mature = rows.loc[rows["label"].notna()].copy()
    mature["date"] = pd.to_datetime(mature["date"], errors="coerce").dt.normalize()
    mature = mature.dropna(subset=["date"])
    candidate = mature.loc[mature["candidate"]]
    primary = nonoverlapping_origins(candidate)
    all_origin: dict[str, Any] = {}
    primary_metrics: dict[str, Any] = {}
    for name, first, last in (("selection_2023_2024", 2023, 2024), ("audit_2025_2026", 2025, 2026)):
        signal = primary.loc[primary["date"].dt.year.between(first, last)]
        all_signal = candidate.loc[candidate["date"].dt.year.between(first, last)]
        baseline = mature.loc[mature["date"].dt.year.between(first, last)]
        def matched(signal_rows: pd.DataFrame, baseline_rows: pd.DataFrame) -> dict[str, Any]:
            counts = signal_rows.groupby("date").size()
            by_date = baseline_rows.loc[baseline_rows["date"].isin(counts.index)].groupby("date")["label"].agg(["count", "sum"])
            weights = counts.reindex(by_date.index).astype(float)
            weighted_n = float(weights.sum())
            weighted_hits = float((weights * by_date["sum"].div(by_date["count"])).sum())
            result = _summary(signal_rows)
            result["same_date_baseline"] = {"precision": weighted_hits / weighted_n if weighted_n else None, "weighted_n": int(weighted_n), "weighted_hits": weighted_hits}
            result["precision_lift"] = result["precision"] - result["same_date_baseline"]["precision"] if result["precision"] is not None and result["same_date_baseline"]["precision"] is not None else None
            return result
        primary_metrics[name] = matched(signal, baseline)
        all_origin[name] = matched(all_signal, baseline)
    for year in range(2023, 2027):
        primary_metrics[f"year_{year}"] = matched(primary.loc[primary["date"].dt.year.eq(year)], mature.loc[mature["date"].dt.year.eq(year)])
    return primary_metrics, all_origin
