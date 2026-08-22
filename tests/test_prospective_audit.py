from __future__ import annotations

import importlib.util
import json
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

from ashare_edge_scout.contracts import EdgeScoutResult, EdgeScoutScanSummary, Tier
from ashare_edge_scout.prospective_audit import (
    build_prospective_audit,
    canonical_snapshots,
    evaluate_archived_row,
    load_valid_snapshot,
)
from ashare_edge_scout.publisher import publish_scan_results


def _bars(origin_close: float = 10.0, *, pending: bool = False) -> pd.DataFrame:
    dates = pd.bdate_range("2026-07-28", periods=7)
    closes = [origin_close, 10.1, 10.31, 10.2, 10.15, 10.1, 10.0]
    frame = pd.DataFrame({"date": dates, "close": closes, "tradestatus": ["1"] * len(dates)})
    if pending:
        frame = frame.iloc[:4]
    return frame


def _publish(root: Path, run_id: str, published_hour: int, *, eligible: bool = True) -> Path:
    scan_date = date(2026, 7, 28)
    selected_tier = Tier("sh.600001", scan_date, "watchlist", 55.0, 25.0, 20.0, 10.0)
    baseline_tier = Tier("sh.600002", scan_date, "near_miss", 40.0, 20.0, 12.0, 8.0)
    results = [
        EdgeScoutResult(
            code="sh.600001", as_of=scan_date, status="admitted", tier=selected_tier,
            research_close=10.0, valid_setup_confirmed=True, t_day_setup_valid=True,
            start_signal_count=3,
        ),
        EdgeScoutResult(
            code="sh.600002", as_of=scan_date, status="admitted", tier=baseline_tier,
            research_close=10.0, discovery_eligible=False, start_signal_count=1,
        ),
    ]
    summary = EdgeScoutScanSummary(
        schema_version="edge_scout_v1", status="success", run_id=run_id, as_of=scan_date,
        input_code_count=2, admitted_count=2, rejected_count=0,
        production_candidate_count=0, watchlist_count=1, near_miss_count=1,
        inputs={"config_sha256": "config-sha"},
    )
    return publish_scan_results(
        root, run_id=run_id, results=results, production_candidates=[],
        watchlist_candidates=[selected_tier], near_miss_candidates=[baseline_tier],
        summary=summary, prospective_eligible=eligible,
        visible_data_through=date(2026, 7, 30),
        published_at_utc=datetime(2026, 7, 30, published_hour, tzinfo=timezone.utc),
    )


def test_snapshot_validation_detects_source_tampering(tmp_path: Path) -> None:
    run = _publish(tmp_path, "market-early", 10)
    snapshot, error = load_valid_snapshot(run)
    assert error is None
    assert snapshot is not None
    (run / "results.jsonl").write_text("tampered\n", encoding="utf-8")
    assert load_valid_snapshot(run)[1] == "source_hash_mismatch:results.jsonl"


def test_canonical_snapshots_keep_earliest_and_exclude_manual(tmp_path: Path) -> None:
    _publish(tmp_path, "market-later", 11)
    _publish(tmp_path, "market-early", 10)
    _publish(tmp_path, "market-manual", 9, eligible=False)
    snapshots, report = canonical_snapshots(tmp_path)
    assert [snapshot["run_id"] for snapshot in snapshots] == ["market-early"]
    assert report["duplicates"] == ["market-later"]
    assert report["ineligible"] == ["market-manual"]


def test_archived_row_matures_skips_suspensions_and_detects_revision(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    data_root.mkdir()
    frame = _bars()
    suspended = pd.DataFrame({
        "date": [pd.Timestamp("2026-07-29 12:00")], "close": [99.0], "tradestatus": ["0"],
    })
    frame = pd.concat((frame.iloc[:1], suspended, frame.iloc[1:]), ignore_index=True)
    frame.to_parquet(data_root / "sh.600001.parquet", index=False)
    row = {"code": "sh.600001", "as_of": "2026-07-28", "research_close": 10.0, "watch_stage": "confirmed_watch"}
    result = evaluate_archived_row(row, data_root)
    assert result["status"] == "mature"
    assert result["label"] is True

    row["research_close"] = 9.0
    revised = evaluate_archived_row(row, data_root)
    assert revised["status"] == "data_revision"
    assert revised["label"] is None


def test_pending_and_full_audit_metrics(tmp_path: Path) -> None:
    output_root = tmp_path / "output"
    data_root = tmp_path / "data"
    data_root.mkdir()
    _publish(output_root, "market-early", 10)
    _bars().to_parquet(data_root / "sh.600001.parquet", index=False)
    _bars().to_parquet(data_root / "sh.600002.parquet", index=False)
    report = build_prospective_audit(output_root, data_root)
    assert report["snapshot_report"]["canonical"] == 1
    assert report["cohorts"]["all_watch"]["n"] == 1
    assert report["cohorts"]["all_watch"]["hits"] == 1
    assert report["cohorts"]["all_watch"]["same_date_admitted_baseline"]["precision"] == 1.0
    assert report["evidence_sufficient"] is False

    _bars(pending=True).to_parquet(data_root / "sh.600001.parquet", index=False)
    pending = build_prospective_audit(output_root, data_root)
    assert pending["cohorts"]["all_watch"]["n"] == 0
    assert pending["cohorts"]["all_watch"]["status_counts"] == {"pending": 1}
    json.dumps(pending, allow_nan=False)


def _load_cli_module():
    path = Path(__file__).parents[1] / "scripts" / "audit_prospective_watchlist.py"
    spec = importlib.util.spec_from_file_location("audit_prospective_watchlist", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_audit_output_refuses_overwrite(tmp_path: Path) -> None:
    module = _load_cli_module()
    output = tmp_path / "audit.json"
    module._write_new_json(output, {"status": "first"})
    assert json.loads(output.read_text(encoding="utf-8"))["status"] == "first"
    with pytest.raises(FileExistsError):
        module._write_new_json(output, {"status": "second"})
