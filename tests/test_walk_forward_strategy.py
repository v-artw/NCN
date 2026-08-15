from __future__ import annotations

import pandas as pd

from scripts.evaluate_walk_forward_strategy import _stock_batch, run_walk_forward, summarize_predictions


def _counts(**strategies):
    return strategies


def test_maturity_on_prediction_date_is_unavailable():
    maturity = _counts(
        admitted_baseline={"2023-01-09": [10, 1], "2023-01-10": [10, 0]},
        candidate={"2023-01-09": [10, 2], "2023-01-10": [10, 10]},
    )

    records = run_walk_forward(
        {}, maturity, ["2023-01-10"], min_observations=10, min_active_dates=1
    )

    assert records[0]["selected_strategy"] == "candidate"
    assert records[0]["prior_n"] == 10
    assert records[0]["prior_hits"] == 2


def test_future_excellent_outcomes_cannot_change_prior_selection():
    original = _counts(
        admitted_baseline={"2023-01-05": [20, 4]},
        steady={"2023-01-05": [20, 6]},
        future_winner={"2023-01-05": [20, 3]},
    )
    with_future = {
        **original,
        "future_winner": {**original["future_winner"], "2023-01-11": [1000, 1000]},
    }

    first = run_walk_forward(
        {}, original, ["2023-01-10"], min_observations=10, min_active_dates=1
    )
    second = run_walk_forward(
        {}, with_future, ["2023-01-10"], min_observations=10, min_active_dates=1
    )

    assert first[0]["selected_strategy"] == "steady"
    assert second[0] == first[0]


def test_cold_start_and_insufficient_date_coverage_abstain():
    maturity = _counts(
        admitted_baseline={"2023-01-01": [100, 10], "2023-01-02": [100, 10]},
        candidate={"2023-01-01": [100, 50], "2023-01-02": [100, 50]},
    )

    records = run_walk_forward(
        {},
        maturity,
        ["2023-01-01", "2023-01-03"],
        min_observations=100,
        min_active_dates=3,
    )

    assert [row["selected_strategy"] for row in records] == [None, None]


def test_tie_break_is_larger_n_then_stable_name():
    maturity = _counts(
        admitted_baseline={"2023-01-01": [100, 10]},
        alpha={"2023-01-01": [100, 50]},
        beta={"2023-01-01": [100, 50]},
    )
    record = run_walk_forward(
        {}, maturity, ["2023-01-02"], min_observations=1, min_active_dates=1
    )[0]
    assert record["selected_strategy"] == "alpha"

    maturity["beta"]["2023-01-01"] = [200, 100]
    record = run_walk_forward(
        {}, maturity, ["2023-01-02"], min_observations=1, min_active_dates=1
    )[0]
    assert record["selected_strategy"] == "beta"


def test_aggregate_brier_and_false_positives_are_observation_weighted():
    maturity = _counts(
        admitted_baseline={"2023-01-01": [2, 0]},
        candidate={"2023-01-01": [2, 1]},
    )
    signal = _counts(
        admitted_baseline={"2023-01-02": [5, 2]},
        candidate={"2023-01-02": [2, 1]},
    )
    records = run_walk_forward(
        signal, maturity, ["2023-01-02"], min_observations=1, min_active_dates=1
    )

    summary = summarize_predictions(records)

    assert summary["n"] == 2
    assert summary["hits"] == 1
    assert summary["false_positives"] == 1
    assert summary["false_negatives"] == 1
    assert summary["true_negatives"] == 2
    assert summary["precision"] == 0.5
    assert summary["recall"] == 0.5
    assert summary["f1"] == 0.5
    assert summary["candidate_prediction_dates"] == 1
    assert summary["empty_candidate_dates"] == 0
    assert summary["weighted_brier_score"] == 0.25
    assert summary["weighted_absolute_calibration_error"] == 0.0


def test_selected_rule_with_no_candidates_counts_as_empty_prediction_date():
    maturity = _counts(
        admitted_baseline={"2023-01-01": [10, 2]},
        candidate={"2023-01-01": [10, 4]},
    )
    signal = _counts(admitted_baseline={"2023-01-02": [5, 2]})

    records = run_walk_forward(
        signal, maturity, ["2023-01-02"], min_observations=1, min_active_dates=1
    )
    summary = summarize_predictions(records)

    assert summary["rule_selected_dates"] == 1
    assert summary["candidate_prediction_dates"] == 0
    assert summary["empty_candidate_dates"] == 1
    assert summary["false_negatives"] == 2


def test_batch_skips_short_history_without_returning_raw_rows(tmp_path):
    path = tmp_path / "sh.600001.parquet"
    columns = [
        "date", "open", "high", "low", "close", "preclose", "volume",
        "amount", "turn", "tradestatus", "isST",
    ]
    pd.DataFrame(columns=columns).to_parquet(path, index=False)

    result = _stock_batch(([str(path)], {}, {}, "2021-01-01", None))

    assert result["stocks"] == 1
    assert result["observations"] == 0
    assert result["signal_counts"] == {}
    assert result["maturity_counts"] == {}
