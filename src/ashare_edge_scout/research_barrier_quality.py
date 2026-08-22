"""D-open anchored, A-share T+1-aware barrier path quality research."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np
import pandas as pd

from .research_nextday_validation import candidate_masks
from .research_precision70 import production_gate_mask
from .research_v2 import summarize_counts

SCHEMA_VERSION = "ncn_d_open_t1_barrier_quality_v1"
DEFAULT_START_DATE = "1900-01-01"
CANDIDATES = ("smc_medium_buy", "smc_bull_bos", "kdj_trend_pro_buy")
HORIZONS = (5, 10)
BARRIERS = {"target3_risk3": (0.03, 0.03), "target5_risk5": (0.05, 0.05)}
MIN_BASELINE_ROWS = 150
PATH_STATES = ("target_first", "risk_first", "same_day_ambiguous", "neither")


def first_touch_state(
    highs: Sequence[float],
    lows: Sequence[float],
    reference: float,
    target: float,
    risk: float,
) -> str:
    for high, low in zip(highs, lows, strict=True):
        target_touched = float(high) >= reference * (1.0 + target)
        risk_touched = float(low) <= reference * (1.0 - risk)
        if target_touched and risk_touched:
            return "same_day_ambiguous"
        if target_touched:
            return "target_first"
        if risk_touched:
            return "risk_first"
    return "neither"


def _stock_outcomes(data: pd.DataFrame) -> dict[pd.Timestamp, dict[str, Any]]:
    trade = data.get("tradestatus", pd.Series(index=data.index, dtype=object)).astype("string")
    indices = np.flatnonzero(trade.eq("1").fillna(False).to_numpy())
    dates = pd.to_datetime(data["date"], errors="coerce").to_numpy()
    open_ = pd.to_numeric(data.get("open"), errors="coerce").to_numpy(dtype=float)
    high = pd.to_numeric(data.get("high"), errors="coerce").to_numpy(dtype=float)
    low = pd.to_numeric(data.get("low"), errors="coerce").to_numpy(dtype=float)
    close = pd.to_numeric(data.get("close"), errors="coerce").to_numpy(dtype=float)
    positions = {int(index): position for position, index in enumerate(indices)}
    outcomes: dict[pd.Timestamp, dict[str, Any]] = {}
    for origin in range(len(data)):
        origin_date = pd.Timestamp(dates[origin])
        position = positions.get(origin)
        row: dict[str, Any] = {"status": "origin_invalid", "entry_date": pd.NaT}
        if position is None or position + 1 >= len(indices) or not np.isfinite(close[origin]) or close[origin] <= 0:
            outcomes[origin_date] = row
            continue
        entry = int(indices[position + 1])
        entry_open = open_[entry]
        if not np.isfinite(entry_open) or entry_open <= 0:
            row["status"] = "entry_invalid"
            row["entry_date"] = pd.Timestamp(dates[entry])
            outcomes[origin_date] = row
            continue
        eligible = indices[position + 2:position + 12]
        row.update({
            "status": "mature" if len(eligible) >= 10 else "partial",
            "entry_date": pd.Timestamp(dates[entry]),
            "entry_open": float(entry_open),
            "entry_gap": float(entry_open / close[origin] - 1.0),
            "entry_day_touch_3pct": bool(np.isfinite(high[entry]) and high[entry] >= entry_open * 1.03),
            "entry_day_touch_5pct": bool(np.isfinite(high[entry]) and high[entry] >= entry_open * 1.05),
        })
        for horizon in HORIZONS:
            if len(eligible) < horizon:
                row[f"status_{horizon}d"] = "pending"
                continue
            window = eligible[:horizon]
            highs, lows = high[window], low[window]
            if not np.isfinite(highs).all() or not np.isfinite(lows).all():
                row[f"status_{horizon}d"] = "invalid"
                continue
            row[f"status_{horizon}d"] = "mature"
            row[f"mfe_{horizon}d"] = float(highs.max() / entry_open - 1.0)
            row[f"mae_{horizon}d"] = float(lows.min() / entry_open - 1.0)
            for name, (target, risk) in BARRIERS.items():
                row[f"{name}_{horizon}d"] = first_touch_state(highs, lows, entry_open, target, risk)
        outcomes[origin_date] = row
    return outcomes


def build_barrier_panel(
    code: str,
    frame: pd.DataFrame,
    config: Mapping[str, Any],
    *,
    start_date: str = DEFAULT_START_DATE,
    end_date: str | None = None,
) -> pd.DataFrame:
    data = frame.copy()
    data["date"] = pd.to_datetime(data.get("date"), errors="coerce").dt.normalize()
    data = data.dropna(subset=["date"]).sort_values("date", kind="stable").drop_duplicates("date", keep="last").reset_index(drop=True)
    masks = candidate_masks(data)
    selected = data["date"].ge(pd.Timestamp(start_date))
    if end_date is not None:
        selected &= data["date"].le(pd.Timestamp(end_date))
    panel = pd.DataFrame({
        "code": code,
        "origin_date": data["date"],
        "admitted": production_gate_mask(code, data, config),
    }).loc[selected].reset_index(drop=True)
    for name in CANDIDATES:
        panel[name] = panel["origin_date"].map(dict(zip(data["date"], masks[name], strict=True))).fillna(False).astype(bool)
    outcomes = _stock_outcomes(data)
    rows = panel["origin_date"].map(outcomes)
    panel["entry_date"] = pd.to_datetime(rows.map(lambda value: value.get("entry_date", pd.NaT)))
    for field in ("entry_gap", "entry_open"):
        panel[field] = pd.to_numeric(rows.map(lambda value, key=field: value.get(key, np.nan)), errors="coerce")
    for field in ("entry_day_touch_3pct", "entry_day_touch_5pct"):
        panel[field] = pd.array(rows.map(lambda value, key=field: value.get(key, pd.NA)), dtype="boolean")
    for horizon in HORIZONS:
        panel[f"status_{horizon}d"] = rows.map(lambda value, h=horizon: value.get(f"status_{h}d", "missing"))
        for field in ("mfe", "mae"):
            panel[f"{field}_{horizon}d"] = pd.to_numeric(rows.map(lambda value, h=horizon, key=field: value.get(f"{key}_{h}d", np.nan)), errors="coerce")
        for barrier in BARRIERS:
            panel[f"{barrier}_{horizon}d"] = rows.map(lambda value, h=horizon, key=barrier: value.get(f"{key}_{h}d", pd.NA))
    return panel


def _periods(panel: pd.DataFrame) -> dict[str, tuple[int, int]]:
    years = sorted(int(year) for year in panel["entry_date"].dropna().dt.year.unique())
    return {"full_available_history": (years[0], years[-1]), **{f"year_{year}": (year, year) for year in years}}


def _state_summary(signal: pd.DataFrame, baseline: pd.DataFrame, state_column: str) -> dict[str, Any]:
    rows = signal.loc[signal[state_column].notna()]
    counts = {state: int(rows[state_column].eq(state).sum()) for state in PATH_STATES}
    result: dict[str, Any] = {"n": len(rows), "states": counts, "entry_dates": int(rows["entry_date"].nunique()), "codes": int(rows["code"].nunique())}
    for state in PATH_STATES:
        hits = counts[state]
        cell = summarize_counts(len(rows), hits)
        by_signal_date = rows.groupby("entry_date").size()
        by_date = baseline.loc[baseline["entry_date"].isin(by_signal_date.index)].assign(hit=baseline[state_column].eq(state)).groupby("entry_date")["hit"].agg(["count", "sum"])
        weights = by_signal_date.reindex(by_date.index).astype(float)
        weighted_n = int(weights.sum())
        weighted_hits = float((weights * by_date["sum"].div(by_date["count"])).sum()) if weighted_n else 0.0
        baseline_rate = weighted_hits / weighted_n if weighted_n else None
        cell["same_entry_date_baseline"] = {"weighted_n": weighted_n, "weighted_hits": weighted_hits, "rate": baseline_rate}
        cell["rate_lift"] = None if cell["precision"] is None or baseline_rate is None else cell["precision"] - baseline_rate
        result[state] = cell
    return result


def _quantiles(rows: pd.DataFrame, column: str) -> dict[str, float | None]:
    values = pd.to_numeric(rows[column], errors="coerce").dropna()
    return {str(q): (float(values.quantile(q)) if len(values) else None) for q in (0.1, 0.25, 0.5, 0.75, 0.9)}


def aggregate_barrier_metrics(panel: pd.DataFrame) -> dict[str, Any]:
    periods = _periods(panel)
    metrics: dict[str, Any] = {}
    for horizon in HORIZONS:
        status = f"status_{horizon}d"
        mature = panel.loc[panel["admitted"].fillna(False) & panel[status].eq("mature")].copy()
        day_counts = mature.groupby("entry_date").size()
        baseline = mature.loc[mature["entry_date"].isin(set(day_counts[day_counts.ge(MIN_BASELINE_ROWS)].index))]
        metrics[f"{horizon}d"] = {}
        for candidate in CANDIDATES:
            usable = panel.loc[panel[candidate] & panel["admitted"].fillna(False) & panel[status].eq("mature") & panel["entry_date"].isin(baseline["entry_date"])]
            metrics[f"{horizon}d"][candidate] = {}
            for period, (first, last) in periods.items():
                rows = usable.loc[usable["entry_date"].dt.year.between(first, last)]
                base = baseline.loc[baseline["entry_date"].dt.year.between(first, last)]
                metrics[f"{horizon}d"][candidate][period] = {
                    "barriers": {name: _state_summary(rows, base, f"{name}_{horizon}d") for name in BARRIERS},
                    "mfe_quantiles": _quantiles(rows, f"mfe_{horizon}d"),
                    "mae_quantiles": _quantiles(rows, f"mae_{horizon}d"),
                    "entry_gap_quantiles": _quantiles(rows, "entry_gap"),
                    "entry_day_touch_3pct_rate": float(rows["entry_day_touch_3pct"].mean()) if len(rows) else None,
                    "entry_day_touch_5pct_rate": float(rows["entry_day_touch_5pct"].mean()) if len(rows) else None,
                }
    extensions: dict[str, Any] = {}
    mature10 = panel.loc[panel["admitted"].fillna(False) & panel["status_10d"].eq("mature")]
    day_counts10 = mature10.groupby("entry_date").size()
    valid10 = set(day_counts10[day_counts10.ge(MIN_BASELINE_ROWS)].index)
    for candidate in CANDIDATES:
        rows = panel.loc[panel[candidate] & panel["admitted"].fillna(False) & panel["status_10d"].eq("mature") & panel["entry_date"].isin(valid10)]
        extensions[candidate] = {}
        for period, (first, last) in periods.items():
            selected = rows.loc[rows["entry_date"].dt.year.between(first, last)]
            extensions[candidate][period] = {}
            for barrier in BARRIERS:
                state5 = f"{barrier}_5d"
                state10 = f"{barrier}_10d"
                unresolved = selected.loc[selected[state5].eq("neither")]
                transitions = {
                    state: int(unresolved[state10].eq(state).sum()) for state in PATH_STATES
                }
                extensions[candidate][period][barrier] = {
                    "five_day_neither_n": int(len(unresolved)),
                    "ten_day_states": transitions,
                    "target_first_recovery_rate": (
                        transitions["target_first"] / len(unresolved) if len(unresolved) else None
                    ),
                }
    return {"periods": periods, "metrics": metrics, "five_to_ten_day_extension": extensions}


def _combine_years(
    metrics: Mapping[str, Mapping[str, Any]], years: range, barrier: str
) -> dict[str, Any]:
    cells = [metrics[f"year_{year}"]["barriers"][barrier] for year in years if f"year_{year}" in metrics]
    n = sum(int(cell["n"]) for cell in cells)
    states = {state: sum(int(cell["states"][state]) for cell in cells) for state in PATH_STATES}
    result: dict[str, Any] = {
        "n": n,
        "states": states,
        "entry_dates": sum(int(cell["entry_dates"]) for cell in cells),
    }
    for state in ("target_first", "risk_first"):
        cell = summarize_counts(n, states[state])
        baseline_n = sum(int(value[state]["same_entry_date_baseline"]["weighted_n"]) for value in cells)
        baseline_hits = sum(float(value[state]["same_entry_date_baseline"]["weighted_hits"]) for value in cells)
        baseline_rate = baseline_hits / baseline_n if baseline_n else None
        cell["same_entry_date_baseline"] = {
            "weighted_n": baseline_n,
            "weighted_hits": baseline_hits,
            "rate": baseline_rate,
        }
        cell["rate_lift"] = None if cell["precision"] is None or baseline_rate is None else cell["precision"] - baseline_rate
        result[state] = cell
    return result


def evaluate_barrier_quality(
    metrics: Mapping[str, Mapping[str, Any]], *, barrier: str, last_year: int
) -> dict[str, Any]:
    periods = {
        "selection_2021_2023": _combine_years(metrics, range(2021, 2024), barrier),
        "audit_2024_present": _combine_years(metrics, range(2024, last_year + 1), barrier),
    }
    failures: list[str] = []
    for period, cell in periods.items():
        target = cell["target_first"]
        risk = cell["risk_first"]
        target_baseline = target["same_entry_date_baseline"]["rate"]
        if int(cell["n"]) < 300:
            failures.append(f"{period}:n_below_300")
        if int(cell["entry_dates"]) < 120:
            failures.append(f"{period}:entry_dates_below_120")
        if target["rate_lift"] is None or target["rate_lift"] < 0.03:
            failures.append(f"{period}:target_first_lift_below_0.03")
        if target["wilson_lower_95"] is None or target_baseline is None or target["wilson_lower_95"] <= target_baseline:
            failures.append(f"{period}:target_wilson_lower_not_above_baseline")
        if risk["rate_lift"] is None or risk["rate_lift"] > 0:
            failures.append(f"{period}:risk_first_rate_increased")
    complete_audit_years = range(2024, last_year if last_year == 2026 else last_year + 1)
    for year in complete_audit_years:
        target = metrics.get(f"year_{year}", {}).get("barriers", {}).get(barrier, {}).get("target_first")
        if target is None or target["rate_lift"] is None or target["rate_lift"] <= 0:
            failures.append(f"year_{year}:target_first_lift_not_positive")
    return {"passed": not failures, "failure_codes": failures, "decision_periods": periods}


def build_barrier_report(*, panel: pd.DataFrame, code_list: list[str], code_list_sha256: str, start_date: str, end_date: str | None, workers: int) -> dict[str, Any]:
    aggregated = aggregate_barrier_metrics(panel)
    years = [value[0] for key, value in aggregated["periods"].items() if key.startswith("year_")]
    last_year = max(years)
    decisions = {
        horizon: {
            candidate: {
                barrier: evaluate_barrier_quality(candidate_metrics, barrier=barrier, last_year=last_year)
                for barrier in BARRIERS
            }
            for candidate, candidate_metrics in aggregated["metrics"][horizon].items()
        }
        for horizon in ("5d", "10d")
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "study": "d_open_t1_barrier_path_quality",
        "research_only": True,
        "classification_only": True,
        "production_enabled": False,
        "alignment": {
            "signal": "T-only signal",
            "reference": "next tradable D open",
            "eligible_observation": "D+1 through D+5/D+10 tradable rows due to A-share T+1",
            "same_day_dual_touch": "ambiguous; no favorable ordering assumed",
        },
        "barriers": {name: {"target": target, "risk": -risk} for name, (target, risk) in BARRIERS.items()},
        "candidates": list(CANDIDATES),
        "sample": {"method": "all_current_main_board_sorted_code", "codes": len(code_list), "code_list": code_list, "code_list_sha256": code_list_sha256},
        "date_range": {"start_date": start_date, "end_date": end_date},
        "workers": workers,
        "decision": {
            "gates": "Selection and audit require n>=300, >=120 entry dates, target-first lift >=3pp, target Wilson lower above baseline, no risk-first increase, and positive complete-audit-year target-first lift.",
            "by_horizon_candidate_barrier": decisions,
            "passed": {
                horizon: {
                    candidate: sorted(barrier for barrier, value in barriers.items() if value["passed"])
                    for candidate, barriers in candidates.items()
                }
                for horizon, candidates in decisions.items()
            },
        },
        **aggregated,
        "limitations": [
            "Daily OHLC cannot resolve intraday ordering when target and risk are touched on the same day.",
            "D open is a reference observation, not proof of an executable fill.",
            "Adjusted current-vintage data and current-file survivorship remain limitations.",
            "No orders, positions, allocation, costs, realized returns, or P&L are modeled.",
        ],
    }
