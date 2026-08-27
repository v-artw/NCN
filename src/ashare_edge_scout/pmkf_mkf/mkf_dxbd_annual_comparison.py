from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np
import pandas as pd

from ..research_precision70 import production_gate_mask
from .mkf_dxbd_profitability import HORIZONS, build_mkf_dxbd_event_panel
from .quality import _numeric, normalise_stock_frame
from .research import mkf_red_blue_cross20_green_exit_under80_mask

SCHEMA_VERSION = "ncn_mkf_dxbd_annual_comparison_v1"


def build_mkf_next_open_panel(
    code: str,
    frame: pd.DataFrame,
    config: Mapping[str, Any],
    *,
    start_date: str = "2021-01-01",
    end_date: str | None = None,
) -> pd.DataFrame:
    data = normalise_stock_frame(frame)
    admitted = production_gate_mask(code, data, config).reindex(data.index, fill_value=False).astype(bool)
    mkf = mkf_red_blue_cross20_green_exit_under80_mask(data).reindex(data.index, fill_value=False).astype(bool)
    signal = admitted & mkf
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
            "mkf_date": signal_date,
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
    columns = ["code", "mkf_date", "entry_date", "entry_open", "status"]
    for horizon in HORIZONS:
        columns.extend((f"ret_t{horizon}_close", f"date_t{horizon}"))
    return columns


