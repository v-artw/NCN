from __future__ import annotations

import csv
import hashlib
import http.client
import json
from pathlib import Path

import pandas as pd
import pytest

from ashare_edge_scout import mkf_ai_review
from ashare_edge_scout.mkf_ai_review import load_mkf_ai_config, parse_ai_response, run_mkf_ai_review, validate_mkf_selection_run
from ashare_edge_scout.mkf_candidate_selector import MkfCandidateRow, _atomic_publish


class FakeClient:
    def __init__(self, payload: dict[str, object] | None = None, fail: bool = False):
        self.calls: list[str] = []
        self.payload = payload or {
            "review_state": "priority_research",
            "confidence": 0.8,
            "research_summary": "MKF节奏改善，仅作研究优先级。",
            "technical_observations": ["红蓝线同步上穿20"],
            "risk_flags": [],
            "committee": {
                "technical_analyst": {"stance": "supportive", "notes": ["candlestick context supportive"]},
                "risk_manager": {"stance": "low", "notes": ["no major candle risk"]},
            },
            "committee_disagreement_flags": [],
        }
        self.fail = fail
        self.candidate: dict[str, object] | None = None
        self.context: dict[str, object] | None = None
        self.news_context: dict[str, object] | None = None

    def analyze(self, candidate: dict[str, object], context: dict[str, object], news_context: dict[str, object]) -> tuple[dict[str, object], str]:
        self.calls.append(str(candidate["code"]))
        self.candidate = candidate
        self.context = context
        self.news_context = news_context
        if self.fail:
            raise ValueError("boom")
        return self.payload, "fake-model"


def _mkf_run(root: Path, count: int = 1) -> Path:
    rows = [
        MkfCandidateRow(f"sh.{600000 + index:06d}", "2026-04-09", "2026-04-08", 1, 9.0 + index, 2e8, 2.0, 30.0, 24.0, 35.0, True, True, True, "")
        for index in range(1, count + 1)
    ]
    return _atomic_publish(root, "mkf-select-test", rows, {"schema_version": "ncn_mkf_candidate_selector_v5", "candidate_count": count, "published_at_utc": "2026-04-09T00:00:00+00:00"})


def _news_config(path: Path) -> Path:
    config = path / "mkf_news_context.yaml"
    config.write_text(
        "NEWS_LIMIT: 5\n"
        "NEWS_DAYS: 7\n"
        "ENABLE_NEWS_CACHE: true\n"
        "NEWS_CACHE_DIR: './Message'\n"
        "ENABLE_AUTO_CLEANUP: true\n"
        "CACHE_RETENTION_DAYS: 7\n"
        "FETCH_ONLINE_BY_DEFAULT: true\n"
        "ENABLE_GOOGLE_NEWS: false\n"
        "ENABLE_EASTMONEY_NEWS: false\n"
        "ENABLE_EASTMONEY_ANNOUNCEMENTS: false\n"
        "FATAL_RISK_WORDS: ['收到立案告知书']\n"
        "ATTENTION_WORDS: ['减持']\n",
        encoding="utf-8",
    )
    return config


def _ai_provider_config(path: Path) -> Path:
    key = path / "fake.key"
    key.write_text("fake-secret\n", encoding="utf-8")
    config = path / "ai_providers.yaml"
    config.write_text(
        "schema_version: ncn_ai_providers_v1\n"
        "enabled: true\n"
        "provider: fake\n"
        "timeout_seconds: 120\n"
        "temperature: 0\n"
        "seed: 42\n"
        "response_format:\n  type: json_object\n"
        "providers:\n"
        "  fake:\n"
        "    enabled: true\n"
        "    base_url: http://example.invalid/v1\n"
        "    model: fake\n"
        f"    key_file: {key}\n"
        "  local_finance:\n"
        "    enabled: false\n"
        "    base_url: http://127.0.0.1:1234/v1\n"
        "    model: local-finance-ai\n"
        f"    key_file: {key}\n",
        encoding="utf-8",
    )
    return config


def _config(path: Path, *, max_candidates: int | None = None) -> Path:
    news = _news_config(path)
    ai = _ai_provider_config(path)
    config = path / "mkf_ai.yaml"
    review = "" if max_candidates is None else f"review:\n  max_candidates: {max_candidates}\n"
    config.write_text(
        f"ai_config: {ai}\nnews_config: {news}\n{review}",
        encoding="utf-8",
    )
    return config


