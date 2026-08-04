"""Edge Scout 主扫描器。

复用 V1 的扫描循环逻辑，适配新的数据结构。
"""

from __future__ import annotations

import os
import shutil
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from .candle_rules import CandleRuleSet, HammerRule
from .candles import detect_bearish_risk_patterns

from .candle_timing import (
    detect_candle_patterns,
    observe_t1,
    evaluate_t_day_setup,
    has_bullish_pattern,
)
from .config import load_config, validate_config, compute_config_sha256
from .contracts import (
    EdgeScoutResult,
    EdgeScoutScanSummary,
    ScoringResult,
    ReferencePricePublicationRow,
    Tier,
)
from .data_sources import (
    get_parquet_latest_date_coverage,
    get_parquet_codes,
    load_industry_map,
    load_stock_records,
)
from .admission import admission_universe
from .signal_scoring import (
    apply_hard_gates,
    classify_tier,
    compute_base_quality_score,
    compute_edge_score,
    compute_risk_score,
    compute_timing_score,
    compute_discovery_score,
    classify_discovery_tier,
    score_single_stock,
)
from .pmk_features import compute_pmk_features
from .candle_confirm import compute_candle_confirmation_features
from .start_signals import compute_start_signals
from .discovery import (
    compute_cnstock_discovery_rank,
    compute_price_volume_base_score,
    evaluate_discovery_pool,
)
from .reference_prices import compute_reference_prices, within_v1_risk_range


# ---------------------------------------------------------------------------
# Public input / output dataclasses
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class EdgeScoutScanInput:
    """Edge Scout 扫描输入参数。"""

    data_root: Path
    config_path: Path
    output_root: Path
    as_of: date | None = None
    top: int = 30
    run_id: str | None = None


