from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from typing import Any

import numpy as np
import pandas as pd

from ..research_futu_ranking import candidate_masks_from_values, tradable_indicator_values
from ..research_precision70 import production_gate_mask
from .quality import _numeric, normalise_stock_frame
from .research import mkf_red_blue_cross20_green_exit_under80_mask

SCHEMA_VERSION = "ncn_mkf_dxbd_profitability_t1_t10_v1"
HORIZONS = tuple(range(1, 11))
MAX_DXBD_LAG = 5
CANDIDATE_NAME = "mkf_v3_then_dxbd_control_within_0_to_5_tradable_days"


def _signal_masks(frame: pd.DataFrame, config: Mapping[str, Any], code: str) -> tuple[pd.Series, pd.Series]:
    admitted = production_gate_mask(code, frame, config).reindex(frame.index, fill_value=False).astype(bool)
    mkf = mkf_red_blue_cross20_green_exit_under80_mask(frame).reindex(frame.index, fill_value=False).astype(bool)
    values = tradable_indicator_values(frame)
    dxbd_trading = candidate_masks_from_values(values)["dxbd_cross_zero"]
    dxbd = pd.Series(False, index=frame.index, dtype=bool)
    dxbd.loc[values.index] = dxbd_trading
    return admitted & mkf, dxbd


def build_mkf_dxbd_event_panel(
    code: str,
    frame: pd.DataFrame,
    config: Mapping[str, Any],
    *,
    start_date: str = "2021-01-01",
    end_date: str | None = None,
) -> pd.DataFrame:
    data = normalise_stock_frame(frame)
    mkf, dxbd = _signal_masks(data, config, code)
    trade = data.get("tradestatus", pd.Series(index=data.index, dtype=object)).astype("string")
    tradable = list(np.flatnonzero(trade.eq("1").fillna(False).to_numpy()))
    positions = {row_index: position for position, row_index in enumerate(tradable)}
    dates = pd.to_datetime(data["date"], errors="coerce")
    open_ = _numeric(data, "open").to_numpy(dtype=float)
    close = _numeric(data, "close").to_numpy(dtype=float)

    rows: list[dict[str, Any]] = []
    diagnostics: Counter[str] = Counter()
    used_entry_indexes: set[int] = set()
    eligible_mkf_indexes = [
        index
        for index in data.index[mkf.fillna(False)]
        if dates.iat[index] >= pd.Timestamp(start_date)
        and (end_date is None or dates.iat[index] <= pd.Timestamp(end_date))
    ]
    diagnostics["mkf_signals"] = len(eligible_mkf_indexes)
    for mkf_index in eligible_mkf_indexes:
        mkf_position = positions.get(mkf_index)
        if mkf_position is None:
            continue
        confirmation_index: int | None = None
        confirmation_lag: int | None = None
        for lag in range(MAX_DXBD_LAG + 1):
            candidate_position = mkf_position + lag
            if candidate_position >= len(tradable):
                break
            candidate_index = tradable[candidate_position]
            if bool(dxbd.loc[candidate_index]):
                confirmation_index = candidate_index
                confirmation_lag = lag
                break
        if confirmation_index is None or confirmation_lag is None:
            diagnostics["no_dxbd_within_window"] += 1
            continue
        diagnostics["matched_mkf_dxbd"] += 1
        confirmation_position = positions[confirmation_index]
        if confirmation_position + 1 >= len(tradable):
            diagnostics["missing_entry_row"] += 1
            continue
        entry_index = tradable[confirmation_position + 1]
        if entry_index in used_entry_indexes:
            diagnostics["duplicate_entry_row"] += 1
            continue
        entry_open = open_[entry_index]
        if not np.isfinite(entry_open) or entry_open <= 0:
            diagnostics["invalid_entry_open"] += 1
            continue
        used_entry_indexes.add(entry_index)
        row: dict[str, Any] = {
            "code": code,
            "mkf_date": dates.iat[mkf_index],
            "dxbd_confirmation_date": dates.iat[confirmation_index],
            "confirmation_lag": confirmation_lag,
            "entry_date": dates.iat[entry_index],
            "entry_open": float(entry_open),
            "status": "mature",
        }
        future = tradable[confirmation_position + 2:confirmation_position + 2 + len(HORIZONS)]
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

    panel = pd.DataFrame(rows)
    if panel.empty:
        columns = [
            "code", "mkf_date", "dxbd_confirmation_date", "confirmation_lag",
            "entry_date", "entry_open", "status",
        ]
        for horizon in HORIZONS:
            columns.extend((f"ret_t{horizon}_close", f"date_t{horizon}"))
        result = pd.DataFrame(columns=columns)
        result.attrs["diagnostics"] = dict(diagnostics)
        return result
    result = panel.reset_index(drop=True)
    result.attrs["diagnostics"] = dict(diagnostics)
    return result


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
        "entry_dates": int(mature["entry_date"].nunique()) if len(mature) else 0,
        "codes": int(mature["code"].nunique()) if len(mature) else 0,
    }


