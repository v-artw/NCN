from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from ashare_edge_scout.research_a_class_target_touch import (
    aggregate_a_class_target_touch,
    build_a_class_target_touch_panel,
    build_a_class_target_touch_report,
)
from scripts.evaluate_a_class_target_touch import _atomic_json, parse_args


CONFIG = {
    "universe": {
        "include_prefixes": ["sh.600"],
        "exclude_st": True,
        "min_listing_days": 20,
        "min_close_cny": 5.0,
        "max_close_cny": 80.0,
        "min_adv20_cny": 0.0,
        "min_trading_days_60": 20,
        "block_limit_up_entries": False,
        "block_suspensions": True,
    }
}


def _a_class_frame(extra_tradable: int = 7) -> pd.DataFrame:
    closes = [10.0] * 10 + [12.0] * 5 + [9.0] * 54 + [10.35]
    closes.extend([10.4] * extra_tradable)
    dates = pd.bdate_range("2026-01-01", periods=len(closes))
    rows = []
    for index, (bar_date, close) in enumerate(zip(dates, closes, strict=True)):
        volume = 1_400_000.0 if index == 69 else 1_000_000.0
        high = close + 0.2
        low = close - 0.2
        open_ = close - 0.1
        if index == 69:
            low = 9.0
            high = 11.2
            open_ = 9.9
        rows.append({
            "date": bar_date,
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "preclose": closes[index - 1] if index else close,
            "volume": volume,
            "amount": 200_000_000.0,
            "turn": 2.0,
            "tradestatus": "1",
            "isST": "0",
        })
    return pd.DataFrame(rows)


def test_a_class_target_touch_signal_is_causal() -> None:
    frame = _a_class_frame()
    panel = build_a_class_target_touch_panel("sh.600001", frame, CONFIG, start_date="2026-04-08")
    changed = frame.copy()
    changed.loc[70:, ["open", "high", "low", "close"]] *= 5.0
    changed_panel = build_a_class_target_touch_panel("sh.600001", changed, CONFIG, start_date="2026-04-08")

    assert bool(panel.loc[panel["signal_date"].eq(frame.loc[69, "date"]), "selected"].iloc[0])
    assert panel.loc[0, "selected"] == changed_panel.loc[0, "selected"]


def test_a_class_target_touch_excludes_entry_day_and_tracks_risk_first() -> None:
    frame = _a_class_frame()
    frame.loc[70, "high"] = 20.0
    frame.loc[71, "low"] = 9.0
    frame.loc[72, "high"] = 10.8
    panel = build_a_class_target_touch_panel("sh.600001", frame, CONFIG, start_date="2026-04-08")
    row = panel.loc[panel["signal_date"].eq(frame.loc[69, "date"])].iloc[0]

    assert row["entry_date"] == frame.loc[70, "date"]
    assert bool(row["target_touched"])
    assert bool(row["risk_first_3pct"])


def test_a_class_aggregate_uses_same_entry_date_baseline() -> None:
    rows = []
    for index in range(150):
        rows.append({
            "code": f"sh.{600000 + index}",
            "signal_date": pd.Timestamp("2026-01-01"),
            "entry_date": pd.Timestamp("2026-01-02"),
            "admitted": True,
            "selected": index == 0,
            "status": "mature",
            "target_touched": index % 2 == 0,
            "risk_first_3pct": False,
            "max_drawdown": -0.01,
            "max_excursion": 0.04,
        })
    result = aggregate_a_class_target_touch(pd.DataFrame(rows))

    metric = result["metrics"]["full_2021_present"]
    assert metric["n"] == 1
    assert metric["same_entry_date_baseline"]["win_rate"] == pytest.approx(0.5)
    assert result["mature_candidates_on_valid_baseline_dates"] == 1


def test_a_class_report_contract() -> None:
    panel = pd.DataFrame({
        "code": ["sh.600001"],
        "signal_date": pd.to_datetime(["2026-01-01"]),
        "entry_date": pd.to_datetime(["2026-01-02"]),
        "admitted": [True],
        "selected": [True],
        "status": ["mature"],
        "target_touched": pd.array([True], dtype="boolean"),
        "risk_first_3pct": pd.array([False], dtype="boolean"),
        "max_drawdown": [-0.01],
        "max_excursion": [0.04],
    })
    report = build_a_class_target_touch_report(panel=panel, code_list=["sh.600001"], code_list_sha256="abc", start_date="2026-01-01", end_date=None, workers=4)

    assert report["schema_version"] == "ncn_a_class_t_open_target_touch_v1"
    assert report["classification_only"] is True
    assert report["production_enabled"] is False
    assert "P&L" in " ".join(report["limitations"])


def test_a_class_validation_parse_args_and_atomic_json(tmp_path: Path) -> None:
    args = parse_args(["--output", str(tmp_path / "out.json"), "--workers", "12"])
    assert args.workers == 12
    with pytest.raises(SystemExit):
        parse_args(["--output", str(tmp_path / "out.json"), "--workers", "0"])
    output = tmp_path / "report.json"
    _atomic_json(output, {"schema_version": "ncn_a_class_t_open_target_touch_v1", "value": 1})
    assert json.loads(output.read_text()) == {"schema_version": "ncn_a_class_t_open_target_touch_v1", "value": 1}
