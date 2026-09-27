from __future__ import annotations

import csv
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping, Sequence

CSV_FIELDNAMES = [
    "human_review_order",
    "group",
    "group_label",
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
    "human_review_reason",
    "boundary_note",
]

GROUP_LABELS = {
    "priority_human_review": "优先人工复核",
    "cautious_review": "谨慎复核",
    "temporary_skip_or_risk_excluded": "暂时跳过/风险排除",
}
GROUP_ORDER = (
    ("priority_human_review", "一、优先人工复核"),
    ("cautious_review", "二、谨慎复核"),
    ("temporary_skip_or_risk_excluded", "三、暂时跳过/风险排除"),
)
BOUNDARY_NOTE = "只读人工复核摘要；不改变SMC入选、排序、阈值或News AI口径；不构成买卖建议。"
CLEAN_DIAGNOSTICS = {"base_breakout_start", "pullback_reacceleration"}
LOW_EVENT_RISK = {"low", "medium"}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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


def load_selection_candidates(selection_run: Path) -> tuple[list[dict[str, Any]], str]:
    candidates_path = selection_run / "candidates.json"
    manifest_path = selection_run / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected = (((manifest.get("files") or {}).get("candidates.json") or {}).get("sha256"))
    actual = _sha256(candidates_path)
    if expected != actual:
        raise ValueError("selection candidates.json hash does not match manifest")
    candidates = json.loads(candidates_path.read_text(encoding="utf-8"))
    if not isinstance(candidates, list) or any(not isinstance(row, dict) for row in candidates):
        raise ValueError("selection candidates.json must be a list of objects")
    return candidates, actual


def load_news_reviews(news_run: Path, source_candidates_sha256: str) -> list[dict[str, Any]]:
    reviews_path = news_run / "reviews.json"
    summary_path = news_run / "summary.json"
    manifest_path = news_run / "manifest.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if summary.get("source_candidates_sha256") != source_candidates_sha256:
        raise ValueError("news review summary is not bound to this selection run")
    if manifest.get("source_candidates_sha256") != source_candidates_sha256:
        raise ValueError("news review manifest is not bound to this selection run")
    expected = (((manifest.get("files") or {}).get("reviews.json") or {}).get("sha256"))
    actual = _sha256(reviews_path)
    if expected != actual:
        raise ValueError("news reviews.json hash does not match manifest")
    reviews = json.loads(reviews_path.read_text(encoding="utf-8"))
    if not isinstance(reviews, list) or any(not isinstance(row, dict) for row in reviews):
        raise ValueError("news reviews.json must be a list of objects")
    return reviews


def _classify_smc_only(candidate: Mapping[str, Any]) -> tuple[str, str]:
    risk_count = _safe_int(candidate.get("risk_warning_count"))
    diagnostic = str(candidate.get("start_diagnostic_type") or "unclassified_start_diagnostic")
    if risk_count > 0:
        return "temporary_skip_or_risk_excluded", "存在SMC风险警告，先列入暂时跳过/风险排除；不改变SMC原始入选。"
    if diagnostic == "high_position_chase":
        return "temporary_skip_or_risk_excluded", "诊断为高位追涨，先列入暂时跳过/风险排除；不改变SMC原始入选。"
    if diagnostic in CLEAN_DIAGNOSTICS:
        return "priority_human_review", "干净启动/回踩再加速且无SMC风险警告；优先人工复核，不改变SMC排序。"
    return "cautious_review", "SMC入选但启动诊断未分类或证据不够干净；谨慎复核。"


def _classify_with_news(candidate: Mapping[str, Any], review: Mapping[str, Any]) -> tuple[str, str]:
    risk_count = _safe_int(candidate.get("risk_warning_count"))
    diagnostic = str(candidate.get("start_diagnostic_type") or "unclassified_start_diagnostic")
    review_state = str(review.get("review_state") or "")
    assessment = str(review.get("assessment") or "")
    event_risk = str(review.get("event_risk") or "unknown")
    if review_state == "risk_excluded":
        return "temporary_skip_or_risk_excluded", "News AI标记风险暂缓，先排除出优先复核；不改变SMC原始入选。"
    if risk_count > 0:
        return "temporary_skip_or_risk_excluded", "存在SMC风险警告，即使有AI复核也先列入风险排除。"
    if diagnostic == "high_position_chase":
        return "cautious_review", "SMC入选但诊断为高位追涨；有AI信息也仅谨慎复核。"
    if diagnostic in CLEAN_DIAGNOSTICS and assessment != "adverse" and event_risk in LOW_EVENT_RISK:
        return "priority_human_review", "干净启动/回踩再加速、无SMC风险警告，AI未提示高事件风险；优先人工复核。"
    return "cautious_review", "SMC入选且AI未风险排除，但诊断、事件风险或AI结论不够强；谨慎复核。"