def build_mkf_dxbd_report(
    *,
    panel: pd.DataFrame,
    code_list: list[str],
    code_list_sha256: str,
    start_date: str,
    end_date: str | None,
    workers: int,
) -> dict[str, Any]:
    observed_start = panel["mkf_date"].min() if len(panel) else pd.NaT
    observed_end = panel["mkf_date"].max() if len(panel) else pd.NaT
    lag_counts = Counter(int(value) for value in panel.get("confirmation_lag", pd.Series(dtype=int)).dropna())
    return {
        "schema_version": SCHEMA_VERSION,
        "study": "mkf_v3_then_dxbd_control_next_open_t1_t10_profitability",
        "research_only": True,
        "production_enabled": False,
        "watchlist_modified": False,
        "smc_admission_modified": False,
        "broker_orders_enabled": False,
        "ai_review_called": False,
        "thresholds_tuned": False,
        "original_mkf_v3_modified": False,
        "candidate_definition": {
            "name": CANDIDATE_NAME,
            "mkf": "production_gate_mask AND mkf_red_blue_cross20_green_exit_under80_mask",
            "dxbd": "CROSS((EMA(CS,3)-50)*2, 0)",
            "dxbd_lag_stock_tradable_days": [0, MAX_DXBD_LAG],
        },
        "entry_definition": {
            "confirmation": "DXBD control is known at confirmation-day close",
            "entry": "next stock-tradable day open after DXBD confirmation",
            "future_window": "next_1_to_10_stock_tradable_closes_after_entry_day",
            "return": "future_close / entry_open - 1",
            "win": "return > 0",
        },
        "sample": {
            "method": "all_current_main_board_sorted_code",
            "codes": len(code_list),
            "code_list": code_list,
            "code_list_sha256": code_list_sha256,
            "entries": int(len(panel)),
            "entry_dates": int(panel["entry_date"].nunique()) if len(panel) else 0,
            "entry_codes": int(panel["code"].nunique()) if len(panel) else 0,
            "confirmation_lag_counts": {str(lag): lag_counts.get(lag, 0) for lag in range(MAX_DXBD_LAG + 1)},
            "status_counts": {str(key): int(value) for key, value in panel.get("status", pd.Series(dtype=object)).value_counts().items()},
        },
        "date_range": {
            "start_date": start_date,
            "end_date": end_date,
            "observed_mkf_start": observed_start.strftime("%Y-%m-%d") if pd.notna(observed_start) else None,
            "observed_mkf_end": observed_end.strftime("%Y-%m-%d") if pd.notna(observed_end) else None,
        },
        "workers": workers,
        "horizons": {f"T+{horizon}": _horizon_metrics(panel, horizon) for horizon in HORIZONS},
        "limitations": [
            "Adjusted current-vintage local bars and current-file survivorship remain limitations.",
            "Next-day open is a descriptive execution proxy; no fillability, limit state, slippage, tax, or position sizing is modeled.",
            "The fixed MKF-to-DXBD lag window is 0 to 5 stock-tradable days and was not tuned after seeing this result.",
            "This study is isolated from the original MKF v3 candidate program and does not modify it.",
        ],
    }
