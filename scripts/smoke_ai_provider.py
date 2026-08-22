#!/usr/bin/env python3
"""Bounded no-publication smoke for the central NCN AI provider."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from ashare_edge_scout.ai_providers import (  # noqa: E402
    AIProviderError,
    AIRequestError,
    build_ai_client,
    load_ai_provider_config,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="NCN central AI provider connectivity smoke")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--provider")
    parser.add_argument("--models-only", action="store_true")
    parser.add_argument("--chat", action="store_true")
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    parser.add_argument(
        "--prompt",
        default='Return only JSON with this semantic content: {"status":"ok","paper_only":true,"live_orders":false}',
    )
    args = parser.parse_args(argv)
    if not args.models_only and not args.chat:
        args.models_only = True
    if args.timeout_seconds <= 0:
        parser.error("--timeout-seconds must be positive")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        config = load_ai_provider_config(args.config, provider_override=args.provider)
        client = build_ai_client(config)
        if client is None:
            raise AIProviderError("AI is globally disabled")
        client.timeout_seconds = args.timeout_seconds
    except (AIProviderError, OSError, ValueError) as exc:
        print(f"status=config_error detail={exc}", file=sys.stderr)
        return 2

    print(f"provider={client.provider}")
    print(f"base_url={client.base_url}")
    print(f"configured_model={client.model}")
    started = time.monotonic()
    try:
        payload = client.models(user_agent="NCN-AI-Provider-Smoke/1.0")
    except AIRequestError as exc:
        print(
            f"status=models_failed elapsed_seconds={time.monotonic() - started:.3f} detail={exc}",
            file=sys.stderr,
        )
        return 3
    models = payload.get("data", []) if isinstance(payload, dict) else []
    ids = [str(item.get("id")) for item in models if isinstance(item, dict) and item.get("id")]
    print(f"models_status=ok elapsed_seconds={time.monotonic() - started:.3f}")
    print(f"models_count={len(ids)}")
    print(f"configured_model_listed={str(client.model == 'auto' or client.model in ids).lower()}")
    if not args.chat:
        return 0

    started = time.monotonic()
    try:
        response, model = client.chat_json(
            [
                {"role": "system", "content": "Return only one JSON object."},
                {"role": "user", "content": args.prompt},
            ],
            user_agent="NCN-AI-Provider-Smoke/1.0",
            extra_payload={"max_tokens": 128},
        )
        content = str(response["choices"][0]["message"]["content"] or "").strip()
        start, end = content.find("{"), content.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("chat response contains no JSON object")
        parsed = json.loads(content[start:end + 1])
        if not isinstance(parsed, dict):
            raise ValueError("chat response JSON is not an object")
    except (AIRequestError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(
            f"status=chat_failed elapsed_seconds={time.monotonic() - started:.3f} detail={exc}",
            file=sys.stderr,
        )
        return 4
    print(f"chat_status=ok elapsed_seconds={time.monotonic() - started:.3f}")
    print(f"response_model={model}")
    print("json_object=true")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
