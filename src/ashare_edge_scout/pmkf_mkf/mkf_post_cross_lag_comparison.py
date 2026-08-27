from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from typing import Any

import numpy as np
import pandas as pd

from ..research_precision70 import production_gate_mask
from ..research_v2 import summarize_counts
from .quality import _numeric, normalise_stock_frame
from .research import mkf_red_blue_cross20_green_exit_under80_mask

LAGS = tuple(range(0, 8))
GRID_SCHEMA_VERSION = "ncn_mkf_post_cross_lag_target_grid_v3"
GRID_HORIZONS = tuple(range(1, 21))
GRID_TARGET_PCTS = tuple(range(1, 21))
PRIMARY_HORIZONS = (5, 10)
T20_CLOSE_FALLBACK_SCHEMA_VERSION = "ncn_mkf_post_cross_lag_t20_close_fallback_v1"
T20_CLOSE_FALLBACK_HORIZON = 20

# Pre-registered stability gates: a cell may be named a "best point" candidate only
# if it passes every gate below. Numbers are frozen before any grid run and must not
# be relaxed afterwards merely to produce a positive result.
STABILITY_GATE_CONFIG = {
    "min_n": 300,
    "min_entry_dates": 120,
    "min_codes": 50,
    "audit_drawdown_pp": 3.0,
    "min_years_observed": 4,
    "year_drawdown_pp": 5.0,
    "min_years_within_drawdown": 4,
}


def _grid_columns(horizons: tuple[int, ...] = GRID_HORIZONS, *, include_future_close: bool = False) -> list[str]:
    columns = ["code", "cross_date", "signal_date", "entry_date", "post_cross_lag", "entry_open", "status"]
    for horizon in range(1, max(horizons) + 1):
        columns.extend((f"date_t{horizon}", f"future_high_t{horizon}"))
        if include_future_close:
            columns.append(f"future_close_t{horizon}")
    return columns


def _target_key(target_pct: int) -> str:
    return f"target_{target_pct}pct"


def _target_return(target_pct: int) -> float:
    return float(target_pct) / 100.0


def build_mkf_post_cross_lag_target_grid_panel(
    code: str,
    frame: pd.DataFrame,
    config: Mapping[str, Any],
    *,
    start_date: str = "2021-01-01",
    end_date: str | None = None,
    lags: tuple[int, ...] = LAGS,
    horizons: tuple[int, ...] = GRID_HORIZONS,
    include_future_close: bool = False,
) -> pd.DataFrame:
    data = normalise_stock_frame(frame)
    cross = mkf_red_blue_cross20_green_exit_under80_mask(data).reindex(data.index, fill_value=False).astype(bool)
    admitted = production_gate_mask(code, data, config).reindex(data.index, fill_value=False).astype(bool)
    trade = data.get("tradestatus", pd.Series(index=data.index, dtype=object)).astype("string")
    tradable = list(np.flatnonzero(trade.eq("1").fillna(False).to_numpy()))
    positions = {row_index: position for position, row_index in enumerate(tradable)}
    dates = pd.to_datetime(data["date"], errors="coerce")
    open_ = _numeric(data, "open").to_numpy(dtype=float)
    high = _numeric(data, "high").to_numpy(dtype=float)
    close = _numeric(data, "close").to_numpy(dtype=float) if include_future_close else None
    start = pd.Timestamp(start_date)
    end = pd.Timestamp(end_date) if end_date is not None else None
    max_horizon = max(horizons)

    rows: list[dict[str, Any]] = []
    diagnostics: Counter[str] = Counter()
    used_entry_by_lag: dict[int, set[int]] = {lag: set() for lag in lags}
    parent_indexes = [
        int(index)
        for index in data.index[cross.fillna(False)]
        if dates.iat[int(index)] >= start and (end is None or dates.iat[int(index)] <= end)
    ]
    diagnostics["parent_crosses"] = len(parent_indexes)
    for cross_index in parent_indexes:
        cross_position = positions.get(cross_index)
        if cross_position is None:
            diagnostics["nontradable_parent_cross"] += 1
            continue
        for lag in lags:
            target_position = cross_position + lag
            if target_position >= len(tradable):
                diagnostics[f"lag_{lag}_missing_signal_row"] += 1
                continue
            signal_index = tradable[target_position]
            signal_date = dates.iat[signal_index]
            if end is not None and signal_date > end:
                diagnostics[f"lag_{lag}_after_end_date"] += 1
                continue
            if not bool(admitted.loc[signal_index]):
                diagnostics[f"lag_{lag}_hard_gate_rejected"] += 1
                continue
            entry_position = target_position + 1
            if entry_position >= len(tradable):
                diagnostics[f"lag_{lag}_missing_entry_row"] += 1
                continue
            entry_index = tradable[entry_position]
            if entry_index in used_entry_by_lag[lag]:
                diagnostics[f"lag_{lag}_duplicate_entry_row"] += 1
                continue
            entry_open = open_[entry_index]
            if not np.isfinite(entry_open) or entry_open <= 0:
                diagnostics[f"lag_{lag}_invalid_entry_open"] += 1
                continue
            used_entry_by_lag[lag].add(entry_index)
            future = tradable[entry_position + 1:entry_position + 1 + max_horizon]
            row: dict[str, Any] = {
                "code": code,
                "cross_date": dates.iat[cross_index],
                "signal_date": signal_date,
                "entry_date": dates.iat[entry_index],
                "post_cross_lag": int(lag),
                "entry_open": float(entry_open),
                "status": "mature" if len(future) >= max_horizon else "partial",
            }
            for horizon in range(1, max_horizon + 1):
                if len(future) < horizon:
                    row[f"date_t{horizon}"] = pd.NaT
                    row[f"future_high_t{horizon}"] = np.nan
                    if include_future_close:
                        row[f"future_close_t{horizon}"] = np.nan
                    continue
                future_index = future[horizon - 1]
                if not np.isfinite(high[future_index]):
                    row["status"] = "invalid"
                row[f"date_t{horizon}"] = dates.iat[future_index]
                row[f"future_high_t{horizon}"] = float(high[future_index]) if np.isfinite(high[future_index]) else np.nan
                if include_future_close:
                    assert close is not None
                    future_close = close[future_index]
                    if not np.isfinite(future_close):
                        row["status"] = "invalid"
                    row[f"future_close_t{horizon}"] = float(future_close) if np.isfinite(future_close) else np.nan
            rows.append(row)
            diagnostics[f"lag_{lag}_events"] += 1

    result = pd.DataFrame(rows, columns=_grid_columns(horizons, include_future_close=include_future_close))
    result.attrs["diagnostics"] = dict(diagnostics)
    return result


