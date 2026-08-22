"""Unified causal ranking primitives for the frozen ``futu.md`` families."""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

import numpy as np
import pandas as pd

from .pmkf_mkf.research import mkf_lines
from .research_precision70 import build_stock_panel, nonoverlapping_origins
from .research_v2 import summarize_counts


CANDIDATES = (
    "dxbd_cross_zero",
    "ribbon1_strict_buy",
    "mhpg_buy",
    "kdj_trend_pro_buy",
    "smc_strong_buy",
    "mkf_green_exit_proxy",
    "shengbei_long_flip",
    "gding_bbuy",
    "cpgw_main_long_cross",
)
PERIODS = {
    "calibration_2021_2022": (2021, 2022),
    "selection_2023_2024": (2023, 2024),
    "audit_2025_2026": (2025, 2026),
}
YEARS = tuple(range(2021, 2027))


def _numeric(frame: pd.DataFrame, name: str) -> pd.Series:
    values = pd.to_numeric(frame.get(name, pd.Series(np.nan, index=frame.index)), errors="coerce")
    return values.where(np.isfinite(values))


def _ema(values: pd.Series, span: int) -> pd.Series:
    return values.ewm(span=span, adjust=False, min_periods=1).mean()


def _tdx_sma(values: pd.Series, n: int, m: int = 1) -> pd.Series:
    result = np.full(len(values), np.nan, dtype=float)
    previous = np.nan
    for index, value in enumerate(values.to_numpy(dtype=float)):
        if not math.isfinite(value):
            continue
        previous = value if not math.isfinite(previous) else (m * value + (n - m) * previous) / n
        result[index] = previous
    return pd.Series(result, index=values.index)


def _range_position(close: pd.Series, high: pd.Series, low: pd.Series, window: int) -> pd.Series:
    minimum = low.rolling(window, min_periods=window).min()
    maximum = high.rolling(window, min_periods=window).max()
    denominator = maximum - minimum
    return close.sub(minimum).div(denominator.where(denominator.gt(0))).mul(100.0)


def _cross(left: pd.Series, right: pd.Series | float) -> pd.Series:
    other = right if isinstance(right, pd.Series) else pd.Series(float(right), index=left.index)
    return left.shift(1).le(other.shift(1)) & left.gt(other)


def _shengbei_state(close: pd.Series, high: pd.Series, low: pd.Series) -> pd.Series:
    """Return deterministic 22-day, 3-ATR trailing-wave direction.

    The first row with both stops available starts short. Neutral rows carry the
    prior direction, matching FLAG1 in the source formula.
    """

    previous_close = close.shift(1)
    true_range = pd.concat(
        (high - low, high.sub(previous_close).abs(), low.sub(previous_close).abs()), axis=1
    ).max(axis=1, skipna=True).where(high.notna() & low.notna())
    atr = _tdx_sma(true_range, 22)
    raw_long = close.rolling(22, min_periods=22).max() - 3.0 * atr
    raw_short = close.rolling(22, min_periods=22).min() + 3.0 * atr
    long_stop = np.full(len(close), np.nan, dtype=float)
    short_stop = np.full(len(close), np.nan, dtype=float)
    state = np.full(len(close), np.nan, dtype=float)
    for index in range(len(close)):
        long_value = float(raw_long.iat[index])
        short_value = float(raw_short.iat[index])
        if not (math.isfinite(long_value) and math.isfinite(short_value)):
            continue
        if index and math.isfinite(long_stop[index - 1]) and previous_close.iat[index] > long_stop[index - 1]:
            long_value = max(long_value, long_stop[index - 1])
        if index and math.isfinite(short_stop[index - 1]) and previous_close.iat[index] < short_stop[index - 1]:
            short_value = min(short_value, short_stop[index - 1])
        long_stop[index] = long_value
        short_stop[index] = short_value
        if not index or not math.isfinite(state[index - 1]):
            state[index] = -1.0
        elif close.iat[index] > short_stop[index - 1]:
            state[index] = 1.0
        elif close.iat[index] < long_stop[index - 1]:
            state[index] = -1.0
        else:
            state[index] = state[index - 1]
    return pd.Series(state, index=close.index)


