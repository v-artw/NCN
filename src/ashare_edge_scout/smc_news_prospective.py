"""Prospective archive and audit for SMC selections plus news AI review states."""

from __future__ import annotations

import hashlib
import json
import math
import os
import tempfile
from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .research_v2 import summarize_counts

SNAPSHOT_SCHEMA = "ncn_smc_news_prospective_v1"
AUDIT_SCHEMA = "ncn_smc_news_prospective_audit_v1"
REVIEW_STATES = ("priority_review", "standard_review", "risk_excluded", "insufficient_evidence", "ai_unavailable")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_time(value: Any) -> pd.Timestamp:
    timestamp = pd.Timestamp(value)
    if pd.isna(timestamp):
        raise ValueError("invalid timestamp")
    if timestamp.tzinfo is None:
        timestamp = timestamp.tz_localize(timezone.utc)
    return timestamp.tz_convert(timezone.utc)


def _manifest_hash(manifest: Mapping[str, Any], name: str) -> str | None:
    value = (manifest.get("files") or {}).get(name) or {}
    digest = value.get("sha256")
    return str(digest) if digest else None


def _require_manifest_hash(directory: Path, manifest: Mapping[str, Any], name: str) -> str:
    expected = _manifest_hash(manifest, name)
    if not expected:
        raise ValueError(f"manifest missing hash for {name}")
    actual = _sha256(directory / name)
    if actual != expected:
        raise ValueError(f"manifest hash mismatch: {name}")
    return actual


def _validate_selection_run(selection_run: Path) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any], dict[str, str]]:
    summary_path = selection_run / "summary.json"
    candidates_path = selection_run / "candidates.json"
    manifest_path = selection_run / "manifest.json"
    if not summary_path.is_file() or not candidates_path.is_file() or not manifest_path.is_file():
        raise ValueError("selection run missing summary/candidates/manifest")
    summary = _read_json(summary_path)
    candidates = _read_json(candidates_path)
    manifest = _read_json(manifest_path)
    if not isinstance(summary, dict) or not isinstance(manifest, dict):
        raise ValueError("selection summary/manifest must be objects")
    if not isinstance(candidates, list) or any(not isinstance(row, dict) for row in candidates):
        raise ValueError("selection candidates must be a list of objects")
    if summary.get("schema_version") != "ncn_smc_stock_selector_v4":
        raise ValueError("selection schema invalid")
    if manifest.get("run_id") != selection_run.name or summary.get("run_id") != selection_run.name:
        raise ValueError("selection run_id mismatch")
    if not bool(summary.get("prospective_eligible")):
        raise ValueError("selection is not prospectively eligible")
    candidates_sha = _require_manifest_hash(selection_run, manifest, "candidates.json")
    summary_sha = _require_manifest_hash(selection_run, manifest, "summary.json")
    if int(summary.get("candidate_count", -1)) != len(candidates):
        raise ValueError("selection candidate_count mismatch")
    return summary, candidates, manifest, {"candidates.json": candidates_sha, "summary.json": summary_sha, "manifest.json": _sha256(manifest_path)}


