"""Experimental news and AI review for immutable SMC selection runs."""

from __future__ import annotations

import hashlib
import csv
import json
import os
import re
import shutil
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from .ai_providers import (
    AIProviderConfig,
    AIRequestError,
    OpenAICompatibleClient as SharedOpenAICompatibleClient,
    build_ai_client as build_shared_ai_client,
    forbid_business_ai_overrides,
    load_ai_provider_config,
    resolve_ai_config_path,
)
from .data.data_sources import load_stock_records
from .research_nextday_validation import candlestick_masks


HARD_RISK_TERMS = (
    "立案调查",
    "立案告知",
    "终止上市",
    "退市风险警示",
    "重大违法",
    "暂停上市",
)
ATTENTION_TERMS = (
    "减持",
    "问询函",
    "监管函",
    "行政处罚",
    "异常波动",
    "业绩预亏",
    "业绩下降",
    "商誉减值",
    "诉讼",
    "冻结",
    "质押",
    "澄清公告",
)
VALID_ASSESSMENTS = {"favorable", "neutral", "adverse", "insufficient"}
WEAK_MARKET_FLOW_TERMS = (
    "主力资金",
    "资金净流",
    "资金流出",
    "资金流入",
    "净买入",
    "净卖出",
    "行情快报",
)


@dataclass(frozen=True)
class NewsItem:
    source: str
    title: str
    url: str
    published_at: str | None
    retrieved_at: str


@dataclass(frozen=True)
class NewsFetchResult:
    items: tuple[NewsItem, ...]
    source_status: Mapping[str, str]


@dataclass(frozen=True)
class TechnicalContext:
    status: str
    signal_date: str
    recent_daily_bars: tuple[Mapping[str, Any], ...]
    candlestick_patterns: tuple[str, ...]
    risk_warnings: tuple[str, ...]
    candle_summary: Mapping[str, Any]


@dataclass(frozen=True)
class NewsReviewRow:
    code: str
    signal_date: str
    review_state: str
    assessment: str
    confidence: float
    catalyst_quality: str
    event_risk: str
    summary: str
    evidence: tuple[str, ...]
    risk_flags: tuple[str, ...]
    hard_risk_terms: tuple[str, ...]
    attention_terms: tuple[str, ...]
    news_count: int
    source_count: int
    model: str | None
    experimental_unvalidated: bool = True


@dataclass(frozen=True)
class NewsReviewResult:
    run_directory: Path
    reviews_path: Path
    reviews_csv_path: Path
    ai_committee_csv_path: Path
    ai_committee_latest_csv_path: Path
    news_path: Path
    summary_path: Path
    manifest_path: Path
    priority_review_count: int
    risk_excluded_count: int


