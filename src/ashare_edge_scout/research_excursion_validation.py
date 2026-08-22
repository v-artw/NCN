"""Full-sample rolling 5/10-trading-day intraday excursion validation."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np
import pandas as pd

from .research_nextday_validation import (
    ANNOTATION_CANDIDATES,
    CANDIDATE_REGISTRY,
    EXCLUDED_CANDIDATES,
    IMPLEMENTED_CANDIDATES,
    PRIMARY_CANDIDATES,
    candidate_masks,
    registry_json,
)
from .research_precision70 import production_gate_mask
from .research_v2 import summarize_counts

SCHEMA_VERSION = "ncn_5d_10d_intraday_excursion_v1"
DEFAULT_START_DATE = "1900-01-01"
HORIZONS = (5, 10)
THRESHOLDS = {"pass_3pct": 0.03, "full_5pct": 0.05}
MIN_BASELINE_ROWS = 150


def _future_excursions(data: pd.DataFrame) -> dict[pd.Timestamp, dict[str, Any]]:
    trade = data.get("tradestatus", pd.Series(index=data.index, dtype=object)).astype("string")
    tradable_indices = np.flatnonzero(trade.eq("1").fillna(False).to_numpy())
    close = pd.to_numeric(data.get("close"), errors="coerce").to_numpy(dtype=float)
    high = pd.to_numeric(data.get("high"), errors="coerce").to_numpy(dtype=float)
    dates = pd.to_datetime(data["date"], errors="coerce").to_numpy()
    position_by_index = {int(index): position for position, index in enumerate(tradable_indices)}
    outcomes: dict[pd.Timestamp, dict[str, Any]] = {}
    for index in range(len(data)):
        origin_date = pd.Timestamp(dates[index])
        position = position_by_index.get(index)
        row: dict[str, Any] = {"target_date": pd.NaT}
        if position is None or not np.isfinite(close[index]) or close[index] <= 0:
            for horizon in HORIZONS:
                row[f"status_{horizon}d"] = "origin_invalid"
            outcomes[origin_date] = row
            continue
        future_indices = tradable_indices[position + 1:position + 11]
        if len(future_indices):
            row["target_date"] = pd.Timestamp(dates[future_indices[0]])
        for horizon in HORIZONS:
            if len(future_indices) < horizon:
                row[f"status_{horizon}d"] = "pending"
                continue
            future_highs = high[future_indices[:horizon]]
            if not np.isfinite(future_highs).all() or np.any(future_highs <= 0):
                row[f"status_{horizon}d"] = "target_invalid"
                continue
            maximum_high = float(future_highs.max())
            excursion = maximum_high / close[index] - 1.0
            passed = bool(maximum_high > close[index] * 1.03)
            full = bool(maximum_high >= close[index] * 1.05)
            row[f"status_{horizon}d"] = "mature"
            row[f"max_excursion_{horizon}d"] = excursion
            row[f"pass_3pct_{horizon}d"] = passed
            row[f"full_5pct_{horizon}d"] = full
            row[f"score_{horizon}d"] = 2 if full else 1 if passed else 0
        outcomes[origin_date] = row
    return outcomes


def build_excursion_panel(
    code: str,
    frame: pd.DataFrame,
    config: Mapping[str, Any],
    *,
    start_date: str = DEFAULT_START_DATE,
    end_date: str | None = None,
) -> pd.DataFrame:
    data = frame.copy()
    data["date"] = pd.to_datetime(data.get("date"), errors="coerce").dt.normalize()
    data = data.dropna(subset=["date"]).sort_values("date", kind="stable").drop_duplicates("date", keep="last").reset_index(drop=True)
    masks = candidate_masks(data)
    trade = data.get("tradestatus", pd.Series(index=data.index, dtype=object)).astype("string")
    selected = data["date"].ge(pd.Timestamp(start_date))
    if end_date is not None:
        selected &= data["date"].le(pd.Timestamp(end_date))
    panel = pd.DataFrame({
        "code": code,
        "origin_date": data["date"],
        "date": data["date"],
        "trading_index": trade.eq("1").astype(int).cumsum().sub(1).where(trade.eq("1"), np.nan),
        "admitted": production_gate_mask(code, data, config),
    }).loc[selected].reset_index(drop=True)
    for name in IMPLEMENTED_CANDIDATES:
        if name in masks:
            panel[name] = panel["date"].map(dict(zip(data["date"], masks[name], strict=True))).fillna(False).astype(bool)
    outcomes = _future_excursions(data)
    rows = panel["origin_date"].map(outcomes)
    panel["target_date"] = pd.to_datetime(rows.map(lambda value: value.get("target_date", pd.NaT)))
    for horizon in HORIZONS:
        panel[f"status_{horizon}d"] = rows.map(lambda value, h=horizon: value.get(f"status_{h}d", "missing"))
        panel[f"max_excursion_{horizon}d"] = pd.to_numeric(rows.map(lambda value, h=horizon: value.get(f"max_excursion_{h}d", np.nan)), errors="coerce")
        for label in THRESHOLDS:
            panel[f"{label}_{horizon}d"] = pd.array(rows.map(lambda value, h=horizon, key=label: value.get(f"{key}_{h}d", pd.NA)), dtype="boolean")
        panel[f"score_{horizon}d"] = pd.to_numeric(rows.map(lambda value, h=horizon: value.get(f"score_{h}d", np.nan)), errors="coerce")
    return panel


def _periods(panel: pd.DataFrame) -> dict[str, tuple[int, int]]:
    years = sorted(int(year) for year in panel["target_date"].dropna().dt.year.unique())
    return {"full_available_history": (years[0], years[-1]), **{f"year_{year}": (year, year) for year in years}}


def _summary(signal: pd.DataFrame, baseline: pd.DataFrame, label: str) -> dict[str, Any]:
    rows = signal.loc[signal[label].notna()]
    result = summarize_counts(len(rows), int(rows[label].astype(bool).sum()))
    result["target_dates"] = int(rows["target_date"].nunique())
    result["codes"] = int(rows["code"].nunique())
    counts = rows.groupby("target_date").size()
    by_date = baseline.loc[baseline["target_date"].isin(counts.index)].groupby("target_date")[label].agg(["count", "sum"])
    weights = counts.reindex(by_date.index).astype(float)
    weighted_n = int(weights.sum())
    weighted_hits = float((weights * by_date["sum"].div(by_date["count"])).sum()) if weighted_n else 0.0
    baseline_rate = weighted_hits / weighted_n if weighted_n else None
    result["same_target_date_baseline"] = {"weighted_n": weighted_n, "weighted_hits": weighted_hits, "precision": baseline_rate}
    result["rate_lift"] = None if result["precision"] is None or baseline_rate is None else result["precision"] - baseline_rate
    return result


def aggregate_excursion_metrics(panel: pd.DataFrame) -> dict[str, Any]:
    periods = _periods(panel)
    metrics: dict[str, Any] = {}
    score_distributions: dict[str, Any] = {}
    for horizon in HORIZONS:
        status = f"status_{horizon}d"
        mature = panel.loc[panel["admitted"].fillna(False) & panel[status].eq("mature")].copy()
        counts = mature.groupby("target_date").size()
        baseline = mature.loc[mature["target_date"].isin(set(counts[counts.ge(MIN_BASELINE_ROWS)].index))]
        metrics[f"{horizon}d"] = {}
        score_distributions[f"{horizon}d"] = {}
        for name in IMPLEMENTED_CANDIDATES:
            if name not in panel:
                continue
            usable = panel.loc[panel[name].fillna(False) & panel["admitted"].fillna(False) & panel[status].eq("mature") & panel["target_date"].isin(baseline["target_date"])]
            metrics[f"{horizon}d"][name] = {}
            score_distributions[f"{horizon}d"][name] = {}
            for period, (first, last) in periods.items():
                candidate_period = usable.loc[usable["target_date"].dt.year.between(first, last)]
                baseline_period = baseline.loc[baseline["target_date"].dt.year.between(first, last)]
                metrics[f"{horizon}d"][name][period] = {
                    label: _summary(candidate_period, baseline_period, f"{label}_{horizon}d")
                    for label in THRESHOLDS
                }
                score_distributions[f"{horizon}d"][name][period] = {
                    str(score): int(count) for score, count in candidate_period[f"score_{horizon}d"].value_counts().sort_index().items()
                }
    return {"periods": periods, "metrics": metrics, "score_distributions": score_distributions}


def _combine_years(metrics: Mapping[str, Mapping[str, Any]], years: range, label: str) -> dict[str, Any]:
    cells = [metrics[f"year_{year}"][label] for year in years if f"year_{year}" in metrics]
    n = sum(int(cell["n"]) for cell in cells)
    hits = sum(int(cell["hits"]) for cell in cells)
    result = summarize_counts(n, hits)
    baseline_n = sum(int(cell["same_target_date_baseline"]["weighted_n"]) for cell in cells)
    baseline_hits = sum(float(cell["same_target_date_baseline"]["weighted_hits"]) for cell in cells)
    baseline_rate = baseline_hits / baseline_n if baseline_n else None
    result["target_dates"] = sum(int(cell["target_dates"]) for cell in cells)
    result["same_target_date_baseline"] = {"weighted_n": baseline_n, "weighted_hits": baseline_hits, "precision": baseline_rate}
    result["rate_lift"] = None if result["precision"] is None or baseline_rate is None else result["precision"] - baseline_rate
    return result


def evaluate_excursion_stability(
    metrics: Mapping[str, Mapping[str, Any]],
    *,
    label: str,
    direction: str,
    last_year: int,
) -> dict[str, Any]:
    if direction == "annotation":
        return {"passed": False, "failure_codes": ["annotation_only"], "decision_periods": {}}
    periods = {
        "selection_2021_2023": _combine_years(metrics, range(2021, 2024), label),
        "audit_2024_present": _combine_years(metrics, range(2024, last_year + 1), label),
    }
    failures: list[str] = []
    for period, cell in periods.items():
        baseline = cell["same_target_date_baseline"]["precision"]
        directional_lift = -cell["rate_lift"] if direction == "risk" and cell["rate_lift"] is not None else cell["rate_lift"]
        if int(cell["n"]) < 300:
            failures.append(f"{period}:n_below_300")
        if int(cell["target_dates"]) < 120:
            failures.append(f"{period}:target_dates_below_120")
        if directional_lift is None or directional_lift < 0.03:
            failures.append(f"{period}:directional_lift_below_0.03")
        separated = (
            cell["wilson_upper_95"] < baseline
            if direction == "risk" and cell["wilson_upper_95"] is not None and baseline is not None
            else cell["wilson_lower_95"] > baseline
            if cell["wilson_lower_95"] is not None and baseline is not None
            else False
        )
        if not separated:
            failures.append(f"{period}:wilson_not_separated_from_baseline")
    complete_audit_years = range(2024, last_year if last_year == 2026 else last_year + 1)
    for year in complete_audit_years:
        cell = metrics.get(f"year_{year}", {}).get(label)
        directional_lift = -cell["rate_lift"] if cell and direction == "risk" and cell["rate_lift"] is not None else cell["rate_lift"] if cell else None
        if directional_lift is None or directional_lift <= 0:
            failures.append(f"year_{year}:directional_lift_not_positive")
    return {"passed": not failures, "failure_codes": failures, "decision_periods": periods}


def build_excursion_report(*, panel: pd.DataFrame, code_list: list[str], code_list_sha256: str, start_date: str, end_date: str | None, workers: int) -> dict[str, Any]:
    aggregated = aggregate_excursion_metrics(panel)
    years = [value[0] for key, value in aggregated["periods"].items() if key.startswith("year_")]
    last_year = max(years)
    decisions = {
        horizon: {
            label: {
                name: evaluate_excursion_stability(
                    candidate_metrics,
                    label=label,
                    direction=CANDIDATE_REGISTRY[name].direction,
                    last_year=last_year,
                )
                for name, candidate_metrics in aggregated["metrics"][horizon].items()
            }
            for label in THRESHOLDS
        }
        for horizon in ("5d", "10d")
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "study": "full_sample_5d_10d_intraday_excursion",
        "research_only": True,
        "classification_only": True,
        "production_enabled": False,
        "alignment": {
            "origin": "signals use data visible through T only",
            "outcome": "next 5 and 10 tradable daily highs beginning at D, anchored to T close",
            "pass_3pct": "max high / T close - 1 is strictly greater than 0.03",
            "full_5pct": "max high / T close - 1 is greater than or equal to 0.05",
        },
        "sample": {"method": "all_current_main_board_sorted_code", "codes": len(code_list), "code_list": code_list, "code_list_sha256": code_list_sha256},
        "date_range": {"start_date": start_date, "end_date": end_date},
        "workers": workers,
        "candidate_registry": registry_json(),
        "primary_candidates": list(PRIMARY_CANDIDATES),
        "annotation_candidates": list(ANNOTATION_CANDIDATES),
        "excluded_candidates": list(EXCLUDED_CANDIDATES),
        "decision": {
            "gates": "Both 2021-2023 and 2024-present require n>=300, >=120 target dates, >=3pp directional lift, Wilson separation in the expected direction, and positive complete-audit-year directional lift.",
            "by_horizon_and_threshold": decisions,
            "passed_candidates": {
                horizon: {
                    label: sorted(name for name, value in candidates.items() if value["passed"])
                    for label, candidates in labels.items()
                }
                for horizon, labels in decisions.items()
            },
        },
        **aggregated,
        "limitations": [
            "Daily high records an intraday touch, not executable fill quality or realized return.",
            "Adjusted current-vintage data and current-file survivorship remain limitations.",
            "No order, position, cost, P&L, or personalized action is modeled.",
        ],
    }
