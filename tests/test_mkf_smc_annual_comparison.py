from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from ashare_edge_scout.pmkf_mkf.mkf_smc_annual_comparison import (
    aggregate_mkf_smc_comparison,
    build_mkf_smc_report,
    build_smc_next_open_panel,
    production_smc_mask,
)
from ashare_edge_scout.stock_selector import evaluate_stock


CONFIG = {
    "universe": {
        "include_prefixes": ["sh.600"],
        "exclude_st": True,
        "min_listing_days": 20,
        "min_close_cny": 5.0,
        "max_close_cny": 80.0,
        "min_adv20_cny": 100_000_000.0,
        "min_trading_days_60": 20,
        "block_limit_up_entries": True,
        "block_suspensions": True,
    }
}


def _records(rows: int = 85) -> list[dict[str, object]]:
    dates = pd.bdate_range("2025-10-01", periods=rows)
    closes = [10.0 + index * 0.05 for index in range(rows)]
    result = []
    for index, (bar_date, close) in enumerate(zip(dates, closes, strict=True)):
        result.append({
            "code": "sh.600001", "date": bar_date.date(), "open": close - 0.03,
            "high": close + 0.08, "low": close - 0.08, "close": close,
            "preclose": closes[index - 1] if index else close,
            "volume": 20_000_000.0, "amount": 200_000_000.0, "turn": 2.0,
            "tradestatus": "1", "isST": "0",
        })
    signal_index = 69
    result[signal_index - 2]["high"] = max(float(result[signal_index - 2]["open"]), float(result[signal_index - 2]["close"])) + 0.05
    result[signal_index]["low"] = float(result[signal_index - 2]["high"]) * 1.04
    result[signal_index]["open"] = float(result[signal_index]["low"]) + 0.05
    result[signal_index]["close"] = float(result[signal_index]["low"]) + 0.15
    result[signal_index]["high"] = float(result[signal_index]["low"]) + 0.25
    result[signal_index]["preclose"] = result[signal_index - 1]["close"]
    return result


def test_historical_smc_mask_matches_production_selector_latest_row() -> None:
    records = _records(70)
    frame = pd.DataFrame(records)
    frame["date"] = pd.to_datetime(frame["date"])
    frame = frame.reset_index(drop=True)
    as_of = records[-1]["date"]

    production = evaluate_stock("sh.600001", records, CONFIG, as_of)
    historical = production_smc_mask("sh.600001", frame, CONFIG)

    assert production is not None
    assert bool(historical.iloc[-1]) is True

    st_records = [dict(row) for row in records]
    st_records[-1]["isST"] = "1"
    st_frame = pd.DataFrame(st_records)
    st_frame["date"] = pd.to_datetime(st_frame["date"])
    assert evaluate_stock("sh.600001", st_records, CONFIG, as_of) is None
    assert bool(production_smc_mask("sh.600001", st_frame, CONFIG).iloc[-1]) is False


def test_smc_next_open_and_t1_alignment(monkeypatch) -> None:
    frame = pd.DataFrame(_records())
    frame["date"] = pd.to_datetime(frame["date"])
    fake = pd.Series(False, index=frame.index)
    fake.iloc[69] = True
    monkeypatch.setattr(
        "ashare_edge_scout.pmkf_mkf.mkf_smc_annual_comparison.production_smc_mask",
        lambda code, data, config: fake.reindex(data.index, fill_value=False),
    )

    panel = build_smc_next_open_panel("sh.600001", frame, CONFIG, start_date="2021-01-01")

    assert len(panel) == 1
    assert panel.loc[0, "signal_date"] == frame.loc[69, "date"]
    assert panel.loc[0, "entry_date"] == frame.loc[70, "date"]
    assert panel.loc[0, "entry_open"] == frame.loc[70, "open"]
    assert panel.loc[0, "date_t1"] == frame.loc[71, "date"]
    assert panel.loc[0, "ret_t1_close"] == pytest.approx(frame.loc[71, "close"] / frame.loc[70, "open"] - 1.0)
    assert panel.loc[0, "date_t10"] == frame.loc[80, "date"]


def test_suspension_is_skipped_for_entry_and_horizon(monkeypatch) -> None:
    frame = pd.DataFrame(_records())
    frame["date"] = pd.to_datetime(frame["date"])
    frame.loc[70, "tradestatus"] = "0"
    fake = pd.Series(False, index=frame.index)
    fake.iloc[69] = True
    monkeypatch.setattr(
        "ashare_edge_scout.pmkf_mkf.mkf_smc_annual_comparison.production_smc_mask",
        lambda code, data, config: fake.reindex(data.index, fill_value=False),
    )

    panel = build_smc_next_open_panel("sh.600001", frame, CONFIG)

    assert panel.loc[0, "entry_date"] == frame.loc[71, "date"]
    assert panel.loc[0, "date_t1"] == frame.loc[72, "date"]


def test_annual_comparison_uses_entry_year() -> None:
    mkf = pd.DataFrame({
        "code": ["sh.600001"], "entry_date": pd.to_datetime(["2025-12-31"]),
        **{f"ret_t{h}_close": [0.01] for h in range(1, 11)},
    })
    smc = pd.DataFrame({
        "code": ["sh.600002"], "entry_date": pd.to_datetime(["2026-01-02"]),
        **{f"ret_t{h}_close": [0.02] for h in range(1, 11)},
    })

    report = aggregate_mkf_smc_comparison(mkf, smc)

    assert report["comparisons"]["year_2025"]["T+1"]["mkf_v3"]["n"] == 1
    assert report["comparisons"]["year_2025"]["T+1"]["production_smc"]["n"] == 0
    assert report["comparisons"]["year_2026"]["T+1"]["production_smc"]["n"] == 1


def test_report_metadata_preserves_both_production_strategies() -> None:
    frame = pd.DataFrame({
        "code": ["sh.600001"], "entry_date": pd.to_datetime(["2026-01-02"]), "status": ["mature"],
        **{f"ret_t{h}_close": [0.01] for h in range(1, 11)},
    })
    report = build_mkf_smc_report(
        mkf=frame, smc=frame.copy(), code_list=["sh.600001"], code_list_sha256="abc",
        start_date="2021-01-01", end_date=None, workers=1,
    )

    assert report["research_only"] is True
    assert report["production_enabled"] is False
    assert report["original_mkf_v3_modified"] is False
    assert report["production_smc_modified"] is False
    assert report["strategy_definitions"]["production_smc"].endswith("[smc_medium_buy]")
    assert report["execution_definition"]["annual_grouping"] == "entry_year"
