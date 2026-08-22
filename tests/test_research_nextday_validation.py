from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from ashare_edge_scout.research_nextday_validation import (
    CANDIDATE_REGISTRY,
    build_nextday_panel,
    build_report,
    aggregate_nextday_metrics,
    candlestick_masks,
    evaluate_stability,
)
from scripts.evaluate_nextday_validation import _atomic_json, parse_args


def _config() -> dict[str, object]:
    return {
        "universe": {
            "include_prefixes": ["sh.600"],
            "exclude_st": True,
            "min_listing_days": 1,
            "min_close_cny": 1.0,
            "max_close_cny": 1000.0,
            "block_suspensions": True,
            "min_trading_days_60": 1,
            "min_adv20_cny": 0.0,
            "block_limit_up_entries": False,
        }
    }


def _bars(closes: list[float], *, start: str = "2024-12-20") -> pd.DataFrame:
    dates = pd.bdate_range(start, periods=len(closes))
    return pd.DataFrame({
        "date": dates,
        "open": [value * 0.99 for value in closes],
        "high": [value * 1.01 for value in closes],
        "low": [value * 0.98 for value in closes],
        "close": closes,
        "preclose": [closes[0], *closes[:-1]],
        "volume": [1_000_000.0] * len(closes),
        "amount": [10_000_000.0] * len(closes),
        "tradestatus": ["1"] * len(closes),
        "isST": ["0"] * len(closes),
    })


def test_nextday_label_compares_target_close_with_origin_close() -> None:
    frame = _bars([10.0, 11.0, 10.5])
    panel = build_nextday_panel("sh.600001", frame, _config(), start_date="2024-12-20")
    row = panel.iloc[0]
    assert row["origin_date"] == pd.Timestamp("2024-12-20")
    assert row["target_date"] == pd.Timestamp("2024-12-23")
    assert row["target_close"] == 11.0
    assert bool(row["target_up"]) is True
    assert bool(row["target_down"]) is False


def test_candidate_masks_do_not_use_target_or_future_bars() -> None:
    frame = _bars([10.0, 9.8, 9.6, 9.4, 9.2, 9.5, 9.8, 10.1])
    panel = build_nextday_panel("sh.600001", frame, _config(), start_date="2024-12-20")
    changed = frame.copy()
    changed.loc[1:, ["open", "high", "low", "close"]] *= 5.0
    changed.loc[:, "preclose"] = [changed.loc[0, "close"], *changed["close"].iloc[:-1].tolist()]
    changed_panel = build_nextday_panel("sh.600001", changed, _config(), start_date="2024-12-20")
    candidate_columns = [name for name in CANDIDATE_REGISTRY if name in panel]
    assert panel.loc[0, candidate_columns].tolist() == changed_panel.loc[0, candidate_columns].tolist()


def test_origin_suspension_blocks_candidate_and_target_skips_suspension() -> None:
    frame = _bars([10.0, 10.5, 10.7, 10.8, 10.9, 11.0, 11.1])
    frame.loc[0, "tradestatus"] = "0"
    panel = build_nextday_panel("sh.600001", frame, _config(), start_date="2024-12-20")
    assert not bool(panel.loc[0, "admitted"])

    frame = _bars([10.0, 10.5, 10.7, 10.8, 10.9, 11.0, 11.1])
    frame.loc[1, "tradestatus"] = "0"
    panel = build_nextday_panel("sh.600001", frame, _config(), start_date="2024-12-20")
    assert panel.loc[0, "target_status"] == "mature"
    assert panel.loc[0, "target_date"] == frame.loc[2, "date"]


def test_same_target_date_baseline_is_signal_count_weighted() -> None:
    rows = []
    for index in range(150):
        rows.append({
            "code": f"a{index}",
            "origin_date": pd.Timestamp("2025-01-01"),
            "date": pd.Timestamp("2025-01-01"),
            "target_date": pd.Timestamp("2025-01-02"),
            "trading_index": 0,
            "admitted": True,
            "target_status": "mature",
            "target_up": index == 0,
            "target_down": index != 0,
            "mhpg_buy": index < 2,
        })
    for index in range(150):
        rows.append({
            "code": f"b{index}",
            "origin_date": pd.Timestamp("2025-01-02"),
            "date": pd.Timestamp("2025-01-02"),
            "target_date": pd.Timestamp("2025-01-03"),
            "trading_index": 1,
            "admitted": True,
            "target_status": "mature",
            "target_up": index < 100,
            "target_down": index >= 100,
            "mhpg_buy": index == 0,
        })
    panel = pd.DataFrame(rows)
    panel["target_up"] = pd.array(panel["target_up"], dtype="boolean")
    panel["target_down"] = pd.array(panel["target_down"], dtype="boolean")
    metrics = aggregate_nextday_metrics(panel)
    summary = metrics["primary_metrics"]["mhpg_buy"]["full_available_history"]
    assert summary["n"] == 3
    assert summary["hits"] == 2
    assert summary["same_target_date_baseline"]["precision"] == pytest.approx((2 * (1 / 150) + 1 * (100 / 150)) / 3)


