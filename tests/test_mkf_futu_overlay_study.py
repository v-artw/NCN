from __future__ import annotations

import pandas as pd
import pytest

from ashare_edge_scout.pmkf_mkf.mkf_futu_overlay_study import (
    OVERLAYS,
    aggregate_overlay_metrics,
    build_overlay_panel,
    build_overlay_report,
    evaluate_overlay_decisions,
)


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
        "amount": [200_000_000.0] * rows,
        "tradestatus": ["1"] * rows,
        "isST": ["0"] * rows,
    })


def _config() -> dict:
    return {
        "universe": {
            "include_prefixes": ["sh.600"], "exclude_st": True,
            "min_listing_days": 1, "min_close_cny": 1.0, "max_close_cny": 200.0,
            "min_adv20_cny": 0.0, "min_trading_days_60": 1,
            "block_limit_up_entries": False, "block_suspensions": True,
        }
    }


def test_overlay_panel_uses_same_row_subset_and_next_open(monkeypatch) -> None:
    frame = _frame()
    parent = pd.Series(False, index=frame.index)
    parent.iloc[[0, 1]] = True
    overlays = {name: pd.Series(False, index=frame.index) for name in OVERLAYS}
    overlays["kdj_trend_pro_buy"].iloc[0] = True
    overlays["dxbd_cross_zero"].iloc[1] = True
    monkeypatch.setattr(
        "ashare_edge_scout.pmkf_mkf.mkf_futu_overlay_study._masks",
        lambda code, data, config: (parent.reindex(data.index), {k: v.reindex(data.index) for k, v in overlays.items()}),
    )

    panel = build_overlay_panel("sh.600001", frame, _config())

    assert len(panel) == 2
    assert panel["kdj_trend_pro_buy"].tolist() == [True, False]
    assert panel["dxbd_cross_zero"].tolist() == [False, True]
    assert panel.loc[0, "entry_date"] == frame.loc[1, "date"]
    assert panel.loc[0, "date_t1"] == frame.loc[2, "date"]
    assert panel.loc[0, "ret_t1_close"] == pytest.approx(frame.loc[2, "close"] / frame.loc[1, "open"] - 1.0)


def test_suspension_does_not_consume_entry_or_horizon(monkeypatch) -> None:
    frame = _frame()
    frame.loc[1, "tradestatus"] = "0"
    parent = pd.Series(False, index=frame.index)
    parent.iloc[0] = True
    overlays = {name: parent.copy() for name in OVERLAYS}
    monkeypatch.setattr(
        "ashare_edge_scout.pmkf_mkf.mkf_futu_overlay_study._masks",
        lambda code, data, config: (parent.reindex(data.index), {k: v.reindex(data.index) for k, v in overlays.items()}),
    )

    panel = build_overlay_panel("sh.600001", frame, _config())

    assert panel.loc[0, "entry_date"] == frame.loc[2, "date"]
    assert panel.loc[0, "date_t1"] == frame.loc[3, "date"]


def _decision_panel(*, lift: bool) -> pd.DataFrame:
    rows = []
    for year in range(2021, 2027):
        for index in range(100):
            parent_win = index < 50
            overlay_member = index < 20
            overlay_win = index < (14 if lift else 8)
            row = {
                "code": f"c{year}{index:03d}",
                "signal_date": pd.Timestamp(year, 1, 2),
                "entry_date": pd.Timestamp(year, 1, 3),
                "status": "mature",
                **{name: overlay_member for name in OVERLAYS},
            }
            for horizon in range(1, 11):
                win = overlay_win if overlay_member else parent_win
                row[f"ret_t{horizon}_close"] = 0.02 if win else -0.02
                row[f"date_t{horizon}"] = pd.Timestamp(year, 1, 3) + pd.offsets.BDay(horizon)
            rows.append(row)
    return pd.DataFrame(rows)


def test_decision_rejects_small_or_unstable_lift() -> None:
    aggregated = aggregate_overlay_metrics(_decision_panel(lift=False))
    decision = evaluate_overlay_decisions(aggregated)

    assert decision["accepted_overlays"] == []
    assert decision["stop_direction"] is True
    for name in OVERLAYS:
        assert "t5_win_rate_lift_below_0.03" in decision["candidates"][name]["failure_codes"]


def test_decision_requires_retention_dates_and_codes_even_with_lift() -> None:
    aggregated = aggregate_overlay_metrics(_decision_panel(lift=True))
    decision = evaluate_overlay_decisions(aggregated)

    for name in OVERLAYS:
        failures = decision["candidates"][name]["failure_codes"]
        assert "t5_entry_dates_below_120" in failures


def test_report_metadata_keeps_mkf_unchanged() -> None:
    panel = _decision_panel(lift=False)
    report = build_overlay_report(
        panel=panel, code_list=["sh.600001"], code_list_sha256="abc",
        start_date="2021-01-01", end_date=None, workers=1,
    )

    assert report["research_only"] is True
    assert report["production_enabled"] is False
    assert report["original_mkf_v3_modified"] is False
    assert set(report["overlay_definitions"]) == set(OVERLAYS)
    assert report["execution_definition"]["primary_horizon"] == "T+5"
    assert report["decision"]["stop_rule"].startswith("If none pass")
