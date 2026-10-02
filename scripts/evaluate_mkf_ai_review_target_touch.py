#!/usr/bin/env python3
"""Evaluate immutable MKF AI review strata against an exploratory target-touch grid."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

from ashare_edge_scout.pmkf_mkf.mkf_post_cross_lag_comparison import GRID_HORIZONS, GRID_TARGET_PCTS
from ashare_edge_scout.research_mkf_ai_target_touch import analyze_review_run, analysis_fingerprint


def _csv_ints(value: str) -> tuple[int, ...]:
    try:
        values = tuple(int(item) for item in value.split(","))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("expected comma-separated integers") from exc
    if not values or len(set(values)) != len(values) or min(values) < 1 or max(values) > 20:
        raise argparse.ArgumentTypeError("values must be unique integers between 1 and 20")
    return values


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review-run", type=Path, action="append", required=True)
    parser.add_argument("--data-root", type=Path, default=PROJECT_ROOT / "PFrontStockData")
    parser.add_argument("--target-pcts", type=_csv_ints, default=GRID_TARGET_PCTS)
    parser.add_argument("--horizons", type=_csv_ints, default=GRID_HORIZONS)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    if len({path.expanduser().resolve() for path in args.review_run}) != len(args.review_run):
        parser.error("--review-run values must be unique")
    if not 1 <= args.workers <= 16:
        parser.error("--workers must be between 1 and 16")
    if tuple(args.target_pcts) != GRID_TARGET_PCTS or tuple(args.horizons) != GRID_HORIZONS:
        parser.error("this exploratory study requires the complete existing 1..20 target and horizon grids")
    return args


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    keys = list(rows[0]) if rows else []
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    output = args.output_dir.expanduser().resolve()
    temporary = output.parent / f".{output.name}.tmp"
    if output.exists() or temporary.exists():
        raise FileExistsError(f"output directory already exists: {output}")
    reports = [analyze_review_run(path, args.data_root, target_pcts=args.target_pcts, horizons=args.horizons) for path in args.review_run]
    temporary.mkdir(parents=True)
    try:
        _write_json(temporary / "summary.json", {"schema_version": "ncn_mkf_ai_review_target_touch_study_v1", "generated_at_utc": datetime.now(timezone.utc).isoformat(), "review_run_count": len(reports), "target_pcts": list(args.target_pcts), "horizons": list(args.horizons), "boundaries": reports[0]["boundaries"], "limitations": reports[0]["limitations"], "runs": [{key: report[key] for key in ("review_run", "provider", "model", "prompt_sha256", "coverage")} | {"protocol_fingerprint": analysis_fingerprint(report), "independent_observation": False if report.get("replay_provenance") else True} for report in reports]})
        evidence = [dict(item, review_run=report["review_run"]) for report in reports for item in report["candidate_evidence"]]
        _write_csv(temporary / "candidate_evidence.csv", evidence)
        grids = [dict(cell, review_run=report["review_run"], provider=report["provider"], model=report["model"], review_state=state) for report in reports for state, stratum in report["strata"].items() for cell in stratum["grid"]]
        _write_csv(temporary / "stratum_grid.csv", grids)
        for index, report in enumerate(reports):
            _write_json(temporary / f"run_{index:02d}.json", report)
        manifest = {"schema_version": "ncn_mkf_ai_review_target_touch_study_v1", "files": {path.name: {"sha256": _sha256(path)} for path in sorted(temporary.iterdir()) if path.is_file()}, "ai_calls_made": 0, "news_refresh_performed": False}
        _write_json(temporary / "manifest.json", manifest)
        os.replace(temporary, output)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    print(f"output_dir={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
