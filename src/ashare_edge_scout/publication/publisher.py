"""Edge Scout read-only research publication module.

镜像 V1 的原子发布模式（temp dir + os.replace）。
Outputs the complete audit bundle, including discovery and daily research watchlists.
The V1 production tier is fail-closed and candidates.csv must remain empty.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import shutil
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from ..data.contracts import (
    EdgeScoutResult,
    EdgeScoutScanSummary,
    ReferencePricePublicationRow,
    Tier,
)
from ..data.reference_prices import ReferencePrices


def publish_scan_results(
    run_directory: Path,
    *,
    run_id: str,
    results: Sequence[EdgeScoutResult],
    production_candidates: Sequence[Tier],
    watchlist_candidates: Sequence[Tier],
    near_miss_candidates: Sequence[Tier],
    summary: EdgeScoutScanSummary,
    top_reference_prices: Sequence[ReferencePricePublicationRow] = (),
    prospective_eligible: bool = False,
    visible_data_through: date | None = None,
    published_at_utc: datetime | None = None,
) -> Path:
    """发布扫描结果。

    通过临时目录 + os.replace 实现原子发布。
    目标目录由 scanner 传入（output_root / run_id）， publisher 在临时目录中构建内容后 atomic move。

    参数：
      run_directory: 输出根目录（不为目标 run 目录，由 publisher 内部构造）
      run_id: 运行 ID
      results: 所有股票扫描结果
      production_candidates: A 级生产候选
      watchlist_candidates: B 级观察候选
      near_miss_candidates: C 级近 miss 候选
      summary: 扫描摘要
      top_reference_prices: 按 T+1 确认优先 + 层级优先级 + edge_score 排序的 TOP 候选参考价
       每行显式携带 T 日 setup、价格量能观察和有效 setup 确认状态。

    返回：
      最终 run_directory 路径
    """

    run_target = run_directory / run_id

    if summary.status != "success":
        raise ValueError(f"only successful scans may be published as latest: {summary.status!r}")
    if production_candidates or summary.production_candidate_count:
        raise ValueError("Edge Scout V1 production tier is disabled; production candidates must be empty")

    # 创建临时目录（禁止覆盖已存在的 run）
    temporary_directory = run_directory / f".{run_id}.tmp"

    # 如果目标 run 已存在，拒绝覆盖（保证审计产物不可变性）
    if run_target.exists():
        raise FileExistsError(
            f"run_id '{run_id}' 已存在，禁止覆盖已发布的审计产物。"
            f"如需重新运行，请更换 run_id 或手动删除旧 run。"
        )

    if temporary_directory.exists():
        raise FileExistsError(
            f"temporary run directory already exists: {temporary_directory}; refusing to delete it"
        )

    temporary_directory.mkdir(parents=True, exist_ok=True)

    try:
        # 写出 CSV
        _write_candidates_csv(
            path=temporary_directory / "candidates.csv",
            tiers=production_candidates,
        )

        _write_watchlist_csv(
            path=temporary_directory / "watchlist.csv",
            tiers=watchlist_candidates,
        )

        _write_near_miss_csv(
            path=temporary_directory / "near_miss.csv",
            tiers=near_miss_candidates,
        )

        # 写出 TOP 研究参考价 CSV（research-only）
        _write_reference_prices_csv(
            path=temporary_directory / "reference_prices.csv",
            tiers_with_prices=top_reference_prices,
        )
        _write_discovery_csv(
            path=temporary_directory / "discovery.csv",
            results=results,
        )
        _write_daily_research_watchlist_csv(
            path=temporary_directory / "daily_research_watchlist.csv",
            results=results,
        )

        publication_time = published_at_utc or datetime.now(timezone.utc)

        # 写出 summary.json
        summary_path = temporary_directory / "summary.json"
        _write_json(summary_path, summary.__dict__)

        # 写出 report.md
        report_path = temporary_directory / "report.md"
        report_path.write_text(
            _generate_report(
                summary,
                production_candidates,
                watchlist_candidates,
                near_miss_candidates,
                top_reference_prices=top_reference_prices,
                results=results,
            ),
            encoding="utf-8",
        )

        # 写出逐股票审计 CSV（包含所有股票的 status/tier/score/error_code）
        _write_audit_csv(
            path=temporary_directory / "results.jsonl",
            results=results,
        )
        _write_prospective_snapshot(
            path=temporary_directory / "prospective_snapshot.json",
            run_id=run_id,
            summary=summary,
            results=results,
            prospective_eligible=prospective_eligible,
            visible_data_through=visible_data_through,
            published_at_utc=publication_time,
            source_artifacts={
                name: _sha256(temporary_directory / name)
                for name in ("daily_research_watchlist.csv", "results.jsonl", "summary.json")
            },
        )

        # 写出 manifest.json（包含所有产出文件）
        manifest = {
            "schema_version": summary.schema_version,
            "run_id": summary.run_id,
            "as_of": summary.as_of.isoformat() if isinstance(summary.as_of, date) else str(summary.as_of),
            "files": {
                name: {"sha256": _sha256(temporary_directory / name)}
                for name in ("candidates.csv", "watchlist.csv", "near_miss.csv",
                             "discovery.csv", "daily_research_watchlist.csv", "reference_prices.csv",
                             "results.jsonl", "summary.json", "report.md",
                             "prospective_snapshot.json")
            },
        }
        manifest_path = temporary_directory / "manifest.json"
        _write_json(manifest_path, manifest)

        # 原子移动
        os.replace(temporary_directory, run_target)

        # 更新 latest.json（原子）
        latest_path = run_directory / "latest.json"
        latest_temporary = run_directory / f".{run_id}.latest.json.tmp"

        latest = {
            "schema_version": summary.schema_version,
            "status": summary.status,
            "run_id": summary.run_id,
            "run_directory": run_id,
            "as_of": summary.as_of.isoformat() if isinstance(summary.as_of, date) else str(summary.as_of),
            "candidate_count": summary.production_candidate_count,
            "watchlist_count": summary.watchlist_count,
            "near_miss_count": summary.near_miss_count,
            "published_at_utc": publication_time.isoformat(),
        }
        _write_json(latest_temporary, latest)
        os.replace(latest_temporary, latest_path)

    except Exception:
        if temporary_directory.is_dir():
            shutil.rmtree(temporary_directory)
        raise

    return run_target


def _watch_stage(result: EdgeScoutResult) -> str | None:
    if result.valid_setup_confirmed:
        return "confirmed_watch"
    if result.t_day_setup_valid:
        return "setup_watch"
    if result.cnstock_pool_eligible:
        return "cnstock_pool_watch"
    if result.discovery_eligible and (result.start_signal_count or 0) >= 2:
        return "discovery_watch"
    return None


def _prospective_row(result: EdgeScoutResult, watch_stage: str | None) -> dict[str, Any]:
    tier = result.tier
    return {
        "code": result.code,
        "as_of": result.as_of.isoformat(),
        "watch_stage": watch_stage,
        "research_close": result.research_close,
        "tier": tier.tier if tier else None,
        "edge_score": tier.edge_score if tier else None,
        "base_quality_score": tier.base_quality_score if tier else None,
        "timing_score": tier.timing_score if tier else None,
        "risk_score": tier.risk_score if tier else None,
        "valid_setup_confirmed": result.valid_setup_confirmed,
        "t_day_setup_valid": result.t_day_setup_valid,
        "price_volume_confirmed": result.price_volume_confirmed,
        "cnstock_pool": result.cnstock_pool,
        "cnstock_pool_eligible": result.cnstock_pool_eligible,
        "cnstock_discovery_rank": result.cnstock_discovery_rank,
        "start_signal_count": result.start_signal_count,
        "start_signals": list(result.start_signals),
        "selection_reason": (
            "v1_t_setup_and_t1_confirmation" if watch_stage == "confirmed_watch"
            else "v1_t_setup_waiting_for_confirmation" if watch_stage == "setup_watch"
            else f"cnstock_pool:{result.cnstock_pool}" if watch_stage == "cnstock_pool_watch"
            else "broad_2plus_discovery_filter" if watch_stage == "discovery_watch"
            else None
        ),
        "futu_status_codes": list(result.futu_status_codes),
        "futu_risk_codes": list(result.futu_risk_codes),
        "candle_bearish_risk_patterns": list(result.candle_bearish_risk_patterns),
        "limitations": list(result.limitations),
    }


def _write_prospective_snapshot(
    path: Path,
    *,
    run_id: str,
    summary: EdgeScoutScanSummary,
    results: Sequence[EdgeScoutResult],
    prospective_eligible: bool,
    visible_data_through: date | None,
    published_at_utc: datetime,
    source_artifacts: Mapping[str, str],
) -> None:
    baseline = [result for result in results if result.tier is not None]
    rows = [_prospective_row(result, _watch_stage(result)) for result in baseline]
    selected = [row for row in rows if row["watch_stage"] is not None]
    payload = {
        "schema_version": "edge_scout_prospective_v1",
        "research_only": True,
        "classification_only": True,
        "run_id": run_id,
        "as_of": summary.as_of.isoformat(),
        "published_at_utc": published_at_utc.astimezone(timezone.utc).isoformat(),
        "visible_data_through": visible_data_through.isoformat() if visible_data_through else None,
        "prospective_eligible": prospective_eligible,
        "eligibility_reason": "automatic_as_of" if prospective_eligible else "manual_or_unknown_as_of",
        "config_sha256": summary.inputs.get("config_sha256"),
        "label": "next_five_tradable_closes_reach_3pct_without_close_below_minus_3pct",
        "source_artifacts": dict(source_artifacts),
        "baseline_rows": rows,
        "selected_rows": selected,
    }
    _write_json(path, payload)


def _write_candidates_csv(
    path: Path,
    tiers: Sequence[Tier],
) -> None:
    """写出 A 级生产候选 CSV。"""

    if not tiers:
        path.write_text("rank,code,as_of,edge_score,base_quality_score,timing_score,risk_score\n", encoding="utf-8")
        return

    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=[
            "rank", "code", "as_of", "edge_score", "base_quality_score",
            "timing_score", "risk_score"
        ])
        writer.writeheader()
        for index, tier in enumerate(tiers, start=1):
            writer.writerow({
                "rank": str(index),
                "code": tier.code,
                "as_of": tier.as_of.isoformat(),
                "edge_score": f"{tier.edge_score:.6f}",
                "base_quality_score": f"{tier.base_quality_score:.6f}",
                "timing_score": f"{tier.timing_score:.6f}",
                "risk_score": f"{tier.risk_score:.6f}",
            })


def _write_watchlist_csv(
    path: Path,
    tiers: Sequence[Tier],
) -> None:
    """写出 B 级观察候选 CSV。"""

    if not tiers:
        path.write_text("rank,code,as_of,edge_score,base_quality_score,timing_score,risk_score\n", encoding="utf-8")
        return

    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=[
            "rank", "code", "as_of", "edge_score", "base_quality_score",
            "timing_score", "risk_score"
        ])
        writer.writeheader()
        for index, tier in enumerate(tiers, start=1):
            writer.writerow({
                "rank": str(index),
                "code": tier.code,
                "as_of": tier.as_of.isoformat(),
                "edge_score": f"{tier.edge_score:.6f}",
                "base_quality_score": f"{tier.base_quality_score:.6f}",
                "timing_score": f"{tier.timing_score:.6f}",
                "risk_score": f"{tier.risk_score:.6f}",
            })


def _write_audit_csv(
    path: Path,
    results: Sequence[EdgeScoutResult],
) -> None:
    """写出逐股票审计 JSONL（每行一个股票的 status/tier/score/error_code/P0-7 审计字段）。"""

    import json

    with path.open("w", encoding="utf-8") as file:
        for result in results:
            audit_record = {
                "code": result.code,
                "as_of": result.as_of.isoformat() if isinstance(result.as_of, date) else str(result.as_of),
                "status": result.status,
            }
            if result.tier:
                audit_record["tier"] = result.tier.tier
                audit_record["edge_score"] = result.tier.edge_score
                audit_record["base_quality_score"] = result.tier.base_quality_score
                audit_record["timing_score"] = result.tier.timing_score
                audit_record["risk_score"] = result.tier.risk_score
            if result.admission_error_code:
                audit_record["admission_error_code"] = result.admission_error_code
            # P0-7: 硬门槛具体失败原因
            if result.hard_gate_details:
                audit_record["hard_gate_details"] = list(result.hard_gate_details)
            # P0-7: 单股评分子项
            if result.base_quality_score is not None:
                audit_record["base_quality_score_raw"] = result.base_quality_score
            if result.timing_score is not None:
                audit_record["timing_score_raw"] = result.timing_score
            if result.risk_score is not None:
                audit_record["risk_score_raw"] = result.risk_score
            # P0-7: T+1 确认状态
            if result.t1_confirmed is not None:
                audit_record["t1_confirmed"] = result.t1_confirmed
            if result.t1_reason:
                audit_record["t1_reason"] = result.t1_reason
            if result.t_day_setup_valid is not None:
                audit_record["t_day_setup_valid"] = result.t_day_setup_valid
                audit_record["t_day_setup_reason"] = result.t_day_setup_reason
                audit_record["t_day_patterns"] = list(result.t_day_patterns)
                audit_record["t_day_setup_failed_conditions"] = list(
                    result.t_day_setup_failed_conditions
                )
            if result.price_volume_confirmed is not None:
                audit_record["price_volume_confirmed"] = result.price_volume_confirmed
                audit_record["price_volume_confirmation_reason"] = (
                    result.price_volume_confirmation_reason
                )
                audit_record["price_volume_ratio"] = result.price_volume_ratio
            if result.valid_setup_confirmed is not None:
                audit_record["valid_setup_confirmed"] = result.valid_setup_confirmed
                audit_record["valid_setup_confirmation_reason"] = (
                    result.valid_setup_confirmation_reason
                )
            if result.discovery_tier is not None:
                audit_record.update({
                    "industry": result.industry,
                    "research_close": result.research_close,
                    "pct_chg": result.pct_chg,
                    "ret_5d": result.ret_5d,
                    "amount_cny": result.amount_cny,
                    "turn": result.turn,
                    "volume_ratio_20": result.volume_ratio_20,
                    "pmk_trend_confirmed": result.pmk_trend_confirmed,
                    "pmk_trend_reason": result.pmk_trend_reason,
                    "pmk_shape_score": result.pmk_shape_score,
                    "pmk_shape_pattern": result.pmk_shape_pattern,
                    "pmk_rsi": result.pmk_rsi,
                    "pmk_atr_squeeze": result.pmk_atr_squeeze,
                    "pmk_macd_confirm": result.pmk_macd_confirm,
                    "pmk_volume_breakout": result.pmk_volume_breakout,
                    "pmk_feature_bonus": result.pmk_feature_bonus,
                    "candle_position_zone": result.candle_position_zone,
                    "candle_low_position_pct": result.candle_low_position_pct,
                    "candle_close_location": result.candle_close_location,
                    "candle_volume_confirm": result.candle_volume_confirm,
                    "candle_volume_ratio_20": result.candle_volume_ratio_20,
                    "candle_upper_shadow_pct": result.candle_upper_shadow_pct,
                    "candle_long_upper_shadow_risk": result.candle_long_upper_shadow_risk,
                    "candle_bearish_risk_patterns": list(result.candle_bearish_risk_patterns),
                    "candle_bullish_reversal": result.candle_bullish_reversal,
                    "candle_bullish_continuation": result.candle_bullish_continuation,
                    "candle_box_breakout": result.candle_box_breakout,
                    "candle_confirm_score": result.candle_confirm_score,
                    "candle_confirm_reason": result.candle_confirm_reason,
                    "start_signal_count": result.start_signal_count,
                    "start_signals": list(result.start_signals),
                    "start_signal_reasons": list(result.start_signal_reasons),
                    "mhpg_buy": result.mhpg_buy,
                    "dxbd_up": result.dxbd_up,
                    "mfk4_triggered": result.mfk4_triggered,
                    "gding_up": result.gding_up,
                    "dingdi_safe_up": result.dingdi_safe_up,
                    "futu_bonus": result.futu_bonus,
                    "futu_status_codes": list(result.futu_status_codes),
                    "futu_risk_codes": list(result.futu_risk_codes),
                    "cnstock_base_score": result.cnstock_base_score,
                    "cnstock_pool": result.cnstock_pool,
                    "cnstock_pool_eligible": result.cnstock_pool_eligible,
                    "cnstock_pool_rejection_reasons": list(result.cnstock_pool_rejection_reasons),
                    "cnstock_discovery_rank": result.cnstock_discovery_rank,
                    "cnstock_discovery_rank_breakdown": result.cnstock_discovery_rank_breakdown,
                    "discovery_tier": result.discovery_tier,
                    "discovery_eligible": result.discovery_eligible,
                    "discovery_rejection_reasons": list(result.discovery_rejection_reasons),
                    "discovery_score": result.discovery_score,
                    "discovery_score_breakdown": result.discovery_score_breakdown,
                })
            # P0 新增：写出 admission_detail 和 limitations，方便定位错误
            if result.admission_detail:
                audit_record["admission_detail"] = result.admission_detail
            if result.limitations:
                audit_record["limitations"] = list(result.limitations)
            # 研究参考价（research-only，非执行价）：随单股审计明细一并输出
            if result.reference_prices is not None:
                rp = result.reference_prices
                audit_record["reference_prices"] = {
                    "close_now": rp.close_now,
                    "signal_high": rp.signal_high,
                    "signal_low": rp.signal_low,
                    "atr14": rp.atr14,
                    "buy_reference": rp.buy_reference,
                    "stop_reference": rp.stop_reference,
                    "partial_take_profit_reference": rp.partial_take_profit_reference,
                    "take_profit_reference": rp.take_profit_reference,
                    "risk_distance_pct": rp.risk_distance_pct,
                    "methodology": rp.methodology,
                }
            file.write(json.dumps(audit_record, ensure_ascii=False) + "\n")


def _write_near_miss_csv(
    path: Path,
    tiers: Sequence[Tier],
) -> None:
    """写出 C 级近 miss 候选 CSV。"""

    if not tiers:
        path.write_text("rank,code,as_of,edge_score,base_quality_score,timing_score,risk_score\n", encoding="utf-8")
        return

    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=[
            "rank", "code", "as_of", "edge_score", "base_quality_score",
            "timing_score", "risk_score"
        ])
        writer.writeheader()
        for index, tier in enumerate(tiers, start=1):
            writer.writerow({
                "rank": str(index),
                "code": tier.code,
                "as_of": tier.as_of.isoformat(),
                "edge_score": f"{tier.edge_score:.6f}",
                "base_quality_score": f"{tier.base_quality_score:.6f}",
                "timing_score": f"{tier.timing_score:.6f}",
                "risk_score": f"{tier.risk_score:.6f}",
            })


def _write_reference_prices_csv(
    path: Path,
    tiers_with_prices: Sequence[ReferencePricePublicationRow],
) -> None:
    """写出 TOP 研究参考价 CSV（research-only，非执行价、非投资建议）。"""

    header = (
        "rank,code,as_of,tier,edge_score,close_now,signal_high,signal_low,atr14,"
        "buy_reference,stop_reference,take_profit_reference,"
        "partial_take_profit_reference,risk_distance_pct,t_day_setup_valid,"
        "price_volume_confirmed,valid_setup_confirmed,discovery_tier,"
        "discovery_score,start_signal_count"
    )
    if not tiers_with_prices:
        path.write_text(header + "\n", encoding="utf-8")
        return

    with path.open("w", encoding="utf-8", newline="") as file:
        file.write(header + "\n")
        for index, row in enumerate(tiers_with_prices, start=1):
            tier = row.tier
            prices = row.prices
            file.write(",".join([
                str(index),
                tier.code,
                tier.as_of.isoformat(),
                tier.tier,
                f"{tier.edge_score:.6f}",
                f"{prices.close_now:.4f}",
                f"{prices.signal_high:.4f}",
                f"{prices.signal_low:.4f}",
                f"{prices.atr14:.4f}",
                f"{prices.buy_reference:.4f}",
                f"{prices.stop_reference:.4f}",
                f"{prices.take_profit_reference:.4f}",
                f"{prices.partial_take_profit_reference:.4f}",
                f"{prices.risk_distance_pct:.6f}",
                "True" if row.t_day_setup_valid else "False",
                "True" if row.price_volume_confirmed else "False",
                "True" if row.valid_setup_confirmed else "False",
                row.discovery_tier,
                f"{row.discovery_score:.6f}",
                str(row.start_signal_count),
            ]) + "\n")


def _write_discovery_csv(path: Path, results: Sequence[EdgeScoutResult]) -> None:
    """Publish rich research discovery rows without changing production eligibility."""

    fields = [
        "rank", "code", "industry", "as_of", "discovery_tier", "discovery_eligible",
        "discovery_rejection_reasons", "discovery_score",
        "cnstock_pool", "cnstock_pool_eligible", "cnstock_pool_rejection_reasons",
        "cnstock_base_score", "cnstock_discovery_rank", "cnstock_discovery_rank_breakdown",
        "start_signal_count", "start_signals", "start_signal_reasons",
        "mhpg_buy", "dxbd_up", "mfk4_triggered", "gding_up", "dingdi_safe_up",
        "futu_bonus", "futu_status_codes", "futu_risk_codes", "edge_score",
        "research_close", "pct_chg", "ret_5d", "turn", "amount_cny", "volume_ratio_20",
        "pmk_trend_confirmed", "pmk_trend_reason", "pmk_shape_score", "pmk_shape_pattern",
        "pmk_rsi", "pmk_atr_squeeze", "pmk_macd_confirm", "pmk_volume_breakout",
        "pmk_feature_bonus", "candle_position_zone", "candle_low_position_pct",
        "candle_close_location", "candle_volume_confirm", "candle_volume_ratio_20",
        "candle_upper_shadow_pct", "candle_long_upper_shadow_risk",
        "candle_bearish_risk_patterns", "candle_bullish_reversal",
        "candle_bullish_continuation", "candle_box_breakout", "candle_confirm_score",
        "candle_confirm_reason", "t_day_setup_valid", "t_day_patterns",
        "price_volume_confirmed", "valid_setup_confirmed", "discovery_score_breakdown",
    ]
    rows = sorted(
        (result for result in results if result.tier is not None and result.discovery_score is not None),
        key=lambda result: (
            0 if result.discovery_eligible else 1,
            -(result.start_signal_count or 0),
            -(result.discovery_score or 0.0),
            result.code,
        ),
    )
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        for rank, result in enumerate(rows, start=1):
            writer.writerow({
                "rank": rank,
                "code": result.code,
                "industry": result.industry or "",
                "as_of": result.as_of.isoformat(),
                "discovery_tier": result.discovery_tier,
                "discovery_eligible": result.discovery_eligible,
                "discovery_rejection_reasons": "|".join(result.discovery_rejection_reasons),
                "discovery_score": result.discovery_score,
                "cnstock_pool": result.cnstock_pool,
                "cnstock_pool_eligible": result.cnstock_pool_eligible,
                "cnstock_pool_rejection_reasons": "|".join(result.cnstock_pool_rejection_reasons),
                "cnstock_base_score": result.cnstock_base_score,
                "cnstock_discovery_rank": result.cnstock_discovery_rank,
                "cnstock_discovery_rank_breakdown": result.cnstock_discovery_rank_breakdown,
                "start_signal_count": result.start_signal_count,
                "start_signals": "|".join(result.start_signals),
                "start_signal_reasons": "|".join(result.start_signal_reasons),
                "mhpg_buy": result.mhpg_buy,
                "dxbd_up": result.dxbd_up,
                "mfk4_triggered": result.mfk4_triggered,
                "gding_up": result.gding_up,
                "dingdi_safe_up": result.dingdi_safe_up,
                "futu_bonus": result.futu_bonus,
                "futu_status_codes": "|".join(result.futu_status_codes),
                "futu_risk_codes": "|".join(result.futu_risk_codes),
                "edge_score": result.tier.edge_score,
                "research_close": result.research_close,
                "pct_chg": result.pct_chg,
                "ret_5d": result.ret_5d,
                "turn": result.turn,
                "amount_cny": result.amount_cny,
                "volume_ratio_20": result.volume_ratio_20,
                "pmk_trend_confirmed": result.pmk_trend_confirmed,
                "pmk_trend_reason": result.pmk_trend_reason,
                "pmk_shape_score": result.pmk_shape_score,
                "pmk_shape_pattern": result.pmk_shape_pattern,
                "pmk_rsi": result.pmk_rsi,
                "pmk_atr_squeeze": result.pmk_atr_squeeze,
                "pmk_macd_confirm": result.pmk_macd_confirm,
                "pmk_volume_breakout": result.pmk_volume_breakout,
                "pmk_feature_bonus": result.pmk_feature_bonus,
                "candle_position_zone": result.candle_position_zone,
                "candle_low_position_pct": result.candle_low_position_pct,
                "candle_close_location": result.candle_close_location,
                "candle_volume_confirm": result.candle_volume_confirm,
                "candle_volume_ratio_20": result.candle_volume_ratio_20,
                "candle_upper_shadow_pct": result.candle_upper_shadow_pct,
                "candle_long_upper_shadow_risk": result.candle_long_upper_shadow_risk,
                "candle_bearish_risk_patterns": "|".join(result.candle_bearish_risk_patterns),
                "candle_bullish_reversal": result.candle_bullish_reversal,
                "candle_bullish_continuation": result.candle_bullish_continuation,
                "candle_box_breakout": result.candle_box_breakout,
                "candle_confirm_score": result.candle_confirm_score,
                "candle_confirm_reason": result.candle_confirm_reason,
                "t_day_setup_valid": result.t_day_setup_valid,
                "t_day_patterns": "|".join(result.t_day_patterns),
                "price_volume_confirmed": result.price_volume_confirmed,
                "valid_setup_confirmed": result.valid_setup_confirmed,
                "discovery_score_breakdown": result.discovery_score_breakdown,
            })


def _write_daily_research_watchlist_csv(path: Path, results: Sequence[EdgeScoutResult]) -> None:
    """Publish one daily research table without promoting discovery into buy eligibility."""

    fields = [
        "rank", "code", "industry", "as_of", "watch_stage", "research_only",
        "valid_setup_confirmed", "t_day_setup_valid", "price_volume_confirmed",
        "cnstock_pool", "cnstock_pool_eligible", "cnstock_discovery_rank",
        "cnstock_base_score", "edge_score", "base_quality_score", "timing_score", "risk_score",
        "start_signal_count", "start_signals", "futu_bonus", "futu_status_codes",
        "futu_risk_codes", "candle_bearish_risk_patterns",
        "t_day_patterns",
        "pct_chg", "ret_5d", "amount_cny", "turn", "volume_ratio_20",
        "buy_reference", "stop_reference", "partial_take_profit_reference",
        "take_profit_reference", "risk_distance_pct", "selection_reason", "limitations",
    ]

    rows = [(result, _watch_stage(result)) for result in results if result.tier is not None]
    rows = [(result, watch_stage) for result, watch_stage in rows if watch_stage is not None]
    priority = {
        "confirmed_watch": 0,
        "setup_watch": 1,
        "cnstock_pool_watch": 2,
        "discovery_watch": 3,
    }
    rows.sort(key=lambda item: (
        priority[item[1]],
        -(item[0].start_signal_count or 0),
        -(item[0].cnstock_discovery_rank or 0.0),
        item[0].code,
    ))

    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        for rank, (result, watch_stage) in enumerate(rows, start=1):
            prices = result.reference_prices
            if watch_stage == "confirmed_watch":
                reason = "v1_t_setup_and_t1_confirmation"
            elif watch_stage == "setup_watch":
                reason = "v1_t_setup_waiting_for_confirmation"
            elif watch_stage == "cnstock_pool_watch":
                reason = f"cnstock_pool:{result.cnstock_pool}"
            else:
                reason = "broad_2plus_discovery_filter"
            writer.writerow({
                "rank": rank,
                "code": result.code,
                "industry": result.industry or "",
                "as_of": result.as_of.isoformat(),
                "watch_stage": watch_stage,
                "research_only": True,
                "valid_setup_confirmed": result.valid_setup_confirmed,
                "t_day_setup_valid": result.t_day_setup_valid,
                "price_volume_confirmed": result.price_volume_confirmed,
                "cnstock_pool": result.cnstock_pool,
                "cnstock_pool_eligible": result.cnstock_pool_eligible,
                "cnstock_discovery_rank": result.cnstock_discovery_rank,
                "cnstock_base_score": result.cnstock_base_score,
                "edge_score": result.tier.edge_score,
                "base_quality_score": result.tier.base_quality_score,
                "timing_score": result.tier.timing_score,
                "risk_score": result.tier.risk_score,
                "start_signal_count": result.start_signal_count,
                "start_signals": "|".join(result.start_signals),
                "futu_bonus": result.futu_bonus,
                "futu_status_codes": "|".join(result.futu_status_codes),
                "futu_risk_codes": "|".join(result.futu_risk_codes),
                "candle_bearish_risk_patterns": "|".join(result.candle_bearish_risk_patterns),
                "t_day_patterns": "|".join(result.t_day_patterns),
                "pct_chg": result.pct_chg,
                "ret_5d": result.ret_5d,
                "amount_cny": result.amount_cny,
                "turn": result.turn,
                "volume_ratio_20": result.volume_ratio_20,
                "buy_reference": prices.buy_reference if prices else "",
                "stop_reference": prices.stop_reference if prices else "",
                "partial_take_profit_reference": prices.partial_take_profit_reference if prices else "",
                "take_profit_reference": prices.take_profit_reference if prices else "",
                "risk_distance_pct": prices.risk_distance_pct if prices else "",
                "selection_reason": reason,
                "limitations": "|".join(result.limitations),
            })


def _generate_report(
    summary: EdgeScoutScanSummary,
    production_candidates: Sequence[Tier],
    watchlist_candidates: Sequence[Tier],
    near_miss_candidates: Sequence[Tier],
    top_reference_prices: Sequence[ReferencePricePublicationRow] = (),
    results: Sequence[EdgeScoutResult] = (),
) -> str:
    """生成 Markdown 报告。"""

    lines = [
        "# A 股 Edge Scout 扫描报告",
        "",
        "> 仅用于人工研究筛选，不是投资建议，不连接券商，不提交订单。",
        "",
        f"- 运行状态：`{summary.status}`",
        f"- 数据日期：`{summary.as_of}`" if isinstance(summary.as_of, date) else f"- 数据日期：`{summary.as_of}`",
        f"- 候选数量：`{summary.production_candidate_count}`",
        f"- 观察数量：`{summary.watchlist_count}`",
        f"- 近 miss 数量：`{summary.near_miss_count}`",
        f"- Hard-gate 拒绝数量：`{summary.hard_gate_rejected_count}`",
        f"- 全扫描数量守恒：`{summary.scan_quantity_conservation_valid}`",
        f"- 发现层分布：`{summary.discovery_tier_counts}`",
        f"- CNstock 兼容池分布：`{summary.cnstock_pool_counts}`",
        "",
        "## A 级生产候选",
        "",
        "| rank | code | edge_score | base_quality | timing | risk |",
        "|---:|---|---:|---:|---:|---:|",
    ]

    for index, tier in enumerate(production_candidates, start=1):
        lines.append(
            f"| {index} | `{tier.code}` | {tier.edge_score:.4f} | "
            f"{tier.base_quality_score:.4f} | {tier.timing_score:.4f} | {tier.risk_score:.4f} |"
        )

    if not production_candidates:
        lines.append("| - | 无候选 | - | - | - | - |")

    lines.extend([
        "",
        "## B 级观察候选",
        "",
        "| rank | code | edge_score |",
        "|---:|---|---:|",
    ])

    for index, tier in enumerate(watchlist_candidates, start=1):
        lines.append(f"| {index} | `{tier.code}` | {tier.edge_score:.4f} |")

    if not watchlist_candidates:
        lines.append("| - | 无观察候选 | - |")

    lines.extend([
        "",
        "## C 级近 miss",
        "",
        "| rank | code | edge_score |",
        "|---:|---|---:|",
    ])

    for index, tier in enumerate(near_miss_candidates, start=1):
        lines.append(f"| {index} | `{tier.code}` | {tier.edge_score:.4f} |")

    if not near_miss_candidates:
        lines.append("| - | 无近 miss | - |")

    daily_rows = [
        result for result in results
        if result.valid_setup_confirmed
        or result.t_day_setup_valid
        or result.cnstock_pool_eligible
        or (result.discovery_eligible and (result.start_signal_count or 0) >= 2)
    ]
    daily_rows.sort(key=lambda result: (
        0 if result.valid_setup_confirmed else 1 if result.t_day_setup_valid else 2 if result.cnstock_pool_eligible else 3,
        -(result.start_signal_count or 0),
        -(result.cnstock_discovery_rank or 0.0),
        result.code,
    ))
    lines.extend([
        "",
        "## 每日统一研究观察",
        "",
        "> 该表只用于人工复核。`research_only=true`，不是买入建议或订单资格。",
        "",
        "| rank | code | stage | pool | signals | compatibility rank |",
        "|---:|---|---|---|---:|---:|",
    ])
    for index, result in enumerate(daily_rows[:20], start=1):
        if result.valid_setup_confirmed:
            stage = "confirmed_watch"
        elif result.t_day_setup_valid:
            stage = "setup_watch"
        elif result.cnstock_pool_eligible:
            stage = "cnstock_pool_watch"
        else:
            stage = "discovery_watch"
        lines.append(
            f"| {index} | `{result.code}` | {stage} | {result.cnstock_pool or '-'} | "
            f"{result.start_signal_count or 0}/5 | {result.cnstock_discovery_rank or 0.0:.2f} |"
        )
    if not daily_rows:
        lines.append("| - | 无符合分层门槛的样本 | - | - | - | - |")

    lines.extend([
        "",
        "## TOP 研究参考价",
        "",
        "> 以下价格为研究近似参考价，不是可执行价格、真实成交价或投资建议。",
        "> T+1 价格/量能观察通过后仅进入 T+2 人工观察阶段，不代表可成交或应入场。",
        "> 仅展示参考风险距落在 V1 可交易范围 [2.5%, 6.0%] 内的样本；超出范围的样本已排除，仅供观察。",
        "> 有效确认列：✓ = T 日 setup 有效且 T+1 价格/量能观察通过；仍不是订单或成交资格。",
        "",
        "| rank | code | tier | edge_score | 有效确认 | 研究触发参考 | 参考止损 | 参考止盈(1.5R) | 参考止盈(2R) | 风险距离 |",
        "|---:|---|---:|---:|---|---:|---:|---:|---:|---:|",
    ])

    if top_reference_prices:
        for index, row in enumerate(top_reference_prices, start=1):
            tier = row.tier
            prices = row.prices
            mark = "✓" if row.valid_setup_confirmed else "✗"
            lines.append(
                f"| {index} | `{tier.code}` | {tier.tier} | {tier.edge_score:.4f} | {mark} | "
                f"{prices.buy_reference:.4f} | {prices.stop_reference:.4f} | "
                f"{prices.partial_take_profit_reference:.4f} | "
                f"{prices.take_profit_reference:.4f} | "
                f"{prices.risk_distance_pct * 100:.2f}% |"
            )
    else:
        lines.append("| - | 无参考价候选 | - | - | - | - | - | - | - | - |")

    lines.extend([
        "",
        "## Hard-gate 审计",
        "",
        "| reason | count |",
        "|---|---:|",
    ])
    if summary.hard_gate_rejection_counts:
        for reason, count in sorted(summary.hard_gate_rejection_counts.items()):
            lines.append(f"| `{reason}` | {count} |")
    else:
        lines.append("| 无 | 0 |")

    lines.extend([
        "",
        "## 限制",
        "",
        "- 使用前复权研究数据，不能作为成交或撮合价格。",
        "- 存在数据覆盖与幸存者偏差风险。",
        "- 本扫描器不具备券商连接或下单能力。",
        "- 候选与参考价不构成个股推荐或投资建议。",
        "",
    ])

    return "\n".join(lines)


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    """写出 JSON 文件（处理 date 序列化）。"""

    def _serialize(obj: Any) -> Any:
        """将不可序列化的对象转换为可序列化的类型。"""

        from datetime import date as _date, datetime as _datetime, time as _time
        if isinstance(obj, (_date,)):
            return obj.isoformat()
        if isinstance(obj, (_datetime, _time)):
            return obj.isoformat()
        if isinstance(obj, (set, frozenset)):
            return list(obj)
        return obj

    path.write_text(
        json.dumps(
            {k: _serialize(v) for k, v in payload.items()},
            ensure_ascii=False, indent=2, sort_keys=True, default=_serialize,
        ) + "\n",
        encoding="utf-8",
    )


def _sha256(path: Path) -> str:
    """计算文件 SHA-256。"""

    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
