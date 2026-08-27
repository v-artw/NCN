from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from scripts.review_smc_news import _format_review_card, main as review_smc_news_main

from ashare_edge_scout.news_ai_review import (
    AIRequestError,
    NewsFetchResult,
    NewsItem,
    fetch_news,
    _parse_ai_json,
    classify_review,
    filter_ai_evidence,
    build_ai_client,
    load_review_config,
    run_news_ai_review,
)


def _review_config(root: Path, *, enabled: bool = False) -> Path:
    key = root / "test-ai.key"
    key.write_text("test-secret\n", encoding="utf-8")
    providers = root / "ai_providers.yaml"
    providers.write_text(
        "schema_version: ncn_ai_providers_v1\n"
        f"enabled: {str(enabled).lower()}\n"
        "provider: test\n"
        "timeout_seconds: 120\n"
        "temperature: 0\n"
        "seed: 42\n"
        "response_format:\n  type: json_object\n"
        "providers:\n"
        "  test:\n"
        "    enabled: true\n"
        "    base_url: http://localhost/v1\n"
        "    model: test\n"
        f"    key_file: {key}\n",
        encoding="utf-8",
    )
    config = root / "config.yaml"
    config.write_text(
        f"ai_config: {providers}\n"
        "news:\n  days: 7\n  cache_dir: cache\n  refresh_hours: 6\n  per_source_limit: 100\n  timeout_seconds: 1\n",
        encoding="utf-8",
    )
    return config


def _candidate(code: str = "sh.600001") -> dict[str, object]:
    return {
        "code": code,
        "signal_date": "2026-08-14",
        "research_close": 10.0,
        "amount_cny": 200_000_000.0,
        "turn_pct": 2.0,
        "smc_gap_pct": 1.5,
        "risk_warnings": [],
    }


def _news(*titles: str) -> NewsFetchResult:
    return NewsFetchResult(
        tuple(
            NewsItem(
                "eastmoney_announcement",
                title,
                f"https://example.test/{index}",
                "2026-08-15T01:00:00+00:00",
                "2026-08-15T02:00:00+00:00",
            )
            for index, title in enumerate(titles)
        ),
        {"eastmoney_announcement": f"success:{len(titles)}"},
    )


def _ai(assessment: str = "favorable", confidence: float = 0.8) -> dict[str, object]:
    return {
        "assessment": assessment,
        "confidence": confidence,
        "catalyst_quality": "strong",
        "event_risk": "low",
        "summary": "订单与业绩预告形成可核验催化",
        "evidence": ["公告A", "公告B"],
        "risk_flags": [],
    }


def test_priority_requires_multiple_items_confidence_and_no_attention_risk() -> None:
    priority = classify_review(_candidate(), _news("签订重大订单公告", "业绩预增公告"), _ai(), "model-a")
    assert priority.review_state == "priority_review"

    attention = classify_review(_candidate(), _news("签订重大订单公告", "股东减持公告"), _ai(), "model-a")
    assert attention.review_state == "standard_review"
    assert attention.attention_terms == ("减持",)

    undated = NewsFetchResult(
        (NewsItem("google_news_rss", "重大订单", "https://example.test/a", None, "2026-08-15T02:00:00+00:00"),
         NewsItem("google_news_rss", "业绩预增", "https://example.test/b", None, "2026-08-15T02:00:00+00:00")),
        {"google_news_rss": "success:2"},
    )
    assert classify_review(_candidate(), undated, _ai(), "model-a").review_state == "standard_review"


def test_code_level_hard_risk_overrides_favorable_ai() -> None:
    row = classify_review(_candidate(), _news("公司收到立案调查告知书", "业务进展公告"), _ai(), "model-a")
    assert row.review_state == "risk_excluded"
    assert row.hard_risk_terms == ("立案调查",)