@dataclass(frozen=True)
class EdgeScoutScanResult:
    """Edge Scout 扫描结果。"""

    run_directory: Path
    candidates_path: Path
    watchlist_path: Path
    near_miss_path: Path
    summary_path: Path
    report_path: Path
    manifest_path: Path
    latest_path: Path
    as_of: date
    candidate_count: int
    watchlist_count: int
    near_miss_count: int


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _to_date(d: Any) -> date | None:
    """将各种日期类型（str, pandas Timestamp, numpy datetime64, date）转换为 date。

    P0-3 修复：确保所有类型统一返回纯 datetime.date 对象。
    注意：pd.Timestamp 继承自 datetime.date，所以 isinstance 检查会误匹配，
    必须先检查 pandas/numpy 类型。
    numpy datetime64 没有 .date() 方法，需要特殊处理。
    """

    if d is None:
        return None

    # 先处理 pandas Timestamp（有 .date() 方法，且继承自 date）
    import pandas as pd
    if isinstance(d, pd.Timestamp):
        return d.date()

    # 处理 numpy datetime64（无 .date() 方法）
    import numpy as np
    if isinstance(d, np.datetime64):
        try:
            return datetime.strptime(
                np.datetime_as_string(d, unit="D"), "%Y-%m-%d"
            ).date()
        except (ValueError, TypeError):
            return None

    # datetime.datetime 是 date 的子类；归一化为纯 date，
    # 避免 isoformat() 带时间部分导致字符串比较与纯 date 不一致
    if isinstance(d, datetime):
        return d.date()

    # 纯 Python date 对象（不含时间部分）
    if isinstance(d, date):
        return d

    # 字符串日期
    if isinstance(d, str):
        try:
            return datetime.strptime(d, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            return None

    # 其他类型无法转换
    return None


def _build_candle_rule_set(config: Mapping[str, Any]) -> CandleRuleSet:
    """从 edge_scout 配置构建 V1 CandleRuleSet（兼容 edge_scout YAML 格式）。

    edge_scout_v1.yaml 的 ``setup.candle`` 节使用与 V1 ``config_rules`` 兼容的
    结构，但 V1 的 ``build_strategy_rule_set`` 要求 ``setup.candle.hammer`` 子节。
    当 edge_scout 配置不含 ``hammer`` 子节时，回退到 V1 默认 HammerRule 阈值。

    返回 V1 的 ``CandleRuleSet``，供 ``detect_candle_patterns`` 使用。
    """
    candle_cfg = config.get("setup", {}).get("candle", {})
    hammer_cfg = candle_cfg.get("hammer")
    enabled = candle_cfg.get("enabled", ["hammer", "bullish_engulfing", "piercing", "morning_star"])

    if isinstance(enabled, str):
        enabled = [enabled]

    if hammer_cfg is None:
        # 回退默认阈值（与 V1 一致）
        hammer_cfg = {
            "max_body_to_range": 0.40,
            "min_lower_shadow_to_body": 2.0,
            "max_upper_shadow_to_body": 0.50,
            "min_close_location": 0.65,
        }

    return CandleRuleSet(
        enabled_patterns=tuple(enabled),
        hammer=_build_hammer_rule(hammer_cfg),
    )


def _build_hammer_rule(cfg: Mapping[str, Any]) -> Any:
    """将 edge_scout 的 hammer 子节转换为 V1 ``HammerRule``。"""

    return HammerRule(
        max_body_to_range=float(cfg.get("max_body_to_range", 0.40)),
        min_lower_shadow_to_body=float(cfg.get("min_lower_shadow_to_body", 2.0)),
        max_upper_shadow_to_body=float(cfg.get("max_upper_shadow_to_body", 0.50)),
        min_close_location=float(cfg.get("min_close_location", 0.65)),
        uses_documented_upper_shadow_range_guard=True,
    )


def _latest_minus_trading_days(
    features_by_code: Mapping[str, Any],
    latest: date | None,
    days: int = 2,
) -> date | None:
    """取最新交易日回退 days 个交易日的日期（基于实际数据日历）。

    只考虑"最后一条记录恰好等于 latest"的股票，取其倒数第 days+1 条记录
    的日期，再取这些日期中的最大值作为全局 T。这样能保证对覆盖最新
    数据日的股票，T+1 与 T+2 都为真实交易日（T+2 = latest）。
    没有足够数据的股票返回 None。
    """

    if latest is None:
        return None
    latest_date = _to_date(latest)
    if latest_date is None:
        return None
    latest_str = latest_date.isoformat()
    candidates: list[date] = []
    for result in features_by_code.values():
        records = getattr(result, "records", None)
        if not records:
            continue
        last = _to_date(records[-1].get("date"))
        if last is None or last.isoformat() != latest_str:
            continue
        target_index = -days - 1
        if len(records) < abs(target_index):
            continue
        d = _to_date(records[target_index].get("date"))
        if d is not None:
            candidates.append(d)
    return max(candidates) if candidates else None


def _truncated_records(
    records: Sequence[Mapping[str, Any]],
    as_of: date | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """按 as_of 截断 records，并返回 (truncated, truncated_dates) 供 T+1 用。

    如果 as_of 为 None，使用最后一条记录日期。
    """

    if not records:
        return [], []

    if as_of is None:
        last = _to_date(records[-1].get("date"))
        as_of = last or datetime.now().date()

    # 统一转换为字符串日期比较（兼容 pandas Timestamp 与 date）
    as_of_str = as_of.isoformat()

    truncated: list[dict[str, Any]] = []
    for r in records:
        d = _to_date(r.get("date"))
        if d is None:
            continue
        if d.isoformat() <= as_of_str:
            truncated.append(r)
        else:
            break

    # 提取 T+1 可用记录（as_of 之后的第一个交易日）
    t1_records: list[dict[str, Any]] = []
    for r in records:
        d = _to_date(r.get("date"))
        if d is None:
            continue
        if d.isoformat() > as_of_str:
            t1_records.append(r)
            if len(t1_records) >= 2:  # 最多到 T+1
                break

    return truncated, t1_records


def _evaluate_discovery_eligibility(
    *,
    close: float,
    amount_cny: float,
    pct_chg: float,
    ret_5d: float,
    turn: float,
    volume_ratio_20: float,
    config: Mapping[str, Any],
) -> tuple[bool, tuple[str, ...]]:
    """Apply research-only discovery filters without changing V1 eligibility."""

    discovery_cfg = config.get("discovery", {})
    if not bool(discovery_cfg.get("enabled", True)):
        return False, ("discovery_disabled",)

    rejections: list[str] = []
    if close > float(discovery_cfg.get("max_price_cny", 20.0)):
        rejections.append("discovery_price_too_high")
    if amount_cny < float(discovery_cfg.get("min_amount_cny", 15_000_000.0)):
        rejections.append("discovery_amount_too_low")
    if abs(pct_chg) > float(discovery_cfg.get("max_pct_chg", 7.0)):
        rejections.append("discovery_daily_move_too_high")
    if ret_5d > float(discovery_cfg.get("max_ret_5d", 12.0)):
        rejections.append("discovery_ret_5d_too_high")
    if turn > float(discovery_cfg.get("max_turn", 35.0)):
        rejections.append("discovery_turn_too_high")
    if volume_ratio_20 > float(discovery_cfg.get("max_volume_ratio", 5.0)):
        rejections.append("discovery_volume_ratio_too_high")
    return not rejections, tuple(rejections)


def _generate_run_id(input_: EdgeScoutScanInput, as_of: date) -> str:
    """生成唯一 run_id。

    优先使用 input_.run_id（如果用户指定），否则生成基于日期和时间的唯一 ID。
    """

    if input_.run_id:
        return input_.run_id
    # 不带时区：使用 ISO 格式 + 时间戳
    now_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"scan-{as_of.isoformat()}_{now_str}"


def _write_manifest(
    run_directory: Path,
    results: Sequence[EdgeScoutResult],
    production: Sequence[Tier],
    watchlist: Sequence[Tier],
    near_miss: Sequence[Tier],
    summary: EdgeScoutScanSummary,
) -> None:
    """写出 manifest.json 包含所有输出文件。"""

    import json
    import hashlib

    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        try:
            with path.open("rb") as f:
                for chunk in iter(lambda: f.read(1024 * 1024), b""):
                    digest.update(chunk)
            return digest.hexdigest()
        except OSError:
            return "unavailable"

    files = {}
    for name in ("candidates.csv", "watchlist.csv", "near_miss.csv",
                 "summary.json", "report.md"):
        p = run_directory / name
        files[name] = {"sha256": _sha256(p)}
    # 自身 manifest
    manifest_path = run_directory / "manifest.json"
    manifest = {
        "schema_version": summary.schema_version,
        "run_id": summary.run_id,
        "as_of": summary.as_of.isoformat() if isinstance(summary.as_of, date) else str(summary.as_of),
        "files": files,
        "limitation_note": (
            "manifest lists produced artifacts; self-hash is not yet computed "
            "to avoid circular reference."
        ),
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_latest(
    output_root: Path,
    run_directory: Path,
    summary: EdgeScoutScanSummary,
) -> None:
    """原子更新 latest.json。"""

    import json

    latest_path = output_root / "latest.json"
    latest_temporary = output_root / f".{run_directory.name}.latest.json.tmp"

    latest = {
        "schema_version": summary.schema_version,
        "status": summary.status,
        "run_id": summary.run_id,
        "run_directory": run_directory.name,
        "as_of": summary.as_of.isoformat() if isinstance(summary.as_of, date) else str(summary.as_of),
        "candidate_count": summary.production_candidate_count,
        "watchlist_count": summary.watchlist_count,
        "near_miss_count": summary.near_miss_count,
        "published_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    latest_temporary.write_text(
        json.dumps(latest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(latest_temporary, latest_path)


# ---------------------------------------------------------------------------
# Public scan entry
# ---------------------------------------------------------------------------

def run_edge_scout_scan(
    input_: EdgeScoutScanInput,
    *,
    now_utc: Callable[[], datetime] | None = None,
    progress_callback: Callable[[str, int, int, str | None], None] | None = None,
    freshness_calendar: Sequence[date] | None = None,
    freshness_policy: Any | None = None,
    freshness_now: datetime | None = None,
) -> EdgeScoutScanResult:
    """运行 Edge Scout 扫描。

    参数：
      input_: 扫描输入参数
      now_utc: 当前时间函数（用于生成 run_id）

    返回：
      扫描结果
    """

    # 加载配置
    config = load_config(input_.config_path)
    validate_config(config, input_.config_path)
    config_sha256 = compute_config_sha256(input_.config_path)

    # 构建 V1 CandleRuleSet（正确类型）
    candle_rule_set = _build_candle_rule_set(config)

    # 获取股票代码列表
    codes = get_parquet_codes(input_.data_root)
    if not codes:
        raise ValueError(f"数据根目录 {input_.data_root} 没有 parquet 文件")
    raw_observed_latest: date | None = None
    raw_covered_count = 0
    raw_input_count = len(codes)
    if freshness_calendar is not None or freshness_policy is not None:
        raw_observed_latest, raw_covered_count, raw_input_count = get_parquet_latest_date_coverage(
            input_.data_root, codes
        )
        if raw_observed_latest is None:
            raise ValueError("freshness validation found no readable parquet date")

    # 加载行业映射
    industry_map_path = config.get("paths", {}).get("industry_map", "")
    if industry_map_path:
        industry_path = Path(industry_map_path)
        if not industry_path.is_absolute():
            industry_path = input_.config_path.resolve().parents[1] / industry_path
        industry_map = load_industry_map(industry_path)
    else:
        industry_map = {}

    # 执行数据准入
    admission_kwargs: dict[str, Any] = {}
    if progress_callback is not None:
        progress_callback("data_admission", 0, len(codes), None)
        admission_kwargs["progress_callback"] = (
            lambda processed, total, code: progress_callback(
                "data_admission", processed, total, code
            )
        )
    features_by_code, failures_by_code = admission_universe(
        codes,
        input_.data_root,
        research_window_admission=False,
        **admission_kwargs,
    )

    # 确定 as_of 日期（T 信号日）
    if input_.as_of is None:
        # 默认自动回退 2 个交易日：T = 最新交易日往前 2 个交易日，
        # 使 T+1（昨日）研究确认可计算，T+2（最新数据日）进入人工观察阶段。
        # 统一用 _to_date 归一化为纯 datetime.date，避免 pandas Timestamp /
        # datetime / date 混用时 isoformat 与字符串比较不一致导致选错 T。
        latest = max(
            (
                _to_date(result.records[-1].get("date"))
                for result in features_by_code.values()
                if result.records and result.records[-1].get("date") is not None
            ),
            default=datetime.now().date(),
        )
        as_of = _latest_minus_trading_days(features_by_code, latest, days=2) or latest
    else:
        as_of = input_.as_of

    # 扫描每只股票
    results: list[EdgeScoutResult] = []
    if progress_callback is not None:
        progress_callback("signal_scan", 0, len(codes), None)
    for processed, code in enumerate(codes, start=1):
        if code in failures_by_code:
            result = EdgeScoutResult(
                code=code,
                as_of=as_of,
                status="rejected",
                admission_error_code=failures_by_code[code],
                limitations=("research_approximation_only",),
            )
        elif code in features_by_code:
            admission_result = features_by_code[code]
            # 按 as_of 截断 records，消除前视风险
            truncated, t1_records = _truncated_records(admission_result.records, as_of)
            if not truncated:
                result = EdgeScoutResult(
                    code=code,
                    as_of=as_of,
                    status="insufficient_data",
                    admission_error_code="no_records_before_as_of",
                    limitations=("no_trading_data_before_as_of",),
                )
            else:
                result = _scan_one_stock(
                    code=code,
                    records=truncated,
                    t1_records=t1_records,
                    config=config,
                    candle_rule_set=candle_rule_set,
                    industry=industry_map.get(code),
                    as_of=as_of,
                )
        else:
            result = EdgeScoutResult(
                code=code,
                as_of=as_of,
                status="rejected",
                admission_error_code="unknown",
                limitations=("research_approximation_only",),
            )

        results.append(result)
        if progress_callback is not None:
            progress_callback("signal_scan", processed, len(codes), code)

    # 分类 A/B/C 层级
    production_candidates: list[Tier] = []
    watchlist_candidates: list[Tier] = []
    near_miss_candidates: list[Tier] = []

    for result in results:
        if result.tier is None:
            continue

        tier = result.tier
        if tier.tier == "production":
            production_candidates.append(tier)
        elif tier.tier == "watchlist":
            watchlist_candidates.append(tier)
        else:
            near_miss_candidates.append(tier)

    # 按分数排序
    production_candidates.sort(key=lambda t: -t.edge_score)
    watchlist_candidates.sort(key=lambda t: -t.edge_score)
    near_miss_candidates.sort(key=lambda t: -t.edge_score)

    # 应用 ranking 上限
    ranking_cfg = config.get("ranking", {})
    max_prod = ranking_cfg.get("max_production_candidates", input_.top)
    max_watch = ranking_cfg.get("max_watchlist_candidates", input_.top * 2)
    max_near = ranking_cfg.get("max_near_miss", input_.top * 5)

    production_candidates = production_candidates[: int(max_prod)]
    watchlist_candidates = watchlist_candidates[: int(max_watch)]
    near_miss_candidates = near_miss_candidates[: int(max_near)]

    # 生成 run_id
    run_id = _generate_run_id(input_, as_of)

    # 不再预创建 run_directory，让 publisher 通过临时目录 + os.replace 原子发布
    output_root = input_.output_root

    # P0-7: 计算硬门槛拒绝统计和截断前后 tier 统计
    no_tier_reason_counts: dict[str, int] = {}
    unexpected_error_count = 0
    scored_count = 0

    for r in results:
        if r.status == "rejected" and r.admission_error_code == "unexpected_error":
            unexpected_error_count += 1
        elif r.status == "rejected" and r.admission_error_code:
            if r.admission_error_code == "hard_gate_failure":
                pass
            else:
                no_tier_reason_counts[r.admission_error_code] = (
                    no_tier_reason_counts.get(r.admission_error_code, 0) + 1
                )
        elif r.tier is not None:
            scored_count += 1

    # Collect actual gate codes from the structured per-stock field.
    hard_gate_detail: Counter[str] = Counter()
    for r in results:
        if r.status == "rejected" and r.admission_error_code == "hard_gate_failure":
            hard_gate_detail.update(r.hard_gate_details)

    # 截断前/后 tier 计数
    tier_counts_before_truncation: dict[str, int] = {}
    for r in results:
        if r.tier is not None:
            t = r.tier.tier
            tier_counts_before_truncation[t] = tier_counts_before_truncation.get(t, 0) + 1
    discovery_tier_counts = Counter(
        result.discovery_tier for result in results if result.discovery_tier is not None
    )
    cnstock_pool_counts = Counter(
        result.cnstock_pool
        for result in results
        if result.cnstock_pool_eligible and result.cnstock_pool is not None
    )

    data_rejected_count = sum(1 for r in results if r.code in failures_by_code)
    no_records_before_as_of_count = sum(
        1 for r in results if r.admission_error_code == "no_records_before_as_of"
    )
    hard_gate_rejected_count = sum(
        1 for r in results if r.admission_error_code == "hard_gate_failure"
    )
    unclassified_count = len(results) - (
        data_rejected_count
        + no_records_before_as_of_count
        + hard_gate_rejected_count
        + scored_count
        + unexpected_error_count
    )
    admission_conservation = len(features_by_code) + len(failures_by_code) == len(codes)
    scan_conservation = len(results) == len(codes) and unclassified_count == 0
    tier_conservation = sum(tier_counts_before_truncation.values()) == scored_count
    conservation_check = admission_conservation and scan_conservation and tier_conservation

    summary = EdgeScoutScanSummary(
        schema_version="edge_scout_v1",
        status="success" if len(results) > 0 else "empty",
        run_id=run_id,
        as_of=as_of,
        input_code_count=len(codes),
        admitted_count=len(features_by_code),
        rejected_count=len(failures_by_code),
        production_candidate_count=len(production_candidates),
        watchlist_count=len(watchlist_candidates),
        near_miss_count=len(near_miss_candidates),
        quality_error_counts=Counter(failures_by_code.values()),
        hard_gate_rejection_counts=dict(sorted(hard_gate_detail.items())),
        hard_gate_rejected_count=hard_gate_rejected_count,
        data_rejected_count=data_rejected_count,
        no_records_before_as_of_count=no_records_before_as_of_count,
        scored_count=scored_count,
        unexpected_error_count=unexpected_error_count,
        unclassified_count=unclassified_count,
        no_tier_reason_counts=no_tier_reason_counts,
        tier_counts_before_truncation=tier_counts_before_truncation,
        tier_counts_after_truncation={
            "production": len(production_candidates),
            "watchlist": len(watchlist_candidates),
            "near_miss": len(near_miss_candidates),
        },
        discovery_tier_counts=dict(sorted(discovery_tier_counts.items())),
        cnstock_pool_counts=dict(sorted(cnstock_pool_counts.items())),
        quantity_conservation_valid=conservation_check,
        admission_quantity_conservation_valid=admission_conservation,
        scan_quantity_conservation_valid=scan_conservation,
        tier_quantity_conservation_valid=tier_conservation,
        boundaries={
            "read_only": True,
            "broker_connected": False,
            "orders_submitted": False,
            "investment_advice": False,
        },
        inputs={
            "data_root": str(input_.data_root),
            "config_path": str(input_.config_path),
            "config_sha256": config_sha256,
        },
        limitations=(
            "research_only",
            "no_real_execution_prices",
            "no_pit_universe",
            "production_tier_disabled_in_mvp",
        ),
    )
    if freshness_calendar is not None or freshness_policy is not None:
        if freshness_calendar is None or freshness_policy is None:
            raise ValueError("freshness_calendar and freshness_policy must be supplied together")
        from .operations import validate_freshness
        evidence = validate_freshness(
            calendar=list(freshness_calendar),
            policy=freshness_policy,
            scan_as_of=as_of,
            observed_latest=raw_observed_latest,
            covered_count=raw_covered_count,
            input_count=raw_input_count,
            now=freshness_now or datetime.now(timezone.utc),
        )
        summary = EdgeScoutScanSummary(**{**summary.__dict__, "freshness_evidence": evidence.as_dict()})

    # 写出 CSV
    from .publisher import publish_scan_results

    # 构建 TOP 研究参考价列表（按层级优先级 + edge_score 降序，取前 10）
    # 仅保留参考风险距落在 V1 可交易范围 [2.5%, 6.0%] 内的样本，
    # 超出范围的研究参考价不进入 reference_prices.csv / 屏幕 TOP 表，
    # 避免用户把超过 V1 风险约束的参考价误解为可交易入场价。
    tier_priority = {"production": 0, "watchlist": 1, "near_miss": 2}
    top_reference_prices: list[ReferencePricePublicationRow] = []
    for result in results:
        if result.tier is None or result.reference_prices is None:
            continue
        if not within_v1_risk_range(result.reference_prices.risk_distance_pct, config):
            continue
        top_reference_prices.append(ReferencePricePublicationRow(
            tier=result.tier,
            prices=result.reference_prices,
            t_day_setup_valid=bool(result.t_day_setup_valid),
            price_volume_confirmed=bool(result.price_volume_confirmed),
            valid_setup_confirmed=bool(result.valid_setup_confirmed),
            discovery_tier=result.discovery_tier or "general_observation",
            discovery_score=float(result.discovery_score or 0.0),
            start_signal_count=int(result.start_signal_count or 0),
        ))
    top_reference_prices.sort(
        key=lambda item: (
            0 if item.valid_setup_confirmed else 1,
            -item.start_signal_count,
            -item.discovery_score,
            tier_priority.get(item.tier.tier, 99),
        )
    )
    top_reference_prices = top_reference_prices[: int(config.get("ranking", {}).get("max_reference_prices_top_n", 10))]

    if progress_callback is not None:
        progress_callback("publication", 0, 1, None)
    publish_scan_results(
        run_directory=output_root,
        run_id=run_id,
        results=results,
        production_candidates=production_candidates,
        watchlist_candidates=watchlist_candidates,
        near_miss_candidates=near_miss_candidates,
        summary=summary,
        top_reference_prices=top_reference_prices,
    )
    if progress_callback is not None:
        progress_callback("publication", 1, 1, None)

    run_directory = output_root / run_id

    return EdgeScoutScanResult(
        run_directory=run_directory,
        candidates_path=run_directory / "candidates.csv",
        watchlist_path=run_directory / "watchlist.csv",
        near_miss_path=run_directory / "near_miss.csv",
        summary_path=run_directory / "summary.json",
        report_path=run_directory / "report.md",
        manifest_path=run_directory / "manifest.json",
        latest_path=output_root / "latest.json",
        as_of=as_of,
        candidate_count=len(production_candidates),
        watchlist_count=len(watchlist_candidates),
        near_miss_count=len(near_miss_candidates),
    )


# ---------------------------------------------------------------------------
# 单股扫描
# ---------------------------------------------------------------------------

def _scan_one_stock(
    code: str,
    records: Sequence[Mapping[str, Any]],
    t1_records: Sequence[Mapping[str, Any]],
    config: Mapping[str, Any],
    candle_rule_set: CandleRuleSet,
    industry: str | None = None,
    as_of: date | None = None,
) -> EdgeScoutResult:
    """扫描单只股票。

    参数：
      code: 股票代码
      records: 截断到 as_of 的日线记录序列（不含 T+1）
      t1_records: T+1 可用记录（最多 T+1 一个交易日）
      config: 配置字典
      candle_rule_set: V1 CandleRuleSet（正确类型）
      industry: 行业（可选）
      as_of: 扫描日期

    返回：
      扫描结果
    """

    if as_of is None:
        as_of = _to_date(records[-1].get("date")) or datetime.now().date()

    first_date = _to_date(records[0].get("date")) or datetime.now().date()
    last_date = _to_date(records[-1].get("date")) or datetime.now().date()

    # 应用硬门槛
    gates_passed, gate_failures = apply_hard_gates(code, records, config)

    if not gates_passed:
        return EdgeScoutResult(
            code=code,
            as_of=as_of,
            status="rejected",
            admission_error_code="hard_gate_failure",
            hard_gate_details=tuple(gate_failures),  # P0-7: 具体硬门槛失败原因
            first_date=first_date,
            last_date=last_date,
            limitations=tuple(gate_failures) if gate_failures else ("hard_gate_failure",),
        )

    # 计算综合评分
    try:
        # 检测 V1 蜡烛图形态（使用正确的 CandleRuleSet 类型）
        candle_patterns = detect_candle_patterns(records, candle_rule_set)
        bearish_risk_patterns = detect_bearish_risk_patterns(records)
        latest_bearish_risks = tuple(
            name for name, values in bearish_risk_patterns.items() if values and values[-1]
        )
        setup = evaluate_t_day_setup(records, config, candle_patterns)

        # 计算 PMK 特征
        open_ = [float(r.get("open", 0)) for r in records]
        high = [float(r.get("high", 0)) for r in records]
        low = [float(r.get("low", 0)) for r in records]
        close = [float(r.get("close", 0)) for r in records]
        volume = [float(r.get("volume", 0)) for r in records]

        pmk_features = compute_pmk_features(open_, high, low, close, volume)
        candle_features = compute_candle_confirmation_features(open_, high, low, close, volume)
        start_signals = compute_start_signals(high, low, close, volume)

        latest = records[-1]
        preclose = float(latest.get("preclose", 0) or 0)
        pct_chg = (close[-1] / preclose - 1.0) * 100.0 if preclose > 0 else 0.0
        ret_5d = (close[-1] / close[-6] - 1.0) * 100.0 if len(close) >= 6 and close[-6] > 0 else 0.0
        volume_ma20 = sum(volume[-20:]) / min(20, len(volume)) if volume else 0.0
        volume_ratio_20 = volume[-1] / volume_ma20 if volume_ma20 > 0 else 0.0
        discovery_tier = classify_discovery_tier(start_signals.count)
        discovery_eligible, discovery_rejections = _evaluate_discovery_eligibility(
            close=close[-1],
            amount_cny=float(latest.get("amount", 0) or 0),
            pct_chg=pct_chg,
            ret_5d=ret_5d,
            turn=float(latest.get("turn", 0) or 0),
            volume_ratio_20=volume_ratio_20,
            config=config,
        )
        cnstock_base_score = compute_price_volume_base_score(
            high,
            low,
            close,
            volume,
            futu_bonus=start_signals.futu_bonus,
        )
        cnstock_pool = evaluate_discovery_pool(
            start_count=start_signals.count,
            base_score=cnstock_base_score,
            pct_chg=pct_chg,
            ret_5d=ret_5d,
            amount_cny=float(latest.get("amount", 0) or 0),
            risk_codes=start_signals.risk_codes,
            config=config,
        )
        cnstock_rank, cnstock_rank_breakdown = compute_cnstock_discovery_rank(
            cnstock_base_score,
            pmk_features,
            candle_features,
            pct_chg,
            ret_5d,
            volume_ratio_20,
        )

        # 计算 T+1 确认（使用真实 T+1 数据）
        # P0 修复：as_of_index 必须在 if t1_records 之外初始化，否则 as_of 为最新交易日
        # 且无 T+1 bar 时（合理场景），会因 NameError 抛出 unexpected_error。
        t1_confirmed = False
        t1_obs = None
        as_of_index = None

        # 先定位 as_of 在截断后 records 中的索引（无论是否有 T+1）
        for i, r in enumerate(records):
            record_date = _to_date(r.get("date"))
            if record_date == as_of:
                as_of_index = i
                break

        if t1_records and len(t1_records) >= 1:
            # 获取 signal_high（使用 T 日信号日的高点）
            signal_high = float(high[-1]) if high else 0.0
            volume_ma20 = 0.0
            if volume and len(volume) >= 20:
                volume_ma20 = sum(volume[-20:]) / 20.0

            min_volume_ratio = float(
                config.get("setup", {}).get("confirmation", {}).get("min_volume_to_ma20", 1.05)
            )

            if as_of_index is not None:
                try:
                    # 关键修复：T+1 确认输入应为 records_until_t + [first_t1_bar]
                    # 当前代码错误地只传入 records（不含 T+1 bar），导致永远无法确认
                    records_with_t1 = list(records)
                    records_with_t1.append(t1_records[0])  # 添加第一根 T+1 bar

                    # 日期列表也需包含 T+1 日期
                    dates_with_t1 = [r["date"] for r in records]
                    dates_with_t1.append(t1_records[0].get("date"))

                    t1_obs = observe_t1(
                        records=records_with_t1,
                        dates=dates_with_t1,
                        as_of_index=as_of_index,
                        signal_high=signal_high,
                        volume_ma20_at_signal=volume_ma20,
                        min_volume_ratio=min_volume_ratio,
                    )
                    t1_confirmed = bool(t1_obs.confirmed) if t1_obs.confirmed is not None else False
                except Exception:
                    t1_confirmed = False

        price_volume_reason = "missing_t1_bar"
        price_volume_ratio = None
        if t1_obs is not None:
            price_volume_reason = t1_obs.reason
            price_volume_ratio = t1_obs.volume_ratio
        valid_setup_confirmed = setup.valid and t1_confirmed
        if valid_setup_confirmed:
            valid_setup_reason = "valid_setup_confirmed"
        elif not setup.valid:
            valid_setup_reason = "t_day_setup_not_valid"
        else:
            valid_setup_reason = price_volume_reason

        # Recompute the unified score after T+1 is known. Positive Futu evidence
        # is bounded inside timing; explicit Futu risks reduce the risk subscore.
        scoring_result, rejection_reason = score_single_stock(
            code=code,
            records=records,
            config=config,
            candle_patterns=candle_patterns,
            t1_observation=t1_obs if setup.valid else None,
            futu_bonus=start_signals.futu_bonus,
            futu_risk_codes=(
                *start_signals.risk_codes,
                *(("bearish_candle_risk",) if latest_bearish_risks else ()),
            ),
        )
        discovery_score, discovery_breakdown = compute_discovery_score(
            scoring_result.edge_score,
            pmk_features,
            candle_features,
            start_signals.count,
            pct_chg,
            ret_5d,
            volume_ratio_20,
        )

        # Production eligibility requires a valid T-day setup and its T+1 confirmation.
        tier_type = classify_tier(
            edge_score=scoring_result.edge_score,
            t1_confirmed=valid_setup_confirmed,
            hard_gate_failures=scoring_result.hard_gate_failures,
            production_enabled=bool(config.get("production_enabled", False)),
        )

        # P0 修复：收集 T+1 确认状态，as_of 为最新交易日且无 T+1 时返回稳定原因 missing_t1_bar
        if t1_records and len(t1_records) >= 1:
            t1_reason = "confirmed" if t1_confirmed else "not_confirmed"
            admission_error_code = rejection_reason
        else:
            # 没有 T+1 bar（as_of 为最新交易日）：返回稳定原因，不抛 unexpected_error
            t1_reason = "missing_t1_bar"
            admission_error_code = "missing_t1_bar"

        # 构造 limitations
        if industry is None:
            stock_limitations: tuple[str, ...] = ("research_approximation_only",)
        else:
            stock_limitations = ("research_approximation_only",)

        # 如果 missing_t1_bar，添加限制说明
        if t1_reason == "missing_t1_bar":
            stock_limitations = stock_limitations + ("missing_t1_bar",)

        # 计算研究参考价（research-only，非执行价）
        reference_prices = compute_reference_prices(
            code=code,
            records=records,
            config=config,
            as_of=as_of,
        )

        return EdgeScoutResult(
            code=code,
            as_of=as_of,
            status="admitted" if tier_type != "rejected" else "rejected",
            admission_error_code=admission_error_code,
            admission_detail=f"t1_reason={t1_reason}" if t1_reason == "missing_t1_bar" else None,
            hard_gate_details=scoring_result.hard_gate_failures,
            first_date=first_date,
            last_date=last_date,
            base_quality_score=scoring_result.base_quality_score,
            timing_score=scoring_result.timing_score,
            risk_score=scoring_result.risk_score,
            t1_confirmed=t1_confirmed,
            t1_reason=t1_reason,
            t_day_setup_valid=setup.valid,
            t_day_setup_reason=setup.reason,
            t_day_patterns=setup.matched_patterns,
            t_day_setup_failed_conditions=setup.failed_conditions,
            price_volume_confirmed=t1_confirmed,
            price_volume_confirmation_reason=price_volume_reason,
            price_volume_ratio=price_volume_ratio,
            valid_setup_confirmed=valid_setup_confirmed,
            valid_setup_confirmation_reason=valid_setup_reason,
            industry=industry,
            research_close=close[-1],
            pct_chg=pct_chg,
            ret_5d=ret_5d,
            amount_cny=float(latest.get("amount", 0) or 0),
            turn=float(latest.get("turn", 0) or 0),
            volume_ratio_20=volume_ratio_20,
            pmk_trend_confirmed=bool(pmk_features.get("pmk_trend_confirmed")),
            pmk_trend_reason=str(pmk_features.get("pmk_trend_reason", "")),
            pmk_shape_score=float(pmk_features.get("pmk_shape_score", 0.0)),
            pmk_shape_pattern=str(pmk_features.get("pmk_shape_pattern", "N/A")),
            pmk_rsi=float(pmk_features.get("pmk_rsi", 50.0)),
            pmk_atr_squeeze=bool(pmk_features.get("pmk_atr_squeeze")),
            pmk_macd_confirm=bool(pmk_features.get("pmk_macd_confirm")),
            pmk_volume_breakout=bool(pmk_features.get("pmk_volume_breakout")),
            pmk_feature_bonus=float(pmk_features.get("pmk_feature_bonus", 0.0)),
            candle_position_zone=str(candle_features.get("candle_position_zone", "N/A")),
            candle_low_position_pct=float(candle_features.get("candle_low_position_pct", 1.0)),
            candle_close_location=float(candle_features.get("candle_close_location", 0.0)),
            candle_volume_confirm=bool(candle_features.get("candle_volume_confirm")),
            candle_volume_ratio_20=float(candle_features.get("candle_volume_ratio_20", 0.0)),
            candle_upper_shadow_pct=float(candle_features.get("candle_upper_shadow_pct", 1.0)),
            candle_long_upper_shadow_risk=bool(candle_features.get("candle_long_upper_shadow_risk")),
            candle_bearish_risk_patterns=latest_bearish_risks,
            candle_bullish_reversal=bool(candle_features.get("candle_bullish_reversal")),
            candle_bullish_continuation=bool(candle_features.get("candle_bullish_continuation")),
            candle_box_breakout=bool(candle_features.get("candle_box_breakout")),
            candle_confirm_score=float(candle_features.get("candle_confirm_score", 0.0)),
            candle_confirm_reason=str(candle_features.get("candle_confirm_reason", "no_confirmation")),
            start_signal_count=start_signals.count,
            start_signals=start_signals.names,
            start_signal_reasons=start_signals.reasons,
            mhpg_buy=start_signals.mhpg_buy,
            dxbd_up=start_signals.dxbd_up,
            mfk4_triggered=start_signals.mfk4_triggered,
            gding_up=start_signals.gding_up,
            dingdi_safe_up=start_signals.dingdi_safe_up,
            futu_bonus=start_signals.futu_bonus,
            futu_status_codes=start_signals.status_codes,
            futu_risk_codes=start_signals.risk_codes,
            cnstock_base_score=cnstock_base_score,
            cnstock_pool=cnstock_pool.pool,
            cnstock_pool_eligible=cnstock_pool.eligible,
            cnstock_pool_rejection_reasons=cnstock_pool.rejection_reasons,
            cnstock_discovery_rank=cnstock_rank,
            cnstock_discovery_rank_breakdown=cnstock_rank_breakdown,
            discovery_tier=discovery_tier,
            discovery_eligible=discovery_eligible,
            discovery_rejection_reasons=discovery_rejections,
            discovery_score=discovery_score,
            discovery_score_breakdown=discovery_breakdown,
            tier=Tier(
                code=code,
                as_of=as_of,
                tier=tier_type,
                edge_score=scoring_result.edge_score,
                base_quality_score=scoring_result.base_quality_score,
                timing_score=scoring_result.timing_score,
                risk_score=scoring_result.risk_score,
            ),
            limitations=stock_limitations,
            reference_prices=reference_prices,
        )
    except Exception as exc:
        error_text = str(exc)
        return EdgeScoutResult(
            code=code,
            as_of=as_of,
            status="rejected",
            admission_error_code="unexpected_error",
            admission_detail=error_text,
            first_date=first_date,
            last_date=last_date,
            limitations=(f"unexpected_error: {error_text}",),
        )
