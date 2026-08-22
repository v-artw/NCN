from __future__ import annotations

import pandas as pd

from ashare_edge_scout.research_risk_disclosure import (
    evaluate_risk_decision,
    risk_disclosure_mask,
)


def _timestamp(value: str) -> int:
    return int(pd.Timestamp(value, tz="Asia/Shanghai").timestamp() * 1000)


def test_risk_disclosure_starts_next_trading_date_and_spans_ten_trading_dates() -> None:
    dates = pd.bdate_range("2025-01-02", periods=14)
    mask = risk_disclosure_mask(dates, ["1"] * len(dates), [_timestamp("2025-01-03 00:00")])

    assert not bool(mask.iloc[1])
    assert mask.iloc[2:12].all()
    assert not bool(mask.iloc[12])


def test_risk_disclosure_does_not_consume_suspension_rows() -> None:
    dates = pd.bdate_range("2025-01-02", periods=13)
    trading = ["1"] * len(dates)
    trading[3] = "0"
    mask = risk_disclosure_mask(dates, trading, [_timestamp("2025-01-02 23:30")])

    assert not bool(mask.iloc[0])
    assert not bool(mask.iloc[3])
    assert mask.sum() == 10
    assert bool(mask.iloc[11])
    assert not bool(mask.iloc[12])


def test_invalid_announcement_timestamp_is_ignored() -> None:
    dates = pd.bdate_range("2025-01-02", periods=5)
    mask = risk_disclosure_mask(dates, ["1"] * len(dates), [None, "bad"])

    assert not mask.any()


def _cell(n: int, precision: float, wilson: float = 0.65) -> dict[str, float | int]:
    hits = round(n * precision)
    return {
        "n": n,
        "hits": hits,
        "false_positives": n - hits,
        "precision": precision,
        "fpr": 1.0 - precision,
        "wilson_lower_95": wilson,
    }


def _passing_summaries() -> dict[str, dict[str, dict[str, float | int]]]:
    return {
        "mhpg_baseline": {
            "selection_2023_2024": _cell(400, 0.40),
            "holdout_2025_2026": _cell(400, 0.40),
        },
        "risk_exclusion": {
            "selection_2023_2024": _cell(320, 0.72),
            "holdout_2025_2026": _cell(320, 0.72),
            "year_2023": _cell(160, 0.72),
            "year_2024": _cell(160, 0.72),
            "year_2025": _cell(220, 0.72),
            "year_2026": _cell(100, 0.72),
        },
    }


def test_decision_accepts_only_when_all_frozen_gates_pass() -> None:
    decision = evaluate_risk_decision(
        _passing_summaries(),
        {"holdout_2025_2026": _cell(310, 0.71)},
    )

    assert decision["stage1_passed"] is True
    assert decision["selection_failure_codes"] == []


def test_decision_rejects_sub_70_precision_and_small_sample() -> None:
    summaries = _passing_summaries()
    summaries["risk_exclusion"]["selection_2023_2024"] = _cell(299, 0.69, 0.59)
    decision = evaluate_risk_decision(summaries, {"holdout_2025_2026": _cell(310, 0.71)})

    assert decision["stage1_passed"] is False
    assert "precision_below_0.70" in decision["selection_failure_codes"]
    assert "n_below_300" in decision["selection_failure_codes"]
    assert "wilson_lower_below_0.60" in decision["selection_failure_codes"]
