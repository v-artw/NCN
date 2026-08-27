from __future__ import annotations

import pandas as pd
import pytest

from ashare_edge_scout.pmkf_mkf.profitability import (
    build_profitability_panel,
    build_profitability_report,
    horizon_close_outcomes,
    mkf_profitability_candidate_mask,
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


def _frame(rows: int = 16) -> pd.DataFrame:
    close = [100.0 + index for index in range(rows)]
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


def test_horizon_outcomes_skip_suspensions_and_anchor_to_t_close() -> None:
    frame = _frame(13)
    frame.loc[0, "close"] = 100.0
    frame.loc[1, "tradestatus"] = "0"
    frame.loc[1, "close"] = 999.0
    frame.loc[2:11, "close"] = [101.0, 102.0, 103.0, 104.0, 105.0, 106.0, 107.0, 108.0, 109.0, 110.0]

    row = horizon_close_outcomes(frame)[pd.Timestamp(frame.loc[0, "date"])]

    assert row["status"] == "mature"
    assert row["date_t1"] == pd.Timestamp(frame.loc[2, "date"])
    assert row["ret_t1_close"] == pytest.approx(0.01)
    assert row["date_t10"] == pd.Timestamp(frame.loc[11, "date"])
    assert row["ret_t10_close"] == pytest.approx(0.10)


def test_horizon_outcomes_marks_late_horizons_partial() -> None:
    frame = _frame(4)

    row = horizon_close_outcomes(frame)[pd.Timestamp(frame.loc[0, "date"])]

    assert row["status"] == "partial"
    assert row["ret_t3_close"] == pytest.approx(0.03)
    assert pd.isna(row["ret_t4_close"])
    assert pd.isna(row["date_t10"])


def test_candidate_mask_uses_v3_mkf_signal_and_existing_hard_gates(monkeypatch) -> None:
    frame = _frame()
    fake_mkf = pd.Series(False, index=frame.index)
    fake_mkf.iloc[-2:] = True
    monkeypatch.setattr("ashare_edge_scout.pmkf_mkf.profitability.mkf_red_blue_cross20_green_exit_under80_mask", lambda _: fake_mkf)
    frame.loc[frame.index[-1], "isST"] = "1"

    mask = mkf_profitability_candidate_mask(frame, _config(), "sh.600001")

    assert bool(mask.iloc[-2]) is True
    assert bool(mask.iloc[-1]) is False


def test_profitability_panel_and_report_include_horizon_metrics_and_boundaries(monkeypatch) -> None:
    frame = _frame(16)
    fake_mkf = pd.Series(False, index=frame.index)
    fake_mkf.iloc[1] = True
    monkeypatch.setattr("ashare_edge_scout.pmkf_mkf.profitability.mkf_red_blue_cross20_green_exit_under80_mask", lambda _: fake_mkf)

    panel = build_profitability_panel("sh.600001", frame, _config(), start_date="2025-01-01", end_date="2025-12-31")
    report = build_profitability_report(
        panel=panel,
        code_list=["sh.600001"],
        code_list_sha256="abc",
        start_date="2025-01-01",
        end_date="2025-12-31",
        workers=1,
    )

    assert len(panel) == 1
    assert panel.loc[0, "ret_t1_close"] == pytest.approx(1 / 101)
    assert panel.loc[0, "ret_t10_close"] == pytest.approx(10 / 101)
    assert report["research_only"] is True
    assert report["production_enabled"] is False
    assert report["watchlist_modified"] is False
    assert report["broker_orders_enabled"] is False
    assert report["ai_review_called"] is False
    assert report["thresholds_tuned"] is False
    assert report["sample"]["candidate_rows"] == 1
    assert report["horizons"]["T+1"]["n"] == 1
    assert report["horizons"]["T+10"]["win_rate"] == 1.0
