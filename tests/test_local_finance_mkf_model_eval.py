from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

PATH = Path(__file__).resolve().parents[1] / "scripts/evaluate_local_finance_models_on_mkf_candidates.py"
SPEC = importlib.util.spec_from_file_location("mkf_model_eval", PATH)
module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = module
SPEC.loader.exec_module(module)


class FakeClient:
    model = "model-a"

    def __init__(self, content=None, finish="stop"):
        self.content = content or json.dumps({"review_state": "standard_research", "confidence": 0.6})
        self.finish = finish
        self.calls = []

    def chat_json(self, messages, **kwargs):
        self.calls.append((self.model, messages, kwargs))
        return {"choices": [{"message": {"content": self.content}, "finish_reason": self.finish}]}, self.model


def case():
    messages = [{"role": "user", "content": "fixed"}]
    return {"code": "sh.600000", "signal_date": "2026-09-03", "messages": messages,
            "messages_sha256": module.digest(messages)}


def test_audit_cli_does_not_require_candidate_or_provider():
    args = module.parse_args(["--audit-run", "/tmp/saved-eval"])
    assert args.selection_run is None
    assert args.audit_run == Path("/tmp/saved-eval")


def test_token_budget_and_raw_response_are_preserved():
    client = FakeClient()
    result = module.evaluate_case(client, case(), 2048)
    assert client.calls[0][2]["extra_payload"] == {"max_tokens": 2048}
    assert result["contract_pass"]
    assert result["response"]["choices"][0]["finish_reason"] == "stop"


def test_truncation_not_misreported_as_contract_pass():
    result = module.evaluate_case(FakeClient(finish="length"), case(), 2048)
    assert result["parsed_by_project"]
    assert not result["contract_pass"]


def test_invalid_json_retains_raw_evidence():
    result = module.evaluate_case(FakeClient(content='{"review_state":'), case(), 2048)
    assert result["content"] == '{"review_state":'
    assert not result["parsed_by_project"]
    assert result["error"]


def test_human_research_advice_is_allowed_by_contract():
    content = json.dumps({
        "review_state": "standard_research",
        "confidence": 0.6,
        "research_summary": "人工复核建议：买入观察，等待确认，参考止损和目标区间。",
    }, ensure_ascii=False)
    result = module.evaluate_case(FakeClient(content), case(), 2048)
    assert result["forbidden_term_count"] == 0
    assert result["contract_pass"]


def test_execution_claim_flag_independent_of_parser():
    content = json.dumps({"review_state": "standard_research", "confidence": 0.6,
                          "research_summary": "系统将自动下单"}, ensure_ascii=False)
    result = module.evaluate_case(FakeClient(content), case(), 2048)
    assert result["forbidden_term_count"] == 1
    assert not result["contract_pass"]


def test_negated_execution_disclaimer_is_allowed():
    content = json.dumps({"review_state": "standard_research", "confidence": 0.6,
                          "research_summary": "所有判断仅为人工复核参考，非自动交易或收益承诺。"}, ensure_ascii=False)
    result = module.evaluate_case(FakeClient(content), case(), 2048)
    assert result["forbidden_term_count"] == 0
    assert result["contract_pass"]


def test_escaped_chinese_is_checked_before_parser_normalization():
    content = json.dumps({"review_state": "standard_research", "confidence": 0.6,
                          "committee": {"technical_analyst": {"notes": "保证收益"}}})
    assert "保证收益" not in content
    result = module.evaluate_case(FakeClient(content), case(), 2048)
    assert result["forbidden_term_count"] == 1
    assert result["committee_notes_type_mismatch_count"] == 1
    assert not result["contract_pass"]


def test_research_advice_with_string_notes_only_fails_schema_mismatch():
    content = json.dumps({"review_state": "standard_research", "confidence": 0.6,
                          "committee": {"technical_analyst": {"notes": "建议买入观察"}}}, ensure_ascii=False)
    result = module.evaluate_case(FakeClient(content), case(), 2048)
    assert result["forbidden_term_count"] == 0
    assert result["committee_notes_type_mismatch_count"] == 1
    assert result["parsed_by_project"]
    assert result["contract_pass"]


def test_model_major_serial_replay_and_no_quality_ranking(tmp_path):
    client = FakeClient()
    cases = [case(), {**case(), "code": "sh.600001"}]
    report = module.run_eval(client, {"cases": cases}, ["model-a", "model-b"], tmp_path, 2048)
    assert [call[0] for call in client.calls] == ["model-a", "model-a", "model-b", "model-b"]
    assert client.calls[0][1] == client.calls[2][1]
    assert report["completed_requests"] == 4
    assert report["recommended_model"] is None
    assert len(list(tmp_path.glob("response-*.json"))) == 4


def test_freeze_uses_production_prompt_without_network(monkeypatch):
    candidates = [{"code": f"sh.{600000 + i}", "signal_date": "2026-09-03"} for i in range(10)]
    monkeypatch.setattr(module, "validate_mkf_selection_run", lambda path: (candidates, "hash"))
    monkeypatch.setattr(module, "_mkf_technical_context", lambda *args: {"status": "ok"})
    config = {"prompt": {"system": "fixed system"}}
    frozen = module.freeze_inputs(Path("unused"), Path("unused"), config, 10)
    assert len(frozen["cases"]) == 10
    payload = json.loads(frozen["cases"][0]["messages"][1]["content"])
    assert payload["cnstock_news_context"]["news_txt"] == module.NO_NEWS_TEXT
    assert payload["boundary"]["scanner_selection_is_immutable"]


def test_missing_technical_context_fails_before_requests(monkeypatch):
    monkeypatch.setattr(module, "validate_mkf_selection_run", lambda path: ([{"code": "x"}] * 10, "hash"))
    monkeypatch.setattr(module, "_mkf_technical_context", lambda *args: {"status": "missing_signal_bar"})
    with pytest.raises(ValueError, match="missing_signal_bar"):
        module.freeze_inputs(Path("unused"), Path("unused"), {"prompt": {"system": "fixed"}}, 10)


def test_audit_checks_hashes_and_keeps_raw_files_unchanged(tmp_path):
    inputs = {"cases": [case()], "models": ["model-a"]}
    module.write_json(tmp_path / "inputs.json", inputs)
    module.run_eval(FakeClient(), inputs, inputs["models"], tmp_path, 2048)
    hashes = {p.name: module.hashlib.sha256(p.read_bytes()).hexdigest() for p in tmp_path.iterdir()}
    module.write_json(tmp_path / "manifest.json", {"sha256": hashes})
    report = module.audit_saved_run(tmp_path)
    assert report["completed_requests"] == 1
    for name, expected in hashes.items():
        assert module.hashlib.sha256((tmp_path / name).read_bytes()).hexdigest() == expected
    (tmp_path / "response-01-01.json").write_text("tampered")
    with pytest.raises(ValueError, match="manifest mismatch"):
        module.audit_saved_run(tmp_path)


def test_transport_failure_stops_remaining_requests(tmp_path):
    client = FakeClient()

    def fail(*args, **kwargs):
        raise module.AIRequestError(None, "sensitive server body")

    client.chat_json = fail
    report = module.run_eval(client, {"cases": [case(), case()]}, ["a", "b"], tmp_path, 2048)
    assert report["status"] == "aborted_transport_failure"
    assert report["completed_requests"] == 1
    assert "sensitive" not in (tmp_path / "response-01-01.json").read_text()
