"""A-class T-open target-touch and path-quality validation."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np
import pandas as pd

from .research_precision70 import production_gate_mask
from .research_target_touch import MIN_BASELINE_ROWS, stock_target_outcomes
from .research_v2 import summarize_counts

SCHEMA_VERSION = "ncn_a_class_t_open_target_touch_v1"


def _path_outcomes(data: pd.DataFrame) -> dict[pd.Timestamp, dict[str, Any]]:
    trade = data.get("tradestatus", pd.Series(index=data.index, dtype=object)).astype("string")
    indices = np.flatnonzero(trade.eq("1").fillna(False).to_numpy())
    dates = pd.to_datetime(data["date"], errors="coerce").to_numpy()
    opens = pd.to_numeric(data.get("open"), errors="coerce").to_numpy(dtype=float)
    highs = pd.to_numeric(data.get("high"), errors="coerce").to_numpy(dtype=float)
    lows = pd.to_numeric(data.get("low"), errors="coerce").to_numpy(dtype=float)
    positions = {int(index): position for position, index in enumerate(indices)}
    rows: dict[pd.Timestamp, dict[str, Any]] = {}
    for origin in range(len(data)):
        origin_date = pd.Timestamp(dates[origin])
        position = positions.get(origin)
        row: dict[str, Any] = {"risk_first_3pct": pd.NA, "max_drawdown": np.nan, "max_excursion": np.nan}
        if position is None or position + 1 >= len(indices):
            rows[origin_date] = row
            continue
        entry = int(indices[position + 1])
        entry_open = opens[entry]
        eligible = indices[position + 2:position + 7]
        if len(eligible) < 5 or not np.isfinite(entry_open) or entry_open <= 0:
            rows[origin_date] = row
            continue
        window_highs = highs[eligible]
        window_lows = lows[eligible]
        if not np.isfinite(window_highs).all() or not np.isfinite(window_lows).all():
            rows[origin_date] = row
            continue
        target_touches = window_highs >= entry_open * 1.03
        risk_touches = window_lows <= entry_open * 0.97
        target_first = int(np.argmax(target_touches)) if bool(target_touches.any()) else None
        risk_first = int(np.argmax(risk_touches)) if bool(risk_touches.any()) else None
        row.update({
            "risk_first_3pct": bool(risk_first is not None and (target_first is None or risk_first < target_first)),
            "max_drawdown": float(window_lows.min() / entry_open - 1.0),
            "max_excursion": float(window_highs.max() / entry_open - 1.0),
        })
        rows[origin_date] = row
    return rows


def a_class_signal_mask(frame: pd.DataFrame, config: Mapping[str, Any], code: str) -> pd.Series:
    admitted = production_gate_mask(code, frame, config)
    trade = frame.get("tradestatus", pd.Series(index=frame.index, dtype=object)).astype("string").eq("1").fillna(False)
    trading = frame.loc[trade].copy()
    result = pd.Series(False, index=frame.index, dtype=bool)
    if trading.empty:
        return result

    close = pd.to_numeric(trading["close"], errors="coerce")
    high = pd.to_numeric(trading["high"], errors="coerce")
    low = pd.to_numeric(trading["low"], errors="coerce")
    open_ = pd.to_numeric(trading["open"], errors="coerce")
    volume = pd.to_numeric(trading["volume"], errors="coerce")
    range20_low = low.rolling(20, min_periods=1).min()
    range20_high = high.rolling(20, min_periods=1).max()
    range60_low = low.rolling(60, min_periods=1).min()
    range60_high = high.rolling(60, min_periods=1).max()
    range120_low = low.rolling(120, min_periods=1).min()
    range120_high = high.rolling(120, min_periods=1).max()
    range20 = close.sub(range20_low).div(range20_high.sub(range20_low).where(range20_high.gt(range20_low))).mul(100.0)
    range60 = close.sub(range60_low).div(range60_high.sub(range60_low).where(range60_high.gt(range60_low))).mul(100.0)
    range120 = close.sub(range120_low).div(range120_high.sub(range120_low).where(range120_high.gt(range120_low))).mul(100.0)
    prior_return20 = close.shift(1).div(close.shift(21)).sub(1.0).mul(100.0)
    prior_high20 = high.shift(1).rolling(20, min_periods=1).max()
    breakout = close.gt(prior_high20.mul(1.003))
    volume_ratio20 = volume.div(volume.rolling(20, min_periods=1).mean().where(volume.rolling(20, min_periods=1).mean().gt(0)))
    day_range = high.sub(low)
    close_location = close.sub(low).div(day_range.where(day_range.gt(0)))
    upper_shadow = high.sub(pd.concat((open_, close), axis=1).max(axis=1))
    upper_shadow_pct = upper_shadow.div(day_range.where(day_range.gt(0)))
    mask = (
        admitted.loc[trading.index]
        & range60.le(55.0).fillna(False)
        & range120.le(65.0).fillna(False)
        & range20.le(75.0).fillna(False)
        & prior_return20.le(15.0).fillna(False)
        & breakout.fillna(False)
        & volume_ratio20.between(1.05, 2.80).fillna(False)
        & close_location.ge(0.55).fillna(False)
        & upper_shadow_pct.le(0.40).fillna(False)
    )
    result.loc[trading.index] = mask.astype(bool)
    return result


def build_a_class_target_touch_panel(
    code: str,
    frame: pd.DataFrame,
    config: Mapping[str, Any],
    *,
    start_date: str = "2021-01-01",
    end_date: str | None = None,
) -> pd.DataFrame:
    data = frame.copy()
    data["date"] = pd.to_datetime(data.get("date"), errors="coerce").dt.normalize()
    data = data.dropna(subset=["date"]).sort_values("date", kind="stable").drop_duplicates("date", keep="last").reset_index(drop=True)
    selected = data["date"].ge(pd.Timestamp(start_date))
    if end_date is not None:
        selected &= data["date"].le(pd.Timestamp(end_date))
    panel = pd.DataFrame({
        "code": code,
        "signal_date": data["date"],
        "admitted": production_gate_mask(code, data, config),
        "selected": a_class_signal_mask(data, config, code),
    }).loc[selected].reset_index(drop=True)
    target_rows = panel["signal_date"].map(stock_target_outcomes(data))
    path_rows = panel["signal_date"].map(_path_outcomes(data))
    panel["entry_date"] = pd.to_datetime(target_rows.map(lambda value: value.get("entry_date", pd.NaT)))
    panel["status"] = target_rows.map(lambda value: value.get("status", "missing"))
    for field in ("entry_open", "target_price", "max_high", "first_touch_day"):
        panel[field] = pd.to_numeric(target_rows.map(lambda value, key=field: value.get(key, np.nan)), errors="coerce")
    panel["target_touched"] = pd.array(target_rows.map(lambda value: value.get("target_touched", pd.NA)), dtype="boolean")
    panel["risk_first_3pct"] = pd.array(path_rows.map(lambda value: value.get("risk_first_3pct", pd.NA)), dtype="boolean")
    panel["max_drawdown"] = pd.to_numeric(path_rows.map(lambda value: value.get("max_drawdown", np.nan)), errors="coerce")
    panel["max_excursion"] = pd.to_numeric(path_rows.map(lambda value: value.get("max_excursion", np.nan)), errors="coerce")
    return panel


def _summary(rows: pd.DataFrame, baseline: pd.DataFrame) -> dict[str, Any]:
    mature = rows.loc[rows["status"].eq("mature") & rows["target_touched"].notna()]
    result = summarize_counts(len(mature), int(mature["target_touched"].astype(bool).sum()))
    result["losses"] = int(result["n"] - result["hits"])
    result["signal_dates"] = int(mature["signal_date"].nunique())
    result["entry_dates"] = int(mature["entry_date"].nunique())
    result["codes"] = int(mature["code"].nunique())
    counts = mature.groupby("entry_date").size()
    matched = baseline.loc[baseline["entry_date"].isin(counts.index)]
    by_date = matched.groupby("entry_date")["target_touched"].agg(["count", "sum"])
    weights = counts.reindex(by_date.index).astype(float)
    weighted_n = int(weights.sum())
    weighted_hits = float((weights * by_date["sum"].div(by_date["count"])).sum()) if weighted_n else 0.0
    baseline_rate = weighted_hits / weighted_n if weighted_n else None
    result["same_entry_date_baseline"] = {
        "admitted_n": int(by_date["count"].sum()) if len(by_date) else 0,
        "weighted_n": weighted_n,
        "weighted_hits": weighted_hits,
        "win_rate": baseline_rate,
    }
    result["win_rate"] = result.pop("precision")
    result["win_rate_lift"] = None if result["win_rate"] is None or baseline_rate is None else result["win_rate"] - baseline_rate
    if len(mature):
        result["risk_first_3pct_rate"] = float(mature["risk_first_3pct"].fillna(False).astype(bool).mean())
        result["median_max_drawdown"] = float(mature["max_drawdown"].median())
        result["median_max_excursion"] = float(mature["max_excursion"].median())
    else:
        result["risk_first_3pct_rate"] = None
        result["median_max_drawdown"] = None
        result["median_max_excursion"] = None
    return result


def aggregate_a_class_target_touch(panel: pd.DataFrame) -> dict[str, Any]:
    mature_admitted = panel.loc[panel["admitted"].fillna(False) & panel["status"].eq("mature") & panel["target_touched"].notna()].copy()
    day_counts = mature_admitted.groupby("entry_date").size()
    valid_dates = set(day_counts[day_counts.ge(MIN_BASELINE_ROWS)].index)
    baseline = mature_admitted.loc[mature_admitted["entry_date"].isin(valid_dates)]
    all_candidates = panel.loc[panel["selected"].fillna(False) & panel["admitted"].fillna(False)]
    candidates = all_candidates.loc[all_candidates["entry_date"].isin(valid_dates)]
    mature_candidates = candidates.loc[candidates["status"].eq("mature")]
    years = sorted(int(year) for year in mature_candidates["entry_date"].dropna().dt.year.unique())
    if years:
        periods = {
            "full_2021_present": (2021, max(years)),
            "selection_2021_2023": (2021, 2023),
            "audit_2024_present": (2024, max(years)),
            **{f"year_{year}": (year, year) for year in years},
        }
    else:
        periods = {"full_2021_present": (2021, 2021), "selection_2021_2023": (2021, 2023), "audit_2024_present": (2024, 2024)}
    metrics = {
        name: _summary(
            mature_candidates.loc[mature_candidates["entry_date"].dt.year.between(first, last)],
            baseline.loc[baseline["entry_date"].dt.year.between(first, last)],
        )
        for name, (first, last) in periods.items()
    }
    return {
        "periods": periods,
        "metrics": metrics,
        "candidate_status_counts": {str(key): int(value) for key, value in all_candidates["status"].value_counts(dropna=False).sort_index().items()},
        "mature_candidates_on_valid_baseline_dates": int(len(mature_candidates)),
        "excluded_mature_candidates_on_thin_baseline_dates": int(
            (all_candidates["status"].eq("mature") & ~all_candidates["entry_date"].isin(valid_dates)).sum()
        ),
    }


def build_a_class_target_touch_report(
    *,
    panel: pd.DataFrame,
    code_list: list[str],
    code_list_sha256: str,
    start_date: str,
    end_date: str | None,
    workers: int,
) -> dict[str, Any]:
    aggregated = aggregate_a_class_target_touch(panel)
    return {
        "schema_version": SCHEMA_VERSION,
        "study": "a_class_t_open_plus3_t_plus_1_through_t_plus_5_path_quality",
        "research_only": True,
        "classification_only": True,
        "production_enabled": False,
        "alignment": {
            "signal": "A-class base-breakout signal using origin-date-visible rows only",
            "entry_reference": "next stock-tradable T open",
            "target": "T open * 1.03",
            "eligible_window": "T+1 through T+5 stock-tradable rows; T high excluded",
            "risk_path": "risk_first_3pct checks whether -3% low is touched before +3% target in the eligible window",
        },
        "sample": {"method": "all_current_main_board_sorted_code", "codes": len(code_list), "code_list": code_list, "code_list_sha256": code_list_sha256},
        "date_range": {"start_date": start_date, "end_date": end_date},
        "workers": workers,
        **aggregated,
        "limitations": [
            "Target touch is not proof that a queued limit sell filled.",
            "T open is a reference observation, not proof of a buy fill.",
            "No fees, tax, slippage, T+5 fallback exit, return, or P&L is modeled.",
            "Adjusted current-vintage bars and current-file survivorship remain limitations.",
        ],
    }
