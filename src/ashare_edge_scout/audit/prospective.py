"""Immutable prospective watchlist snapshot validation and maturity audit."""

from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from ..research_precision70 import five_close_label
from ..research_v2 import summarize_counts


SNAPSHOT_SCHEMA = "edge_scout_prospective_v1"
WATCH_STAGES = (
    "confirmed_watch",
    "setup_watch",
    "cnstock_pool_watch",
    "discovery_watch",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_valid_snapshot(run_directory: Path) -> tuple[dict[str, Any] | None, str | None]:
    """Validate one snapshot against its run manifest and source artifacts."""

    snapshot_path = run_directory / "prospective_snapshot.json"
    manifest_path = run_directory / "manifest.json"
    if not snapshot_path.exists():
        return None, "snapshot_missing"
    if not manifest_path.exists():
        return None, "manifest_missing"
    try:
        snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None, "invalid_json"
    if snapshot.get("schema_version") != SNAPSHOT_SCHEMA:
        return None, "snapshot_schema_invalid"
    if snapshot.get("run_id") != run_directory.name or manifest.get("run_id") != run_directory.name:
        return None, "run_id_mismatch"
    expected_snapshot = manifest.get("files", {}).get("prospective_snapshot.json", {}).get("sha256")
    if not expected_snapshot or _sha256(snapshot_path) != expected_snapshot:
        return None, "snapshot_hash_mismatch"
    for name, expected in snapshot.get("source_artifacts", {}).items():
        source = run_directory / name
        if not source.is_file() or _sha256(source) != expected:
            return None, f"source_hash_mismatch:{name}"
    try:
        as_of = pd.Timestamp(snapshot["as_of"]).normalize()
        visible = pd.Timestamp(snapshot["visible_data_through"]).normalize()
        published = pd.Timestamp(datetime.fromisoformat(snapshot["published_at_utc"]))
    except (KeyError, TypeError, ValueError):
        return None, "snapshot_time_invalid"
    if pd.isna(as_of) or pd.isna(visible) or pd.isna(published):
        return None, "snapshot_time_invalid"
    if as_of > visible or published.date() < visible.date():
        return None, "snapshot_time_inconsistent"
    if not isinstance(snapshot.get("baseline_rows"), list) or not isinstance(snapshot.get("selected_rows"), list):
        return None, "snapshot_rows_invalid"
    return snapshot, None


def canonical_snapshots(output_root: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Select the earliest eligible valid snapshot for each signal date."""

    valid: list[dict[str, Any]] = []
    invalid: list[dict[str, str]] = []
    ineligible: list[str] = []
    for run_directory in sorted(path for path in output_root.glob("market-*") if path.is_dir()):
        snapshot, error = load_valid_snapshot(run_directory)
        if error:
            if error != "snapshot_missing":
                invalid.append({"run_id": run_directory.name, "error": error})
            continue
        assert snapshot is not None
        if not bool(snapshot.get("prospective_eligible")):
            ineligible.append(run_directory.name)
            continue
        valid.append(snapshot)
    valid.sort(key=lambda item: (item["published_at_utc"], item["run_id"]))
    canonical: dict[str, dict[str, Any]] = {}
    duplicates: list[str] = []
    for snapshot in valid:
        if snapshot["as_of"] in canonical:
            duplicates.append(snapshot["run_id"])
        else:
            canonical[snapshot["as_of"]] = snapshot
    return list(canonical.values()), {
        "directories_seen": len([path for path in output_root.glob("market-*") if path.is_dir()]),
        "valid_eligible": len(valid),
        "canonical": len(canonical),
        "duplicates": duplicates,
        "ineligible": ineligible,
        "invalid": invalid,
    }


def evaluate_archived_row(row: Mapping[str, Any], data_root: Path) -> dict[str, Any]:
    """Evaluate one archived reference close without mutating the snapshot."""

    result: dict[str, Any] = {
        "code": row.get("code"),
        "as_of": row.get("as_of"),
        "watch_stage": row.get("watch_stage"),
        "status": "invalid_snapshot_row",
        "label": None,
        "maturity_date": None,
    }
    try:
        code = str(row["code"])
        as_of = pd.Timestamp(row["as_of"]).normalize()
        archived_close = float(row["research_close"])
    except (KeyError, TypeError, ValueError):
        return result
    if not math.isfinite(archived_close) or archived_close <= 0 or pd.isna(as_of):
        return result
    path = data_root / f"{code}.parquet"
    if not path.is_file():
        result["status"] = "data_missing"
        return result
    try:
        frame = pd.read_parquet(path, columns=["date", "close", "tradestatus"])
    except Exception:
        result["status"] = "data_invalid"
        return result
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame["close"] = pd.to_numeric(frame["close"], errors="coerce")
    frame = frame.dropna(subset=["date"]).sort_values("date", kind="stable").drop_duplicates("date", keep="last")
    origin = frame.loc[frame["date"].eq(as_of)]
    if len(origin) != 1 or str(origin.iloc[0].get("tradestatus", "")) != "1":
        result["status"] = "origin_missing"
        return result
    current_close = float(origin.iloc[0]["close"])
    if not math.isfinite(current_close):
        result["status"] = "data_invalid"
        return result
    if not math.isclose(current_close, archived_close, rel_tol=1e-8, abs_tol=1e-6):
        result.update({"status": "data_revision", "current_origin_close": current_close})
        return result
    future = frame.loc[frame["date"].gt(as_of) & frame["tradestatus"].astype("string").eq("1")].head(5)
    if len(future) < 5:
        result["status"] = "pending"
        return result
    closes = future["close"].astype(float).tolist()
    if not all(math.isfinite(value) and value > 0 for value in closes):
        result["status"] = "data_invalid"
        return result
    result.update({
        "status": "mature",
        "label": five_close_label(archived_close, closes),
        "maturity_date": future.iloc[-1]["date"].date().isoformat(),
    })
    return result


def _cohort_summary(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    mature = [row for row in rows if row.get("status") == "mature"]
    hits = sum(bool(row["label"]) for row in mature)
    result = summarize_counts(len(mature), hits)
    status_counts = pd.Series([row.get("status") for row in rows]).value_counts().sort_index()
    result.update({
        "signal_dates": len({row["as_of"] for row in mature}),
        "codes": len({row["code"] for row in mature}),
        "status_counts": {str(key): int(value) for key, value in status_counts.items()},
    })
    return result


def build_prospective_audit(output_root: Path, data_root: Path) -> dict[str, Any]:
    """Build one read-only audit from canonical prospective snapshots."""

    snapshots, snapshot_report = canonical_snapshots(output_root)
    selected_outcomes: list[dict[str, Any]] = []
    baseline_by_date: dict[str, list[dict[str, Any]]] = {}
    for snapshot in snapshots:
        baseline = [evaluate_archived_row(row, data_root) for row in snapshot["baseline_rows"]]
        selected = [evaluate_archived_row(row, data_root) for row in snapshot["selected_rows"]]
        baseline_by_date[snapshot["as_of"]] = baseline
        selected_outcomes.extend(selected)

    cohorts: dict[str, Any] = {}
    cohort_rows = {"all_watch": selected_outcomes}
    cohort_rows.update({stage: [row for row in selected_outcomes if row.get("watch_stage") == stage] for stage in WATCH_STAGES})
    for name, rows in cohort_rows.items():
        metric = _cohort_summary(rows)
        counts = defaultdict(int)
        for row in rows:
            if row.get("status") == "mature":
                counts[str(row["as_of"])] += 1
        weighted_n = 0
        weighted_hits = 0.0
        baseline_observations = 0
        for as_of, weight in counts.items():
            mature_baseline = [row for row in baseline_by_date.get(as_of, []) if row.get("status") == "mature"]
            if not mature_baseline:
                continue
            precision = sum(bool(row["label"]) for row in mature_baseline) / len(mature_baseline)
            weighted_n += weight
            weighted_hits += weight * precision
            baseline_observations += len(mature_baseline)
        baseline_precision = weighted_hits / weighted_n if weighted_n else None
        metric["same_date_admitted_baseline"] = {
            "observations": baseline_observations,
            "weighted_n": weighted_n,
            "weighted_hits": weighted_hits,
            "precision": baseline_precision,
        }
        metric["precision_lift"] = (
            None if metric["precision"] is None or baseline_precision is None
            else metric["precision"] - baseline_precision
        )
        cohorts[name] = metric
    primary = cohorts["all_watch"]
    sufficient = (
        int(primary["n"]) >= 300
        and int(primary["signal_dates"]) >= 120
        and int(primary["codes"]) >= 50
        and primary["wilson_lower_95"] is not None
        and primary["same_date_admitted_baseline"]["precision"] is not None
        and primary["wilson_lower_95"] > primary["same_date_admitted_baseline"]["precision"]
    )
    return {
        "schema_version": "edge_scout_prospective_audit_v1",
        "research_only": True,
        "classification_only": True,
        "label": "next_five_tradable_closes_reach_3pct_without_close_below_minus_3pct",
        "snapshot_report": snapshot_report,
        "cohorts": cohorts,
        "evidence_sufficient": sufficient,
        "selected_observations": selected_outcomes,
        "limitations": [
            "Automatic scans publish after T+1 and T+2 may already be visible; this is prospective publication evidence, not a pristine T-origin forecast.",
            "Adjusted-data revisions are excluded rather than silently relabeled.",
            "Selection precision is not profitability, execution evidence, or investment advice.",
        ],
    }
