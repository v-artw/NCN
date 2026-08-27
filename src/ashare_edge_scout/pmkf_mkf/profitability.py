from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np
import pandas as pd

from ..research_precision70 import production_gate_mask
from .quality import _numeric, normalise_stock_frame
from .research import mkf_red_blue_cross20_green_exit_under80_mask

SCHEMA_VERSION = "ncn_mkf_profitability_t1_t10_v1"
MAX_HORIZON_TRADING_DAYS = 10
HORIZONS = tuple(range(1, MAX_HORIZON_TRADING_DAYS + 1))
CANDIDATE_NAME = "mkf_red_blue_cross20_green_exit_under80_v3_and_existing_hard_gates"


def mkf_profitability_candidate_mask(frame: pd.DataFrame, config: Mapping[str, Any], code: str) -> pd.Series:
    admitted = production_gate_mask(code, frame, config).reindex(frame.index, fill_value=False).astype(bool)
    mkf = mkf_red_blue_cross20_green_exit_under80_mask(frame).reindex(frame.index, fill_value=False).astype(bool)
    return admitted & mkf


def horizon_close_outcomes(frame: pd.DataFrame) -> dict[pd.Timestamp, dict[str, Any]]:
    trade = frame.get("tradestatus", pd.Series(index=frame.index, dtype=object)).astype("string")
    tradable = list(np.flatnonzero(trade.eq("1").fillna(False).to_numpy()))
    positions = {index: position for position, index in enumerate(tradable)}
    dates = pd.to_datetime(frame["date"], errors="coerce").to_numpy()
    close = _numeric(frame, "close").to_numpy(dtype=float)
    outcomes: dict[pd.Timestamp, dict[str, Any]] = {}
    for origin in range(len(frame)):
        origin_date = pd.Timestamp(dates[origin])
        row: dict[str, Any] = {"status": "origin_invalid"}
        position = positions.get(origin)
        reference = close[origin]
        if position is None or not np.isfinite(reference) or reference <= 0:
            outcomes[origin_date] = row
            continue
        row = {"status": "mature"}
        future = tradable[position + 1:position + 1 + MAX_HORIZON_TRADING_DAYS]
        for horizon in HORIZONS:
            ret_key = f"ret_t{horizon}_close"
            date_key = f"date_t{horizon}"
            if len(future) < horizon:
                row[ret_key] = np.nan
                row[date_key] = pd.NaT
                row["status"] = "partial"
                continue
            future_index = future[horizon - 1]
            future_close = close[future_index]
            if not np.isfinite(future_close):
                row[ret_key] = np.nan
                row[date_key] = pd.NaT
                row["status"] = "invalid"
                continue
            row[ret_key] = float(future_close / reference - 1.0)
            row[date_key] = pd.Timestamp(dates[future_index])
        outcomes[origin_date] = row
    return outcomes


def build_profitability_panel(
    code: str,
    frame: pd.DataFrame,
    config: Mapping[str, Any],
    *,
    start_date: str = "2021-01-01",
    end_date: str | None = None,
) -> pd.DataFrame:
    data = normalise_stock_frame(frame)
    candidates = mkf_profitability_candidate_mask(data, config, code)
    selected = data["date"].ge(pd.Timestamp(start_date))
    if end_date is not None:
        selected &= data["date"].le(pd.Timestamp(end_date))
    selected &= candidates.fillna(False)
    outcomes = horizon_close_outcomes(data)
    rows = data["date"].map(outcomes)
    panel: dict[str, Any] = {
        "code": code,
        "date": data["date"],
        "close": _numeric(data, "close"),
        "candidate": candidates,
        "status": rows.map(lambda value: value.get("status", "missing")),
    }
    for horizon in HORIZONS:
        panel[f"ret_t{horizon}_close"] = pd.to_numeric(
            rows.map(lambda value, h=horizon: value.get(f"ret_t{h}_close", np.nan)), errors="coerce"
        )
        panel[f"date_t{horizon}"] = pd.to_datetime(rows.map(lambda value, h=horizon: value.get(f"date_t{h}", pd.NaT)))
    return pd.DataFrame(panel).loc[selected].reset_index(drop=True)