def tradable_indicator_values(frame: pd.DataFrame) -> pd.DataFrame:
    """Compute all frozen formula values on stock-tradable rows only."""

    trade = frame.get("tradestatus", pd.Series(index=frame.index, dtype=object)).astype("string")
    trading = frame.loc[trade.eq("1").fillna(False)].copy()
    close, open_, high, low = (_numeric(trading, name) for name in ("close", "open", "high", "low"))
    volume = _numeric(trading, "volume")
    values = pd.DataFrame(index=trading.index)
    values["close"] = close
    values["high"] = high
    values["low"] = low

    values["dxbd"] = (_ema(_range_position(close, high, low, 8), 3) - 50.0) * 2.0
    ribbon = _tdx_sma(_tdx_sma(_range_position(close, high, low, 60).abs(), 3), 5)
    values["ribbon"] = ribbon
    values["ribbon_signal"] = _tdx_sma(ribbon, 8)

    values["ema20"] = _ema(close, 20)
    values["ema50"] = _ema(close, 50)
    values["ema60"] = _ema(close, 60)
    volume_ma20 = volume.rolling(20, min_periods=20).mean()
    volume_change = volume.div(volume_ma20.where(volume_ma20.gt(0))).sub(1.0)
    daily_return = close.div(close.shift(1)).sub(1.0)
    volume_return = daily_return * (volume_change + 1.0)
    trend60 = close.div(close.rolling(60, min_periods=60).mean()).sub(1.0)
    return5 = close.div(close.shift(5)).sub(1.0)
    div_condition = volume_change.div(volume_return.where(volume_return.abs().gt(0.000001))).fillna(0.0)
    gate_result = trend60.where(div_condition.gt(0.0), return5)
    values["alphagpt_factor"] = (gate_result - trend60) * 100.0
    mhpg_k = _tdx_sma(_range_position(close, high, low, 30), 3)
    values["mhpg_k"] = mhpg_k
    values["mhpg_d"] = _tdx_sma(mhpg_k, 3)
    kdj_k = _tdx_sma(_range_position(close, high, low, 9), 3)
    values["kdj_k"] = kdj_k
    values["kdj_d"] = _tdx_sma(kdj_k, 3)

    values["prior_high30"] = high.rolling(30, min_periods=30).max().shift(1)
    values["prior_low30"] = low.rolling(30, min_periods=30).min().shift(1)
    values["prior_close"] = close.shift(1)
    values["body_ratio"] = close.sub(open_).div(high.sub(low).where(high.gt(low)))
    values["liquidity_high10"] = high.rolling(10, min_periods=10).max()
    values["liquidity_low10"] = low.rolling(10, min_periods=10).min()

    lines = mkf_lines(trading)
    for name in ("momentum", "inter", "near"):
        values[f"mkf_{name}"] = lines[name]
    values["shengbei_state"] = _shengbei_state(close, high, low)

    typical = (close + high + low) / 3.0
    values["gding_fast"] = _ema(typical, 6)
    values["gding_signal"] = _ema(values["gding_fast"], 5)
    cpgw_position = _range_position(close, high, low, 34)
    values["cpgw_main"] = _ema(cpgw_position, 4)
    values["cpgw_long"] = cpgw_position.rolling(19, min_periods=19).mean()
    return values