def _empty_grid_metric() -> dict[str, Any]:
    empty_counts = summarize_counts(0, 0)
    return {
        "n": 0,
        "target_hits": 0,
        "target_hit_rate": empty_counts["precision"],
        "target_hit_wilson_lower_95": empty_counts["wilson_lower_95"],
        "target_hit_wilson_upper_95": empty_counts["wilson_upper_95"],
        "mean_target_zero_return": None,
        "entry_dates": 0,
        "codes": 0,
    }


def _grid_metrics_from_arrays(
    *,
    mature: pd.DataFrame,
    entry_values: np.ndarray,
    max_highs: np.ndarray,
    target_pct: int,
) -> dict[str, Any]:
    if mature.empty:
        return _empty_grid_metric()
    target_hits = np.greater_equal(max_highs, entry_values * (1.0 + _target_return(target_pct)))
    hit_counts = summarize_counts(len(mature), int(target_hits.sum()))
    target_return = _target_return(target_pct)
    hit_rate = hit_counts["precision"]
    return {
        "n": hit_counts["n"],
        "target_hits": hit_counts["hits"],
        "target_hit_rate": hit_rate,
        "target_hit_wilson_lower_95": hit_counts["wilson_lower_95"],
        "target_hit_wilson_upper_95": hit_counts["wilson_upper_95"],
        "mean_target_zero_return": float(target_return * hit_rate) if hit_rate is not None else None,
        "entry_dates": int(mature["entry_date"].nunique()),
        "codes": int(mature["code"].nunique()),
    }


def _grid_metrics_for_targets(rows: pd.DataFrame, horizon: int, target_pcts: tuple[int, ...]) -> dict[str, Any]:
    entry = pd.to_numeric(rows.get("entry_open"), errors="coerce")
    horizon_high = pd.to_numeric(rows.get(f"future_high_t{horizon}"), errors="coerce")
    mature = rows.loc[entry.gt(0) & entry.notna() & horizon_high.notna()].copy()
    if mature.empty:
        return {_target_key(target_pct): _empty_grid_metric() for target_pct in target_pcts}
    entry_values = pd.to_numeric(mature["entry_open"], errors="coerce").to_numpy(dtype=float)
    high_columns = [f"future_high_t{step}" for step in range(1, horizon + 1)]
    highs = mature.reindex(columns=high_columns).apply(pd.to_numeric, errors="coerce").to_numpy(dtype=float)
    max_highs = np.nanmax(highs, axis=1)
    return {
        _target_key(target_pct): _grid_metrics_from_arrays(
            mature=mature,
            entry_values=entry_values,
            max_highs=max_highs,
            target_pct=target_pct,
        )
        for target_pct in target_pcts
    }


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


