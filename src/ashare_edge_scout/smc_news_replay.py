"""Simulation-only replay for existing SMC selections and news-review artifacts."""

from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .research_v2 import summarize_counts

SCHEMA_VERSION = "ncn_smc_news_replay_v1"
OBSERVATION_SCHEMA = "ncn_smc_news_replay_observation_v1"
NEWS_ITEM_SCHEMA = "ncn_smc_news_replay_news_item_v1"
REVIEW_STATES = ("priority_review", "standard_review", "risk_excluded", "insufficient_evidence", "ai_unavailable")
UNAVAILABLE_STATE = "review_unavailable"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_sha256(value: Mapping[str, Any]) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def _parse_time(value: Any) -> pd.Timestamp | None:
    if not value:
        return None
    timestamp = pd.Timestamp(value)
    if pd.isna(timestamp):
        return None
    if timestamp.tzinfo is None:
        timestamp = timestamp.tz_localize(timezone.utc)
    return timestamp.tz_convert(timezone.utc)


def _date_filter(signal_date: str, start_date: str | None, end_date: str | None) -> bool:
    value = pd.Timestamp(signal_date).normalize()
    if start_date and value < pd.Timestamp(start_date).normalize():
        return False
    if end_date and value > pd.Timestamp(end_date).normalize():
        return False
    return True


def _resolve_source_path(path_text: str, fallback_root: Path) -> Path:
    source = Path(path_text)
    if source.is_dir():
        return source
    candidate = fallback_root / source.name
    if candidate.is_dir():
        return candidate
    return source


def _validate_selection_run(selection_run: Path) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, str]]:
    summary_path = selection_run / "summary.json"
    candidates_path = selection_run / "candidates.json"
    manifest_path = selection_run / "manifest.json"
    if not summary_path.is_file() or not candidates_path.is_file() or not manifest_path.is_file():
        raise ValueError(f"selection run missing summary/candidates/manifest: {selection_run}")
    summary = _read_json(summary_path)
    candidates = _read_json(candidates_path)
    manifest = _read_json(manifest_path)
    if not isinstance(summary, dict) or not isinstance(manifest, dict):
        raise ValueError("selection summary/manifest must be objects")
    if summary.get("schema_version") != "ncn_smc_stock_selector_v4":
        raise ValueError("selection schema invalid")
    if summary.get("run_id") != selection_run.name or manifest.get("run_id") != selection_run.name:
        raise ValueError("selection run_id mismatch")
    if not isinstance(candidates, list) or any(not isinstance(row, dict) for row in candidates):
        raise ValueError("selection candidates must be a list of objects")
    if int(summary.get("candidate_count", -1)) != len(candidates):
        raise ValueError("selection candidate_count mismatch")
    candidates_sha = _require_manifest_hash(selection_run, manifest, "candidates.json")
    summary_sha = _require_manifest_hash(selection_run, manifest, "summary.json")
    return summary, candidates, {"candidates.json": candidates_sha, "summary.json": summary_sha, "manifest.json": _sha256(manifest_path)}


def _validate_news_item(item: Mapping[str, Any]) -> None:
    for key in ("title", "url", "published_at", "retrieved_at", "source"):
        if not item.get(key):
            raise ValueError(f"news item missing {key}")


