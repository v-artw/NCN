from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

import pandas as pd

from ashare_edge_scout.research_bullish_engulfing import aggregate, confirmed_at_t, context_at_t, engulfing_at_t


def _bar(open_: float, high: float, low: float, close: float, volume: float = 100.0, status: str = "1"):
    return {"open": open_, "high": high, "low": low, "close": close, "volume": volume, "tradestatus": status}


def _history() -> list[dict]:
    return [_bar(10 + i * 0.04, 10.2 + i * 0.04, 9.9 + i * 0.04, 10.1 + i * 0.04, 100) for i in range(70)]


def test_engulfing_and_next_close_confirmation_are_separate() -> None:
    bars = _history()
    bars[-2] = _bar(12.7, 12.8, 12.0, 12.2, 80)
    bars[-1] = _bar(12.1, 13.3, 12.0, 13.0, 160)
    assert context_at_t(bars, len(bars) - 1)
    assert engulfing_at_t(bars, len(bars) - 1)
    bars.append(_bar(13.0, 13.5, 12.8, 13.2, 170))
    assert confirmed_at_t(bars, len(bars) - 2)


@pytest.mark.parametrize("mutation", [
    lambda bars: bars[-1].update(close=12.69),
    lambda bars: bars[-2].update(close=12.69),
    lambda bars: bars[-1].update(volume=70),
])
def test_engulfing_boundaries(mutation) -> None:
    bars = _history()
    bars[-2] = _bar(12.7, 12.8, 12.0, 12.2, 80)
    bars[-1] = _bar(12.1, 13.3, 12.0, 13.0, 160)
    bars[-1]["low"] = 12.4
    mutation(bars)
    assert not engulfing_at_t(bars, len(bars) - 1)


def test_suspension_blocks_confirmation() -> None:
    bars = _history()
    bars[-2] = _bar(12.7, 12.8, 12.0, 12.2, 80)
    bars[-1] = _bar(12.1, 13.3, 12.4, 13.0, 160, "0")
    assert not engulfing_at_t(bars, len(bars) - 1)


def test_cli_worker_limit() -> None:
    path = Path(__file__).parents[1] / "scripts/evaluate_bullish_engulfing_confirmation.py"
    spec = importlib.util.spec_from_file_location("engulfing_cli", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.parse_args(["--output", "x", "--workers", "8"]).workers == 8
    with pytest.raises(SystemExit):
        module.parse_args(["--output", "x", "--workers", "9"])


def test_aggregate_handles_no_candidates_without_losing_date_type() -> None:
    rows = pd.DataFrame([
        {"code": f"c{number:03d}", "date": pd.Timestamp("2023-01-03"), "trading_index": 10, "label": number < 50, "candidate": False}
        for number in range(150)
    ])
    primary, all_origin = aggregate(rows)
    assert primary["selection_2023_2024"]["n"] == 0
    assert all_origin["selection_2023_2024"]["n"] == 0


def test_aggregate_does_not_require_unregistered_daily_baseline_size() -> None:
    rows = pd.DataFrame([
        {"code": "a", "date": pd.Timestamp("2023-01-03"), "trading_index": 10, "label": True, "candidate": True},
        {"code": "b", "date": pd.Timestamp("2023-01-03"), "trading_index": 10, "label": False, "candidate": False},
    ])
    primary, _ = aggregate(rows)
    assert primary["selection_2023_2024"]["n"] == 1
    assert primary["selection_2023_2024"]["same_date_baseline"]["precision"] == 0.5