def _data(root: Path, count: int = 1) -> Path:
    data_root = root / "data"
    data_root.mkdir()
    dates = pd.bdate_range(end="2026-04-09", periods=30)
    for code_index in range(1, count + 1):
        code = f"sh.{600000 + code_index:06d}"
        rows = []
        for index, date in enumerate(dates):
            close = 9.0 + code_index + index * 0.02
            rows.append({"code": code, "date": date.date(), "open": close - 0.05, "high": close + 0.2, "low": close - 0.2, "close": close, "preclose": close - 0.02, "volume": 1000 + index * 10, "amount": 2000000 + index * 1000, "turn": 2.0, "tradestatus": "1", "isST": "0"})
        rows[-1]["close"] = rows[-1]["open"] + 0.2
        pd.DataFrame(rows).to_parquet(data_root / f"{code}.parquet", index=False)
    return data_root


def test_mkf_ai_review_validates_source_manifest_hash(tmp_path: Path) -> None:
    run = _mkf_run(tmp_path / "selections")
    validate_mkf_selection_run(run)
    (run / "candidates.json").write_text("[]\n", encoding="utf-8")

    with pytest.raises(ValueError, match="hash"):
        validate_mkf_selection_run(run)


def _fake_news_context(code: str, config: dict[str, object]) -> object:
    class News:
        def to_dict(self) -> dict[str, object]:
            return {
                "code": code,
                "normalized_code": "sh.600001",
                "em_code": "600001",
                "date": "2026-04-09",
                "cache_path": str(Path(str(config["_resolved_news_cache_dir"])) / "sh.600001_20260409.json"),
                "cache_status": "refreshed",
                "source_status": {"eastmoney_announcement": "success:1"},
                "news_txt": "[📋 公告] 公司收到立案告知书",
                "fatal_risks": ("收到立案告知书",),
                "attn_risks": (),
                "config": {"NEWS_DAYS": 7, "NEWS_LIMIT": 5, "NEWS_CACHE_DIR": "./Message"},
            }
    return News()


def test_mkf_ai_review_publishes_research_labels_and_source_hash(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mkf_ai_review, "build_mkf_news_context", _fake_news_context)
    selection_root = tmp_path / "selections"
    run = _mkf_run(selection_root)
    client = FakeClient()
    result = run_mkf_ai_review(
        selection_root=selection_root,
        selection_run=run,
        output_root=tmp_path / "reviews",
        config_path=_config(tmp_path),
        data_root=_data(tmp_path),
        ai_client=client,
        run_id="mkf-ai-test",
    )

    rows = json.loads(result.reviews_path.read_text())
    summary = json.loads(result.summary_path.read_text())
    contexts = json.loads(result.technical_contexts_path.read_text())
    news_contexts = json.loads(result.news_contexts_path.read_text())
    manifest = json.loads(result.manifest_path.read_text())
    assert rows[0]["review_state"] == "priority_research"
    assert rows[0]["committee_summary"]["technical_analyst"]["stance"] == "supportive"
    assert rows[0]["technical_context_status"] == "ok"
    assert rows[0]["candle_confirm_score"] is not None
    assert "BUY" not in json.dumps(rows, ensure_ascii=False)
    assert summary["source_candidates_sha256"]
    assert summary["ai_provider_config_style"] == "ncn_ai_providers_v1"
    assert summary["ai_provider_schema"] == "ncn_ai_providers_v1"
    assert summary["ai_client_status"] == "injected"
    assert summary["ai_config_sha256"]
    assert summary["prompt_source"] == "module_default_prompt.system"
    assert summary["prompt_sha256"] == hashlib.sha256(mkf_ai_review.DEFAULT_MKF_AI_SYSTEM_PROMPT.encode("utf-8")).hexdigest()
    assert summary["boundaries"]["smc_ranking_modified"] is False
    assert summary["boundaries"]["mkf_selection_modified"] is False
    assert summary["boundaries"]["pmkf_kalman_used"] is False
    assert summary["boundaries"]["futu_fields_used"] is False
    assert summary["technical_context"]["uses_pmkf_kalman"] is False
    assert summary["technical_context"]["uses_futu_fields"] is False
    assert summary["news_context"]["enabled"] is True
    assert summary["news_context"]["used_for"] == "mkf_ai_research_layer_only"
    assert summary["news_context"]["subjective_news_invention_allowed"] is False
    assert summary["boundaries"]["news_used_only_for_mkf_ai_layer"] is True
    assert "technical_contexts.json" in manifest["files"]
    assert "news_contexts.json" in manifest["files"]
    assert news_contexts[0]["news_context"]["news_txt"] == "[📋 公告] 公司收到立案告知书"
    assert news_contexts[0]["news_context"]["fatal_risks"] == ["收到立案告知书"]
    assert contexts[0]["technical_context"]["method_reference"] == "Japanese Candlestick Charting Techniques style OHLC shape review"
    assert contexts[0]["technical_context"]["mkf_selection_snapshot"]["mkf_momentum"] == 30.0
    with result.reviews_csv_path.open(encoding="utf-8", newline="") as file:
        header = next(csv.reader(file))
    assert header[header.index("confidence") + 1] == "local_score"
    assert header[:5] == ["code", "signal_date", "review_state", "confidence", "local_score"]
    assert client.context is not None
    assert client.context["excluded_contexts"]["pmkf_kalman_used"] is False
    assert client.context["excluded_contexts"]["futu_fields_used"] is False
    assert client.news_context is not None
    assert client.news_context["news_txt"] == "[📋 公告] 公司收到立案告知书"
    assert client.news_context["fatal_risks"] == ("收到立案告知书",)
    context_text = json.dumps(client.context, ensure_ascii=False).lower()
    for forbidden in ("futu_bonus", "futu_status", "mhpg", "dxbd", "bullcluster", "powerline"):
        assert forbidden not in context_text
    assert result.run_directory.parent.name == "reviews"