def _validate_news_run(news_run: Path) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], dict[str, str]]:
    summary_path = news_run / "summary.json"
    reviews_path = news_run / "reviews.json"
    news_path = news_run / "news.json"
    manifest_path = news_run / "manifest.json"
    if not summary_path.is_file() or not reviews_path.is_file() or not news_path.is_file() or not manifest_path.is_file():
        raise ValueError(f"news review run missing summary/reviews/news/manifest: {news_run}")
    summary = _read_json(summary_path)
    reviews = _read_json(reviews_path)
    news = _read_json(news_path)
    manifest = _read_json(manifest_path)
    if not isinstance(summary, dict) or not isinstance(manifest, dict):
        raise ValueError("news summary/manifest must be objects")
    if summary.get("schema_version") != "ncn_smc_news_ai_review_v1":
        raise ValueError("news review schema invalid")
    if summary.get("run_id") != news_run.name or manifest.get("run_id") != news_run.name:
        raise ValueError("news review run_id mismatch")
    if str(summary.get("source_candidates_sha256") or "") != str(manifest.get("source_candidates_sha256") or ""):
        raise ValueError("news source_candidates_sha256 mismatch")
    if not isinstance(reviews, list) or any(not isinstance(row, dict) for row in reviews):
        raise ValueError("reviews must be a list of objects")
    if not isinstance(news, list) or any(not isinstance(row, dict) for row in news):
        raise ValueError("news must be a list of objects")
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
    for record in news:
        for item in list(record.get("items") or []) + list(record.get("ai_evidence_items") or []):
            if not isinstance(item, dict):
                raise ValueError("news item must be an object")
            _validate_news_item(item)
    reviews_sha = _require_manifest_hash(news_run, manifest, "reviews.json")
    news_sha = _require_manifest_hash(news_run, manifest, "news.json")
    summary_sha = _require_manifest_hash(news_run, manifest, "summary.json")
    return summary, reviews, news, {"reviews.json": reviews_sha, "news.json": news_sha, "summary.json": summary_sha, "manifest.json": _sha256(manifest_path)}


def _selection_by_candidates_sha(selection_root: Path, source_sha: str) -> Path | None:
    for run in sorted(path for path in selection_root.glob("select-*") if (path / "manifest.json").is_file()):
        manifest = _read_json(run / "manifest.json")
        if _manifest_hash(manifest, "candidates.json") == source_sha:
            return run
    return None


def _resolve_selection_for_news(news_summary: Mapping[str, Any], selection_root: Path) -> Path:
    source = _resolve_source_path(str(news_summary.get("source_selection_run") or ""), selection_root)
    if source.is_dir():
        return source
    by_hash = _selection_by_candidates_sha(selection_root, str(news_summary.get("source_candidates_sha256") or ""))
    if by_hash is not None:
        return by_hash
    raise ValueError("matching selection run not found for news review")


