from __future__ import annotations

import pandas as pd
import pytest

from ashare_edge_scout.pmkf_mkf.mkf_post_cross_lag_comparison import (
    GRID_SCHEMA_VERSION,
    PRIMARY_HORIZONS,
    STABILITY_GATE_CONFIG,
    T20_CLOSE_FALLBACK_SCHEMA_VERSION,
    _best_return_cell,
    _stability_gate_result,
    aggregate_lag_target_grid_metrics,
    build_lag_target_grid_report,
    build_mkf_post_cross_lag_t20_close_fallback_panel,
    build_mkf_post_cross_lag_target_grid_panel,
    build_t20_close_fallback_report,
    lag_target_grid_summary_csv_rows,
    t20_close_fallback_summary_csv_rows,
)
from ashare_edge_scout.research_v2 import summarize_counts


def _frame(rows: int = 26, start: str = "2025-01-01") -> pd.DataFrame:
    close = [100.0 for _ in range(rows)]
    return pd.DataFrame({
        "date": pd.bdate_range(start, periods=rows),
        "open": [100.0 for _ in range(rows)],
        "high": [101.0 for _ in range(rows)],
        "low": [99.0 for _ in range(rows)],
        "close": close,
        "preclose": [close[0], *close[:-1]],
        "volume": [1_000_000.0] * rows,
        "amount": [50_000_000.0] * rows,
        "tradestatus": ["1"] * rows,
        "isST": ["0"] * rows,
    })


def _config() -> dict:
    return {
        "universe": {
            "include_prefixes": ["sh.600"],
            "exclude_st": True,
            "min_listing_days": 1,
            "min_close_cny": 1.0,
            "max_close_cny": 200.0,
            "min_adv20_cny": 0.0,
            "min_trading_days_60": 1,
            "block_limit_up_entries": False,
            "block_suspensions": True,
        }
    }


def _patch_signal(monkeypatch: pytest.MonkeyPatch, frame: pd.DataFrame, index: int = 0) -> None:
    signal = pd.Series(False, index=frame.index)
    signal.iloc[index] = True
    monkeypatch.setattr(
        "ashare_edge_scout.pmkf_mkf.mkf_post_cross_lag_comparison.mkf_red_blue_cross20_green_exit_under80_mask",
        lambda _: signal,
    )


def _metric(n: int, hits: int, *, target_pct: int = 5, entry_dates: int | None = None, codes: int | None = None) -> dict:
    counts = summarize_counts(n, hits)
    return {
        "n": n,
        "target_hits": hits,
        "target_hit_rate": counts["precision"],
        "target_hit_wilson_lower_95": counts["wilson_lower_95"],
        "target_hit_wilson_upper_95": counts["wilson_upper_95"],
        "mean_target_zero_return": None if counts["precision"] is None else counts["precision"] * target_pct / 100.0,
        "entry_dates": n if entry_dates is None else entry_dates,
        "codes": 60 if codes is None else codes,
    }


def test_target_grid_includes_requested_dimensions(monkeypatch: pytest.MonkeyPatch) -> None:
    frame = _frame(rows=28)
    _patch_signal(monkeypatch, frame)

    panel = build_mkf_post_cross_lag_target_grid_panel("sh.600001", frame, _config(), lags=(0,), horizons=tuple(range(1, 21)))
    report = build_lag_target_grid_report(
        panel=panel,
        diagnostics=panel.attrs["diagnostics"],
        code_list=["sh.600001"],
        code_list_sha256="abc",
        start_date="2025-01-01",
        end_date=None,
        workers=1,
        horizons=tuple(range(1, 21)),
        target_pcts=tuple(range(1, 21)),
    )

    assert report["schema_version"] == GRID_SCHEMA_VERSION
    assert report["grid"]["lags"] == list(range(0, 8))
    assert report["grid"]["horizons"] == list(range(1, 21))
    assert report["grid"]["target_pcts"] == list(range(1, 21))
    assert "T+20" in report["grid_metrics"]["0"]["full_period"]
    assert "target_20pct" in report["grid_metrics"]["0"]["full_period"]["T+20"]


