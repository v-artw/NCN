from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from ashare_edge_scout.signal_scoring import apply_hard_gates
from scripts.evaluate_joint_strategy import _stock_counts


def _config() -> dict:
    return {
        "universe": {
            "include_prefixes": ["sh.600"],
            "exclude_st": True,
            "min_listing_days": 252,
            "min_close_cny": 5.0,
            "max_close_cny": 80.0,
            "min_adv20_cny": 100_000_000.0,
            "min_trading_days_60": 55,
            "block_limit_up_entries": True,
            "block_suspensions": True,
        },
        "setup": {
            "trend": {
                "fast_ma": 20,
                "slow_ma": 60,
                "ma_slope_lookback": 5,
                "min_return_20d": 0.03,
                "max_return_20d": 0.30,
            },
            "pullback": {
                "high_lookback": 10,
                "min_drawdown_from_high": 0.03,
                "max_drawdown_from_high": 0.10,
                "min_low_to_ma60_ratio": 0.98,
            },
        },
        "research_market_regime": {
            "enforcement": "none",
            "max_5d_benchmark_drawdown": -0.03,
        },
    }


def _frame() -> pd.DataFrame:
    rows = []
    start = date(2020, 3, 1)
    for index in range(340):
        close = 10.0 + index * 0.002
        rows.append({
            "date": start + timedelta(days=index),
            "code": "sh.600001",
            "open": close - 0.02,
            "high": close + 0.05,
            "low": close - 0.05,
            "close": close,
            "preclose": close - 0.002,
            "volume": 10_000_000.0,
            "amount": 120_000_000.0,
            "turn": 1.0,
            "tradestatus": "1",
            "isST": "0",
        })
    return pd.DataFrame(rows)


def test_research_admitted_baseline_matches_production_gate_on_evaluation_date(tmp_path):
    frame = _frame()
    stock_path = tmp_path / "sh.600001.parquet"
    frame.to_parquet(stock_path, index=False)
    config = _config()
    signal_index = 330
    signal_date = frame.at[signal_index, "date"].isoformat()

    passed, failures = apply_hard_gates(
        "sh.600001",
        frame.iloc[: signal_index + 1].to_dict("records"),
        config,
    )
    result = _stock_counts((str(stock_path), config, {signal_date: True}, signal_date, signal_date))

    assert passed, failures
    assert result["counts"]["admitted_baseline"]["calibration"][0] == 1


def test_research_and_production_both_reject_low_adv20(tmp_path):
    frame = _frame()
    frame.loc[frame.index[-20:], "amount"] = 50_000_000.0
    stock_path = tmp_path / "sh.600001.parquet"
    frame.to_parquet(stock_path, index=False)
    config = _config()
    signal_index = 330
    signal_date = frame.at[signal_index, "date"].isoformat()
    frame.loc[signal_index - 19:signal_index, "amount"] = 50_000_000.0
    frame.to_parquet(stock_path, index=False)

    passed, failures = apply_hard_gates(
        "sh.600001",
        frame.iloc[: signal_index + 1].to_dict("records"),
        config,
    )
    result = _stock_counts((str(stock_path), config, {signal_date: True}, signal_date, signal_date))

    assert not passed
    assert "adv20_too_low" in failures
    assert result["counts"]["admitted_baseline"]["calibration"][0] == 0