def _lag_rows(panel: pd.DataFrame, lag: int, bounds: tuple[int, int] | None) -> pd.DataFrame:
    rows = panel.loc[pd.to_numeric(panel.get("post_cross_lag"), errors="coerce").eq(lag)]
    if bounds is None or rows.empty:
        return rows
    years = pd.to_datetime(rows["entry_date"], errors="coerce").dt.year
    return rows.loc[years.between(*bounds)]


def aggregate_lag_target_grid_metrics(
    panel: pd.DataFrame,
    diagnostics: Mapping[str, Any] | None = None,
    *,
    horizons: tuple[int, ...] = GRID_HORIZONS,
    target_pcts: tuple[int, ...] = GRID_TARGET_PCTS,
) -> dict[str, Any]:
    periods = _periods(panel)
    parent_crosses = int((diagnostics or {}).get("parent_crosses", 0))
    lag_summary: dict[str, Any] = {}
    grid_metrics: dict[str, Any] = {}
    for lag in LAGS:
        rows = _lag_rows(panel, lag, None)
        lag_summary[str(lag)] = {
            "events": int(len(rows)),
            "retention_vs_parent_crosses": float(len(rows) / parent_crosses) if parent_crosses else 0.0,
            "signal_dates": int(rows["signal_date"].nunique()) if len(rows) else 0,
            "entry_dates": int(rows["entry_date"].nunique()) if len(rows) else 0,
            "codes": int(rows["code"].nunique()) if len(rows) else 0,
            "status_counts": {str(key): int(value) for key, value in rows.get("status", pd.Series(dtype=object)).value_counts().items()},
        }
        grid_metrics[str(lag)] = {}
        for period, bounds in periods.items():
            period_rows = _lag_rows(panel, lag, bounds)
            grid_metrics[str(lag)][period] = {
                f"T+{horizon}": _grid_metrics_for_targets(period_rows, horizon, target_pcts)
                for horizon in horizons
            }
    return {"periods": list(periods), "lag_summary": lag_summary, "grid_metrics": grid_metrics}


def _parse_target_pct(target_label: str) -> int:
    return int(target_label.removeprefix("target_").removesuffix("pct"))


def _stability_gate_result(period_metrics: Mapping[str, Mapping[str, Any]], config: Mapping[str, Any] = STABILITY_GATE_CONFIG) -> dict[str, Any]:
    full = period_metrics.get("full_period") or {}
    full_rate = full.get("target_hit_rate")
    n = int(full.get("n") or 0)
    checks: dict[str, bool] = {
        "min_n": n >= int(config["min_n"]),
        "min_entry_dates": int(full.get("entry_dates") or 0) >= int(config["min_entry_dates"]),
        "min_codes": int(full.get("codes") or 0) >= int(config["min_codes"]),
    }
    audit = period_metrics.get("audit_2024_present") or {}
    audit_rate = audit.get("target_hit_rate")
    audit_drawdown_pp: float | None = None
    if full_rate is not None and audit_rate is not None:
        audit_drawdown_pp = (full_rate - audit_rate) * 100.0
        checks["audit_within_drawdown"] = audit_drawdown_pp <= float(config["audit_drawdown_pp"])
    else:
        checks["audit_within_drawdown"] = False
    year_deltas: dict[str, float] = {}
    for period_key, metrics in period_metrics.items():
        if not period_key.startswith("year_"):
            continue
        year_rate = metrics.get("target_hit_rate")
        if full_rate is None or year_rate is None or int(metrics.get("n") or 0) <= 0:
            continue
        year_deltas[period_key] = (full_rate - year_rate) * 100.0
    years_within = sum(1 for delta in year_deltas.values() if delta <= float(config["year_drawdown_pp"]))
    checks["min_years_observed"] = len(year_deltas) >= int(config["min_years_observed"])
    checks["min_years_within_drawdown"] = years_within >= int(config["min_years_within_drawdown"])
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "full_period_hit_rate": full_rate,
        "audit_hit_rate": audit_rate,
        "audit_drawdown_pp": audit_drawdown_pp,
        "year_deltas_pp": {key: round(value, 4) for key, value in sorted(year_deltas.items())},
        "years_within_drawdown": years_within,
        "years_observed": len(year_deltas),
    }


