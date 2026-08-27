from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np
import pandas as pd

from ..research_nextday_validation import candidate_masks
from ..research_precision70 import production_gate_mask
from .mkf_dxbd_annual_comparison import build_mkf_next_open_panel
from .mkf_dxbd_profitability import HORIZONS
from .quality import _numeric, normalise_stock_frame

SCHEMA_VERSION = "ncn_mkf_smc_annual_comparison_v1"


def production_smc_mask(code: str, frame: pd.DataFrame, config: Mapping[str, Any]) -> pd.Series:
    admitted = production_gate_mask(code, frame, config).reindex(frame.index, fill_value=False).astype(bool)
    smc = candidate_masks(frame)["smc_medium_buy"].reindex(frame.index, fill_value=False).astype(bool)
    return admitted & smc


def build_smc_next_open_panel(
    code: str,
    frame: pd.DataFrame,
    config: Mapping[str, Any],
    *,
    start_date: str = "2021-01-01",
    end_date: str | None = None,
) -> pd.DataFrame:
    data = normalise_stock_frame(frame)
    signal = production_smc_mask(code, data, config)
    trade = data.get("tradestatus", pd.Series(index=data.index, dtype=object)).astype("string")
    tradable = list(np.flatnonzero(trade.eq("1").fillna(False).to_numpy()))
    positions = {row_index: position for position, row_index in enumerate(tradable)}
    dates = pd.to_datetime(data["date"], errors="coerce")
    open_ = _numeric(data, "open").to_numpy(dtype=float)
    close = _numeric(data, "close").to_numpy(dtype=float)
    start = pd.Timestamp(start_date)
    end = pd.Timestamp(end_date) if end_date is not None else None

    rows: list[dict[str, Any]] = []
    for signal_index in data.index[signal.fillna(False)]:
        signal_date = dates.iat[signal_index]
        if signal_date < start or (end is not None and signal_date > end):
            continue
        signal_position = positions.get(signal_index)
        if signal_position is None or signal_position + 1 >= len(tradable):
            continue
        entry_index = tradable[signal_position + 1]
        entry_open = open_[entry_index]
        if not np.isfinite(entry_open) or entry_open <= 0:
            continue
        row: dict[str, Any] = {
            "code": code,
            "signal_date": signal_date,
            "entry_date": dates.iat[entry_index],
            "entry_open": float(entry_open),
            "status": "mature",
        }
        future = tradable[signal_position + 2:signal_position + 2 + len(HORIZONS)]
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
    return pd.DataFrame(rows, columns=_event_columns())


def _event_columns() -> list[str]:
    columns = ["code", "signal_date", "entry_date", "entry_open", "status"]
    for horizon in HORIZONS:
        columns.extend((f"ret_t{horizon}_close", f"date_t{horizon}"))
    return columns