def _quantiles(values: pd.Series) -> dict[str, float | None]:
    clean = pd.to_numeric(values, errors="coerce").dropna()
    return {str(q): (float(clean.quantile(q)) if len(clean) else None) for q in (0.1, 0.25, 0.5, 0.75, 0.9)}


def _horizon_metrics(panel: pd.DataFrame, horizon: int) -> dict[str, Any]:
    column = f"ret_t{horizon}_close"
    mature = panel.loc[pd.to_numeric(panel[column], errors="coerce").notna()].copy()
    returns = pd.to_numeric(mature[column], errors="coerce")
    wins = returns.gt(0)
    return {
        "n": int(len(mature)),
        "wins": int(wins.sum()),
        "win_rate": float(wins.mean()) if len(mature) else None,
        "mean_return": float(returns.mean()) if len(mature) else None,
        "median_return": float(returns.median()) if len(mature) else None,
        "return_quantiles": _quantiles(returns),
        "signal_dates": int(mature["date"].nunique()) if len(mature) else 0,
        "codes": int(mature["code"].nunique()) if len(mature) else 0,
    }


def aggregate_profitability_metrics(panel: pd.DataFrame) -> dict[str, Any]:
    return {f"T+{horizon}": _horizon_metrics(panel, horizon) for horizon in HORIZONS}


def build_profitability_report(
    *,
    panel: pd.DataFrame,
    code_list: list[str],
    code_list_sha256: str,
    start_date: str,
    end_date: str | None,
    workers: int,
) -> dict[str, Any]:
    observed_start = panel["date"].min() if len(panel) else pd.NaT
    observed_end = panel["date"].max() if len(panel) else pd.NaT
    return {
        "schema_version": SCHEMA_VERSION,
        "study": "mkf_t1_t10_close_to_close_profitability",
        "research_only": True,
        "classification_only": False,
        "production_enabled": False,
        "watchlist_modified": False,
        "smc_admission_modified": False,
        "broker_orders_enabled": False,
        "ai_review_called": False,
        "thresholds_tuned": False,
        "candidate_definition": {
            "name": CANDIDATE_NAME,
            "definition": "production_gate_mask AND mkf_red_blue_cross20_green_exit_under80_mask",
        },
        "return_definition": {
            "anchor": "signal_date_T_close",
            "future_window": "next_1_to_10_stock_tradable_closes",
            "return": "future_close / signal_date_close - 1",
            "win": "return > 0",
        },
        "sample": {
            "method": "all_current_main_board_sorted_code",
            "codes": len(code_list),
            "code_list": code_list,
            "code_list_sha256": code_list_sha256,
            "candidate_rows": int(len(panel)),
            "candidate_signal_dates": int(panel["date"].nunique()) if len(panel) else 0,
            "candidate_codes": int(panel["code"].nunique()) if len(panel) else 0,
        },
        "date_range": {
            "start_date": start_date,
            "end_date": end_date,
            "observed_start": observed_start.strftime("%Y-%m-%d") if pd.notna(observed_start) else None,
            "observed_end": observed_end.strftime("%Y-%m-%d") if pd.notna(observed_end) else None,
        },
        "workers": workers,
        "horizons": aggregate_profitability_metrics(panel),
        "limitations": [
            "Adjusted current-vintage local bars and current-file survivorship remain limitations.",
            "This is read-only research, not execution, orders, positions, or live-trading evidence.",
            "No transaction costs, slippage, liquidity execution, stop-loss, or take-profit rules are modeled.",
            "MKF thresholds are fixed before running and must not be tuned after seeing results.",
        ],
    }
