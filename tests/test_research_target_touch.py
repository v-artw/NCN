from __future__ import annotations

import pandas as pd

from ashare_edge_scout.research_target_touch import aggregate_target_touch, evaluate_stability, stock_target_outcomes
from ashare_edge_scout.research_v2 import summarize_counts


def _frame() -> pd.DataFrame:
    return pd.DataFrame({
        "date": pd.bdate_range("2025-01-01", periods=8),
        "open": [100.0] * 8,
        "high": [101.0] * 8,
        "tradestatus": ["1"] * 8,
    })


def test_t_high_is_excluded_and_exact_target_counts() -> None:
    frame = _frame()
    frame.loc[1, "high"] = 110.0
    frame.loc[3, "high"] = 103.0
    row = stock_target_outcomes(frame)[pd.Timestamp("2025-01-01")]
    assert row["entry_date"] == frame.loc[1, "date"]
    assert row["target_touched"] is True
    assert row["first_touch_day"] == 2


def test_suspensions_do_not_consume_entry_or_five_day_window() -> None:
    frame = pd.DataFrame({
        "date": pd.bdate_range("2025-01-01", periods=10),
        "open": [100.0] * 10,
        "high": [101.0] * 10,
        "tradestatus": ["1", "0", "1", "0", "1", "1", "1", "1", "1", "1"],
    })
    frame.loc[1, "open"] = 1.0
    frame.loc[3, "high"] = 200.0
    frame.loc[8, "high"] = 103.0
    row = stock_target_outcomes(frame)[pd.Timestamp("2025-01-01")]
    assert row["entry_date"] == frame.loc[2, "date"]
    assert row["first_touch_day"] == 5


def test_fewer_than_five_post_entry_tradable_rows_is_pending() -> None:
    row = stock_target_outcomes(_frame().iloc[:6])[pd.Timestamp("2025-01-01")]
    assert row["status"] == "pending"


def test_stability_requires_lift_and_wilson_separation() -> None:
    def metric(rate: float, baseline: float) -> dict[str, object]:
        value = summarize_counts(1000, round(1000 * rate))
        value["win_rate"] = value.pop("precision")
        value.update({
            "entry_dates": 200,
            "codes": 100,
            "same_entry_date_baseline": {"win_rate": baseline},
            "win_rate_lift": rate - baseline,
        })
        return value

    metrics = {
        "selection_2021_2023": metric(0.65, 0.55),
        "audit_2024_present": metric(0.65, 0.55),
        **{f"year_{year}": metric(0.65, 0.55) for year in range(2021, 2027)},
    }
    assert evaluate_stability(metrics, 2026)["passed"] is True
    metrics["audit_2024_present"] = metric(0.56, 0.55)
    assert evaluate_stability(metrics, 2026)["passed"] is False


def test_coverage_reports_pending_candidates_before_baseline_date_filter() -> None:
    rows = []
    for index in range(150):
        rows.append({
            "code": f"sh.{600000 + index}",
            "signal_date": pd.Timestamp("2025-01-01"),
            "entry_date": pd.Timestamp("2025-01-02"),
            "admitted": True,
            "selected": index == 0,
            "status": "mature",
            "target_touched": index % 2 == 0,
        })
    rows.append({
        "code": "sh.600999",
        "signal_date": pd.Timestamp("2025-01-03"),
        "entry_date": pd.Timestamp("2025-01-06"),
        "admitted": True,
        "selected": True,
        "status": "pending",
        "target_touched": pd.NA,
    })
    result = aggregate_target_touch(pd.DataFrame(rows))
    assert result["candidate_status_counts"] == {"mature": 1, "pending": 1}
    assert result["mature_candidates_on_valid_baseline_dates"] == 1