def test_mkf_ai_review_limits_ai_calls_from_yaml_but_keeps_all_rows(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mkf_ai_review, "build_mkf_news_context", _fake_news_context)
    selection_root = tmp_path / "selections"
    run = _mkf_run(selection_root, count=3)
    client = FakeClient()
    result = run_mkf_ai_review(
        selection_root=selection_root,
        selection_run=run,
        output_root=tmp_path / "reviews",
        config_path=_config(tmp_path, max_candidates=2),
        data_root=_data(tmp_path, count=3),
        ai_client=client,
        run_id="mkf-ai-yaml-limit",
    )

    rows = json.loads(result.reviews_path.read_text())
    summary = json.loads(result.summary_path.read_text())
    assert client.calls == ["sh.600001", "sh.600002"]
    assert len(rows) == 3
    assert rows[2]["review_state"] == "ai_unavailable"
    assert summary["configured_max_candidates"] == 2
    assert summary["effective_max_candidates"] == 2
    assert summary["ai_attempt_count"] == 2
    assert summary["ai_skipped_by_max_candidates"] == 1


def test_mkf_ai_review_cli_limit_overrides_yaml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mkf_ai_review, "build_mkf_news_context", _fake_news_context)
    selection_root = tmp_path / "selections"
    run = _mkf_run(selection_root, count=3)
    client = FakeClient()
    result = run_mkf_ai_review(
        selection_root=selection_root,
        selection_run=run,
        output_root=tmp_path / "reviews",
        config_path=_config(tmp_path, max_candidates=1),
        data_root=_data(tmp_path, count=3),
        max_candidates=3,
        ai_client=client,
        run_id="mkf-ai-cli-limit",
    )

    rows = json.loads(result.reviews_path.read_text())
    summary = json.loads(result.summary_path.read_text())
    assert client.calls == ["sh.600001", "sh.600002", "sh.600003"]
    assert [row["review_state"] for row in rows] == ["priority_research", "priority_research", "priority_research"]
    assert summary["configured_max_candidates"] == 1
    assert summary["effective_max_candidates"] == 3
    assert summary["ai_skipped_by_max_candidates"] == 0


def test_mkf_ai_review_fails_closed_when_ai_fails(tmp_path: Path) -> None:
    selection_root = tmp_path / "selections"
    run = _mkf_run(selection_root)
    result = run_mkf_ai_review(
        selection_root=selection_root,
        selection_run=run,
        output_root=tmp_path / "mkf_ai_reviews",
        config_path=_config(tmp_path),
        data_root=_data(tmp_path),
        ai_client=FakeClient(fail=True),
        run_id="mkf-ai-failed",
    )

    rows = json.loads(result.reviews_path.read_text())
    summary = json.loads(result.summary_path.read_text())
    assert rows[0]["review_state"] == "ai_unavailable"
    assert summary["status"] == "ai_failed"
    assert summary["ai_success_count"] == 0


