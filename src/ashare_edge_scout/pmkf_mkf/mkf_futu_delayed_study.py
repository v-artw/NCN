from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from typing import Any

import numpy as np
import pandas as pd

from ..research_futu_ranking import candidate_masks_from_values, tradable_indicator_values
from ..research_precision70 import production_gate_mask
from .mkf_dxbd_annual_comparison import build_mkf_next_open_panel
from .mkf_dxbd_profitability import HORIZONS
from .mkf_futu_overlay_study import COMPLETE_YEARS, OVERLAYS, _delta, _metrics
from .quality import _numeric, normalise_stock_frame
from .research import mkf_red_blue_cross20_green_exit_under80_mask

SCHEMA_VERSION = "ncn_mkf_futu_delayed_study_v1"
MIN_LAG = 1
MAX_LAG = 5


def build_delayed_stock_panels(
    code: str,
    frame: pd.DataFrame,
    config: Mapping[str, Any],
    *,
    start_date: str = "2021-01-01",
    end_date: str | None = None,
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame], dict[str, dict[str, int]]]:
    data = normalise_stock_frame(frame)
    parent = build_mkf_next_open_panel(code, data, config, start_date=start_date, end_date=end_date)
    admitted = production_gate_mask(code, data, config).reindex(data.index, fill_value=False).astype(bool)
    mkf = mkf_red_blue_cross20_green_exit_under80_mask(data).reindex(data.index, fill_value=False).astype(bool)
    parent_mask = admitted & mkf
    values = tradable_indicator_values(data)
    trading_masks = candidate_masks_from_values(values)
    full_masks: dict[str, pd.Series] = {}
    for name in OVERLAYS:
        full = pd.Series(False, index=data.index, dtype=bool)
        full.loc[values.index] = trading_masks[name]
        full_masks[name] = full

    trade = data.get("tradestatus", pd.Series(index=data.index, dtype=object)).astype("string")
    tradable = list(np.flatnonzero(trade.eq("1").fillna(False).to_numpy()))
    positions = {row_index: position for position, row_index in enumerate(tradable)}
    dates = pd.to_datetime(data["date"], errors="coerce")
    open_ = _numeric(data, "open").to_numpy(dtype=float)
    close = _numeric(data, "close").to_numpy(dtype=float)
    start = pd.Timestamp(start_date)
    end = pd.Timestamp(end_date) if end_date is not None else None
    origins = [
        index for index in data.index[parent_mask.fillna(False)]
        if dates.iat[index] >= start and (end is None or dates.iat[index] <= end)
    ]

    panels: dict[str, pd.DataFrame] = {}
    diagnostics: dict[str, dict[str, int]] = {}
    for name in OVERLAYS:
        rows: list[dict[str, Any]] = []
        counts: Counter[str] = Counter({"mkf_origins": len(origins)})
        used_entries: set[int] = set()
        for origin_index in origins:
            origin_position = positions.get(origin_index)
            if origin_position is None:
                continue
            confirmation_index: int | None = None
            confirmation_lag: int | None = None
            for lag in range(MIN_LAG, MAX_LAG + 1):
                candidate_position = origin_position + lag
                if candidate_position >= len(tradable):
                    break
                candidate_index = tradable[candidate_position]
                if bool(full_masks[name].loc[candidate_index]):
                    confirmation_index = candidate_index
                    confirmation_lag = lag
                    break
            if confirmation_index is None or confirmation_lag is None:
                counts["no_confirmation"] += 1
                continue
            counts["matched_confirmation"] += 1
            confirmation_position = positions[confirmation_index]
            if confirmation_position + 1 >= len(tradable):
                counts["missing_entry_row"] += 1
                continue
            entry_index = tradable[confirmation_position + 1]
            if entry_index in used_entries:
                counts["duplicate_entry"] += 1
                continue
            entry_open = open_[entry_index]
            if not np.isfinite(entry_open) or entry_open <= 0:
                counts["invalid_entry_open"] += 1
                continue
            used_entries.add(entry_index)
            counts[f"lag_{confirmation_lag}"] += 1
            row: dict[str, Any] = {
                "code": code,
                "mkf_date": dates.iat[origin_index],
                "confirmation_date": dates.iat[confirmation_index],
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
        panels[name] = pd.DataFrame(rows, columns=_columns())
        diagnostics[name] = {str(key): int(value) for key, value in counts.items()}
    return parent, panels, diagnostics


def _columns() -> list[str]:
    columns = [
        "code", "mkf_date", "confirmation_date", "confirmation_lag",
        "entry_date", "entry_open", "status",
    ]
    for horizon in HORIZONS:
        columns.extend((f"ret_t{horizon}_close", f"date_t{horizon}"))
    return columns


def _periods(parent: pd.DataFrame, candidates: Mapping[str, pd.DataFrame]) -> dict[str, tuple[int, int] | None]:
    years = sorted({
        int(year)
        for frame in (parent, *candidates.values())
        for year in pd.to_datetime(frame.get("entry_date"), errors="coerce").dropna().dt.year
    })
    if not years:
        return {"full_period": None}
    return {
        "full_period": None,
        "selection_2021_2023": (2021, 2023),
        "audit_2024_present": (2024, years[-1]),
        **{f"year_{year}": (year, year) for year in years},
    }


def aggregate_delayed_metrics(parent: pd.DataFrame, candidates: Mapping[str, pd.DataFrame]) -> dict[str, Any]:
    periods = _periods(parent, candidates)
    results: dict[str, Any] = {name: {} for name in OVERLAYS}
    for period, bounds in periods.items():
        parent_rows = parent if bounds is None else parent.loc[pd.to_datetime(parent["entry_date"]).dt.year.between(*bounds)]
        for name in OVERLAYS:
            frame = candidates[name]
            candidate_rows = frame if bounds is None else frame.loc[pd.to_datetime(frame["entry_date"]).dt.year.between(*bounds)]
            results[name][period] = {}
            for horizon in HORIZONS:
                parent_metrics = _metrics(parent_rows, horizon)
                candidate_metrics = _metrics(candidate_rows, horizon)
                results[name][period][f"T+{horizon}"] = {
                    "mkf_parent": parent_metrics,
                    "candidate": candidate_metrics,
                    "candidate_minus_parent": _delta(candidate_metrics, parent_metrics),
                    "retention": candidate_metrics["n"] / parent_metrics["n"] if parent_metrics["n"] else 0.0,
                }
    return {"periods": list(periods), "candidates": results}


def evaluate_delayed_decisions(aggregated: Mapping[str, Any]) -> dict[str, Any]:
    decisions: dict[str, Any] = {}
    for name in OVERLAYS:
        metrics = aggregated["candidates"][name]
        t5 = metrics["full_period"]["T+5"]
        parent = t5["mkf_parent"]
        candidate = t5["candidate"]
        delta = t5["candidate_minus_parent"]
        failures: list[str] = []
        if int(candidate["n"]) < 300:
            failures.append("t5_n_below_300")
        if float(t5["retention"]) < 0.10:
            failures.append("t5_retention_below_0.10")
        if int(candidate["entry_dates"]) < 120:
            failures.append("t5_entry_dates_below_120")
        if int(candidate["codes"]) < 50:
            failures.append("t5_codes_below_50")
        if delta["win_rate"] is None or delta["win_rate"] < 0.03:
            failures.append("t5_win_rate_lift_below_0.03")
        if candidate["wilson_lower_95"] is None or parent["win_rate"] is None or candidate["wilson_lower_95"] <= parent["win_rate"]:
            failures.append("t5_wilson_lower_not_above_parent")
        for period in ("selection_2021_2023", "audit_2024_present"):
            lift = metrics[period]["T+5"]["candidate_minus_parent"]["win_rate"]
            if lift is None or lift <= 0:
                failures.append(f"{period}_t5_lift_not_positive")
        for year in COMPLETE_YEARS:
            period = f"year_{year}"
            if period not in metrics:
                failures.append(f"{period}_missing")
                continue
            lift = metrics[period]["T+5"]["candidate_minus_parent"]["win_rate"]
            if lift is None or lift <= 0:
                failures.append(f"{period}_t5_lift_not_positive")
        for horizon in (1, 3, 10):
            lift = metrics["full_period"][f"T+{horizon}"]["candidate_minus_parent"]["win_rate"]
            if lift is None or lift < -0.01:
                failures.append(f"t{horizon}_win_rate_delta_below_minus_0.01")
        if delta["median_return"] is None or delta["median_return"] < 0:
            failures.append("t5_median_return_declined")
        if delta["q10"] is None or delta["q10"] < -0.005:
            failures.append("t5_q10_worsened_over_0.005")
        decisions[name] = {"accepted": not failures, "failure_codes": failures, "primary_t5": t5}
    accepted = [name for name in OVERLAYS if decisions[name]["accepted"]]
    return {
        "candidates": decisions,
        "accepted_candidates": accepted,
        "stop_direction": not accepted,
        "stop_rule": "If none pass, do not narrow lag, combine candidates, or relax gates.",
    }


def build_delayed_report(
    *,
    parent: pd.DataFrame,
    candidates: Mapping[str, pd.DataFrame],
    diagnostics: Mapping[str, Mapping[str, int]],
    code_list: list[str],
    code_list_sha256: str,
    start_date: str,
    end_date: str | None,
    workers: int,
) -> dict[str, Any]:
    aggregated = aggregate_delayed_metrics(parent, candidates)
    decision = evaluate_delayed_decisions(aggregated)
    return {
        "schema_version": SCHEMA_VERSION,
        "study": "mkf_then_first_futu_confirmation_lag_1_to_5",
        "research_only": True,
        "production_enabled": False,
        "watchlist_modified": False,
        "broker_orders_enabled": False,
        "ai_review_called": False,
        "thresholds_tuned": False,
        "original_mkf_v3_modified": False,
        "candidate_definitions": {
            "names": list(OVERLAYS),
            "window": "first occurrence at stock-tradable lag 1..5 after MKF; lag0 excluded",
            "confirmation": "candidate-day close",
            "entry": "next stock-tradable day open",
            "primary_horizon": "T+5",
        },
        "preregistered_gates": {
            "min_t5_n": 300,
            "min_t5_retention": 0.10,
            "min_entry_dates": 120,
            "min_codes": 50,
            "min_t5_win_rate_lift": 0.03,
            "t5_wilson_lower_above_parent": True,
            "positive_selection_audit_and_complete_year_t5_lifts": True,
            "t1_t3_t10_max_win_rate_degradation": -0.01,
            "t5_median_must_not_decline": True,
            "t5_q10_max_degradation": -0.005,
        },
        "sample": {
            "method": "all_current_main_board_sorted_code",
            "codes": len(code_list),
            "code_list": code_list,
            "code_list_sha256": code_list_sha256,
            "mkf_parent_entries": int(len(parent)),
            "candidate_entries": {name: int(len(candidates[name])) for name in OVERLAYS},
            "diagnostics": {name: dict(values) for name, values in diagnostics.items()},
        },
        "date_range": {"start_date": start_date, "end_date": end_date},
        "workers": workers,
        **aggregated,
        "decision": decision,
        "limitations": [
            "Adjusted current-vintage local bars and current-file survivorship remain limitations.",
            "Confirmation-next-open entry is a descriptive proxy; no fillability, slippage, tax, or sizing is modeled.",
            "Four candidates and lag 1..5 were fixed before computation; no any-of or lag-subrange mining is permitted.",
            "Original MKF v3 remains unchanged regardless of this study result.",
        ],
    }