def _candidate_key(item: Mapping[str, Any]) -> tuple[float, float, float, int, int, int]:
    return (
        item["mean_target_zero_return"] if item.get("mean_target_zero_return") is not None else -1.0,
        item["target_hit_rate"] if item.get("target_hit_rate") is not None else -1.0,
        item["target_hit_wilson_lower_95"] if item.get("target_hit_wilson_lower_95") is not None else -1.0,
        int(item.get("n") or 0),
        -int(item["lag"]),
        -int(item["target_pct"]),
    )


def _metric_candidate(lag: str, horizon_label: str, target_label: str, metrics: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "lag": int(lag),
        "horizon": horizon_label,
        "target_pct": _parse_target_pct(target_label),
        "n": metrics.get("n"),
        "target_hits": metrics.get("target_hits"),
        "target_hit_rate": metrics.get("target_hit_rate"),
        "target_hit_wilson_lower_95": metrics.get("target_hit_wilson_lower_95"),
        "target_hit_wilson_upper_95": metrics.get("target_hit_wilson_upper_95"),
        "mean_target_zero_return": metrics.get("mean_target_zero_return"),
        "entry_dates": metrics.get("entry_dates"),
        "codes": metrics.get("codes"),
    }


def _best_return_cell(aggregated: Mapping[str, Any], *, period: str = "full_period") -> dict[str, Any] | None:
    best: dict[str, Any] | None = None
    for lag, periods in aggregated["grid_metrics"].items():
        horizons = periods.get(period) or {}
        for horizon_label, targets in horizons.items():
            for target_label, metrics in targets.items():
                if int(metrics.get("n") or 0) <= 0:
                    continue
                candidate = _metric_candidate(lag, horizon_label, target_label, metrics)
                if best is None or _candidate_key(candidate) > _candidate_key(best):
                    best = candidate
    return best


def _best_return_by_horizon(aggregated: Mapping[str, Any], *, period: str = "full_period") -> dict[str, Any]:
    best_by_horizon: dict[str, dict[str, Any]] = {}
    for lag, periods in aggregated["grid_metrics"].items():
        horizons = periods.get(period) or {}
        for horizon_label, targets in horizons.items():
            for target_label, metrics in targets.items():
                if int(metrics.get("n") or 0) <= 0:
                    continue
                candidate = _metric_candidate(lag, horizon_label, target_label, metrics)
                current = best_by_horizon.get(horizon_label)
                if current is None or _candidate_key(candidate) > _candidate_key(current):
                    best_by_horizon[horizon_label] = candidate
    return {horizon: best_by_horizon[horizon] for horizon in sorted(best_by_horizon, key=lambda item: int(item[2:]))}


def _best_return_by_target(aggregated: Mapping[str, Any], *, period: str = "full_period") -> dict[str, Any]:
    best_by_target: dict[int, dict[str, Any]] = {}
    for lag, periods in aggregated["grid_metrics"].items():
        horizons = periods.get(period) or {}
        for horizon_label, targets in horizons.items():
            for target_label, metrics in targets.items():
                if int(metrics.get("n") or 0) <= 0:
                    continue
                candidate = _metric_candidate(lag, horizon_label, target_label, metrics)
                target_pct = candidate["target_pct"]
                current = best_by_target.get(target_pct)
                if current is None or _candidate_key(candidate) > _candidate_key(current):
                    best_by_target[target_pct] = candidate
    return {str(target_pct): best_by_target[target_pct] for target_pct in sorted(best_by_target)}


def _eligible_best_point_cells(aggregated: Mapping[str, Any], *, horizon_label: str) -> list[dict[str, Any]]:
    eligible: list[dict[str, Any]] = []
    for lag, periods in aggregated["grid_metrics"].items():
        targets = (periods.get("full_period") or {}).get(horizon_label, {})
        for target_label, metrics in targets.items():
            if int(metrics.get("n") or 0) <= 0:
                continue
            gate = _stability_gate_result(
                {period: (horizons.get(horizon_label, {}) or {}).get(target_label, {}) for period, horizons in periods.items()}
            )
            if not gate["passed"]:
                continue
            candidate = _metric_candidate(lag, horizon_label, target_label, metrics)
            candidate["stability_gate"] = gate
            eligible.append(candidate)
    eligible.sort(key=_candidate_key, reverse=True)
    return eligible


