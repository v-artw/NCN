#!/usr/bin/env python3
"""Audit bounded local MKF contract replays without persisting source or response text."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from ashare_edge_scout.ai_providers import AIRequestError  # noqa: E402
from ashare_edge_scout.mkf_ai_review import (  # noqa: E402
    build_ai_client,
    build_mkf_ai_messages,
    load_mkf_ai_config,
    load_persisted_mkf_review_inputs,
    parse_ai_response,
)

DEFAULT_SOURCE_RUN = PROJECT_ROOT / "output/edge_scout/mkf_ai_reviews/mkf-ai-review-20260930_162748"
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "output/edge_scout/mkf_ai_reviews"
ALLOWED_CONFIGS = {
    (PROJECT_ROOT / "yaml/mkf_ai_review_local_finance_retest.yaml").resolve(),
    (PROJECT_ROOT / "yaml/mkf_ai_review_local_ornith_retest.yaml").resolve(),
}
MAX_REQUESTS = 3


def _sha256_json(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run bounded local contract audits against immutable MKF inputs.")
    parser.add_argument("--source-run", type=Path, required=True)
    parser.add_argument("--case", action="append", nargs=2, metavar=("COMMITTEE_CONFIG", "CODE"), required=True)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--timeout-seconds", type=float, default=120.0)
    return parser.parse_args(argv)


def _classify_parse_error(exc: Exception) -> str:
    message = str(exc)
    if message == "AI response contains no JSON object":
        return "no_json_object"
    if message == "AI review_state is invalid":
        return "invalid_review_state"
    if message == "AI confidence is outside [0, 1]":
        return "invalid_confidence"
    if type(exc).__name__ == "JSONDecodeError":
        return "invalid_json"
    return "schema_or_parser_value_error"


def _response_shape(content: str) -> dict[str, Any]:
    normalized = content.strip()
    if normalized.startswith("```"):
        normalized = normalized.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    start, end = normalized.find("{"), normalized.rfind("}")
    if start < 0 or end <= start:
        return {"json_object_found": False}
    try:
        parsed = json.loads(normalized[start:end + 1])
    except json.JSONDecodeError:
        return {"json_object_found": True, "json_valid": False}
    if not isinstance(parsed, dict):
        return {"json_object_found": True, "json_valid": True, "parsed_type": type(parsed).__name__}
    committee = parsed.get("committee")
    return {
        "json_object_found": True,
        "json_valid": True,
        "top_level_keys": sorted(map(str, parsed)),
        "review_state_type": type(parsed.get("review_state")).__name__,
        "review_state": parsed.get("review_state") if isinstance(parsed.get("review_state"), str) else None,
        "confidence_type": type(parsed.get("confidence")).__name__,
        "confidence_in_range": isinstance(parsed.get("confidence"), (int, float)) and 0 <= parsed["confidence"] <= 1,
        "committee_type": type(committee).__name__,
        "committee_roles_present": sorted(map(str, committee)) if isinstance(committee, Mapping) else [],
    }


def _validate_cases(raw_cases: list[list[str]], timeout_seconds: float) -> list[tuple[Path, str]]:
    if timeout_seconds <= 0:
        raise ValueError("--timeout-seconds must be positive")
    if len(raw_cases) > MAX_REQUESTS:
        raise ValueError(f"at most {MAX_REQUESTS} audit requests are allowed")
    cases = [(Path(config).expanduser().resolve(), code.strip()) for config, code in raw_cases]
    if len(cases) != len(set(cases)):
        raise ValueError("duplicate audit case")
    if any(config not in ALLOWED_CONFIGS for config, _ in cases):
        raise ValueError("audit config is not an approved local retest committee")
    return cases


def _write_audit(output_root: Path, audit: Mapping[str, Any]) -> Path:
    run_id = f"mkf-frozen-contract-audit-{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
    destination = output_root / run_id
    temporary = output_root / f".{run_id}.tmp"
    if destination.exists() or temporary.exists():
        raise FileExistsError(f"audit destination already exists: {destination}")
    temporary.mkdir(parents=True)
    try:
        path = temporary / "audit.json"
        path.write_text(json.dumps(audit, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        os.replace(temporary, destination)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return destination / "audit.json"


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    cases = _validate_cases(args.case, args.timeout_seconds)
    persisted = load_persisted_mkf_review_inputs(args.source_run)
    candidates = {(str(item.get("code")), str(item.get("signal_date"))): item for item in persisted.candidates}
    records: list[dict[str, Any]] = []

    for config_path, code in cases:
        matches = [(identity, candidate) for identity, candidate in candidates.items() if identity[0] == code]
        if len(matches) != 1:
            raise ValueError(f"requested code is not uniquely present in frozen source: {code}")
        identity, candidate = matches[0]
        context, news_context = persisted.technical_contexts[identity], persisted.news_contexts[identity]
        if context.get("status") != "ok" or not isinstance(news_context.get("news_txt"), str):
            raise ValueError(f"frozen context is not usable for {code}")
        config = load_mkf_ai_config(config_path)
        client = build_ai_client(config)
        if client is None:
            raise ValueError(f"approved audit provider is disabled: {config_path}")
        client.timeout_seconds = args.timeout_seconds
        messages = build_mkf_ai_messages(candidate, context, news_context, config["prompt"]["system"])
        started = time.monotonic()
        content = ""
        finish_reason: str | None = None
        parse_status, parse_category, request_error_type = "request_failed", "transport_failed", None
        model = client.model
        try:
            response, model = client.chat_json(messages, user_agent="NCN-MKF-Frozen-Contract-Audit/1.0")
            choices = response.get("choices", []) if isinstance(response, Mapping) else []
            first = choices[0] if isinstance(choices, list) and choices and isinstance(choices[0], Mapping) else {}
            message = first.get("message") if isinstance(first, Mapping) else {}
            content = str(message.get("content") or "") if isinstance(message, Mapping) else ""
            finish_reason = str(first.get("finish_reason")) if first.get("finish_reason") is not None else None
            try:
                parse_ai_response(content)
                parse_status, parse_category = "ok", "parse_ok"
            except Exception as exc:
                parse_status, parse_category = "failed", _classify_parse_error(exc)
        except AIRequestError as exc:
            request_error_type = type(exc).__name__
        record = {
            "code": identity[0],
            "signal_date": identity[1],
            "provider": client.provider,
            "model": model,
            "committee_config_path": str(config_path),
            "committee_config_sha256": config["committee_config_sha256"],
            "ai_config_path": config["ai_config_path"],
            "ai_config_sha256": config["ai_config_sha256"],
            "prompt_sha256": config["prompt"]["sha256"],
            "input_sha256": _sha256_json(messages[1]),
            "messages_sha256": _sha256_json(messages),
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "response_char_count": len(content),
            "response_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
            "finish_reason": finish_reason,
            "parse_status": parse_status,
            "parse_category": parse_category,
            "request_error_type": request_error_type,
            "response_shape": _response_shape(content),
        }
        records.append(record)

    audit = {
        "schema_version": "ncn_mkf_frozen_contract_audit_v1",
        "source_run": str(args.source_run.expanduser().resolve()),
        "source_selection_run": str(persisted.source_selection_run),
        "source_candidates_sha256": persisted.candidates_sha256,
        "source_manifest_sha256": hashlib.sha256((args.source_run.expanduser().resolve() / "manifest.json").read_bytes()).hexdigest(),
        "records": records,
        "raw_content_persisted": False,
    }
    path = _write_audit(args.output_root, audit)
    print(f"audit_path={path}")
    print(json.dumps(audit, ensure_ascii=False, indent=2))
    return 0 if all(record["parse_status"] == "ok" for record in records) else 1


if __name__ == "__main__":
    raise SystemExit(main())