def test_mkf_ai_review_treats_incomplete_read_as_ai_unavailable(tmp_path: Path) -> None:
    class IncompleteReadClient:
        def analyze(self, candidate: dict[str, object], context: dict[str, object], news_context: dict[str, object]) -> tuple[dict[str, object], str]:
            raise http.client.IncompleteRead(b"")

    selection_root = tmp_path / "selections"
    run = _mkf_run(selection_root)
    result = run_mkf_ai_review(
        selection_root=selection_root,
        selection_run=run,
        output_root=tmp_path / "mkf_ai_reviews",
        config_path=_config(tmp_path),
        data_root=_data(tmp_path),
        ai_client=IncompleteReadClient(),
        run_id="mkf-ai-incomplete-read",
    )

    rows = json.loads(result.reviews_path.read_text())
    summary = json.loads(result.summary_path.read_text())
    assert rows[0]["review_state"] == "ai_unavailable"
    assert summary["status"] == "ai_failed"
    assert summary["ai_error_counts"] == {"IncompleteRead": 1}


def test_mkf_ai_review_progress_includes_candidate_and_result_details(tmp_path: Path) -> None:
    selection_root = tmp_path / "selections"
    run = _mkf_run(selection_root)
    events: list[tuple[int, int, str, str, dict[str, object]]] = []

    result = run_mkf_ai_review(
        selection_root=selection_root,
        selection_run=run,
        output_root=tmp_path / "reviews",
        config_path=_config(tmp_path),
        data_root=_data(tmp_path),
        ai_client=FakeClient(),
        run_id="mkf-ai-progress",
        progress=lambda index, total, code, stage, detail=None: events.append((index, total, code, stage, detail or {})),
    )

    assert result.priority_research_count == 1
    assert events[0][3] == "context"
    assert events[0][4]["close"] == 10.0
    assert events[0][4]["amount_cny"] == 200_000_000.0
    assert events[0][4]["mkf_momentum"] == 30.0
    assert events[-1][3] == "priority_research"
    assert events[-1][4]["confidence"] == 0.8
    assert events[-1][4]["local_score"] >= 0.0


def test_mkf_ai_review_orders_ai_unavailable_after_risk_attention(tmp_path: Path) -> None:
    rows = [
        MkfCandidateRow("sh.600001", "2026-04-09", "2026-04-08", 1, 10.0, 2e8, 2.0, 30.0, 24.0, 35.0, True, True, True, ""),
        MkfCandidateRow("sh.600002", "2026-04-09", "2026-04-07", 2, 11.0, 2e8, 2.0, 30.0, 24.0, 35.0, True, True, True, ""),
    ]
    selection_root = tmp_path / "selections"
    _atomic_publish(selection_root, "mkf-select-test", rows, {"schema_version": "ncn_mkf_candidate_selector_v5", "candidate_count": 2, "published_at_utc": "2026-04-09T00:00:00+00:00"})

    class MixedClient:
        def analyze(self, candidate: dict[str, object], context: dict[str, object], news_context: dict[str, object]) -> tuple[dict[str, object], str]:
            if candidate["code"] == "sh.600001":
                raise ValueError("boom")
            return {
                "review_state": "risk_attention",
                "confidence": 0.1,
                "research_summary": "风险关注。",
                "technical_observations": [],
                "risk_flags": ["风险测试"],
            }, "fake-model"

    result = run_mkf_ai_review(
        selection_root=selection_root,
        selection_run=selection_root / "mkf-select-test",
        output_root=tmp_path / "reviews",
        config_path=_config(tmp_path),
        data_root=_data(tmp_path),
        ai_client=MixedClient(),
        run_id="mkf-ai-order",
    )

    published = json.loads(result.reviews_path.read_text())
    assert [row["review_state"] for row in published] == ["risk_attention", "ai_unavailable"]


@pytest.mark.parametrize(
    "payload",
    [
        '{"review_state":"priority_research","confidence":0.8,"research_summary":"BUY"}',
        '{"review_state":"priority_research","confidence":0.8,"research_summary":"SELL"}',
        '{"review_state":"priority_research","confidence":0.8,"research_summary":"WAIT"}',
        '{"review_state":"priority_research","confidence":0.8,"research_summary":"PRE-BUY"}',
        '{"review_state":"priority_research","confidence":0.8,"max_position_pct":10}',
        '{"review_state":"priority_research","confidence":0.8,"stop_loss":9.8}',
        '{"review_state":"priority_research","confidence":0.8,"target_price":12.0}',
        '{"review_state":"priority_research","confidence":0.8,"pnl":"positive"}',
    ],
)

