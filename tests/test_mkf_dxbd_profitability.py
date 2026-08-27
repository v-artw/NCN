from __future__ import annotations

import pandas as pd
import pytest

from ashare_edge_scout.pmkf_mkf.mkf_dxbd_profitability import (
    build_mkf_dxbd_event_panel,
    build_mkf_dxbd_report,
)
from ashare_edge_scout.research_futu_ranking import candidate_masks_from_values


def _frame(rows: int = 20) -> pd.DataFrame:
    close = [100.0 + index for index in range(rows)]
    return pd.DataFrame({
        "date": pd.bdate_range("2025-01-01", periods=rows),
        "open": [90.0 + index for index in range(rows)],
        "high": [value + 1.0 for value in close],
        "low": [value - 1.0 for value in close],
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


def _patch_signals(monkeypatch, frame: pd.DataFrame, mkf_indexes: list[int], dxbd_indexes: list[int]) -> None:
    mkf = pd.Series(False, index=frame.index)
    dxbd = pd.Series(False, index=frame.index)
    mkf.loc[mkf_indexes] = True
    dxbd.loc[dxbd_indexes] = True
    monkeypatch.setattr(
        "ashare_edge_scout.pmkf_mkf.mkf_dxbd_profitability._signal_masks",
        lambda data, config, code: (mkf.reindex(data.index, fill_value=False), dxbd.reindex(data.index, fill_value=False)),
    )


def test_dxbd_control_is_zero_axis_up_cross() -> None:
    values = pd.DataFrame({
        "dxbd": [-1.0, 1.0],
        "ribbon": [0.0, 0.0],
        "ribbon_signal": [1.0, 1.0],
        "ema20": [1.0, 1.0],
        "ema60": [2.0, 2.0],
        "mhpg_k": [0.0, 0.0],
        "mhpg_d": [1.0, 1.0],
        "kdj_k": [0.0, 0.0],
        "kdj_d": [1.0, 1.0],
        "close": [1.0, 1.0],
        "prior_high30": [2.0, 2.0],
        "prior_close": [1.0, 1.0],
        "body_ratio": [0.0, 0.0],
        "mkf_momentum": [50.0, 50.0],
        "mkf_inter": [50.0, 50.0],
        "mkf_near": [50.0, 50.0],
        "shengbei_state": [-1.0, -1.0],
        "gding_fast": [0.0, 0.0],
        "gding_signal": [1.0, 1.0],
        "cpgw_main": [0.0, 0.0],
        "cpgw_long": [1.0, 1.0],
    })

    assert candidate_masks_from_values(values)["dxbd_cross_zero"].tolist() == [False, True]


def test_lag_five_matches_and_entry_uses_next_tradable_open(monkeypatch) -> None:
    frame = _frame(18)
    _patch_signals(monkeypatch, frame, [0], [5])

    panel = build_mkf_dxbd_event_panel("sh.600001", frame, _config(), start_date="2025-01-01")

    assert len(panel) == 1
    assert panel.loc[0, "confirmation_lag"] == 5
    assert panel.loc[0, "dxbd_confirmation_date"] == frame.loc[5, "date"]
    assert panel.loc[0, "entry_date"] == frame.loc[6, "date"]
    assert panel.loc[0, "entry_open"] == frame.loc[6, "open"]
    assert panel.loc[0, "date_t1"] == frame.loc[7, "date"]
    assert panel.loc[0, "ret_t1_close"] == pytest.approx(frame.loc[7, "close"] / frame.loc[6, "open"] - 1.0)
    assert panel.loc[0, "date_t10"] == frame.loc[16, "date"]


def test_lag_six_does_not_match(monkeypatch) -> None:
    frame = _frame(18)
    _patch_signals(monkeypatch, frame, [0], [6])

    panel = build_mkf_dxbd_event_panel("sh.600001", frame, _config(), start_date="2025-01-01")

    assert panel.empty


def test_suspension_does_not_consume_confirmation_window(monkeypatch) -> None:
    frame = _frame(19)
    frame.loc[1, "tradestatus"] = "0"
    _patch_signals(monkeypatch, frame, [0], [6])

    panel = build_mkf_dxbd_event_panel("sh.600001", frame, _config(), start_date="2025-01-01")

    assert len(panel) == 1
    assert panel.loc[0, "confirmation_lag"] == 5


def test_overlapping_mkf_signals_do_not_duplicate_same_entry(monkeypatch) -> None:
    frame = _frame(18)
    _patch_signals(monkeypatch, frame, [0, 1], [2])

    panel = build_mkf_dxbd_event_panel("sh.600001", frame, _config(), start_date="2025-01-01")

    assert len(panel) == 1
    assert panel.loc[0, "entry_date"] == frame.loc[3, "date"]


def test_report_is_isolated_from_original_mkf_v3(monkeypatch) -> None:
    frame = _frame(18)
    _patch_signals(monkeypatch, frame, [0], [0])
    panel = build_mkf_dxbd_event_panel("sh.600001", frame, _config(), start_date="2025-01-01")

    report = build_mkf_dxbd_report(
        panel=panel,
        code_list=["sh.600001"],
        code_list_sha256="abc",
        start_date="2025-01-01",
        end_date=None,
        workers=1,
    )

    assert report["research_only"] is True
    assert report["production_enabled"] is False
    assert report["watchlist_modified"] is False
    assert report["broker_orders_enabled"] is False
    assert report["original_mkf_v3_modified"] is False
    assert report["candidate_definition"]["dxbd_lag_stock_tradable_days"] == [0, 5]
    assert report["entry_definition"]["entry"] == "next stock-tradable day open after DXBD confirmation"
    assert report["horizons"]["T+1"]["n"] == 1
