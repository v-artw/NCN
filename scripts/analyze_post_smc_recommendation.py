#!/usr/bin/env python3
"""CLI for read-only post-SMC human-review recommendation analysis."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from ashare_edge_scout.post_smc_recommendation import (  # noqa: E402
    format_post_smc_recommendation,
    write_post_smc_recommendation_csv,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="NCN read-only post-SMC recommendation analysis")
    parser.add_argument("--selection-run", type=Path, required=True)
    parser.add_argument("--news-run", type=Path)
    parser.add_argument("--top", type=int, default=20)
    args = parser.parse_args(argv)
    if args.top < 1:
        parser.error("--top must be at least 1")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    print("SMC 后人工复核建议分析：开始读取已冻结选股/新闻复核结果...", flush=True)
    try:
        output_path, rows = write_post_smc_recommendation_csv(args.selection_run, args.news_run)
    except Exception as exc:
        print(f"post_smc_analysis_failed: {exc}", file=sys.stderr)
        return 2

    print("post_smc_analysis=success")
    print(f"selection_run={args.selection_run}")
    if args.news_run is not None:
        print(f"news_run={args.news_run}")
    print(f"post_smc_analysis_csv={output_path}")
    print(f"post_smc_analysis_count={len(rows)}")
    print(format_post_smc_recommendation(rows, top=args.top))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
