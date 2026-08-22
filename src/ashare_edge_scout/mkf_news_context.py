"""CNstock-compatible deterministic news context for MKF AI review."""

from __future__ import annotations

import json
import os
import re
import shutil
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

import yaml

NO_NEWS_TEXT = "暂无新闻数据"
DEFAULT_FATAL_RISK_WORDS = (
    "收到立案告知书",
    "退市整理期",
    "强制退市",
    "财务造假被罚",
    "停牌核查",
    "证监会处罚",
)
DEFAULT_ATTENTION_WORDS = (
    "立案",
    "减持",
    "警示",
    "违规",
    "处罚",
    "问询",
    "内幕交易",
    "暴雷",
    "限售股解禁",
)


@dataclass(frozen=True)
class MkfNewsContext:
    code: str
    normalized_code: str | None
    em_code: str | None
    date: str
    cache_path: str | None
    cache_status: str
    source_status: Mapping[str, str]
    news_txt: str
    fatal_risks: tuple[str, ...]
    attn_risks: tuple[str, ...]
    config: Mapping[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def default_mkf_news_config(project_root: Path) -> dict[str, Any]:
    return {
        "ENABLED": True,
        "FETCH_ONLINE_BY_DEFAULT": True,
        "NEWS_LIMIT": 5,
        "NEWS_DAYS": 7,
        "ENABLE_NEWS_CACHE": True,
        "NEWS_CACHE_DIR": "./Message",
        "ENABLE_AUTO_CLEANUP": True,
        "CACHE_RETENTION_DAYS": 7,
        "ENABLE_GOOGLE_NEWS": True,
        "ENABLE_EASTMONEY_NEWS": True,
        "ENABLE_EASTMONEY_ANNOUNCEMENTS": True,
        "FATAL_RISK_WORDS": list(DEFAULT_FATAL_RISK_WORDS),
        "ATTENTION_WORDS": list(DEFAULT_ATTENTION_WORDS),
        "_resolved_news_cache_dir": str((project_root / "Message").resolve()),
    }


def load_mkf_news_config(path: Path, *, project_root: Path | None = None) -> dict[str, Any]:
    root = project_root or path.resolve().parents[1]
    config = default_mkf_news_config(root)
    if path.is_file():
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("MKF news context config must be a mapping")
        for key, value in payload.items():
            config[str(key)] = value
    cache_dir = Path(str(config.get("NEWS_CACHE_DIR") or "./Message")).expanduser()
    if not cache_dir.is_absolute():
        cache_dir = root / cache_dir
    config["_resolved_news_cache_dir"] = str(cache_dir.resolve())
    config["_config_path"] = str(path)
    if int(config.get("NEWS_DAYS", 7)) != 7:
        raise ValueError("MKF CNstock news context requires NEWS_DAYS=7")
    if int(config.get("NEWS_LIMIT", 5)) < 1:
        raise ValueError("MKF CNstock news context requires NEWS_LIMIT >= 1")
    if int(config.get("CACHE_RETENTION_DAYS", 7)) != 7:
        raise ValueError("MKF CNstock news context requires CACHE_RETENTION_DAYS=7")
    return config


def normalize_cnstock_code(code: str) -> str | None:
    text = str(code or "").strip().lower()
    match = re.search(r"(sh|sz|bj)[.\-_]?(\d{6})", text)
    if match:
        return f"{match.group(1)}.{match.group(2)}"
    digits = re.sub(r"\D", "", text)
    if len(digits) != 6:
        return None
    if digits.startswith(("6", "9")):
        return f"sh.{digits}"
    if digits.startswith(("0", "2", "3")):
        return f"sz.{digits}"
    if digits.startswith(("4", "8")):
        return f"bj.{digits}"
    return None


def em_code_from_normalized(normalized_code: str | None) -> str | None:
    if not normalized_code:
        return None
    match = re.search(r"(\d{6})$", normalized_code)
    return match.group(1) if match else None


def cache_file_for_code(code: str, config: Mapping[str, Any], *, today: date | None = None) -> Path | None:
    normalized = normalize_cnstock_code(code)
    if not normalized:
        return None
    day = today or date.today()
    cache_dir = Path(str(config.get("_resolved_news_cache_dir") or config.get("NEWS_CACHE_DIR") or "Message"))
    return cache_dir / f"{normalized}_{day:%Y%m%d}.json"


def _cache_payload(news_txt: str, fatal_risks: tuple[str, ...], attn_risks: tuple[str, ...], *, today: date) -> dict[str, Any]:
    return {
        "date": today.isoformat(),
        "news_txt": news_txt,
        "fatal_risks": list(fatal_risks),
        "attn_risks": list(attn_risks),
    }


def _load_cache(path: Path, *, today: date) -> tuple[str, tuple[str, ...], tuple[str, ...]] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict) or payload.get("date") != today.isoformat():
        return None
    return (
        str(payload.get("news_txt") or NO_NEWS_TEXT),
        tuple(str(item) for item in payload.get("fatal_risks") or ()),
        tuple(str(item) for item in payload.get("attn_risks") or ()),
    )


