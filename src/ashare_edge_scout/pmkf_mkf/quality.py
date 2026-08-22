from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np
import pandas as pd

from ..discovery import _kalman_prices
from ..research_barrier_quality import first_touch_state
from .research import mkf_red_blue_cross20_under80_mask
from ..research_precision70 import five_close_label, production_gate_mask
from ..research_v2 import summarize_counts

SCHEMA_VERSION = "ncn_pmkf_mkf_t5_quality_comparison_v1"
CANDIDATES = ("A_mkf_red_blue", "B_pmkf_backbone", "C_pmkf_plus_mkf_timing")
PMKF_MIN_BASE_SCORE = 75.0
TARGET_RETURN = 0.03
RISK_RETURN = -0.03
HORIZON_TRADING_DAYS = 5
PATH_STATES = ("target_first", "risk_first", "same_day_ambiguous", "neither")


def normalise_stock_frame(frame: pd.DataFrame) -> pd.DataFrame:
    data = frame.copy()
    data["date"] = pd.to_datetime(data.get("date"), errors="coerce").dt.normalize()
    return data.dropna(subset=["date"]).sort_values("date", kind="stable").drop_duplicates("date", keep="last").reset_index(drop=True)


def _numeric(frame: pd.DataFrame, name: str) -> pd.Series:
    values = pd.to_numeric(frame.get(name), errors="coerce") if name in frame else pd.Series(np.nan, index=frame.index)
    return values.where(np.isfinite(values))


def pmkf_base_score_series(frame: pd.DataFrame) -> pd.Series:
    close = _numeric(frame, "close")
    low = _numeric(frame, "low")
    volume = _numeric(frame, "volume")
    scores = pd.Series(0.0, index=frame.index, dtype=float)
    if len(frame) < 60 or close.isna().any() or low.isna().any() or volume.isna().any():
        return scores

    close_values = close.to_numpy(dtype=float)
    low_values = low.to_numpy(dtype=float)
    volume_values = volume.to_numpy(dtype=float)
    smoothed = _kalman_prices(close_values)
    rolling_std = close.rolling(20).std()

    for index in range(59, len(frame)):
        if smoothed[index - 19] == 0:
            continue
        momentum = (smoothed[index] / (smoothed[index - 19] + 1e-12) - 1.0) * 100.0
        if momentum < 0:
            continue
        std_20 = rolling_std.iat[index]
        if not np.isfinite(std_20):
            continue
        lower_bound = float(np.mean(smoothed[index - 19:index + 1]) - 1.5 * std_20)
        pit_hit = float(np.min(low_values[index - 2:index + 1])) < lower_bound
        volume_ratio = float(volume_values[index] / (np.mean(volume_values[index - 4:index + 1]) + 1e-6))
        penalty = 0.0
        if not pit_hit:
            penalty += 10.0
        if momentum < 5.0:
            penalty += min((5.0 - momentum) * 2.0, 20.0)
        elif momentum > 80.0:
            penalty += min((momentum - 80.0) * 3.0, 30.0)
        if volume_ratio < 1.0:
            penalty += min((1.0 - volume_ratio) * 10.0, 15.0)
        volume_penalty = volume_ratio * 12.0 if volume_ratio > 3.0 else 0.0
        score = 40.0 + min(momentum, 50.0) + 20.0 - volume_penalty - penalty
        ret_5d = (close_values[index] / close_values[index - 5] - 1.0) * 100.0
        if ret_5d < -5.0:
            score -= min((abs(ret_5d) - 5.0) * 2.0, 15.0)
        scores.iat[index] = round(float(score), 6)
    return scores


def candidate_masks(frame: pd.DataFrame, config: Mapping[str, Any], code: str) -> dict[str, pd.Series]:
    admitted = production_gate_mask(code, frame, config)
    mkf = mkf_red_blue_cross20_under80_mask(frame).reindex(frame.index, fill_value=False).astype(bool)
    pmkf_score = pmkf_base_score_series(frame)
    pmkf = pmkf_score.ge(PMKF_MIN_BASE_SCORE).fillna(False)
    return {
        "admitted": admitted.astype(bool),
        "mkf_red_blue_signal": mkf,
        "cnstock_base_score": pmkf_score,
        "A_mkf_red_blue": admitted & mkf,
        "B_pmkf_backbone": admitted & pmkf,
        "C_pmkf_plus_mkf_timing": admitted & pmkf & mkf,
    }