def test_low_confidence_or_single_source_adverse_ai_does_not_exclude() -> None:
    low_confidence = _ai("adverse", 0.4)
    low_confidence["event_risk"] = "low"
    assert classify_review(_candidate(), _news("主力资金小额流出"), low_confidence, "model-a").review_state == "insufficient_evidence"

    two_sources = NewsFetchResult(
        (
            NewsItem("google_news_rss", "机构下调盈利预测", "https://example.test/a", "2026-08-15T01:00:00+00:00", "2026-08-15T02:00:00+00:00"),
            NewsItem("eastmoney_announcement", "限售股上市流通公告", "https://example.test/b", "2026-08-15T01:00:00+00:00", "2026-08-15T02:00:00+00:00"),
        ),
        {"google_news_rss": "success:1", "eastmoney_announcement": "success:1"},
    )
    adverse = _ai("adverse", 0.7)
    adverse["event_risk"] = "medium"
    assert classify_review(_candidate(), two_sources, adverse, "model-a").review_state == "risk_excluded"


def test_missing_news_or_ai_fails_closed() -> None:
    assert classify_review(_candidate(), _news(), None, None).review_state == "insufficient_evidence"
    assert classify_review(_candidate(), _news("普通公告"), None, None).review_state == "ai_unavailable"


def test_ai_evidence_filters_generic_industry_news_and_weak_flow_only() -> None:
    candidate = _candidate("sh.600885")
    generic = NewsItem("google_news_rss", "中报动向：QFII持仓近百股 市值合计超过230亿元", "https://example.test/generic", "2026-08-15T01:00:00+00:00", "2026-08-15T02:00:00+00:00")
    direct_flow = NewsItem("google_news_rss", "股票行情快报：宏发股份（600885）8月10日主力资金净卖出2114.85万元", "https://example.test/flow", "2026-08-15T01:00:00+00:00", "2026-08-15T02:00:00+00:00")
    assert filter_ai_evidence(candidate, (generic, direct_flow)) == ()

    announcement = NewsItem("eastmoney_announcement", "宏发股份:关于控股股东部分股份解质押的公告", "https://example.test/notice", "2026-08-15T01:00:00+00:00", "2026-08-15T02:00:00+00:00")
    assert filter_ai_evidence(candidate, (generic, direct_flow, announcement)) == (announcement,)


def test_single_weak_flow_title_is_insufficient_even_with_ai() -> None:
    weak_flow = NewsFetchResult(
        (NewsItem("google_news_rss", "金房能源（001210）8月13日主力资金净卖出319.19万元", "https://example.test/flow", "2026-08-15T01:00:00+00:00", "2026-08-15T02:00:00+00:00"),),
        {"google_news_rss": "success:1"},
    )
    assert classify_review(_candidate("sz.001210"), weak_flow, _ai("adverse", 0.9), "model-a").review_state == "insufficient_evidence"


def test_terminal_review_card_is_watchlist_friendly() -> None:
    card = _format_review_card(1, {
        "code": "sh.600001",
        "review_state": "standard_review",
        "assessment": "adverse",
        "confidence": 0.65,
        "event_risk": "medium",
        "summary": "长上影线后量能放大，新闻利弊并存，人工复核需谨慎。",
        "evidence": ["信号日K线长上影，收盘靠近低位", "公告包含资产减值准备"],
        "risk_flags": ["long_upper_shadow", "asset_impairment"],
    })
    assert "谨慎观察 / 偏负面" in card
    assert "技术：" in card
    assert "新闻：" in card
    assert "风险：" in card
    assert "结论：" in card
    assert "summary" not in card


def test_ai_json_parser_rejects_invalid_contract() -> None:
    assert _parse_ai_json('```json\n{"assessment":"neutral","confidence":0.4}\n```')["assessment"] == "neutral"
    with pytest.raises(ValueError):
        _parse_ai_json('{"assessment":"buy","confidence":0.9}')
    with pytest.raises(ValueError):
        _parse_ai_json('{"assessment":"neutral","confidence":1.2}')