def _best_point_readout(aggregated: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "method": "Rank cells by mean_target_zero_return = target_pct / 100 * target_hit_rate; non-hit samples contribute 0% return.",
        "best_by_mean_target_zero_return": _best_return_cell(aggregated),
        "best_by_horizon": _best_return_by_horizon(aggregated),
        "best_by_target_pct": _best_return_by_target(aggregated),
        "primary_horizons": [f"T+{horizon}" for horizon in PRIMARY_HORIZONS],
        "stability_gates": dict(STABILITY_GATE_CONFIG),
        "eligible_cells_by_primary_horizon": {
            f"T+{horizon}": _eligible_best_point_cells(aggregated, horizon_label=f"T+{horizon}")
            for horizon in PRIMARY_HORIZONS
        },
        "warning": "Readout cells are in-sample descriptive research results, not production selection or take-profit rules; do not promote them without separate out-of-sample validation.",
    }


def build_lag_target_grid_report(
    *,
    panel: pd.DataFrame,
    diagnostics: Mapping[str, Any],
    code_list: list[str],
    code_list_sha256: str,
    start_date: str,
    end_date: str | None,
    workers: int,
    horizons: tuple[int, ...] = GRID_HORIZONS,
    target_pcts: tuple[int, ...] = GRID_TARGET_PCTS,
) -> dict[str, Any]:
    aggregated = aggregate_lag_target_grid_metrics(panel, diagnostics, horizons=horizons, target_pcts=target_pcts)
    observed_start = panel["cross_date"].min() if len(panel) else pd.NaT
    observed_end = panel["cross_date"].max() if len(panel) else pd.NaT
    return {
        "schema_version": GRID_SCHEMA_VERSION,
        "study": "mkf_post_cross_lag0_to_lag7_target_zero_return_grid",
        "research_only": True,
        "production_enabled": False,
        "watchlist_modified": False,
        "smc_admission_modified": False,
        "broker_orders_enabled": False,
        "ai_review_called": False,
        "thresholds_tuned": False,
        "original_mkf_selector_modified": False,
        "grid": {
            "lags": list(LAGS),
            "horizons": list(horizons),
            "target_pcts": list(target_pcts),
        },
        "candidate_definition": {
            "parent_cross": "mkf_red_blue_cross20_green_exit_under80_mask",
            "lag_signal": "lag0..5 stock-tradable rows from parent cross, evaluated as independent cohorts",
            "hard_gate": "production_gate_mask applied at each lag signal row",
            "suspension_handling": "non-tradable rows do not consume lag or horizon windows",
        },
        "entry_definition": {
            "entry": "next stock-tradable open after lag signal close",
            "target_price": "entry_open * (1 + target_pct / 100)",
            "target_hit": "any high from T+1 through T+n sellable stock-tradable days after entry reaches target_price",
            "non_hit_outcome": "not hit by T+n; return is fixed at 0% by user instruction, with no T+n close fallback and no stop-loss rule",
            "ranking": "highest mean_target_zero_return, where mean_target_zero_return = target_pct / 100 * target_hit_rate",
            "entry_day_high": "excluded because newly bought A-share positions are not same-day sellable",
            "fees_slippage_tax_fillability": "not modeled",
        },
        "sample": {
            "method": "all_current_main_board_sorted_code",
            "codes": len(code_list),
            "code_list": code_list,
            "code_list_sha256": code_list_sha256,
            "parent_crosses": int(diagnostics.get("parent_crosses", 0)),
            "lag_events": int(len(panel)),
            "event_lag_counts": {str(lag): int((panel.get("post_cross_lag", pd.Series(dtype=int)) == lag).sum()) for lag in LAGS},
            "status_counts": {str(key): int(value) for key, value in panel.get("status", pd.Series(dtype=object)).value_counts().items()},
        },
        "event_diagnostics": {str(key): int(value) for key, value in diagnostics.items()},
        "date_range": {
            "start_date": start_date,
            "end_date": end_date,
            "observed_cross_start": observed_start.strftime("%Y-%m-%d") if pd.notna(observed_start) else None,
            "observed_cross_end": observed_end.strftime("%Y-%m-%d") if pd.notna(observed_end) else None,
        },
        "workers": workers,
        **aggregated,
        "best_point_readout": _best_point_readout(aggregated),
        "limitations": [
            "Adjusted current-vintage local bars and current-file survivorship remain limitations.",
            "Next-open entry is descriptive; no fillability, limit state, fees, slippage, tax, sizing, or stop loss is modeled.",
            "Non-hit trades are fixed at 0% return by user decision; no timeout close, stop loss, fees, slippage, tax, sizing, or fillability is modeled.",
            "Mean target-zero return is a simplified capped return metric, not an executable P&L model or real profit promise.",
            "The study uses the current local NCN MKF formula; prior Futu chart formula calibration risk remains unresolved.",
            "Lag0..5 target grid cells are descriptive in-sample research cohorts and no production selector behavior was changed.",
            "Any cell named a best point must pass the pre-registered stability gates and still requires separate out-of-sample validation before any production use.",
        ],
    }


