#!/usr/bin/env python3
"""Replay frozen MKF prompts sequentially; measure contracts, not accuracy."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from ashare_edge_scout.ai_providers import (  # noqa: E402
    AIRequestError, build_ai_client, load_ai_provider_config,
)
from ashare_edge_scout.mkf_ai_review import (  # noqa: E402
    OpenAICompatibleClient, _mkf_technical_context, load_mkf_ai_config,
    parse_ai_response, validate_mkf_selection_run,
)
from ashare_edge_scout.mkf_news_context import NO_NEWS_TEXT  # noqa: E402

DEFAULT_MODELS = (
    "Qwen3.8-27B-oQ4e-mtp", "Ornith-1.0-35B-4bit",
    "Ornith-1.5-35B-A3B-oQ6e-mtp", "Ornith-1.5-35B-A3B-oQ4e-mtp",
)
FORBIDDEN = re.compile(
    r"\b(AUTO[_ -]?(?:ORDER|TRADE|REBALANCE)|BROKER[_ -]?(?:ORDER|SESSION|CONNECTIVITY)|"
    r"REAL[_ -]?MONEY[_ -]?(?:TRADE|ORDER|PNL)|LIVE[_ -]?(?:TRADE|ORDER)|FILLED[_ -]?ORDER|"
    r"GUARANTEED[_ -]?(?:RETURN|WIN[_ -]?RATE)|LEVERAGE)\b"
    r"|自动下单|自动交易|自动调仓|券商下单|连接券商|已连接券商|真实下单|实盘下单|真实成交"
    r"|保证收益|保证胜率|杠杆|真实P&L|实盘P&L|真实盈亏|实盘盈亏",
    re.IGNORECASE,
)
NEGATED_EXECUTION_PREFIXES = (
    "非", "不是", "不作为", "不会", "不得", "不能", "不可", "禁止", "无", "没有", "未", "并非",
    "not ", "non-", "without ", "no ", "never ",
)


def forbidden_matches(text: str) -> list[str]:
    hits = []
    for match in FORBIDDEN.finditer(text):
        prefix = text[max(0, match.start() - 8):match.start()].lower()
        if not any(marker in prefix for marker in NEGATED_EXECUTION_PREFIXES):
            hits.append(match.group(0))
    return hits


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def write_json(path: Path, value: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


class MessagesCaptured(Exception):
    pass


class PromptCapture(OpenAICompatibleClient):
    """Intercept production message construction without issuing any request."""

    def chat_json(self, messages, **kwargs):
        self.messages = messages
        raise MessagesCaptured


def freeze_inputs(selection_run: Path, data_root: Path, config: dict, top: int) -> dict:
    candidates, source_hash = validate_mkf_selection_run(selection_run)
    candidates = candidates[:top]
    if len(candidates) < 10:
        raise ValueError("selection must contain at least 10 candidates")
    capture = PromptCapture(base_url="http://unused.invalid/v1", api_key="unused",
                            model="capture", timeout_seconds=1,
                            system_prompt=config["prompt"]["system"])
    cases = []
    for candidate in candidates:
        context = _mkf_technical_context(candidate, data_root, config)
        if context["status"] != "ok":
            raise ValueError(f"{candidate['code']}: technical context {context['status']}")
        news = {"news_txt": NO_NEWS_TEXT, "fatal_risks": [], "attn_risks": [],
                "cache_status": "disabled_for_eval", "source_status": {},
                "evidence_status": "unavailable_no_point_in_time_news"}
        try:
            capture.analyze(candidate, context, news)
        except MessagesCaptured:
            pass
        messages = capture.messages
        cases.append({"code": candidate["code"], "signal_date": candidate["signal_date"],
                      "messages": messages, "messages_sha256": digest(messages)})
    return {"selection_run": str(selection_run), "source_candidates_sha256": source_hash,
            "news_policy": "no_news_no_online_fetch", "cases": cases}


def inspect_content(content: str) -> dict:
    result = {"json_valid": False, "forbidden_term_count": len(forbidden_matches(content)),
              "committee_notes_type_mismatch_count": 0}
    try:
        raw = json.loads(content)
    except (ValueError, TypeError):
        return result
    result["json_valid"] = isinstance(raw, dict)
    result["forbidden_term_count"] = len(forbidden_matches(json.dumps(raw, ensure_ascii=False)))
    if isinstance(raw, dict) and isinstance(raw.get("committee"), dict):
        result["committee_notes_type_mismatch_count"] = sum(
            isinstance(role, dict) and isinstance(role.get("notes"), str) and bool(role["notes"])
            for role in raw["committee"].values()
        )
    return result


def evaluate_case(client, case: dict, max_tokens: int) -> dict:
    row = {"code": case["code"], "signal_date": case["signal_date"],
           "model": client.model, "messages_sha256": case["messages_sha256"],
           "json_valid": False, "parsed_by_project": False, "contract_pass": False,
           "finish_reason": "", "forbidden_term_count": 0, "error": ""}
    started = time.monotonic()
    try:
        response, resolved = client.chat_json(
            case["messages"], user_agent="NCN-MKF-Model-Eval/1.0",
            extra_payload={"max_tokens": max_tokens},
        )
        row["response"] = response
        row["resolved_model"] = resolved
        choice = response["choices"][0]
        row["finish_reason"] = choice.get("finish_reason") or ""
        content = choice["message"].get("content") or ""
        row["content"] = content
        row.update(inspect_content(content))
        parsed = parse_ai_response(content)
        row["parsed"] = parsed
        row["parsed_by_project"] = True
        row["contract_pass"] = (row["json_valid"] and row["finish_reason"] == "stop"
                                and row["forbidden_term_count"] == 0)
    except (AIRequestError, ValueError, TypeError, KeyError, IndexError, OSError) as exc:
        # Do not persist transport errors, which can include server-echoed secrets.
        row["error"] = type(exc).__name__ if isinstance(exc, AIRequestError) else str(exc)
        row["transport_failed"] = isinstance(exc, (AIRequestError, OSError))
    row["elapsed_seconds"] = round(time.monotonic() - started, 3)
    return row


def report_results(models: list[str], cases: list[dict], results: list[dict], complete: bool) -> dict:
    summaries = []
    for model in models:
        rows = [r for r in results if r["model"] == model]
        valid = [r for r in rows if r["parsed_by_project"]]
        summaries.append({
            "model": model, "expected_count": len(cases), "completed_count": len(rows),
            "json_valid_count": sum(r["json_valid"] for r in rows),
            "parser_success_count": len(valid),
            "contract_pass_count": sum(r["contract_pass"] for r in rows),
            "truncated_count": sum(r["finish_reason"] == "length" for r in rows),
            "forbidden_output_count": sum(r["forbidden_term_count"] > 0 for r in rows),
            "committee_notes_mismatch_outputs": sum(r.get("committee_notes_type_mismatch_count", 0) > 0 for r in rows),
            "error_count": sum(bool(r["error"]) for r in rows),
            "mean_seconds": round(sum(r["elapsed_seconds"] for r in rows) / len(rows), 3) if rows else None,
            "mean_confidence": round(sum(r["parsed"]["confidence"] for r in valid) / len(valid), 4) if valid else None,
            "state_counts": dict(Counter(r["parsed"]["review_state"] for r in valid)),
        })
    return {"schema_version": "ncn_mkf_model_eval_v2", "status": "completed" if complete else "running",
            "expected_requests": len(models) * len(cases), "completed_requests": len(results),
            "recommended_model": None, "quality_ranking": "not_measured_requires_evidence_review",
            "limitations": ["single_date_ten_to_twenty_cases", "no_outcome_labels",
                            "confidence_is_self_report_not_accuracy", "no_news_lane_only",
                            "keyword_flags_require_manual_review", "not_a_return_backtest"],
            "summaries": summaries}


def run_eval(client, inputs: dict, models: list[str], output: Path, max_tokens: int) -> dict:
    results = []
    cases = inputs["cases"]
    for model_index, model in enumerate(models):
        client.model = model
        for case_index, case in enumerate(cases):
            print(f"START model={model} candidate={case_index + 1}/{len(cases)} code={case['code']}", flush=True)
            row = evaluate_case(client, case, max_tokens)
            results.append(row)
            write_json(output / f"response-{model_index + 1:02d}-{case_index + 1:02d}.json", row)
            report = report_results(models, cases, results, False)
            write_json(output / "summary.json", report)
            print(f"DONE model={model} code={case['code']} parser={row['parsed_by_project']} finish={row['finish_reason']} seconds={row['elapsed_seconds']} error={row['error']}", flush=True)
            if row.get("transport_failed"):
                report["status"] = "aborted_transport_failure"
                write_json(output / "summary.json", report)
                return report
    report = report_results(models, cases, results, True)
    write_json(output / "summary.json", report)
    with (output / "summary.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(report["summaries"][0]))
        writer.writeheader()
        writer.writerows(report["summaries"])
    return report


def audit_saved_run(output: Path) -> dict:
    """Recompute diagnostics locally without changing immutable inference evidence."""
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    for name, expected in manifest["sha256"].items():
        if hashlib.sha256((output / name).read_bytes()).hexdigest() != expected:
            raise ValueError(f"manifest mismatch: {name}")
    inputs = json.loads((output / "inputs.json").read_text(encoding="utf-8"))
    cases = inputs["cases"]
    models = inputs["models"]
    rows = []
    for model_index, model in enumerate(models):
        for case_index, case in enumerate(cases):
            path = output / f"response-{model_index + 1:02d}-{case_index + 1:02d}.json"
            row = json.loads(path.read_text(encoding="utf-8"))
            if (row["code"], row["model"], row["messages_sha256"]) != (case["code"], model, digest(case["messages"])):
                raise ValueError(f"input identity mismatch: {path.name}")
            row.update(inspect_content(row.get("content", "")))
            row["contract_pass"] = (row["json_valid"] and row["parsed_by_project"]
                                    and row["finish_reason"] == "stop" and not row["forbidden_term_count"])
            rows.append(row)
    report = report_results(models, cases, rows, True)
    report["audit"] = "manifest_and_prompt_identity_verified_decoded_keywords"
    report["rows"] = [{k: v for k, v in r.items() if k not in {"response", "content", "parsed"}} for r in rows]
    write_json(output / "audit-summary.json", report)
    with (output / "audit-summary.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(report["summaries"][0]))
        writer.writeheader()
        writer.writerows(report["summaries"])
    return report


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--selection-run", type=Path)
    source.add_argument("--audit-run", type=Path, help="Audit saved responses only; no model requests")
    parser.add_argument("--data-root", type=Path, default=PROJECT_ROOT / "PFrontStockData")
    parser.add_argument("--config", type=Path, default=PROJECT_ROOT / "yaml/mkf_ai_review.yaml")
    parser.add_argument("--ai-config", type=Path, default=PROJECT_ROOT / "yaml/ai_providers.yaml")
    parser.add_argument("--models", nargs="+", default=list(DEFAULT_MODELS))
    parser.add_argument("--top", type=int, default=10)
    parser.add_argument("--max-tokens", type=int, default=2048)
    parser.add_argument("--timeout-seconds", type=float, default=180)
    parser.add_argument("--output-root", type=Path, default=PROJECT_ROOT / "output/回测结果" / time.strftime("mkf-model-eval-%Y%m%d-%H%M%S"))
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args(argv)
    if not 10 <= args.top <= 20 or args.max_tokens < 1 or args.timeout_seconds <= 0:
        parser.error("require top=10..20 and positive token/timeout budgets")
    if len(set(args.models)) != len(args.models):
        parser.error("duplicate model IDs are not allowed")
    return args


def main(argv=None):
    args = parse_args(argv)
    if args.audit_run:
        report = audit_saved_run(args.audit_run)
        print(json.dumps({k: v for k, v in report.items() if k != "rows"}, ensure_ascii=False, indent=2))
        return 0
    config = load_mkf_ai_config(args.config)
    inputs = freeze_inputs(args.selection_run.resolve(), args.data_root, config, args.top)
    provider = load_ai_provider_config(args.ai_config, provider_override="local_finance")
    client = build_ai_client(provider)
    if client is None:
        raise ValueError("local_finance provider disabled")
    client.timeout_seconds = args.timeout_seconds
    inputs["generation"] = {"max_tokens": args.max_tokens, "temperature": client.temperature,
                            "seed": client.seed, "response_format": client.response_format,
                            "extra_options": client.extra_options, "timeout_seconds": args.timeout_seconds}
    inputs["models"] = args.models
    args.output_root.mkdir(parents=True, exist_ok=False)
    write_json(args.output_root / "inputs.json", inputs)
    print(f"OUTPUT {args.output_root}", flush=True)
    if args.prepare_only:
        return 0
    report = run_eval(client, inputs, args.models, args.output_root, args.max_tokens)
    hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in args.output_root.iterdir() if p.is_file()}
    write_json(args.output_root / "manifest.json", {"sha256": hashes, "status": report["status"]})
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
    return 0 if report["status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
