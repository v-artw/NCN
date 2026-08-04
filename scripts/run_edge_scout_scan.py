#!/usr/bin/env python3
"""Edge Scout 全市场扫描 CLI。"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import date
from pathlib import Path

# 添加 src 到路径
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from ashare_edge_scout.scanner import EdgeScoutScanInput, run_edge_scout_scan


class ConsoleProgressReporter:
    """Throttle progress while always showing stage changes and completion."""

    def __init__(self) -> None:
        self._last_stage: str | None = None
        self._last_processed = 0
        self._last_time = 0.0

    def update(self, stage: str, processed: int, total: int, code: str | None) -> None:
        now = time.monotonic()
        stage_changed = stage != self._last_stage
        completed = total > 0 and processed == total
        should_print = (
            stage_changed
            or completed
            or processed - self._last_processed >= 100
            or now - self._last_time >= 10.0
        )
        if not should_print:
            return

        percent = processed / total * 100.0 if total else 0.0
        current = f" | current={code}" if code else ""
        print(
            f"progress stage={stage} processed={processed}/{total} "
            f"({percent:.1f}%){current}",
            file=sys.stderr,
            flush=True,
        )
        self._last_stage = stage
        self._last_processed = processed
        self._last_time = now


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Edge Scout 只读研究扫描器。"
    )
    parser.add_argument("--data-root", required=True, type=Path,
                        help="数据根目录")
    parser.add_argument("--config", required=True, type=Path,
                        help="配置文件路径")
    parser.add_argument("--output-root", required=True, type=Path,
                        help="输出根目录")
    parser.add_argument("--as-of", type=str, default=None,
                        help="扫描日期（YYYY-MM-DD）")
    parser.add_argument("--top", type=int, default=30,
                        help="候选上限")
    parser.add_argument("--run-id", type=str, default=None,
                        help="运行 ID")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        # 解析 as_of 日期
        as_of = date.fromisoformat(args.as_of) if args.as_of else None

        # 创建扫描输入
        input_ = EdgeScoutScanInput(
            data_root=args.data_root,
            config_path=args.config,
            output_root=args.output_root,
            as_of=as_of,
            top=args.top,
            run_id=args.run_id,
        )

        # 运行扫描
        progress = ConsoleProgressReporter()
        result = run_edge_scout_scan(input_, progress_callback=progress.update)

        # 输出结果
        print(f"status=success")
        print(f"as_of={result.as_of.isoformat()}")
        print(f"as_of_is_t_signal_day=True")
        print("observation_day=T+2")
        print(f"candidate_count={result.candidate_count}")
        print(f"watchlist_count={result.watchlist_count}")
        print(f"near_miss_count={result.near_miss_count}")

        # P0-7: 输出审计统计（从 summary.json 读取）
        summary_path = result.summary_path
        if summary_path.exists():
            import json
            with open(summary_path) as sf:
                s = json.load(sf)
            print(f"input_code_count={s.get('input_code_count', '?')}")
            print(f"admitted_count={s.get('admitted_count', '?')}")
            print(f"rejected_count={s.get('rejected_count', '?')}")
            print(f"scored_count={s.get('scored_count', '?')}")
            print(f"unexpected_error_count={s.get('unexpected_error_count', '?')}")
            print(f"hard_gate_rejection_counts={json.dumps(s.get('hard_gate_rejection_counts', {}))}")
            print(f"no_tier_reason_counts={json.dumps(s.get('no_tier_reason_counts', {}))}")
            print(f"quantity_conservation_valid={s.get('quantity_conservation_valid', '?')}")
            print(f"admission_quantity_conservation_valid={s.get('admission_quantity_conservation_valid', '?')}")
            print(f"scan_quantity_conservation_valid={s.get('scan_quantity_conservation_valid', '?')}")
            print(f"tier_quantity_conservation_valid={s.get('tier_quantity_conservation_valid', '?')}")
            print(f"tier_counts_before_truncation={json.dumps(s.get('tier_counts_before_truncation', {}))}")
            print(f"tier_counts_after_truncation={json.dumps(s.get('tier_counts_after_truncation', {}))}")
            print(f"discovery_tier_counts={json.dumps(s.get('discovery_tier_counts', {}))}")
            print(f"cnstock_pool_counts={json.dumps(s.get('cnstock_pool_counts', {}))}")
            print(f"limitations={json.dumps(s.get('limitations', ()))}")

        print(f"run_directory={result.run_directory}")

        # 屏幕输出 TOP 研究参考价表（research-only，非执行价/非投资建议）
        ref_csv = result.run_directory / "reference_prices.csv"
        if ref_csv.exists():
            print_top_reference_prices(ref_csv)
        discovery_csv = result.run_directory / "discovery.csv"
        if discovery_csv.exists():
            print_top_discovery(discovery_csv)
        daily_watchlist_csv = result.run_directory / "daily_research_watchlist.csv"
        if daily_watchlist_csv.exists():
            print_daily_research_watchlist(daily_watchlist_csv)

        return 0

    except Exception as exc:
        print(f"edge_scout_scan_failed: {exc}", file=sys.stderr)
        return 2


def print_top_reference_prices(ref_csv: Path) -> None:
    """读取 reference_prices.csv 并在屏幕打印 TOP 候选参考价表。"""

    import csv

    rows: list[dict[str, str]] = []
    with ref_csv.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not rows:
        print("\nTOP 研究参考价：无候选")
        return

    print("\n==============================================")
    print(" TOP 10 研究观察样本 · 参考价（研究近似，非执行价）")
    print("==============================================")
    print(
        f"{'#':>2}  {'code':<12} {'tier':<9} {'edge':>6}  {'有效':>4}  "
        f"{'触发参考':>8} {'参考止损':>8} {'止盈1.5R':>8} {'止盈2R':>8} {'风险距':>6}"
    )
    print("-" * 98)
    for row in rows:
        risk_pct = float(row.get("risk_distance_pct", 0) or 0) * 100
        confirmed = "✓" if row.get("valid_setup_confirmed", "False") == "True" else "✗"
        print(
            f"{row['rank']:>2}  {row['code']:<12} {row['tier']:<9} {row['edge_score'][:6]:>6}  "
            f"{confirmed:>4}  "
            f"{row['buy_reference']:>8} {row['stop_reference']:>8} "
            f"{row['partial_take_profit_reference']:>8} {row['take_profit_reference']:>8} "
            f"{risk_pct:>5.2f}%"
        )
    print("-" * 98)
    print(" 说明：✓ = T 日 setup 有效且 T+1 价格/量能研究观察通过；")
    print("       该状态仅进入 T+2 人工观察阶段，不代表可成交或应入场。")
    print("       触发参考为 T 日 signal_high，不是 T+2 开盘价。")
    print("       参考价基于前复权研究数据推算，")
    print("       不是可执行价格、真实成交价，也不构成投资建议。")
    print("       仅展示参考风险距在 V1 范围 [2.5%, 6.0%] 内的样本；")
    print("       超过 6% 的样本已排除，仅供观察，不满足 V1 入场风险约束。")
    print("==============================================")


def print_top_discovery(discovery_csv: Path) -> None:
    """Print the strongest research-only discovery rows with deterministic reasons."""

    import csv

    with discovery_csv.open("r", encoding="utf-8") as file:
        rows = [row for row in csv.DictReader(file) if row.get("discovery_eligible") == "True"]
    rows = [row for row in rows if int(row.get("start_signal_count", 0) or 0) >= 2][:15]
    if not rows:
        print("\n发现层 TOP：当前无满足 2/5 以上启动信号及研究过滤的样本")
        return

    print("\n============================================================")
    print(" CNstock 风格发现层 TOP（只读研究，不是 production/买入建议）")
    print("============================================================")
    print(f"{'#':>2}  {'code':<11} {'层级':<18} {'启动':>4} {'发现分':>7} {'涨幅':>7} {'5日':>7}  信号")
    print("-" * 100)
    for index, row in enumerate(rows, start=1):
        signals = row.get("start_signals", "").replace("|", ",") or "none"
        print(
            f"{index:>2}  {row['code']:<11} {row['discovery_tier']:<18} "
            f"{row['start_signal_count']:>4} {float(row['discovery_score']):>7.2f} "
            f"{float(row['pct_chg']):>6.2f}% {float(row['ret_5d']):>6.2f}%  {signals}"
        )
        print(
            f"    PMK={row.get('pmk_trend_reason') or row.get('pmk_shape_pattern') or 'none'}; "
            f"Candle={row.get('candle_confirm_reason') or 'none'}"
        )
    print("-" * 100)
    print(" 说明：strong_start/profit_shadow/early_low_position 均为研究发现层；")
    print("       只有独立的 V1 setup + T+1 有效确认才能升级，当前 production 仍禁用。")
    print("============================================================")


def print_daily_research_watchlist(path: Path) -> None:
    """Print the unified daily research table, never as a buy recommendation."""

    import csv

    with path.open("r", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))[:20]
    if not rows:
        print("\n每日统一研究观察表：无符合分层门槛的样本")
        return

    print("\n================================================================")
    print(" 每日统一研究观察 TOP（人工复核，非买入建议）")
    print("================================================================")
    print(f"{'#':>2}  {'code':<11} {'阶段':<24} {'池':<23} {'启动':>4} {'兼容分':>8}")
    print("-" * 96)
    for row in rows:
        print(
            f"{row['rank']:>2}  {row['code']:<11} {row['watch_stage']:<24} "
            f"{row['cnstock_pool']:<23} {row['start_signal_count']:>4} "
            f"{float(row['cnstock_discovery_rank'] or 0):>8.2f}"
        )
    print("-" * 96)
    print(" 说明：confirmed/setup/discovery 均为研究观察阶段；research_only=true。")
    print("       discovery 样本未通过完整 V1 setup/T+1 时序，不得视为应买入股票。")
    print("================================================================")


if __name__ == "__main__":
    raise SystemExit(main())
