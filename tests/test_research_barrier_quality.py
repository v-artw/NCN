from __future__ import annotations

import pandas as pd

from ashare_edge_scout.research_barrier_quality import (
    _stock_outcomes,
    evaluate_barrier_quality,
    first_touch_state,
)
from ashare_edge_scout.research_v2 import summarize_counts


def test_first_touch_states_are_ordered_and_ambiguous() -> None:
    assert first_touch_state([104, 100], [99, 96], 100, 0.03, 0.03) == "target_first"
    assert first_touch_state([101, 104], [96, 99], 100, 0.03, 0.03) == "risk_first"
    assert first_touch_state([104], [96], 100, 0.03, 0.03) == "same_day_ambiguous"
    assert first_touch_state([102], [98], 100, 0.03, 0.03) == "neither"


def _frame() -> pd.DataFrame:
    closes = [100.0] * 13
    return pd.DataFrame({
        "date": pd.bdate_range("2025-01-01", periods=len(closes)),
        "open": closes, "high": [101.0] * len(closes), "low": [99.0] * len(closes), "close": closes,
        "tradestatus": ["1"] * len(closes),
    })


def test_entry_day_is_excluded_and_d_plus_one_starts_window() -> None:
    frame = _frame()
    frame.loc[1, "high"] = 110.0
    frame.loc[2, "high"] = 104.0
    row = _stock_outcomes(frame)[pd.Timestamp("2025-01-01")]
    assert row["entry_date"] == frame.loc[1, "date"]
    assert row["entry_day_touch_5pct"] is True
    assert row["target3_risk3_5d"] == "target_first"


def test_suspension_is_skipped_for_entry_and_exit_window() -> None:
    frame = _frame()
    frame.loc[1, "tradestatus"] = "0"
    frame.loc[1, "open"] = 1.0
    frame.loc[3, "tradestatus"] = "0"
    frame.loc[3, "low"] = 1.0
    frame.loc[4, "high"] = 104.0
    row = _stock_outcomes(frame)[pd.Timestamp("2025-01-01")]
    assert row["entry_date"] == frame.loc[2, "date"]
    assert row["target3_risk3_5d"] == "target_first"


def test_exact_barriers_count_as_touched() -> None:
    assert first_touch_state([103.0], [99.0], 100.0, 0.03, 0.03) == "target_first"
    assert first_touch_state([101.0], [97.0], 100.0, 0.03, 0.03) == "risk_first"


def test_quality_gate_requires_target_lift_without_risk_increase() -> None:
    def year_cell(target_rate: float, target_base: float, risk_rate: float, risk_base: float) -> dict:
        n = 400
        target = summarize_counts(n, round(n * target_rate))
        target.update({"same_entry_date_baseline": {"weighted_n": n, "weighted_hits": n * target_base, "rate": target_base}, "rate_lift": target_rate - target_base})
        risk = summarize_counts(n, round(n * risk_rate))
        risk.update({"same_entry_date_baseline": {"weighted_n": n, "weighted_hits": n * risk_base, "rate": risk_base}, "rate_lift": risk_rate - risk_base})
        return {"barriers": {"target3_risk3": {"n": n, "states": {"target_first": target["hits"], "risk_first": risk["hits"], "same_day_ambiguous": 0, "neither": 0}, "entry_dates": 130, "target_first": target, "risk_first": risk}}}

    metrics = {f"year_{year}": year_cell(0.60, 0.50, 0.20, 0.25) for year in range(2021, 2027)}
    assert evaluate_barrier_quality(metrics, barrier="target3_risk3", last_year=2026)["passed"]
    for year in range(2024, 2027):
        metrics[f"year_{year}"] = year_cell(0.60, 0.50, 0.30, 0.25)
    assert not evaluate_barrier_quality(metrics, barrier="target3_risk3", last_year=2026)["passed"]