def build_mkf_post_cross_lag_t20_close_fallback_panel(
    code: str,
    frame: pd.DataFrame,
    config: Mapping[str, Any],
    *,
    start_date: str = "2021-01-01",
    end_date: str | None = None,
    lags: tuple[int, ...] = LAGS,
) -> pd.DataFrame:
    return build_mkf_post_cross_lag_target_grid_panel(
        code,
        frame,
        config,
        start_date=start_date,
        end_date=end_date,
        lags=lags,
        horizons=(T20_CLOSE_FALLBACK_HORIZON,),
        include_future_close=True,
    )


def _empty_t20_close_fallback_metric() -> dict[str, Any]:
    empty_counts = summarize_counts(0, 0)
    return {
        "n": 0,
        "target_hits": 0,
        "target_hit_rate": empty_counts["precision"],
        "target_hit_wilson_lower_95": empty_counts["wilson_lower_95"],
        "target_hit_wilson_upper_95": empty_counts["wilson_upper_95"],
        "mean_realized_return": None,
        "median_realized_return": None,
        "entry_dates": 0,
        "codes": 0,
    }


def _t20_close_fallback_metrics_for_targets(rows: pd.DataFrame, target_pcts: tuple[int, ...]) -> dict[str, Any]:
    entry = pd.to_numeric(rows.get("entry_open"), errors="coerce")
    horizon_high = pd.to_numeric(rows.get("future_high_t20"), errors="coerce")
    horizon_close = pd.to_numeric(rows.get("future_close_t20"), errors="coerce")
    mature = rows.loc[entry.gt(0) & entry.notna() & horizon_high.notna() & horizon_close.notna()].copy()
    if mature.empty:
        return {_target_key(target_pct): _empty_t20_close_fallback_metric() for target_pct in target_pcts}
    entry_values = pd.to_numeric(mature["entry_open"], errors="coerce").to_numpy(dtype=float)
    high_columns = [f"future_high_t{step}" for step in range(1, T20_CLOSE_FALLBACK_HORIZON + 1)]
    highs = mature.reindex(columns=high_columns).apply(pd.to_numeric, errors="coerce").to_numpy(dtype=float)
    max_highs = np.nanmax(highs, axis=1)
    close_values = pd.to_numeric(mature["future_close_t20"], errors="coerce").to_numpy(dtype=float)
    close_returns = close_values / entry_values - 1.0
    metrics_by_target: dict[str, Any] = {}
    for target_pct in target_pcts:
        target_return = _target_return(target_pct)
        target_hits = np.greater_equal(max_highs, entry_values * (1.0 + target_return))
        realized = np.where(target_hits, target_return, close_returns)
        hit_counts = summarize_counts(len(mature), int(target_hits.sum()))
        metrics_by_target[_target_key(target_pct)] = {
            "n": hit_counts["n"],
            "target_hits": hit_counts["hits"],
            "target_hit_rate": hit_counts["precision"],
            "target_hit_wilson_lower_95": hit_counts["wilson_lower_95"],
            "target_hit_wilson_upper_95": hit_counts["wilson_upper_95"],
            "mean_realized_return": float(np.mean(realized)),
            "median_realized_return": float(np.median(realized)),
            "entry_dates": int(mature["entry_date"].nunique()),
            "codes": int(mature["code"].nunique()),
        }
    return metrics_by_target


def _t20_close_fallback_candidate_key(item: Mapping[str, Any]) -> tuple[float, float, float, int, int, int]:
    return (
        item["mean_realized_return"] if item.get("mean_realized_return") is not None else -999.0,
        item["median_realized_return"] if item.get("median_realized_return") is not None else -999.0,
        item["target_hit_rate"] if item.get("target_hit_rate") is not None else -1.0,
        int(item.get("n") or 0),
        -int(item["lag"]),
        -int(item["target_pct"]),
    )