def _time_diagnostics(signal_date: str, items: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    signal = pd.Timestamp(signal_date).tz_localize(timezone.utc) if pd.Timestamp(signal_date).tzinfo is None else pd.Timestamp(signal_date).tz_convert(timezone.utc)
    published = [_parse_time(item.get("published_at")) for item in items]
    retrieved = [_parse_time(item.get("retrieved_at")) for item in items]
    published_ok = [item for item in published if item is not None]
    retrieved_ok = [item for item in retrieved if item is not None]
    published_after = sum(item.normalize() > signal.normalize() for item in published_ok)
    retrieved_after = sum(item.normalize() > signal.normalize() for item in retrieved_ok)
    reason = None
    if retrieved_after:
        reason = "retrieved_at_after_signal_date"
    elif published_after:
        reason = "published_at_after_signal_date"
    return {
        "min_published_at_utc": None if not published_ok else min(published_ok).isoformat(),
        "max_published_at_utc": None if not published_ok else max(published_ok).isoformat(),
        "min_retrieved_at_utc": None if not retrieved_ok else min(retrieved_ok).isoformat(),
        "max_retrieved_at_utc": None if not retrieved_ok else max(retrieved_ok).isoformat(),
        "published_after_signal_count": int(published_after),
        "retrieved_after_signal_count": int(retrieved_after),
        "missing_published_at_count": len(items) - len(published_ok),
        "missing_retrieved_at_count": len(items) - len(retrieved_ok),
        "not_point_in_time_reason": reason,
    }


def evaluate_replay_target_touch(row: Mapping[str, Any], data_root: Path) -> dict[str, Any]:
    result: dict[str, Any] = {"status": "invalid_snapshot_row", "target_touched": None, "risk_first_3pct": None, "maturity_date": None}
    try:
        code = str(row["code"])
        signal_date = pd.Timestamp(row["signal_date"]).normalize()
        archived_close = float(row["research_close"])
    except (KeyError, TypeError, ValueError):
        return result
    if not code or pd.isna(signal_date) or not math.isfinite(archived_close) or archived_close <= 0:
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


def _observation(
    *,
    run_id: str,
    candidate: Mapping[str, Any],
    review: Mapping[str, Any] | None,
    news_record: Mapping[str, Any] | None,
    selection_run: Path,
    news_run: Path,
    source_candidates_sha256: str,
    include_outcomes: bool,
    data_root: Path,
) -> dict[str, Any]:
    code = str(candidate.get("code") or "")
    signal_date = str(candidate.get("signal_date") or "")
    raw_items = list((news_record or {}).get("items") or [])
    ai_items = list((news_record or {}).get("ai_evidence_items") or [])
    row = {
        "schema_version": OBSERVATION_SCHEMA,
        "replay_run_id": run_id,
        "simulation_only": True,
        "not_prospective_evidence": True,
        "not_for_production_selection": True,
        "code": code,
        "signal_date": signal_date,
        "candidate_key": f"{signal_date}|{code}",
        "source_selection_run": str(selection_run),
        "source_news_review_run": str(news_run),
        "source_candidates_sha256": source_candidates_sha256,
        "research_close": candidate.get("research_close"),
        "selection_reason": candidate.get("selection_reason"),
        "risk_warning_count": int(candidate.get("risk_warning_count") or 0),
        "risk_warnings": list(candidate.get("risk_warnings") or []),
        "start_diagnostic_type": candidate.get("start_diagnostic_type"),
        "review_state": str((review or {}).get("review_state") or UNAVAILABLE_STATE),
        "review_state_source": "news_review_artifact" if review else "missing_review_artifact",
        "assessment": (review or {}).get("assessment"),
        "confidence": float((review or {}).get("confidence") or 0.0),
        "catalyst_quality": (review or {}).get("catalyst_quality"),
        "event_risk": (review or {}).get("event_risk"),
        "model": (review or {}).get("model"),
        "raw_news_item_count": len(raw_items),
        "ai_evidence_item_count": len(ai_items),
        "source_count": int((review or {}).get("source_count") or len({str(item.get("source")) for item in raw_items if isinstance(item, dict)})),
        "news_time_diagnostics": _time_diagnostics(signal_date, raw_items),
    }
    if include_outcomes:
        row["outcome"] = evaluate_replay_target_touch(row, data_root)
    return row


def _flatten_news_items(run_id: str, observation: Mapping[str, Any], news_record: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    if news_record is None:
        return []
    raw_items = list(news_record.get("items") or [])
    ai_items = list(news_record.get("ai_evidence_items") or [])
    ai_hashes = {_json_sha256(item) for item in ai_items if isinstance(item, dict)}
    rows: list[dict[str, Any]] = []
    seen = set()
    for role, items in (("raw", raw_items), ("ai_evidence", ai_items)):
        for item in items:
            if not isinstance(item, dict):
                continue
            item_hash = _json_sha256(item)
            key = (role, item_hash)
            if key in seen:
                continue
            seen.add(key)
            diag = _time_diagnostics(str(observation["signal_date"]), [item])
            rows.append({
                "schema_version": NEWS_ITEM_SCHEMA,
                "replay_run_id": run_id,
                "candidate_key": observation["candidate_key"],
                "code": observation["code"],
                "signal_date": observation["signal_date"],
                "source_news_review_run": observation["source_news_review_run"],
                "role": role,
                "also_ai_evidence": item_hash in ai_hashes,
                "source": item.get("source"),
                "title": item.get("title"),
                "url": item.get("url"),
                "published_at": item.get("published_at"),
                "retrieved_at": item.get("retrieved_at"),
                "published_relative_to_signal": "post_signal" if diag["published_after_signal_count"] else "on_or_before_signal",
                "retrieved_after_signal": bool(diag["retrieved_after_signal_count"]),
                "not_point_in_time": bool(diag["not_point_in_time_reason"]),
                "item_sha256": item_hash,
            })
    return rows


def _cohort_summary(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    mature = [row for row in rows if (row.get("outcome") or {}).get("status") == "mature"]
    hits = sum(bool((row.get("outcome") or {}).get("target_touched")) for row in mature)
    result = summarize_counts(len(mature), hits)
    result["win_rate"] = result.pop("precision")
    result["signal_dates"] = len({row.get("signal_date") for row in mature})
    result["codes"] = len({row.get("code") for row in mature})
    statuses = Counter(str((row.get("outcome") or {}).get("status", "not_evaluated")) for row in rows)
    result["status_counts"] = dict(sorted(statuses.items()))
    result["interpretation_boundary"] = "descriptive_simulation_only_not_selection_precision"
    return result


def _build_cohorts(observations: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    cohorts: dict[str, Any] = {"all_replay_rows": _cohort_summary(observations)}
    for state in (*REVIEW_STATES, UNAVAILABLE_STATE):
        cohorts[state] = _cohort_summary([row for row in observations if row.get("review_state") == state])
    cohorts["published_after_signal"] = _cohort_summary([
        row for row in observations if int((row.get("news_time_diagnostics") or {}).get("published_after_signal_count") or 0) > 0
    ])
    cohorts["retrieved_after_signal"] = _cohort_summary([
        row for row in observations if int((row.get("news_time_diagnostics") or {}).get("retrieved_after_signal_count") or 0) > 0
    ])
    cohorts["has_ai_evidence_items"] = _cohort_summary([row for row in observations if int(row.get("ai_evidence_item_count") or 0) > 0])
    cohorts["no_ai_evidence_items"] = _cohort_summary([row for row in observations if int(row.get("ai_evidence_item_count") or 0) == 0])
    return cohorts


def _source_artifacts_entry(selection_run: Path, news_run: Path, selection_hashes: Mapping[str, str], news_hashes: Mapping[str, str]) -> dict[str, Any]:
    return {
        "selection_run": str(selection_run),
        "news_review_run": str(news_run),
        "selection": {name: {"path": str(selection_run / name), "sha256": digest} for name, digest in selection_hashes.items()},
        "news_review": {name: {"path": str(news_run / name), "sha256": digest} for name, digest in news_hashes.items()},
    }


def build_smc_news_replay(
    *,
    selection_root: Path,
    news_root: Path,
    cache_root: Path | None,
    data_root: Path,
    output_root: Path,
    run_id: str,
    start_date: str | None = None,
    end_date: str | None = None,
    include_outcomes: bool = True,
) -> dict[str, Any]:
    observations: list[dict[str, Any]] = []
    news_items: list[dict[str, Any]] = []
    source_artifacts: list[dict[str, Any]] = []
    invalid_runs: list[dict[str, str]] = []
    seen_news_runs = 0
    for news_run in sorted(path for path in news_root.glob("news-review-*") if path.is_dir()):
        try:
            news_summary, reviews, news_records, news_hashes = _validate_news_run(news_run)
            selection_run = _resolve_selection_for_news(news_summary, selection_root)
            selection_summary, candidates, selection_hashes = _validate_selection_run(selection_run)
            source_sha = str(news_summary.get("source_candidates_sha256") or "")
            if source_sha != selection_hashes["candidates.json"]:
                raise ValueError("news review is not bound to selection candidates hash")
            signal_date = str(selection_summary.get("signal_date") or "")
            if signal_date and not _date_filter(signal_date, start_date, end_date):
                continue
            reviews_by_code = {str(row.get("code")): row for row in reviews}
            news_by_code = {str(row.get("code")): row for row in news_records}
            seen_news_runs += 1
            source_artifacts.append(_source_artifacts_entry(selection_run, news_run, selection_hashes, news_hashes))
            for candidate in candidates:
                code = str(candidate.get("code") or "")
                observation = _observation(
                    run_id=run_id,
                    candidate=candidate,
                    review=reviews_by_code.get(code),
                    news_record=news_by_code.get(code),
                    selection_run=selection_run,
                    news_run=news_run,
                    source_candidates_sha256=source_sha,
                    include_outcomes=include_outcomes,
                    data_root=data_root,
                )
                observations.append(observation)
                news_items.extend(_flatten_news_items(run_id, observation, news_by_code.get(code)))
        except Exception as exc:
            invalid_runs.append({"run_id": news_run.name, "error": str(exc)})
    cohorts = _build_cohorts(observations)
    summary = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "published_at_utc": _utc_now(),
        "simulation_only": True,
        "not_prospective_evidence": True,
        "prospective_evidence_claimed": False,
        "research_only": True,
        "classification_only": True,
        "production_enabled": False,
        "source_mode": "news_reviews",
        "output_namespace": str(output_root),
        "source_news_review_root": str(news_root),
        "source_selection_root": str(selection_root),
        "source_cache_root": None if cache_root is None else str(cache_root),
        "candidate_count": len(observations),
        "news_review_run_count": seen_news_runs,
        "invalid_news_review_runs": invalid_runs,
        "raw_news_item_count": sum(int(row.get("raw_news_item_count") or 0) for row in observations),
        "ai_evidence_item_count": sum(int(row.get("ai_evidence_item_count") or 0) for row in observations),
        "date_range": {"start_date": start_date, "end_date": end_date},
        "replay_contract": {
            "selection_source": "existing_immutable_smc_selection_artifacts",
            "news_source": "existing_news_review_artifacts",
            "news_time_basis": "published_at_utc_and_retrieved_at_utc_metadata",
            "point_in_time_status": "not_point_in_time; retrieved_after_signal_allowed_only_for_simulation",
            "no_network_fetch": True,
            "no_ai_call": True,
            "no_execution_or_profit_loss": True,
        },
        "label_contract": {
            "enabled": include_outcomes,
            "data_source": "local_adjusted_research_daily_bars",
            "entry_reference": "next stock-tradable T open",
            "target": "T open * 1.03",
            "eligible_window": "T+1 through T+5 stock-tradable rows; T high excluded",
            "risk_path": "risk_first_3pct checks whether -3% low is touched before +3% target",
            "not_returns_or_execution": True,
        },
        "causality_boundary": "simulation_only_replay; historical_news_metadata_may_have_been_retrieved_after_signal_date; never_use_as_prospective_evidence_or_production_selection_precision",
        "limitations": [
            "simulation_only_not_prospective_evidence",
            "historical_news_metadata_collected_after_signal_date",
            "published_at_is_provider_metadata_not_exchange_sla",
            "headline_and_announcement_metadata_not_full_article_text",
            "llm_review_states_from_prior_runs_are_not_recomputed",
            "adjusted_research_daily_bars_not_executable_prices",
            "target_touch_is_not_execution_or_profitability",
            "read_only_research_not_investment_advice",
        ],
    }
    return {
        "summary": summary,
        "observations": observations,
        "news_items": news_items,
        "cohorts": cohorts,
        "source_artifacts": source_artifacts,
    }


def _guard_output_root(output_root: Path) -> None:
    resolved = output_root.resolve()
    prospective = (Path("output/edge_scout/smc_news_prospective")).resolve()
    if resolved == prospective or resolved.is_relative_to(prospective):
        raise ValueError("simulation outputs cannot write into the prospective archive root")


def publish_smc_news_replay(output_root: Path, run_id: str, report: Mapping[str, Any]) -> Path:
    _guard_output_root(output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    destination = output_root / run_id
    temporary = output_root / f".{run_id}.tmp"
    if destination.exists() or temporary.exists():
        raise FileExistsError(f"SMC news replay already exists: {destination}")
    temporary.mkdir()
    try:
        files = {
            "summary.json": report["summary"],
            "observations.json": report["observations"],
            "news_items.json": report["news_items"],
            "cohorts.json": report["cohorts"],
            "source_artifacts.json": report["source_artifacts"],
        }
        for name, value in files.items():
            (temporary / name).write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
        manifest = {
            "schema_version": SCHEMA_VERSION,
            "run_id": run_id,
            "simulation_only": True,
            "not_prospective_evidence": True,
            "files": {name: {"sha256": _sha256(temporary / name)} for name in files},
        }
        (temporary / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
        os.replace(temporary, destination)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return destination
