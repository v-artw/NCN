"""Frozen RSRS structure-quality filter for existing MHPG candidates."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np
import pandas as pd

from .research_futu_ranking import PERIODS, _matched_summary, _period_failures, build_futu_panel
from .research_precision70 import nonoverlapping_origins


CANDIDATE = "mhpg_rsrs_quality"
PARENT = "mhpg_buy"
RSRS_REGRESSION_WINDOW = 18
RSRS_STANDARDIZATION_WINDOW = 600
RSRS_Z_MIN = 0.7
RSRS_R2_MIN = 0.8


def rsrs_values(frame: pd.DataFrame) -> pd.DataFrame:
    """Compute frozen rolling RSRS values on tradable rows only."""

    trade = frame.get("tradestatus", pd.Series(index=frame.index, dtype=object)).astype("string")
    trading = frame.loc[trade.eq("1").fillna(False)]
    low = pd.to_numeric(trading.get("low"), errors="coerce").where(lambda value: np.isfinite(value))
    high = pd.to_numeric(trading.get("high"), errors="coerce").where(lambda value: np.isfinite(value))
    low_variance = low.rolling(RSRS_REGRESSION_WINDOW, min_periods=RSRS_REGRESSION_WINDOW).var(ddof=1)
    covariance = low.rolling(RSRS_REGRESSION_WINDOW, min_periods=RSRS_REGRESSION_WINDOW).cov(high, ddof=1)
    slope = covariance.div(low_variance.where(low_variance.gt(0)))
    correlation = low.rolling(RSRS_REGRESSION_WINDOW, min_periods=RSRS_REGRESSION_WINDOW).corr(high)
    slope_mean = slope.rolling(
        RSRS_STANDARDIZATION_WINDOW, min_periods=RSRS_STANDARDIZATION_WINDOW
    ).mean()
    slope_std = slope.rolling(
        RSRS_STANDARDIZATION_WINDOW, min_periods=RSRS_STANDARDIZATION_WINDOW
    ).std(ddof=1)
    result = pd.DataFrame(index=trading.index)
    result["rsrs_slope"] = slope
    result["rsrs_r2"] = correlation.pow(2)
    result["rsrs_z"] = slope.sub(slope_mean).div(slope_std.where(slope_std.gt(0)))
    result["rsrs_quality"] = result["rsrs_z"].gt(RSRS_Z_MIN) & result["rsrs_r2"].ge(RSRS_R2_MIN)
    return result


def build_rsrs_panel(code: str, frame: pd.DataFrame, config: Mapping[str, Any]) -> pd.DataFrame:
    """Attach the frozen RSRS quality filter to the existing MHPG panel."""

    data = frame.copy()
    data["date"] = pd.to_datetime(data.get("date"), errors="coerce").dt.normalize()
    data = data.dropna(subset=["date"]).sort_values("date", kind="stable").drop_duplicates(
        "date", keep="last"
    ).reset_index(drop=True)
    values = rsrs_values(data)
    trading_dates = data.loc[values.index, "date"]
    panel = build_futu_panel(code, data, config)
    for name in ("rsrs_slope", "rsrs_r2", "rsrs_z", "rsrs_quality"):
        panel[name] = panel["date"].map(dict(zip(trading_dates, values[name], strict=True)))
    panel["rsrs_quality"] = panel["rsrs_quality"].fillna(False).astype(bool)
    panel[CANDIDATE] = panel[PARENT].fillna(False) & panel["rsrs_quality"]
    return panel


def _period_keys() -> dict[str, tuple[int, int]]:
    return {**PERIODS, **{f"year_{year}": (year, year) for year in range(2021, 2027)}}


def _matched_parent_summary(signal_rows: pd.DataFrame, parent_rows: pd.DataFrame) -> dict[str, Any]:
    """Compare only candidate dates that retain a spaced parent observation."""

    signal = signal_rows.loc[signal_rows["label"].notna()]
    parent = parent_rows.loc[parent_rows["label"].notna()]
    by_date = parent.groupby("date")["label"].agg(["count", "sum"])
    counts = signal.groupby("date").size().reindex(by_date.index).dropna().astype(float)
    by_date = by_date.reindex(counts.index)
    matched_signal = signal.loc[signal["date"].isin(counts.index)]
    weighted_n = float(counts.sum())
    weighted_hits = float((counts * by_date["sum"].div(by_date["count"])).sum())
    precision = weighted_hits / weighted_n if weighted_n else None
    signal_precision = matched_signal["label"].astype(bool).mean() if len(matched_signal) else None
    return {
        "candidate_observations": int(len(matched_signal)),
        "parent_observations": int(len(parent.loc[parent["date"].isin(counts.index)])),
        "parent_signal_dates": int(len(counts.index)),
        "weighted_n": int(weighted_n),
        "weighted_hits": weighted_hits,
        "precision": precision,
        "combination_precision_delta": (
            None if signal_precision is None or precision is None else signal_precision - precision
        ),
    }


def aggregate_rsrs_metrics(
    panel: pd.DataFrame,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Report candidate metrics against market and matched parent MHPG."""

    mature = panel.loc[panel["admitted"].fillna(False) & panel["label"].notna()].copy()
    counts = mature.groupby("date").size()
    valid_dates = set(counts[counts.ge(150)].index)
    baseline = mature.loc[mature["date"].isin(valid_dates)]
    signal_all = baseline.loc[baseline[CANDIDATE].fillna(False)]
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
        primary[key]["parent_mhpg"] = _matched_parent_summary(
            primary_signal, in_period(parent_primary)
        )
        all_origin[key] = _matched_summary(all_signal, in_period(baseline))
        all_origin[key]["parent_mhpg"] = _matched_parent_summary(
            all_signal, in_period(parent_all)
        )
    coverage = {
        "mature_admitted": int(len(mature)),
        "valid_dates": int(len(valid_dates)),
        "rsrs_available": int(mature["rsrs_z"].notna().sum()),
        "rsrs_quality": int(mature["rsrs_quality"].fillna(False).sum()),
        "parent_mhpg": int(parent_all.shape[0]),
        "candidate": int(signal_all.shape[0]),
    }
    return primary, all_origin, coverage


