#!/usr/bin/env python3
"""CLI for the read-only SMC stock selector."""

from __future__ import annotations

import argparse
import csv
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from ashare_edge_scout.human_review_summary import format_human_review_summary, write_human_review_summary_csv
from ashare_edge_scout.stock_selector import run_stock_selection


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="NCN read-only SMC stock selector")
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--as-of", type=date.fromisoformat, help="T-1 signal date (YYYY-MM-DD)")
    parser.add_argument("--run-id")
    parser.add_argument("--top", type=int, default=20)
    args = parser.parse_args(argv)
    if args.top < 1:
        parser.error("--top must be at least 1")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    print("SMC 选股：开始读取本地日线并扫描候选...", flush=True)

    def progress(done: int, total: int, selected: int) -> None:
        print(f"SMC 选股进度：已评估 {done}/{total}，当前候选 {selected}", flush=True)

    try:
        result = run_stock_selection(
            data_root=args.data_root,
            config_path=args.config,
            output_root=args.output_root,
            as_of=args.as_of,
            run_id=args.run_id,
            progress=progress,
        )
    except Exception as exc:
        print(f"stock_selection_failed: {exc}", file=sys.stderr)
        return 2

    print("status=success")
    print(f"signal_date={result.signal_date.isoformat()}")
    print("intended_entry_reference_session=next_trading_session_open")
    print("later_target_contract=entry_open_x_1.03_observed_on_entry_plus_1_through_entry_plus_5")
    print(f"candidate_count={result.candidate_count}")
    print(f"run_directory={result.run_directory}")
    print(f"timestamped_csv={result.timestamped_candidates_path}")
    human_summary_path, human_summary_rows = write_human_review_summary_csv(result.run_directory)
    print(f"human_review_summary_csv={human_summary_path}")
    with result.candidates_path.open("r", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))[: args.top]
    if not rows:
        print("\nSMC 候选：无")
        print(format_human_review_summary(human_summary_rows))
        return 0
    print("\nSMC 只读研究候选（非买入建议）")
    print(f"{'#':>2}  {'code':<11} {'close':>8} {'amount(亿)':>10} {'gap%':>7} {'diag':<6} {'warnings'}")
    for index, row in enumerate(rows, start=1):
        warnings = row["risk_warnings"] or "none"
        diagnostic = row.get("start_diagnostic_label", "未分类")
        print(
            f"{index:>2}  {row['code']:<11} {float(row['research_close']):>8.2f} "
            f"{float(row['amount_cny']) / 100_000_000:>10.2f} "
            f"{float(row['smc_gap_pct']):>7.2f} {diagnostic:<6} {warnings}"
        )
    print("说明：排序仅用于人工复核；候选不代表成交、收益或个性化操作建议。")
    print(format_human_review_summary(human_summary_rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
