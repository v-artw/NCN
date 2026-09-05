#!/usr/bin/env python3
"""Compare local_finance models with bounded JSON-only NCN review prompts."""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from ashare_edge_scout.ai_providers import (  # noqa: E402
    AIProviderError,
    AIRequestError,
    OpenAICompatibleClient,
    load_ai_provider_config,
)
from ashare_edge_scout.mkf_ai_review import parse_ai_response  # noqa: E402

DEFAULT_MODELS = (
    "Ornith-1.5-35B-A3B-oQ6e-mtp",
    "Ornith-1.5-35B-A3B-oQ4e-mtp",
    "Ornith-1.0-35B-4bit",
    "Qwen3.8-27B-oQ4e-mtp",
)
FORBIDDEN_EXECUTION_PATTERN = (
    "AUTO_ORDER|AUTO_TRADE|AUTO_REBALANCE|BROKER_ORDER|BROKER_SESSION|BROKER_CONNECTIVITY|"
    "REAL_MONEY_TRADE|REAL_MONEY_ORDER|REAL_MONEY_PNL|LIVE_TRADE|LIVE_ORDER|FILLED_ORDER|"
    "GUARANTEED_RETURN|GUARANTEED_WIN_RATE|LEVERAGE|"
    "自动下单|自动交易|自动调仓|券商下单|连接券商|已连接券商|真实下单|实盘下单|真实成交|"
    "保证收益|保证胜率|杠杆|真实P&L|实盘P&L|真实盈亏|实盘盈亏"
)
NEGATED_EXECUTION_PREFIXES = (
    "非", "不是", "不作为", "不会", "不得", "不能", "不可", "禁止", "无", "没有", "未", "并非",
    "not ", "non-", "without ", "no ", "never ",
)

SYSTEM_PROMPT = """你是NCN A股MKF只读人工复核模型。只能基于给定MKF/OHLCV上下文做研究排序证据整理。
本系统未对接实盘，允许输出买入观察、卖出风险、持有观察、等待确认、参考目标区间、参考止盈止损和风险失效位等人工研判建议。
禁止输出或暗示系统会自动下单、自动交易、自动调仓、连接券商、真实成交、保证收益、保证胜率、真实P&L或杠杆执行。所有建议都必须是人工复核参考。
仅输出JSON对象，字段为review_state(priority_research|standard_research|risk_attention|insufficient_evidence)、confidence(0到1)、research_summary、technical_observations(字符串数组)、risk_flags(字符串数组)、committee(对象)、committee_disagreement_flags(字符串数组)。"""

USER_PROMPT = """候选：sh.600000，信号日2026-09-04，post_cross_lag=1。
MKF快照：momentum=31.2，inter=24.8，near=33.5，红蓝线刚从20下方向上修复，当前仍低于80。
OHLCV上下文：收盘价12.34，今日振幅3.1%，candle_close_location=0.72，candle_upper_shadow_pct=0.18，candle_long_upper_shadow_risk=false，candle_volume_ratio_20=1.42，candle_volume_confirm=true，recent_close_return_5d_pct=6.8，recent_close_return_10d_pct=13.5，candle_box_breakout=true，candle_confirm_score=8.5。
新闻上下文：暂无新闻数据；fatal_risks=[]；attn_risks=[]。
请输出只读人工复核JSON。"""


@dataclass(frozen=True)
class ModelResult:
    model: str
    ok: bool
    elapsed_seconds: float
    review_state: str = ""
    confidence: float | None = None
    json_valid: bool = False
    parsed_by_project: bool = False
    forbidden_term_count: int = 0
    observation_count: int = 0
    risk_flag_count: int = 0
    summary_chars: int = 0
    error: str = ""

    def score(self) -> tuple[int, float, int, int, float]:
        if not self.ok:
            return (0, 0.0, 0, 0, -self.elapsed_seconds)
        state_score = {
            "priority_research": 4,
            "standard_research": 3,
            "insufficient_evidence": 2,
            "risk_attention": 1,
        }.get(self.review_state, 0)
        return (
            int(self.json_valid) + int(self.parsed_by_project) + int(self.forbidden_term_count == 0),
            float(self.confidence or 0.0),
            state_score,
            min(self.observation_count, 4),
            -self.elapsed_seconds,
        )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare TS local_finance model JSON smoke quality")
    parser.add_argument("--config", type=Path, default=PROJECT_ROOT / "yaml" / "ai_providers.yaml")
    parser.add_argument("--provider", default="local_finance")
    parser.add_argument("--models", nargs="*", default=list(DEFAULT_MODELS))
    parser.add_argument("--timeout-seconds", type=float, default=90.0)
    parser.add_argument("--max-tokens", type=int, default=2048)
    parser.add_argument("--delay-between-models-seconds", type=float, default=0.0)
    parser.add_argument("--output", type=Path)
    return parser.parse_args(argv)


