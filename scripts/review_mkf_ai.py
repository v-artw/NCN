#!/usr/bin/env python3
"""CLI for optional read-only AI review of immutable MKF candidate runs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from ashare_edge_scout.mkf_ai_review import run_mkf_ai_review

STATE_LABELS = {
    "priority_research": "优先研究",
    "standard_research": "标准研究",
    "risk_attention": "风险关注",
    "insufficient_evidence": "证据不足",
    "ai_unavailable": "AI未评分",
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="NCN optional MKF AI committee read-only review")
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
    print("MKF AI 委员会只读复核：开始读取候选源实验结果并生成研究分层...", flush=True)

    def _fmt_float(value: object, digits: int = 2) -> str:
        try:
            return f"{float(value):.{digits}f}"
        except (TypeError, ValueError):
            return "NA"

    def progress(index: int, total: int, code: str, stage: str, detail: dict[str, object] | None = None) -> None:
        detail = detail or {}
        labels = {
            "context": "构建本地蜡烛图/OHLCV上下文",
            "news": "抓取/刷新CNstock兼容新闻上下文",
            "ai": "调用AI委员会研究分层",
            "priority_research": "完成：优先研究",
            "standard_research": "完成：标准研究",
            "risk_attention": "完成：风险关注",
            "insufficient_evidence": "完成：证据不足",
            "ai_unavailable": "完成：AI不可用",
        }
        base = (
            f"MKF AI复核进度：{index}/{total} {code} - {labels.get(stage, stage)}"
            f" | close={_fmt_float(detail.get('close'))}"
            f" amount亿={_fmt_float(float(detail.get('amount_cny') or 0.0) / 100000000.0)}"
            f" red={_fmt_float(detail.get('mkf_momentum'))}"
            f" blue={_fmt_float(detail.get('mkf_near'))}"
        )
        if detail.get("technical_context_status"):
            base += f" ctx={detail['technical_context_status']}"
        if detail.get("news_context_status"):
            base += f" news={detail['news_context_status']}"
        if detail.get("news_cache_status"):
            base += f" cache={detail['news_cache_status']}"
        if detail.get("fatal_news_risk_count") is not None:
            base += f" fatal={detail['fatal_news_risk_count']}"
        if detail.get("attention_news_risk_count") is not None:
            base += f" attention={detail['attention_news_risk_count']}"
        if detail.get("candle_confirm_score") is not None:
            base += f" candle={_fmt_float(detail.get('candle_confirm_score'))}"
        patterns = list(detail.get("candlestick_patterns") or [])
        if patterns:
            base += " patterns=" + "|".join(str(item) for item in patterns[:2])
        if stage in STATE_LABELS:
            base += f" | state={STATE_LABELS[stage]} conf={_fmt_float(detail.get('confidence'))} local={_fmt_float(detail.get('local_score'))}"
            risks = detail.get("risk_flags") or []
            if risks:
                base += " risk=" + "；".join(str(item) for item in list(risks)[:2])
            if detail.get("error"):
                base += f" error={detail['error']}"
        print(base, flush=True)

    try:
        result = run_mkf_ai_review(
            selection_root=args.selection_root,
            selection_run=args.selection_run,
            output_root=args.output_root,
            config_path=args.config,
            run_id=args.run_id,
            data_root=args.data_root,
            progress=progress,
        )
    except Exception as exc:
        print(f"mkf_ai_review_failed: {exc}", file=sys.stderr)
        return 2
    rows = json.loads(result.reviews_path.read_text(encoding="utf-8"))
    summary = json.loads(result.summary_path.read_text(encoding="utf-8"))
    print(f"status={summary['status']}")
    print(f"priority_research_count={result.priority_research_count}")
    print(f"risk_attention_count={result.risk_attention_count}")
    news_summary = summary.get("news_context") or {}
    print(f"run_directory={result.run_directory}")
    print(f"timestamped_csv={result.reviews_csv_path}")
    print(f"news_contexts={result.news_contexts_path}")
    print(f"news_cache_dir={news_summary.get('storage_dir') or ''}")
    print(f"news_cache_status_counts={json.dumps(news_summary.get('cache_status_counts') or {}, ensure_ascii=False, sort_keys=True)}")
    print("\nMKF AI 委员会研究分层（仅展示AI有效评分；只读研究，未经胜率验证）")
    scored_rows = [row for row in rows if row.get("review_state") != "ai_unavailable"]
    unavailable_rows = [row for row in rows if row.get("review_state") == "ai_unavailable"]
    for index, row in enumerate(scored_rows[: args.top], start=1):
        label = STATE_LABELS.get(str(row.get("review_state")), str(row.get("review_state")))
        print(
            f"{index:>2}. {row.get('code')}  {label}  置信度={float(row.get('confidence') or 0.0):.2f} "
            f"本地分={float(row.get('local_score') or 0.0):.2f}"
        )
        print(f"    结论：{row.get('research_summary') or '无'}")
        risks = row.get("risk_flags") or []
        if risks:
            print(f"    风险：{'；'.join(str(item) for item in risks[:4])}")
    if not scored_rows:
        print("无AI有效评分结果。")
    if unavailable_rows:
        codes = ", ".join(str(row.get("code")) for row in unavailable_rows[:20])
        suffix = "" if len(unavailable_rows) <= 20 else f" 等{len(unavailable_rows)}只"
        print(f"\nAI未评分清单（不参与上方AI排序）：{codes}{suffix}")
    print("\n说明：MKF AI 复核是独立候选源实验的只读人工研究分层；不是买入、卖出、成交、收益或个性化操作建议。")
    if summary["status"] in {"partial", "ai_failed"}:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