def test_cumulative_hit_excludes_entry_day(monkeypatch: pytest.MonkeyPatch) -> None:
    frame = _frame(rows=12)
    _patch_signal(monkeypatch, frame)
    frame.loc[1, "high"] = 110.0
    frame.loc[2, "high"] = 104.0
    frame.loc[3, "high"] = 106.0
    frame.loc[4, "close"] = 90.0

    panel = build_mkf_post_cross_lag_target_grid_panel("sh.600001", frame, _config(), lags=(0,), horizons=(1, 3))
    aggregated = aggregate_lag_target_grid_metrics(panel, panel.attrs["diagnostics"], horizons=(1, 3), target_pcts=(5,))

    t1 = aggregated["grid_metrics"]["0"]["full_period"]["T+1"]["target_5pct"]
    t3 = aggregated["grid_metrics"]["0"]["full_period"]["T+3"]["target_5pct"]
    assert t1["target_hits"] == 0
    assert t1["target_hit_rate"] == 0.0
    assert t3["target_hits"] == 1
    assert t3["target_hit_rate"] == 1.0


def test_metric_schema_uses_target_zero_return_without_close_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    frame = _frame(rows=12)
    _patch_signal(monkeypatch, frame)
    frame.loc[3, "high"] = 106.0
    panel = build_mkf_post_cross_lag_target_grid_panel("sh.600001", frame, _config(), lags=(0,), horizons=(1, 3))
    aggregated = aggregate_lag_target_grid_metrics(panel, panel.attrs["diagnostics"], horizons=(1, 3), target_pcts=(5,))
    metrics = aggregated["grid_metrics"]["0"]["full_period"]["T+3"]["target_5pct"]
    report = build_lag_target_grid_report(
        panel=panel,
        diagnostics=panel.attrs["diagnostics"],
        code_list=["sh.600001"],
        code_list_sha256="abc",
        start_date="2025-01-01",
        end_date=None,
        workers=1,
        horizons=(1, 3),
        target_pcts=(5,),
    )
    rows = lag_target_grid_summary_csv_rows(report)

    forbidden = {"mean_realized_gross_return", "median_realized_gross_return", "realized_gross_return_quantiles", "realized_positive_rate", "realized_positive_wins"}
    assert forbidden.isdisjoint(metrics.keys())
    assert forbidden.isdisjoint(rows[0].keys())
    assert "realized_gross_return" not in report["entry_definition"]
    assert "future_close_t3" not in panel.columns
    t3_row = next(row for row in rows if row["horizon"] == "T+3" and row["target_pct"] == 5)
    assert metrics["mean_target_zero_return"] == 0.05
    assert t3_row["mean_target_zero_return"] == 0.05
    assert report["entry_definition"]["non_hit_outcome"] == "not hit by T+n; return is fixed at 0% by user instruction, with no T+n close fallback and no stop-loss rule"
    assert report["entry_definition"]["ranking"] == "highest mean_target_zero_return, where mean_target_zero_return = target_pct / 100 * target_hit_rate"
    assert "best_options" not in report
    assert "best_point_readout" in report


def test_different_targets_on_same_event_have_different_hits(monkeypatch: pytest.MonkeyPatch) -> None:
    frame = _frame(rows=12)
    _patch_signal(monkeypatch, frame)
    frame.loc[2, "high"] = 102.0
    frame.loc[3, "high"] = 103.5
    frame.loc[4, "high"] = 103.0
    frame.loc[5, "close"] = 99.0

    panel = build_mkf_post_cross_lag_target_grid_panel("sh.600001", frame, _config(), lags=(0,), horizons=(4,))
    aggregated = aggregate_lag_target_grid_metrics(panel, panel.attrs["diagnostics"], horizons=(4,), target_pcts=(3, 4))

    target3 = aggregated["grid_metrics"]["0"]["full_period"]["T+4"]["target_3pct"]
    target4 = aggregated["grid_metrics"]["0"]["full_period"]["T+4"]["target_4pct"]
    assert target3["target_hits"] == 1
    assert target3["target_hit_rate"] == 1.0
    assert target4["target_hits"] == 0
    assert target4["target_hit_rate"] == 0.0