def build_client(config_path: Path, provider: str, model: str, timeout_seconds: float) -> OpenAICompatibleClient:
    config = load_ai_provider_config(config_path, provider_override=provider)
    provider_config = dict(config.providers[provider])
    key_file = str(provider_config.get("key_file", ""))
    api_key = Path(key_file).read_text(encoding="utf-8").strip() if key_file else ""
    if not api_key:
        raise AIProviderError(f"provider {provider!r} has no readable key_file")
    return OpenAICompatibleClient(
        provider=provider,
        base_url=str(provider_config["base_url"]),
        api_key=api_key,
        model=model,
        timeout_seconds=timeout_seconds,
        temperature=config.temperature,
        seed=config.seed,
        response_format=config.response_format,
        extra_options=provider_config.get("extra_options") or {},
    )


def extract_content(response: Mapping[str, Any]) -> str:
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ValueError("response has no choices")
    message = choices[0].get("message") if isinstance(choices[0], Mapping) else None
    if not isinstance(message, Mapping):
        raise ValueError("response choice has no message")
    return str(message.get("content") or "").strip()


def forbidden_execution_count(text: str) -> int:
    import re

    count = 0
    for match in re.finditer(FORBIDDEN_EXECUTION_PATTERN, text, flags=re.IGNORECASE):
        prefix = text[max(0, match.start() - 8):match.start()].lower()
        if not any(marker in prefix for marker in NEGATED_EXECUTION_PREFIXES):
            count += 1
    return count


def evaluate_model(args: argparse.Namespace, model: str) -> ModelResult:
    started = time.monotonic()
    try:
        client = build_client(args.config, args.provider, model, args.timeout_seconds)
        response, resolved_model = client.chat_json(
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": USER_PROMPT},
            ],
            user_agent="NCN-Local-Finance-Model-Eval/1.0",
            extra_payload={"max_tokens": args.max_tokens},
        )
        elapsed = time.monotonic() - started
        content = extract_content(response)
        forbidden_count = forbidden_execution_count(content)
        parsed = parse_ai_response(content)
        return ModelResult(
            model=resolved_model,
            ok=True,
            elapsed_seconds=elapsed,
            review_state=str(parsed["review_state"]),
            confidence=float(parsed["confidence"]),
            json_valid=True,
            parsed_by_project=True,
            forbidden_term_count=forbidden_count,
            observation_count=len(parsed.get("technical_observations") or []),
            risk_flag_count=len(parsed.get("risk_flags") or []),
            summary_chars=len(str(parsed.get("research_summary") or "")),
        )
    except (AIProviderError, AIRequestError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        return ModelResult(
            model=model,
            ok=False,
            elapsed_seconds=time.monotonic() - started,
            error=str(exc),
        )


def result_row(result: ModelResult) -> dict[str, Any]:
    return {
        "model": result.model,
        "ok": result.ok,
        "elapsed_seconds": round(result.elapsed_seconds, 3),
        "review_state": result.review_state,
        "confidence": result.confidence,
        "json_valid": result.json_valid,
        "parsed_by_project": result.parsed_by_project,
        "forbidden_term_count": result.forbidden_term_count,
        "observation_count": result.observation_count,
        "risk_flag_count": result.risk_flag_count,
        "summary_chars": result.summary_chars,
        "error": result.error,
    }


def write_payload(args: argparse.Namespace, results: list[ModelResult]) -> dict[str, Any]:
    ranked = sorted(results, key=lambda item: item.score(), reverse=True)
    payload = {
        "status": "success" if any(result.ok for result in results) else "failed",
        "provider": args.provider,
        "config": str(args.config),
        "prompt_contract": "ncn_mkf_ai_review_json_smoke_v1",
        "delay_between_models_seconds": args.delay_between_models_seconds,
        "recommended_model": ranked[0].model if ranked and ranked[0].ok else "",
        "results": [result_row(result) for result in ranked],
    }
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    return payload


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    results: list[ModelResult] = []
    for index, model in enumerate(args.models):
        if index > 0 and args.delay_between_models_seconds > 0:
            time.sleep(args.delay_between_models_seconds)
        results.append(evaluate_model(args, model))
        write_payload(args, results)
    payload = write_payload(args, results)
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if payload["status"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