def _review_sort_key(row: Mapping[str, Any]) -> tuple[int, int, int, float, int]:
    group_rank = {name: index for index, (name, _) in enumerate(GROUP_ORDER)}[str(row["group"])]
    assessment_rank = {"favorable": 0, "neutral": 1, "insufficient": 2, "adverse": 3, "": 1}.get(str(row.get("assessment") or ""), 2)
    event_rank = {"low": 0, "medium": 1, "unknown": 2, "high": 3, "": 2}.get(str(row.get("event_risk") or ""), 2)
    return (group_rank, assessment_rank, event_rank, -_safe_float(row.get("amount_cny")), _safe_int(row.get("smc_order")))


def build_human_review_summary_rows(
    candidates: Sequence[Mapping[str, Any]],
    reviews: Sequence[Mapping[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    reviews_by_code = {str(row.get("code")): row for row in reviews or []}
    source_mode = "news_ai_merged" if reviews is not None else "smc_only_degraded"
    rows: list[dict[str, Any]] = []
    for smc_order, candidate in enumerate(candidates, start=1):
        code = str(candidate.get("code") or "")
        review = reviews_by_code.get(code)
        if review is not None:
            group, reason = _classify_with_news(candidate, review)
        else:
            group, reason = _classify_smc_only(candidate)
        risk_warnings = "|".join(_as_list(candidate.get("risk_warnings")))
        row = {
            "human_review_order": 0,
            "group": group,
            "group_label": GROUP_LABELS[group],
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
            "human_review_reason": reason,
            "boundary_note": BOUNDARY_NOTE,
        }
        rows.append(row)
    rows.sort(key=_review_sort_key)
    for human_review_order, row in enumerate(rows, start=1):
        row["human_review_order"] = human_review_order
    return rows


def write_human_review_summary_csv(selection_run: Path, news_run: Path | None = None) -> tuple[Path, list[dict[str, Any]]]:
    candidates, candidates_sha = load_selection_candidates(selection_run)
    reviews = load_news_reviews(news_run, candidates_sha) if news_run is not None else None
    rows = build_human_review_summary_rows(candidates, reviews)
    output_path = selection_run / "human_review_summary.csv"
    temporary = selection_run / ".human_review_summary.csv.tmp"
    with temporary.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=CSV_FIELDNAMES)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    os.replace(temporary, output_path)
    return output_path, rows


def format_human_review_summary(rows: Sequence[Mapping[str, Any]]) -> str:
    lines = ["", "SMC 派生人工复核分组（只读，不改变原SMC/News口径）"]
    if not rows:
        lines.extend([
            "一、优先人工复核（0）",
            "二、谨慎复核（0）",
            "三、暂时跳过/风险排除（0）",
            f"说明：{BOUNDARY_NOTE}",
        ])
        return "\n".join(lines)
    for group, title in GROUP_ORDER:
        group_rows = [row for row in rows if row.get("group") == group]
        lines.append(f"{title}（{len(group_rows)}）")
        if not group_rows:
            lines.append("  无")
            continue
        for row in group_rows:
            warnings = str(row.get("risk_warnings") or "none")
            ai = ""
            if row.get("source_mode") == "news_ai_merged":
                ai = f" AI={row.get('review_state') or '-'} / {row.get('assessment') or '-'} / 事件风险={row.get('event_risk') or '-'}"
            lines.append(
                f"  {int(row['human_review_order']):>2}. {row.get('code')} "
                f"SMC#{row.get('smc_order')} {row.get('start_diagnostic_label')} "
                f"成交额={_safe_float(row.get('amount_cny')) / 100_000_000:.2f}亿 "
                f"风险={warnings}{ai}"
            )
            lines.append(f"      理由：{row.get('human_review_reason')}")
    lines.append(f"说明：{BOUNDARY_NOTE}")
    return "\n".join(lines)