def _write_cache(path: Path, news_txt: str, fatal_risks: tuple[str, ...], attn_risks: tuple[str, ...], *, today: date) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(_cache_payload(news_txt, fatal_risks, attn_risks, today=today), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _extract_risks(news_txt: str, config: Mapping[str, Any]) -> tuple[tuple[str, ...], tuple[str, ...]]:
    fatal_words = tuple(str(item) for item in config.get("FATAL_RISK_WORDS") or DEFAULT_FATAL_RISK_WORDS)
    attention_words = tuple(str(item) for item in config.get("ATTENTION_WORDS") or DEFAULT_ATTENTION_WORDS)
    fatal = tuple(word for word in fatal_words if word and word in news_txt)
    attention = tuple(word for word in attention_words if word and word in news_txt)
    return fatal, attention


def _fetch_google_news(em_code: str, config: Mapping[str, Any]) -> tuple[list[str], str]:
    days = int(config.get("NEWS_DAYS", 7))
    limit = int(config.get("NEWS_LIMIT", 5))
    query_code = str(config.get("_google_query_code") or em_code)
    query = urllib.parse.quote(f"{query_code} A股 when:{days}d")
    url = f"https://news.google.com/rss/search?q={query}&hl=zh-CN&gl=CN&ceid=CN:zh-CN"
    timeout = float(config.get("TIMEOUT_SECONDS", 8) or 8)
    request = urllib.request.Request(url, headers={"User-Agent": "NCN-MKF-News/1.0"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        content = response.read()
    root = ET.fromstring(content)
    titles = []
    for item in root.findall(".//item")[:limit]:
        title = item.findtext("title")
        if title:
            titles.append(f"[📰 Google] {title.strip()}")
    return titles, f"success:{len(titles)}"


def _fetch_eastmoney_stock_news(em_code: str, config: Mapping[str, Any]) -> tuple[list[str], str]:
    limit = int(config.get("NEWS_LIMIT", 5))
    try:
        import akshare as ak  # type: ignore[import-not-found]
    except Exception as exc:
        return [], f"error:{type(exc).__name__}"
    try:
        data = ak.stock_news_em(symbol=em_code)
    except Exception as exc:
        return [], f"error:{type(exc).__name__}"
    if not hasattr(data, "columns") or "新闻标题" not in data.columns:
        return [], "error:missing_column"
    titles = [f"[📈 东方财富] {str(title).strip()}" for title in data["新闻标题"].head(limit).tolist() if str(title).strip()]
    return titles, f"success:{len(titles)}"


def _fetch_eastmoney_announcements(em_code: str, config: Mapping[str, Any]) -> tuple[list[str], str]:
    limit = int(config.get("NEWS_LIMIT", 5))
    timeout = float(config.get("TIMEOUT_SECONDS", 8) or 8)
    url = (
        "https://np-anotice-stock.eastmoney.com/api/security/ann?"
        f"sr=-1&page_size={limit}&page_index=1&ann_type=A&stock_list={em_code}&f_node=0&s_node=0"
    )
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://data.eastmoney.com/"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    notices = ((payload.get("data") or {}).get("list") or []) if isinstance(payload, dict) else []
    titles = []
    for notice in notices[:limit]:
        if isinstance(notice, Mapping) and str(notice.get("title") or "").strip():
            titles.append(f"[📋 公告] {str(notice['title']).strip()}")
    return titles, f"success:{len(titles)}"


def _fetch_news_multi_source(em_code: str, config: Mapping[str, Any]) -> tuple[str, dict[str, str]]:
    sources = (
        ("google_news_rss", bool(config.get("ENABLE_GOOGLE_NEWS", True)), _fetch_google_news),
        ("eastmoney_stock_news", bool(config.get("ENABLE_EASTMONEY_NEWS", True)), _fetch_eastmoney_stock_news),
        ("eastmoney_announcement", bool(config.get("ENABLE_EASTMONEY_ANNOUNCEMENTS", True)), _fetch_eastmoney_announcements),
    )
    titles: list[str] = []
    status: dict[str, str] = {}
    for name, enabled, fetcher in sources:
        if not enabled:
            status[name] = "disabled"
            continue
        try:
            fetched, source_status = fetcher(em_code, config)
        except (OSError, TimeoutError, urllib.error.URLError, ET.ParseError, json.JSONDecodeError) as exc:
            fetched, source_status = [], f"error:{type(exc).__name__}"
        titles.extend(fetched)
        status[name] = source_status
    news_txt = "\n".join(title for title in titles if title.strip()) or NO_NEWS_TEXT
    return news_txt, status


def build_mkf_news_context(code: str, config: Mapping[str, Any], *, today: date | None = None) -> MkfNewsContext:
    day = today or date.today()
    enabled = bool(config.get("ENABLED", True))
    normalized = normalize_cnstock_code(code)
    em_code = em_code_from_normalized(normalized)
    cache_path = cache_file_for_code(code, config, today=day)
    public_config = {
        "NEWS_LIMIT": int(config.get("NEWS_LIMIT", 5)),
        "NEWS_DAYS": int(config.get("NEWS_DAYS", 7)),
        "ENABLE_NEWS_CACHE": bool(config.get("ENABLE_NEWS_CACHE", True)),
        "NEWS_CACHE_DIR": str(config.get("NEWS_CACHE_DIR", "./Message")),
        "ENABLE_AUTO_CLEANUP": bool(config.get("ENABLE_AUTO_CLEANUP", True)),
        "CACHE_RETENTION_DAYS": int(config.get("CACHE_RETENTION_DAYS", 7)),
        "FETCH_ONLINE_BY_DEFAULT": bool(config.get("FETCH_ONLINE_BY_DEFAULT", True)),
    }
    if not enabled:
        return MkfNewsContext(code, normalized, em_code, day.isoformat(), str(cache_path) if cache_path else None, "disabled", {}, NO_NEWS_TEXT, (), (), public_config)
    if not normalized or not em_code or cache_path is None:
        return MkfNewsContext(code, normalized, em_code, day.isoformat(), None, "invalid_code", {}, NO_NEWS_TEXT, (), (), public_config)
    if bool(config.get("ENABLE_AUTO_CLEANUP", True)):
        cleanup_old_cache(config, today=day)
    if bool(config.get("ENABLE_NEWS_CACHE", True)) and cache_path.is_file():
        cached = _load_cache(cache_path, today=day)
        if cached is not None:
            news_txt, fatal, attention = cached
            return MkfNewsContext(code, normalized, em_code, day.isoformat(), str(cache_path), "hit", {}, news_txt, fatal, attention, public_config)
    if not bool(config.get("FETCH_ONLINE_BY_DEFAULT", True)):
        return MkfNewsContext(code, normalized, em_code, day.isoformat(), str(cache_path), "miss_no_fetch", {}, NO_NEWS_TEXT, (), (), public_config)
    fetch_config = dict(config)
    fetch_config["_google_query_code"] = normalized
    news_txt, source_status = _fetch_news_multi_source(em_code, fetch_config)
    fatal, attention = _extract_risks(news_txt, config)
    all_failed = source_status and all(value.startswith("error:") or value == "disabled" for value in source_status.values())
    if bool(config.get("ENABLE_NEWS_CACHE", True)) and not all_failed:
        _write_cache(cache_path, news_txt, fatal, attention, today=day)
        cache_status = "refreshed" if news_txt != NO_NEWS_TEXT else "refreshed_no_data"
    else:
        cache_status = "miss_no_data" if news_txt == NO_NEWS_TEXT else "refreshed_no_cache"
    return MkfNewsContext(code, normalized, em_code, day.isoformat(), str(cache_path), cache_status, source_status, news_txt, fatal, attention, public_config)


def fetch_and_check_news(code: str, config: Mapping[str, Any], *, today: date | None = None) -> tuple[str, list[str], list[str]]:
    context = build_mkf_news_context(code, config, today=today)
    return context.news_txt, list(context.fatal_risks), list(context.attn_risks)


def cleanup_old_cache(config: Mapping[str, Any], *, today: date | None = None) -> int:
    cache_dir = Path(str(config.get("_resolved_news_cache_dir") or config.get("NEWS_CACHE_DIR") or "Message"))
    if not cache_dir.is_dir():
        return 0
    day = today or date.today()
    retention = int(config.get("CACHE_RETENTION_DAYS", 7))
    removed = 0
    for path in cache_dir.glob("*.json"):
        should_remove = False
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            parsed = datetime.strptime(str(payload.get("date") or ""), "%Y-%m-%d").date()
            should_remove = (day - parsed).days > retention
        except Exception:
            try:
                modified = datetime.fromtimestamp(path.stat().st_mtime).date()
                should_remove = (day - modified).days > retention
            except OSError:
                should_remove = False
        if should_remove:
            try:
                path.unlink()
                removed += 1
            except OSError:
                pass
    return removed


def reset_news_cache_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
