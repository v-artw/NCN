from __future__ import annotations

import pytest
import pandas as pd

from ashare_edge_scout.discovery import compute_price_volume_base_score
from ashare_edge_scout.research_pmkf_mkf_t5_quality import (
    CANDIDATES,
    build_comparison_panel,
    build_comparison_report,
    candidate_masks,
    pmkf_base_score_series,
    t5_close_and_path_outcomes,
)


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


def _frame(rows: int = 80) -> pd.DataFrame:
    close = [10.0 + index * 0.1 for index in range(rows)]
    return pd.DataFrame({
        "date": pd.bdate_range("2025-01-01", periods=rows),
        "open": close,
        "high": [value * 1.01 for value in close],
        "low": [value * 0.99 for value in close],
        "close": close,
        "preclose": [close[0], *close[:-1]],
        "volume": [1_000_000.0] * rows,
        "amount": [50_000_000.0] * rows,
        "tradestatus": ["1"] * rows,
        "isST": ["0"] * rows,
    })


def test_pmkf_vector_latest_score_matches_scalar_zero_futu_bonus() -> None:
    frame = _frame()
    vector_score = pmkf_base_score_series(frame).iloc[-1]
    scalar_score = compute_price_volume_base_score(
        frame["high"], frame["low"], frame["close"], frame["volume"], futu_bonus=0.0
    )

    assert vector_score == scalar_score


def test_candidate_masks_define_a_b_c_relationships(monkeypatch) -> None:
    frame = _frame()
    fake_mkf = pd.Series(False, index=frame.index)
    fake_mkf.iloc[-1] = True
    monkeypatch.setattr("ashare_edge_scout.research_pmkf_mkf_t5_quality.mkf_red_blue_cross20_green_exit_under80_mask", lambda _: fake_mkf)
    monkeypatch.setattr("ashare_edge_scout.research_pmkf_mkf_t5_quality.pmkf_base_score_series", lambda _: pd.Series([0.0] * (len(frame) - 1) + [80.0], index=frame.index))

    masks = candidate_masks(frame, _config(), "sh.600001")

    assert bool(masks["A_mkf_red_blue"].iloc[-1]) is True
    assert bool(masks["B_pmkf_backbone"].iloc[-1]) is True
    assert bool(masks["C_pmkf_plus_mkf_timing"].iloc[-1]) is True
    assert (masks["C_pmkf_plus_mkf_timing"] <= masks["A_mkf_red_blue"]).all()
    assert (masks["C_pmkf_plus_mkf_timing"] <= masks["B_pmkf_backbone"]).all()


def test_t5_label_skips_suspensions_and_uses_five_future_tradable_closes() -> None:
    frame = _frame(8)
    frame.loc[1, "tradestatus"] = "0"
    frame.loc[1, "close"] = 1.0
    frame.loc[2:6, "close"] = [101.0, 103.0, 104.0, 105.0, 106.0]
    frame.loc[0, "close"] = 100.0

    row = t5_close_and_path_outcomes(frame)[pd.Timestamp(frame.loc[0, "date"])]

    assert row["status"] == "mature"
    assert row["label"] is True
    assert row["maturity_date"] == pd.Timestamp(frame.loc[6, "date"])


def test_path_metrics_report_same_day_ambiguous() -> None:
    frame = _frame(7)
    frame.loc[0, "close"] = 100.0
    frame.loc[1:5, "high"] = 101.0
    frame.loc[1:5, "low"] = 99.0
    frame.loc[1, "high"] = 104.0
    frame.loc[1, "low"] = 96.0
    row = t5_close_and_path_outcomes(frame)[pd.Timestamp(frame.loc[0, "date"])]

    assert row["target3_touched"] is True
    assert row["risk3_touched"] is True
    assert row["target3_risk3_first_state"] == "same_day_ambiguous"
    assert row["max_excursion"] == pytest.approx(0.04)
    assert row["max_drawdown"] == pytest.approx(-0.04)


def test_panel_and_report_include_side_by_side_readonly_metadata(monkeypatch) -> None:
    frame = _frame(70)
    fake_mkf = pd.Series(False, index=frame.index)
    fake_mkf.iloc[59] = True
    monkeypatch.setattr("ashare_edge_scout.research_pmkf_mkf_t5_quality.mkf_red_blue_cross20_green_exit_under80_mask", lambda _: fake_mkf)
    scores = pd.Series(0.0, index=frame.index)
    scores.iloc[59] = 80.0
    scores.iloc[60] = 80.0
    monkeypatch.setattr("ashare_edge_scout.research_pmkf_mkf_t5_quality.pmkf_base_score_series", lambda _: scores)

    panel = build_comparison_panel("sh.600001", frame, _config(), start_date="2025-01-01", end_date="2025-12-31")
    report = build_comparison_report(
        panel=panel,
        code_list=["sh.600001"],
        code_list_sha256="abc",
        start_date="2025-01-01",
        end_date="2025-12-31",
        workers=1,
    )

    assert set(CANDIDATES).issubset(report["metrics"]["full_requested_range"])
    assert report["research_only"] is True
    assert report["production_enabled"] is False
    assert report["watchlist_modified"] is False
    assert report["smc_admission_modified"] is False
    assert report["broker_orders_enabled"] is False
    assert report["pnl_modeled"] is False
    assert report["futu_signals_ignored"] is True
    assert report["candidate_definitions"]["B_pmkf_backbone"]["futu_bonus"] == 0.0
    assert report["metrics"]["full_requested_range"]["C_pmkf_plus_mkf_timing"]["n"] == 1
