#!/usr/bin/env python3
"""Research-production Edge Scout entry point with freshness and calendar gates."""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from ashare_edge_scout.operations import (  # noqa: E402
    FreshnessPolicy,
    load_calendar_file,
    retain_successful_runs,
)
from ashare_edge_scout.scanner import EdgeScoutScanInput, run_edge_scout_scan  # noqa: E402


class ConsoleProgressReporter:
    """Self-contained throttled progress reporter for the hardened CLI path."""

    def __init__(self) -> None:
        self._last_stage: str | None = None
        self._last_processed = 0
        self._last_time = 0.0

    def update(self, stage: str, processed: int, total: int, code: str | None) -> None:
        now = time.monotonic()
        should_print = (
            stage != self._last_stage
            or (total > 0 and processed == total)
            or processed - self._last_processed >= 100
            or now - self._last_time >= 10.0
        )
        if not should_print:
            return
        percent = processed / total * 100.0 if total else 0.0
        current = f" | current={code}" if code else ""
        print(
            f"progress stage={stage} processed={processed}/{total} ({percent:.1f}%){current}",
            file=sys.stderr,
            flush=True,
        )
        self._last_stage = stage
        self._last_processed = processed
        self._last_time = now


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Edge Scout research-production read-only scan.")
    parser.add_argument("--data-root", required=True, type=Path)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--calendar", required=True, type=Path, help="newline-delimited YYYY-MM-DD calendar")
    parser.add_argument("--calendar-sha256", required=True, help="approved calendar content SHA-256")
    parser.add_argument("--as-of", type=date.fromisoformat, default=None)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--max-lag-trading-days", type=int, default=0)
    parser.add_argument("--minimum-coverage-ratio", type=float, default=0.95)
    parser.add_argument("--retain-runs", type=int, default=30)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    version, calendar = load_calendar_file(args.calendar, expected_sha256=args.calendar_sha256)
    policy = FreshnessPolicy(
        calendar_version=version,
        max_lag_trading_days=args.max_lag_trading_days,
        minimum_coverage_ratio=args.minimum_coverage_ratio,
    )
    progress = ConsoleProgressReporter()
    result = run_edge_scout_scan(
        EdgeScoutScanInput(
            data_root=args.data_root,
            config_path=args.config,
            output_root=args.output_root,
            as_of=args.as_of,
            run_id=args.run_id,
        ),
        progress_callback=progress.update,
        freshness_calendar=calendar,
        freshness_policy=policy,
        freshness_now=datetime.now(timezone.utc),
    )
    removed = retain_successful_runs(args.output_root, keep=args.retain_runs)
    summary = json.loads(result.summary_path.read_text(encoding="utf-8"))
    print("status=success")
    print(f"run_id={args.run_id}")
    print(f"as_of={result.as_of.isoformat()}")
    print(f"run_directory={result.run_directory}")
    print(f"retained_removed={len(removed)}")
    print(f"freshness={json.dumps(summary.get('freshness_evidence', {}), sort_keys=True)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"edge_scout_production_failed: {exc}", file=sys.stderr)
        raise SystemExit(2)