def t5_close_and_path_outcomes(frame: pd.DataFrame) -> dict[pd.Timestamp, dict[str, Any]]:
    trade = frame.get("tradestatus", pd.Series(index=frame.index, dtype=object)).astype("string")
    tradable = list(np.flatnonzero(trade.eq("1").fillna(False).to_numpy()))
    positions = {index: position for position, index in enumerate(tradable)}
    dates = pd.to_datetime(frame["date"], errors="coerce").to_numpy()
    close = _numeric(frame, "close").to_numpy(dtype=float)
    high = _numeric(frame, "high").to_numpy(dtype=float)
    low = _numeric(frame, "low").to_numpy(dtype=float)
    outcomes: dict[pd.Timestamp, dict[str, Any]] = {}
    for origin in range(len(frame)):
        origin_date = pd.Timestamp(dates[origin])
        row: dict[str, Any] = {"status": "origin_invalid", "maturity_date": pd.NaT}
        position = positions.get(origin)
        reference = close[origin]
        if position is None or not np.isfinite(reference) or reference <= 0:
            outcomes[origin_date] = row
            continue
        future = tradable[position + 1:position + 1 + HORIZON_TRADING_DAYS]
        if len(future) < HORIZON_TRADING_DAYS:
            row["status"] = "partial"
            outcomes[origin_date] = row
            continue
        future_close = close[future]
        future_high = high[future]
        future_low = low[future]
        if not (np.isfinite(future_close).all() and np.isfinite(future_high).all() and np.isfinite(future_low).all()):
            row["status"] = "invalid"
            outcomes[origin_date] = row
            continue
        label = five_close_label(float(reference), future_close.tolist())
        row.update({
            "status": "mature",
            "maturity_date": pd.Timestamp(dates[future[-1]]),
            "label": bool(label),
            "ret_5d_close": float(future_close[-1] / reference - 1.0),
            "max_future_close_return": float(future_close.max() / reference - 1.0),
            "min_future_close_return": float(future_close.min() / reference - 1.0),
            "max_excursion": float(future_high.max() / reference - 1.0),
            "max_drawdown": float(future_low.min() / reference - 1.0),
            "target3_touched": bool(future_high.max() >= reference * (1.0 + TARGET_RETURN)),
            "risk3_touched": bool(future_low.min() <= reference * (1.0 + RISK_RETURN)),
            "target3_risk3_first_state": first_touch_state(
                future_high.tolist(), future_low.tolist(), float(reference), TARGET_RETURN, abs(RISK_RETURN)
            ),
        })
        outcomes[origin_date] = row
    return outcomes


def build_comparison_panel(
    code: str,
    frame: pd.DataFrame,
    config: Mapping[str, Any],
    *,
    start_date: str = "2021-01-01",
    end_date: str | None = None,
) -> pd.DataFrame:
    data = normalise_stock_frame(frame)
    masks = candidate_masks(data, config, code)
    selected = data["date"].ge(pd.Timestamp(start_date))
    if end_date is not None:
        selected &= data["date"].le(pd.Timestamp(end_date))
    outcomes = t5_close_and_path_outcomes(data)
    rows = data["date"].map(outcomes)
    panel = pd.DataFrame({
        "code": code,
        "date": data["date"],
        "admitted": masks["admitted"],
        "mkf_red_blue_signal": masks["mkf_red_blue_signal"],
        "cnstock_base_score": masks["cnstock_base_score"],
        **{candidate: masks[candidate] for candidate in CANDIDATES},
        "close": _numeric(data, "close"),
        "status": rows.map(lambda value: value.get("status", "missing")),
        "maturity_date": pd.to_datetime(rows.map(lambda value: value.get("maturity_date", pd.NaT))),
        "label": pd.array(rows.map(lambda value: value.get("label", pd.NA)), dtype="boolean"),
        "ret_5d_close": pd.to_numeric(rows.map(lambda value: value.get("ret_5d_close", np.nan)), errors="coerce"),
        "max_future_close_return": pd.to_numeric(rows.map(lambda value: value.get("max_future_close_return", np.nan)), errors="coerce"),
        "min_future_close_return": pd.to_numeric(rows.map(lambda value: value.get("min_future_close_return", np.nan)), errors="coerce"),
        "max_excursion": pd.to_numeric(rows.map(lambda value: value.get("max_excursion", np.nan)), errors="coerce"),
        "max_drawdown": pd.to_numeric(rows.map(lambda value: value.get("max_drawdown", np.nan)), errors="coerce"),
        "target3_touched": pd.array(rows.map(lambda value: value.get("target3_touched", pd.NA)), dtype="boolean"),
        "risk3_touched": pd.array(rows.map(lambda value: value.get("risk3_touched", pd.NA)), dtype="boolean"),
        "target3_risk3_first_state": rows.map(lambda value: value.get("target3_risk3_first_state", pd.NA)),
    })
    return panel.loc[selected].reset_index(drop=True)


