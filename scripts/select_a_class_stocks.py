#!/usr/bin/env python3
"""CLI for the read-only A-class base-breakout stock selector."""

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

from ashare_edge_scout.a_class_selector import run_a_class_selection


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="NCN read-only A-class base-breakout selector")
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--as-of", type=date.fromisoformat, help="T signal date (YYYY-MM-DD)")
    parser.add_argument("--run-id")
    parser.add_argument("--top", type=int, default=20)
    args = parser.parse_args(argv)
    if args.top < 1:
        parser.error("--top must be at least 1")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    print("A类低位启动扫描：开始读取本地日线并扫描候选...", flush=True)

    def progress(done: int, total: int, selected: int) -> None:
        print(f"A类扫描进度：已评估 {done}/{total}，当前候选 {selected}", flush=True)

    try:
        result = run_a_class_selection(
            data_root=args.data_root,
            config_path=args.config,
            output_root=args.output_root,
            as_of=args.as_of,
            run_id=args.run_id,
            progress=progress,
        )
    except Exception as exc:
        print(f"a_class_selection_failed: {exc}", file=sys.stderr)
        return 2

    print("status=success")
    print(f"signal_date={result.signal_date.isoformat()}")
    print("selector=a_class_base_breakout_v1")
    print("historical_validation=not_run_in_selection_command")
    print(f"candidate_count={result.candidate_count}")
    print(f"run_directory={result.run_directory}")
    print(f"timestamped_csv={result.timestamped_candidates_path}")
    with result.candidates_path.open("r", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))[: args.top]
    if not rows:
        print("\nA类低位启动候选：无")
        return 0
    print("\nA类低位启动候选（只读研究，非买入建议）")
    print(f"{'#':>2}  {'code':<11} {'close':>8} {'amount(亿)':>10} {'pos60':>7} {'pos120':>7} {'ret20':>7} {'vol':>6} {'收盘':>6} reason")
    for index, row in enumerate(rows, start=1):
        print(
            f"{index:>2}  {row['code']:<11} {float(row['research_close']):>8.2f} "
            f"{float(row['amount_cny']) / 100_000_000:>10.2f} "
            f"{float(row['range_position_60d_pct']):>6.1f}% "
            f"{float(row['range_position_120d_pct']):>6.1f}% "
            f"{float(row['current_return_20d_pct']):>6.1f}% "
            f"{float(row['volume_ratio_20']):>6.2f} "
            f"{float(row['close_location']):>6.2f} {row['a_class_reason']}"
        )
    print("说明：A类候选为独立只读研究样本；不代表成交、收益或个性化操作建议。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
