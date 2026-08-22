from __future__ import annotations

import pandas as pd

from ashare_edge_scout.research_excursion_validation import (
    _future_excursions,
    build_excursion_panel,
    evaluate_excursion_stability,
)
from ashare_edge_scout.research_v2 import summarize_counts


def _frame(closes: list[float], highs: list[float] | None = None) -> pd.DataFrame:
    highs = highs or [value * 1.01 for value in closes]
    return pd.DataFrame({
        "date": pd.bdate_range("2025-01-01", periods=len(closes)),
        "open": closes, "high": highs, "low": [value * 0.99 for value in closes], "close": closes,
        "preclose": [closes[0], *closes[:-1]], "volume": [1_000_000] * len(closes),
        "amount": [10_000_000] * len(closes), "tradestatus": ["1"] * len(closes), "isST": ["0"] * len(closes),
    })


def _config() -> dict:
    return {"universe": {"include_prefixes": ["sh.600"], "exclude_st": True, "min_listing_days": 1, "min_close_cny": 1, "max_close_cny": 1000, "block_suspensions": True, "min_trading_days_60": 1, "min_adv20_cny": 0, "block_limit_up_entries": False}}


def test_threshold_boundaries_and_horizon_maturity() -> None:
    frame = _frame([100.0] * 11, [101.0, 103.0, 104.0, 105.0, 104.0, 104.0, 104.0, 105.0, 106.0, 104.0, 104.0])
    row = _future_excursions(frame)[pd.Timestamp("2025-01-01")]
    assert row["pass_3pct_5d"] is True
    assert row["full_5pct_5d"] is True
    assert row["score_5d"] == 2
    assert row["full_5pct_10d"] is True


def test_exact_three_percent_is_not_pass_and_exact_five_is_full() -> None:
    frame = _frame([100.0] * 11, [101.0, 103.0, 102.0, 102.0, 102.0, 102.0, 105.0, 102.0, 102.0, 102.0, 102.0])
    row = _future_excursions(frame)[pd.Timestamp("2025-01-01")]
    assert row["pass_3pct_5d"] is False
    assert row["score_5d"] == 0
    assert row["full_5pct_10d"] is True


def test_suspensions_are_skipped_inside_horizons() -> None:
    frame = _frame([100.0] * 12, [101.0] * 12)
    frame.loc[1, "tradestatus"] = "0"
    frame.loc[1, "high"] = 200.0
    frame.loc[6, "high"] = 106.0
    row = _future_excursions(frame)[pd.Timestamp("2025-01-01")]
    assert row["target_date"] == frame.loc[2, "date"]
    assert row["full_5pct_5d"] is True


def test_future_changes_do_not_change_origin_candidate_masks() -> None:
    frame = _frame([10.0] * 80)
    original = build_excursion_panel("sh.600001", frame, _config(), start_date="2025-01-01")
    changed = frame.copy()
    changed.loc[1:, ["open", "high", "low", "close"]] *= 5
    changed_panel = build_excursion_panel("sh.600001", changed, _config(), start_date="2025-01-01")
    candidate_columns = [name for name in original.columns if name in changed_panel and name.startswith(("dxbd", "candle", "mhpg", "kdj", "smc", "mkf", "shengbei", "gding", "cpgw", "alphagpt", "ribbon"))]
    assert original.loc[0, candidate_columns].tolist() == changed_panel.loc[0, candidate_columns].tolist()


def test_stability_uses_expected_direction_for_bullish_and_risk() -> None:
    def metric(rate: float, baseline: float) -> dict:
        value = summarize_counts(400, round(400 * rate))
        value.update({
            "target_dates": 130,
            "same_target_date_baseline": {"weighted_n": 400, "weighted_hits": 400 * baseline, "precision": baseline},
            "rate_lift": rate - baseline,
        })
        return {"pass_3pct": value}

    bullish = {f"year_{year}": metric(0.60, 0.50) for year in range(2021, 2027)}
    risk = {f"year_{year}": metric(0.40, 0.50) for year in range(2021, 2027)}
    assert evaluate_excursion_stability(bullish, label="pass_3pct", direction="bullish", last_year=2026)["passed"]
    assert evaluate_excursion_stability(risk, label="pass_3pct", direction="risk", last_year=2026)["passed"]
    assert not evaluate_excursion_stability(bullish, label="pass_3pct", direction="annotation", last_year=2026)["passed"]
