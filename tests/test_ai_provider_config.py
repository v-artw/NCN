from __future__ import annotations

import json
import urllib.error
from pathlib import Path

import pytest

from ashare_edge_scout.ai_providers import (
    AIProviderError,
    AIRequestError,
    OpenAICompatibleClient,
    build_ai_client,
    forbid_business_ai_overrides,
    load_ai_provider_config,
)

ROOT = Path(__file__).parents[1]


def _write_config(tmp_path: Path, *, provider: str = "test", enabled: bool = True, provider_enabled: bool = True) -> Path:
    key = tmp_path / "key.txt"
    key.write_text("file-secret\n", encoding="utf-8")
    path = tmp_path / "ai_providers.yaml"
    path.write_text(
        "schema_version: ncn_ai_providers_v1\n"
        f"enabled: {str(enabled).lower()}\n"
        f"provider: {provider}\n"
        "timeout_seconds: 15\n"
        "temperature: 0\n"
        "seed: 42\n"
        "response_format:\n  type: json_object\n"
        "providers:\n"
        "  test:\n"
        f"    enabled: {str(provider_enabled).lower()}\n"
        "    name: Test\n"
        "    base_url: http://example.test/v1/\n"
        "    model: test-model\n"
        f"    key_file: {key}\n"
        "    api_key_env: TEST_AI_KEY\n"
        "    timeout_seconds: 10\n",
        encoding="utf-8",
    )
    return path


def test_repository_ai_provider_inventory() -> None:
    config = load_ai_provider_config(ROOT / "yaml" / "ai_providers.yaml")

    assert config.schema_version == "ncn_ai_providers_v1"
    assert config.provider == "local_finance"
    selected = config.providers[config.provider]
    assert selected["base_url"] == "http://ts.dorisw.kdns.fr:18090/v1"
    assert selected["model"] == "Qwen3.8-27B-oQ4e-mtp"
    assert selected["enabled"] is True
    assert config.providers["deepseek"]["enabled"] is True
    for name in ("deepseek_chat", "deepseek_pro", "lmstudio_finance_8b", "tongyi", "kimi", "zhipu"):
        assert config.providers[name]["enabled"] is False


def test_url_normalization_only_strips_trailing_slash(tmp_path: Path) -> None:
    config = load_ai_provider_config(_write_config(tmp_path))
    assert config.providers["test"]["base_url"] == "http://example.test/v1"


def test_unknown_and_disabled_provider_fail_closed(tmp_path: Path) -> None:
    with pytest.raises(AIProviderError, match="unknown AI provider"):
        load_ai_provider_config(_write_config(tmp_path, provider="missing"))
    with pytest.raises(AIProviderError, match="selected AI provider is disabled"):
        load_ai_provider_config(_write_config(tmp_path, provider_enabled=False))


def test_empty_env_falls_back_to_key_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TEST_AI_KEY", "")
    config = load_ai_provider_config(_write_config(tmp_path))
    client = build_ai_client(config)
    assert client is not None
    assert client.api_key == "file-secret"


def test_nonempty_env_takes_precedence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TEST_AI_KEY", "env-secret")
    config = load_ai_provider_config(_write_config(tmp_path))
    client = build_ai_client(config)
    assert client is not None
    assert client.api_key == "env-secret"


def test_inline_api_key_is_rejected(tmp_path: Path) -> None:
    path = _write_config(tmp_path)
    text = path.read_text(encoding="utf-8").replace("    timeout_seconds: 10\n", "    api_key: secret\n")
    path.write_text(text, encoding="utf-8")
    with pytest.raises(AIProviderError, match="unsupported fields|inline api_key"):
        load_ai_provider_config(path)


def test_business_provider_overrides_are_rejected(tmp_path: Path) -> None:
    source = tmp_path / "business.yaml"
    for payload in (
        {"ai": {"provider": "deepseek"}},
        {"AI_PROVIDER": "deepseek"},
        {"review": {"model": "other"}},
        {"base_url": "http://example.test/v1"},
    ):
        with pytest.raises(AIProviderError, match="must not override"):
            forbid_business_ai_overrides(payload, source=source)
    forbid_business_ai_overrides({"news": {"days": 7, "timeout_seconds": 10}}, source=source)


