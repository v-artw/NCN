"""Read-only target-touch attribution for immutable MKF AI review runs."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .mkf_ai_review import _sha256, load_persisted_mkf_review_inputs
from .pmkf_mkf.mkf_post_cross_lag_comparison import GRID_HORIZONS, GRID_TARGET_PCTS
from .research_v2 import summarize_counts

SCHEMA_VERSION = "ncn_mkf_ai_review_target_touch_v1"
REVIEW_STATES = (
    "priority_research", "standard_research", "insufficient_evidence", "risk_attention", "ai_unavailable",
)
REQUIRED_COLUMNS = ("date", "open", "high", "tradestatus")


def _outcomes(frame: pd.DataFrame, signal_dates: set[str], max_horizon: int) -> dict[str, dict[str, Any]]:
    data = frame.loc[:, REQUIRED_COLUMNS].copy()
    data["date"] = pd.to_datetime(data["date"], errors="coerce").dt.normalize()
    if data["date"].isna().any() or data["date"].duplicated().any():
        raise ValueError("daily bars contain invalid or duplicate dates")
    data = data.sort_values("date", kind="stable").reset_index(drop=True)
    tradable = np.flatnonzero(data["tradestatus"].astype("string").eq("1").fillna(False).to_numpy())
    positions = {int(index): position for position, index in enumerate(tradable)}
    opens = pd.to_numeric(data["open"], errors="coerce").to_numpy(dtype=float)
    highs = pd.to_numeric(data["high"], errors="coerce").to_numpy(dtype=float)
    by_date = {str(value.date()): index for index, value in enumerate(data["date"])}
    results: dict[str, dict[str, Any]] = {}
    for signal_date in signal_dates:
        normalized_signal_date = str(pd.Timestamp(signal_date).date())
        origin = by_date.get(normalized_signal_date)
        position = positions.get(origin) if origin is not None else None
        row: dict[str, Any] = {"status": "origin_invalid", "signal_date": signal_date}
        if position is None:
            results[signal_date] = row
            continue
        if position + 1 >= len(tradable):
            row["status"] = "entry_pending"
            results[signal_date] = row
            continue
        entry_index = int(tradable[position + 1])
        entry_open = opens[entry_index]
        row.update({"entry_date": str(data["date"].iat[entry_index].date())})
        if not np.isfinite(entry_open) or entry_open <= 0:
            row["status"] = "entry_invalid"
            results[signal_date] = row
            continue
        future = tradable[position + 2:position + 2 + max_horizon]
        row["entry_open"] = float(entry_open)
        future_highs = highs[future]
        if not np.isfinite(future_highs).all():
            row["status"] = "invalid"
            results[signal_date] = row
            continue
        cumulative = np.maximum.accumulate(future_highs)
        row.update({
            "status": "mature" if len(future) == max_horizon else "partial",
            "max_highs": [float(value) for value in cumulative],
        })
        results[signal_date] = row
    return results


def _review_rows(run: Path) -> tuple[dict[str, Any], list[dict[str, Any]], Any]:
    persisted = load_persisted_mkf_review_inputs(run)
    manifest = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
    review_path = run / "reviews.json"
    expected = manifest["files"]["reviews.json"]["sha256"]
    if _sha256(review_path) != expected:
        raise ValueError("reviews.json hash does not match manifest")
    summary = json.loads((run / "summary.json").read_text(encoding="utf-8"))
    rows = json.loads(review_path.read_text(encoding="utf-8"))
    if not isinstance(rows, list) or any(not isinstance(row, Mapping) for row in rows):
        raise ValueError("reviews.json must be a list of objects")
    candidates = {(str(row["code"]), str(row["signal_date"])) for row in persisted.candidates}
    mapped: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        key = (str(row.get("code") or ""), str(row.get("signal_date") or ""))
        if key not in candidates or key in mapped:
            raise ValueError("review identities do not exactly match source candidates")
        state = str(row.get("review_state") or "")
        if state not in REVIEW_STATES:
            raise ValueError("review contains invalid review_state")
        mapped[key] = dict(row)
    if set(mapped) != candidates:
        raise ValueError("review identities do not exactly match source candidates")
    return summary, [mapped[(str(c["code"]), str(c["signal_date"]))] for c in persisted.candidates], persisted


def analyze_review_run(run: Path, data_root: Path, *, target_pcts: Sequence[int] = GRID_TARGET_PCTS, horizons: Sequence[int] = GRID_HORIZONS) -> dict[str, Any]:
    if not target_pcts or not horizons or min(target_pcts) < 1 or max(target_pcts) > 20 or min(horizons) < 1 or max(horizons) > 20:
        raise ValueError("targets and horizons must be unique values between 1 and 20")
    if len(set(target_pcts)) != len(target_pcts) or len(set(horizons)) != len(horizons):
        raise ValueError("targets and horizons must not contain duplicates")
    run = run.resolve()
    summary, reviews, persisted = _review_rows(run)
    max_horizon = max(horizons)
    outcomes: dict[tuple[str, str], dict[str, Any]] = {}
    files: dict[str, str] = {}
    by_code: dict[str, set[str]] = {}
    for row in reviews:
        by_code.setdefault(str(row["code"]), set()).add(str(row["signal_date"]))
    for code, dates in by_code.items():
        path = data_root / f"{code}.parquet"
        if not path.is_file():
            raise ValueError(f"missing daily bars for {code}")
        files[code] = _sha256(path)
        for date, outcome in _outcomes(pd.read_parquet(path, columns=list(REQUIRED_COLUMNS)), dates, max_horizon).items():
            outcomes[(code, date)] = outcome
    evidence = []
    for row in reviews:
        key = (str(row["code"]), str(row["signal_date"]))
        evidence.append({"code": key[0], "signal_date": key[1], "review_state": row["review_state"], **outcomes[key]})
    coverage = Counter(item["review_state"] for item in evidence)
    status_counts = Counter(item["status"] for item in evidence)
    strata: dict[str, Any] = {}
    for state in REVIEW_STATES:
        members = [item for item in evidence if item["review_state"] == state]
        grid: list[dict[str, Any]] = []
        for horizon in horizons:
            mature_all = [item for item in evidence if len(item.get("max_highs", [])) >= horizon]
            mature = [item for item in members if len(item.get("max_highs", [])) >= horizon]
            for target in target_pcts:
                baseline_hits = sum(item["max_highs"][horizon - 1] >= item["entry_open"] * (1 + target / 100) for item in mature_all)
                hits = sum(item["max_highs"][horizon - 1] >= item["entry_open"] * (1 + target / 100) for item in mature)
                metric, baseline = summarize_counts(len(mature), hits), summarize_counts(len(mature_all), baseline_hits)
                grid.append({"target_pct": target, "horizon": horizon, "n": metric["n"], "hits": metric["hits"], "target_hit_rate": metric["precision"], "wilson_lower_95": metric["wilson_lower_95"], "wilson_upper_95": metric["wilson_upper_95"], "baseline_n": baseline["n"], "baseline_target_hit_rate": baseline["precision"], "lift": None if metric["precision"] is None or baseline["precision"] is None else metric["precision"] - baseline["precision"]})
        strata[state] = {"candidate_count": len(members), "mature_count": sum(item["status"] == "mature" for item in members), "grid": grid}
    return {"schema_version": SCHEMA_VERSION, "review_run": str(run), "review_manifest_sha256": _sha256(run / "manifest.json"), "source_selection_run": str(persisted.source_selection_run), "source_candidates_sha256": persisted.candidates_sha256, "provider": summary.get("ai_provider"), "model": summary.get("ai_model"), "prompt_sha256": summary.get("prompt_sha256"), "replay_provenance": summary.get("replay_provenance"), "target_pcts": list(target_pcts), "horizons": list(horizons), "coverage": {"review_state_counts": dict(coverage), "outcome_status_counts": dict(status_counts)}, "data_files_sha256": files, "strata": strata, "candidate_evidence": evidence, "boundaries": {"research_only": True, "production_enabled": False, "allow_live_order_submission": False, "ai_calls_made": 0, "news_refresh_performed": False, "target_touch_not_fill_or_pnl": True, "selection_prohibited": True}, "limitations": ["exploratory_full_grid_multiple_testing_no_best_cell_selection", "review_runs_and_replays_are_not_independent", "target_touch_is_not_a_trade_fill_or_return"]}


def analysis_fingerprint(report: Mapping[str, Any]) -> str:
    value = {key: report.get(key) for key in ("source_candidates_sha256", "provider", "model", "prompt_sha256", "replay_provenance")}
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
