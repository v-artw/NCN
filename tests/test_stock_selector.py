from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from ashare_edge_scout.research_futu_ranking import tradable_indicator_values
from ashare_edge_scout.stock_selector import (
    StockSelectionRow,
    _atomic_publish,
    _compute_start_diagnostic,
    evaluate_stock,
    run_stock_selection,
)
from scripts import select_stocks
from scripts.select_stocks import parse_args


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


def _records() -> list[dict[str, object]]:
    dates = pd.bdate_range("2026-01-01", periods=70)
    closes = [10.0 + index * 0.05 for index in range(70)]
    rows = []
    for index, (bar_date, close) in enumerate(zip(dates, closes, strict=True)):
        rows.append({
            "code": "sh.600001",
            "date": bar_date.date(),
            "open": close - 0.03,
            "high": close + 0.08,
            "low": close - 0.08,
            "close": close,
            "preclose": closes[index - 1] if index else close,
            "volume": 20_000_000.0,
            "amount": 200_000_000.0,
            "turn": 2.0,
            "tradestatus": "1",
            "isST": "0",
        })
    rows[-3]["high"] = max(float(rows[-3]["open"]), float(rows[-3]["close"])) + 0.05
    rows[-1]["low"] = float(rows[-3]["high"]) * 1.04
    rows[-1]["open"] = float(rows[-1]["low"]) + 0.05
    rows[-1]["close"] = float(rows[-1]["low"]) + 0.15
    rows[-1]["high"] = float(rows[-1]["low"]) + 0.25
    rows[-1]["preclose"] = rows[-2]["close"]
    return rows


def test_selector_requires_smc_signal_and_existing_hard_gates() -> None:
    records = _records()
    as_of = records[-1]["date"]
    row = evaluate_stock("sh.600001", records, CONFIG, as_of)
    assert row is not None
    assert row.signal_date == as_of.isoformat()
    assert row.selection_reason == "smc_medium_buy_and_hard_gates"
    assert row.smc_gap_pct == pytest.approx(4.0)
    assert row.start_diagnostic_label in {"A", "B", "高位追涨", "未分类"}
    assert row.start_diagnostic_type
    assert 0.0 <= row.range_position_60d_pct <= 100.0

    st_records = [dict(value) for value in records]
    st_records[-1]["isST"] = "1"
    assert evaluate_stock("sh.600001", st_records, CONFIG, as_of) is None


def test_selector_is_causal_at_manual_as_of() -> None:
    records = _records()
    as_of = records[-1]["date"]
    expected = evaluate_stock("sh.600001", records, CONFIG, as_of)
    future = dict(records[-1])
    future["date"] = (pd.Timestamp(as_of) + pd.offsets.BDay()).date()
    future["open"] = future["high"] = future["low"] = future["close"] = 70.0
    future["preclose"] = records[-1]["close"]
    assert evaluate_stock("sh.600001", [*records, future], CONFIG, as_of) == expected


def test_risk_annotations_do_not_remove_primary_candidate(monkeypatch: pytest.MonkeyPatch) -> None:
    records = _records()
    import ashare_edge_scout.stock_selector as selector

    original = selector.expanded_futu_masks_from_values

    def annotated(values):
        masks = original(values)
        masks["kdj_trend_pro_sell"].iloc[-1] = True
        return masks

    monkeypatch.setattr(selector, "expanded_futu_masks_from_values", annotated)
    row = evaluate_stock("sh.600001", records, CONFIG, records[-1]["date"])
    assert row is not None
    assert "kdj_trend_pro_sell" in row.risk_warnings


def _diagnostic_from_closes(
    closes: list[float],
    *,
    signal_low: float | None = None,
    signal_high: float | None = None,
    volume: float = 2_000_000.0,
    baseline_volume: float = 1_000_000.0,
    smc_gap_pct: float = 1.0,
) -> dict[str, object]:
    dates = pd.bdate_range("2026-01-01", periods=len(closes))
    records = []
    for index, (bar_date, close) in enumerate(zip(dates, closes, strict=True)):
        day_volume = volume if index == len(closes) - 1 else baseline_volume
        low = signal_low if index == len(closes) - 1 and signal_low is not None else close - 0.2
        high = signal_high if index == len(closes) - 1 and signal_high is not None else close + 0.2
        records.append({
            "date": bar_date.date(),
            "open": close - 0.1,
            "high": high,
            "low": low,
            "close": close,
            "volume": day_volume,
            "tradestatus": "1",
        })
    frame = pd.DataFrame(records)
    values = tradable_indicator_values(frame)
    return _compute_start_diagnostic(frame, values, int(values.index[-1]), smc_gap_pct)


def test_start_diagnostic_marks_high_position_chase() -> None:
    diagnostic = _diagnostic_from_closes([10.0 + index * 0.2 for index in range(70)])

    assert diagnostic["start_diagnostic_label"] == "高位追涨"
    assert diagnostic["start_diagnostic_type"] == "high_position_chase"
    assert "pos20_ge_95" in str(diagnostic["start_diagnostic_reason"])


def test_start_diagnostic_marks_base_breakout_start() -> None:
    closes = [10.0] * 10 + [12.0] * 5 + [9.0] * 44 + [10.35]
    diagnostic = _diagnostic_from_closes(closes, signal_low=9.0, signal_high=11.3, volume=1_400_000.0)

    assert diagnostic["start_diagnostic_label"] == "A"
    assert diagnostic["start_diagnostic_type"] == "base_breakout_start"
    assert "prior_box_breakout" in str(diagnostic["start_diagnostic_reason"])


def test_start_diagnostic_marks_pullback_reacceleration() -> None:
    closes = [10.0 + index * 0.06 for index in range(50)]
    closes.extend([12.6, 12.3, 12.0, 11.7, 11.6, 11.8, 12.0, 12.2, 12.4, 12.65])
    diagnostic = _diagnostic_from_closes(closes, signal_low=12.3, signal_high=13.2, volume=1_300_000.0)

    assert diagnostic["start_diagnostic_label"] == "B"
    assert diagnostic["start_diagnostic_type"] == "pullback_reacceleration"
    assert "recent_pullback" in str(diagnostic["start_diagnostic_reason"])


def test_start_diagnostic_falls_back_when_setup_is_mixed() -> None:
    closes = [10.0] * 10 + [12.0] * 5 + [10.0 + ((index % 2) * 0.05) for index in range(55)]
    diagnostic = _diagnostic_from_closes(closes, volume=500_000.0, smc_gap_pct=0.0)

    assert diagnostic["start_diagnostic_label"] == "未分类"
    assert diagnostic["start_diagnostic_type"] == "unclassified_start_diagnostic"


def test_atomic_publish_keeps_all_rows_and_refuses_overwrite(tmp_path: Path) -> None:
    rows = [
        StockSelectionRow("sh.600001", "2026-04-09", 10.0, 2e8, 2.0, 1.0, 10.0, 9.0, 0, ()),
        StockSelectionRow("sh.600002", "2026-04-09", 11.0, 1e8, 3.0, 2.0, 11.0, 10.0, 1, ("mkf_bearcluster",)),
    ]
    directory = _atomic_publish(tmp_path, "run-1", rows, {"candidate_count": 2})
    assert len(json.loads((directory / "candidates.json").read_text())) == 2
    assert json.loads((directory / "summary.json").read_text())["candidate_count"] == 2
    manifest = json.loads((directory / "manifest.json").read_text())
    assert manifest["schema_version"] == "ncn_smc_stock_selector_v4"
    timestamped_name = manifest["timestamped_candidates_csv"]
    assert re.fullmatch(r"smc_candidates_\d{8}_\d{6}\.csv", timestamped_name)
    assert (directory / timestamped_name).read_bytes() == (directory / "candidates.csv").read_bytes()
    assert timestamped_name in manifest["files"]
    assert "human_review_summary.csv" not in manifest["files"]
    with pytest.raises(FileExistsError):
        _atomic_publish(tmp_path, "run-1", rows, {"candidate_count": 2})


def test_diagnostics_do_not_change_review_sort_order() -> None:
    rows = [
        StockSelectionRow(
            "sh.600003", "2026-04-09", 10.0, 1e8, 2.0, 1.0, 10.0, 9.0, 0, (),
            start_diagnostic_label="高位追涨",
        ),
        StockSelectionRow(
            "sh.600001", "2026-04-09", 10.0, 3e8, 2.0, 1.0, 10.0, 9.0, 0, (),
            start_diagnostic_label="A",
        ),
        StockSelectionRow(
            "sh.600002", "2026-04-09", 10.0, 5e8, 2.0, 1.0, 10.0, 9.0, 1, ("mkf_bearcluster",),
            start_diagnostic_label="B",
        ),
    ]

    rows.sort(key=lambda row: (row.risk_warning_count, -row.amount_cny, row.code))

    assert [row.code for row in rows] == ["sh.600001", "sh.600003", "sh.600002"]


def test_stock_selection_reports_progress(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    data_root.mkdir()
    pd.DataFrame(_records()).to_parquet(data_root / "sh.600001.parquet", index=False)
    config_path = Path(__file__).parents[1] / "yaml" / "edge_scout_v1.yaml"
    events: list[tuple[int, int, int]] = []
    result = run_stock_selection(
        data_root=data_root,
        config_path=config_path,
        output_root=tmp_path / "out",
        as_of=_records()[-1]["date"],
        run_id="select-progress",
        progress=lambda done, total, selected: events.append((done, total, selected)),
    )
    assert result.candidate_count >= 0
    assert events[-1][0:2] == (1, 1)
    summary = json.loads(result.summary_path.read_text(encoding="utf-8"))
    assert summary["prospective_eligible"] is False
    assert summary["prospective_eligibility_reason"] == "manual_as_of"


def test_cli_prints_start_diagnostic_label(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    data_root = tmp_path / "data"
    data_root.mkdir()
    pd.DataFrame(_records()).to_parquet(data_root / "sh.600001.parquet", index=False)
    config_path = Path(__file__).parents[1] / "yaml" / "edge_scout_v1.yaml"

    exit_code = select_stocks.main([
        "--data-root", str(data_root),
        "--config", str(config_path),
        "--output-root", str(tmp_path / "out"),
        "--as-of", _records()[-1]["date"].isoformat(),
        "--run-id", "select-cli-diag",
        "--top", "1",
    ])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "diag" in output
    assert "human_review_summary_csv=" in output
    assert "SMC 派生人工复核分组" in output
    assert (tmp_path / "out" / "select-cli-diag" / "human_review_summary.csv").is_file()


def test_cli_top_is_display_only_and_must_be_positive(tmp_path: Path) -> None:
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
