#!/usr/bin/env python3
"""CLI for experimental news/AI review of an immutable SMC selection."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
import textwrap

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from ashare_edge_scout.human_review_summary import format_human_review_summary, write_human_review_summary_csv
from ashare_edge_scout.news_ai_review import run_news_ai_review


STATE_LABELS = {
    "priority_review": "优先观察",
    "standard_review": "谨慎观察",
    "risk_excluded": "风险暂缓",
    "insufficient_evidence": "证据不足",
    "ai_unavailable": "AI不可用",
}
ASSESSMENT_LABELS = {
    "favorable": "偏正面",
    "neutral": "中性",
    "adverse": "偏负面",
    "insufficient": "证据不足",
}
GROUP_ORDER = (
    ("priority_review", "一、优先观察"),
    ("standard_review", "二、谨慎观察"),
    ("risk_excluded", "三、风险暂缓"),
    ("insufficient_evidence", "四、证据不足"),
    ("ai_unavailable", "五、AI不可用"),
)


def _compact_text(value: object, limit: int = 220) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def _first_matching(items: list[str], keywords: tuple[str, ...], fallback_index: int = 0) -> str:
    for item in items:
        if any(keyword in item for keyword in keywords):
            return item
    if items:
        return items[min(fallback_index, len(items) - 1)]
    return "无"


def _format_wrapped(prefix: str, text: str, width: int = 100) -> list[str]:
    wrapped = textwrap.wrap(text, width=width, break_long_words=False, break_on_hyphens=False) or ["无"]
    lines = [f"    {prefix}{wrapped[0]}"]
    indent = "    " + " " * len(prefix)
    lines.extend(f"{indent}{line}" for line in wrapped[1:])
    return lines


def _format_review_card(index: int, row: dict[str, object]) -> str:
    assessment = ASSESSMENT_LABELS.get(str(row.get("assessment")), str(row.get("assessment")))
    state = STATE_LABELS.get(str(row.get("review_state")), str(row.get("review_state")))
    confidence = float(row.get("confidence") or 0.0)
    event_risk = str(row.get("event_risk") or "unknown")
    evidence = [str(item) for item in row.get("evidence") or []]
    risk_flags = [str(item) for item in row.get("risk_flags") or []]
    technical = _compact_text(_first_matching(evidence, ("K线", "信号", "signal", "candle", "影线", "实体", "量")), 180)
    news = _compact_text(_first_matching(evidence, ("公告", "新闻", "中报", "解禁", "减值", "业绩", "质押"), 1), 180)
    risk = _compact_text("；".join(risk_flags[:4]) if risk_flags else "无明显新增风险词", 180)
    summary = _compact_text(row.get("summary"), 240)
    lines = [
        f"{index:>2}. {row.get('code')}  {state} / {assessment}  置信度={confidence:.2f}  事件风险={event_risk}",
        *_format_wrapped("技术：", technical),
        *_format_wrapped("新闻：", news),
        *_format_wrapped("风险：", risk),
        *_format_wrapped("结论：", summary),
    ]
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="NCN experimental SMC news/AI second review")
    parser.add_argument("--selection-root", type=Path, required=True)
    parser.add_argument("--selection-run", type=Path)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--data-root", type=Path)
    parser.add_argument("--run-id")
    parser.add_argument("--top", type=int, default=20)
    args = parser.parse_args(argv)
    if args.top < 1:
        parser.error("--top must be at least 1")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    print("新闻 + 日K线 AI 二次复核：开始读取候选、新闻缓存和本地K线...", flush=True)

    def progress(index: int, total: int, code: str, stage: str) -> None:
        labels = {
            "fetch": "获取新闻/公告并构建K线摘要",
            "ai": "调用AI综合分析",
            "priority_review": "完成：优先观察",
            "standard_review": "完成：谨慎观察",
            "risk_excluded": "完成：风险暂缓",
            "insufficient_evidence": "完成：证据不足",
            "ai_unavailable": "完成：AI不可用",
        }
        print(f"AI复核进度：{index}/{total} {code} - {labels.get(stage, stage)}", flush=True)

    try:
        result = run_news_ai_review(
            selection_root=args.selection_root,
            selection_run=args.selection_run,
            output_root=args.output_root,
            config_path=args.config,
            run_id=args.run_id,
            data_root=args.data_root,
            progress=progress,
        )
    except Exception as exc:
        print(f"news_ai_review_failed: {exc}", file=sys.stderr)
        return 2
    rows = json.loads(result.reviews_path.read_text(encoding="utf-8"))
    summary = json.loads(result.summary_path.read_text(encoding="utf-8"))
    human_summary_path, human_summary_rows = write_human_review_summary_csv(
        Path(summary["source_selection_run"]),
        result.run_directory,
    )
    print(f"status={summary['status']}")
    print(f"priority_review_count={result.priority_review_count}")
    print(f"risk_excluded_count={result.risk_excluded_count}")
    print(f"run_directory={result.run_directory}")
    print(f"timestamped_csv={result.reviews_csv_path}")
    print(f"ai_committee_csv={result.ai_committee_csv_path}")
    print(f"ai_committee_latest_csv={result.ai_committee_latest_csv_path}")
    print(f"human_review_summary_csv={human_summary_path}")
    print("\n新闻 + 日K线 AI 二次复核（参考日本蜡烛图技术，未经胜率验证）")
    shown = rows[: args.top]
    printed = 0
    for state, title in GROUP_ORDER:
        group = [row for row in shown if row.get("review_state") == state]
        if not group:
            continue
        print(f"\n{title}")
        for row in group:
            printed += 1
            print(_format_review_card(printed, row))
    if not printed:
        print("无可展示复核结果。")
    print(format_human_review_summary(human_summary_rows))
    print("\n说明：以上是只读人工复核参考，不是买入、卖出、成交、收益或个性化操作建议；AI 状态未经胜率验证。")
    if summary["status"] in {"partial", "technical_only_ai_failed"}:
        errors = sorted(set(summary["ai_error_counts"].values()))
        reason = "技术上下文 AI 调用全部失败" if summary["status"] == "technical_only_ai_failed" else "AI 调用全部失败"
        print(f"{reason}：{'; '.join(errors)}", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