def _validate_news_run(news_run: Path) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any], dict[str, str]]:
    summary_path = news_run / "summary.json"
    reviews_path = news_run / "reviews.json"
    news_path = news_run / "news.json"
    manifest_path = news_run / "manifest.json"
    if not summary_path.is_file() or not reviews_path.is_file() or not news_path.is_file() or not manifest_path.is_file():
        raise ValueError("news review run missing summary/reviews/news/manifest")
    summary = _read_json(summary_path)
    reviews = _read_json(reviews_path)
    news = _read_json(news_path)
    manifest = _read_json(manifest_path)
    if not isinstance(summary, dict) or not isinstance(manifest, dict):
        raise ValueError("news summary/manifest must be objects")
    if not isinstance(reviews, list) or any(not isinstance(row, dict) for row in reviews):
        raise ValueError("reviews must be a list of objects")
    if not isinstance(news, list) or any(not isinstance(row, dict) for row in news):
        raise ValueError("news must be a list of objects")
    if summary.get("schema_version") != "ncn_smc_news_ai_review_v1":
        raise ValueError("news review schema invalid")
    if manifest.get("run_id") != news_run.name or summary.get("run_id") != news_run.name:
        raise ValueError("news review run_id mismatch")
    reviews_sha = _require_manifest_hash(news_run, manifest, "reviews.json")
    news_sha = _require_manifest_hash(news_run, manifest, "news.json")
    summary_sha = _require_manifest_hash(news_run, manifest, "summary.json")
    news_hashes = {"reviews.json": reviews_sha, "news.json": news_sha, "summary.json": summary_sha, "manifest.json": _sha256(manifest_path)}
    for csv_key in ("timestamped_ai_committee_csv", "latest_ai_committee_csv"):
        csv_name = manifest.get(csv_key) or summary.get(csv_key)
        if csv_name:
            csv_name = str(csv_name)
            if "/" in csv_name or "\\" in csv_name:
                raise ValueError(f"invalid committee csv name: {csv_key}")
            news_hashes[csv_name] = _require_manifest_hash(news_run, manifest, csv_name)
    source_sha = str(summary.get("source_candidates_sha256") or "")
    if source_sha != str(manifest.get("source_candidates_sha256") or ""):
        raise ValueError("news source_candidates_sha256 mismatch")
    if int(summary.get("candidate_count", -1)) != len(reviews):
        raise ValueError("news candidate_count mismatch")
    review_codes = [str(row.get("code") or "") for row in reviews]
    if any(not code for code in review_codes) or len(set(review_codes)) != len(review_codes):
        raise ValueError("news review codes invalid")
    state_counts = {state: sum(str(row.get("review_state") or "") == state for row in reviews) for state in REVIEW_STATES}
    if state_counts != (summary.get("state_counts") or {}):
        raise ValueError("news state_counts mismatch")
    news_codes = [str(row.get("code") or "") for row in news]
    if any(not code for code in news_codes) or len(set(news_codes)) != len(news_codes):
        raise ValueError("news record codes invalid")
    return summary, reviews, news, manifest, news_hashes


def resolve_latest_news_run(news_root: Path) -> Path:
    candidates = sorted(path for path in news_root.glob("news-review-*") if (path / "summary.json").is_file())
    if not candidates:
        raise ValueError(f"no news review runs found under {news_root}")
    return candidates[-1]


def resolve_selection_for_news(news_summary: Mapping[str, Any], selection_root: Path) -> Path:
    source = Path(str(news_summary.get("source_selection_run") or ""))
    if source.is_dir():
        return source
    candidate = selection_root / source.name
    if candidate.is_dir():
        return candidate
    source_sha = str(news_summary.get("source_candidates_sha256") or "")
    for run in sorted(path for path in selection_root.glob("select-*") if (path / "manifest.json").is_file()):
        manifest = _read_json(run / "manifest.json")
        if _manifest_hash(manifest, "candidates.json") == source_sha:
            return run
    raise ValueError("matching selection run not found for news review")


def _freeze_candidate(candidate: Mapping[str, Any], review: Mapping[str, Any], news_record: Mapping[str, Any]) -> dict[str, Any]:
    code = str(candidate.get("code") or review.get("code") or news_record.get("code") or "")
    signal_date = str(candidate.get("signal_date") or review.get("signal_date") or "")
    research_close = float(candidate.get("research_close"))
    if not code or not signal_date or not math.isfinite(research_close) or research_close <= 0:
        raise ValueError("invalid candidate row for prospective archive")
    items = news_record.get("items") or []
    ai_evidence = news_record.get("ai_evidence_items") or []
    review_state = str(review.get("review_state") or "ai_unavailable")
    if review_state not in REVIEW_STATES:
        raise ValueError(f"invalid review_state: {review_state}")
    confidence = float(review.get("confidence") or 0.0)
    if not math.isfinite(confidence) or not 0.0 <= confidence <= 1.0:
        raise ValueError("invalid review confidence")
    return {
        "code": code,
        "signal_date": signal_date,
        "research_close": research_close,
        "selection_reason": candidate.get("selection_reason"),
        "risk_warning_count": int(candidate.get("risk_warning_count") or 0),
        "risk_warnings": list(candidate.get("risk_warnings") or []),
        "start_diagnostic_label": candidate.get("start_diagnostic_label"),
        "start_diagnostic_type": candidate.get("start_diagnostic_type"),
        "start_diagnostic_reason": candidate.get("start_diagnostic_reason"),
        "range_position_20d_pct": candidate.get("range_position_20d_pct"),
        "range_position_60d_pct": candidate.get("range_position_60d_pct"),
        "range_position_120d_pct": candidate.get("range_position_120d_pct"),
        "prior_return_20d_pct": candidate.get("prior_return_20d_pct"),
        "current_return_20d_pct": candidate.get("current_return_20d_pct"),
        "distance_to_high_60d_pct": candidate.get("distance_to_high_60d_pct"),
        "recent_pullback_from_high_pct": candidate.get("recent_pullback_from_high_pct"),
        "volume_ratio_20": candidate.get("volume_ratio_20"),
        "review_state": review_state,
        "assessment": review.get("assessment"),
        "confidence": confidence,
        "catalyst_quality": review.get("catalyst_quality"),
        "event_risk": review.get("event_risk"),
        "news_count": int(review.get("news_count") or len(items)),
        "source_count": int(review.get("source_count") or 0),
        "model": review.get("model"),
        "ai_evidence_count": len(ai_evidence) if isinstance(ai_evidence, list) else 0,
        "raw_news_item_count": len(items) if isinstance(items, list) else 0,
        "experimental_unvalidated": bool(review.get("experimental_unvalidated", True)),
    }