def _t20_close_fallback_candidate(lag: str, target_label: str, metrics: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "lag": int(lag),
        "horizon": "T+20",
        "target_pct": _parse_target_pct(target_label),
        "n": metrics.get("n"),
        "target_hits": metrics.get("target_hits"),
        "target_hit_rate": metrics.get("target_hit_rate"),
        "target_hit_wilson_lower_95": metrics.get("target_hit_wilson_lower_95"),
        "target_hit_wilson_upper_95": metrics.get("target_hit_wilson_upper_95"),
        "mean_realized_return": metrics.get("mean_realized_return"),
        "median_realized_return": metrics.get("median_realized_return"),
        "entry_dates": metrics.get("entry_dates"),
        "codes": metrics.get("codes"),
    }


def _best_t20_close_fallback_cell(grid_metrics: Mapping[str, Any]) -> dict[str, Any] | None:
    best: dict[str, Any] | None = None
    for lag, periods in grid_metrics.items():
        targets = (periods.get("full_period") or {}).get("T+20", {})
        for target_label, metrics in targets.items():
            if int(metrics.get("n") or 0) <= 0:
                continue
            candidate = _t20_close_fallback_candidate(lag, target_label, metrics)
            if best is None or _t20_close_fallback_candidate_key(candidate) > _t20_close_fallback_candidate_key(best):
                best = candidate
    return best


def aggregate_t20_close_fallback_metrics(
    panel: pd.DataFrame,
    diagnostics: Mapping[str, Any] | None = None,
    *,
    target_pcts: tuple[int, ...] = GRID_TARGET_PCTS,
) -> dict[str, Any]:
    periods = _periods(panel)
    parent_crosses = int((diagnostics or {}).get("parent_crosses", 0))
    lag_summary: dict[str, Any] = {}
    grid_metrics: dict[str, Any] = {}
    for lag in LAGS:
        rows = _lag_rows(panel, lag, None)
        lag_summary[str(lag)] = {
            "events": int(len(rows)),
            "retention_vs_parent_crosses": float(len(rows) / parent_crosses) if parent_crosses else 0.0,
            "signal_dates": int(rows["signal_date"].nunique()) if len(rows) else 0,
            "entry_dates": int(rows["entry_date"].nunique()) if len(rows) else 0,
            "codes": int(rows["code"].nunique()) if len(rows) else 0,
            "status_counts": {str(key): int(value) for key, value in rows.get("status", pd.Series(dtype=object)).value_counts().items()},
        }
        grid_metrics[str(lag)] = {}
        for period, bounds in periods.items():
            period_rows = _lag_rows(panel, lag, bounds)
            grid_metrics[str(lag)][period] = {"T+20": _t20_close_fallback_metrics_for_targets(period_rows, target_pcts)}
    return {"periods": list(periods), "lag_summary": lag_summary, "grid_metrics": grid_metrics}


def build_t20_close_fallback_report(
    *,
    panel: pd.DataFrame,
    diagnostics: Mapping[str, Any],
    code_list: list[str],
    code_list_sha256: str,
    start_date: str,
    end_date: str | None,
    workers: int,
    target_pcts: tuple[int, ...] = GRID_TARGET_PCTS,
) -> dict[str, Any]:
    aggregated = aggregate_t20_close_fallback_metrics(panel, diagnostics, target_pcts=target_pcts)
    observed_start = panel["cross_date"].min() if len(panel) else pd.NaT
    observed_end = panel["cross_date"].max() if len(panel) else pd.NaT
    return {
        "schema_version": T20_CLOSE_FALLBACK_SCHEMA_VERSION,
        "study": "mkf_post_cross_lag0_to_lag7_t20_close_fallback_return_grid",
        "research_only": True,
        "production_enabled": False,
        "watchlist_modified": False,
        "smc_admission_modified": False,
        "broker_orders_enabled": False,
        "ai_review_called": False,
        "thresholds_tuned": False,
        "original_mkf_selector_modified": False,
        "grid": {"lags": list(LAGS), "horizon": "T+20", "target_pcts": list(target_pcts)},
        "candidate_definition": {
            "parent_cross": "mkf_red_blue_cross20_green_exit_under80_mask",
            "lag_signal": "lag0..7 stock-tradable rows from parent cross, evaluated as independent cohorts",
            "hard_gate": "production_gate_mask applied at each lag signal row",
            "suspension_handling": "non-tradable rows do not consume lag or horizon windows",
        },
        "entry_definition": {
            "entry": "next stock-tradable open after lag signal close",
            "target_price": "entry_open * (1 + target_pct / 100)",
            "target_hit": "any high from T+1 through T+20 sellable stock-tradable days after entry reaches target_price",
            "hit_return": "target_pct / 100",
            "non_hit_return": "T+20 close / entry_open - 1",
            "ranking": "highest mean_realized_return",
            "entry_day_high": "excluded because newly bought A-share positions are not same-day sellable",
            "fees_slippage_tax_fillability": "not modeled",
        },
        "sample": {
            "method": "all_current_main_board_sorted_code",
            "codes": len(code_list),
            "code_list": code_list,
            "code_list_sha256": code_list_sha256,
            "parent_crosses": int(diagnostics.get("parent_crosses", 0)),
            "lag_events": int(len(panel)),
            "event_lag_counts": {str(lag): int((panel.get("post_cross_lag", pd.Series(dtype=int)) == lag).sum()) for lag in LAGS},
            "status_counts": {str(key): int(value) for key, value in panel.get("status", pd.Series(dtype=object)).value_counts().items()},
        },
        "event_diagnostics": {str(key): int(value) for key, value in diagnostics.items()},
        "date_range": {
            "start_date": start_date,
            "end_date": end_date,
            "observed_cross_start": observed_start.strftime("%Y-%m-%d") if pd.notna(observed_start) else None,
            "observed_cross_end": observed_end.strftime("%Y-%m-%d") if pd.notna(observed_end) else None,
        },
        "workers": workers,
        **aggregated,
        "best_point_readout": {
            "method": "Rank by realized return: target_pct/100 if target is hit by T+20, otherwise T+20 close / entry_open - 1.",
            "best_by_mean_realized_return": _best_t20_close_fallback_cell(aggregated["grid_metrics"]),
        },
        "limitations": [
            "Adjusted current-vintage local bars and current-file survivorship remain limitations.",
            "T+20 close fallback is user-defined for this study; fees, slippage, tax, sizing, stop loss, and fillability are not modeled.",
            "This is descriptive research, not real P&L or a production rule.",
            "No production selector behavior was changed.",
        ],
    }


def t20_close_fallback_summary_csv_rows(report: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for lag, periods in report["grid_metrics"].items():
        for period, horizons in periods.items():
            targets = horizons["T+20"]
            for target_label, metrics in targets.items():
                rows.append({
                    "lag": lag,
                    "period": period,
                    "horizon": "T+20",
                    "target_pct": _parse_target_pct(target_label),
                    "target_label": target_label,
                    "n": metrics.get("n"),
                    "target_hits": metrics.get("target_hits"),
                    "target_hit_rate": metrics.get("target_hit_rate"),
                    "target_hit_wilson_lower_95": metrics.get("target_hit_wilson_lower_95"),
                    "target_hit_wilson_upper_95": metrics.get("target_hit_wilson_upper_95"),
                    "mean_realized_return": metrics.get("mean_realized_return"),
                    "median_realized_return": metrics.get("median_realized_return"),
                    "entry_dates": metrics.get("entry_dates"),
                    "codes": metrics.get("codes"),
                    "events": report["lag_summary"].get(lag, {}).get("events"),
                    "retention_vs_parent_crosses": report["lag_summary"].get(lag, {}).get("retention_vs_parent_crosses"),
                })
    return rows


def lag_target_grid_summary_csv_rows(report: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for lag, periods in report["grid_metrics"].items():
        for period, horizons in periods.items():
            for horizon, targets in horizons.items():
                for target_label, metrics in targets.items():
                    target_pct = _parse_target_pct(target_label)
                    rows.append({
                        "lag": lag,
                        "period": period,
                        "horizon": horizon,
                        "target_pct": target_pct,
                        "target_label": target_label,
                        "n": metrics.get("n"),
                        "target_hits": metrics.get("target_hits"),
                        "target_hit_rate": metrics.get("target_hit_rate"),
                        "target_hit_wilson_lower_95": metrics.get("target_hit_wilson_lower_95"),
                        "target_hit_wilson_upper_95": metrics.get("target_hit_wilson_upper_95"),
                        "mean_target_zero_return": metrics.get("mean_target_zero_return"),
                        "entry_dates": metrics.get("entry_dates"),
                        "codes": metrics.get("codes"),
                        "events": report["lag_summary"].get(lag, {}).get("events"),
                        "retention_vs_parent_crosses": report["lag_summary"].get(lag, {}).get("retention_vs_parent_crosses"),
                    })
    return rows
