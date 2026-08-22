from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from ashare_edge_scout.research_precision70 import (
    CANDIDATES,
    add_cross_sectional_features,
    build_stock_panel,
    candidate_masks,
    causal_barrier_prior,
    evaluate_decision,
    five_close_label,
    next_five_trading_closes_and_maturity,
    nonoverlapping_origins,
    production_gate_mask,
    stable_sample,
)
from ashare_edge_scout.research_v2 import summarize_counts
from ashare_edge_scout.signal_scoring import apply_hard_gates


CONFIG = {
    "universe": {
        "include_prefixes": ["sh.600"],
        "exclude_st": True,
        "min_listing_days": 3,
        "min_close_cny": 5.0,
        "max_close_cny": 80.0,
        "min_adv20_cny": 100.0,
        "min_trading_days_60": 2,
        "block_limit_up_entries": True,
        "block_suspensions": True,
    }
}


def bars(count: int = 140, *, start: str = "2020-01-01") -> pd.DataFrame:
    dates = pd.date_range(start, periods=count, freq="D")
    close = 10.0 + np.arange(count) * 0.01
    return pd.DataFrame({
        "date": dates,
        "open": close - 0.02,
        "high": close + 0.05,
        "low": close - 0.05,
        "close": close,
        "preclose": close / 1.01,
        "volume": 1000.0,
        "amount": 200.0,
        "tradestatus": "1",
        "isST": "0",
    })


def test_production_gate_mask_matches_apply_hard_gates_on_representative_dates() -> None:
    frame = bars(70)
    frame.loc[65, "isST"] = "1"
    frame.loc[66, "tradestatus"] = "0"
    frame.loc[67, "close"] = 4.0
    frame.loc[68, "close"] = frame.loc[68, "preclose"] * 1.095
    mask = production_gate_mask("sh.600001", frame, CONFIG)
    for index in range(len(frame)):
        passed, _ = apply_hard_gates("sh.600001", frame.iloc[: index + 1].to_dict("records"), CONFIG)
        assert bool(mask.iat[index]) == passed


def test_production_gate_missing_and_invalid_values_fail() -> None:
    frame = bars(25)
    frame.loc[24, "preclose"] = np.nan
    assert not production_gate_mask("sh.600001", frame, CONFIG).iat[-1]
    frame.loc[24, "preclose"] = 10.0
    frame["amount"] = frame["amount"].astype(object)
    frame.loc[24, "amount"] = "bad"
    assert not production_gate_mask("sh.600001", frame, CONFIG).iat[-1]


def test_exact_label_and_suspension_aware_fifth_maturity() -> None:
    records = [
        {"date": f"2024-01-{day:02d}", "close": close, "tradestatus": trade}
        for day, close, trade in (
            (1, 10.0, "1"), (2, 9.8, "1"), (3, 50.0, "0"), (4, 10.3, "1"),
            (5, 10.1, "1"), (6, 9.7, "1"), (7, 10.2, "1"),
        )
    ]
    future = next_five_trading_closes_and_maturity(records, 0)
    assert future is not None
    closes, maturity = future
    assert closes == [9.8, 10.3, 10.1, 9.7, 10.2]
    assert maturity == pd.Timestamp("2024-01-07")
    assert five_close_label(10.0, closes)
    assert not five_close_label(10.0, [10.3, 9.699, 10.0, 10.0, 10.0])


def test_maturity_must_be_strictly_before_origin_and_prior_is_latest_252() -> None:
    dates = pd.date_range("2023-01-01", periods=270)
    maturities = dates + pd.Timedelta(days=1)
    labels = [index % 2 == 0 for index in range(270)]
    prior_n, prior_hits, posterior = causal_barrier_prior(dates, maturities, labels, [True] * 270)
    assert prior_n[1] == 0  # Origin 0 matures on T date and is excluded.
    assert prior_n[2] == 1
    assert prior_n[-1] == 252
    expected = sum(labels[16:268])
    assert prior_hits[-1] == expected
    assert posterior[119] != posterior[119]  # Fewer than 120 matured origins.
    assert posterior[-1] == pytest.approx((expected + 10) / 282)


