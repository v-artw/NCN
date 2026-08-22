#!/usr/bin/env python3
"""Create an immutable maturity audit for SMC plus news-review prospective archives."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from ashare_edge_scout.smc_news_prospective import build_smc_news_prospective_audit, write_new_json


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=Path("output/edge_scout"))
    parser.add_argument("--data-root", type=Path, default=Path("PFrontStockData"))
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    report = build_smc_news_prospective_audit(args.output_root, args.data_root)
    write_new_json(args.output, report)
    all_smc = report["cohorts"]["all_smc"]
    print(f"canonical_smc_news_snapshots={report['snapshot_report']['canonical']}")
    print(f"mature_all_smc={all_smc['n']}")
    print(f"parent_maturity_sufficient={report['parent_maturity_sufficient']}")
    print(f"promotion_evidence_sufficient={report['promotion_evidence_sufficient']}")
    print(f"evidence_sufficient={report['evidence_sufficient']}")
    print(f"output={args.output}")


if __name__ == "__main__":
    main()
