#!/usr/bin/env python3
"""CLI for the read-only MKF configured post-cross lag candidate-source experiment."""

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

from ashare_edge_scout.mkf_candidate_selector import run_mkf_candidate_selection


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="NCN read-only MKF red/blue cross-up-20 configured post-lag candidate-source experiment")
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--as-of", type=date.fromisoformat, help="T signal date (YYYY-MM-DD)")
    parser.add_argument("--run-id")
    parser.add_argument("--min-adv20-cny", type=float, help="Override 20-day average amount floor for research profiles")
    parser.add_argument("--selection-profile", default="standard")
    parser.add_argument("--top", type=int, default=20)
    args = parser.parse_args(argv)
    if args.top < 1:
        parser.error("--top must be at least 1")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    print("MKF 候选源实验：开始读取本地日线并扫描配置的红蓝线上穿20后滞后窗口候选...", flush=True)

    def progress(done: int, total: int, selected: int) -> None:
        print(f"MKF扫描进度：已评估 {done}/{total}，当前候选 {selected}", flush=True)

    try:
        result = run_mkf_candidate_selection(
            data_root=args.data_root,
            config_path=args.config,
            output_root=args.output_root,
            as_of=args.as_of,
            run_id=args.run_id,
            min_adv20_cny=args.min_adv20_cny,
            selection_profile=args.selection_profile,
            progress=progress,
        )
    except Exception as exc:
        print(f"mkf_candidate_selection_failed: {exc}", file=sys.stderr)
        return 2

    print("status=success")
    print(f"signal_date={result.signal_date.isoformat()}")
    print(f"selector={result.selector_id}")
    print(f"post_cross_lag_range={result.post_cross_lag_range}")
    print(f"selection_profile={args.selection_profile}")
    if args.min_adv20_cny is not None:
        print(f"effective_min_adv20_cny={args.min_adv20_cny:.0f}")
    print("historical_validation=not_run_in_selection_command")
    print(f"candidate_count={result.candidate_count}")
    print(f"run_directory={result.run_directory}")
    print(f"timestamped_csv={result.timestamped_candidates_path}")
    with result.candidates_path.open("r", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))[: args.top]
    if not rows:
        print("\nMKF 红蓝线上穿20配置滞后窗口候选：无")
        print("说明：MKF 候选源实验为独立只读研究样本；不影响 SMC 入选、排序、watchlist 或生产逻辑。")
        return 0
    print("\nMKF 红蓝线上穿20配置滞后窗口候选（只读研究，非买入建议）")
    print(f"{'#':>2}  {'code':<11} {'lag':>3} {'cross_date':<10} {'close':>8} {'amount(亿)':>10} {'momentum':>9} {'inter':>8} {'near':>8} reason")
    for index, row in enumerate(rows, start=1):
        print(
            f"{index:>2}  {row['code']:<11} {int(row['post_cross_lag']):>3} {row['cross_date']:<10} {float(row['research_close']):>8.2f} "
            f"{float(row['amount_cny']) / 100_000_000:>10.2f} "
            f"{float(row['mkf_momentum']):>9.2f} "
            f"{float(row['mkf_inter']):>8.2f} "
            f"{float(row['mkf_near']):>8.2f} {row['selection_reason']}"
        )
    print("说明：MKF 候选源实验为独立只读研究样本；不影响 SMC 入选、排序、watchlist 或生产逻辑。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
