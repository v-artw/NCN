from __future__ import annotations

import numpy as np
import pandas as pd

from ashare_edge_scout.research_mkf import evaluate_mkf_decision, mkf_green_exit_mask


def test_green_exit_requires_all_three_lines_to_transition_on_same_tradable_date(monkeypatch) -> None:
    frame = pd.DataFrame({"tradestatus": ["1", "1", "1"]})
    lines = pd.DataFrame({
        "momentum": [15.0, 25.0, 30.0],
        "inter": [18.0, 21.0, 25.0],
        "near": [20.0, 22.0, 27.0],
    })
    monkeypatch.setattr("ashare_edge_scout.research_mkf.mkf_lines", lambda _: lines)

    assert mkf_green_exit_mask(frame).tolist() == [False, True, False]


def test_suspension_row_does_not_break_prior_tradable_green_state(monkeypatch) -> None:
    frame = pd.DataFrame({"tradestatus": ["1", "0", "1"]})
    lines = pd.DataFrame({
        "momentum": [10.0, np.nan, 21.0],
        "inter": [10.0, np.nan, 21.0],
        "near": [10.0, np.nan, 21.0],
    })
    monkeypatch.setattr("ashare_edge_scout.research_mkf.mkf_lines", lambda _: lines)

    assert mkf_green_exit_mask(frame).tolist() == [False, False, True]


def _cell(n: int, precision: float, lower: float | None = None) -> dict[str, float | int | None]:
    hits = round(n * precision)
    return {
        "n": n, "hits": hits, "false_positives": n - hits, "fpr": 1 - precision,
        "precision": precision, "wilson_lower_95": precision - 0.03 if lower is None else lower,
    }


def _passing() -> tuple[dict, dict]:
    summaries = {
        "same_date_admitted_baseline": {
            "selection_2023_2024": _cell(5000, 0.30), "holdout_2025_2026": _cell(5000, 0.31),
        },
        "mkf_green_exit": {
            "selection_2023_2024": _cell(400, 0.36, 0.32),
            "holdout_2025_2026": _cell(400, 0.37, 0.33),
            "year_2023": _cell(200, 0.36), "year_2024": _cell(200, 0.36),
            "year_2025": _cell(300, 0.37), "year_2026": _cell(100, 0.37),
        },
    }
    sensitivity = {
        "same_date_admitted_baseline": {
            "selection_2023_2024": _cell(4500, 0.30), "holdout_2025_2026": _cell(4500, 0.31),
        },
        "mkf_green_exit": {
            "selection_2023_2024": _cell(350, 0.35), "holdout_2025_2026": _cell(350, 0.36),
        },
    }
    return summaries, sensitivity


def test_decision_requires_stable_lift_and_uncertainty_gates() -> None:
    summaries, sensitivity = _passing()
    assert evaluate_mkf_decision(summaries, sensitivity)["historically_effective"] is True

    summaries["mkf_green_exit"]["holdout_2025_2026"] = _cell(400, 0.32, 0.29)
    decision = evaluate_mkf_decision(summaries, sensitivity)
    assert decision["historically_effective"] is False
    assert "precision_lift_below_0.03" in decision["failure_codes"]["holdout_2025_2026"]
    assert "wilson_lower_not_above_baseline" in decision["failure_codes"]["holdout_2025_2026"]

from ashare_edge_scout.research_mkf import mkf_red_blue_cross20_lines, mkf_red_blue_cross20_under80_mask


def test_red_blue_cross20_under80_requires_same_tradable_date(monkeypatch) -> None:
    frame = pd.DataFrame({"tradestatus": ["1", "1", "1"]})
    lines = pd.DataFrame({
        "momentum": [15.0, 25.0, 30.0],
        "inter": [40.0, 42.0, 43.0],
        "near": [18.0, 35.0, 40.0],
    })
    monkeypatch.setattr("ashare_edge_scout.research_mkf.mkf_red_blue_cross20_lines", lambda _: lines)

    assert mkf_red_blue_cross20_under80_mask(frame).tolist() == [False, True, False]


def test_red_blue_cross20_under80_rejects_single_line_crosses(monkeypatch) -> None:
    frame = pd.DataFrame({"tradestatus": ["1", "1", "1"]})
    lines = pd.DataFrame({
        "momentum": [15.0, 25.0, 30.0],
        "inter": [40.0, 42.0, 43.0],
        "near": [22.0, 35.0, 18.0],
    })
    monkeypatch.setattr("ashare_edge_scout.research_mkf.mkf_red_blue_cross20_lines", lambda _: lines)

    assert mkf_red_blue_cross20_under80_mask(frame).tolist() == [False, False, False]


def test_red_blue_cross20_under80_rejects_current_overheated_lines(monkeypatch) -> None:
    frame = pd.DataFrame({"tradestatus": ["1", "1"]})
    lines = pd.DataFrame({
        "momentum": [15.0, 80.0],
        "inter": [40.0, 42.0],
        "near": [18.0, 35.0],
    })
    monkeypatch.setattr("ashare_edge_scout.research_mkf.mkf_red_blue_cross20_lines", lambda _: lines)

    assert mkf_red_blue_cross20_under80_mask(frame).tolist() == [False, False]


def test_red_blue_cross20_under80_ignores_suspension_as_prior(monkeypatch) -> None:
    frame = pd.DataFrame({"tradestatus": ["1", "0", "1"]})
    lines = pd.DataFrame({
        "momentum": [15.0, 30.0, 25.0],
        "inter": [40.0, 42.0, 43.0],
        "near": [18.0, 30.0, 35.0],
    })
    monkeypatch.setattr("ashare_edge_scout.research_mkf.mkf_red_blue_cross20_lines", lambda _: lines)

    assert mkf_red_blue_cross20_under80_mask(frame).tolist() == [False, False, True]


def test_red_blue_cross20_lines_match_migrated_us_formula() -> None:
    frame = pd.DataFrame({
        "tradestatus": ["1"] * 40,
        "high": [10.0 + index for index in range(40)],
        "low": [8.0 + index for index in range(40)],
        "close": [9.0 + index for index in range(40)],
    })

    lines = mkf_red_blue_cross20_lines(frame)

    low = pd.to_numeric(frame["low"])
    high = pd.to_numeric(frame["high"])
    close = pd.to_numeric(frame["close"])
    expected_momentum = (close - low.rolling(2, min_periods=2).min()) / (high.rolling(4, min_periods=4).max() - low.rolling(4, min_periods=4).min()) * 100.0
    expected_near = ((close - low.rolling(5, min_periods=5).min()) / (high.rolling(5, min_periods=5).max() - low.rolling(5, min_periods=5).min()) * 100.0).rolling(2, min_periods=2).mean()
    expected_inter = ((close - low.rolling(31, min_periods=31).min()) / (high.rolling(31, min_periods=31).max() - low.rolling(31, min_periods=31).min()) * 100.0).rolling(5, min_periods=5).mean()
    pd.testing.assert_series_equal(lines["momentum"], expected_momentum, check_names=False)
    pd.testing.assert_series_equal(lines["near"], expected_near, check_names=False)
    pd.testing.assert_series_equal(lines["inter"], expected_inter, check_names=False)