def _cross_section_panel(dates: list[pd.Timestamp], count: int = 150) -> pd.DataFrame:
    rows = []
    for day_number, date in enumerate(dates):
        for number in range(count):
            rows.append({
                "date": date, "code": f"sh.600{number:03d}", "admitted": True,
                "close": 11.0 if day_number else 9.0, "sma20": 10.0,
                "sma60": 10.0, "ret5": float(number // 2), "ret20": float(number // 2),
                "prior_n": 120, "posterior": float(number // 2) / 100,
            })
    return pd.DataFrame(rows)


def test_cross_section_average_ranks_ties_and_fifth_prior_available_panel_date() -> None:
    dates = list(pd.to_datetime(["2024-01-02", "2024-01-04", "2024-01-09", "2024-01-10", "2024-01-15", "2024-02-01"]))
    result = add_cross_sectional_features(_cross_section_panel(dates))
    first = result[result["date"].eq(dates[0])]
    assert first.iloc[0]["ret20_pct"] == pytest.approx(1.5 / 150)
    last = result[result["date"].eq(dates[-1])].iloc[0]
    assert last["breadth_acceleration"] == pytest.approx(1.0)


def test_invalid_denominator_date_is_not_a_prior_panel_date() -> None:
    dates = list(pd.date_range("2024-01-01", periods=7))
    panel = _cross_section_panel(dates)
    panel = panel[~((panel["date"] == dates[1]) & (panel["code"] >= "sh.600149"))]
    result = add_cross_sectional_features(panel)
    final = result[result["date"].eq(dates[-1])].iloc[0]
    # Five prior valid dates means date[0], whose breadth is zero.
    assert final["breadth_acceleration"] == pytest.approx(1.0)


def passing_candidate_row() -> dict[str, object]:
    return {
        "admitted": True, "daily_denominator": 150, "breadth_sma20": 0.60,
        "breadth_sma60": 0.50, "breadth_acceleration": 0.05, "median_ret5": 0.01,
        "close": 12.0, "sma20": 11.0, "sma60": 10.0, "sma20_t5": 10.9,
        "sma60_t5": 9.9, "ret20_pct": 0.80, "ret5_pct": 0.60,
        "ret20": 0.10, "benchmark_ret20": 0.05, "bullish_t": True,
        "close_location": 0.70, "upper_shadow_ratio": 0.20, "volume_ratio_ma20": 1.5,
        "ret_t3_to_t1": -0.03, "t_return": 0.03, "previous_high": 11.9,
        "prior_n": 120, "posterior_pct": 0.95, "posterior": 0.45, "ret5": 0.02,
    }


@pytest.mark.parametrize("candidate", CANDIDATES)
def test_each_candidate_exact_inclusive_lower_bound(candidate: str) -> None:
    masks = candidate_masks(pd.DataFrame([passing_candidate_row()]))
    assert bool(masks[candidate].iat[0])


@pytest.mark.parametrize(
    ("candidate", "field", "value"),
    [
        (CANDIDATES[0], "ret20_pct", 0.98),
        (CANDIDATES[0], "ret5_pct", 0.95),
        (CANDIDATES[1], "ret20_pct", 0.95),
        (CANDIDATES[1], "ret_t3_to_t1", -0.060001),
        (CANDIDATES[1], "t_return", 0.050001),
        (CANDIDATES[2], "posterior_pct", 0.949999),
        (CANDIDATES[2], "ret5", 0.080001),
    ],
)
def test_candidate_exact_exclusive_or_outside_boundaries(candidate: str, field: str, value: float) -> None:
    row = passing_candidate_row()
    row[field] = value
    assert not candidate_masks(pd.DataFrame([row]))[candidate].iat[0]


def test_candidate_three_does_not_use_breadth_regime() -> None:
    row = passing_candidate_row()
    row.update({"breadth_sma20": 0.0, "breadth_sma60": 0.0, "breadth_acceleration": -1.0, "median_ret5": -1.0})
    masks = candidate_masks(pd.DataFrame([row]))
    assert not masks[CANDIDATES[0]].iat[0]
    assert not masks[CANDIDATES[1]].iat[0]
    assert masks[CANDIDATES[2]].iat[0]


def test_nonoverlap_spacing_uses_stock_tradable_index_causally() -> None:
    rows = pd.DataFrame({
        "date": pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-06", "2024-01-07"]),
        "code": ["a", "a", "b", "a", "a"], "trading_index": [10, 14, 1, 15, 20],
    })
    selected = nonoverlapping_origins(rows)
    assert list(selected[selected["code"].eq("a")]["trading_index"]) == [10, 15, 20]


def _all_pass_summaries() -> tuple[dict[str, object], dict[str, object]]:
    summary: dict[str, object] = {}
    sensitivity: dict[str, object] = {}
    for candidate in CANDIDATES:
        summary[candidate] = {
            "selection_2023_2024": summarize_counts(400, 320),
            "holdout_2025_2026": summarize_counts(400, 320),
            "year_2023": summarize_counts(200, 160), "year_2024": summarize_counts(200, 160),
            "year_2025": summarize_counts(200, 160), "year_2026": summarize_counts(200, 160),
        }
        sensitivity[candidate] = {"holdout_2025_2026": summarize_counts(100, 80)}
    return summary, sensitivity


def test_holdout_is_not_used_in_selection_eligibility() -> None:
    summaries, sensitivity = _all_pass_summaries()
    summaries[CANDIDATES[0]]["holdout_2025_2026"] = summarize_counts(0, 0)
    decision = evaluate_decision(summaries, sensitivity)["candidates"][CANDIDATES[0]]
    assert decision["selection_eligible"]
    assert not decision["final_pass"]


def test_ineligible_selection_forces_final_false_even_with_passing_holdout() -> None:
    summaries, sensitivity = _all_pass_summaries()
    summaries[CANDIDATES[0]]["selection_2023_2024"] = summarize_counts(299, 150)
    summaries[CANDIDATES[0]]["year_2023"] = summarize_counts(49, 40)
    summaries[CANDIDATES[0]]["year_2024"] = summarize_counts(49, 40)
    decision = evaluate_decision(summaries, sensitivity)["candidates"][CANDIDATES[0]]
    assert not decision["selection_eligible"]
    assert not decision["final_pass"]
    assert set(decision["selection_failure_codes"]) == {
        "selection_precision_below_0.70", "selection_n_below_300",
        "selection_year_2023_n_below_50", "selection_year_2024_n_below_50",
        "selection_wilson_lower_below_0.60",
    }


def test_every_holdout_failure_category_has_stable_code() -> None:
    summaries, sensitivity = _all_pass_summaries()
    candidate = CANDIDATES[0]
    summaries[candidate]["holdout_2025_2026"] = summarize_counts(299, 150)
    summaries[candidate]["year_2025"] = summarize_counts(49, 40)
    summaries[candidate]["year_2026"] = summarize_counts(24, 20)
    sensitivity[candidate]["holdout_2025_2026"] = summarize_counts(100, 69)
    failures = set(evaluate_decision(summaries, sensitivity)["candidates"][candidate]["holdout_failure_codes"])
    assert failures == {
        "holdout_precision_below_0.70", "holdout_n_below_300",
        "holdout_year_2025_n_below_50", "holdout_year_2026_n_below_25",
        "holdout_wilson_lower_below_0.60", "holdout_nonoverlap_precision_below_0.70",
    }


def test_future_changes_do_not_alter_past_causal_panel_features() -> None:
    frame = bars(145)
    config = {"universe": {**CONFIG["universe"], "min_listing_days": 20}}
    first = build_stock_panel("sh.600001", frame, config, {}, start_date="2020-01-01")
    changed = frame.copy()
    changed.loc[130:, ["open", "high", "low", "close", "preclose", "volume", "amount"]] *= 2
    second = build_stock_panel("sh.600001", changed, config, {}, start_date="2020-01-01")
    causal_columns = [column for column in first.columns if column not in {"label", "maturity_date"}]
    pd.testing.assert_frame_equal(first.loc[:124, causal_columns], second.loc[:124, causal_columns])


def test_stable_sample_exact_size_hash_and_constraints(tmp_path: Path) -> None:
    paths = [tmp_path / f"sh.600{number:03d}.parquet" for number in range(405)]
    sampled = stable_sample(paths)
    assert len(sampled) == 400
    assert sampled == sorted(sampled, key=lambda path: path.stem)
    with pytest.raises(ValueError, match="must equal 400"):
        stable_sample(paths, 399)
    with pytest.raises(ValueError, match="exactly 400"):
        stable_sample(paths[:399])


def _load_cli_module():
    path = Path(__file__).parents[1] / "scripts" / "evaluate_precision70_stage1.py"
    spec = importlib.util.spec_from_file_location("evaluate_precision70_stage1", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("arguments", [["--output", "x", "--max-codes", "399"], ["--output", "x", "--workers", "0"], ["--output", "x", "--workers", "9"]])
def test_cli_rejects_nonfixed_sample_and_worker_limits(arguments: list[str]) -> None:
    with pytest.raises(SystemExit) as error:
        _load_cli_module().parse_args(arguments)
    assert error.value.code == 2


def test_cli_accepts_exact_constraints() -> None:
    args = _load_cli_module().parse_args(["--output", "x", "--max-codes", "400", "--workers", "8"])
    assert (args.max_codes, args.workers) == (400, 8)


def test_cli_limits_each_blas_runtime_to_one_thread(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_cli_module()
    for name in module.BLAS_THREAD_VARIABLES:
        monkeypatch.setenv(name, "9")
    module._limit_blas_threads()
    assert all(module.os.environ[name] == "1" for name in module.BLAS_THREAD_VARIABLES)