def test_mkf_ai_review_rejects_action_labels(payload: str) -> None:
    with pytest.raises(ValueError, match="forbidden"):
        parse_ai_response(payload)


def test_mkf_ai_config_loads_unified_provider_yaml(tmp_path: Path) -> None:
    news = _news_config(tmp_path)
    providers = _ai_provider_config(tmp_path)
    config = tmp_path / "mkf_ai.yaml"
    config.write_text(f"ai_config: {providers}\nnews_config: {news}\n", encoding="utf-8")

    loaded = load_mkf_ai_config(config)

    assert loaded["ai"]["provider"] == "fake"
    assert loaded["ai"]["providers"]["fake"]["model"] == "fake"
    assert loaded["ai"]["providers"]["local_finance"]["base_url"] == "http://127.0.0.1:1234/v1"
    assert loaded["ai"]["provider_config_style"] == "ncn_ai_providers_v1"
    assert loaded["ai_config_path"] == str(providers.resolve())
    assert loaded["ai_config_sha256"]
    assert loaded["prompt"]["source"] == "module_default_prompt.system"
    assert loaded["prompt"]["system"] == mkf_ai_review.DEFAULT_MKF_AI_SYSTEM_PROMPT
    assert loaded["prompt"]["sha256"] == hashlib.sha256(loaded["prompt"]["system"].encode("utf-8")).hexdigest()


def test_repository_mkf_ai_config_loads_yaml_prompt() -> None:
    root = Path(__file__).parents[1]
    loaded = load_mkf_ai_config(root / "yaml" / "mkf_ai_review.yaml")

    assert loaded["prompt"]["source"] == "business_yaml_prompt.system"
    assert loaded["prompt"]["system"]
    assert "MKF AI委员会" in loaded["prompt"]["system"]
    assert loaded["prompt"]["sha256"] == hashlib.sha256(loaded["prompt"]["system"].encode("utf-8")).hexdigest()


def test_mkf_ai_client_uses_yaml_prompt(tmp_path: Path) -> None:
    news = _news_config(tmp_path)
    providers = _ai_provider_config(tmp_path)
    config = tmp_path / "mkf_ai.yaml"
    config.write_text(
        f"ai_config: {providers}\nnews_config: {news}\nprompt:\n  system: '自定义MKF提示词，只读研究。'\n",
        encoding="utf-8",
    )
    client = mkf_ai_review.build_ai_client(load_mkf_ai_config(config))
    assert client is not None
    captured: dict[str, object] = {}

    def fake_chat(messages, *, user_agent):
        captured["messages"] = messages
        return {"choices": [{"message": {"content": json.dumps({"review_state": "standard_research", "confidence": 0.4}, ensure_ascii=False)}}]}, "fake"

    client.chat_json = fake_chat  # type: ignore[method-assign]
    client.analyze({"code": "sh.600001"}, {}, {"news_txt": "暂无新闻数据"})

    messages = captured["messages"]
    assert isinstance(messages, list)
    assert messages[0] == {"role": "system", "content": "自定义MKF提示词，只读研究。"}


def test_mkf_business_config_rejects_provider_override(tmp_path: Path) -> None:
    news = _news_config(tmp_path)
    providers = _ai_provider_config(tmp_path)
    config = tmp_path / "mkf_ai.yaml"
    config.write_text(
        f"ai_config: {providers}\nnews_config: {news}\nai:\n  provider: deepseek\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="must not override"):
        load_mkf_ai_config(config)


def test_mkf_ai_config_rejects_forbidden_context_switches(tmp_path: Path) -> None:
    news = _news_config(tmp_path)
    providers = _ai_provider_config(tmp_path)
    config = tmp_path / "mkf_ai.yaml"
    config.write_text(
        f"ai_config: {providers}\nnews_config: {news}\nreview:\n  technical_context:\n    use_pmkf_kalman: true\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="PMKF Kalman"):
        load_mkf_ai_config(config)
    config.write_text(
        f"ai_config: {providers}\nnews_config: {news}\nreview:\n  technical_context:\n    use_futu_fields: true\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Futu"):
        load_mkf_ai_config(config)
