from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

PATH = Path(__file__).resolve().parents[1] / "scripts/audit_mkf_frozen_contract.py"
SPEC = importlib.util.spec_from_file_location("mkf_contract_audit", PATH)
module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = module
SPEC.loader.exec_module(module)


class FakeClient:
    provider = "local_finance"
    model = "fake-model"
    timeout_seconds = 120.0

    def __init__(self, content: str | None = None, error: Exception | None = None):
        self.content = content or json.dumps({"review_state": "standard_research", "confidence": 0.6})
        self.error = error
        self.calls = []

    def chat_json(self, messages, **kwargs):
        self.calls.append((messages, kwargs))
        if self.error:
            raise self.error
        return {"choices": [{"message": {"content": self.content}, "finish_reason": "stop"}]}, self.model


def _persisted() -> SimpleNamespace:
    identity = ("sh.601666", "2026-09-29")
    return SimpleNamespace(
        candidates=[{"code": identity[0], "signal_date": identity[1]}],
        technical_contexts={identity: {"status": "ok", "code": identity[0]}},
        news_contexts={identity: {"news_txt": "frozen", "code": identity[0]}},
        source_selection_run=Path("/selection"),
        candidates_sha256="candidates-hash",
    )


def _config(path: Path) -> dict[str, object]:
    return {
        "prompt": {"system": "fixed", "sha256": "prompt-hash"},
        "committee_config_sha256": "committee-hash",
        "ai_config_path": str(path),
        "ai_config_sha256": "provider-hash",
    }


def _run(monkeypatch, tmp_path, content: str | None = None, error: Exception | None = None):
    source = tmp_path / "source"
    source.mkdir()
    (source / "manifest.json").write_text("{}", encoding="utf-8")
    client = FakeClient(content, error)
    monkeypatch.setattr(module, "load_persisted_mkf_review_inputs", lambda _: _persisted())
    monkeypatch.setattr(module, "load_mkf_ai_config", lambda path: _config(path))
    monkeypatch.setattr(module, "build_ai_client", lambda _: client)
    result = module.main([
        "--source-run", str(source), "--output-root", str(tmp_path / "out"),
        "--case", str(next(iter(module.ALLOWED_CONFIGS))), "sh.601666",
    ])
    audit_paths = list((tmp_path / "out").glob("*/audit.json"))
    return result, json.loads(audit_paths[0].read_text(encoding="utf-8")), client


@pytest.mark.parametrize(("content", "category"), [
    ("not json", "no_json_object"),
    ('{"review_state":}', "invalid_json"),
    (json.dumps({"review_state": "unknown", "confidence": 0.5}), "invalid_review_state"),
    (json.dumps({"review_state": "standard_research", "confidence": 1.5}), "invalid_confidence"),
])
def test_audit_classifies_redacted_parse_failures(monkeypatch, tmp_path, content, category):
    result, audit, _ = _run(monkeypatch, tmp_path, content)
    record = audit["records"][0]
    assert result == 1
    assert record["parse_category"] == category
    assert content not in json.dumps(audit, ensure_ascii=False)


def test_audit_records_only_hashes_for_success(monkeypatch, tmp_path):
    result, audit, client = _run(monkeypatch, tmp_path)
    record = audit["records"][0]
    assert result == 0
    assert record["parse_category"] == "parse_ok"
    assert audit["raw_content_persisted"] is False
    serialized = json.dumps(audit)
    assert client.content not in serialized
    assert '"ncn_technical_context"' not in serialized
    assert client.calls[0][0][0]["content"] == "fixed"


def test_audit_accepts_execution_text_and_extensions(monkeypatch, tmp_path):
    content = json.dumps({
        "review_state": "standard_research",
        "confidence": 0.6,
        "research_summary": "系统将自动下单",
        "execution_intent": {"orders": [{"side": "buy"}]},
    }, ensure_ascii=False)
    result, audit, _ = _run(monkeypatch, tmp_path, content)
    assert result == 0
    assert audit["records"][0]["parse_category"] == "parse_ok"
    assert content not in json.dumps(audit, ensure_ascii=False)


def test_audit_redacts_transport_error(monkeypatch, tmp_path):
    result, audit, _ = _run(monkeypatch, tmp_path, error=module.AIRequestError(None, "sensitive server response"))
    record = audit["records"][0]
    assert result == 1
    assert record["parse_category"] == "transport_failed"
    assert record["request_error_type"] == "AIRequestError"
    assert "sensitive" not in json.dumps(audit)


def test_invalid_case_rejected_before_loader(monkeypatch, tmp_path):
    monkeypatch.setattr(module, "load_persisted_mkf_review_inputs", lambda _: pytest.fail("must not load"))
    with pytest.raises(ValueError, match="duplicate"):
        module.main([
            "--source-run", str(tmp_path),
            "--case", str(next(iter(module.ALLOWED_CONFIGS))), "sh.601666",
            "--case", str(next(iter(module.ALLOWED_CONFIGS))), "sh.601666",
        ])


def test_unknown_candidate_rejected_before_client(monkeypatch, tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "manifest.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(module, "load_persisted_mkf_review_inputs", lambda _: _persisted())
    monkeypatch.setattr(module, "build_ai_client", lambda _: pytest.fail("must not build client"))
    with pytest.raises(ValueError, match="not uniquely"):
        module.main([
            "--source-run", str(source), "--case", str(next(iter(module.ALLOWED_CONFIGS))), "sh.603301",
        ])
