from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd
import pytest

from ashare_edge_scout.a_class_selector import (
    AClassSelectionRow,
    _atomic_publish,
    evaluate_a_class_stock,
    run_a_class_selection,
)
from scripts import select_a_class_stocks
from scripts.select_a_class_stocks import parse_args


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


def _records(*, long_upper: bool = False, hot_volume: bool = False, high_position: bool = False) -> list[dict[str, object]]:
    dates = pd.bdate_range("2026-01-01", periods=70)
    closes = [10.0] * 10 + [12.0] * 5 + [9.0] * 54 + [10.35]
    if high_position:
        closes = [8.0 + index * 0.05 for index in range(69)] + [11.6]
    rows = []
    for index, (bar_date, close) in enumerate(zip(dates, closes, strict=True)):
        volume = 1_000_000.0
        if index == len(closes) - 1:
            volume = 4_000_000.0 if hot_volume else 1_400_000.0
        high = close + 0.2
        low = close - 0.2
        open_ = close - 0.1
        if index == len(closes) - 1:
            low = 9.0
            high = 12.5 if long_upper else 11.2
            open_ = 9.9
        rows.append({
            "code": "sh.600001",
            "date": bar_date.date(),
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
    return rows


def test_a_class_selector_selects_base_breakout_without_smc_gap() -> None:
    records = _records()
    row = evaluate_a_class_stock("sh.600001", records, CONFIG, records[-1]["date"])

    assert row is not None
    assert row.selection_reason == "a_class_base_breakout_v1_and_hard_gates"
    assert row.range_position_60d_pct <= 55.0
    assert row.range_position_120d_pct <= 65.0
    assert row.breakout_margin_pct > 0.3
    assert "prior_box_breakout" in row.a_class_reason


def test_a_class_selector_is_causal_at_manual_as_of() -> None:
    records = _records()
    as_of = records[-1]["date"]
    expected = evaluate_a_class_stock("sh.600001", records, CONFIG, as_of)
    future = dict(records[-1])
    future["date"] = (pd.Timestamp(as_of) + pd.offsets.BDay()).date()
    future["open"] = future["high"] = future["low"] = future["close"] = 70.0
    future["preclose"] = records[-1]["close"]

    assert evaluate_a_class_stock("sh.600001", [*records, future], CONFIG, as_of) == expected


def test_a_class_selector_keeps_existing_hard_gates() -> None:
    records = _records()
    records[-1]["isST"] = "1"

    assert evaluate_a_class_stock("sh.600001", records, CONFIG, records[-1]["date"]) is None


@pytest.mark.parametrize("records", [_records(long_upper=True), _records(hot_volume=True), _records(high_position=True)])
def test_a_class_selector_rejects_risky_or_hot_setups(records: list[dict[str, object]]) -> None:
    assert evaluate_a_class_stock("sh.600001", records, CONFIG, records[-1]["date"]) is None


def test_a_class_atomic_publish_keeps_all_rows_and_refuses_overwrite(tmp_path: Path) -> None:
    rows = [
        AClassSelectionRow("sh.600001", "2026-04-09", 10.0, 2e8, 2.0, 40.0, 45.0, 50.0, 2.0, 4.0, -10.0, 1.4, 0.8, 0.1, 1.0, "x"),
        AClassSelectionRow("sh.600002", "2026-04-09", 11.0, 1e8, 3.0, 42.0, 46.0, 52.0, 3.0, 5.0, -9.0, 1.5, 0.7, 0.2, 1.1, "y"),
    ]
    directory = _atomic_publish(tmp_path, "run-1", rows, {"candidate_count": 2, "published_at_utc": "2026-04-09T00:00:00+00:00"})

    assert len(json.loads((directory / "candidates.json").read_text())) == 2
    assert json.loads((directory / "summary.json").read_text())["candidate_count"] == 2
    manifest = json.loads((directory / "manifest.json").read_text())
    assert manifest["schema_version"] == "ncn_a_class_selector_v1"
    timestamped_name = manifest["timestamped_candidates_csv"]
    assert re.fullmatch(r"a_class_candidates_\d{8}_\d{6}\.csv", timestamped_name)
    assert (directory / timestamped_name).read_bytes() == (directory / "candidates.csv").read_bytes()
    with pytest.raises(FileExistsError):
        _atomic_publish(tmp_path, "run-1", rows, {"candidate_count": 2})


def test_a_class_selection_reports_progress(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    data_root.mkdir()
    pd.DataFrame(_records()).to_parquet(data_root / "sh.600001.parquet", index=False)
    config_path = Path(__file__).parents[1] / "yaml" / "edge_scout_v1.yaml"
    events: list[tuple[int, int, int]] = []
    result = run_a_class_selection(
        data_root=data_root,
        config_path=config_path,
        output_root=tmp_path / "out",
        as_of=_records()[-1]["date"],
        run_id="a-class-progress",
        progress=lambda done, total, selected: events.append((done, total, selected)),
    )

    assert result.candidate_count >= 0
    assert events[-1][0:2] == (1, 1)
    summary = json.loads(result.summary_path.read_text())
    assert summary["schema_version"] == "ncn_a_class_selector_v1"
    assert summary["boundaries"]["orders_submitted"] is False


def test_a_class_cli_prints_table(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    data_root = tmp_path / "data"
    data_root.mkdir()
    pd.DataFrame(_records()).to_parquet(data_root / "sh.600001.parquet", index=False)
    config_path = Path(__file__).parents[1] / "yaml" / "edge_scout_v1.yaml"

    exit_code = select_a_class_stocks.main([
        "--data-root", str(data_root),
        "--config", str(config_path),
        "--output-root", str(tmp_path / "out"),
        "--as-of", _records()[-1]["date"].isoformat(),
        "--run-id", "a-class-cli",
        "--top", "1",
    ])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "selector=a_class_base_breakout_v1" in output
    assert "candidate_count=" in output


def test_a_class_cli_top_is_display_only_and_must_be_positive(tmp_path: Path) -> None:
    args = parse_args([
        "--data-root", str(tmp_path), "--config", "config.yaml",
        "--output-root", str(tmp_path / "out"), "--top", "3",
    ])
    assert args.top == 3
    with pytest.raises(SystemExit):
        parse_args([
            "--data-root", str(tmp_path), "--config", "config.yaml",
            "--output-root", str(tmp_path / "out"), "--top", "0",
        ])
