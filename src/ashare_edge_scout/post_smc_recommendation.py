from __future__ import annotations

import csv
import os
from pathlib import Path
from typing import Any, Mapping, Sequence

from ashare_edge_scout.human_review_summary import (
    load_news_reviews,
    load_selection_candidates,
)

CSV_FIELDNAMES = [
    "analysis_order",
    "analysis_bucket",
    "analysis_label",
    "source_mode",
    "code",
    "signal_date",
    "smc_order",
    "start_diagnostic_label",
    "start_diagnostic_type",
    "risk_warning_count",
    "risk_warnings",
    "amount_cny",
    "turn_pct",
    "range_position_20d_pct",
    "range_position_60d_pct",
    "prior_return_20d_pct",
    "volume_ratio_20",
    "review_state",
    "assessment",
    "confidence",
    "event_risk",
    "catalyst_quality",
    "analysis_score",
    "analysis_reason",
    "boundary_note",
]

BUCKET_LABELS = {
    "priority_manual_review": "优先人工复核建议",
    "cautious_observation": "谨慎观察建议",
    "defer_for_risk": "风险暂缓建议",
}
BUCKET_ORDER = (
    ("priority_manual_review", "一、优先人工复核建议"),
    ("cautious_observation", "二、谨慎观察建议"),
    ("defer_for_risk", "三、风险暂缓建议"),
)
BOUNDARY_NOTE = "只读SMC后人工复核建议分析；不改变SMC入选、排序、阈值或News AI口径；不构成买卖建议或已验证胜率。"
CLEAN_DIAGNOSTICS = {"base_breakout_start", "pullback_reacceleration"}
LOW_EVENT_RISK = {"low", "medium"}


def _as_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [item for item in value.split("|") if item]
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        return [str(item) for item in value if str(item)]
    return [str(value)]


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: object, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _classify_smc_only(candidate: Mapping[str, Any]) -> tuple[str, int, str]:
    risk_count = _safe_int(candidate.get("risk_warning_count"))
    diagnostic = str(candidate.get("start_diagnostic_type") or "unclassified_start_diagnostic")
    if risk_count > 0:
        return "defer_for_risk", 20, "存在SMC风险警告，仅作为风险暂缓复核；不改变SMC原始入选。"
    if diagnostic == "high_position_chase":
        return "defer_for_risk", 30, "诊断为高位追涨，缺少新闻复核时先风险暂缓；不改变SMC原始入选。"
    if diagnostic in CLEAN_DIAGNOSTICS:
        return "priority_manual_review", 80, "干净启动/回踩再加速且无SMC风险警告；建议优先人工复核。"
    return "cautious_observation", 50, "SMC入选但启动诊断未分类或证据不够干净；建议谨慎观察。"


def _classify_with_news(candidate: Mapping[str, Any], review: Mapping[str, Any]) -> tuple[str, int, str]:
    risk_count = _safe_int(candidate.get("risk_warning_count"))
    diagnostic = str(candidate.get("start_diagnostic_type") or "unclassified_start_diagnostic")
    review_state = str(review.get("review_state") or "")
    assessment = str(review.get("assessment") or "")
    event_risk = str(review.get("event_risk") or "unknown")
    confidence = _safe_float(review.get("confidence"))

    if review_state == "risk_excluded" or event_risk == "high":
        return "defer_for_risk", 15, "News AI提示风险暂缓或高事件风险，建议先风险暂缓；不改变SMC原始入选。"
    if risk_count > 0:
        return "defer_for_risk", 20, "存在SMC风险警告，即使有新闻复核也先风险暂缓。"
    if assessment == "adverse":
        return "cautious_observation", 35, "News AI结论偏负面，建议仅谨慎观察，不提升优先级。"
    if diagnostic == "high_position_chase":
        return "cautious_observation", 40, "SMC入选但诊断为高位追涨；有AI信息也仅谨慎观察。"
    if diagnostic in CLEAN_DIAGNOSTICS and assessment == "favorable" and event_risk in LOW_EVENT_RISK:
        score = 85 if confidence >= 0.6 else 75
        return "priority_manual_review", score, "干净启动/回踩再加速、无SMC风险警告，且新闻复核未提示高事件风险；建议优先人工复核。"
    if diagnostic in CLEAN_DIAGNOSTICS and assessment != "adverse" and event_risk in LOW_EVENT_RISK:
        return "priority_manual_review", 70, "SMC结构较干净且新闻复核未提示高事件风险；可优先人工复核但需确认催化强度。"
    return "cautious_observation", 45, "SMC入选且未被风险排除，但诊断、事件风险或AI结论不够强；建议谨慎观察。"


def _sort_key(row: Mapping[str, Any]) -> tuple[int, int, int, float, int]:
    bucket_rank = {name: index for index, (name, _) in enumerate(BUCKET_ORDER)}[str(row["analysis_bucket"])]
    event_rank = {"low": 0, "medium": 1, "unknown": 2, "high": 3, "": 2}.get(str(row.get("event_risk") or ""), 2)
    return (
        bucket_rank,
        -_safe_int(row.get("analysis_score")),
        event_rank,
        -_safe_float(row.get("amount_cny")),
        _safe_int(row.get("smc_order")),
    )


