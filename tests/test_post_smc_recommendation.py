from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pytest

from ashare_edge_scout.post_smc_recommendation import (
    BOUNDARY_NOTE,
    build_post_smc_recommendation_rows,
    format_post_smc_recommendation,
    write_post_smc_recommendation_csv,
)


def _candidate(
    code: str,
    *,
    diagnostic: str = "pullback_reacceleration",
    label: str = "B",
    warnings: list[str] | None = None,
    amount: float = 100_000_000.0,
) -> dict[str, object]:
    warnings = warnings or []
    return {
        "code": code,
        "signal_date": "2026-08-20",
        "amount_cny": amount,
        "turn_pct": 1.0,
        "risk_warning_count": len(warnings),
        "risk_warnings": warnings,
        "start_diagnostic_label": label,
        "start_diagnostic_type": diagnostic,
        "range_position_20d_pct": 60.0,
        "range_position_60d_pct": 80.0,
        "prior_return_20d_pct": 3.0,
        "volume_ratio_20": 1.0,
    }


def _review(code: str, state: str, *, assessment: str = "favorable", event_risk: str = "low") -> dict[str, object]:
    return {
        "code": code,
        "signal_date": "2026-08-20",
        "review_state": state,
        "assessment": assessment,
        "confidence": 0.65,
        "event_risk": event_risk,
        "catalyst_quality": "weak",
        "summary": "测试摘要",
        "risk_flags": [],
    }


def _selection_run(root: Path, candidates: list[dict[str, object]]) -> Path:
    run = root / "select-1"
    run.mkdir(parents=True)
    candidates_path = run / "candidates.json"
    candidates_path.write_text(json.dumps(candidates, ensure_ascii=False), encoding="utf-8")
    digest = hashlib.sha256(candidates_path.read_bytes()).hexdigest()
    (run / "manifest.json").write_text(json.dumps({"files": {"candidates.json": {"sha256": digest}}}), encoding="utf-8")
    return run


def _news_run(root: Path, reviews: list[dict[str, object]], source_sha: str) -> Path:
    run = root / "news-1"
    run.mkdir(parents=True)
    reviews_path = run / "reviews.json"
    reviews_path.write_text(json.dumps(reviews, ensure_ascii=False), encoding="utf-8")
    digest = hashlib.sha256(reviews_path.read_bytes()).hexdigest()
    (run / "summary.json").write_text(json.dumps({"source_candidates_sha256": source_sha}), encoding="utf-8")
    (run / "manifest.json").write_text(
        json.dumps({"source_candidates_sha256": source_sha, "files": {"reviews.json": {"sha256": digest}}}),
        encoding="utf-8",
    )
    return run


def test_smc_only_recommendation_rows_are_read_only_and_ordered() -> None:
    rows = build_post_smc_recommendation_rows([
        _candidate("sh.600001", amount=300_000_000),
        _candidate("sh.600002", diagnostic="high_position_chase", label="高位追涨", amount=500_000_000),
        _candidate("sh.600003", diagnostic="unclassified_start_diagnostic", label="未分类", amount=400_000_000),
        _candidate("sh.600004", warnings=["mkf_bearcluster"], amount=600_000_000),
    ])

    by_code = {row["code"]: row for row in rows}
    assert by_code["sh.600001"]["analysis_bucket"] == "priority_manual_review"
    assert by_code["sh.600003"]["analysis_bucket"] == "cautious_observation"
    assert by_code["sh.600002"]["analysis_bucket"] == "defer_for_risk"
    assert by_code["sh.600004"]["analysis_bucket"] == "defer_for_risk"
    assert by_code["sh.600004"]["smc_order"] == 4
    assert {row["source_mode"] for row in rows} == {"smc_only"}
    assert all(row["boundary_note"] == BOUNDARY_NOTE for row in rows)


def test_news_merged_recommendation_is_conservative() -> None:
    candidates = [
        _candidate("sh.600001"),
        _candidate("sh.600002", diagnostic="high_position_chase", label="高位追涨"),
        _candidate("sh.600003"),
        _candidate("sh.600004", warnings=["mkf_bearcluster"]),
    ]
    rows = build_post_smc_recommendation_rows(candidates, [
        _review("sh.600001", "standard_review", assessment="favorable", event_risk="medium"),
        _review("sh.600002", "standard_review", assessment="favorable", event_risk="low"),
        _review("sh.600003", "risk_excluded", assessment="adverse", event_risk="high"),
        _review("sh.600004", "priority_review", assessment="favorable", event_risk="low"),
    ])

    by_code = {row["code"]: row for row in rows}
    assert by_code["sh.600001"]["analysis_bucket"] == "priority_manual_review"
    assert by_code["sh.600002"]["analysis_bucket"] == "cautious_observation"
    assert by_code["sh.600003"]["analysis_bucket"] == "defer_for_risk"
    assert by_code["sh.600004"]["analysis_bucket"] == "defer_for_risk"
    assert by_code["sh.600001"]["review_state"] == "standard_review"
    assert {row["source_mode"] for row in rows} == {"news_ai_merged"}


def test_write_csv_validates_binding_and_formats_empty_candidates(tmp_path: Path) -> None:
    selection = _selection_run(tmp_path / "selections", [])
    path, rows = write_post_smc_recommendation_csv(selection)
    assert rows == []
    assert path == selection / "post_smc_recommendation_analysis.csv"
    assert list(csv.DictReader(path.open(encoding="utf-8"))) == []
    assert "不构成买卖建议" in format_post_smc_recommendation(rows)

    selection = _selection_run(tmp_path / "selections2", [_candidate("sh.600001")])
    wrong_news = _news_run(tmp_path / "news", [_review("sh.600001", "priority_review")], "bad-sha")
    with pytest.raises(ValueError, match="not bound"):
        write_post_smc_recommendation_csv(selection, wrong_news)