def _periods(panel: pd.DataFrame) -> dict[str, tuple[int, int]]:
    years = sorted(int(year) for year in panel["date"].dropna().dt.year.unique())
    if not years:
        return {}
    periods = {"full_requested_range": (years[0], years[-1])}
    periods.update({f"year_{year}": (year, year) for year in years})
    if years[0] <= 2021 and years[-1] >= 2023:
        periods["selection_2021_2023"] = (2021, 2023)
    if years[-1] >= 2024:
        periods["audit_2024_present"] = (2024, years[-1])
    return periods


def _quantiles(rows: pd.DataFrame, column: str) -> dict[str, float | None]:
    values = pd.to_numeric(rows[column], errors="coerce").dropna()
    return {str(q): (float(values.quantile(q)) if len(values) else None) for q in (0.1, 0.25, 0.5, 0.75, 0.9)}


def _rate(rows: pd.DataFrame, column: str) -> float | None:
    values = rows[column].dropna()
    return float(values.mean()) if len(values) else None


def _candidate_period_metrics(rows: pd.DataFrame) -> dict[str, Any]:
    mature = rows.loc[rows["status"].eq("mature")].copy()
    labels = mature["label"].fillna(False).astype(bool)
    counts = summarize_counts(len(mature), int(labels.sum()))
    states = {state: int(mature["target3_risk3_first_state"].eq(state).sum()) for state in PATH_STATES}
    result: dict[str, Any] = {
        "n": counts["n"],
        "wins": counts["hits"],
        "win_rate": counts["precision"],
        "wilson_lower_95": counts["wilson_lower_95"],
        "wilson_upper_95": counts["wilson_upper_95"],
        "signal_dates": int(mature["date"].nunique()),
        "codes": int(mature["code"].nunique()),
        "mean_ret_5d_close": float(mature["ret_5d_close"].mean()) if len(mature) else None,
        "median_ret_5d_close": float(mature["ret_5d_close"].median()) if len(mature) else None,
        "max_drawdown_quantiles": _quantiles(mature, "max_drawdown"),
        "max_excursion_quantiles": _quantiles(mature, "max_excursion"),
        "target3_touched_rate": _rate(mature, "target3_touched"),
        "risk3_touched_rate": _rate(mature, "risk3_touched"),
        "path_states": states,
    }
    for state in PATH_STATES:
        result[f"{state}_rate"] = states[state] / len(mature) if len(mature) else None
    return result


