"""T-open anchored T+1..T+5 plus-3% target-touch classification."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np
import pandas as pd

from .research_nextday_validation import candidate_masks
from .research_precision70 import production_gate_mask
from .research_v2 import summarize_counts

SCHEMA_VERSION = "ncn_t_open_plus3_five_day_win_rate_v1"
MIN_BASELINE_ROWS = 150


def stock_target_outcomes(data: pd.DataFrame) -> dict[pd.Timestamp, dict[str, Any]]:
    """Map each T-1 origin to its T-open anchored five-tradable-day outcome."""

    trade = data.get("tradestatus", pd.Series(index=data.index, dtype=object)).astype("string")
    indices = np.flatnonzero(trade.eq("1").fillna(False).to_numpy())
    dates = pd.to_datetime(data["date"], errors="coerce").to_numpy()
    opens = pd.to_numeric(data.get("open"), errors="coerce").to_numpy(dtype=float)
    highs = pd.to_numeric(data.get("high"), errors="coerce").to_numpy(dtype=float)
    positions = {int(index): position for position, index in enumerate(indices)}
    outcomes: dict[pd.Timestamp, dict[str, Any]] = {}
    for origin in range(len(data)):
        origin_date = pd.Timestamp(dates[origin])
        position = positions.get(origin)
        row: dict[str, Any] = {"status": "origin_invalid", "entry_date": pd.NaT}
        if position is None or position + 1 >= len(indices):
            outcomes[origin_date] = row
            continue
        entry = int(indices[position + 1])
        entry_open = opens[entry]
        row["entry_date"] = pd.Timestamp(dates[entry])
        if not np.isfinite(entry_open) or entry_open <= 0:
            row["status"] = "entry_invalid"
            outcomes[origin_date] = row
            continue
        eligible = indices[position + 2:position + 7]
        if len(eligible) < 5:
            row.update({"status": "pending", "entry_open": float(entry_open)})
            outcomes[origin_date] = row
            continue
        window_highs = highs[eligible]
        if not np.isfinite(window_highs).all():
            row.update({"status": "path_invalid", "entry_open": float(entry_open)})
            outcomes[origin_date] = row
            continue
        target_price = float(entry_open * 1.03)
        touched = window_highs >= target_price
        first_touch = int(np.argmax(touched)) + 1 if bool(touched.any()) else None
        row.update({
            "status": "mature",
            "entry_open": float(entry_open),
            "target_price": target_price,
            "target_touched": bool(touched.any()),
            "first_touch_day": first_touch,
            "max_high": float(window_highs.max()),
            "max_excursion": float(window_highs.max() / entry_open - 1.0),
        })
        outcomes[origin_date] = row
    return outcomes


def build_target_touch_panel(
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
    masks = candidate_masks(data)
    selected = data["date"].ge(pd.Timestamp(start_date))
    if end_date is not None:
        selected &= data["date"].le(pd.Timestamp(end_date))
    panel = pd.DataFrame({
        "code": code,
        "signal_date": data["date"],
        "admitted": production_gate_mask(code, data, config),
        "selected": masks["smc_medium_buy"],
    }).loc[selected].reset_index(drop=True)
    outcomes = stock_target_outcomes(data)
    rows = panel["signal_date"].map(outcomes)
    panel["entry_date"] = pd.to_datetime(rows.map(lambda value: value.get("entry_date", pd.NaT)))
    panel["status"] = rows.map(lambda value: value.get("status", "missing"))
    for field in ("entry_open", "target_price", "max_high", "max_excursion", "first_touch_day"):
        panel[field] = pd.to_numeric(rows.map(lambda value, key=field: value.get(key, np.nan)), errors="coerce")
    panel["target_touched"] = pd.array(rows.map(lambda value: value.get("target_touched", pd.NA)), dtype="boolean")
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
    result["win_rate_lift"] = None if result["precision"] is None or baseline_rate is None else result["precision"] - baseline_rate
    result["win_rate"] = result.pop("precision")
    return result


def aggregate_target_touch(panel: pd.DataFrame) -> dict[str, Any]:
    mature_admitted = panel.loc[panel["admitted"].fillna(False) & panel["status"].eq("mature") & panel["target_touched"].notna()].copy()
    day_counts = mature_admitted.groupby("entry_date").size()
    valid_dates = set(day_counts[day_counts.ge(MIN_BASELINE_ROWS)].index)
    baseline = mature_admitted.loc[mature_admitted["entry_date"].isin(valid_dates)]
    all_candidates = panel.loc[panel["selected"].fillna(False) & panel["admitted"].fillna(False)]
    candidates = all_candidates.loc[all_candidates["entry_date"].isin(valid_dates)]
    mature_candidates = candidates.loc[candidates["status"].eq("mature")]
    years = sorted(int(year) for year in mature_candidates["entry_date"].dropna().dt.year.unique())
    periods = {
        "full_2021_present": (2021, max(years)),
        "selection_2021_2023": (2021, 2023),
        "audit_2024_present": (2024, max(years)),
        **{f"year_{year}": (year, year) for year in years},
    }
    metrics = {
        name: _summary(
            mature_candidates.loc[mature_candidates["entry_date"].dt.year.between(first, last)],
            baseline.loc[baseline["entry_date"].dt.year.between(first, last)],
        )
        for name, (first, last) in periods.items()
    }
    status_counts = {str(key): int(value) for key, value in all_candidates["status"].value_counts(dropna=False).sort_index().items()}
    return {
        "periods": periods,
        "metrics": metrics,
        "candidate_status_counts": status_counts,
        "mature_candidates_on_valid_baseline_dates": int(len(mature_candidates)),
        "excluded_mature_candidates_on_thin_baseline_dates": int(
            (all_candidates["status"].eq("mature") & ~all_candidates["entry_date"].isin(valid_dates)).sum()
        ),
    }


def evaluate_stability(metrics: Mapping[str, Mapping[str, Any]], last_year: int) -> dict[str, Any]:
    failures: list[str] = []
    for period in ("selection_2021_2023", "audit_2024_present"):
        cell = metrics[period]
        baseline = cell["same_entry_date_baseline"]["win_rate"]
        if int(cell["n"]) < 300:
            failures.append(f"{period}:n_below_300")
        if int(cell["entry_dates"]) < 120:
            failures.append(f"{period}:entry_dates_below_120")
        if int(cell["codes"]) < 50:
            failures.append(f"{period}:codes_below_50")
        if cell["win_rate_lift"] is None or cell["win_rate_lift"] < 0.03:
            failures.append(f"{period}:win_rate_lift_below_0.03")
        if cell["wilson_lower_95"] is None or baseline is None or cell["wilson_lower_95"] <= baseline:
            failures.append(f"{period}:wilson_lower_not_above_baseline")
    for year in range(2021, last_year):
        cell = metrics.get(f"year_{year}")
        if cell is None or cell["win_rate_lift"] is None or cell["win_rate_lift"] <= 0:
            failures.append(f"year_{year}:win_rate_lift_not_positive")
    return {"passed": not failures, "failure_codes": failures}


def build_report(*, panel: pd.DataFrame, code_list: list[str], code_list_sha256: str, start_date: str, end_date: str | None, workers: int) -> dict[str, Any]:
    aggregated = aggregate_target_touch(panel)
    years = [value[0] for key, value in aggregated["periods"].items() if key.startswith("year_")]
    decision = evaluate_stability(aggregated["metrics"], max(years))
    return {
        "schema_version": SCHEMA_VERSION,
        "study": "t_open_plus3_t_plus_1_through_t_plus_5_win_rate",
        "research_only": True,
        "classification_only": True,
        "production_enabled": False,
        "alignment": {
            "signal": "T-1 close using T-1-visible rows only",
            "entry_reference": "next stock-tradable T open",
            "target": "T open * 1.03",
            "eligible_window": "T+1 through T+5 stock-tradable rows; T high excluded",
            "win": "any eligible daily high >= target",
            "loss": "all five eligible daily highs < target",
        },
        "sample": {"method": "all_current_main_board_sorted_code", "codes": len(code_list), "code_list": code_list, "code_list_sha256": code_list_sha256},
        "date_range": {"start_date": start_date, "end_date": end_date},
        "workers": workers,
        "decision": decision,
        **aggregated,
        "limitations": [
            "Target touch is not proof that a queued limit sell filled.",
            "T open is a reference observation, not proof of a buy fill.",
            "No fees, tax, slippage, T+5 fallback exit, return, or P&L is modeled.",
            "Adjusted current-vintage bars and current-file survivorship remain limitations.",
        ],
    }
