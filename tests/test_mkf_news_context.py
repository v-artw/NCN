from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from ashare_edge_scout import mkf_news_context
from ashare_edge_scout.mkf_news_context import (
    NO_NEWS_TEXT,
    build_mkf_news_context,
    cache_file_for_code,
    cleanup_old_cache,
    fetch_and_check_news,
    load_mkf_news_config,
    normalize_cnstock_code,
)


def _config(tmp_path: Path) -> dict[str, object]:
    path = tmp_path / "mkf_news_context.yaml"
    path.write_text(
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
    return load_mkf_news_config(path, project_root=tmp_path)


def test_mkf_news_config_loads_cnstock_style_defaults(tmp_path: Path) -> None:
    config = _config(tmp_path)

    assert config["NEWS_LIMIT"] == 5
    assert config["NEWS_DAYS"] == 7
    assert config["NEWS_CACHE_DIR"] == "./Message"
    assert Path(str(config["_resolved_news_cache_dir"])).name == "Message"


def test_mkf_news_normalizes_ncn_codes() -> None:
    assert normalize_cnstock_code("sh.600001") == "sh.600001"
    assert normalize_cnstock_code("SZ000001") == "sz.000001"
    assert normalize_cnstock_code("300001") == "sz.300001"
    assert normalize_cnstock_code("bj.830001") == "bj.830001"
    assert normalize_cnstock_code("bad") is None


def test_mkf_news_cache_path_and_schema(tmp_path: Path) -> None:
    config = _config(tmp_path)
    cache_path = cache_file_for_code("sh.600001", config, today=date(2026, 8, 21))
    assert cache_path == tmp_path / "Message" / "sh.600001_20260821.json"

    def fake_fetch(em_code: str, config: dict[str, object]) -> tuple[str, dict[str, str]]:
        return "[📋 公告] 公司收到立案告知书\n[📈 东方财富] 股东减持", {"fake": "success:2"}

    original = mkf_news_context._fetch_news_multi_source
    mkf_news_context._fetch_news_multi_source = fake_fetch  # type: ignore[assignment]
    try:
        context = build_mkf_news_context("sh.600001", config, today=date(2026, 8, 21))
    finally:
        mkf_news_context._fetch_news_multi_source = original  # type: ignore[assignment]

    assert context.cache_status == "refreshed"
    payload = cache_path.read_text(encoding="utf-8")
    assert '"date"' in payload
    assert '"news_txt"' in payload
    assert '"fatal_risks"' in payload
    assert '"attn_risks"' in payload
    assert context.fatal_risks == ("收到立案告知书",)
    assert context.attn_risks == ("减持",)


def test_mkf_news_same_day_cache_hit_avoids_network(tmp_path: Path) -> None:
    config = _config(tmp_path)
    cache_path = tmp_path / "Message" / "sh.600001_20260821.json"
    cache_path.parent.mkdir()
    cache_path.write_text(
        '{"date":"2026-08-21","news_txt":"[📋 公告] 已缓存","fatal_risks":[],"attn_risks":[]}\n',
        encoding="utf-8",
    )

    def fail_fetch(em_code: str, config: dict[str, object]) -> tuple[str, dict[str, str]]:
        raise AssertionError("network should not be called")

    original = mkf_news_context._fetch_news_multi_source
    mkf_news_context._fetch_news_multi_source = fail_fetch  # type: ignore[assignment]
    try:
        context = build_mkf_news_context("sh.600001", config, today=date(2026, 8, 21))
    finally:
        mkf_news_context._fetch_news_multi_source = original  # type: ignore[assignment]

    assert context.cache_status == "hit"
    assert context.news_txt == "[📋 公告] 已缓存"


def test_mkf_news_all_sources_fail_closed_without_cache(tmp_path: Path) -> None:
    config = _config(tmp_path)

    def no_data(em_code: str, config: dict[str, object]) -> tuple[str, dict[str, str]]:
        return NO_NEWS_TEXT, {"google_news_rss": "error:TimeoutError"}

    original = mkf_news_context._fetch_news_multi_source
    mkf_news_context._fetch_news_multi_source = no_data  # type: ignore[assignment]
    try:
        news_txt, fatal, attention = fetch_and_check_news("sh.600001", config, today=date(2026, 8, 21))
    finally:
        mkf_news_context._fetch_news_multi_source = original  # type: ignore[assignment]

    assert news_txt == NO_NEWS_TEXT
    assert fatal == []
    assert attention == []
    assert not (tmp_path / "Message" / "sh.600001_20260821.json").exists()


def test_mkf_news_cleanup_removes_old_cnstock_cache(tmp_path: Path) -> None:
    config = _config(tmp_path)
    cache_dir = tmp_path / "Message"
    cache_dir.mkdir()
    old_file = cache_dir / "sh.600001_20260801.json"
    old_file.write_text('{"date":"2026-08-01","news_txt":"old","fatal_risks":[],"attn_risks":[]}\n', encoding="utf-8")
    fresh_file = cache_dir / "sh.600002_20260821.json"
    fresh_file.write_text('{"date":"2026-08-21","news_txt":"fresh","fatal_risks":[],"attn_risks":[]}\n', encoding="utf-8")

    assert cleanup_old_cache(config, today=date(2026, 8, 21)) == 1
    assert not old_file.exists()
    assert fresh_file.exists()


def test_mkf_news_rejects_non_cnstock_retention(tmp_path: Path) -> None:
    path = tmp_path / "mkf_news_context.yaml"
    path.write_text("NEWS_DAYS: 5\n", encoding="utf-8")
    with pytest.raises(ValueError, match="NEWS_DAYS=7"):
        load_mkf_news_config(path, project_root=tmp_path)