def build_stock_strategy_panels(
    code: str,
    frame: pd.DataFrame,
    config: Mapping[str, Any],
    *,
    start_date: str = "2021-01-01",
    end_date: str | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    mkf = build_mkf_next_open_panel(code, frame, config, start_date=start_date, end_date=end_date)
    smc = build_smc_next_open_panel(code, frame, config, start_date=start_date, end_date=end_date)
    return mkf, smc


def _quantiles(values: pd.Series) -> dict[str, float | None]:
    clean = pd.to_numeric(values, errors="coerce").dropna()
    return {str(q): (float(clean.quantile(q)) if len(clean) else None) for q in (0.1, 0.25, 0.5, 0.75, 0.9)}


def _metrics(rows: pd.DataFrame, horizon: int) -> dict[str, Any]:
    column = f"ret_t{horizon}_close"
    returns = pd.to_numeric(rows.get(column), errors="coerce")
    mature = rows.loc[returns.notna()].copy()
    returns = pd.to_numeric(mature[column], errors="coerce")
    return {
        "n": int(len(mature)),
        "wins": int(returns.gt(0).sum()),
        "win_rate": float(returns.gt(0).mean()) if len(mature) else None,
        "mean_return": float(returns.mean()) if len(mature) else None,
        "median_return": float(returns.median()) if len(mature) else None,
        "return_quantiles": _quantiles(returns),
        "entry_dates": int(mature["entry_date"].nunique()) if len(mature) else 0,
        "codes": int(mature["code"].nunique()) if len(mature) else 0,
    }


def _delta(smc: Mapping[str, Any], mkf: Mapping[str, Any]) -> dict[str, float | None]:
    pairs = {
        "win_rate": (smc.get("win_rate"), mkf.get("win_rate")),
        "mean_return": (smc.get("mean_return"), mkf.get("mean_return")),
        "median_return": (smc.get("median_return"), mkf.get("median_return")),
        "q10": (smc.get("return_quantiles", {}).get("0.1"), mkf.get("return_quantiles", {}).get("0.1")),
        "q25": (smc.get("return_quantiles", {}).get("0.25"), mkf.get("return_quantiles", {}).get("0.25")),
    }
    return {name: (None if left is None or right is None else float(left - right)) for name, (left, right) in pairs.items()}


def aggregate_mkf_smc_comparison(mkf: pd.DataFrame, smc: pd.DataFrame) -> dict[str, Any]:
    years = sorted({
        int(year)
        for frame in (mkf, smc)
        for year in pd.to_datetime(frame.get("entry_date"), errors="coerce").dropna().dt.year
    })
    periods: dict[str, int | None] = {"full_period": None, **{f"year_{year}": year for year in years}}
    comparisons: dict[str, Any] = {}
    for period, year in periods.items():
        mkf_rows = mkf if year is None else mkf.loc[pd.to_datetime(mkf["entry_date"]).dt.year.eq(year)]
        smc_rows = smc if year is None else smc.loc[pd.to_datetime(smc["entry_date"]).dt.year.eq(year)]
        comparisons[period] = {}
        for horizon in HORIZONS:
            mkf_metrics = _metrics(mkf_rows, horizon)
            smc_metrics = _metrics(smc_rows, horizon)
            comparisons[period][f"T+{horizon}"] = {
                "mkf_v3": mkf_metrics,
                "production_smc": smc_metrics,
                "smc_minus_mkf": _delta(smc_metrics, mkf_metrics),
            }
    mkf_keys = set(zip(mkf.get("code", []), pd.to_datetime(mkf.get("entry_date"), errors="coerce")))
    smc_keys = set(zip(smc.get("code", []), pd.to_datetime(smc.get("entry_date"), errors="coerce")))
    return {
        "periods": list(periods),
        "comparisons": comparisons,
        "overlap": {
            "same_code_entry_date": len(mkf_keys & smc_keys),
            "mkf_unique_code_entry_dates": len(mkf_keys),
            "smc_unique_code_entry_dates": len(smc_keys),
        },
    }


def build_mkf_smc_report(
    *,
    mkf: pd.DataFrame,
    smc: pd.DataFrame,
    code_list: list[str],
    code_list_sha256: str,
    start_date: str,
    end_date: str | None,
    workers: int,
) -> dict[str, Any]:
    aggregated = aggregate_mkf_smc_comparison(mkf, smc)
    return {
        "schema_version": SCHEMA_VERSION,
        "study": "mkf_v3_vs_production_smc_next_open_t1_t10",
        "research_only": True,
        "production_enabled": False,
        "watchlist_modified": False,
        "broker_orders_enabled": False,
        "ai_review_called": False,
        "thresholds_tuned": False,
        "original_mkf_v3_modified": False,
        "production_smc_modified": False,
        "strategy_definitions": {
            "mkf_v3": "production_gate_mask AND mkf_red_blue_cross20_green_exit_under80_mask",
            "production_smc": "production_gate_mask AND expanded_futu_masks_from_values(...)[smc_medium_buy]",
            "smc_formula": "current tradable low > high two stock-tradable rows earlier AND EMA20 > EMA50",
        },
        "execution_definition": {
            "confirmation": "signal-day close",
            "entry": "next stock-tradable day open",
            "future_window": "first through tenth stock-tradable closes after entry row",
            "return": "future_close / entry_open - 1",
            "win": "return > 0",
            "annual_grouping": "entry_year",
        },
        "sample": {
            "method": "all_current_main_board_sorted_code",
            "codes": len(code_list),
            "code_list": code_list,
            "code_list_sha256": code_list_sha256,
            "mkf_entries": int(len(mkf)),
            "smc_entries": int(len(smc)),
            "mkf_status_counts": {str(key): int(value) for key, value in mkf.get("status", pd.Series(dtype=object)).value_counts().items()},
            "smc_status_counts": {str(key): int(value) for key, value in smc.get("status", pd.Series(dtype=object)).value_counts().items()},
        },
        "date_range": {"start_date": start_date, "end_date": end_date},
        "workers": workers,
        **aggregated,
        "limitations": [
            "Adjusted current-vintage local bars and current-file survivorship remain limitations.",
            "Next-open entry is a descriptive proxy; no fillability, limit state, slippage, tax, or sizing is modeled.",
            "The primary comparison uses independent strategy cohorts; overlap is reported but no post-hoc matching is imposed.",
            "Original MKF v3 and production SMC selectors were not modified.",
        ],
    }
