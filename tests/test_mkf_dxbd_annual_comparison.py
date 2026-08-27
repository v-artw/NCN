from __future__ import annotations

import pandas as pd
import pytest

from ashare_edge_scout.pmkf_mkf.mkf_dxbd_annual_comparison import (
    aggregate_annual_comparison,
    build_annual_comparison_report,
    build_mkf_next_open_panel,
    build_stock_comparison_panels,
)


def _frame(rows: int = 16, start: str = "2025-01-01") -> pd.DataFrame:
    close = [100.0 + index for index in range(rows)]
    return pd.DataFrame({
        "date": pd.bdate_range(start, periods=rows),
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


def test_mkf_baseline_enters_next_open_and_t1_starts_after_entry(monkeypatch) -> None:
    frame = _frame()
    signal = pd.Series(False, index=frame.index)
    signal.iloc[0] = True
    monkeypatch.setattr(
        "ashare_edge_scout.pmkf_mkf.mkf_dxbd_annual_comparison.mkf_red_blue_cross20_green_exit_under80_mask",
        lambda _: signal,
    )

    panel = build_mkf_next_open_panel("sh.600001", frame, _config())

    assert len(panel) == 1
    assert panel.loc[0, "entry_date"] == frame.loc[1, "date"]
    assert panel.loc[0, "entry_open"] == frame.loc[1, "open"]
    assert panel.loc[0, "date_t1"] == frame.loc[2, "date"]
    assert panel.loc[0, "ret_t1_close"] == pytest.approx(frame.loc[2, "close"] / frame.loc[1, "open"] - 1.0)


def test_annual_grouping_uses_entry_year_across_year_boundary(monkeypatch) -> None:
    frame = _frame(start="2025-12-30")
    signal = pd.Series(False, index=frame.index)
    signal.iloc[1] = True
    monkeypatch.setattr(
        "ashare_edge_scout.pmkf_mkf.mkf_dxbd_annual_comparison.mkf_red_blue_cross20_green_exit_under80_mask",
        lambda _: signal,
    )
    baseline = build_mkf_next_open_panel("sh.600001", frame, _config(), start_date="2025-01-01")
    empty_delayed = pd.DataFrame(columns=["code", "entry_date", *[f"ret_t{h}_close" for h in range(1, 11)]])
    empty_matched = pd.DataFrame(columns=[
        "code", "delayed_entry_date", "immediate_entry_date",
        *[name for h in range(1, 11) for name in (f"delayed_ret_t{h}_close", f"immediate_ret_t{h}_close")],
    ])

    result = aggregate_annual_comparison(baseline, empty_delayed, empty_matched)

    assert baseline.loc[0, "mkf_date"].year == 2025
    assert baseline.loc[0, "entry_date"].year == 2026
    assert result["primary_comparison"]["year_2026"]["T+1"]["mkf_v3_baseline"]["n"] == 1
    assert "year_2025" not in result["primary_comparison"]


def test_primary_and_matched_deltas_are_separate() -> None:
    baseline = pd.DataFrame({
        "code": ["sh.600001", "sh.600002"],
        "entry_date": pd.to_datetime(["2025-01-02", "2025-01-02"]),
        "ret_t1_close": [0.10, -0.10],
    })
    delayed = pd.DataFrame({
        "code": ["sh.600001"],
        "entry_date": pd.to_datetime(["2025-01-06"]),
        "ret_t1_close": [0.20],
    })
    matched = pd.DataFrame({
        "code": ["sh.600001"],
        "delayed_entry_date": pd.to_datetime(["2025-01-06"]),
        "immediate_entry_date": pd.to_datetime(["2025-01-02"]),
        "delayed_ret_t1_close": [0.20],
        "immediate_ret_t1_close": [0.10],
    })
    for horizon in range(2, 11):
        baseline[f"ret_t{horizon}_close"] = pd.NA
        delayed[f"ret_t{horizon}_close"] = pd.NA
        matched[f"delayed_ret_t{horizon}_close"] = pd.NA
        matched[f"immediate_ret_t{horizon}_close"] = pd.NA

    result = aggregate_annual_comparison(baseline, delayed, matched)
    primary = result["primary_comparison"]["year_2025"]["T+1"]
    timing = result["matched_timing_diagnostic"]["year_2025"]["T+1"]

    assert primary["mkf_v3_baseline"]["n"] == 2
    assert primary["mkf_plus_dxbd"]["n"] == 1
    assert primary["dxbd_minus_baseline"]["mean_return"] == pytest.approx(0.20)
    assert timing["matched_immediate_mkf_entry"]["n"] == 1
    assert timing["delayed_minus_immediate"]["mean_return"] == pytest.approx(0.10)


def test_stock_panels_pair_by_originating_mkf_event(monkeypatch) -> None:
    frame = _frame()
    mkf_date = frame.loc[0, "date"]
    baseline = pd.DataFrame({
        "code": ["sh.600001"], "mkf_date": [mkf_date], "entry_date": [frame.loc[1, "date"]],
        **{f"ret_t{h}_close": [h / 100.0] for h in range(1, 11)},
    })
    delayed = pd.DataFrame({
        "code": ["sh.600001"], "mkf_date": [mkf_date], "dxbd_confirmation_date": [frame.loc[2, "date"]],
        "confirmation_lag": [2], "entry_date": [frame.loc[3, "date"]],
        **{f"ret_t{h}_close": [(h + 1) / 100.0] for h in range(1, 11)},
    })
    monkeypatch.setattr(
        "ashare_edge_scout.pmkf_mkf.mkf_dxbd_annual_comparison.build_mkf_next_open_panel",
        lambda *args, **kwargs: baseline,
    )
    monkeypatch.setattr(
        "ashare_edge_scout.pmkf_mkf.mkf_dxbd_annual_comparison.build_mkf_dxbd_event_panel",
        lambda *args, **kwargs: delayed,
    )

    _, _, matched = build_stock_comparison_panels("sh.600001", frame, _config())

    assert len(matched) == 1
    assert matched.loc[0, "immediate_entry_date"] == frame.loc[1, "date"]
    assert matched.loc[0, "delayed_entry_date"] == frame.loc[3, "date"]
    assert matched.loc[0, "immediate_ret_t1_close"] == pytest.approx(0.01)
    assert matched.loc[0, "delayed_ret_t1_close"] == pytest.approx(0.02)


def test_stock_comparison_returns_stable_empty_matched_schema(monkeypatch) -> None:
    frame = _frame()
    empty_baseline = pd.DataFrame(columns=["code", "mkf_date", "entry_date"])
    empty_delayed = pd.DataFrame(columns=["code", "mkf_date", "entry_date"])
    monkeypatch.setattr(
        "ashare_edge_scout.pmkf_mkf.mkf_dxbd_annual_comparison.build_mkf_next_open_panel",
        lambda *args, **kwargs: empty_baseline,
    )
    monkeypatch.setattr(
        "ashare_edge_scout.pmkf_mkf.mkf_dxbd_annual_comparison.build_mkf_dxbd_event_panel",
        lambda *args, **kwargs: empty_delayed,
    )

    _, _, matched = build_stock_comparison_panels("sh.600001", frame, _config())

    assert matched.empty
    assert "delayed_ret_t10_close" in matched
    assert "immediate_ret_t10_close" in matched


def test_report_metadata_preserves_original_mkf_v3() -> None:
    baseline = pd.DataFrame({
        "code": ["sh.600001"], "entry_date": pd.to_datetime(["2025-01-02"]),
        **{f"ret_t{h}_close": [0.01] for h in range(1, 11)},
    })
    delayed = baseline.copy()
    matched = pd.DataFrame({
        "code": ["sh.600001"],
        "delayed_entry_date": pd.to_datetime(["2025-01-02"]),
        "immediate_entry_date": pd.to_datetime(["2025-01-02"]),
        **{f"delayed_ret_t{h}_close": [0.01] for h in range(1, 11)},
        **{f"immediate_ret_t{h}_close": [0.01] for h in range(1, 11)},
    })

    report = build_annual_comparison_report(
        baseline=baseline, delayed=delayed, matched=matched,
        code_list=["sh.600001"], code_list_sha256="abc",
        start_date="2025-01-01", end_date=None, workers=1,
    )

    assert report["research_only"] is True
    assert report["production_enabled"] is False
    assert report["original_mkf_v3_modified"] is False
    assert report["primary_definition"]["annual_grouping"] == "entry_year"
    assert report["matched_diagnostic_definition"]["annual_grouping"] == "delayed_DXBD_entry_year"
