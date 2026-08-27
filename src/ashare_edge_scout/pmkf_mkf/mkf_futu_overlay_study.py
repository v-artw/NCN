from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np
import pandas as pd

from ..research_futu_ranking import candidate_masks_from_values, tradable_indicator_values
from ..research_precision70 import production_gate_mask
from ..research_v2 import summarize_counts
from .mkf_dxbd_profitability import HORIZONS
from .quality import _numeric, normalise_stock_frame
from .research import mkf_red_blue_cross20_green_exit_under80_mask

SCHEMA_VERSION = "ncn_mkf_futu_overlay_study_v1"
OVERLAYS = ("kdj_trend_pro_buy", "dxbd_cross_zero", "gding_bbuy", "mhpg_buy")
COMPLETE_YEARS = tuple(range(2021, 2026))


def _masks(code: str, data: pd.DataFrame, config: Mapping[str, Any]) -> tuple[pd.Series, dict[str, pd.Series]]:
    admitted = production_gate_mask(code, data, config).reindex(data.index, fill_value=False).astype(bool)
    mkf = mkf_red_blue_cross20_green_exit_under80_mask(data).reindex(data.index, fill_value=False).astype(bool)
    parent = admitted & mkf
    values = tradable_indicator_values(data)
    trading_masks = candidate_masks_from_values(values)
    overlays: dict[str, pd.Series] = {}
    for name in OVERLAYS:
        full = pd.Series(False, index=data.index, dtype=bool)
        full.loc[values.index] = trading_masks[name]
        overlays[name] = parent & full
    return parent, overlays


def build_overlay_panel(
    code: str,
    frame: pd.DataFrame,
    config: Mapping[str, Any],
    *,
    start_date: str = "2021-01-01",
    end_date: str | None = None,
) -> pd.DataFrame:
    data = normalise_stock_frame(frame)
    parent, overlays = _masks(code, data, config)
    trade = data.get("tradestatus", pd.Series(index=data.index, dtype=object)).astype("string")
    tradable = list(np.flatnonzero(trade.eq("1").fillna(False).to_numpy()))
    positions = {row_index: position for position, row_index in enumerate(tradable)}
    dates = pd.to_datetime(data["date"], errors="coerce")
    open_ = _numeric(data, "open").to_numpy(dtype=float)
    close = _numeric(data, "close").to_numpy(dtype=float)
    start = pd.Timestamp(start_date)
    end = pd.Timestamp(end_date) if end_date is not None else None

    rows: list[dict[str, Any]] = []
    for signal_index in data.index[parent.fillna(False)]:
        signal_date = dates.iat[signal_index]
        if signal_date < start or (end is not None and signal_date > end):
            continue
        position = positions.get(signal_index)
        if position is None or position + 1 >= len(tradable):
            continue
        entry_index = tradable[position + 1]
        entry_open = open_[entry_index]
        if not np.isfinite(entry_open) or entry_open <= 0:
            continue
        row: dict[str, Any] = {
            "code": code,
            "signal_date": signal_date,
            "entry_date": dates.iat[entry_index],
            "entry_open": float(entry_open),
            "status": "mature",
            **{name: bool(overlays[name].loc[signal_index]) for name in OVERLAYS},
        }
        future = tradable[position + 2:position + 2 + len(HORIZONS)]
        for horizon in HORIZONS:
            if len(future) < horizon:
                row[f"ret_t{horizon}_close"] = np.nan
                row[f"date_t{horizon}"] = pd.NaT
                row["status"] = "partial"
                continue
            future_index = future[horizon - 1]
            future_close = close[future_index]
            if not np.isfinite(future_close):
                row[f"ret_t{horizon}_close"] = np.nan
                row[f"date_t{horizon}"] = pd.NaT
                row["status"] = "invalid"
                continue
            row[f"ret_t{horizon}_close"] = float(future_close / entry_open - 1.0)
            row[f"date_t{horizon}"] = dates.iat[future_index]
        rows.append(row)
    return pd.DataFrame(rows, columns=_columns())


def _columns() -> list[str]:
    columns = ["code", "signal_date", "entry_date", "entry_open", "status", *OVERLAYS]
    for horizon in HORIZONS:
        columns.extend((f"ret_t{horizon}_close", f"date_t{horizon}"))
    return columns


def _quantiles(values: pd.Series) -> dict[str, float | None]:
    clean = pd.to_numeric(values, errors="coerce").dropna()
    return {str(q): (float(clean.quantile(q)) if len(clean) else None) for q in (0.1, 0.25, 0.5, 0.75, 0.9)}