class OpenAICompatibleClient(SharedOpenAICompatibleClient):
    def __init__(self, *, base_url: str, api_key: str, model: str, timeout_seconds: float, provider: str = "injected", temperature: float = 0, seed: int | None = 42, response_format: Mapping[str, Any] | None = None, extra_options: Mapping[str, Any] | None = None):
        super().__init__(provider=provider, base_url=base_url, api_key=api_key, model=model, timeout_seconds=timeout_seconds, temperature=temperature, seed=seed, response_format=response_format, extra_options=extra_options)

    def _request_json(self, path: str, payload: Mapping[str, Any] | None = None) -> Any:
        return self.request_json(path, payload, user_agent="NCN-News-Review/1.0")

    def analyze(
        self,
        candidate: Mapping[str, Any],
        items: Sequence[NewsItem],
        technical: TechnicalContext | None = None,
    ) -> tuple[dict[str, Any], str]:
        model = self.resolved_model(user_agent="NCN-News-Review/1.0")
        news_lines = [
            {
                "source": item.source,
                "published_at": item.published_at,
                "title": item.title,
                "url": item.url,
            }
            for item in items
        ]
        system_prompt = (
            "你是A股短周期复核员，需要同时参考新闻/公告和本地日K线结构。候选已由固定SMC规则产生，"
            "你不能创造或修改技术信号。请用日本蜡烛图技术作为解释框架，重点检查实体、影线、收盘位置、"
            "量能确认、反转/持续形态和顶部风险形态；只能依据给定标题、公告和K线摘要，不得使用训练记忆、"
            "不得补充未提供事实。新闻或K线利好只能提高人工复核优先级，不能形成买入建议；明确风险应保守。"
            "summary、evidence、risk_flags 必须使用简体中文，不要输出英文解释。仅输出JSON对象，字段为assessment(favorable|neutral|adverse|insufficient)、confidence(0到1)、"
            "catalyst_quality(strong|moderate|weak|none|unknown)、event_risk(low|medium|high|unknown)、summary、"
            "evidence(字符串数组)、risk_flags(字符串数组)。证据不足时必须assessment=insufficient。"
        )
        user_payload = {
            "candidate": {
                key: candidate.get(key)
                for key in (
                    "code", "signal_date", "research_close", "amount_cny", "turn_pct",
                    "smc_gap_pct", "risk_warnings",
                )
            },
            "news": news_lines,
            "daily_kline_candlestick_context": asdict(technical) if technical is not None else None,
        }
        messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False, sort_keys=True)},
            ]
        response, model = self.chat_json(
            messages, user_agent="NCN-News-Review/1.0"
        )
        content = response["choices"][0]["message"]["content"]
        return _parse_ai_json(content), model


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_review_rows_csv(path: Path, rows: Sequence[NewsReviewRow]) -> None:
    csv_fields = list(NewsReviewRow.__dataclass_fields__)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=csv_fields)
        writer.writeheader()
        for row in rows:
            values = asdict(row)
            for field in ("evidence", "risk_flags", "hard_risk_terms", "attention_terms"):
                values[field] = "|".join(values[field])
            writer.writerow(values)


def _http_get(url: str, timeout_seconds: float) -> bytes:
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/json, application/rss+xml, application/xml", "User-Agent": "Mozilla/5.0 NCN/1.0"},
    )
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        return response.read()


def _normalise_published_at(value: Any) -> str | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    try:
        parsed = parsedate_to_datetime(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).isoformat()
    except (TypeError, ValueError, OverflowError):
        pass
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).isoformat()
    except ValueError:
        return text


def _fetch_google_news(code: str, *, days: int, limit: int, timeout_seconds: float, retrieved_at: str) -> list[NewsItem]:
    query = urllib.parse.quote_plus(f"{code.split('.')[-1]} A股 when:{days}d")
    url = f"https://news.google.com/rss/search?q={query}&hl=zh-CN&gl=CN&ceid=CN:zh-CN"
    root = ET.fromstring(_http_get(url, timeout_seconds))
    items: list[NewsItem] = []
    for node in root.findall(".//item")[:limit]:
        title = (node.findtext("title") or "").strip()
        if not title:
            continue
        items.append(NewsItem(
            source="google_news_rss",
            title=title,
            url=(node.findtext("link") or "").strip(),
            published_at=_normalise_published_at(node.findtext("pubDate")),
            retrieved_at=retrieved_at,
        ))
    return items


def _fetch_eastmoney_announcements(code: str, *, limit: int, timeout_seconds: float, retrieved_at: str) -> list[NewsItem]:
    digits = code.split(".")[-1]
    query = urllib.parse.urlencode({
        "sr": "-1", "page_size": str(limit), "page_index": "1", "ann_type": "A",
        "stock_list": digits, "f_node": "0", "s_node": "0",
    })
    url = f"https://np-anotice-stock.eastmoney.com/api/security/ann?{query}"
    payload = json.loads(_http_get(url, timeout_seconds).decode("utf-8"))
    notices = ((payload.get("data") or {}).get("list") or []) if isinstance(payload, dict) else []
    items: list[NewsItem] = []
    for notice in notices[:limit]:
        title = str(notice.get("title") or "").strip()
        if not title:
            continue
        article_code = str(notice.get("art_code") or notice.get("artCode") or "").strip()
        article_url = f"https://data.eastmoney.com/notices/detail/{digits}/{article_code}.html" if article_code else ""
        items.append(NewsItem(
            source="eastmoney_announcement",
            title=title,
            url=article_url,
            published_at=_normalise_published_at(notice.get("notice_date") or notice.get("display_time")),
            retrieved_at=retrieved_at,
        ))
    return items