def build_smc_news_snapshot(selection_run: Path, news_run: Path) -> dict[str, Any]:
    selection_summary, candidates, _, selection_hashes = _validate_selection_run(selection_run)
    news_summary, reviews, news_records, _, news_hashes = _validate_news_run(news_run)
    if str(news_summary.get("source_candidates_sha256")) != selection_hashes["candidates.json"]:
        raise ValueError("news review is not bound to selection candidates hash")
    reviews_by_code = {str(row.get("code")): row for row in reviews}
    news_by_code = {str(row.get("code")): row for row in news_records}
    rows = []
    for candidate in candidates:
        code = str(candidate.get("code") or "")
        if code not in reviews_by_code:
            raise ValueError(f"review row missing for {code}")
        rows.append(_freeze_candidate(candidate, reviews_by_code[code], news_by_code.get(code, {"code": code})))
    signal_dates = {row["signal_date"] for row in rows}
    if len(signal_dates) > 1:
        raise ValueError("selection contains multiple signal dates")
    published_at = _utc_now()
    return {
        "schema_version": SNAPSHOT_SCHEMA,
        "research_only": True,
        "classification_only": True,
        "production_enabled": False,
        "run_id": None,
        "published_at_utc": published_at,
        "signal_date": selection_summary.get("signal_date"),
        "source_selection_run": str(selection_run),
        "source_news_review_run": str(news_run),
        "source_selection_schema_version": selection_summary.get("schema_version"),
        "source_news_review_schema_version": news_summary.get("schema_version"),
        "source_selection_config_sha256": selection_summary.get("config_sha256"),
        "source_news_review_config_sha256": news_summary.get("config_sha256"),
        "source_candidates_sha256": selection_hashes["candidates.json"],
        "source_artifacts": {
            "selection": {name: {"path": str(selection_run / name), "sha256": digest} for name, digest in selection_hashes.items()},
            "news_review": {name: {"path": str(news_run / name), "sha256": digest} for name, digest in news_hashes.items()},
        },
        "label_contract": {
            "entry_reference": "next stock-tradable T open",
            "target": "T open * 1.03",
            "eligible_window": "T+1 through T+5 stock-tradable rows; T high excluded",
            "risk_path": "risk_first_3pct checks whether -3% low is touched before +3% target in the eligible window",
            "no_execution_or_pnl": True,
        },
        "candidate_count": len(rows),
        "review_state_counts": {state: sum(row["review_state"] == state for row in rows) for state in REVIEW_STATES},
        "rows": rows,
        "limitations": [
            "news_review_states_are_publication_time_evidence_only",
            "llm_output_can_be_incorrect_or_non_reproducible",
            "target_touch_is_not_execution_or_profitability",
            "read_only_research_not_investment_advice",
        ],
    }