def test_error_redaction() -> None:
    error = AIRequestError(401, "Authorization: Bearer secret-token api_key=secret-key")
    assert "secret-token" not in str(error)
    assert "secret-key" not in str(error)
    assert "[redacted]" in str(error)


def test_chat_400_retries_without_response_format_and_seed(monkeypatch: pytest.MonkeyPatch) -> None:
    client = OpenAICompatibleClient(
        provider="test",
        base_url="http://example.test/v1",
        api_key="secret",
        model="test-model",
        timeout_seconds=5,
        seed=42,
        response_format={"type": "json_object"},
    )
    calls: list[dict[str, object]] = []

    def fake_request(path, payload=None, *, user_agent):
        calls.append(dict(payload or {}))
        if len(calls) == 1:
            raise AIRequestError(400, "unsupported")
        return {"choices": [{"message": {"content": json.dumps({"ok": True})}}]}

    monkeypatch.setattr(client, "request_json", fake_request)
    response, model = client.chat_json(
        [{"role": "user", "content": "return json"}], user_agent="test"
    )
    assert model == "test-model"
    assert response["choices"]
    assert "response_format" in calls[0] and "seed" in calls[0]
    assert "response_format" not in calls[1] and "seed" not in calls[1]


def test_mkf_and_news_resolve_same_repository_provider() -> None:
    from ashare_edge_scout.mkf_ai_review import load_mkf_ai_config, build_ai_client as build_mkf_client
    from ashare_edge_scout.news_ai_review import load_review_config, build_ai_client as build_news_client

    mkf = load_mkf_ai_config(ROOT / "yaml" / "mkf_ai_review.yaml")
    news = load_review_config(ROOT / "yaml" / "news_ai_review.yaml")
    mkf_client = build_mkf_client(mkf)
    news_client = build_news_client(news)
    assert mkf["ai_config_path"] == news["ai_config_path"]
    assert mkf["ai_config_sha256"] == news["ai_config_sha256"]
    assert mkf["ai"]["provider"] == news["ai"]["provider"] == "local_finance"
    assert mkf_client is not None and news_client is not None
    assert mkf_client.base_url == news_client.base_url
    assert mkf_client.model == news_client.model == "Qwen3.8-27B-oQ4e-mtp"
    assert mkf_client.timeout_seconds == news_client.timeout_seconds


def test_smoke_stops_before_chat_when_models_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from scripts import smoke_ai_provider

    config_path = _write_config(tmp_path)
    calls: list[str] = []

    class FakeClient:
        provider = "test"
        base_url = "http://example.test/v1"
        model = "test-model"
        timeout_seconds = 5.0

        def models(self, *, user_agent):
            calls.append("models")
            raise AIRequestError(401, "Authorization: Bearer secret")

        def chat_json(self, *args, **kwargs):
            calls.append("chat")
            raise AssertionError("chat must not run after models failure")

    monkeypatch.setattr(smoke_ai_provider, "build_ai_client", lambda config: FakeClient())
    assert smoke_ai_provider.main(["--config", str(config_path), "--chat"]) == 3
    assert calls == ["models"]


def test_smoke_models_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from scripts import smoke_ai_provider

    config_path = _write_config(tmp_path)

    class FakeClient:
        provider = "test"
        base_url = "http://example.test/v1"
        model = "test-model"
        timeout_seconds = 5.0

        def models(self, *, user_agent):
            return {"data": [{"id": "test-model"}]}

    monkeypatch.setattr(smoke_ai_provider, "build_ai_client", lambda config: FakeClient())
    assert smoke_ai_provider.main(["--config", str(config_path), "--models-only"]) == 0


def test_chat_401_does_not_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    client = OpenAICompatibleClient(
        provider="test",
        base_url="http://example.test/v1",
        api_key="secret",
        model="test-model",
        timeout_seconds=5,
    )
    calls = 0

    def fake_request(path, payload=None, *, user_agent):
        nonlocal calls
        calls += 1
        raise AIRequestError(401, "unauthorized")

    monkeypatch.setattr(client, "request_json", fake_request)
    with pytest.raises(AIRequestError):
        client.chat_json([{"role": "user", "content": "x"}], user_agent="test")
    assert calls == 1