def _news_timestamp(item: NewsItem) -> datetime | None:
    value = item.published_at or item.retrieved_at
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _deduplicate_recent_news(items: Sequence[NewsItem], *, cutoff: datetime) -> tuple[NewsItem, ...]:
    selected: dict[str, NewsItem] = {}
    for item in items:
        timestamp = _news_timestamp(item)
        if timestamp is None or timestamp < cutoff:
            continue
        key = re.sub(r"[\s\-—·,，。:：]", "", item.title).lower()
        if not key:
            continue
        previous = selected.get(key)
        if previous is None or (_news_timestamp(previous) or cutoff) < timestamp:
            selected[key] = item
    return tuple(sorted(selected.values(), key=lambda item: (_news_timestamp(item) or cutoff, item.source, item.title), reverse=True))


def _fetch_news_remote(code: str, config: Mapping[str, Any], *, retrieved_at: str) -> NewsFetchResult:
    days = int(config.get("days", 7))
    limit = int(config.get("per_source_limit", 100))
    timeout = float(config.get("timeout_seconds", 10))
    source_status: dict[str, str] = {}
    items: list[NewsItem] = []
    sources: list[tuple[str, Callable[[], list[NewsItem]]]] = [
        ("google_news_rss", lambda: _fetch_google_news(code, days=days, limit=limit, timeout_seconds=timeout, retrieved_at=retrieved_at)),
        ("eastmoney_announcement", lambda: _fetch_eastmoney_announcements(code, limit=limit, timeout_seconds=timeout, retrieved_at=retrieved_at)),
    ]
    for name, loader in sources:
        try:
            loaded = loader()
            items.extend(loaded)
            source_status[name] = f"success:{len(loaded)}"
        except (OSError, ValueError, KeyError, ET.ParseError, urllib.error.URLError) as exc:
            source_status[name] = f"error:{type(exc).__name__}"
    cutoff = datetime.fromisoformat(retrieved_at) - timedelta(days=days)
    return NewsFetchResult(_deduplicate_recent_news(items, cutoff=cutoff), source_status)


def _load_news_cache(path: Path, code: str) -> tuple[datetime | None, tuple[NewsItem, ...]]:
    if not path.is_file():
        return None, ()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("schema_version") != "ncn_news_cache_v1" or payload.get("code") != code:
            return None, ()
        fetched_at = datetime.fromisoformat(str(payload["fetched_at_utc"]).replace("Z", "+00:00"))
        if fetched_at.tzinfo is None:
            fetched_at = fetched_at.replace(tzinfo=timezone.utc)
        items = tuple(NewsItem(**item) for item in payload.get("items", []))
        return fetched_at.astimezone(timezone.utc), items
    except (KeyError, TypeError, ValueError, json.JSONDecodeError, OSError):
        return None, ()


