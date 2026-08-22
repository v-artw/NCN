from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

from ashare_edge_scout.smc_news_replay import build_smc_news_replay, publish_smc_news_replay


def _sha256(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def _selection_run(root: Path, run_id: str = "select-1", *, eligible: bool = False) -> Path:
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
            "start_diagnostic_type": "high_position_chase",
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
            "start_diagnostic_type": "unclassified_start_diagnostic",
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
    _write_json(run / "manifest.json", {
        "schema_version": "ncn_smc_stock_selector_v4",
        "run_id": run_id,
        "files": {
            "candidates.json": {"sha256": _sha256(run / "candidates.json")},
            "summary.json": {"sha256": _sha256(run / "summary.json")},
        },
    })
    return run


def _item(title: str, *, published_at: str, retrieved_at: str) -> dict[str, str]:
    return {
        "source": "google_news_rss",
        "title": title,
        "url": f"https://example.test/{title}",
        "published_at": published_at,
        "retrieved_at": retrieved_at,
    }


def _news_run(root: Path, selection: Path, run_id: str = "news-review-1") -> Path:
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
            "source_count": 1,
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
        {
            "code": "sh.600001",
            "items": [
                _item("pre", published_at="2026-07-28T00:00:00+00:00", retrieved_at="2026-07-28T01:00:00+00:00"),
                _item("post", published_at="2026-07-29T00:00:00+00:00", retrieved_at="2026-07-29T01:00:00+00:00"),
            ],
            "ai_evidence_items": [_item("pre", published_at="2026-07-28T00:00:00+00:00", retrieved_at="2026-07-28T01:00:00+00:00")],
            "technical_context": {"status": "ok"},
        },
        {
            "code": "sh.600002",
            "items": [_item("risk", published_at="2026-07-29T00:00:00+00:00", retrieved_at="2026-07-29T01:00:00+00:00")],
            "ai_evidence_items": [],
            "technical_context": {"status": "ok"},
        },
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
    _write_json(run / "summary.json", summary)
    _write_json(run / "manifest.json", {
        "schema_version": "ncn_smc_news_ai_review_v1",
        "run_id": run_id,
        "source_candidates_sha256": candidates_sha,
        "files": {
            "reviews.json": {"sha256": _sha256(run / "reviews.json")},
            "news.json": {"sha256": _sha256(run / "news.json")},
            "summary.json": {"sha256": _sha256(run / "summary.json")},
        },
    })
    return run


def _bars(*, revised: bool = False, pending: bool = False) -> pd.DataFrame:
    dates = pd.bdate_range("2026-07-28", periods=7 if not pending else 4)
    return pd.DataFrame({
        "date": dates,
        "open": [10.0, 10.0, 10.2, 10.1, 10.0, 10.0, 10.0][: len(dates)],
        "high": [10.0, 10.1, 10.4, 10.2, 10.1, 10.0, 10.0][: len(dates)],
        "low": [10.0, 9.9, 10.0, 9.7, 9.8, 9.9, 9.9][: len(dates)],
        "close": [9.0 if revised else 10.0, 10.0, 10.2, 10.1, 10.0, 10.0, 10.0][: len(dates)],
        "tradestatus": ["1"] * len(dates),
    })


def _build(tmp_path: Path, *, eligible: bool = False, revised: bool = False) -> dict[str, object]:
    selection = _selection_run(tmp_path / "selections", eligible=eligible)
    _news_run(tmp_path / "news", selection)
    data_root = tmp_path / "data"
    data_root.mkdir()
    _bars(revised=revised).to_parquet(data_root / "sh.600001.parquet", index=False)
    _bars(pending=True).to_parquet(data_root / "sh.600002.parquet", index=False)
    return build_smc_news_replay(
        selection_root=tmp_path / "selections",
        news_root=tmp_path / "news",
        cache_root=tmp_path / "cache",
        data_root=data_root,
        output_root=tmp_path / "out" / "smc_news_replay",
        run_id="replay-1",
    )


def test_replay_accepts_manual_selection_and_marks_simulation_only(tmp_path: Path) -> None:
    report = _build(tmp_path, eligible=False)
    summary = report["summary"]
    assert summary["schema_version"] == "ncn_smc_news_replay_v1"
    assert summary["simulation_only"] is True
    assert summary["not_prospective_evidence"] is True
    assert summary["prospective_evidence_claimed"] is False
    assert summary["candidate_count"] == 2
    assert "prospective_eligible" not in summary


def test_replay_preserves_news_time_diagnostics_and_no_forbidden_keys(tmp_path: Path) -> None:
    report = _build(tmp_path)
    first = report["observations"][0]
    assert first["news_time_diagnostics"]["published_after_signal_count"] == 1
    assert first["news_time_diagnostics"]["retrieved_after_signal_count"] == 1
    payload = json.dumps(report, ensure_ascii=False).lower()
    for forbidden in ("pnl", "broker", "order", "position_size"):
        assert forbidden not in payload


def test_replay_outcome_handles_mature_pending_and_revision(tmp_path: Path) -> None:
    report = _build(tmp_path)
    outcomes = {row["code"]: row["outcome"]["status"] for row in report["observations"]}
    assert outcomes == {"sh.600001": "mature", "sh.600002": "pending"}
    assert report["cohorts"]["priority_review"]["hits"] == 1

    revised = _build(tmp_path / "revised", revised=True)
    assert revised["observations"][0]["outcome"]["status"] == "data_revision"


def test_replay_rejects_tampered_selection_and_news(tmp_path: Path) -> None:
    selection = _selection_run(tmp_path / "selections")
    news = _news_run(tmp_path / "news", selection)
    data_root = tmp_path / "data"
    data_root.mkdir()
    _bars().to_parquet(data_root / "sh.600001.parquet", index=False)
    _bars().to_parquet(data_root / "sh.600002.parquet", index=False)

    (selection / "candidates.json").write_text("[]", encoding="utf-8")
    report = build_smc_news_replay(
        selection_root=tmp_path / "selections",
        news_root=tmp_path / "news",
        cache_root=None,
        data_root=data_root,
        output_root=tmp_path / "out",
        run_id="replay-1",
    )
    assert report["summary"]["candidate_count"] == 0
    assert report["summary"]["invalid_news_review_runs"]

    selection = _selection_run(tmp_path / "selections2")
    news = _news_run(tmp_path / "news2", selection)
    (news / "reviews.json").write_text("[]", encoding="utf-8")
    report = build_smc_news_replay(
        selection_root=tmp_path / "selections2",
        news_root=tmp_path / "news2",
        cache_root=None,
        data_root=data_root,
        output_root=tmp_path / "out",
        run_id="replay-2",
    )
    assert report["summary"]["invalid_news_review_runs"]


def test_replay_rejects_news_selection_binding_mismatch(tmp_path: Path) -> None:
    selection = _selection_run(tmp_path / "selections")
    news = _news_run(tmp_path / "news", selection)
    summary = json.loads((news / "summary.json").read_text(encoding="utf-8"))
    summary["source_candidates_sha256"] = "wrong"
    _write_json(news / "summary.json", summary)
    manifest = json.loads((news / "manifest.json").read_text(encoding="utf-8"))
    manifest["source_candidates_sha256"] = "wrong"
    manifest["files"]["summary.json"]["sha256"] = _sha256(news / "summary.json")
    _write_json(news / "manifest.json", manifest)
    data_root = tmp_path / "data"
    data_root.mkdir()
    report = build_smc_news_replay(
        selection_root=tmp_path / "selections",
        news_root=tmp_path / "news",
        cache_root=None,
        data_root=data_root,
        output_root=tmp_path / "out",
        run_id="replay-1",
    )
    assert "not bound to selection candidates hash" in report["summary"]["invalid_news_review_runs"][0]["error"]


def test_publish_replay_manifest_and_refuses_prospective_namespace(tmp_path: Path) -> None:
    report = _build(tmp_path)
    destination = publish_smc_news_replay(tmp_path / "out" / "smc_news_replay", "replay-1", report)
    manifest = json.loads((destination / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["simulation_only"] is True
    assert manifest["files"]["summary.json"]["sha256"] == _sha256(destination / "summary.json")
    with pytest.raises(FileExistsError):
        publish_smc_news_replay(tmp_path / "out" / "smc_news_replay", "replay-1", report)
    with pytest.raises(ValueError, match="prospective archive root"):
        publish_smc_news_replay(Path("output/edge_scout/smc_news_prospective"), "replay-2", report)