def test_candidate_registry_marks_underdefined_entries() -> None:
    assert CANDIDATE_REGISTRY["mhpg_buy"].primary_selectable is True
    assert CANDIDATE_REGISTRY["alphagpt_cross_001"].implementability == "objective"
    assert CANDIDATE_REGISTRY["unnamed_kd_block"].implementability == "underdefined"
    assert CANDIDATE_REGISTRY["candle_hammer"].source == "Japanese Candlestick Charting Techniques"


def test_flat_target_close_is_a_miss_in_both_directions() -> None:
    panel = build_nextday_panel("sh.600001", _bars([10.0, 10.0]), _config(), start_date="2024-12-20")
    assert bool(panel.loc[0, "target_up"]) is False
    assert bool(panel.loc[0, "target_down"]) is False


def test_candlestick_project_patterns_are_causal() -> None:
    frame = _bars([10.0, 9.8, 9.6, 9.4, 9.5, 20.0, 30.0])
    frame.loc[4, ["open", "high", "low", "close"]] = [9.45, 10.4, 9.4, 9.5]
    masks = candlestick_masks(frame)
    changed = frame.copy()
    changed.loc[5:, ["open", "high", "low", "close"]] *= 10.0
    changed_masks = candlestick_masks(changed)
    assert bool(masks["candle_inverted_hammer"].iloc[4])
    assert bool(changed_masks["candle_inverted_hammer"].iloc[4]) == bool(masks["candle_inverted_hammer"].iloc[4])


def test_parse_args_defaults_to_full_universe_and_rejects_bad_workers(tmp_path: Path) -> None:
    args = parse_args(["--output", str(tmp_path / "out.json")])
    assert args.start_date == "1900-01-01"
    assert not hasattr(args, "max_codes")
    with pytest.raises(SystemExit):
        parse_args(["--output", str(tmp_path / "out.json"), "--workers", "0"])
    with pytest.raises(SystemExit):
        parse_args(["--output", str(tmp_path / "out.json"), "--workers", "9"])


def test_atomic_json_writes_valid_json(tmp_path: Path) -> None:
    output = tmp_path / "report.json"
    _atomic_json(output, {"schema_version": "ncn_nextday_validation_v1", "value": 1})
    assert json.loads(output.read_text()) == {"schema_version": "ncn_nextday_validation_v1", "value": 1}


def test_build_report_contract() -> None:
    panel = pd.DataFrame({
        "code": ["a"],
        "origin_date": pd.to_datetime(["2025-01-01"]),
        "date": pd.to_datetime(["2025-01-01"]),
        "target_date": pd.to_datetime(["2025-01-02"]),
        "trading_index": [0],
        "admitted": [True],
        "target_status": ["mature"],
        "target_up": pd.array([True], dtype="boolean"),
        "target_down": pd.array([False], dtype="boolean"),
        "mhpg_buy": [True],
    })
    report = build_report(panel=panel, code_list=["sh.600001"], code_list_sha256="abc", start_date="2021-01-01", end_date=None, workers=1)
    assert report["schema_version"] == "ncn_next_trading_day_direction_v2"
    assert report["classification_only"] is True
    assert report["production_enabled"] is False
    assert report["alignment"]["label_anchor"] == "target_date_close_vs_origin_date_close"


def test_stability_requires_both_periods_and_complete_audit_years() -> None:
    def metric(n: int, hits: int, baseline: float) -> dict[str, object]:
        from ashare_edge_scout.research_v2 import summarize_counts
        value = summarize_counts(n, hits)
        value.update({
            "target_dates": 130,
            "same_target_date_baseline": {"weighted_n": n, "weighted_hits": n * baseline, "precision": baseline},
            "precision_lift": hits / n - baseline,
        })
        return value

    yearly = {f"year_{year}": metric(400, 240, 0.50) for year in range(2021, 2027)}
    assert evaluate_stability(yearly, 2026)["passed"] is True
    yearly["year_2024"] = metric(400, 200, 0.50)
    decision = evaluate_stability(yearly, 2026)
    assert decision["passed"] is False
    assert "year_2024:lift_not_positive" in decision["failure_codes"]
