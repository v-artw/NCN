"""MKF 与 SMC 新闻复核必须解析到同一 AI provider 配置（2026-09-27 自
tests/test_ai_provider_config.py 移植：news_ai_review 已属 smc/ 子项目，
主仓测试不能再导入它，等价校验在此以 smc -> main 方向继续成立）。
"""

from __future__ import annotations

from pathlib import Path

import pytest

SMC_ROOT = Path(__file__).parents[1]
ROOT = SMC_ROOT.parent


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


def test_mkf_and_news_resolve_same_repository_provider(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from ashare_edge_scout.mkf_ai_review import load_mkf_ai_config, build_ai_client as build_mkf_client
    from ashare_smc.news_ai_review import load_review_config, build_ai_client as build_news_client

    monkeypatch.setenv("EDGE_SCOUT_LOCAL_AI_API_KEY", "test-secret")
    monkeypatch.setenv("EDGE_SCOUT_AI_PROVIDERS_CONFIG", str(_write_config(tmp_path)))
    mkf = load_mkf_ai_config(ROOT / "yaml" / "mkf_ai_review.yaml")
    news = load_review_config(SMC_ROOT / "yaml" / "news_ai_review.yaml")
    mkf_client = build_mkf_client(mkf)
    news_client = build_news_client(news)
    assert mkf["ai_config_path"] == news["ai_config_path"]
    assert mkf["ai_config_sha256"] == news["ai_config_sha256"]
    assert mkf["ai"]["provider"] == news["ai"]["provider"] == "test"
    assert mkf_client is not None and news_client is not None
    assert mkf_client.base_url == news_client.base_url == "http://example.test/v1"
    assert mkf_client.model == news_client.model == "test-model"
    assert mkf_client.timeout_seconds == news_client.timeout_seconds == 10
