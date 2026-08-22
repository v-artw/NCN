"""Point-in-time CNInfo risk-disclosure exclusion research primitives."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np
import pandas as pd

from .research_precision70 import nonoverlapping_origins
from .research_v2 import summarize_counts


PERIODS = {
    "selection_2023_2024": (2023, 2024),
    "holdout_2025_2026": (2025, 2026),
}


def risk_disclosure_mask(
    dates: Sequence[Any], tradestatus: Sequence[Any], announcement_timestamps_ms: Sequence[Any]
) -> pd.Series:
    """Flag the first 10 tradable dates after each provider calendar date."""

    date_values = pd.to_datetime(pd.Series(dates), errors="coerce").dt.normalize()
    trading = pd.Series(tradestatus).astype("string").eq("1").fillna(False)
    flagged = np.zeros(len(date_values), dtype=bool)
    trading_indices = np.flatnonzero(trading.to_numpy())
    trading_dates = date_values.iloc[trading_indices].to_numpy(dtype="datetime64[ns]")
    for raw_timestamp in announcement_timestamps_ms:
        try:
            timestamp = pd.to_datetime(raw_timestamp, unit="ms", utc=True).tz_convert("Asia/Shanghai")
        except (TypeError, ValueError, OverflowError):
            continue
        if pd.isna(timestamp):
            continue
        calendar_date = np.datetime64(timestamp.tz_localize(None).normalize())
        availability = int(np.searchsorted(trading_dates, calendar_date, side="right"))
        for position in trading_indices[availability:availability + 10]:
            flagged[position] = True
    return pd.Series(flagged, index=date_values.index, dtype=bool)


def apply_risk_events(panel: pd.DataFrame, events: Mapping[str, Sequence[Any]]) -> pd.DataFrame:
    """Attach frozen risk windows to each stock panel."""

    pieces: list[pd.DataFrame] = []
    for code, rows in panel.groupby("code", sort=True):
        stock = rows.sort_values("date", kind="stable").copy()
        synthetic_trade = np.where(stock["trading_index"].notna(), "1", "0")
        stock["recent_risk_disclosure"] = risk_disclosure_mask(
            stock["date"], synthetic_trade, events.get(str(code), ())
        ).to_numpy()
        pieces.append(stock)
    if not pieces:
        result = panel.copy()
        result["recent_risk_disclosure"] = pd.Series(dtype=bool)
        return result
    return pd.concat(pieces, ignore_index=True).sort_values(["date", "code"], kind="stable").reset_index(drop=True)


def _summary(rows: pd.DataFrame) -> dict[str, Any]:
    mature = rows.loc[rows["label"].notna()]
    result = summarize_counts(len(mature), int(mature["label"].astype(bool).sum()))
    result["signal_dates"] = int(mature["date"].nunique())
    return result


def aggregate_risk_metrics(panel: pd.DataFrame) -> tuple[dict[str, Any], dict[str, Any]]:
    """Summarize same-coverage MHPG baseline and the fixed exclusion."""

    baseline = panel["admitted"].fillna(False) & panel["mhpg_buy"].fillna(False)
    candidate = baseline & ~panel["recent_risk_disclosure"].fillna(False)
    summaries: dict[str, Any] = {}
    for name, mask in {"mhpg_baseline": baseline, "risk_exclusion": candidate}.items():
        rows = panel.loc[mask]
        summaries[name] = {
            period: _summary(rows.loc[rows["date"].dt.year.between(first, last)])
            for period, (first, last) in PERIODS.items()
        }
        for year in range(2023, 2027):
            summaries[name][f"year_{year}"] = _summary(rows.loc[rows["date"].dt.year.eq(year)])
    spaced = nonoverlapping_origins(panel.loc[candidate])
    sensitivity = {
        period: _summary(spaced.loc[spaced["date"].dt.year.between(first, last)])
        for period, (first, last) in PERIODS.items()
    }
    return summaries, sensitivity


def evaluate_risk_decision(summaries: Mapping[str, Any], sensitivity: Mapping[str, Any]) -> dict[str, Any]:
    """Apply frozen selection and holdout gates without threshold tuning."""

    failures: dict[str, list[str]] = {}
    for period, years in (("selection_2023_2024", (2023, 2024)), ("holdout_2025_2026", (2025, 2026))):
        candidate = summaries["risk_exclusion"][period]
        baseline = summaries["mhpg_baseline"][period]
        codes: list[str] = []
        if candidate["precision"] is None or candidate["precision"] < 0.70:
            codes.append("precision_below_0.70")
        if int(candidate["n"]) < 300:
            codes.append("n_below_300")
        for year in years:
            minimum = 25 if year == 2026 else 50
            if int(summaries["risk_exclusion"][f"year_{year}"]["n"]) < minimum:
                codes.append(f"year_{year}_n_below_{minimum}")
        if candidate["wilson_lower_95"] is None or candidate["wilson_lower_95"] < 0.60:
            codes.append("wilson_lower_below_0.60")
        if candidate["precision"] is None or baseline["precision"] is None or candidate["precision"] - baseline["precision"] < 0.03:
            codes.append("precision_lift_below_0.03")
        baseline_fpr = baseline["fpr"]
        candidate_fpr = candidate["fpr"]
        reduction = None if baseline_fpr in (None, 0) or candidate_fpr is None else (baseline_fpr - candidate_fpr) / baseline_fpr
        if reduction is None or reduction < 0.20:
            codes.append("relative_fpr_reduction_below_0.20")
        if period == "holdout_2025_2026":
            nonoverlap = sensitivity[period]
            if nonoverlap["precision"] is None or nonoverlap["precision"] < 0.70:
                codes.append("nonoverlap_precision_below_0.70")
        failures[period] = codes
    return {
        "selection_failure_codes": failures["selection_2023_2024"],
        "holdout_audit_only_unless_selection_passes": bool(failures["selection_2023_2024"]),
        "holdout_failure_codes": failures["holdout_2025_2026"],
        "stage1_passed": not any(failures.values()),
    }