def _add_comparisons(period_metrics: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    for candidate, metrics in period_metrics.items():
        for baseline in ("A_mkf_red_blue", "B_pmkf_backbone"):
            base = period_metrics.get(baseline, {})
            suffix = baseline.split("_", 1)[0]
            win_rate = metrics.get("win_rate")
            base_win = base.get("win_rate")
            risk_rate = metrics.get("risk_first_rate")
            base_risk = base.get("risk_first_rate")
            drawdown = metrics.get("max_drawdown_quantiles", {}).get("0.5")
            base_drawdown = base.get("max_drawdown_quantiles", {}).get("0.5")
            metrics[f"lift_vs_{suffix}_win_rate"] = None if win_rate is None or base_win is None else win_rate - base_win
            metrics[f"risk_first_delta_vs_{suffix}"] = None if risk_rate is None or base_risk is None else risk_rate - base_risk
            metrics[f"median_drawdown_delta_vs_{suffix}"] = None if drawdown is None or base_drawdown is None else drawdown - base_drawdown
    return period_metrics


def _overlap_matrix(panel: pd.DataFrame) -> dict[str, dict[str, int]]:
    return {
        left: {
            right: int((panel[left].fillna(False) & panel[right].fillna(False)).sum())
            for right in CANDIDATES
        }
        for left in CANDIDATES
    }


def aggregate_comparison_metrics(panel: pd.DataFrame) -> dict[str, Any]:
    periods = _periods(panel)
    metrics: dict[str, dict[str, Any]] = {}
    for name, (first, last) in periods.items():
        period_rows = panel.loc[panel["date"].dt.year.between(first, last)]
        period_metrics = {
            candidate: _candidate_period_metrics(period_rows.loc[period_rows[candidate].fillna(False)])
            for candidate in CANDIDATES
        }
        metrics[name] = _add_comparisons(period_metrics)
    any_candidate = panel.loc[pd.concat([panel[candidate].fillna(False) for candidate in CANDIDATES], axis=1).any(axis=1)]
    return {
        "periods": periods,
        "metrics": metrics,
        "status_counts": {str(key): int(value) for key, value in any_candidate["status"].value_counts(dropna=False).sort_index().items()},
        "overlap_matrix": _overlap_matrix(panel),
    }


def build_comparison_report(
    *,
    panel: pd.DataFrame,
    code_list: list[str],
    code_list_sha256: str,
    start_date: str,
    end_date: str | None,
    workers: int,
) -> dict[str, Any]:
    aggregated = aggregate_comparison_metrics(panel)
    observed_start = panel["date"].min()
    observed_end = panel["date"].max()
    return {
        "schema_version": SCHEMA_VERSION,
        "study": "pmkf_mkf_t5_candidate_quality_comparison",
        "research_only": True,
        "classification_only": True,
        "production_enabled": False,
        "watchlist_modified": False,
        "smc_admission_modified": False,
        "broker_orders_enabled": False,
        "pnl_modeled": False,
        "futu_signals_ignored": True,
        "candidate_definitions": {
            "A_mkf_red_blue": {"definition": "production_gate_mask AND mkf_red_blue_cross20_under80_mask"},
            "B_pmkf_backbone": {"definition": "production_gate_mask AND cnstock_base_score >= 75.0", "futu_bonus": 0.0},
            "C_pmkf_plus_mkf_timing": {"definition": "B_pmkf_backbone AND mkf_red_blue_cross20_under80_mask"},
        },
        "thresholds": {
            "pmkf_min_base_score": PMKF_MIN_BASE_SCORE,
            "target_return": TARGET_RETURN,
            "risk_return": RISK_RETURN,
            "horizon_trading_days": HORIZON_TRADING_DAYS,
        },
        "label": {
            "anchor": "signal_date_T_close",
            "future_window": "next_5_stock_tradable_closes",
            "win": "max_close >= +3% and min_close >= -3%",
        },
        "path_risk": {
            "anchor": "signal_date_T_close",
            "future_window": "next_5_stock_tradable_high_low_rows",
            "same_day_dual_touch": "same_day_ambiguous; no favorable ordering assumed",
        },
        "sample": {"method": "all_current_main_board_sorted_code", "codes": len(code_list), "code_list": code_list, "code_list_sha256": code_list_sha256},
        "date_range": {
            "start_date": start_date,
            "end_date": end_date,
            "observed_start": observed_start.strftime("%Y-%m-%d") if pd.notna(observed_start) else None,
            "observed_end": observed_end.strftime("%Y-%m-%d") if pd.notna(observed_end) else None,
        },
        "workers": workers,
        **aggregated,
        "limitations": [
            "Adjusted current-vintage local bars and current-file survivorship remain limitations.",
            "This is classification research only, not execution, orders, positions, or P&L.",
            "Daily OHLC cannot resolve intraday ordering when target and risk are touched on the same day.",
            "PMKF threshold is frozen before running and must not be tuned after seeing results.",
        ],
    }