def build_stock_comparison_panels(
    code: str,
    frame: pd.DataFrame,
    config: Mapping[str, Any],
    *,
    start_date: str = "2021-01-01",
    end_date: str | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    baseline = build_mkf_next_open_panel(code, frame, config, start_date=start_date, end_date=end_date)
    delayed = build_mkf_dxbd_event_panel(code, frame, config, start_date=start_date, end_date=end_date)
    if delayed.empty or baseline.empty:
        return baseline, delayed, _empty_matched_panel()

    immediate_columns = ["code", "mkf_date", "entry_date", *[f"ret_t{h}_close" for h in HORIZONS]]
    immediate = baseline[immediate_columns].rename(
        columns={
            "entry_date": "immediate_entry_date",
            **{f"ret_t{h}_close": f"immediate_ret_t{h}_close" for h in HORIZONS},
        }
    )
    delayed_columns = [
        "code", "mkf_date", "dxbd_confirmation_date", "confirmation_lag", "entry_date",
        *[f"ret_t{h}_close" for h in HORIZONS],
    ]
    delayed_for_merge = delayed[delayed_columns].rename(
        columns={
            "entry_date": "delayed_entry_date",
            **{f"ret_t{h}_close": f"delayed_ret_t{h}_close" for h in HORIZONS},
        }
    )
    matched = delayed_for_merge.merge(immediate, on=["code", "mkf_date"], how="inner", validate="one_to_one")
    return baseline, delayed, matched


def _empty_matched_panel() -> pd.DataFrame:
    columns = [
        "code", "mkf_date", "dxbd_confirmation_date", "confirmation_lag",
        "delayed_entry_date", "immediate_entry_date",
    ]
    for horizon in HORIZONS:
        columns.extend((f"delayed_ret_t{horizon}_close", f"immediate_ret_t{horizon}_close"))
    return pd.DataFrame(columns=columns)


def _quantiles(values: pd.Series) -> dict[str, float | None]:
    clean = pd.to_numeric(values, errors="coerce").dropna()
    return {str(q): (float(clean.quantile(q)) if len(clean) else None) for q in (0.1, 0.25, 0.5, 0.75, 0.9)}


def _metrics(rows: pd.DataFrame, return_column: str, date_column: str) -> dict[str, Any]:
    returns = pd.to_numeric(rows.get(return_column), errors="coerce")
    mature = rows.loc[returns.notna()].copy()
    returns = pd.to_numeric(mature[return_column], errors="coerce")
    quantiles = _quantiles(returns)
    return {
        "n": int(len(mature)),
        "wins": int(returns.gt(0).sum()),
        "win_rate": float(returns.gt(0).mean()) if len(mature) else None,
        "mean_return": float(returns.mean()) if len(mature) else None,
        "median_return": float(returns.median()) if len(mature) else None,
        "return_quantiles": quantiles,
        "entry_dates": int(mature[date_column].nunique()) if len(mature) else 0,
        "codes": int(mature["code"].nunique()) if len(mature) else 0,
    }


def _delta(left: Mapping[str, Any], right: Mapping[str, Any]) -> dict[str, float | None]:
    pairs = {
        "win_rate": (left.get("win_rate"), right.get("win_rate")),
        "mean_return": (left.get("mean_return"), right.get("mean_return")),
        "median_return": (left.get("median_return"), right.get("median_return")),
        "q10": (left.get("return_quantiles", {}).get("0.1"), right.get("return_quantiles", {}).get("0.1")),
        "q25": (left.get("return_quantiles", {}).get("0.25"), right.get("return_quantiles", {}).get("0.25")),
    }
    return {name: (None if a is None or b is None else float(a - b)) for name, (a, b) in pairs.items()}


def _periods(*date_series: pd.Series) -> dict[str, int | None]:
    years = sorted({int(year) for series in date_series for year in pd.to_datetime(series, errors="coerce").dropna().dt.year})
    return {"full_period": None, **{f"year_{year}": year for year in years}}


def aggregate_annual_comparison(
    baseline: pd.DataFrame,
    delayed: pd.DataFrame,
    matched: pd.DataFrame,
) -> dict[str, Any]:
    periods = _periods(baseline.get("entry_date", pd.Series(dtype="datetime64[ns]")), delayed.get("entry_date", pd.Series(dtype="datetime64[ns]")))
    primary: dict[str, Any] = {}
    timing: dict[str, Any] = {}
    for period, year in periods.items():
        base_rows = baseline if year is None else baseline.loc[pd.to_datetime(baseline["entry_date"]).dt.year.eq(year)]
        delayed_rows = delayed if year is None else delayed.loc[pd.to_datetime(delayed["entry_date"]).dt.year.eq(year)]
        matched_rows = matched if year is None else matched.loc[pd.to_datetime(matched["delayed_entry_date"]).dt.year.eq(year)]
        primary[period] = {}
        timing[period] = {}
        for horizon in HORIZONS:
            base_metrics = _metrics(base_rows, f"ret_t{horizon}_close", "entry_date")
            delayed_metrics = _metrics(delayed_rows, f"ret_t{horizon}_close", "entry_date")
            immediate_metrics = _metrics(matched_rows, f"immediate_ret_t{horizon}_close", "immediate_entry_date")
            matched_delayed_metrics = _metrics(matched_rows, f"delayed_ret_t{horizon}_close", "delayed_entry_date")
            primary[period][f"T+{horizon}"] = {
                "mkf_v3_baseline": base_metrics,
                "mkf_plus_dxbd": delayed_metrics,
                "dxbd_minus_baseline": _delta(delayed_metrics, base_metrics),
            }
            timing[period][f"T+{horizon}"] = {
                "matched_immediate_mkf_entry": immediate_metrics,
                "matched_delayed_dxbd_entry": matched_delayed_metrics,
                "delayed_minus_immediate": _delta(matched_delayed_metrics, immediate_metrics),
            }
    return {"periods": list(periods), "primary_comparison": primary, "matched_timing_diagnostic": timing}


def build_annual_comparison_report(
    *,
    baseline: pd.DataFrame,
    delayed: pd.DataFrame,
    matched: pd.DataFrame,
    code_list: list[str],
    code_list_sha256: str,
    start_date: str,
    end_date: str | None,
    workers: int,
) -> dict[str, Any]:
    aggregated = aggregate_annual_comparison(baseline, delayed, matched)
    return {
        "schema_version": SCHEMA_VERSION,
        "study": "annual_mkf_dxbd_vs_mkf_v3_fair_next_open_comparison",
        "research_only": True,
        "production_enabled": False,
        "watchlist_modified": False,
        "broker_orders_enabled": False,
        "ai_review_called": False,
        "thresholds_tuned": False,
        "original_mkf_v3_modified": False,
        "primary_definition": {
            "baseline": "hard-gated MKF v3 close confirmation; next stock-tradable open entry",
            "candidate": "MKF v3 then DXBD control within lag 0..5; next stock-tradable open after DXBD confirmation",
            "annual_grouping": "entry_year",
            "return": "T+n close after entry row / entry open - 1",
        },
        "matched_diagnostic_definition": {
            "cohort": "de-duplicated MKF events that later receive DXBD control within lag 0..5",
            "immediate": "next open after MKF confirmation",
            "delayed": "next open after DXBD confirmation",
            "annual_grouping": "delayed_DXBD_entry_year",
        },
        "sample": {
            "method": "all_current_main_board_sorted_code",
            "codes": len(code_list),
            "code_list": code_list,
            "code_list_sha256": code_list_sha256,
            "baseline_entries": int(len(baseline)),
            "dxbd_entries": int(len(delayed)),
            "matched_entries": int(len(matched)),
        },
        "date_range": {"start_date": start_date, "end_date": end_date},
        "workers": workers,
        **aggregated,
        "limitations": [
            "Adjusted current-vintage local bars and current-file survivorship remain limitations.",
            "Next-open entry is a descriptive proxy; no fillability, limit state, slippage, tax, or sizing is modeled.",
            "Independent-cohort differences combine DXBD cohort selection and delayed timing; use the matched diagnostic to inspect timing separately.",
            "No lag, threshold, year, or horizon was selected after observing this comparison.",
        ],
    }