def _metrics(rows: pd.DataFrame, horizon: int) -> dict[str, Any]:
    column = f"ret_t{horizon}_close"
    returns = pd.to_numeric(rows.get(column), errors="coerce")
    mature = rows.loc[returns.notna()].copy()
    returns = pd.to_numeric(mature[column], errors="coerce")
    counts = summarize_counts(len(mature), int(returns.gt(0).sum()))
    return {
        "n": counts["n"],
        "wins": counts["hits"],
        "win_rate": counts["precision"],
        "wilson_lower_95": counts["wilson_lower_95"],
        "wilson_upper_95": counts["wilson_upper_95"],
        "mean_return": float(returns.mean()) if len(mature) else None,
        "median_return": float(returns.median()) if len(mature) else None,
        "return_quantiles": _quantiles(returns),
        "entry_dates": int(mature["entry_date"].nunique()) if len(mature) else 0,
        "codes": int(mature["code"].nunique()) if len(mature) else 0,
    }


def _delta(overlay: Mapping[str, Any], parent: Mapping[str, Any]) -> dict[str, float | None]:
    pairs = {
        "win_rate": (overlay.get("win_rate"), parent.get("win_rate")),
        "mean_return": (overlay.get("mean_return"), parent.get("mean_return")),
        "median_return": (overlay.get("median_return"), parent.get("median_return")),
        "q10": (overlay.get("return_quantiles", {}).get("0.1"), parent.get("return_quantiles", {}).get("0.1")),
        "q25": (overlay.get("return_quantiles", {}).get("0.25"), parent.get("return_quantiles", {}).get("0.25")),
    }
    return {name: (None if left is None or right is None else float(left - right)) for name, (left, right) in pairs.items()}


def _periods(panel: pd.DataFrame) -> dict[str, tuple[int, int] | None]:
    years = sorted(int(year) for year in pd.to_datetime(panel.get("entry_date"), errors="coerce").dropna().dt.year.unique())
    if not years:
        return {"full_period": None}
    return {
        "full_period": None,
        "selection_2021_2023": (2021, 2023),
        "audit_2024_present": (2024, years[-1]),
        **{f"year_{year}": (year, year) for year in years},
    }


def aggregate_overlay_metrics(panel: pd.DataFrame) -> dict[str, Any]:
    periods = _periods(panel)
    results: dict[str, Any] = {name: {} for name in OVERLAYS}
    for period, bounds in periods.items():
        parent_rows = panel if bounds is None else panel.loc[pd.to_datetime(panel["entry_date"]).dt.year.between(*bounds)]
        for name in OVERLAYS:
            overlay_rows = parent_rows.loc[parent_rows[name].fillna(False)]
            results[name][period] = {}
            for horizon in HORIZONS:
                parent_metrics = _metrics(parent_rows, horizon)
                overlay_metrics = _metrics(overlay_rows, horizon)
                results[name][period][f"T+{horizon}"] = {
                    "mkf_parent": parent_metrics,
                    "overlay": overlay_metrics,
                    "overlay_minus_parent": _delta(overlay_metrics, parent_metrics),
                    "retention": overlay_metrics["n"] / parent_metrics["n"] if parent_metrics["n"] else 0.0,
                }
    return {"periods": list(periods), "overlays": results}