def _parent_failures(
    primary: Mapping[str, Any], all_origin: Mapping[str, Any], *, audit: bool
) -> list[str]:
    period = "audit_2025_2026" if audit else "selection_2023_2024"
    years = (2025, 2026) if audit else (2023, 2024)
    failures: list[str] = []
    aggregate = primary[period]
    parent_precision = aggregate["parent_mhpg"]["precision"]
    aggregate_delta = aggregate["parent_mhpg"]["combination_precision_delta"]
    if aggregate_delta is None or aggregate_delta < 0.03:
        failures.append("parent_mhpg_lift_below_0.03")
    if (
        aggregate["wilson_lower_95"] is None
        or parent_precision is None
        or aggregate["wilson_lower_95"] <= parent_precision
    ):
        failures.append("wilson_lower_not_above_parent_mhpg")
    for year in years:
        delta = primary[f"year_{year}"]["parent_mhpg"]["combination_precision_delta"]
        if delta is None or delta <= 0:
            failures.append(f"year_{year}_parent_mhpg_lift_not_positive")
    all_delta = all_origin[period]["parent_mhpg"]["combination_precision_delta"]
    if all_delta is None or all_delta <= 0:
        failures.append("all_origin_parent_mhpg_lift_not_positive")
    return failures


def evaluate_rsrs_filter(
    primary: Mapping[str, Any], all_origin: Mapping[str, Any]
) -> dict[str, Any]:
    """Apply the frozen market and matched-parent acceptance gates."""

    selection_failures = _period_failures(primary, all_origin, audit=False)
    selection_failures.extend(_parent_failures(primary, all_origin, audit=False))
    audit_failures = _period_failures(primary, all_origin, audit=True)
    audit_failures.extend(_parent_failures(primary, all_origin, audit=True))
    return {
        "selection_eligible": not selection_failures,
        "selection_failure_codes": selection_failures,
        "audit_accepted": not audit_failures,
        "audit_failure_codes": audit_failures,
        "accepted_for_prospective_observation": not selection_failures and not audit_failures,
    }