def candidate_masks_from_values(values: pd.DataFrame) -> dict[str, pd.Series]:
    """Apply exactly the nine frozen trigger definitions to formula values."""

    mkf_columns = [f"mkf_{name}" for name in ("momentum", "inter", "near")]
    masks = {
        "dxbd_cross_zero": _cross(values["dxbd"], 0.0),
        "ribbon1_strict_buy": _cross(values["ribbon"], values["ribbon_signal"]) & values["ribbon_signal"].lt(30.0),
        "mhpg_buy": (
            values["ema20"].gt(values["ema60"]) & values["ema60"].gt(values["ema60"].shift(1))
            & _cross(values["mhpg_k"], values["mhpg_d"]) & values["mhpg_k"].lt(60.0)
        ),
        "kdj_trend_pro_buy": (
            _cross(values["kdj_k"], values["kdj_d"])
            & values["close"].gt(values["ema60"]) & values["kdj_k"].lt(90.0)
        ),
        "smc_strong_buy": (
            values["close"].gt(values["prior_high30"])
            & values["prior_close"].le(values["prior_high30"])
            & values["body_ratio"].gt(0.70)
        ),
        "mkf_green_exit_proxy": values[mkf_columns].shift(1).le(20.0).all(axis=1) & values[mkf_columns].gt(20.0).all(axis=1),
        "shengbei_long_flip": values["shengbei_state"].shift(1).eq(-1.0) & values["shengbei_state"].eq(1.0),
        "gding_bbuy": _cross(values["gding_fast"], values["gding_signal"]),
        "cpgw_main_long_cross": _cross(values["cpgw_main"], values["cpgw_long"]) & values["cpgw_long"].lt(50.0),
    }
    return {name: mask.fillna(False).astype(bool) for name, mask in masks.items()}


def indicator_masks(frame: pd.DataFrame) -> dict[str, pd.Series]:
    """Map tradable-only formula triggers back to the complete stock frame."""

    values = tradable_indicator_values(frame)
    trading_masks = candidate_masks_from_values(values)
    result: dict[str, pd.Series] = {}
    for name in CANDIDATES:
        result[name] = pd.Series(False, index=frame.index, dtype=bool)
        result[name].loc[values.index] = trading_masks[name]
    return result


def build_futu_panel(code: str, frame: pd.DataFrame, config: Mapping[str, Any]) -> pd.DataFrame:
    """Attach nine causal triggers to the existing production/label panel."""

    data = frame.copy()
    data["date"] = pd.to_datetime(data.get("date"), errors="coerce").dt.normalize()
    data = data.dropna(subset=["date"]).sort_values("date", kind="stable").drop_duplicates("date", keep="last").reset_index(drop=True)
    values = tradable_indicator_values(data)
    trading_masks = candidate_masks_from_values(values)
    trading_dates = data.loc[values.index, "date"]
    by_date = {
        name: dict(zip(trading_dates, trading_masks[name], strict=True))
        for name in CANDIDATES
    }
    panel = build_stock_panel(code, data, config, start_date="2021-01-01")
    for name in CANDIDATES:
        panel[name] = panel["date"].map(by_date[name]).fillna(False).astype(bool)
    state_by_date = dict(zip(trading_dates, values["shengbei_state"], strict=True))
    panel["shengbei_state"] = panel["date"].map(state_by_date)
    return panel


def _keys() -> dict[str, tuple[int, int]]:
    return {**PERIODS, **{f"year_{year}": (year, year) for year in YEARS}}


def _matched_summary(signal_rows: pd.DataFrame, baseline: pd.DataFrame) -> dict[str, Any]:
    signal = signal_rows.loc[signal_rows["label"].notna()]
    result = summarize_counts(len(signal), int(signal["label"].astype(bool).sum()))
    result["signal_dates"] = int(signal["date"].nunique())
    result["codes"] = int(signal["code"].nunique())
    counts = signal.groupby("date").size()
    matched = baseline.loc[baseline["date"].isin(counts.index)]
    by_date = matched.groupby("date")["label"].agg(["count", "sum"])
    weights = counts.reindex(by_date.index).astype(float)
    weighted_n = float(weights.sum())
    weighted_hits = float((weights * by_date["sum"].div(by_date["count"])).sum())
    baseline_precision = weighted_hits / weighted_n if weighted_n else None
    result["same_date_baseline"] = {
        "admitted_n": int(by_date["count"].sum()),
        "admitted_hits": int(by_date["sum"].sum()),
        "weighted_n": int(weighted_n),
        "weighted_hits": weighted_hits,
        "precision": baseline_precision,
    }
    result["precision_lift"] = None if result["precision"] is None or baseline_precision is None else result["precision"] - baseline_precision
    return result