def test_repository_news_ai_config_defaults_to_doris_qwen() -> None:
    root = Path(__file__).parents[1]
    config = load_review_config(root / "yaml" / "news_ai_review.yaml")
    ai = config["ai"]
    provider = ai["providers"][ai["provider"]]

    assert ai["provider"] == "local_finance"
    assert provider["base_url"] == "http://ts.dorisw.kdns.fr:18090/v1"
    assert provider["model"] == "Qwen3.8-27B-4bit"
    assert provider["api_key_env"] == "EDGE_SCOUT_LOCAL_AI_API_KEY"
    assert Path(provider["key_file"]) == root / "Key" / "ts.key"


def test_news_business_config_rejects_provider_override(tmp_path: Path) -> None:
    config = _review_config(tmp_path)
    config.write_text(
        config.read_text(encoding="utf-8") + "ai:\n  provider: deepseek\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="must not override"):
        load_review_config(config)


def test_provider_key_file_is_loaded(tmp_path: Path) -> None:
    config_path = _review_config(tmp_path, enabled=True)
    config = load_review_config(config_path)
    client = build_ai_client(config)
    assert client is not None
    assert client.api_key == "test-secret"


def test_news_cache_reuses_all_recent_items_without_network(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cache_dir = tmp_path / "cache"
    now = datetime.now(timezone.utc)
    items = [
        NewsItem("source_a", f"新闻{index}", f"https://example.test/{index}", (now - timedelta(days=index % 7)).isoformat(), now.isoformat())
        for index in range(12)
    ]
    calls = []

    def first_remote(code, config, *, retrieved_at):
        calls.append(code)
        return NewsFetchResult(tuple(items), {"source_a": "success:12"})

    monkeypatch.setattr("ashare_edge_scout.news_ai_review._fetch_news_remote", first_remote)
    config = {"days": 7, "cache_dir": str(cache_dir), "refresh_hours": 6, "per_source_limit": 100, "timeout_seconds": 1}
    first = fetch_news("sh.600001", config)
    assert len(first.items) == 12
    assert calls == ["sh.600001"]

    def no_network(*args, **kwargs):
        raise AssertionError("fresh cache must not access network")

    monkeypatch.setattr("ashare_edge_scout.news_ai_review._fetch_news_remote", no_network)
    second = fetch_news("sh.600001", config)
    assert len(second.items) == 12
    assert second.source_status == {"local_cache": "hit:12"}


def test_news_cache_removes_items_older_than_seven_days(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cache_dir = tmp_path / "cache"
    now = datetime.now(timezone.utc)
    recent = NewsItem("source_a", "七日内", "https://example.test/recent", (now - timedelta(days=6)).isoformat(), now.isoformat())
    expired = NewsItem("source_a", "超过七日", "https://example.test/old", (now - timedelta(days=8)).isoformat(), now.isoformat())
    monkeypatch.setattr(
        "ashare_edge_scout.news_ai_review._fetch_news_remote",
        lambda code, config, *, retrieved_at: NewsFetchResult((recent, expired), {"source_a": "success:2"}),
    )
    result = fetch_news("sh.600001", {"days": 7, "cache_dir": str(cache_dir), "refresh_hours": 6, "per_source_limit": 100})
    assert [item.title for item in result.items] == ["七日内"]
    cached = json.loads((cache_dir / "sh.600001.json").read_text(encoding="utf-8"))
    assert [item["title"] for item in cached["items"]] == ["七日内"]


def test_failed_initial_refresh_does_not_create_empty_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cache_dir = tmp_path / "cache"
    monkeypatch.setattr(
        "ashare_edge_scout.news_ai_review._fetch_news_remote",
        lambda code, config, *, retrieved_at: NewsFetchResult((), {"source_a": "error:TimeoutError"}),
    )
    result = fetch_news("sh.600001", {"days": 7, "cache_dir": str(cache_dir), "refresh_hours": 6, "per_source_limit": 100})
    assert result.items == ()
    assert result.source_status["local_cache"] == "miss_no_data"
    assert not (cache_dir / "sh.600001.json").exists()


class _FakeAI:
    def analyze(self, candidate, items, technical=None):
        if candidate["code"] == "sh.600002":
            raise ValueError("bad response")
        return _ai(), "fake-model"


class _FailingAI:
    def analyze(self, candidate, items, technical=None):
        raise ValueError("model unavailable")


class _CapturingAI:
    def __init__(self) -> None:
        self.item_counts: list[int] = []
        self.technical_statuses: list[str | None] = []

    def analyze(self, candidate, items, technical=None):
        self.item_counts.append(len(items))
        self.technical_statuses.append(None if technical is None else technical.status)
        return _ai(), "fake-model"


def _selection_run(root: Path) -> Path:
    run = root / "select-1"
    run.mkdir(parents=True)
    candidates = [_candidate(), _candidate("sh.600002")]
    candidates_path = run / "candidates.json"
    candidates_path.write_text(json.dumps(candidates, ensure_ascii=False), encoding="utf-8")
    digest = hashlib.sha256(candidates_path.read_bytes()).hexdigest()
    (run / "manifest.json").write_text(
        json.dumps({"files": {"candidates.json": {"sha256": digest}}}),
        encoding="utf-8",
    )
    return run


def test_review_publishes_immutable_evidence_and_binds_source(tmp_path: Path) -> None:
    selection = _selection_run(tmp_path / "selections")
    config = _review_config(tmp_path)

    result = run_news_ai_review(
        selection_root=selection.parent,
        selection_run=selection,
        output_root=tmp_path / "reviews",
        config_path=config,
        run_id="review-1",
        news_fetcher=lambda code, cfg: _news(f"{code} 签订重大订单公告", f"{code} 业绩预增公告"),
        ai_client=_FakeAI(),
    )

    rows = json.loads(result.reviews_path.read_text(encoding="utf-8"))
    summary = json.loads(result.summary_path.read_text(encoding="utf-8"))
    assert [row["review_state"] for row in rows] == ["priority_review", "ai_unavailable"]
    assert summary["source_candidates_sha256"] == hashlib.sha256((selection / "candidates.json").read_bytes()).hexdigest()
    assert summary["ai_provider_config_style"] == "ncn_ai_providers_v1"
    assert summary["ai_provider_schema"] == "ncn_ai_providers_v1"
    assert summary["ai_client_status"] == "injected"
    assert summary["ai_config_sha256"]
    assert summary["status"] == "success"
    assert summary["ai_success_count"] == 1
    assert "never backfill" in summary["causality_boundary"]
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == "ncn_smc_news_ai_review_v1"
    timestamped_name = manifest["timestamped_reviews_csv"]
    assert re.fullmatch(r"news_ai_reviews_\d{8}_\d{6}\.csv", timestamped_name)
    assert result.reviews_csv_path == result.run_directory / timestamped_name
    assert timestamped_name in manifest["files"]
    committee_name = manifest["timestamped_ai_committee_csv"]
    assert re.fullmatch(r"ai_committee_reviews_\d{8}_\d{6}\.csv", committee_name)
    assert manifest["latest_ai_committee_csv"] == "ai_committee_reviews_latest.csv"
    assert result.ai_committee_csv_path == result.run_directory / committee_name
    assert result.ai_committee_latest_csv_path == result.run_directory / "ai_committee_reviews_latest.csv"
    assert committee_name in manifest["files"]
    assert "ai_committee_reviews_latest.csv" in manifest["files"]
    assert result.ai_committee_csv_path.read_bytes() == result.ai_committee_latest_csv_path.read_bytes()
    csv_text = result.ai_committee_csv_path.read_text(encoding="utf-8")
    assert "sh.600001" in csv_text
    assert "priority_review" in csv_text
    with pytest.raises(FileExistsError):
        run_news_ai_review(
            selection_root=selection.parent,
            selection_run=selection,
            output_root=tmp_path / "reviews",
            config_path=config,
            run_id="review-1",
            news_fetcher=lambda code, cfg: _news(),
            ai_client=_FakeAI(),
        )


def test_review_cli_writes_ai_merged_human_summary(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    selection = _selection_run(tmp_path / "selections")
    config = _review_config(tmp_path)

    exit_code = review_smc_news_main([
        "--selection-root", str(selection.parent),
        "--selection-run", str(selection),
        "--output-root", str(tmp_path / "reviews"),
        "--config", str(config),
        "--run-id", "review-cli",
        "--top", "2",
    ])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "ai_committee_csv=" in output
    assert "ai_committee_latest_csv=" in output
    assert "human_review_summary_csv=" in output
    assert "SMC 派生人工复核分组" in output
    human_summary = selection / "human_review_summary.csv"
    assert human_summary.is_file()
    csv_text = human_summary.read_text(encoding="utf-8")
    assert "news_ai_merged" in csv_text
    assert "insufficient_evidence" in csv_text


def test_review_sends_every_cached_seven_day_item_to_ai(tmp_path: Path) -> None:
    selection = _selection_run(tmp_path / "selections")
    config = _review_config(tmp_path)
    all_news = _news(*(f"七日新闻{index}" for index in range(17)))
    ai = _CapturingAI()
    run_news_ai_review(
        selection_root=selection.parent,
        selection_run=selection,
        output_root=tmp_path / "reviews",
        config_path=config,
        news_fetcher=lambda code, cfg: all_news,
        ai_client=ai,
    )
    assert ai.item_counts == [17, 17]


def test_review_uses_daily_kline_context_when_news_is_filtered_out(tmp_path: Path) -> None:
    selection = _selection_run(tmp_path / "selections")
    config = _review_config(tmp_path)
    data_root = tmp_path / "data"
    data_root.mkdir()
    import pandas as pd

    pd.DataFrame([
        {"code": "sh.600001", "date": "2026-08-11", "open": 9.8, "high": 10.2, "low": 9.7, "close": 10.0, "preclose": 9.7, "volume": 1000, "amount": 10000, "turn": 1.0, "tradestatus": "1", "isST": "0"},
        {"code": "sh.600001", "date": "2026-08-12", "open": 10.0, "high": 10.4, "low": 9.9, "close": 10.2, "preclose": 10.0, "volume": 1200, "amount": 12000, "turn": 1.1, "tradestatus": "1", "isST": "0"},
        {"code": "sh.600001", "date": "2026-08-13", "open": 10.2, "high": 10.5, "low": 10.0, "close": 10.1, "preclose": 10.2, "volume": 900, "amount": 9000, "turn": 0.9, "tradestatus": "1", "isST": "0"},
        {"code": "sh.600001", "date": "2026-08-14", "open": 9.9, "high": 10.6, "low": 9.8, "close": 10.5, "preclose": 10.1, "volume": 1500, "amount": 15000, "turn": 1.4, "tradestatus": "1", "isST": "0"},
    ]).to_parquet(data_root / "sh.600001.parquet", index=False)
    pd.DataFrame([
        {"code": "sh.600002", "date": "2026-08-14", "open": 9.8, "high": 10.1, "low": 9.7, "close": 10.0, "preclose": 9.8, "volume": 1000, "amount": 10000, "turn": 1.0, "tradestatus": "1", "isST": "0"},
    ]).to_parquet(data_root / "sh.600002.parquet", index=False)
    ai = _CapturingAI()
    result = run_news_ai_review(
        selection_root=selection.parent,
        selection_run=selection,
        output_root=tmp_path / "reviews",
        config_path=config,
        data_root=data_root,
        news_fetcher=lambda code, cfg: NewsFetchResult((NewsItem("google_news_rss", "股票行情快报：测试股（600001）主力资金净卖出", "https://example.test/flow", "2026-08-15T01:00:00+00:00", "2026-08-15T02:00:00+00:00"),), {"google_news_rss": "success:1"}),
        ai_client=ai,
    )
    assert ai.item_counts == [0, 0]
    assert ai.technical_statuses == ["ok", "ok"]
    records = json.loads(result.news_path.read_text(encoding="utf-8"))
    assert records[0]["ai_evidence_items"] == []
    assert records[0]["technical_context"]["status"] == "ok"
    assert records[0]["technical_context"]["recent_daily_bars"][-1]["date"] == "2026-08-14"


def test_technical_only_ai_failure_is_not_clean_success(tmp_path: Path) -> None:
    selection = _selection_run(tmp_path / "selections")
    config = _review_config(tmp_path)
    data_root = tmp_path / "data"
    data_root.mkdir()
    import pandas as pd

    rows = [
        {"code": "sh.600001", "date": "2026-08-14", "open": 9.9, "high": 10.6, "low": 9.8, "close": 10.5, "preclose": 10.1, "volume": 1500, "amount": 15000, "turn": 1.4, "tradestatus": "1", "isST": "0"},
        {"code": "sh.600002", "date": "2026-08-14", "open": 9.8, "high": 10.1, "low": 9.7, "close": 10.0, "preclose": 9.8, "volume": 1000, "amount": 10000, "turn": 1.0, "tradestatus": "1", "isST": "0"},
    ]
    pd.DataFrame([rows[0]]).to_parquet(data_root / "sh.600001.parquet", index=False)
    pd.DataFrame([rows[1]]).to_parquet(data_root / "sh.600002.parquet", index=False)

    result = run_news_ai_review(
        selection_root=selection.parent,
        selection_run=selection,
        output_root=tmp_path / "reviews",
        config_path=config,
        data_root=data_root,
        news_fetcher=lambda code, cfg: _news(),
        ai_client=_FailingAI(),
    )

    summary = json.loads(result.summary_path.read_text(encoding="utf-8"))
    assert summary["status"] == "technical_only_ai_failed"
    assert summary["ai_attempt_count"] == 2
    assert summary["ai_success_count"] == 0
    assert summary["technical_context_candidate_count"] == 2


def test_news_review_reports_progress(tmp_path: Path) -> None:
    selection = _selection_run(tmp_path / "selections")
    config = _review_config(tmp_path)
    events: list[tuple[int, int, str, str]] = []
    run_news_ai_review(
        selection_root=selection.parent,
        selection_run=selection,
        output_root=tmp_path / "reviews",
        config_path=config,
        news_fetcher=lambda code, cfg: _news(f"{code} 普通公告"),
        ai_client=_CapturingAI(),
        progress=lambda index, total, code, stage: events.append((index, total, code, stage)),
    )
    stages = [event[3] for event in events]
    assert stages.count("fetch") == 2
    assert stages.count("ai") == 2
    assert stages.count("standard_review") == 2


def test_selection_manifest_tampering_is_rejected(tmp_path: Path) -> None:
    selection = _selection_run(tmp_path / "selections")
    (selection / "candidates.json").write_text("[]", encoding="utf-8")
    config = _review_config(tmp_path)
    with pytest.raises(ValueError, match="hash"):
        run_news_ai_review(
            selection_root=selection.parent,
            selection_run=selection,
            output_root=tmp_path / "reviews",
            config_path=config,
        )


class _FailingAI:
    def analyze(self, candidate, items, technical=None):
        raise AIRequestError(503, '{"error":"model unavailable"}')


def test_all_ai_failures_publish_partial_status_and_diagnostic(tmp_path: Path) -> None:
    selection = _selection_run(tmp_path / "selections")
    config = _review_config(tmp_path, enabled=True)
    result = run_news_ai_review(
        selection_root=selection.parent,
        selection_run=selection,
        output_root=tmp_path / "reviews",
        config_path=config,
        news_fetcher=lambda code, cfg: _news("普通公告"),
        ai_client=_FailingAI(),
    )
    summary = json.loads(result.summary_path.read_text(encoding="utf-8"))
    assert summary["status"] == "partial"
    assert summary["ai_success_count"] == 0
    assert set(summary["ai_error_counts"].values()) == {'http_503:{"error":"model unavailable"}'}
