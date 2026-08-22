#!/usr/bin/env python3
"""Freeze a prospective SMC selection plus news AI review archive."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from ashare_edge_scout.smc_news_prospective import (
    find_canonical_smc_news_snapshot,
    publish_smc_news_snapshot,
    resolve_latest_news_run,
    resolve_selection_for_news,
    selection_signal_date,
)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selection-root", type=Path, default=Path("output/edge_scout/selections"))
    parser.add_argument("--selection-run", type=Path)
    parser.add_argument("--news-root", type=Path, default=Path("output/edge_scout/news_reviews"))
    parser.add_argument("--news-run", type=Path)
    parser.add_argument("--output-root", type=Path, default=Path("output/edge_scout/smc_news_prospective"))
    parser.add_argument("--run-id")
    parser.add_argument(
        "--check-existing-signal-date",
        action="store_true",
        help="Only check whether the selection signal date already has a canonical prospective archive.",
    )
    return parser.parse_args(argv)


def _print_existing(signal_date: str, existing: dict[str, object] | None) -> None:
    print(f"archive_signal_date={signal_date}")
    if existing:
        print("archive_duplicate=1")
        print(f"existing_archive_run_id={existing['run_id']}")
        print(f"existing_archive={existing['archive_path']}")
    else:
        print("archive_duplicate=0")


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    if args.check_existing_signal_date:
        if args.selection_run is None:
            raise SystemExit("--check-existing-signal-date requires --selection-run")
        signal_date = selection_signal_date(args.selection_run)
        _print_existing(signal_date, find_canonical_smc_news_snapshot(args.output_root, signal_date))
        return

    news_run = args.news_run or resolve_latest_news_run(args.news_root)
    selection_run = args.selection_run or resolve_selection_for_news(
        __import__("json").loads((news_run / "summary.json").read_text(encoding="utf-8")),
        args.selection_root,
    )
    signal_date = selection_signal_date(selection_run)
    existing = find_canonical_smc_news_snapshot(args.output_root, signal_date)
    if existing:
        print("smc_news_prospective_archive_status=skipped_existing_signal_date")
        print(f"archive_signal_date={signal_date}")
        print(f"existing_archive_run_id={existing['run_id']}")
        print(f"existing_archive={existing['archive_path']}")
        return
    destination = publish_smc_news_snapshot(
        selection_run=selection_run,
        news_run=news_run,
        output_root=args.output_root,
        run_id=args.run_id,
    )
    print("smc_news_prospective_archive_status=created")
    print(f"archive_signal_date={signal_date}")
    print(f"smc_news_prospective_archive={destination}")


if __name__ == "__main__":
    main()
