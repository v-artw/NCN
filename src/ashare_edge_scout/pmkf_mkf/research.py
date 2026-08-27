"""Frozen strict MkF green-zone exit research primitives."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np
import pandas as pd

from ..research_precision70 import (
    build_stock_panel,
    nonoverlapping_origins,
)
from ..research_v2 import summarize_counts


PERIODS = {
    "selection_2023_2024": (2023, 2024),
    "holdout_2025_2026": (2025, 2026),
}


def mkf_lines(frame: pd.DataFrame) -> pd.DataFrame:
    """Compute frozen MkF lines on tradable rows only, without future data."""

    data = frame.copy()
    trade = data.get("tradestatus", pd.Series(index=data.index, dtype=object)).astype("string")
    trading = data.loc[trade.eq("1").fillna(False)].copy()
    high = pd.to_numeric(trading.get("high"), errors="coerce")
    low = pd.to_numeric(trading.get("low"), errors="coerce")
    close = pd.to_numeric(trading.get("close"), errors="coerce")

    def range_position(low_window: int, high_window: int) -> pd.Series:
        minimum = low.rolling(low_window, min_periods=low_window).min()
        maximum = high.rolling(high_window, min_periods=high_window).max()
        denominator = maximum - minimum
        return close.sub(minimum).div(denominator.where(denominator.gt(0))).mul(100.0)

    fast_inter = range_position(20, 20)
    fast_near = range_position(15, 15)
    momentum_minimum = low.rolling(2, min_periods=2).min()
    momentum_maximum = high.rolling(4, min_periods=4).max()
    momentum_denominator = momentum_maximum - momentum_minimum
    momentum = close.sub(momentum_minimum).div(momentum_denominator.where(momentum_denominator.gt(0))).mul(100.0)
    result = pd.DataFrame(index=frame.index, columns=["momentum", "inter", "near"], dtype=float)
    result.loc[trading.index, "momentum"] = momentum
    result.loc[trading.index, "inter"] = fast_inter.rolling(5, min_periods=5).mean()
    result.loc[trading.index, "near"] = fast_near.rolling(2, min_periods=2).mean()
    return result


def mkf_red_blue_cross20_lines(frame: pd.DataFrame) -> pd.DataFrame:
    """Compute the migrated US MKF red/blue cross lines on tradable rows only, without future data."""

    data = frame.copy()
    trade = data.get("tradestatus", pd.Series(index=data.index, dtype=object)).astype("string")
    trading = data.loc[trade.eq("1").fillna(False)].copy()
    high = pd.to_numeric(trading.get("high"), errors="coerce")
    low = pd.to_numeric(trading.get("low"), errors="coerce")
    close = pd.to_numeric(trading.get("close"), errors="coerce")

    def rolling_rsv(window: int) -> pd.Series:
        minimum = low.rolling(window, min_periods=window).min()
        maximum = high.rolling(window, min_periods=window).max()
        denominator = maximum - minimum
        return close.sub(minimum).div(denominator.where(denominator.gt(0))).mul(100.0)

    momentum_minimum = low.rolling(2, min_periods=2).min()
    momentum_base_minimum = low.rolling(4, min_periods=4).min()
    momentum_maximum = high.rolling(4, min_periods=4).max()
    momentum_denominator = momentum_maximum - momentum_base_minimum
    momentum = close.sub(momentum_minimum).div(momentum_denominator.where(momentum_denominator.gt(0))).mul(100.0)
    result = pd.DataFrame(index=frame.index, columns=["momentum", "inter", "near"], dtype=float)
    result.loc[trading.index, "momentum"] = momentum
    result.loc[trading.index, "inter"] = rolling_rsv(31).rolling(5, min_periods=5).mean()
    result.loc[trading.index, "near"] = rolling_rsv(5).rolling(2, min_periods=2).mean()
    return result


def mkf_green_exit_mask(frame: pd.DataFrame) -> pd.Series:
    """Require all three lines to move from <=20 at T-1 to >20 at T."""

    lines = mkf_lines(frame)
    trading = frame.get("tradestatus", pd.Series(index=frame.index, dtype=object)).astype("string").eq("1").fillna(False)
    trading_lines = lines.loc[trading]
    prior_green = trading_lines.shift(1).le(20.0).all(axis=1)
    current_above = trading_lines.gt(20.0).all(axis=1)
    signal = pd.Series(False, index=frame.index, dtype=bool)
    signal.loc[trading_lines.index] = (prior_green & current_above).fillna(False)
    return signal


def mkf_red_blue_cross20_under80_mask(frame: pd.DataFrame) -> pd.Series:
    """Legacy raw red/blue cross-up-20 mask, without green-zone episode state."""

    lines = mkf_red_blue_cross20_lines(frame)
    trading = frame.get("tradestatus", pd.Series(index=frame.index, dtype=object)).astype("string").eq("1").fillna(False)
    trading_lines = lines.loc[trading]
    prior = trading_lines.shift(1)
    red_cross = prior["momentum"].lt(20.0) & trading_lines["momentum"].ge(20.0)
    blue_cross = prior["near"].lt(20.0) & trading_lines["near"].ge(20.0)
    under_80 = trading_lines["momentum"].lt(80.0) & trading_lines["near"].lt(80.0)
    signal = pd.Series(False, index=frame.index, dtype=bool)
    signal.loc[trading_lines.index] = (red_cross & blue_cross & under_80).fillna(False)
    return signal


def mkf_red_blue_cross20_green_exit_under80_mask(frame: pd.DataFrame) -> pd.Series:
    """Require red/blue to cross up 20 on the BULLCLUSTER exit row."""

    lines = mkf_red_blue_cross20_lines(frame)
    trading = frame.get("tradestatus", pd.Series(index=frame.index, dtype=object)).astype("string").eq("1").fillna(False)
    trading_lines = lines.loc[trading]
    prior = trading_lines.shift(1)
    prior_bullcluster = prior[["momentum", "inter", "near"]].le(20.0).all(axis=1)
    red_blue_cross = (
        prior["momentum"].lt(20.0)
        & trading_lines["momentum"].ge(20.0)
        & prior["near"].lt(20.0)
        & trading_lines["near"].ge(20.0)
    )
    under_80 = trading_lines["momentum"].lt(80.0) & trading_lines["near"].lt(80.0)
    signal = pd.Series(False, index=frame.index, dtype=bool)
    signal.loc[trading_lines.index] = (prior_bullcluster & red_blue_cross & under_80).fillna(False)
    return signal


def mkf_red_blue_cross20_post_lag_mask(frame: pd.DataFrame, allowed_lags: set[int] | frozenset[int] = frozenset({0, 1, 2})) -> pd.Series:
    base = mkf_red_blue_cross20_green_exit_under80_mask(frame)
    trading = frame.get("tradestatus", pd.Series(index=frame.index, dtype=object)).astype("string").eq("1").fillna(False)
    tradable_indexes = list(frame.index[trading])
    result = pd.Series(False, index=frame.index, dtype=bool)
    for position, row_index in enumerate(tradable_indexes):
        if not bool(base.loc[row_index]):
            continue
        for lag in allowed_lags:
            if lag < 0:
                continue
            target_position = position + lag
            if target_position < len(tradable_indexes):
                result.loc[tradable_indexes[target_position]] = True
    return result


mkf_first_red_blue_cross20_after_green_exit_under80_mask = mkf_red_blue_cross20_green_exit_under80_mask


def build_mkf_panel(code: str, frame: pd.DataFrame, config: Mapping[str, Any]) -> pd.DataFrame:
    """Build causal label/gate rows and attach the exact MkF transition."""

    data = frame.copy()
    data["date"] = pd.to_datetime(data.get("date"), errors="coerce").dt.normalize()
    data = data.dropna(subset=["date"]).sort_values("date", kind="stable").drop_duplicates("date", keep="last").reset_index(drop=True)
    signal_by_date = dict(zip(data["date"], mkf_green_exit_mask(data), strict=True))
    panel = build_stock_panel(code, data, config, start_date="2021-01-01")
    panel["mkf_green_exit"] = panel["date"].map(signal_by_date).fillna(False).astype(bool)
    return panel


def _summary(rows: pd.DataFrame) -> dict[str, Any]:
    mature = rows.loc[rows["label"].notna()]
    result = summarize_counts(len(mature), int(mature["label"].astype(bool).sum()))
    result["signal_dates"] = int(mature["date"].nunique())
    return result


def aggregate_mkf_metrics(panel: pd.DataFrame) -> tuple[dict[str, Any], dict[str, Any]]:
    """Compare strict exits against admitted stocks on identical signal dates."""

    signal = panel["admitted"].fillna(False) & panel["mkf_green_exit"].fillna(False)
    signal_dates = set(panel.loc[signal, "date"])
    baseline = panel["admitted"].fillna(False) & panel["date"].isin(signal_dates)
    summaries: dict[str, Any] = {}
    for name, mask in {"same_date_admitted_baseline": baseline, "mkf_green_exit": signal}.items():
        rows = panel.loc[mask]
        summaries[name] = {
            period: _summary(rows.loc[rows["date"].dt.year.between(first, last)])
            for period, (first, last) in PERIODS.items()
        }
        for year in range(2023, 2027):
            summaries[name][f"year_{year}"] = _summary(rows.loc[rows["date"].dt.year.eq(year)])

    sensitivity: dict[str, Any] = {}
    for name, mask in {"same_date_admitted_baseline": baseline, "mkf_green_exit": signal}.items():
        spaced = nonoverlapping_origins(panel.loc[mask])
        sensitivity[name] = {
            period: _summary(spaced.loc[spaced["date"].dt.year.between(first, last)])
            for period, (first, last) in PERIODS.items()
        }
    return summaries, sensitivity


def evaluate_mkf_decision(summaries: Mapping[str, Any], sensitivity: Mapping[str, Any]) -> dict[str, Any]:
    """Apply the frozen stable-effect gates to both periods."""

    failures: dict[str, list[str]] = {}
    comparisons: dict[str, Any] = {}
    for period, years in (("selection_2023_2024", (2023, 2024)), ("holdout_2025_2026", (2025, 2026))):
        candidate = summaries["mkf_green_exit"][period]
        baseline = summaries["same_date_admitted_baseline"][period]
        candidate_precision = candidate["precision"]
        baseline_precision = baseline["precision"]
        lift = None if candidate_precision is None or baseline_precision is None else candidate_precision - baseline_precision
        nonoverlap_candidate = sensitivity["mkf_green_exit"][period]
        nonoverlap_baseline = sensitivity["same_date_admitted_baseline"][period]
        nonoverlap_lift = (
            None if nonoverlap_candidate["precision"] is None or nonoverlap_baseline["precision"] is None
            else nonoverlap_candidate["precision"] - nonoverlap_baseline["precision"]
        )
        codes: list[str] = []
        if int(candidate["n"]) < 300:
            codes.append("n_below_300")
        for year in years:
            minimum = 25 if year == 2026 else 50
            if int(summaries["mkf_green_exit"][f"year_{year}"]["n"]) < minimum:
                codes.append(f"year_{year}_n_below_{minimum}")
        if lift is None or lift < 0.03:
            codes.append("precision_lift_below_0.03")
        if candidate["wilson_lower_95"] is None or baseline_precision is None or candidate["wilson_lower_95"] <= baseline_precision:
            codes.append("wilson_lower_not_above_baseline")
        if nonoverlap_lift is None or nonoverlap_lift <= 0:
            codes.append("nonoverlap_lift_not_positive")
        failures[period] = codes
        comparisons[period] = {
            "precision_lift": lift,
            "nonoverlap_precision_lift": nonoverlap_lift,
            "reaches_70pct": bool(candidate_precision is not None and candidate_precision >= 0.70),
        }
    return {
        "comparisons": comparisons,
        "failure_codes": failures,
        "historically_effective": not any(failures.values()),
    }
