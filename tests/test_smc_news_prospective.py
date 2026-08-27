from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

from ashare_edge_scout.smc_news_prospective import (
    build_smc_news_prospective_audit,
    canonical_smc_news_snapshots,
    find_canonical_smc_news_snapshot,
    load_valid_smc_news_snapshot,
    publish_smc_news_snapshot,
    write_new_json,
)


def _sha256(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def _selection_run(root: Path, run_id: str = "select-1", *, eligible: bool = True) -> Path:
    run = root / run_id
    run.mkdir(parents=True)
    candidates = [
        {
            "code": "sh.600001",
            "signal_date": "2026-07-28",
            "research_close": 10.0,
            "amount_cny": 2e8,
            "turn_pct": 2.0,
            "smc_gap_pct": 1.0,
            "ema20": 10.0,
            "ema50": 9.0,
            "risk_warning_count": 0,
            "risk_warnings": [],
            "selection_reason": "smc_medium_buy_and_hard_gates",
            "research_only": True,
            "start_diagnostic_label": "高位追涨",
            "start_diagnostic_type": "high_position_chase",
            "start_diagnostic_reason": "near_60d_high",
        },
        {
            "code": "sh.600002",
            "signal_date": "2026-07-28",
            "research_close": 10.0,
            "amount_cny": 1e8,
            "turn_pct": 1.0,
            "smc_gap_pct": 1.0,
            "ema20": 10.0,
            "ema50": 9.0,
            "risk_warning_count": 1,
            "risk_warnings": ["mkf_bearcluster"],
            "selection_reason": "smc_medium_buy_and_hard_gates",
            "research_only": True,
            "start_diagnostic_label": "未分类",
            "start_diagnostic_type": "unclassified_start_diagnostic",
            "start_diagnostic_reason": "mixed",
        },
    ]
    summary = {
        "schema_version": "ncn_smc_stock_selector_v4",
        "run_id": run_id,
        "signal_date": "2026-07-28",
        "published_at_utc": datetime(2026, 7, 28, 9, tzinfo=timezone.utc).isoformat(),
        "candidate_count": len(candidates),
        "selection_rule": "smc_medium_buy_and_existing_hard_gates",
        "config_sha256": "config-sha",
        "prospective_eligible": eligible,
        "prospective_eligibility_reason": "automatic_as_of" if eligible else "manual_as_of",
    }
    _write_json(run / "candidates.json", candidates)
    _write_json(run / "summary.json", summary)
    manifest = {
        "schema_version": "ncn_smc_stock_selector_v4",
        "run_id": run_id,
        "files": {
            "candidates.json": {"sha256": _sha256(run / "candidates.json")},
            "summary.json": {"sha256": _sha256(run / "summary.json")},
        },
    }
    _write_json(run / "manifest.json", manifest)
    return run


def _news_run(root: Path, selection: Path, run_id: str = "news-review-1", *, include_committee_csv: bool = False) -> Path:
    run = root / run_id
    run.mkdir(parents=True)
    candidates_sha = json.loads((selection / "manifest.json").read_text(encoding="utf-8"))["files"]["candidates.json"]["sha256"]
    reviews = [
        {
            "code": "sh.600001",
            "signal_date": "2026-07-28",
            "review_state": "priority_review",
            "assessment": "favorable",
            "confidence": 0.8,
            "catalyst_quality": "strong",
            "event_risk": "low",
            "summary": "ok",
            "evidence": [],
            "risk_flags": [],
            "hard_risk_terms": [],
            "attention_terms": [],
            "news_count": 2,
            "source_count": 2,
            "model": "test",
            "experimental_unvalidated": True,
        },
        {
            "code": "sh.600002",
            "signal_date": "2026-07-28",
            "review_state": "risk_excluded",
            "assessment": "adverse",
            "confidence": 0.9,
            "catalyst_quality": "weak",
            "event_risk": "high",
            "summary": "risk",
            "evidence": [],
            "risk_flags": ["risk"],
            "hard_risk_terms": [],
            "attention_terms": [],
            "news_count": 1,
            "source_count": 1,
            "model": "test",
            "experimental_unvalidated": True,
        },
    ]
    news = [
        {"code": "sh.600001", "items": [{"title": "a"}], "ai_evidence_items": [{"title": "a"}], "technical_context": {"status": "ok"}},
        {"code": "sh.600002", "items": [], "ai_evidence_items": [], "technical_context": {"status": "ok"}},
    ]
    summary = {
        "schema_version": "ncn_smc_news_ai_review_v1",
        "run_id": run_id,
        "published_at_utc": datetime(2026, 7, 28, 10, tzinfo=timezone.utc).isoformat(),
        "source_selection_run": str(selection),
        "source_candidates_sha256": candidates_sha,
        "config_sha256": "news-config-sha",
        "candidate_count": 2,
        "state_counts": {"priority_review": 1, "standard_review": 0, "risk_excluded": 1, "insufficient_evidence": 0, "ai_unavailable": 0},
    }
    _write_json(run / "reviews.json", reviews)
    _write_json(run / "news.json", news)
    if include_committee_csv:
        committee_name = "ai_committee_reviews_20260728_100000.csv"
        latest_name = "ai_committee_reviews_latest.csv"
        (run / committee_name).write_text("code,review_state\nsh.600001,priority_review\n", encoding="utf-8")
        (run / latest_name).write_text((run / committee_name).read_text(encoding="utf-8"), encoding="utf-8")
        summary["timestamped_ai_committee_csv"] = committee_name
        summary["latest_ai_committee_csv"] = latest_name
    _write_json(run / "summary.json", summary)
    files = {
        "reviews.json": {"sha256": _sha256(run / "reviews.json")},
        "news.json": {"sha256": _sha256(run / "news.json")},
        "summary.json": {"sha256": _sha256(run / "summary.json")},
    }
    if include_committee_csv:
        files[committee_name] = {"sha256": _sha256(run / committee_name)}
        files[latest_name] = {"sha256": _sha256(run / latest_name)}
    manifest = {
        "schema_version": "ncn_smc_news_ai_review_v1",
        "run_id": run_id,
        "source_candidates_sha256": candidates_sha,
        "timestamped_ai_committee_csv": committee_name if include_committee_csv else None,
        "latest_ai_committee_csv": latest_name if include_committee_csv else None,
        "files": files,
    }
    _write_json(run / "manifest.json", manifest)
    return run


def _bars(*, revised: bool = False, pending: bool = False) -> pd.DataFrame:
    dates = pd.bdate_range("2026-07-28", periods=7 if not pending else 4)
    frame = pd.DataFrame({
        "date": dates,
        "open": [10.0, 10.0, 10.2, 10.1, 10.0, 10.0, 10.0][: len(dates)],
        "high": [10.0, 10.1, 10.4, 10.2, 10.1, 10.0, 10.0][: len(dates)],
        "low": [10.0, 9.9, 10.0, 9.7, 9.8, 9.9, 9.9][: len(dates)],
        "close": [9.0 if revised else 10.0, 10.0, 10.2, 10.1, 10.0, 10.0, 10.0][: len(dates)],
        "tradestatus": ["1"] * len(dates),
    })
    return frame


def test_archive_binds_sources_and_detects_tampering(tmp_path: Path) -> None:
    selection = _selection_run(tmp_path / "selections")
    news = _news_run(tmp_path / "news", selection)
    archive = publish_smc_news_snapshot(
        selection_run=selection,
        news_run=news,
        output_root=tmp_path / "smc_news_prospective",
        run_id="smc-news-1",
    )
    snapshot = json.loads((archive / "snapshot.json").read_text(encoding="utf-8"))
    assert snapshot["schema_version"] == "ncn_smc_news_prospective_v1"
    assert snapshot["candidate_count"] == 2
    assert snapshot["review_state_counts"]["priority_review"] == 1
    assert (archive / "manifest.json").exists()
    assert load_valid_smc_news_snapshot(archive)[1] is None

    (selection / "candidates.json").write_text("[]", encoding="utf-8")
    assert load_valid_smc_news_snapshot(archive)[1] == "source_hash_mismatch:selection:candidates.json"


def test_archive_binds_ai_committee_csv_and_detects_tampering(tmp_path: Path) -> None:
    selection = _selection_run(tmp_path / "selections")
    news = _news_run(tmp_path / "news", selection, include_committee_csv=True)
    archive = publish_smc_news_snapshot(
        selection_run=selection,
        news_run=news,
        output_root=tmp_path / "smc_news_prospective",
        run_id="smc-news-committee",
    )

    snapshot = json.loads((archive / "snapshot.json").read_text(encoding="utf-8"))
    artifacts = snapshot["source_artifacts"]["news_review"]
    assert "ai_committee_reviews_20260728_100000.csv" in artifacts
    assert "ai_committee_reviews_latest.csv" in artifacts
    assert load_valid_smc_news_snapshot(archive)[1] is None

    (news / "ai_committee_reviews_latest.csv").write_text("tampered", encoding="utf-8")
    assert load_valid_smc_news_snapshot(archive)[1] == "source_hash_mismatch:news_review:ai_committee_reviews_latest.csv"


def test_ineligible_selection_is_rejected(tmp_path: Path) -> None:
    selection = _selection_run(tmp_path / "selections", eligible=False)
    news = _news_run(tmp_path / "news", selection)
    with pytest.raises(ValueError, match="not prospectively eligible"):
        publish_smc_news_snapshot(selection_run=selection, news_run=news, output_root=tmp_path / "out")


def test_news_review_source_hash_mismatch_is_rejected(tmp_path: Path) -> None:
    selection = _selection_run(tmp_path / "selections")
    news = _news_run(tmp_path / "news", selection)
    summary = json.loads((news / "summary.json").read_text(encoding="utf-8"))
    summary["source_candidates_sha256"] = "wrong-sha"
    _write_json(news / "summary.json", summary)
    manifest = json.loads((news / "manifest.json").read_text(encoding="utf-8"))
    manifest["files"]["summary.json"]["sha256"] = _sha256(news / "summary.json")
    _write_json(news / "manifest.json", manifest)

    with pytest.raises(ValueError, match="source_candidates_sha256 mismatch"):
        publish_smc_news_snapshot(selection_run=selection, news_run=news, output_root=tmp_path / "out")


def test_news_review_rows_must_match_summary_counts(tmp_path: Path) -> None:
    selection = _selection_run(tmp_path / "selections")
    news = _news_run(tmp_path / "news", selection)
    reviews = json.loads((news / "reviews.json").read_text(encoding="utf-8"))
    reviews[1]["review_state"] = "priority_review"
    _write_json(news / "reviews.json", reviews)
    manifest = json.loads((news / "manifest.json").read_text(encoding="utf-8"))
    manifest["files"]["reviews.json"]["sha256"] = _sha256(news / "reviews.json")
    _write_json(news / "manifest.json", manifest)

    with pytest.raises(ValueError, match="state_counts mismatch"):
        publish_smc_news_snapshot(selection_run=selection, news_run=news, output_root=tmp_path / "out")


def test_news_review_duplicate_codes_are_rejected(tmp_path: Path) -> None:
    selection = _selection_run(tmp_path / "selections")
    news = _news_run(tmp_path / "news", selection)
    reviews = json.loads((news / "reviews.json").read_text(encoding="utf-8"))
    reviews[1]["code"] = reviews[0]["code"]
    _write_json(news / "reviews.json", reviews)
    manifest = json.loads((news / "manifest.json").read_text(encoding="utf-8"))
    manifest["files"]["reviews.json"]["sha256"] = _sha256(news / "reviews.json")
    _write_json(news / "manifest.json", manifest)

    with pytest.raises(ValueError, match="review codes invalid"):
        publish_smc_news_snapshot(selection_run=selection, news_run=news, output_root=tmp_path / "out")


def test_news_artifact_tampering_is_detected(tmp_path: Path) -> None:
    selection = _selection_run(tmp_path / "selections")
    news = _news_run(tmp_path / "news", selection)
    archive = publish_smc_news_snapshot(selection_run=selection, news_run=news, output_root=tmp_path / "out", run_id="smc-news-1")

    (news / "reviews.json").write_text("[]", encoding="utf-8")

    assert load_valid_smc_news_snapshot(archive)[1] == "source_hash_mismatch:news_review:reviews.json"


def test_find_canonical_smc_news_snapshot_returns_existing_signal_date(tmp_path: Path) -> None:
    selection = _selection_run(tmp_path / "selections")
    news = _news_run(tmp_path / "news", selection)
    output = tmp_path / "out"
    publish_smc_news_snapshot(selection_run=selection, news_run=news, output_root=output, run_id="smc-news-1")

    existing = find_canonical_smc_news_snapshot(output, "2026-07-28")

    assert existing is not None
    assert existing["run_id"] == "smc-news-1"
    assert existing["archive_path"] == str(output / "smc-news-1")
    assert find_canonical_smc_news_snapshot(output, "2026-07-29") is None


def test_duplicate_signal_date_archive_cli_skips_second_publish(tmp_path: Path) -> None:
    import subprocess

    selection = _selection_run(tmp_path / "selections")
    news = _news_run(tmp_path / "news", selection)
    output = tmp_path / "out"
    publish_smc_news_snapshot(selection_run=selection, news_run=news, output_root=output, run_id="smc-news-1")

    completed = subprocess.run(
        [
            str(Path(__file__).parents[1] / ".venv/bin/python"),
            str(Path(__file__).parents[1] / "scripts/archive_smc_news_prospective.py"),
            "--selection-run",
            str(selection),
            "--news-run",
            str(news),
            "--output-root",
            str(output),
            "--run-id",
            "smc-news-2",
        ],
        cwd=Path(__file__).parents[1],
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "smc_news_prospective_archive_status=skipped_existing_signal_date" in completed.stdout
    assert "existing_archive_run_id=smc-news-1" in completed.stdout
    assert not (output / "smc-news-2").exists()


def test_archive_cli_preflight_reports_duplicate_signal_date(tmp_path: Path) -> None:
    import subprocess

    selection = _selection_run(tmp_path / "selections")
    news = _news_run(tmp_path / "news", selection)
    output = tmp_path / "out"
    publish_smc_news_snapshot(selection_run=selection, news_run=news, output_root=output, run_id="smc-news-1")

    completed = subprocess.run(
        [
            str(Path(__file__).parents[1] / ".venv/bin/python"),
            str(Path(__file__).parents[1] / "scripts/archive_smc_news_prospective.py"),
            "--selection-run",
            str(selection),
            "--output-root",
            str(output),
            "--check-existing-signal-date",
        ],
        cwd=Path(__file__).parents[1],
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "archive_signal_date=2026-07-28" in completed.stdout
    assert "archive_duplicate=1" in completed.stdout
    assert "existing_archive_run_id=smc-news-1" in completed.stdout


def test_archive_cli_preflight_reports_no_duplicate_signal_date(tmp_path: Path) -> None:
    import subprocess

    selection = _selection_run(tmp_path / "selections")
    output = tmp_path / "out"
    output.mkdir()

    completed = subprocess.run(
        [
            str(Path(__file__).parents[1] / ".venv/bin/python"),
            str(Path(__file__).parents[1] / "scripts/archive_smc_news_prospective.py"),
            "--selection-run",
            str(selection),
            "--output-root",
            str(output),
            "--check-existing-signal-date",
        ],
        cwd=Path(__file__).parents[1],
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "archive_signal_date=2026-07-28" in completed.stdout
    assert "archive_duplicate=0" in completed.stdout


def test_smc_news_audit_mature_pending_and_revision(tmp_path: Path) -> None:
    selection = _selection_run(tmp_path / "selections")
    news = _news_run(tmp_path / "news", selection)
    publish_smc_news_snapshot(selection_run=selection, news_run=news, output_root=tmp_path / "out" / "smc_news_prospective", run_id="smc-news-1")
    data_root = tmp_path / "data"
    data_root.mkdir()
    _bars().to_parquet(data_root / "sh.600001.parquet", index=False)
    _bars(pending=True).to_parquet(data_root / "sh.600002.parquet", index=False)

    report = build_smc_news_prospective_audit(tmp_path / "out", data_root)
    assert report["schema_version"] == "ncn_smc_news_prospective_audit_v1"
    assert report["snapshot_report"]["canonical"] == 1
    assert report["cohorts"]["all_smc"]["n"] == 1
    assert report["cohorts"]["priority_review"]["hits"] == 1
    assert report["cohorts"]["risk_excluded"]["status_counts"] == {"pending": 1}
    assert report["parent_maturity_sufficient"] is False
    assert report["promotion_evidence_sufficient"] is False
    assert report["evidence_sufficient"] is False
    assert "priority_review_mature_n_below_300" in report["promotion_evidence_failure_reasons"]
    assert report["promotion_evidence_requirements"]["cohort"] == "priority_review"

    _bars(revised=True).to_parquet(data_root / "sh.600001.parquet", index=False)
    revised = build_smc_news_prospective_audit(tmp_path / "out", data_root)
    statuses = {row["code"]: row["status"] for row in revised["observations"]}
    assert statuses["sh.600001"] == "data_revision"


def test_write_new_json_refuses_overwrite(tmp_path: Path) -> None:
    output = tmp_path / "audit.json"
    write_new_json(output, {"ok": True})
    with pytest.raises(FileExistsError):
        write_new_json(output, {"ok": False})