def build_post_smc_recommendation_rows(
    candidates: Sequence[Mapping[str, Any]],
    reviews: Sequence[Mapping[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    reviews_by_code = {str(row.get("code")): row for row in reviews or []}
    source_mode = "news_ai_merged" if reviews is not None else "smc_only"
    rows: list[dict[str, Any]] = []
    for smc_order, candidate in enumerate(candidates, start=1):
        code = str(candidate.get("code") or "")
        review = reviews_by_code.get(code)
        if review is None:
            bucket, score, reason = _classify_smc_only(candidate)
        else:
            bucket, score, reason = _classify_with_news(candidate, review)
        risk_warnings = "|".join(_as_list(candidate.get("risk_warnings")))
        row = {
            "analysis_order": 0,
            "analysis_bucket": bucket,
            "analysis_label": BUCKET_LABELS[bucket],
            "source_mode": source_mode,
            "code": code,
            "signal_date": str(candidate.get("signal_date") or ""),
            "smc_order": smc_order,
            "start_diagnostic_label": str(candidate.get("start_diagnostic_label") or "未分类"),
            "start_diagnostic_type": str(candidate.get("start_diagnostic_type") or "unclassified_start_diagnostic"),
            "risk_warning_count": _safe_int(candidate.get("risk_warning_count")),
            "risk_warnings": risk_warnings,
            "amount_cny": _safe_float(candidate.get("amount_cny")),
            "turn_pct": _safe_float(candidate.get("turn_pct")),
            "range_position_20d_pct": _safe_float(candidate.get("range_position_20d_pct")),
            "range_position_60d_pct": _safe_float(candidate.get("range_position_60d_pct")),
            "prior_return_20d_pct": _safe_float(candidate.get("prior_return_20d_pct")),
            "volume_ratio_20": _safe_float(candidate.get("volume_ratio_20")),
            "review_state": "" if review is None else str(review.get("review_state") or ""),
            "assessment": "" if review is None else str(review.get("assessment") or ""),
            "confidence": "" if review is None else _safe_float(review.get("confidence")),
            "event_risk": "" if review is None else str(review.get("event_risk") or "unknown"),
            "catalyst_quality": "" if review is None else str(review.get("catalyst_quality") or ""),
            "analysis_score": score,
            "analysis_reason": reason,
            "boundary_note": BOUNDARY_NOTE,
        }
        rows.append(row)
    rows.sort(key=_sort_key)
    for analysis_order, row in enumerate(rows, start=1):
        row["analysis_order"] = analysis_order
    return rows


def write_post_smc_recommendation_csv(selection_run: Path, news_run: Path | None = None) -> tuple[Path, list[dict[str, Any]]]:
    candidates, candidates_sha = load_selection_candidates(selection_run)
    reviews = load_news_reviews(news_run, candidates_sha) if news_run is not None else None
    rows = build_post_smc_recommendation_rows(candidates, reviews)
    output_path = selection_run / "post_smc_recommendation_analysis.csv"
    temporary = selection_run / ".post_smc_recommendation_analysis.csv.tmp"
    with temporary.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=CSV_FIELDNAMES)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    os.replace(temporary, output_path)
    return output_path, rows


def format_post_smc_recommendation(rows: Sequence[Mapping[str, Any]], *, top: int | None = None) -> str:
    lines = ["", "SMC 后人工复核建议分析（只读，不改变原SMC/News口径）"]
    display_rows = list(rows if top is None else rows[:top])
    if not rows:
        lines.extend([
            "一、优先人工复核建议（0）",
            "二、谨慎观察建议（0）",
            "三、风险暂缓建议（0）",
            f"说明：{BOUNDARY_NOTE}",
        ])
        return "\n".join(lines)
    for bucket, title in BUCKET_ORDER:
        bucket_total = sum(1 for row in rows if row.get("analysis_bucket") == bucket)
        bucket_rows = [row for row in display_rows if row.get("analysis_bucket") == bucket]
        lines.append(f"{title}（展示 {len(bucket_rows)}/{bucket_total}）")
        if not bucket_rows:
            lines.append("  无")
            continue
        for row in bucket_rows:
            warnings = str(row.get("risk_warnings") or "none")
            ai = ""
            if row.get("source_mode") == "news_ai_merged":
                ai = f" AI={row.get('review_state') or '-'} / {row.get('assessment') or '-'} / 事件风险={row.get('event_risk') or '-'}"
            lines.append(
                f"  {int(row['analysis_order']):>2}. {row.get('code')} "
                f"SMC#{row.get('smc_order')} {row.get('start_diagnostic_label')} "
                f"建议={row.get('analysis_label')} 分={row.get('analysis_score')} "
                f"成交额={_safe_float(row.get('amount_cny')) / 100_000_000:.2f}亿 "
                f"风险={warnings}{ai}"
            )
            lines.append(f"      理由：{row.get('analysis_reason')}")
    lines.append(f"说明：{BOUNDARY_NOTE}")
    return "\n".join(lines)