def evaluate_overlay_decisions(aggregated: Mapping[str, Any]) -> dict[str, Any]:
    decisions: dict[str, Any] = {}
    for name in OVERLAYS:
        metrics = aggregated["overlays"][name]
        t5 = metrics["full_period"]["T+5"]
        parent = t5["mkf_parent"]
        overlay = t5["overlay"]
        delta = t5["overlay_minus_parent"]
        failures: list[str] = []
        if int(overlay["n"]) < 300:
            failures.append("t5_n_below_300")
        if float(t5["retention"]) < 0.10:
            failures.append("t5_retention_below_0.10")
        if int(overlay["entry_dates"]) < 120:
            failures.append("t5_entry_dates_below_120")
        if int(overlay["codes"]) < 50:
            failures.append("t5_codes_below_50")
        if delta["win_rate"] is None or delta["win_rate"] < 0.03:
            failures.append("t5_win_rate_lift_below_0.03")
        if overlay["wilson_lower_95"] is None or parent["win_rate"] is None or overlay["wilson_lower_95"] <= parent["win_rate"]:
            failures.append("t5_wilson_lower_not_above_parent")
        for period in ("selection_2021_2023", "audit_2024_present"):
            lift = metrics[period]["T+5"]["overlay_minus_parent"]["win_rate"]
            if lift is None or lift <= 0:
                failures.append(f"{period}_t5_lift_not_positive")
        for year in COMPLETE_YEARS:
            period = f"year_{year}"
            if period not in metrics:
                failures.append(f"{period}_missing")
                continue
            lift = metrics[period]["T+5"]["overlay_minus_parent"]["win_rate"]
            if lift is None or lift <= 0:
                failures.append(f"{period}_t5_lift_not_positive")
        for horizon in (1, 3, 10):
            lift = metrics["full_period"][f"T+{horizon}"]["overlay_minus_parent"]["win_rate"]
            if lift is None or lift < -0.01:
                failures.append(f"t{horizon}_win_rate_delta_below_minus_0.01")
        if delta["median_return"] is None or delta["median_return"] < 0:
            failures.append("t5_median_return_declined")
        if delta["q10"] is None or delta["q10"] < -0.005:
            failures.append("t5_q10_worsened_over_0.005")
        decisions[name] = {
            "accepted": not failures,
            "failure_codes": failures,
            "primary_t5": t5,
        }
    accepted = [name for name in OVERLAYS if decisions[name]["accepted"]]
    return {
        "candidates": decisions,
        "accepted_overlays": accepted,
        "stop_direction": not accepted,
        "stop_rule": "If none pass, do not compose overlays or relax gates.",
    }


def build_overlay_report(
    *,
    panel: pd.DataFrame,
    code_list: list[str],
    code_list_sha256: str,
    start_date: str,
    end_date: str | None,
    workers: int,
) -> dict[str, Any]:
    aggregated = aggregate_overlay_metrics(panel)
    decision = evaluate_overlay_decisions(aggregated)
    return {
        "schema_version": SCHEMA_VERSION,
        "study": "controlled_same_day_futu_overlays_on_unchanged_mkf_v3",
        "research_only": True,
        "production_enabled": False,
        "watchlist_modified": False,
        "broker_orders_enabled": False,
        "ai_review_called": False,
        "thresholds_tuned": False,
        "original_mkf_v3_modified": False,
        "parent_definition": "production_gate_mask AND mkf_red_blue_cross20_green_exit_under80_mask",
        "overlay_definitions": {
            "kdj_trend_pro_buy": "K cross above D AND close>EMA60 AND K<90",
            "dxbd_cross_zero": "DXBD crosses from <=0 to >0",
            "gding_bbuy": "GDING fast crosses above signal",
            "mhpg_buy": "EMA20>EMA60 AND EMA60 rising AND MHPG K crosses D AND K<60",
        },
        "execution_definition": {
            "confirmation": "same MKF signal-day close",
            "entry": "next stock-tradable day open",
            "return": "T+n close after entry row / entry open - 1",
            "primary_horizon": "T+5",
        },
        "preregistered_gates": {
            "min_t5_n": 300,
            "min_t5_retention": 0.10,
            "min_entry_dates": 120,
            "min_codes": 50,
            "min_t5_win_rate_lift": 0.03,
            "t5_wilson_lower_above_parent": True,
            "positive_selection_and_audit_t5_lift": True,
            "positive_complete_year_t5_lift": True,
            "t1_t3_t10_max_win_rate_degradation": -0.01,
            "t5_median_must_not_decline": True,
            "t5_q10_max_degradation": -0.005,
        },
        "sample": {
            "method": "all_current_main_board_sorted_code",
            "codes": len(code_list),
            "code_list": code_list,
            "code_list_sha256": code_list_sha256,
            "mkf_parent_entries": int(len(panel)),
            "parent_status_counts": {str(key): int(value) for key, value in panel.get("status", pd.Series(dtype=object)).value_counts().items()},
        },
        "date_range": {"start_date": start_date, "end_date": end_date},
        "workers": workers,
        **aggregated,
        "decision": decision,
        "limitations": [
            "Adjusted current-vintage local bars and current-file survivorship remain limitations.",
            "Next-open entry is a descriptive proxy; no fillability, limit state, slippage, tax, or sizing is modeled.",
            "Only four preregistered same-day single overlays were evaluated; no pair, lag, or threshold mining was performed.",
            "Original MKF v3 remains unchanged regardless of this study result.",
        ],
    }