def _write_news_cache(path: Path, code: str, fetched_at: str, items: Sequence[NewsItem]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    payload = {
        "schema_version": "ncn_news_cache_v1",
        "code": code,
        "fetched_at_utc": fetched_at,
        "retention_days": 7,
        "items": [asdict(item) for item in items],
    }
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def fetch_news(code: str, config: Mapping[str, Any]) -> NewsFetchResult:
    now = datetime.now(timezone.utc)
    retrieved_at = now.isoformat()
    days = int(config.get("days", 7))
    refresh_hours = float(config.get("refresh_hours", 6))
    cache_dir = Path(str(config.get("cache_dir", ".runtime/news_cache"))).expanduser()
    cache_path = cache_dir / f"{code}.json"
    fetched_at, cached_items = _load_news_cache(cache_path, code)
    cutoff = now - timedelta(days=days)
    cached_items = _deduplicate_recent_news(cached_items, cutoff=cutoff)
    if fetched_at is not None and now - fetched_at < timedelta(hours=refresh_hours):
        return NewsFetchResult(cached_items, {"local_cache": f"hit:{len(cached_items)}"})

    remote = _fetch_news_remote(code, config, retrieved_at=retrieved_at)
    source_success = any(str(status).startswith("success:") for status in remote.source_status.values())
    if not source_success and cached_items:
        statuses = {**dict(remote.source_status), "local_cache": f"stale_fallback:{len(cached_items)}"}
        return NewsFetchResult(cached_items, statuses)
    if not source_success:
        statuses = {**dict(remote.source_status), "local_cache": "miss_no_data"}
        return NewsFetchResult((), statuses)
    merged = _deduplicate_recent_news((*cached_items, *remote.items), cutoff=cutoff)
    _write_news_cache(cache_path, code, retrieved_at, merged)
    statuses = {**dict(remote.source_status), "local_cache": f"refreshed:{len(merged)}"}
    return NewsFetchResult(merged, statuses)


def _safe_float(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(result):
        return None
    return round(result, 4)


def _daily_bar_summary(row: Mapping[str, Any]) -> dict[str, Any]:
    open_ = _safe_float(row.get("open"))
    high = _safe_float(row.get("high"))
    low = _safe_float(row.get("low"))
    close = _safe_float(row.get("close"))
    volume = _safe_float(row.get("volume"))
    amount = _safe_float(row.get("amount"))
    candle_range = (high - low) if high is not None and low is not None else None
    body = abs(close - open_) if close is not None and open_ is not None else None
    close_location = ((close - low) / candle_range) if close is not None and low is not None and candle_range and candle_range > 0 else None
    upper_shadow = (high - max(open_, close)) if high is not None and open_ is not None and close is not None else None
    lower_shadow = (min(open_, close) - low) if low is not None and open_ is not None and close is not None else None
    return {
        "date": str(row.get("date"))[:10],
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
        "amount": amount,
        "body_pct_of_range": round(body / candle_range, 4) if body is not None and candle_range and candle_range > 0 else None,
        "close_location": round(close_location, 4) if close_location is not None else None,
        "upper_shadow_pct_of_range": round(upper_shadow / candle_range, 4) if upper_shadow is not None and candle_range and candle_range > 0 else None,
        "lower_shadow_pct_of_range": round(lower_shadow / candle_range, 4) if lower_shadow is not None and candle_range and candle_range > 0 else None,
        "bullish_body": bool(close is not None and open_ is not None and close > open_),
    }


def build_technical_context(candidate: Mapping[str, Any], data_root: Path | None) -> TechnicalContext:
    signal_date = str(candidate.get("signal_date") or "")
    if data_root is None:
        return TechnicalContext("disabled", signal_date, (), (), tuple(candidate.get("risk_warnings") or ()), {})
    try:
        records = load_stock_records(str(candidate.get("code", "")), data_root)
        data = pd.DataFrame(records)
        data["date"] = pd.to_datetime(data.get("date"), errors="coerce").dt.normalize()
        data = data.dropna(subset=["date"]).sort_values("date", kind="stable").drop_duplicates("date", keep="last")
        signal = pd.Timestamp(signal_date)
        data = data.loc[data["date"].le(signal)].reset_index(drop=True)
        if data.empty or data.iloc[-1]["date"] != signal:
            return TechnicalContext("missing_signal_bar", signal_date, (), (), tuple(candidate.get("risk_warnings") or ()), {})
        candle = candlestick_masks(data)
        row_index = data.index[-1]
        patterns = tuple(name for name, mask in candle.items() if bool(mask.loc[row_index]))
        recent = tuple(_daily_bar_summary(row) for row in data.tail(8).to_dict("records"))
        latest = recent[-1] if recent else {}
        summary = {
            "source": "local_adjusted_daily_bars_through_signal_date",
            "method_reference": "Japanese Candlestick Charting Techniques style OHLC shape review",
            "signal_bar": latest,
            "pattern_count": len(patterns),
        }
        return TechnicalContext("ok", signal_date, recent, patterns, tuple(candidate.get("risk_warnings") or ()), summary)
    except Exception as exc:
        return TechnicalContext(f"error:{type(exc).__name__}", signal_date, (), (), tuple(candidate.get("risk_warnings") or ()), {})


def _candidate_names(candidate: Mapping[str, Any]) -> tuple[str, ...]:
    names: list[str] = []
    for key in ("name", "stock_name", "display_name"):
        value = str(candidate.get(key) or "").strip()
        if value:
            names.append(value)
    return tuple(dict.fromkeys(names))


def _is_weak_market_flow_title(title: str) -> bool:
    return any(term in title for term in WEAK_MARKET_FLOW_TERMS)


def _title_mentions_candidate(title: str, candidate: Mapping[str, Any]) -> bool:
    digits = str(candidate.get("code") or "").split(".")[-1]
    if digits and digits in title:
        return True
    return any(name in title for name in _candidate_names(candidate))


def filter_ai_evidence(candidate: Mapping[str, Any], items: Sequence[NewsItem]) -> tuple[NewsItem, ...]:
    return tuple(
        item for item in items
        if not _is_weak_market_flow_title(item.title)
        and (item.source == "eastmoney_announcement" or _title_mentions_candidate(item.title, candidate))
    )


def _material_news_counts(items: Sequence[NewsItem]) -> tuple[int, int, int]:
    material_items = tuple(item for item in items if not _is_weak_market_flow_title(item.title))
    source_count = len({item.source for item in material_items})
    dated_news_count = sum(bool(item.published_at) for item in material_items)
    return len(material_items), source_count, dated_news_count


def _parse_ai_json(content: Any) -> dict[str, Any]:
    text = str(content or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("AI response contains no JSON object")
    parsed = json.loads(text[start:end + 1])
    if not isinstance(parsed, dict):
        raise ValueError("AI response is not an object")
    assessment = str(parsed.get("assessment", "")).lower()
    if assessment not in VALID_ASSESSMENTS:
        raise ValueError("AI assessment is invalid")
    confidence = float(parsed.get("confidence", 0))
    if not 0 <= confidence <= 1:
        raise ValueError("AI confidence is outside [0, 1]")
    parsed["assessment"] = assessment
    parsed["confidence"] = confidence
    return parsed


def _string_tuple(value: Any, *, maximum: int = 8) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(str(item).strip()[:300] for item in value[:maximum] if str(item).strip())


def classify_review(
    candidate: Mapping[str, Any],
    news: NewsFetchResult,
    ai_result: Mapping[str, Any] | None,
    model: str | None,
    technical: TechnicalContext | None = None,
) -> NewsReviewRow:
    titles = "\n".join(item.title for item in news.items)
    hard_terms = tuple(term for term in HARD_RISK_TERMS if term in titles)
    attention_terms = tuple(term for term in ATTENTION_TERMS if term in titles)
    material_news_count, material_source_count, material_dated_count = _material_news_counts(news.items)
    source_count = len({item.source for item in news.items})
    has_technical_context = technical is not None and technical.status == "ok" and bool(technical.recent_daily_bars)
    if hard_terms:
        state = "risk_excluded"
    elif (not news.items and not has_technical_context) or (news.items and material_news_count == 0):
        state = "insufficient_evidence"
    elif ai_result is None:
        state = "ai_unavailable"
    elif str(ai_result.get("event_risk", "")).lower() == "high" or (
        ai_result["assessment"] == "adverse"
        and float(ai_result["confidence"]) >= 0.70
        and material_dated_count >= 2
        and material_source_count >= 2
    ):
        state = "risk_excluded"
    elif (
        ai_result["assessment"] == "favorable"
        and float(ai_result["confidence"]) >= 0.70
        and material_news_count >= 2
        and material_dated_count >= 2
        and not attention_terms
    ):
        state = "priority_review"
    elif ai_result["assessment"] == "insufficient":
        state = "insufficient_evidence"
    else:
        state = "standard_review"

    result = ai_result or {}
    return NewsReviewRow(
        code=str(candidate["code"]),
        signal_date=str(candidate["signal_date"]),
        review_state=state,
        assessment=str(result.get("assessment", "insufficient")),
        confidence=float(result.get("confidence", 0.0)),
        catalyst_quality=str(result.get("catalyst_quality", "unknown")),
        event_risk=str(result.get("event_risk", "unknown")),
        summary=str(result.get("summary", "AI analysis unavailable" if news.items else "No material candidate-specific news evidence after filtering"))[:1000],
        evidence=_string_tuple(result.get("evidence")),
        risk_flags=_string_tuple(result.get("risk_flags")),
        hard_risk_terms=hard_terms,
        attention_terms=attention_terms,
        news_count=len(news.items),
        source_count=source_count,
        model=model,
    )


def load_review_config(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("news AI config must be a mapping")
    forbid_business_ai_overrides(payload, source=path)
    news = payload.get("news") or {}
    if not isinstance(news, dict):
        raise ValueError("news config section must be a mapping")
    if int(news.get("days", 0)) != 7:
        raise ValueError("news retention must remain exactly 7 days")
    if int(news.get("per_source_limit", 0)) < 1 or float(news.get("refresh_hours", 0)) <= 0:
        raise ValueError("news per_source_limit and refresh_hours must be positive")
    project_root = path.resolve().parents[1]
    cache_dir = Path(str(news.get("cache_dir", ".runtime/news_cache"))).expanduser()
    if not cache_dir.is_absolute():
        cache_dir = project_root / cache_dir
    news["cache_dir"] = str(cache_dir)
    ai_config_path = resolve_ai_config_path(
        payload.get("ai_config"), business_config_path=path
    )
    provider_config = load_ai_provider_config(
        ai_config_path, project_root=project_root
    )
    payload["news"] = news
    payload["ai"] = provider_config.as_mapping()
    payload["_ai_provider_config"] = provider_config
    payload["ai_config_path"] = str(provider_config.config_path)
    payload["ai_config_sha256"] = provider_config.config_sha256
    return payload


def build_ai_client(config: Mapping[str, Any]) -> OpenAICompatibleClient | None:
    provider_config = config.get("_ai_provider_config")
    if not isinstance(provider_config, AIProviderConfig):
        ai = config.get("ai") or {}
        config_path = ai.get("config_path") or config.get("ai_config_path")
        if not config_path:
            raise ValueError("normalized AI config is missing central config path")
        provider_config = load_ai_provider_config(Path(str(config_path)))
    shared = build_shared_ai_client(provider_config)
    if shared is None:
        return None
    return OpenAICompatibleClient(
        provider=shared.provider,
        base_url=shared.base_url,
        api_key=shared.api_key,
        model=shared.model,
        timeout_seconds=shared.timeout_seconds,
        temperature=shared.temperature,
        seed=shared.seed,
        response_format=shared.response_format,
        extra_options=shared.extra_options,
    )


def resolve_selection_run(selection_root: Path, selection_run: Path | None) -> Path:
    if selection_run is not None:
        return selection_run.resolve()
    runs = sorted(
        path for path in selection_root.glob("select-*")
        if path.is_dir() and (path / "candidates.json").is_file() and (path / "manifest.json").is_file()
    )
    if not runs:
        raise FileNotFoundError(f"no immutable SMC selection run under {selection_root}")
    return runs[-1].resolve()


def _validate_selection_run(run: Path) -> tuple[list[dict[str, Any]], str]:
    candidates_path = run / "candidates.json"
    manifest_path = run / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected = (((manifest.get("files") or {}).get("candidates.json") or {}).get("sha256"))
    actual = _sha256(candidates_path)
    if expected != actual:
        raise ValueError("selection candidates.json hash does not match manifest")
    candidates = json.loads(candidates_path.read_text(encoding="utf-8"))
    if not isinstance(candidates, list) or any(not isinstance(row, dict) for row in candidates):
        raise ValueError("selection candidates.json must be a list of objects")
    return candidates, actual


def run_news_ai_review(
    *,
    selection_root: Path,
    output_root: Path,
    config_path: Path,
    selection_run: Path | None = None,
    run_id: str | None = None,
    data_root: Path | None = None,
    news_fetcher: Callable[[str, Mapping[str, Any]], NewsFetchResult] = fetch_news,
    ai_client: Any | None = None,
    progress: Callable[[int, int, str, str], None] | None = None,
) -> NewsReviewResult:
    config = load_review_config(config_path)
    if data_root is None:
        data_root = config_path.resolve().parents[1] / "PFrontStockData"
    source_run = resolve_selection_run(selection_root, selection_run)
    candidates, candidates_sha = _validate_selection_run(source_run)
    client = ai_client if ai_client is not None else build_ai_client(config)
    rows: list[NewsReviewRow] = []
    news_records: list[dict[str, Any]] = []
    ai_errors: dict[str, str] = {}
    ai_attempt_count = 0
    technical_context_candidate_count = 0
    news_ai_attempt_count = 0
    for index, candidate in enumerate(candidates, start=1):
        code = str(candidate.get("code", ""))
        if progress is not None:
            progress(index, len(candidates), code, "fetch")
        fetched = news_fetcher(code, config["news"])
        technical = build_technical_context(candidate, data_root)
        ai_result = None
        model = None
        ai_evidence = filter_ai_evidence(candidate, fetched.items)
        filtered = NewsFetchResult(ai_evidence, fetched.source_status)
        if technical.status == "ok":
            technical_context_candidate_count += 1
        if (filtered.items or technical.status == "ok") and client is not None:
            ai_attempt_count += 1
            if filtered.items:
                news_ai_attempt_count += 1
            if progress is not None:
                progress(index, len(candidates), code, "ai")
            try:
                ai_result, model = client.analyze(candidate, filtered.items, technical)
                ai_result = _parse_ai_json(json.dumps(ai_result, ensure_ascii=False))
            except (AIRequestError, KeyError, TypeError, ValueError, OSError, urllib.error.URLError) as exc:
                ai_errors[code] = str(exc) if isinstance(exc, AIRequestError) else type(exc).__name__
        row = classify_review(candidate, filtered, ai_result, model, technical)
        if progress is not None:
            progress(index, len(candidates), code, row.review_state)
        rows.append(row)
        news_records.append({
            "code": code,
            "source_status": dict(fetched.source_status),
            "items": [asdict(item) for item in fetched.items],
            "ai_evidence_items": [asdict(item) for item in filtered.items],
            "technical_context": asdict(technical),
        })

    state_order = {"priority_review": 0, "standard_review": 1, "insufficient_evidence": 2, "ai_unavailable": 3, "risk_excluded": 4}
    rows.sort(key=lambda row: (state_order[row.review_state], -row.confidence, row.code))
    actual_run_id = run_id or f"news-review-{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    output_root.mkdir(parents=True, exist_ok=True)
    destination = output_root / actual_run_id
    temporary = output_root / f".{actual_run_id}.tmp"
    if destination.exists() or temporary.exists():
        raise FileExistsError(f"news review run already exists: {destination}")
    temporary.mkdir()
    try:
        generated_at = datetime.now().astimezone()
        timestamp = generated_at.strftime('%Y%m%d_%H%M%S')
        reviews_csv_name = f"news_ai_reviews_{timestamp}.csv"
        ai_committee_csv_name = f"ai_committee_reviews_{timestamp}.csv"
        ai_committee_latest_csv_name = "ai_committee_reviews_latest.csv"
        reviews_path = temporary / "reviews.json"
        reviews_csv_path = temporary / reviews_csv_name
        ai_committee_csv_path = temporary / ai_committee_csv_name
        ai_committee_latest_csv_path = temporary / ai_committee_latest_csv_name
        news_path = temporary / "news.json"
        summary_path = temporary / "summary.json"
        reviews_path.write_text(json.dumps([asdict(row) for row in rows], ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        for csv_path in (reviews_csv_path, ai_committee_csv_path, ai_committee_latest_csv_path):
            _write_review_rows_csv(csv_path, rows)
        news_path.write_text(json.dumps(news_records, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        counts = {state: sum(row.review_state == state for row in rows) for state in state_order}
        news_candidate_count = sum(bool(record["items"]) for record in news_records)
        ai_success_count = sum(row.model is not None for row in rows)
        if client is not None and ai_attempt_count > 0 and ai_success_count == 0:
            status = "partial" if news_ai_attempt_count > 0 else "technical_only_ai_failed"
        else:
            status = "success"
        ai_config = config.get("_ai_provider_config")
        ai_mapping = config.get("ai") or {}
        ai_model = None
        if isinstance(ai_config, AIProviderConfig) and ai_config.provider in ai_config.providers:
            ai_model = ai_config.providers[ai_config.provider].get("model")
        summary = {
            "schema_version": "ncn_smc_news_ai_review_v1",
            "status": status,
            "run_id": actual_run_id,
            "timestamped_reviews_csv": reviews_csv_name,
            "timestamped_ai_committee_csv": ai_committee_csv_name,
            "latest_ai_committee_csv": ai_committee_latest_csv_name,
            "published_at_utc": _utc_now(),
            "source_selection_run": str(source_run),
            "source_candidates_sha256": candidates_sha,
            "config_path": str(config_path),
            "config_sha256": _sha256(config_path),
            "ai_config_path": str(config.get("ai_config_path") or ""),
            "ai_config_sha256": config.get("ai_config_sha256"),
            "candidate_count": len(candidates),
            "ai_provider": str(ai_mapping.get("provider", "injected_or_disabled")),
            "ai_provider_config_style": str(ai_mapping.get("provider_config_style", "ncn_ai_providers_v1")),
            "ai_provider_schema": str(ai_mapping.get("schema_version", "ncn_ai_providers_v1")),
            "ai_client_status": "injected" if ai_client is not None else ("enabled" if client is not None else "disabled"),
            "ai_model": ai_model,
            "ai_response_format": ai_mapping.get("response_format"),
            "ai_temperature": ai_mapping.get("temperature"),
            "ai_seed": ai_mapping.get("seed"),
            "news_candidate_count": news_candidate_count,
            "technical_context_candidate_count": technical_context_candidate_count,
            "ai_attempt_count": ai_attempt_count,
            "ai_success_count": ai_success_count,
            "state_counts": counts,
            "ai_error_counts": ai_errors,
            "review_order": "state_priority_then_ai_confidence_desc_then_code",
            "ai_committee_review": {
                "enabled": True,
                "artifact_schema": "ncn_smc_news_ai_committee_csv_v1",
                "source": "same_validated_news_ai_review_rows",
                "execution": "existing_single_news_kline_ai_review_no_extra_provider_call",
                "stable_latest_reference": ai_committee_latest_csv_name,
            },
            "decision_boundary": "experimental_human_review_priority_not_validated_win_probability",
            "causality_boundary": "news_visible_at_review_publication_only; never backfill historical selection precision",
            "limitations": [
                "headline_and_announcement_metadata_not_full_article_text",
                "provider_coverage_and_timestamps_are_not_exchange_sla",
                "llm_output_can_be_incorrect_or_non_reproducible",
                "priority_review_has_not_proven_higher_target_touch_precision",
                "read_only_research_not_investment_advice",
            ],
        }
        summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
        files = {
            name: {"sha256": _sha256(temporary / name)}
            for name in (
                "reviews.json",
                reviews_csv_name,
                ai_committee_csv_name,
                ai_committee_latest_csv_name,
                "news.json",
                "summary.json",
            )
        }
        manifest = {
            "schema_version": "ncn_smc_news_ai_review_v1",
            "run_id": actual_run_id,
            "source_candidates_sha256": candidates_sha,
            "timestamped_reviews_csv": reviews_csv_name,
            "timestamped_ai_committee_csv": ai_committee_csv_name,
            "latest_ai_committee_csv": ai_committee_latest_csv_name,
            "files": files,
        }
        (temporary / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
        os.replace(temporary, destination)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return NewsReviewResult(
        run_directory=destination,
        reviews_path=destination / "reviews.json",
        reviews_csv_path=destination / reviews_csv_name,
        ai_committee_csv_path=destination / ai_committee_csv_name,
        ai_committee_latest_csv_path=destination / ai_committee_latest_csv_name,
        news_path=destination / "news.json",
        summary_path=destination / "summary.json",
        manifest_path=destination / "manifest.json",
        priority_review_count=sum(row.review_state == "priority_review" for row in rows),
        risk_excluded_count=sum(row.review_state == "risk_excluded" for row in rows),
    )
