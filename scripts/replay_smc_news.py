#!/usr/bin/env python3
"""Create a simulation-only replay from existing SMC news-review artifacts."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path
from typing import Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from ashare_edge_scout.smc_news_replay import build_smc_news_replay, publish_smc_news_replay


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selection-root", type=Path, default=Path("output/edge_scout/selections"))
    parser.add_argument("--news-root", type=Path, default=Path("output/edge_scout/news_reviews"))
    parser.add_argument("--cache-root", type=Path, default=Path(".runtime/news_cache"))
    parser.add_argument("--data-root", type=Path, default=Path("PFrontStockData"))
    parser.add_argument("--output-root", type=Path, default=Path("output/edge_scout/smc_news_replay"))
    parser.add_argument("--start-date")
    parser.add_argument("--end-date")
    parser.add_argument("--run-id")
    parser.add_argument("--include-outcomes", dest="include_outcomes", action="store_true", default=True)
    parser.add_argument("--no-outcomes", dest="include_outcomes", action="store_false")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--top", type=int, default=10)
    args = parser.parse_args(argv)
    if args.top < 0:
        parser.error("--top must be non-negative")
    return args


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    run_id = args.run_id or f"replay-{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    try:
        report = build_smc_news_replay(
            selection_root=args.selection_root,
            news_root=args.news_root,
            cache_root=args.cache_root,
            data_root=args.data_root,
            output_root=args.output_root,
            run_id=run_id,
            start_date=args.start_date,
            end_date=args.end_date,
            include_outcomes=args.include_outcomes,
        )
        if args.dry_run:
            destination = None
        else:
            destination = publish_smc_news_replay(args.output_root, run_id, report)
    except Exception as exc:
        print(f"smc_news_replay_failed: {exc}", file=sys.stderr)
        return 2
    summary = report["summary"]
    cohorts = report["cohorts"]
    print("status=dry_run_success" if args.dry_run else "status=success")
    print(f"would_write={'false' if args.dry_run else 'true'}")
    print(f"schema_version={summary['schema_version']}")
    print(f"simulation_only={str(summary['simulation_only']).lower()}")
    print(f"not_prospective_evidence={str(summary['not_prospective_evidence']).lower()}")
    print(f"candidate_count={summary['candidate_count']}")
    print(f"news_review_run_count={summary['news_review_run_count']}")
    print(f"raw_news_item_count={summary['raw_news_item_count']}")
    print(f"ai_evidence_item_count={summary['ai_evidence_item_count']}")
    print(f"mature_count={cohorts['all_replay_rows']['n']}")
    if destination is not None:
        print(f"run_directory={destination}")
    for row in report["observations"][: args.top]:
        outcome = row.get("outcome") or {}
        print(
            f"{row['code']} {row['signal_date']} state={row['review_state']} "
            f"raw_news={row['raw_news_item_count']} ai_evidence={row['ai_evidence_item_count']} "
            f"outcome={outcome.get('status', 'not_evaluated')}"
        )
    print("说明：以上为 simulation_only 回放，不是前瞻证据、收益、成交或个性化操作建议。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
