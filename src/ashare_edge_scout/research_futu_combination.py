"""Frozen Shengbei-state plus KDJ-trigger combination evaluation."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pandas as pd

from .research_futu_ranking import PERIODS, _matched_summary, _period_failures
from .research_precision70 import nonoverlapping_origins


COMBINATION = "shengbei_long_state_kdj_buy"
PARENT = "kdj_trend_pro_buy"


def attach_combination(panel: pd.DataFrame) -> pd.DataFrame:
    """Attach the fixed T-1 Shengbei-long plus T KDJ trigger mask."""

    result = panel.copy()
    prior_long = result.groupby("code", sort=False)["shengbei_state"].shift(1).eq(1.0)
    result[COMBINATION] = prior_long & result[PARENT].fillna(False)
    return result


def _period_keys() -> dict[str, tuple[int, int]]:
    return {**PERIODS, **{f"year_{year}": (year, year) for year in range(2021, 2027)}}


def _parent_summary(signal_rows: pd.DataFrame, parent_rows: pd.DataFrame) -> dict[str, Any]:
    signal = signal_rows.loc[signal_rows["label"].notna()]
    counts = signal.groupby("date").size()
    parent = parent_rows.loc[parent_rows["label"].notna() & parent_rows["date"].isin(counts.index)]
    by_date = parent.groupby("date")["label"].agg(["count", "sum"])
    weights = counts.reindex(by_date.index).astype(float)
    weighted_n = float(weights.sum())
    weighted_hits = float((weights * by_date["sum"].div(by_date["count"])).sum())
    precision = weighted_hits / weighted_n if weighted_n else None
    signal_precision = signal["label"].astype(bool).mean() if len(signal) else None
    return {
        "parent_observations": int(len(parent)),
        "parent_signal_dates": int(parent["date"].nunique()),
        "weighted_n": int(weighted_n),
        "weighted_hits": weighted_hits,
        "precision": precision,
        "combination_precision_delta": (
            None if signal_precision is None or precision is None else signal_precision - precision
        ),
    }


def aggregate_combination_metrics(panel: pd.DataFrame) -> tuple[dict[str, Any], dict[str, Any]]:
    """Report combination metrics against market and same-date parent KDJ."""

    mature = panel.loc[panel["admitted"].fillna(False) & panel["label"].notna()].copy()
    counts = mature.groupby("date").size()
    valid_dates = set(counts[counts.ge(150)].index)
    baseline = mature.loc[mature["date"].isin(valid_dates)]
    signal_all = baseline.loc[baseline[COMBINATION].fillna(False)]
    parent_all = baseline.loc[baseline[PARENT].fillna(False)]
    signal_primary = nonoverlapping_origins(signal_all)
    parent_primary = nonoverlapping_origins(parent_all)
    primary: dict[str, Any] = {}
    all_origin: dict[str, Any] = {}
    for key, (first, last) in _period_keys().items():
        in_period = lambda rows: rows.loc[rows["date"].dt.year.between(first, last)]
        primary_signal = in_period(signal_primary)
        all_signal = in_period(signal_all)
        primary[key] = _matched_summary(primary_signal, in_period(baseline))
        primary[key]["parent_kdj"] = _parent_summary(primary_signal, in_period(parent_primary))
        all_origin[key] = _matched_summary(all_signal, in_period(baseline))
        all_origin[key]["parent_kdj"] = _parent_summary(all_signal, in_period(parent_all))
    return primary, all_origin


def evaluate_combination(primary: Mapping[str, Any], all_origin: Mapping[str, Any]) -> dict[str, Any]:
    """Apply existing gates plus the frozen one-point parent-KDJ gate."""

    selection_failures = _period_failures(primary, all_origin, audit=False)
    audit_failures = _period_failures(primary, all_origin, audit=True)
    for period, failures in (
        ("selection_2023_2024", selection_failures),
        ("audit_2025_2026", audit_failures),
    ):
        delta = primary[period]["parent_kdj"]["combination_precision_delta"]
        if delta is None or delta < 0.01:
            failures.append("parent_kdj_lift_below_0.01")
    return {
        "selection_eligible": not selection_failures,
        "selection_failure_codes": selection_failures,
        "audit_accepted": not audit_failures,
        "audit_failure_codes": audit_failures,
        "accepted_for_prospective_observation": not selection_failures and not audit_failures,
    }
