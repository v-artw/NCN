from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest

from ashare_edge_scout.research_mkf_ai_target_touch import _outcomes, analyze_review_run


def _write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False) + "\n", encoding="utf-8")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _review_run(tmp_path: Path, *, state: str = "priority_research") -> tuple[Path, Path]:
    selection = tmp_path / "selection"
    selection.mkdir()
    candidates = [{"code": "sh.600001", "signal_date": "2026-01-01"}]
    _write(selection / "candidates.json", candidates)
    _write(selection / "summary.json", {"schema_version": "ncn_mkf_candidate_selector_v6"})
    _write(selection / "manifest.json", {"schema_version": "ncn_mkf_candidate_selector_v6", "files": {"candidates.json": {"sha256": _sha(selection / "candidates.json")}}})
    run = tmp_path / "review"
    run.mkdir()
    reviews = [{"code": "sh.600001", "signal_date": "2026-01-01", "review_state": state, "confidence": 0.5}]
    contexts = [{"code": "sh.600001", "signal_date": "2026-01-01", "technical_context": {"code": "sh.600001"}}]
    news = [{"code": "sh.600001", "signal_date": "2026-01-01", "news_context": {"code": "sh.600001"}}]
    for name, value in (("reviews.json", reviews), ("technical_contexts.json", contexts), ("news_contexts.json", news)):
        _write(run / name, value)
    summary = {"schema_version": "ncn_mkf_ai_review_v3", "source_selection_run": str(selection), "source_candidates_sha256": _sha(selection / "candidates.json"), "ai_provider": "fake", "ai_model": "fake", "prompt_sha256": "prompt"}
    _write(run / "summary.json", summary)
    files = {name: {"sha256": _sha(run / name)} for name in ("reviews.json", "summary.json", "technical_contexts.json", "news_contexts.json")}
    _write(run / "manifest.json", {"schema_version": "ncn_mkf_ai_review_v3", "source_candidates_sha256": _sha(selection / "candidates.json"), "files": files})
    data = tmp_path / "data"
    data.mkdir()
    dates = pd.bdate_range("2026-01-01", periods=23)
    frame = pd.DataFrame({"date": dates, "open": [100.0] * 23, "high": [101.0] * 23, "tradestatus": ["1"] * 23})
    frame.loc[1, "high"] = 200.0
    frame.loc[3, "high"] = 103.0
    frame.to_parquet(data / "sh.600001.parquet", index=False)
    return run, data


def test_analysis_excludes_entry_high_and_reports_state_coverage(tmp_path: Path) -> None:
    run, data = _review_run(tmp_path, state="ai_unavailable")
    report = analyze_review_run(run, data, target_pcts=(3,), horizons=(1, 2))
    assert report["coverage"]["review_state_counts"] == {"ai_unavailable": 1}
    assert report["candidate_evidence"][0]["status"] == "mature"
    grid = report["strata"]["ai_unavailable"]["grid"]
    assert grid[0]["horizon"] == 1 and grid[0]["hits"] == 0
    assert grid[1]["horizon"] == 2 and grid[1]["hits"] == 1


def test_outcomes_normalize_timestamp_signal_date(tmp_path: Path) -> None:
    _, data = _review_run(tmp_path)
    frame = pd.read_parquet(data / "sh.600001.parquet")
    outcomes = _outcomes(frame, {"2026-01-01T00:00:00"}, 1)
    assert outcomes["2026-01-01T00:00:00"]["status"] == "mature"


def test_analysis_uses_each_horizon_mature_denominator(tmp_path: Path) -> None:
    run, data = _review_run(tmp_path)
    frame = pd.read_parquet(data / "sh.600001.parquet").iloc[:4]
    frame.to_parquet(data / "sh.600001.parquet", index=False)
    report = analyze_review_run(run, data, target_pcts=(3,), horizons=(1, 2, 3))
    grid = report["strata"]["priority_research"]["grid"]
    assert [cell["n"] for cell in grid] == [1, 1, 0]
    assert [cell["hits"] for cell in grid] == [0, 1, 0]


def test_outcomes_classify_missing_entry_as_pending(tmp_path: Path) -> None:
    _, data = _review_run(tmp_path)
    frame = pd.read_parquet(data / "sh.600001.parquet")
    signal_date = str(frame["date"].iloc[-1].date())
    assert _outcomes(frame, {signal_date}, 1)[signal_date]["status"] == "entry_pending"


def test_analysis_rejects_tampered_review_file(tmp_path: Path) -> None:
    run, data = _review_run(tmp_path)
    _write(run / "reviews.json", [])
    with pytest.raises(ValueError, match="hash"):
        analyze_review_run(run, data, target_pcts=(3,), horizons=(5,))


def test_analysis_rejects_missing_daily_bars(tmp_path: Path) -> None:
    run, data = _review_run(tmp_path)
    (data / "sh.600001.parquet").unlink()
    with pytest.raises(ValueError, match="missing daily bars"):
        analyze_review_run(run, data, target_pcts=(3,), horizons=(5,))
