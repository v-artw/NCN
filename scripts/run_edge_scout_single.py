#!/usr/bin/env python3
"""Edge Scout 单股分析 CLI。

只加载并扫描 --code 指定的单只股票，不处理其他任何股票。
输出该股票的状态、分层、评分、信号、T+1 确认与限制。
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
from datetime import date, datetime
from pathlib import Path

# 添加 src 到路径
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from ashare_edge_scout.data.contracts import EdgeScoutResult, Tier
from ashare_edge_scout.data.data_sources import get_parquet_codes, load_stock_records
from ashare_edge_scout.admission import load_research_window_daily_bars
from ashare_edge_scout.scanner import (
    EdgeScoutScanInput,
    _build_candle_rule_set,
    _scan_one_stock,
    _to_date,
    run_edge_scout_scan,
)
from ashare_edge_scout.signals.signal_scoring import (
    apply_hard_gates,
    classify_tier,
    score_single_stock,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Edge Scout 单股分析（只扫描指定股票）。"
    )
    parser.add_argument("--code", required=True, type=str,
                        help="股票代码（如 sh.600000）。必须只扫描该股票。")
    parser.add_argument("--data-root", required=True, type=Path,
                        help="数据根目录")
    parser.add_argument("--config", required=True, type=Path,
                        help="配置文件路径")
    parser.add_argument("--output-root", required=True, type=Path,
                        help="输出根目录")
    parser.add_argument("--as-of", type=str, default=None,
                        help="扫描日期（YYYY-MM-DD）")
    parser.add_argument("--run-id", type=str, default=None,
                        help="运行 ID")
    return parser.parse_args()


def _single_stock_scan(code: str, data_root: Path, config_path: Path, as_of: date | None) -> EdgeScoutResult:
    """对单只股票执行完整扫描，不调用全市场扫描器。"""

    from ashare_edge_scout.scanner import run_edge_scout_scan

    # 验证 code 存在
    codes = get_parquet_codes(data_root)
    if code not in codes:
        return EdgeScoutResult(
            code=code,
            as_of=as_of or datetime.now().date(),
            status="rejected",
            admission_error_code="code_not_found",
            limitations=("code_not_in_data_directory",),
        )

    # 只加载该股票的记录
    try:
        records_flat = load_stock_records(code, data_root)
    except Exception as exc:
        return EdgeScoutResult(
            code=code,
            as_of=as_of or datetime.now().date(),
            status="rejected",
            admission_error_code="data_load_failed",
            admission_detail=str(exc),
            limitations=("data_load_failure",),
        )

    # 转换为列表 dicts
    records: list[dict] = list(records_flat)
    if not records:
        return EdgeScoutResult(
            code=code,
            as_of=as_of or datetime.now().date(),
            status="insufficient_data",
            admission_error_code="no_records",
            limitations=("no_trading_data",),
        )

    # 加载配置并构建 candle rules
    from ashare_edge_scout.config import load_config, validate_config
    config = load_config(config_path)
    validate_config(config, config_path)
    candle_rule_set = _build_candle_rule_set(config)

    # 确定 as_of（T 信号日）
    if as_of is None:
        # 默认自动回退 2 个交易日：T+1 研究确认可计算，T+2 进入人工观察阶段。
        last_d = _to_date(records[-1].get("date"))
        if len(records) >= 3:
            third_last = _to_date(records[-3].get("date"))
            as_of = third_last or last_d or datetime.now().date()
        else:
            as_of = last_d or datetime.now().date()

    # 截断到 as_of（消除前视）
    truncated: list[dict] = []
    for r in records:
        d = _to_date(r.get("date"))
        if d and d <= as_of:
            truncated.append(r)
        else:
            break

    if not truncated:
        return EdgeScoutResult(
            code=code,
            as_of=as_of,
            status="insufficient_data",
            admission_error_code="no_records_before_as_of",
            limitations=("no_trading_data_before_as_of",),
        )

    # 提取 T+1 记录（as_of 之后的下一个交易日）
    t1_records: list[dict] = []
    for r in records:
        d = _to_date(r.get("date"))
        if d and d > as_of:
            t1_records.append(r)
            if len(t1_records) >= 2:
                break

    # 直接调用内部扫描（不经过全市场扫描器）
    result = _scan_one_stock(
        code=code,
        records=truncated,
        t1_records=t1_records,
        config=config,
        candle_rule_set=candle_rule_set,
        industry=None,
        as_of=as_of,
    )

    return result


def main() -> int:
    args = parse_args()

    try:
        as_of = date.fromisoformat(args.as_of) if args.as_of else None

        # 对单只股票执行完整扫描
        result = _single_stock_scan(
            code=args.code,
            data_root=args.data_root,
            config_path=args.config,
            as_of=as_of,
        )

        # 输出单股结果摘要
        print(f"code={result.code}")
        print(f"as_of={result.as_of.isoformat()}")
        print(f"input_code_count=1")
        print(f"status={result.status}")

        if result.admission_error_code:
            print(f"admission_error_code={result.admission_error_code}")
            if result.admission_detail:
                print(f"detail={result.admission_detail}")

        if result.tier is not None:
            tier = result.tier
            print(f"tier={tier.tier}")
            print(f"edge_score={tier.edge_score:.4f}")
            print(f"base_quality_score={tier.base_quality_score:.4f}")
            print(f"timing_score={tier.timing_score:.4f}")
            print(f"risk_score={tier.risk_score:.4f}")
        else:
            print("tier=none")

        if result.t_day_setup_valid is not None:
            print(f"t_day_setup_valid={result.t_day_setup_valid}")
            print(f"t_day_setup_reason={result.t_day_setup_reason}")
            print(f"t_day_patterns={','.join(result.t_day_patterns) if result.t_day_patterns else 'none'}")
        if result.price_volume_confirmed is not None:
            print(f"price_volume_confirmed={result.price_volume_confirmed}")
            print(f"price_volume_confirmation_reason={result.price_volume_confirmation_reason}")
        if result.valid_setup_confirmed is not None:
            print(f"valid_setup_confirmed={result.valid_setup_confirmed}")
            print(f"valid_setup_confirmation_reason={result.valid_setup_confirmation_reason}")

        if result.first_date:
            print(f"first_date={result.first_date.isoformat()}")
        if result.last_date:
            print(f"last_date={result.last_date.isoformat()}")

        if result.tier is not None and result.tier.tier in ("production", "watchlist", "near_miss"):
            # 尝试写出到 output_root
            output_dir = args.output_root / (args.run_id or f"single-{args.code}")
            output_dir.mkdir(parents=True, exist_ok=True)

            tier_csv = output_dir / "single_tier.csv"
            with tier_csv.open("w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=[
                    "code", "as_of", "tier", "edge_score",
                    "base_quality_score", "timing_score", "risk_score"
                ])
                writer.writeheader()
                writer.writerow({
                    "code": result.tier.code,
                    "as_of": result.tier.as_of.isoformat(),
                    "tier": result.tier.tier,
                    "edge_score": f"{result.tier.edge_score:.6f}",
                    "base_quality_score": f"{result.tier.base_quality_score:.6f}",
                    "timing_score": f"{result.tier.timing_score:.6f}",
                    "risk_score": f"{result.tier.risk_score:.6f}",
                })
            print(f"output_path={tier_csv}")

        print(f"limitations={','.join(result.limitations) if result.limitations else 'none'}")

        return 0

    except Exception as exc:
        print(f"edge_scout_single_failed: {exc}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