def publish_smc_news_snapshot(
    *,
    selection_run: Path,
    news_run: Path,
    output_root: Path,
    run_id: str | None = None,
) -> Path:
    snapshot = build_smc_news_snapshot(selection_run, news_run)
    actual_run_id = run_id or f"smc-news-{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    snapshot["run_id"] = actual_run_id
    output_root.mkdir(parents=True, exist_ok=True)
    destination = output_root / actual_run_id
    temporary = output_root / f".{actual_run_id}.tmp"
    if destination.exists() or temporary.exists():
        raise FileExistsError(f"SMC news prospective archive already exists: {destination}")
    temporary.mkdir()
    try:
        (temporary / "snapshot.json").write_text(json.dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
        summary = {
            "schema_version": SNAPSHOT_SCHEMA,
            "run_id": actual_run_id,
            "published_at_utc": snapshot["published_at_utc"],
            "signal_date": snapshot["signal_date"],
            "candidate_count": snapshot["candidate_count"],
            "review_state_counts": snapshot["review_state_counts"],
            "source_selection_run": snapshot["source_selection_run"],
            "source_news_review_run": snapshot["source_news_review_run"],
            "source_candidates_sha256": snapshot["source_candidates_sha256"],
            "decision_boundary": "prospective_archive_only_not_validated_precision",
        }
        (temporary / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
        files = {name: {"sha256": _sha256(temporary / name)} for name in ("snapshot.json", "summary.json")}
        manifest = {"schema_version": SNAPSHOT_SCHEMA, "run_id": actual_run_id, "files": files}
        (temporary / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
        os.replace(temporary, destination)
    except Exception:
        import shutil

        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return destination


def load_valid_smc_news_snapshot(run_directory: Path) -> tuple[dict[str, Any] | None, str | None]:
    snapshot_path = run_directory / "snapshot.json"
    manifest_path = run_directory / "manifest.json"
    if not snapshot_path.exists():
        return None, "snapshot_missing"
    if not manifest_path.exists():
        return None, "manifest_missing"
    try:
        snapshot = _read_json(snapshot_path)
        manifest = _read_json(manifest_path)
    except (OSError, json.JSONDecodeError):
        return None, "invalid_json"
    if snapshot.get("schema_version") != SNAPSHOT_SCHEMA:
        return None, "snapshot_schema_invalid"
    if snapshot.get("run_id") != run_directory.name or manifest.get("run_id") != run_directory.name:
        return None, "run_id_mismatch"
    expected = _manifest_hash(manifest, "snapshot.json")
    if not expected or _sha256(snapshot_path) != expected:
        return None, "snapshot_hash_mismatch"
    for group, artifacts in (snapshot.get("source_artifacts") or {}).items():
        if not isinstance(artifacts, dict):
            return None, f"source_artifacts_invalid:{group}"
        for name, value in artifacts.items():
            path = Path(str((value or {}).get("path") or ""))
            expected_source = str((value or {}).get("sha256") or "")
            if not path.is_file() or not expected_source or _sha256(path) != expected_source:
                return None, f"source_hash_mismatch:{group}:{name}"
    try:
        _parse_time(snapshot["published_at_utc"])
        pd.Timestamp(snapshot["signal_date"]).normalize()
    except (KeyError, TypeError, ValueError):
        return None, "snapshot_time_invalid"
    rows = snapshot.get("rows")
    if not isinstance(rows, list):
        return None, "snapshot_rows_invalid"
    if int(snapshot.get("candidate_count", -1)) != len(rows):
        return None, "candidate_count_mismatch"
    for row in rows:
        if not isinstance(row, dict):
            return None, "snapshot_rows_invalid"
        try:
            if not str(row["code"]) or pd.isna(pd.Timestamp(row["signal_date"])):
                return None, "snapshot_row_invalid"
            close = float(row["research_close"])
            if not math.isfinite(close) or close <= 0:
                return None, "snapshot_row_invalid"
        except (KeyError, TypeError, ValueError):
            return None, "snapshot_row_invalid"
        if row.get("review_state") not in REVIEW_STATES:
            return None, "review_state_invalid"
    return snapshot, None


def canonical_smc_news_snapshots(output_root: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    valid: list[dict[str, Any]] = []
    invalid: list[dict[str, str]] = []
    for run_directory in sorted(path for path in output_root.glob("smc-news-*") if path.is_dir()):
        snapshot, error = load_valid_smc_news_snapshot(run_directory)
        if error:
            if error != "snapshot_missing":
                invalid.append({"run_id": run_directory.name, "error": error})
            continue
        assert snapshot is not None
        valid.append(snapshot)
    valid.sort(key=lambda item: (item["published_at_utc"], item["run_id"]))
    canonical: dict[str, dict[str, Any]] = {}
    duplicates: list[str] = []
    for snapshot in valid:
        signal_date = str(snapshot["signal_date"])
        if signal_date in canonical:
            duplicates.append(str(snapshot["run_id"]))
        else:
            canonical[signal_date] = snapshot
    return list(canonical.values()), {
        "directories_seen": len([path for path in output_root.glob("smc-news-*") if path.is_dir()]),
        "valid": len(valid),
        "canonical": len(canonical),
        "duplicates": duplicates,
        "invalid": invalid,
    }


def _existing_news_review_artifacts(news_run_value: object) -> dict[str, str]:
    news_run = Path(str(news_run_value or ""))
    if not news_run.is_dir():
        return {}
    manifest_path = news_run / "manifest.json"
    summary_path = news_run / "summary.json"
    try:
        manifest = _read_json(manifest_path) if manifest_path.is_file() else {}
        summary = _read_json(summary_path) if summary_path.is_file() else {}
    except (OSError, json.JSONDecodeError):
        return {"source_news_review_run": str(news_run)}
    result = {"source_news_review_run": str(news_run)}
    for key, output_key in (
        ("timestamped_ai_committee_csv", "ai_committee_csv"),
        ("latest_ai_committee_csv", "ai_committee_latest_csv"),
    ):
        name = manifest.get(key) or summary.get(key)
        if name and "/" not in str(name) and "\\" not in str(name):
            path = news_run / str(name)
            if path.is_file():
                result[output_key] = str(path)
    return result


def find_canonical_smc_news_snapshot(output_root: Path, signal_date: str) -> dict[str, Any] | None:
    snapshots, _ = canonical_smc_news_snapshots(output_root)
    for snapshot in snapshots:
        if str(snapshot.get("signal_date") or "") == str(signal_date):
            run_id = str(snapshot.get("run_id") or "")
            result = {
                "run_id": run_id,
                "signal_date": str(snapshot.get("signal_date") or ""),
                "archive_path": str(output_root / run_id) if run_id else "",
                "published_at_utc": snapshot.get("published_at_utc"),
            }
            result.update(_existing_news_review_artifacts(snapshot.get("source_news_review_run")))
            return result
    return None


def selection_signal_date(selection_run: Path) -> str:
    summary, _, _, _ = _validate_selection_run(selection_run)
    signal_date = str(summary.get("signal_date") or "")
    if not signal_date:
        raise ValueError("selection signal_date missing")
    return signal_date


def evaluate_smc_news_row(row: Mapping[str, Any], data_root: Path) -> dict[str, Any]:
    result: dict[str, Any] = {
        "code": row.get("code"),
        "signal_date": row.get("signal_date"),
        "review_state": row.get("review_state"),
        "status": "invalid_snapshot_row",
        "target_touched": None,
        "risk_first_3pct": None,
        "maturity_date": None,
    }
    try:
        code = str(row["code"])
        signal_date = pd.Timestamp(row["signal_date"]).normalize()
        archived_close = float(row["research_close"])
    except (KeyError, TypeError, ValueError):
        return result
    if not math.isfinite(archived_close) or archived_close <= 0 or pd.isna(signal_date):
        return result
    path = data_root / f"{code}.parquet"
    if not path.is_file():
        result["status"] = "data_missing"
        return result
    try:
        frame = pd.read_parquet(path, columns=["date", "open", "high", "low", "close", "tradestatus"])
    except Exception:
        result["status"] = "data_invalid"
        return result
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    for column in ("open", "high", "low", "close"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame.dropna(subset=["date"]).sort_values("date", kind="stable").drop_duplicates("date", keep="last").reset_index(drop=True)
    origin = frame.index[frame["date"].eq(signal_date)]
    if len(origin) != 1 or str(frame.loc[int(origin[0]), "tradestatus"]) != "1":
        result["status"] = "origin_missing"
        return result
    origin_index = int(origin[0])
    current_close = float(frame.loc[origin_index, "close"])
    if not math.isfinite(current_close):
        result["status"] = "data_invalid"
        return result
    if not math.isclose(current_close, archived_close, rel_tol=1e-8, abs_tol=1e-6):
        result.update({"status": "data_revision", "current_origin_close": current_close})
        return result
    tradable_indices = [int(index) for index in frame.index[frame["tradestatus"].astype("string").eq("1")]]
    positions = {index: position for position, index in enumerate(tradable_indices)}
    position = positions.get(origin_index)
    if position is None or position + 1 >= len(tradable_indices):
        result["status"] = "pending"
        return result
    entry = tradable_indices[position + 1]
    entry_open = float(frame.loc[entry, "open"])
    eligible = tradable_indices[position + 2:position + 7]
    if len(eligible) < 5:
        result.update({"status": "pending", "entry_date": frame.loc[entry, "date"].date().isoformat(), "entry_open": entry_open})
        return result
    highs = frame.loc[eligible, "high"].to_numpy(dtype=float)
    lows = frame.loc[eligible, "low"].to_numpy(dtype=float)
    if not math.isfinite(entry_open) or entry_open <= 0 or not np.isfinite(highs).all() or not np.isfinite(lows).all():
        result["status"] = "data_invalid"
        return result
    target_touches = highs >= entry_open * 1.03
    risk_touches = lows <= entry_open * 0.97
    target_first = int(np.argmax(target_touches)) if bool(target_touches.any()) else None
    risk_first = int(np.argmax(risk_touches)) if bool(risk_touches.any()) else None
    result.update({
        "status": "mature",
        "entry_date": frame.loc[entry, "date"].date().isoformat(),
        "entry_open": entry_open,
        "target_price": float(entry_open * 1.03),
        "target_touched": bool(target_touches.any()),
        "first_touch_day": None if target_first is None else target_first + 1,
        "risk_first_3pct": bool(risk_first is not None and (target_first is None or risk_first < target_first)),
        "max_drawdown": float(lows.min() / entry_open - 1.0),
        "max_excursion": float(highs.max() / entry_open - 1.0),
        "maturity_date": frame.loc[eligible[-1], "date"].date().isoformat(),
    })
    return result


def _summary(rows: Sequence[Mapping[str, Any]], baseline: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    mature = [row for row in rows if row.get("status") == "mature" and row.get("target_touched") is not None]
    hits = sum(bool(row["target_touched"]) for row in mature)
    result = summarize_counts(len(mature), hits)
    result["win_rate"] = result.pop("precision")
    result["signal_dates"] = len({row.get("signal_date") for row in mature})
    result["codes"] = len({row.get("code") for row in mature})
    statuses = pd.Series([row.get("status") for row in rows]).value_counts().sort_index()
    result["status_counts"] = {str(key): int(value) for key, value in statuses.items()}
    counts: defaultdict[str, int] = defaultdict(int)
    for row in mature:
        counts[str(row.get("signal_date"))] += 1
    weighted_n = 0
    weighted_hits = 0.0
    baseline_observations = 0
    for signal_date, weight in counts.items():
        same_date = [row for row in baseline if row.get("status") == "mature" and str(row.get("signal_date")) == signal_date]
        if not same_date:
            continue
        precision = sum(bool(row.get("target_touched")) for row in same_date) / len(same_date)
        weighted_n += weight
        weighted_hits += weight * precision
        baseline_observations += len(same_date)
    baseline_rate = weighted_hits / weighted_n if weighted_n else None
    result["same_date_smc_baseline"] = {
        "observations": baseline_observations,
        "weighted_n": weighted_n,
        "weighted_hits": weighted_hits,
        "win_rate": baseline_rate,
    }
    result["win_rate_lift"] = None if result["win_rate"] is None or baseline_rate is None else result["win_rate"] - baseline_rate
    if mature:
        result["risk_first_3pct_rate"] = sum(bool(row.get("risk_first_3pct")) for row in mature) / len(mature)
        result["median_max_drawdown"] = float(pd.Series([row.get("max_drawdown") for row in mature]).median())
        result["median_max_excursion"] = float(pd.Series([row.get("max_excursion") for row in mature]).median())
    else:
        result["risk_first_3pct_rate"] = None
        result["median_max_drawdown"] = None
        result["median_max_excursion"] = None
    return result


def build_smc_news_prospective_audit(output_root: Path, data_root: Path) -> dict[str, Any]:
    archive_root = output_root / "smc_news_prospective"
    snapshots, snapshot_report = canonical_smc_news_snapshots(archive_root)
    observations: list[dict[str, Any]] = []
    for snapshot in snapshots:
        for row in snapshot["rows"]:
            outcome = evaluate_smc_news_row(row, data_root)
            outcome.update({
                "archive_run_id": snapshot["run_id"],
                "published_at_utc": snapshot["published_at_utc"],
                "assessment": row.get("assessment"),
                "confidence": row.get("confidence"),
                "event_risk": row.get("event_risk"),
                "start_diagnostic_type": row.get("start_diagnostic_type"),
                "risk_warning_count": row.get("risk_warning_count"),
            })
            observations.append(outcome)
    cohorts: dict[str, Any] = {"all_smc": _summary(observations, observations)}
    for state in REVIEW_STATES:
        rows = [row for row in observations if row.get("review_state") == state]
        cohorts[state] = _summary(rows, observations)
    primary = cohorts["all_smc"]
    parent_maturity_sufficient = (
        int(primary["n"]) >= 300
        and int(primary["signal_dates"]) >= 120
        and int(primary["codes"]) >= 50
        and primary["wilson_lower_95"] is not None
    )
    priority = cohorts.get("priority_review", {})
    priority_baseline = priority.get("same_date_smc_baseline", {}) if isinstance(priority, dict) else {}
    promotion_failure_reasons: list[str] = []
    if int(priority.get("n", 0) or 0) < 300:
        promotion_failure_reasons.append("priority_review_mature_n_below_300")
    if int(priority.get("signal_dates", 0) or 0) < 120:
        promotion_failure_reasons.append("priority_review_signal_dates_below_120")
    if int(priority.get("codes", 0) or 0) < 50:
        promotion_failure_reasons.append("priority_review_codes_below_50")
    parent_n = int(primary.get("n", 0) or 0)
    priority_n = int(priority.get("n", 0) or 0)
    if parent_n <= 0 or priority_n / parent_n < 0.20:
        promotion_failure_reasons.append("priority_review_retention_below_20pct")
    if (priority.get("win_rate_lift") is None) or float(priority.get("win_rate_lift") or 0.0) < 0.03:
        promotion_failure_reasons.append("priority_review_lift_below_3pp")
    if priority.get("wilson_lower_95") is None or priority_baseline.get("win_rate") is None:
        promotion_failure_reasons.append("priority_review_wilson_or_baseline_missing")
    elif float(priority["wilson_lower_95"]) <= float(priority_baseline["win_rate"]):
        promotion_failure_reasons.append("priority_review_wilson_not_above_parent")
    promotion_evidence_sufficient = parent_maturity_sufficient and not promotion_failure_reasons
    return {
        "schema_version": AUDIT_SCHEMA,
        "research_only": True,
        "classification_only": True,
        "production_enabled": False,
        "precision_improvement_claimed": False,
        "label": "t_open_plus3_t_plus_1_through_t_plus_5_target_touch_with_risk_first_path",
        "snapshot_report": snapshot_report,
        "cohorts": cohorts,
        "parent_maturity_sufficient": parent_maturity_sufficient,
        "promotion_evidence_sufficient": promotion_evidence_sufficient,
        "evidence_sufficient": promotion_evidence_sufficient,
        "parent_maturity_requirements": {"n": 300, "signal_dates": 120, "codes": 50},
        "promotion_evidence_requirements": {
            "cohort": "priority_review",
            "n": 300,
            "signal_dates": 120,
            "codes": 50,
            "parent_retention_min": 0.20,
            "win_rate_lift_min": 0.03,
            "wilson_lower_above_parent": True,
        },
        "promotion_evidence_failure_reasons": promotion_failure_reasons,
        "observations": observations,
        "limitations": [
            "news_review_states_are_publication_time_evidence_only",
            "adjusted_data_revisions_are_excluded",
            "target_touch_is_not_execution_or_profitability",
            "read_only_research_not_investment_advice",
        ],
    }


def write_new_json(path: Path, value: Mapping[str, Any]) -> None:
    if path.exists():
        raise FileExistsError(f"output already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise
