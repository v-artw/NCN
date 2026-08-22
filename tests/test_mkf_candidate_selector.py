from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd
import pytest

from ashare_edge_scout import mkf_candidate_selector as selector
from ashare_edge_scout.mkf_candidate_selector import (
    MkfCandidateRow,
    _atomic_publish,
    evaluate_mkf_candidate_stock,
    run_mkf_candidate_selection,
)
from scripts import select_mkf_candidates
from scripts.select_mkf_candidates import parse_args


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


def _records() -> list[dict[str, object]]:
    dates = pd.bdate_range("2025-03-01", periods=270)
    rows = []
    for index, bar_date in enumerate(dates):
        close = 10.0 + index * 0.01
        rows.append({
            "code": "sh.600001",
            "date": bar_date.date(),
            "open": close - 0.05,
            "high": close + 0.2,
            "low": close - 0.2,
            "close": close,
            "preclose": close - 0.01 if index else close,
            "volume": 1_000_000.0,
            "amount": 200_000_000.0,
            "turn": 2.0,
            "tradestatus": "1",
            "isST": "0",
        })
    return rows


def _patch_mkf(monkeypatch: pytest.MonkeyPatch, *, selected: bool = True) -> None:
    def fake_mask(frame: pd.DataFrame) -> pd.Series:
        values = [False] * len(frame)
        if selected and values:
            values[-1] = True
        return pd.Series(values, index=frame.index, dtype=bool)

    def fake_lines(frame: pd.DataFrame) -> pd.DataFrame:
        lines = pd.DataFrame(25.0, index=frame.index, columns=["momentum", "inter", "near"])
        if len(frame) >= 2:
            lines.loc[frame.index[-2], ["momentum", "near"]] = [15.0, 18.0]
            lines.loc[frame.index[-1], ["momentum", "inter", "near"]] = [30.0, 24.0, 35.0]
        return lines

    monkeypatch.setattr(selector, "mkf_red_blue_cross20_under80_mask", fake_mask)
    monkeypatch.setattr(selector, "mkf_red_blue_cross20_lines", fake_lines)


def test_mkf_candidate_selector_selects_latest_cross_under80(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_mkf(monkeypatch)
    records = _records()

    row = evaluate_mkf_candidate_stock("sh.600001", records, CONFIG, records[-1]["date"])

    assert row is not None
    assert row.selection_reason == "mkf_red_blue_cross20_under80_v1_and_existing_hard_gates"
    assert row.mkf_red_cross_up_20 is True
    assert row.mkf_blue_cross_up_20 is True
    assert row.mkf_red_blue_cross_up_20_under_80 is True
    assert row.research_only is True


def test_mkf_candidate_selector_rejects_absent_signal(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_mkf(monkeypatch, selected=False)
    records = _records()

    assert evaluate_mkf_candidate_stock("sh.600001", records, CONFIG, records[-1]["date"]) is None


def test_mkf_candidate_selector_is_causal_at_manual_as_of(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_mkf(monkeypatch)
    records = _records()
    as_of = records[-1]["date"]
    expected = evaluate_mkf_candidate_stock("sh.600001", records, CONFIG, as_of)
    future = dict(records[-1])
    future["date"] = (pd.Timestamp(as_of) + pd.offsets.BDay()).date()
    future["close"] = 70.0
    future["high"] = 71.0
    future["low"] = 69.0

    assert evaluate_mkf_candidate_stock("sh.600001", [*records, future], CONFIG, as_of) == expected


def test_mkf_candidate_selector_keeps_existing_hard_gates(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_mkf(monkeypatch)
    records = _records()
    records[-1]["isST"] = "1"

    assert evaluate_mkf_candidate_stock("sh.600001", records, CONFIG, records[-1]["date"]) is None


def test_mkf_candidate_selector_honors_min_adv20_override(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_mkf(monkeypatch)
    records = _records()
    for row in records:
        row["amount"] = 75_000_000.0
    config = {
        **CONFIG,
        "universe": {
            **CONFIG["universe"],
            "min_adv20_cny": 100_000_000.0,
        },
    }

    standard = evaluate_mkf_candidate_stock("sh.600001", records, config, records[-1]["date"])
    small = evaluate_mkf_candidate_stock("sh.600001", records, config, records[-1]["date"], min_adv20_cny=50_000_000.0)

    assert standard is None
    assert small is not None
    assert small.code == "sh.600001"


def test_mkf_atomic_publish_keeps_all_rows_and_refuses_overwrite(tmp_path: Path) -> None:
    rows = [
        MkfCandidateRow("sh.600001", "2026-04-09", 10.0, 2e8, 2.0, 30.0, 24.0, 35.0, True, True, True, "a"),
        MkfCandidateRow("sh.600002", "2026-04-09", 11.0, 1e8, 3.0, 25.0, 22.0, 28.0, True, True, True, "b"),
    ]
    directory = _atomic_publish(tmp_path, "mkf-run-1", rows, {"candidate_count": 2, "published_at_utc": "2026-04-09T00:00:00+00:00"})

    assert len(json.loads((directory / "candidates.json").read_text())) == 2
    manifest = json.loads((directory / "manifest.json").read_text())
    assert manifest["schema_version"] == "ncn_mkf_candidate_selector_v1"
    assert re.fullmatch(r"mkf_candidates_\d{8}_\d{6}\.csv", manifest["timestamped_candidates_csv"])
    assert (directory / manifest["timestamped_candidates_csv"]).read_bytes() == (directory / "candidates.csv").read_bytes()
    with pytest.raises(FileExistsError):
        _atomic_publish(tmp_path, "mkf-run-1", rows, {"candidate_count": 2})


def test_mkf_selection_reports_boundaries_and_progress(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_mkf(monkeypatch)
    data_root = tmp_path / "data"
    data_root.mkdir()
    pd.DataFrame(_records()).to_parquet(data_root / "sh.600001.parquet", index=False)
    config_path = Path(__file__).parents[1] / "yaml" / "edge_scout_v1.yaml"
    events: list[tuple[int, int, int]] = []

    result = run_mkf_candidate_selection(
        data_root=data_root,
        config_path=config_path,
        output_root=tmp_path / "out",
        as_of=_records()[-1]["date"],
        run_id="mkf-progress",
        min_adv20_cny=50_000_000.0,
        selection_profile="small_capital",
        progress=lambda done, total, selected: events.append((done, total, selected)),
    )

    assert result.candidate_count == 1
    assert events[-1][0:2] == (1, 1)
    summary = json.loads(result.summary_path.read_text())
    assert summary["schema_version"] == "ncn_mkf_candidate_selector_v1"
    assert summary["selection_profile"] == "small_capital"
    assert summary["effective_min_adv20_cny"] == 50_000_000.0
    assert summary["boundaries"]["production_enabled"] is False
    assert summary["boundaries"]["smc_admission_modified"] is False
    assert summary["boundaries"]["watchlist_modified"] is False


def test_mkf_cli_top_is_display_only_and_must_be_positive(tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_mkf(monkeypatch)
    data_root = tmp_path / "data"
    data_root.mkdir()
    pd.DataFrame(_records()).to_parquet(data_root / "sh.600001.parquet", index=False)
    config_path = Path(__file__).parents[1] / "yaml" / "edge_scout_v1.yaml"

    exit_code = select_mkf_candidates.main([
        "--data-root", str(data_root),
        "--config", str(config_path),
        "--output-root", str(tmp_path / "out"),
        "--as-of", _records()[-1]["date"].isoformat(),
        "--run-id", "mkf-cli",
        "--top", "1",
        "--selection-profile", "small_capital",
        "--min-adv20-cny", "50000000",
    ])

    output = capsys.readouterr().out
    summary = json.loads((tmp_path / "out" / "mkf-cli" / "summary.json").read_text())
    assert exit_code == 0
    assert "selector=mkf_red_blue_cross20_under80_v1" in output
    assert "selection_profile=small_capital" in output
    assert "effective_min_adv20_cny=50000000" in output
    assert "candidate_count=1" in output
    assert summary["selection_profile"] == "small_capital"
    assert summary["effective_min_adv20_cny"] == 50_000_000.0
    assert len(json.loads((tmp_path / "out" / "mkf-cli" / "candidates.json").read_text())) == 1
    with pytest.raises(SystemExit):
        parse_args(["--data-root", str(tmp_path), "--config", "config.yaml", "--output-root", str(tmp_path / "out"), "--top", "0"])