def test_partial_rows_are_excluded_per_horizon(monkeypatch: pytest.MonkeyPatch) -> None:
    frame = _frame(rows=5)
    _patch_signal(monkeypatch, frame)

    panel = build_mkf_post_cross_lag_target_grid_panel("sh.600001", frame, _config(), lags=(0,), horizons=tuple(range(1, 21)))
    aggregated = aggregate_lag_target_grid_metrics(panel, panel.attrs["diagnostics"], horizons=tuple(range(1, 21)), target_pcts=(1,))

    assert panel.loc[0, "status"] == "partial"
    assert aggregated["grid_metrics"]["0"]["full_period"]["T+1"]["target_1pct"]["n"] == 1
    assert aggregated["grid_metrics"]["0"]["full_period"]["T+3"]["target_1pct"]["n"] == 1
    assert aggregated["grid_metrics"]["0"]["full_period"]["T+4"]["target_1pct"]["n"] == 0
    assert aggregated["grid_metrics"]["0"]["full_period"]["T+20"]["target_1pct"]["n"] == 0


def test_suspensions_do_not_consume_lag_or_horizon(monkeypatch: pytest.MonkeyPatch) -> None:
    frame = _frame(rows=10)
    frame.loc[1, "tradestatus"] = "0"
    frame.loc[3, "tradestatus"] = "0"
    _patch_signal(monkeypatch, frame)

    panel = build_mkf_post_cross_lag_target_grid_panel("sh.600001", frame, _config(), lags=(0, 1), horizons=(1,))

    assert panel["post_cross_lag"].tolist() == [0, 1]
    assert panel.loc[0, "entry_date"] == frame.loc[2, "date"]
    assert panel.loc[0, "date_t1"] == frame.loc[4, "date"]
    assert panel.loc[1, "signal_date"] == frame.loc[2, "date"]


def test_hard_gate_still_applies_at_lag_signal_row(monkeypatch: pytest.MonkeyPatch) -> None:
    frame = _frame(rows=10)
    frame.loc[1, "close"] = 250.0
    _patch_signal(monkeypatch, frame)

    panel = build_mkf_post_cross_lag_target_grid_panel("sh.600001", frame, _config(), lags=(0, 1), horizons=(1,))

    assert panel["post_cross_lag"].tolist() == [0]
    assert panel.attrs["diagnostics"]["lag_1_hard_gate_rejected"] == 1


def test_grid_report_metadata_and_csv_rows_preserve_research_boundary(monkeypatch: pytest.MonkeyPatch) -> None:
    frame = _frame(rows=12)
    _patch_signal(monkeypatch, frame)
    panel = build_mkf_post_cross_lag_target_grid_panel("sh.600001", frame, _config(), lags=(0,), horizons=(1, 2))

    report = build_lag_target_grid_report(
        panel=panel,
        diagnostics=panel.attrs["diagnostics"],
        code_list=["sh.600001"],
        code_list_sha256="abc",
        start_date="2025-01-01",
        end_date=None,
        workers=1,
        horizons=(1, 2),
        target_pcts=(1, 2),
    )
    rows = lag_target_grid_summary_csv_rows(report)

    assert report["research_only"] is True
    assert report["production_enabled"] is False
    assert report["original_mkf_selector_modified"] is False
    assert rows[0]["lag"] == "0"
    assert rows[0]["period"] == "full_period"
    assert rows[0]["horizon"] == "T+1"
    assert rows[0]["target_pct"] == 1
    assert set(rows[0]) == {
        "lag", "period", "horizon", "target_pct", "target_label",
        "n", "target_hits", "target_hit_rate",
        "target_hit_wilson_lower_95", "target_hit_wilson_upper_95",
        "mean_target_zero_return",
        "entry_dates", "codes", "events", "retention_vs_parent_crosses",
    }
    readout = report["best_point_readout"]
    assert readout["primary_horizons"] == [f"T+{horizon}" for horizon in PRIMARY_HORIZONS]
    assert readout["stability_gates"] == STABILITY_GATE_CONFIG
    assert readout["best_by_mean_target_zero_return"]["mean_target_zero_return"] == 0.01
    # The one-event frame cannot pass min_n, so no cell is eligible anywhere.
    for cells in readout["eligible_cells_by_primary_horizon"].values():
        assert cells == []