def aggregate_futu_metrics(panel: pd.DataFrame) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Produce primary non-overlap, all-origin, and trigger-coverage reports."""

    mature_admitted = panel.loc[panel["admitted"].fillna(False) & panel["label"].notna()].copy()
    mature_counts = mature_admitted.groupby("date").size()
    valid_dates = set(mature_counts[mature_counts.ge(150)].index)
    baseline = mature_admitted.loc[mature_admitted["date"].isin(valid_dates)]
    primary: dict[str, Any] = {}
    all_origin: dict[str, Any] = {}
    coverage: dict[str, Any] = {}
    for name in CANDIDATES:
        raw = panel.loc[panel[name].fillna(False)]
        usable = raw.loc[raw["admitted"].fillna(False) & raw["label"].notna() & raw["date"].isin(valid_dates)]
        spaced = nonoverlapping_origins(usable)
        primary[name] = {}
        all_origin[name] = {}
        coverage[name] = {}
        for key, (first, last) in _keys().items():
            in_period = lambda rows: rows.loc[rows["date"].dt.year.between(first, last)]
            primary[name][key] = _matched_summary(in_period(spaced), in_period(baseline))
            all_origin[name][key] = _matched_summary(in_period(usable), in_period(baseline))
            raw_period = in_period(raw)
            admitted_period = raw_period.loc[raw_period["admitted"].fillna(False)]
            usable_period = in_period(usable)
            coverage[name][key] = {
                "raw_triggers": len(raw_period),
                "admitted_triggers": len(admitted_period),
                "mature_baseline_usable": len(usable_period),
                "usable_fraction_of_raw": len(usable_period) / len(raw_period) if len(raw_period) else None,
            }
    return primary, all_origin, coverage


def _period_failures(metrics: Mapping[str, Any], all_origin: Mapping[str, Any], *, audit: bool) -> list[str]:
    period = "audit_2025_2026" if audit else "selection_2023_2024"
    years = (2025, 2026) if audit else (2023, 2024)
    aggregate = metrics[period]
    failures: list[str] = []
    if int(aggregate["n"]) < 300:
        failures.append("n_below_300")
    if not audit and int(aggregate["signal_dates"]) < 120:
        failures.append("signal_dates_below_120")
    if not audit and int(aggregate["codes"]) < 50:
        failures.append("codes_below_50")
    for year in years:
        minimum = 25 if year == 2026 else 50
        annual = metrics[f"year_{year}"]
        if int(annual["n"]) < minimum:
            failures.append(f"year_{year}_n_below_{minimum}")
        if annual["precision_lift"] is None or annual["precision_lift"] <= 0:
            failures.append(f"year_{year}_lift_not_positive")
    if aggregate["precision_lift"] is None or aggregate["precision_lift"] < 0.03:
        failures.append("aggregate_lift_below_0.03")
    baseline = aggregate["same_date_baseline"]["precision"]
    if aggregate["wilson_lower_95"] is None or baseline is None or aggregate["wilson_lower_95"] <= baseline:
        failures.append("wilson_lower_not_above_baseline")
    if all_origin[period]["precision_lift"] is None or all_origin[period]["precision_lift"] <= 0:
        failures.append("all_origin_lift_not_positive")
    return failures


def evaluate_futu_ranking(primary: Mapping[str, Any], all_origin: Mapping[str, Any]) -> dict[str, Any]:
    """Apply frozen gates and deterministic selection-lift ranking."""

    decisions: dict[str, Any] = {}
    for name in CANDIDATES:
        selection_failures = _period_failures(primary[name], all_origin[name], audit=False)
        audit_failures = _period_failures(primary[name], all_origin[name], audit=True)
        decisions[name] = {
            "selection_eligible": not selection_failures,
            "selection_failure_codes": selection_failures,
            "audit_accepted": not audit_failures,
            "audit_failure_codes": audit_failures,
        }

    def key(name: str) -> tuple[bool, float, str]:
        lift = primary[name]["selection_2023_2024"]["precision_lift"]
        return (not decisions[name]["selection_eligible"], -(lift if lift is not None else float("-inf")), name)

    ranking = sorted(CANDIDATES, key=key)
    top = ranking[0]
    accepted = top if decisions[top]["selection_eligible"] and decisions[top]["audit_accepted"] else None
    return {
        "ranking": ranking,
        "candidates": decisions,
        "top_ranked": top,
        "accepted_winner": accepted,
        "top_ranked_audit_failure_does_not_promote_next": accepted is None,
    }
