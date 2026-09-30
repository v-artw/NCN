#!/usr/bin/env python3
"""Audit one frozen MKF input against Qwen3.8 Flash without persisting raw content."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from ashare_edge_scout.ai_providers import (  # noqa: E402
    AIRequestError,
    OpenAICompatibleClient,
    build_ai_client,
    load_ai_provider_config,
)
from ashare_edge_scout.mkf_ai_review import (  # noqa: E402
    FORBIDDEN_EXECUTION_PATTERN,
    load_mkf_ai_config,
    parse_ai_response,
)

DEFAULT_SOURCE_RUN = PROJECT_ROOT / "output/edge_scout/mkf_ai_reviews/mkf-ai-review-20260930_155435"
DEFAULT_SELECTION_RUN = PROJECT_ROOT / "output/edge_scout/mkf_candidate_selections/mkf-select-20260930_093606"
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "output/edge_scout/mkf_ai_reviews"
COMMITTEE_ROLES = [
    "technical_analyst",
    "sentiment_analyst",
    "fundamental_analyst",
    "bullish_researcher",
    "bearish_researcher",
    "chief_strategist",
    "risk_manager",
]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Send one frozen public MKF context to Qwen3.8 Flash and write redacted audit metadata."
    )
    parser.add_argument("--code", default="sh.601666")
    parser.add_argument("--source-run", type=Path, default=DEFAULT_SOURCE_RUN)
    parser.add_argument("--selection-run", type=Path, default=DEFAULT_SELECTION_RUN)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--timeout-seconds", type=float, default=90.0)
    return parser.parse_args(argv)


def _load_candidate(selection_run: Path, code: str) -> dict[str, Any]:
    records = json.loads((selection_run / "candidates.json").read_text(encoding="utf-8"))
    candidates = records.get("candidates", []) if isinstance(records, dict) else records
    return next(item for item in candidates if item.get("code") == code)


def _load_context(source_run: Path, filename: str, key: str, code: str) -> dict[str, Any]:
    records = json.loads((source_run / filename).read_text(encoding="utf-8"))
    return next(item[key] for item in records if item.get("code") == code)


def _response_shape(content: str) -> dict[str, Any]:
    try:
        normalized = re.sub(r"^```(?:json)?\s*", "", content, flags=re.IGNORECASE)
        normalized = re.sub(r"\s*```$", "", normalized)
        start, end = normalized.find("{"), normalized.rfind("}")
        if start < 0 or end <= start:
            return {"json_object_found": False}
        parsed = json.loads(normalized[start : end + 1])
        if not isinstance(parsed, dict):
            return {"json_object_found": False, "parsed_type": type(parsed).__name__}
        committee = parsed.get("committee")
        return {
            "top_level_keys": sorted(map(str, parsed)),
            "review_state": parsed.get("review_state"),
            "confidence": parsed.get("confidence"),
            "committee_type": type(committee).__name__,
            "committee_roles_present": sorted(committee) if isinstance(committee, dict) else [],
        }
    except Exception as exc:
        return {"raw_json_parse_error": f"{type(exc).__name__}: {exc}"}


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.timeout_seconds <= 0:
        raise ValueError("--timeout-seconds must be positive")

    candidate = _load_candidate(args.selection_run, args.code)
    technical = _load_context(args.source_run, "technical_contexts.json", "technical_context", args.code)
    news = _load_context(args.source_run, "news_contexts.json", "news_context", args.code)
    review_config = load_mkf_ai_config(
        PROJECT_ROOT / "yaml/mkf_ai_review_aliweek_qwen38_flash.yaml"
    )
    provider_config = load_ai_provider_config(
        PROJECT_ROOT / "yaml/ai_providers.yaml", provider_override="aliweek"
    )
    base_client = build_ai_client(provider_config)
    if base_client is None:
        raise RuntimeError("Aliweek provider is disabled")
    client = OpenAICompatibleClient(
        provider="aliweek",
        base_url=base_client.base_url,
        api_key=base_client.api_key,
        model="qwen3.8-flash",
        timeout_seconds=args.timeout_seconds,
        temperature=base_client.temperature,
        seed=base_client.seed,
        response_format=base_client.response_format,
        extra_options=base_client.extra_options,
    )
    candidate_fields = (
        "code", "signal_date", "cross_date", "post_cross_lag", "research_close", "amount_cny",
        "turn_pct", "mkf_momentum", "mkf_inter", "mkf_near", "mkf_red_cross_up_20",
        "mkf_blue_cross_up_20", "mkf_red_blue_cross_up_20_under_80", "selection_reason",
    )
    payload = {
        "candidate": {key: candidate.get(key) for key in candidate_fields},
        "ncn_technical_context": technical,
        "cnstock_news_context": news,
        "committee_roles": COMMITTEE_ROLES,
        "allowed_review_states": [
            "insufficient_evidence", "priority_research", "risk_attention", "standard_research"
        ],
        "forbidden_execution_claims": [
            "AUTO_ORDER", "AUTO_REBALANCE", "AUTO_TRADE", "BROKER_CONNECTIVITY", "BROKER_ORDER",
            "BROKER_SESSION", "FILLED_ORDER", "GUARANTEED_RETURN", "GUARANTEED_WIN_RATE", "LEVERAGE",
            "LIVE_ORDER", "LIVE_TRADE", "REAL_MONEY_ORDER", "REAL_MONEY_PNL", "REAL_MONEY_TRADE",
        ],
        "boundary": {
            "scanner_selection_is_immutable": True,
            "post_selection_read_only_research_layer": True,
            "do_not_modify_smc_admission_or_ranking": True,
            "do_not_modify_watchlist_or_prospective_archive": True,
            "do_not_use_pmkf_kalman": True,
            "do_not_use_futu_fields": True,
            "not_investment_advice": True,
        },
    }
    started = time.monotonic()
    content = ""
    model = client.model
    request_error = ""
    try:
        response, model = client.chat_json(
            [
                {"role": "system", "content": review_config["prompt"]["system"]},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False, sort_keys=True)},
            ],
            user_agent="NCN-Qwen-Flash-Contract-Audit/1.0",
        )
        content = str(response.get("choices", [{}])[0].get("message", {}).get("content") or "").strip()
        try:
            parse_ai_response(content)
            parse_status, parse_error = "ok", ""
        except Exception as exc:
            parse_status, parse_error = "failed", f"{type(exc).__name__}: {exc}"
    except AIRequestError as exc:
        parse_status, parse_error = "request_failed", ""
        request_error = f"{type(exc).__name__}: {exc}"

    audit = {
        "code": args.code,
        "provider": "aliweek",
        "model": model,
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "source_run": str(args.source_run.resolve()),
        "selection_run": str(args.selection_run.resolve()),
        "input_sha256": hashlib.sha256(
            json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest(),
        "response_char_count": len(content),
        "response_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
        "parse_status": parse_status,
        "parse_error": parse_error,
        "request_error": request_error,
        "forbidden_execution_matches": [match.group(0) for match in FORBIDDEN_EXECUTION_PATTERN.finditer(content)],
        "response_shape": _response_shape(content),
    }
    destination = args.output_root / f"qwen3_8_flash_{args.code.replace('.', '')}_audit_{time.strftime('%Y%m%d_%H%M%S')}"
    destination.mkdir(parents=True)
    audit_path = destination / "audit.json"
    audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"audit_path={audit_path}")
    print(json.dumps(audit, ensure_ascii=False, indent=2))
    return 0 if parse_status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