def test_t20_close_fallback_realized_return(monkeypatch: pytest.MonkeyPatch) -> None:
    hit_frame = _frame(rows=24)
    _patch_signal(monkeypatch, hit_frame)
    hit_frame.loc[3, "high"] = 106.0
    hit_frame.loc[21, "close"] = 80.0
    hit_panel = build_mkf_post_cross_lag_t20_close_fallback_panel("sh.600001", hit_frame, _config(), lags=(0,))
    hit_report = build_t20_close_fallback_report(
        panel=hit_panel,
        diagnostics=hit_panel.attrs["diagnostics"],
        code_list=["sh.600001"],
        code_list_sha256="abc",
        start_date="2025-01-01",
        end_date=None,
        workers=1,
        target_pcts=(5,),
    )
    hit_metric = hit_report["grid_metrics"]["0"]["full_period"]["T+20"]["target_5pct"]
    assert hit_report["schema_version"] == T20_CLOSE_FALLBACK_SCHEMA_VERSION
    assert hit_metric["mean_realized_return"] == 0.05
    assert hit_metric["median_realized_return"] == 0.05

    miss_frame = _frame(rows=24)
    _patch_signal(monkeypatch, miss_frame)
    miss_frame.loc[21, "close"] = 90.0
    miss_panel = build_mkf_post_cross_lag_t20_close_fallback_panel("sh.600001", miss_frame, _config(), lags=(0,))
    miss_report = build_t20_close_fallback_report(
        panel=miss_panel,
        diagnostics=miss_panel.attrs["diagnostics"],
        code_list=["sh.600001"],
        code_list_sha256="abc",
        start_date="2025-01-01",
        end_date=None,
        workers=1,
        target_pcts=(5,),
    )
    miss_metric = miss_report["grid_metrics"]["0"]["full_period"]["T+20"]["target_5pct"]
    rows = t20_close_fallback_summary_csv_rows(miss_report)
    assert miss_metric["target_hits"] == 0
    assert miss_metric["mean_realized_return"] == pytest.approx(-0.1)
    assert rows[0]["mean_realized_return"] == pytest.approx(-0.1)
    assert miss_report["entry_definition"]["non_hit_return"] == "T+20 close / entry_open - 1"


def test_stability_gate_eligibility_with_synthetic_metrics() -> None:
    stable_periods = {
        "full_period": _metric(1000, 400),
        "selection_2021_2023": _metric(500, 200),
        "audit_2024_present": _metric(500, 190),
        "year_2021": _metric(200, 80),
        "year_2022": _metric(200, 74),
        "year_2023": _metric(200, 82),
        "year_2024": _metric(200, 72),
        "year_2025": _metric(200, 78),
        "year_2026": _metric(200, 66),
    }
    result = _stability_gate_result(stable_periods)
    assert result["passed"] is True
    assert result["years_observed"] == 6
    assert result["years_within_drawdown"] >= 4

    audit_regression = dict(stable_periods)
    audit_regression["audit_2024_present"] = _metric(500, 160)
    assert _stability_gate_result(audit_regression)["passed"] is False

    small_sample = dict(stable_periods)
    small_sample["full_period"] = _metric(200, 80)
    assert _stability_gate_result(small_sample)["passed"] is False


def test_best_return_cell_picks_highest_target_zero_return() -> None:
    aggregated = {
        "grid_metrics": {
            "0": {
                "full_period": {"T+5": {"target_5pct": _metric(1000, 600, target_pct=5)}},
            },
            "2": {
                "full_period": {"T+5": {"target_10pct": _metric(1000, 400, target_pct=10)}},
            },
        }
    }
    best = _best_return_cell(aggregated)
    assert best is not None
    assert best["lag"] == 2
    assert best["target_pct"] == 10
    assert best["mean_target_zero_return"] == 0.04


def test_best_return_cell_ignores_empty_cells() -> None:
    aggregated = {
        "grid_metrics": {
            "0": {"full_period": {"T+5": {"target_5pct": _metric(0, 0, target_pct=5)}}},
            "1": {"full_period": {"T+5": {"target_5pct": _metric(400, 120, target_pct=5)}}},
        }
    }
    best = _best_return_cell(aggregated)
    assert best is not None
    assert best["lag"] == 1
