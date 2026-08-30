"""Optional read-only AI committee review for immutable MKF candidate-source runs."""

from __future__ import annotations

import csv
import hashlib
import http.client
import json
import math
import os
import re
import shutil
import urllib.error
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
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
from .signals.candle_confirm import compute_candle_confirmation_features
from .data.data_sources import load_stock_records
from .pmkf_mkf.candidates import SCHEMA_VERSION as MKF_SELECTION_SCHEMA
from .mkf_news_context import NO_NEWS_TEXT, build_mkf_news_context, load_mkf_news_config
from .research_nextday_validation import candlestick_masks

SCHEMA_VERSION = "ncn_mkf_ai_review_v3"
DEFAULT_MAX_CANDIDATES = 20
VALID_REVIEW_STATES = {"priority_research", "standard_research", "risk_attention", "insufficient_evidence", "ai_unavailable"}
FORBIDDEN_ACTION_LABELS = {"BUY", "HOLD", "AVOID", "SELL", "WAIT", "PRE-BUY", "PREBUY"}
FORBIDDEN_RESPONSE_KEYS = {
    "max_position_pct",
    "position_size",
    "order",
    "broker",
    "take_profit",
    "stop_loss",
    "pnl",
    "return_forecast",
    "target_price",
}
COMMITTEE_ROLES = (
    "technical_analyst",
    "sentiment_analyst",
    "fundamental_analyst",
    "bullish_researcher",
    "bearish_researcher",
    "chief_strategist",
    "risk_manager",
)
DEFAULT_MKF_AI_SYSTEM_PROMPT = (
    "你是A股只读研究候选的MKF AI委员会提示词角色，不是真实多代理并发投票系统。"
    "候选已经由NCN红蓝线上穿20当日及后第1/2个交易日规则产生；你不能创造、删除、修改候选，也不能改变SMC、watchlist或production。"
    "技术分析必须只使用提供的NCN English Japanese candlestick/OHLCV上下文和MKF候选快照；"
    "消息面、舆情和基本面角色只能使用提供的CNstock兼容新闻上下文news_txt、fatal_risks和attn_risks；"
    f"如果news_txt为{NO_NEWS_TEXT}，相关角色必须说明evidence unavailable。"
    "禁止使用PMKF Kalman、Futu/MHPG/DXBD/BULLCLUSTER/MFK4/GDING/BBUY/Dingdi/POWERLINE、CNstock旧交易上下文、模型外部记忆或自行联网补充事实。"
    "请在单次JSON输出中模拟technical_analyst、sentiment_analyst、fundamental_analyst、bullish_researcher、bearish_researcher、chief_strategist、risk_manager。"
    "不得编造政策、业绩、诉讼、公告、行业情绪或资金消息；未提供证据时必须说明不可得。"
    "禁止输出买入、卖出、持有、等待、下单、仓位、收益、止盈止损、目标价、P&L等操作建议；不得使用BUY/HOLD/AVOID/SELL/WAIT/PRE-BUY。"
    "仅输出JSON对象，字段为review_state(priority_research|standard_research|risk_attention|insufficient_evidence)、"
    "confidence(0到1)、research_summary、technical_observations(字符串数组)、risk_flags(字符串数组)、"
    "committee(对象，可含各角色stance和notes)、committee_disagreement_flags(字符串数组)。"
)
BULLISH_CANDLE_PATTERNS = {
    "candle_hammer",
    "candle_bullish_engulfing",
    "candle_piercing",
    "candle_morning_star",
    "candle_inverted_hammer",
    "candle_dragonfly_doji",
    "candle_bullish_harami",
    "candle_tweezer_bottom",
    "candle_three_white_soldiers",
}
BEARISH_CANDLE_PATTERNS = {
    "candle_gravestone_doji",
    "candle_bearish_harami",
    "candle_tweezer_top",
    "candle_three_black_crows",
    "candle_hanging_man",
    "candle_shooting_star",
    "candle_bearish_engulfing",
    "candle_dark_cloud_cover",
    "candle_evening_star",
}


MkfAIRequestError = AIRequestError


@dataclass(frozen=True)
class MkfAIReviewRow:
    code: str
    signal_date: str
    review_state: str
    confidence: float
    research_summary: str
    technical_observations: tuple[str, ...]
    risk_flags: tuple[str, ...]
    local_score: float
    model: str | None
    source_selection_reason: str
    committee_summary: Mapping[str, Any] | None = None
    committee_roles: tuple[str, ...] = COMMITTEE_ROLES
    technical_context_status: str = "unknown"
    candlestick_patterns: tuple[str, ...] = ()
    candle_confirm_score: float | None = None
    committee_disagreement_flags: tuple[str, ...] = ()
    news_context_status: str = "unknown"
    news_cache_status: str = "unknown"
    fatal_news_risks: tuple[str, ...] = ()
    attention_news_risks: tuple[str, ...] = ()
    experimental_unvalidated: bool = True


@dataclass(frozen=True)
class MkfAIReviewResult:
    run_directory: Path
    reviews_path: Path
    reviews_csv_path: Path
    technical_contexts_path: Path
    news_contexts_path: Path
    summary_path: Path
    manifest_path: Path
    priority_research_count: int
    risk_attention_count: int


CSV_FIELDNAMES = (
    "code",
    "signal_date",
    "review_state",
    "confidence",
    "local_score",
    "research_summary",
    "technical_observations",
    "risk_flags",
    "model",
    "source_selection_reason",
    "committee_summary",
    "committee_roles",
    "technical_context_status",
    "candlestick_patterns",
    "candle_confirm_score",
    "committee_disagreement_flags",
    "news_context_status",
    "news_cache_status",
    "fatal_news_risks",
    "attention_news_risks",
    "experimental_unvalidated",
)


class OpenAICompatibleClient(SharedOpenAICompatibleClient):
    def __init__(self, *, base_url: str, api_key: str, model: str, timeout_seconds: float, provider: str = "injected", temperature: float = 0, seed: int | None = 42, response_format: Mapping[str, Any] | None = None, extra_options: Mapping[str, Any] | None = None, system_prompt: str = DEFAULT_MKF_AI_SYSTEM_PROMPT):
        super().__init__(provider=provider, base_url=base_url, api_key=api_key, model=model, timeout_seconds=timeout_seconds, temperature=temperature, seed=seed, response_format=response_format, extra_options=extra_options)
        self.system_prompt = system_prompt

    def _request_json(self, path: str, payload: Mapping[str, Any] | None = None) -> Any:
        return self.request_json(path, payload, user_agent="NCN-MKF-AI-Committee/1.0")

    def analyze(self, candidate: Mapping[str, Any], context: Mapping[str, Any], news_context: Mapping[str, Any]) -> tuple[dict[str, Any], str]:
        model = self.resolved_model(user_agent="NCN-MKF-AI-Committee/1.0")
        user_payload = {
            "candidate": {
                key: candidate.get(key)
                for key in (
                    "code", "signal_date", "cross_date", "post_cross_lag", "research_close", "amount_cny", "turn_pct",
                    "mkf_momentum", "mkf_inter", "mkf_near", "mkf_red_cross_up_20",
                    "mkf_blue_cross_up_20", "mkf_red_blue_cross_up_20_under_80", "selection_reason",
                )
            },
            "ncn_technical_context": context,
            "cnstock_news_context": news_context,
            "committee_roles": list(COMMITTEE_ROLES),
            "allowed_review_states": sorted(VALID_REVIEW_STATES - {"ai_unavailable"}),
            "forbidden_actions": sorted(FORBIDDEN_ACTION_LABELS | FORBIDDEN_RESPONSE_KEYS),
            "boundary": {
                "scanner_selection_is_immutable": True,
                "post_selection_read_only_research_layer": True,
                "do_not_modify_smc_admission_or_ranking": True,
                "do_not_modify_watchlist_or_prospective_archive": True,
                "do_not_use_pmkf_kalman": True,
                "do_not_use_futu_fields": True,
                "not_investment_advice": True,
            },
        }
        messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False, sort_keys=True)},
            ]
        response, model = self.chat_json(
            messages, user_agent="NCN-MKF-AI-Committee/1.0"
        )
        content = response["choices"][0]["message"]["content"]
        return parse_ai_response(content), model


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _normalize_prompt_config(payload: Mapping[str, Any]) -> dict[str, Any]:
    prompt = payload.get("prompt") or {}
    if not isinstance(prompt, Mapping):
        raise ValueError("prompt config section must be a mapping")
    if "system" in prompt:
        system = str(prompt.get("system") or "").strip()
        source = "business_yaml_prompt.system"
    else:
        system = DEFAULT_MKF_AI_SYSTEM_PROMPT
        source = "module_default_prompt.system"
    if not system:
        raise ValueError("prompt.system must be a non-empty string")
    return {
        **dict(prompt),
        "system": system,
        "source": source,
        "sha256": _sha256_text(system),
    }


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_max_candidates(review: Mapping[str, Any]) -> int:
    value = int(review.get("max_candidates", DEFAULT_MAX_CANDIDATES))
    if value < 1:
        raise ValueError("review.max_candidates must be at least 1")
    return value


def _string_tuple(value: Any, *, maximum: int = 8) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(str(item).strip()[:300] for item in value[:maximum] if str(item).strip())


def _contains_forbidden_action_text(text: str) -> bool:
    return bool(re.search(r"\b(BUY|HOLD|AVOID|SELL|WAIT|PRE\s*-?\s*BUY|PREBUY)\b", text, flags=re.IGNORECASE))


def _scan_forbidden_payload(value: Any) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            key_text = str(key)
            if key_text in FORBIDDEN_RESPONSE_KEYS or _contains_forbidden_action_text(key_text):
                raise ValueError("AI response contains forbidden action label")
            _scan_forbidden_payload(child)
    elif isinstance(value, list):
        for child in value:
            _scan_forbidden_payload(child)
    elif isinstance(value, str) and _contains_forbidden_action_text(value):
        raise ValueError("AI response contains forbidden action label")


def _normalise_committee(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, Mapping):
        return None
    result: dict[str, Any] = {}
    for role in COMMITTEE_ROLES:
        raw = value.get(role)
        if not isinstance(raw, Mapping):
            continue
        notes = _string_tuple(raw.get("notes"), maximum=5)
        result[role] = {"stance": str(raw.get("stance") or "insufficient")[:80], "notes": list(notes)}
    return result or None


def parse_ai_response(content: Any) -> dict[str, Any]:
    text = str(content or "").strip()
    if _contains_forbidden_action_text(text):
        raise ValueError("AI response contains forbidden action label")
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("AI response contains no JSON object")
    parsed = json.loads(text[start:end + 1])
    if not isinstance(parsed, dict):
        raise ValueError("AI response is not an object")
    _scan_forbidden_payload(parsed)
    state = str(parsed.get("review_state", "")).strip().lower()
    if state not in (VALID_REVIEW_STATES - {"ai_unavailable"}):
        raise ValueError("AI review_state is invalid")
    confidence = float(parsed.get("confidence", 0.0))
    if not 0 <= confidence <= 1:
        raise ValueError("AI confidence is outside [0, 1]")
    parsed["review_state"] = state
    parsed["confidence"] = confidence
    parsed["committee"] = _normalise_committee(parsed.get("committee"))
    parsed["committee_disagreement_flags"] = list(_string_tuple(parsed.get("committee_disagreement_flags"), maximum=6))
    return parsed


def load_mkf_ai_config(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("MKF AI config must be a mapping")
    forbid_business_ai_overrides(payload, source=path)
    project_root = path.resolve().parents[1]
    ai_config_path = resolve_ai_config_path(
        payload.get("ai_config"), business_config_path=path
    )
    provider_config = load_ai_provider_config(
        ai_config_path, project_root=project_root
    )
    payload["ai"] = provider_config.as_mapping()
    payload["_ai_provider_config"] = provider_config
    payload["ai_config_path"] = str(provider_config.config_path)
    payload["ai_config_sha256"] = provider_config.config_sha256
    review = payload.get("review") or {}
    if not isinstance(review, dict):
        raise ValueError("review config section must be a mapping")
    review["max_candidates"] = _normalize_max_candidates(review)
    payload["review"] = review
    technical = review.get("technical_context") or {}
    if not isinstance(technical, dict):
        raise ValueError("review.technical_context must be a mapping")
    if bool(technical.get("use_pmkf_kalman", False)):
        raise ValueError("MKF AI committee must not use PMKF Kalman context")
    if bool(technical.get("use_futu_fields", False)):
        raise ValueError("MKF AI committee must not use Futu fields")
    payload["prompt"] = _normalize_prompt_config(payload)
    news_config_value = payload.get("news_config") or "yaml/mkf_news_context.yaml"
    news_config_path = Path(str(news_config_value)).expanduser()
    if not news_config_path.is_absolute():
        news_config_path = project_root / news_config_path
    news_config = load_mkf_news_config(news_config_path, project_root=project_root)
    payload["news_config_path"] = str(news_config_path)
    payload["news_config"] = news_config
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
    prompt = config.get("prompt") or {}
    system_prompt = str(prompt.get("system") or DEFAULT_MKF_AI_SYSTEM_PROMPT)
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
        system_prompt=system_prompt,
    )


def resolve_mkf_selection_run(selection_root: Path, selection_run: Path | None) -> Path:
    if selection_run is not None:
        return selection_run.resolve()
    runs = sorted(
        path for path in selection_root.glob("mkf-select-*")
        if path.is_dir() and (path / "candidates.json").is_file() and (path / "manifest.json").is_file()
    )
    if not runs:
        raise FileNotFoundError(f"no immutable MKF candidate run under {selection_root}")
    return runs[-1].resolve()


def validate_mkf_selection_run(run: Path) -> tuple[list[dict[str, Any]], str]:
    candidates_path = run / "candidates.json"
    manifest_path = run / "manifest.json"
    summary_path = run / "summary.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != MKF_SELECTION_SCHEMA:
        raise ValueError("selection run is not an MKF candidate selection")
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if summary.get("schema_version") != MKF_SELECTION_SCHEMA:
        raise ValueError("selection summary is not an MKF candidate selection")
    expected = (((manifest.get("files") or {}).get("candidates.json") or {}).get("sha256"))
    actual = _sha256(candidates_path)
    if expected != actual:
        raise ValueError("MKF candidates.json hash does not match manifest")
    candidates = json.loads(candidates_path.read_text(encoding="utf-8"))
    if not isinstance(candidates, list) or any(not isinstance(row, dict) for row in candidates):
        raise ValueError("MKF candidates.json must be a list of objects")
    return candidates, actual


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if pd.notna(result) else default


def _optional_float(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if pd.notna(result) else None


def _json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_safe(child) for key, child in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(child) for child in value]
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return value
    if isinstance(value, (int, float)):
        result = float(value) if isinstance(value, float) else int(value)
        return result if not isinstance(result, float) or math.isfinite(result) else None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if hasattr(value, "item"):
        return _json_safe(value.item())
    return str(value)


def _daily_bar_summary(row: Mapping[str, Any]) -> dict[str, Any]:
    open_ = _optional_float(row.get("open"))
    high = _optional_float(row.get("high"))
    low = _optional_float(row.get("low"))
    close = _optional_float(row.get("close"))
    volume = _optional_float(row.get("volume"))
    amount = _optional_float(row.get("amount"))
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


def _pct_change(current: pd.Series, periods: int) -> float | None:
    if len(current) <= periods:
        return None
    now = _optional_float(current.iloc[-1])
    prior = _optional_float(current.iloc[-periods - 1])
    if now is None or prior is None or prior <= 0:
        return None
    return round((now / prior - 1.0) * 100.0, 4)


def _ratio_to_tail(values: pd.Series, window: int) -> float | None:
    if len(values) < window:
        return None
    now = _optional_float(values.iloc[-1])
    mean = _optional_float(values.tail(window).mean())
    if now is None or mean is None or mean <= 0:
        return None
    return round(now / mean, 4)


def _mkf_technical_context(candidate: Mapping[str, Any], data_root: Path | None, config: Mapping[str, Any] | None = None) -> dict[str, Any]:
    technical_cfg = ((config or {}).get("review") or {}).get("technical_context") or {}
    recent_bars = int(technical_cfg.get("recent_daily_bars", 8) or 8)
    lookback_bars = max(int(technical_cfg.get("lookback_bars", 60) or 60), 20, recent_bars)
    signal_date = str(candidate.get("signal_date") or "")
    snapshot = {
        "mkf_momentum": candidate.get("mkf_momentum"),
        "mkf_inter": candidate.get("mkf_inter"),
        "mkf_near": candidate.get("mkf_near"),
        "mkf_red_cross_up_20": candidate.get("mkf_red_cross_up_20"),
        "mkf_blue_cross_up_20": candidate.get("mkf_blue_cross_up_20"),
        "mkf_red_blue_cross_up_20_under_80": candidate.get("mkf_red_blue_cross_up_20_under_80"),
    }
    base = {
        "status": "disabled" if data_root is None else "unknown",
        "signal_date": signal_date,
        "source": "local_adjusted_daily_bars_through_signal_date",
        "method_reference": "Japanese Candlestick Charting Techniques style OHLC shape review",
        "recent_daily_bars": [],
        "candlestick_patterns": [],
        "candle_confirmation": {},
        "ohlcv_indicators": {},
        "mkf_selection_snapshot": snapshot,
        "excluded_contexts": {"pmkf_kalman_used": False, "futu_fields_used": False, "cnstock_context_used": False},
    }
    if data_root is None:
        return base
    try:
        records = load_stock_records(str(candidate.get("code", "")), data_root)
        data = pd.DataFrame(records)
        data["date"] = pd.to_datetime(data.get("date"), errors="coerce").dt.normalize()
        data = data.dropna(subset=["date"]).sort_values("date", kind="stable").drop_duplicates("date", keep="last")
        signal = pd.Timestamp(signal_date)
        data = data.loc[data["date"].le(signal)].tail(lookback_bars).reset_index(drop=True)
        if data.empty or data.iloc[-1]["date"] != signal:
            return {**base, "status": "missing_signal_bar"}
        candle = candlestick_masks(data)
        row_index = data.index[-1]
        patterns = sorted(name for name, mask in candle.items() if bool(mask.loc[row_index]))
        open_ = pd.to_numeric(data.get("open"), errors="coerce")
        high = pd.to_numeric(data.get("high"), errors="coerce")
        low = pd.to_numeric(data.get("low"), errors="coerce")
        close = pd.to_numeric(data.get("close"), errors="coerce")
        volume = pd.to_numeric(data.get("volume"), errors="coerce")
        amount = pd.to_numeric(data.get("amount"), errors="coerce")
        confirmation = compute_candle_confirmation_features(open_, high, low, close, volume)
        high20 = _optional_float(high.tail(20).max())
        low20 = _optional_float(low.tail(20).min())
        latest_close = _optional_float(close.iloc[-1])
        return _json_safe({
            **base,
            "status": "ok",
            "recent_daily_bars": [_daily_bar_summary(row) for row in data.tail(recent_bars).to_dict("records")],
            "candlestick_patterns": patterns,
            "candle_confirmation": confirmation,
            "ohlcv_indicators": {
                "recent_close_return_5d_pct": _pct_change(close, 5),
                "recent_close_return_10d_pct": _pct_change(close, 10),
                "volume_ratio_5d": _ratio_to_tail(volume, 5),
                "volume_ratio_20d": _ratio_to_tail(volume, 20),
                "amount_ratio_5d": _ratio_to_tail(amount, 5),
                "close_vs_20d_high_pct": round((latest_close / high20 - 1.0) * 100.0, 4) if latest_close is not None and high20 and high20 > 0 else None,
                "close_vs_20d_low_pct": round((latest_close / low20 - 1.0) * 100.0, 4) if latest_close is not None and low20 and low20 > 0 else None,
            },
        })
    except Exception as exc:
        return {**base, "status": f"error:{type(exc).__name__}"}


def _daily_context(candidate: Mapping[str, Any], data_root: Path | None) -> dict[str, Any]:
    return _mkf_technical_context(candidate, data_root)


def _local_score(candidate: Mapping[str, Any], context: Mapping[str, Any]) -> tuple[float, tuple[str, ...], tuple[str, ...]]:
    score = 5.0
    observations: list[str] = []
    risks: list[str] = []
    momentum = _safe_float(candidate.get("mkf_momentum"))
    near = _safe_float(candidate.get("mkf_near"))
    inter = _safe_float(candidate.get("mkf_inter"))
    if 20.0 <= momentum <= 45.0 and 20.0 <= near <= 45.0:
        score += 1.0
        observations.append("MKF红蓝线上穿日及后第1/2个交易日仍未过热")
    if inter >= 20.0:
        score += 0.5
        observations.append("MKF中线同步改善")
    if momentum >= 70.0 or near >= 70.0:
        score -= 1.0
        risks.append("MKF线接近高位区，节奏风险上升")

    ohlcv = context.get("ohlcv_indicators") if isinstance(context.get("ohlcv_indicators"), Mapping) else {}
    confirmation = context.get("candle_confirmation") if isinstance(context.get("candle_confirmation"), Mapping) else {}
    patterns = tuple(str(item) for item in context.get("candlestick_patterns") or ())
    volume_ratio = ohlcv.get("volume_ratio_5d")
    if isinstance(volume_ratio, (int, float)):
        if 1.1 <= float(volume_ratio) <= 3.0:
            score += 0.5
            observations.append("5日量能相对温和放大")
        elif float(volume_ratio) > 5.0:
            score -= 0.8
            risks.append("量能异常放大，需人工排查冲高回落风险")
    ret5 = ohlcv.get("recent_close_return_5d_pct")
    if isinstance(ret5, (int, float)) and float(ret5) > 18.0:
        score -= 0.8
        risks.append("近5日涨幅偏热")
    ret10 = ohlcv.get("recent_close_return_10d_pct")
    if isinstance(ret10, (int, float)) and float(ret10) > 30.0:
        score -= 0.6
        risks.append("近10日涨幅偏热")

    if confirmation.get("candle_close_location") is not None and float(confirmation.get("candle_close_location") or 0.0) >= 0.65:
        score += 0.4
        observations.append("信号日收盘位置偏强")
    if confirmation.get("candle_long_upper_shadow_risk"):
        score -= 0.8
        risks.append("Japanese candlestick long upper shadow risk")
    elif confirmation:
        score += 0.3
        observations.append("信号日无明显长上影风险")
    if confirmation.get("candle_bullish_reversal"):
        score += 0.6
        observations.append("Japanese candlestick bullish reversal context")
    if confirmation.get("candle_bullish_continuation"):
        score += 0.5
        observations.append("Japanese candlestick bullish continuation context")
    if confirmation.get("candle_box_breakout"):
        score += 0.5
        observations.append("OHLCV box breakout confirmation")
    if confirmation.get("candle_volume_confirm"):
        score += 0.3
        observations.append("20日量能确认健康")
    if float(confirmation.get("candle_close_location") or 1.0) <= 0.25:
        score -= 0.6
        risks.append("信号日收盘接近日内低位")
    bullish = sorted(set(patterns) & BULLISH_CANDLE_PATTERNS)
    bearish = sorted(set(patterns) & BEARISH_CANDLE_PATTERNS)
    if bullish:
        score += 0.5
        observations.append("Japanese candlestick bullish pattern: " + ",".join(bullish[:3]))
    if bearish:
        score -= 0.8
        risks.append("Japanese candlestick bearish risk pattern: " + ",".join(bearish[:3]))
    if context.get("status") not in {"ok", None}:
        score -= 0.5
        risks.append(f"本地蜡烛图上下文不可用:{context.get('status')}")
    if not observations:
        observations.append("仅满足MKF红蓝线上穿日及后第1/2个交易日基础候选条件")
    return max(1.0, min(10.0, round(score, 4))), tuple(observations), tuple(risks)


def _context_summary_fields(context: Mapping[str, Any]) -> tuple[str, tuple[str, ...], float | None]:
    confirmation = context.get("candle_confirmation") if isinstance(context.get("candle_confirmation"), Mapping) else {}
    score = _optional_float(confirmation.get("candle_confirm_score")) if confirmation else None
    return str(context.get("status") or "unknown"), tuple(str(item) for item in context.get("candlestick_patterns") or ()), score


def _news_summary_fields(news_context: Mapping[str, Any]) -> tuple[str, str, tuple[str, ...], tuple[str, ...]]:
    cache_status = str(news_context.get("cache_status") or "unknown")
    status = "no_data" if news_context.get("news_txt") == NO_NEWS_TEXT else cache_status
    return (
        status,
        cache_status,
        tuple(str(item) for item in news_context.get("fatal_risks") or ()),
        tuple(str(item) for item in news_context.get("attn_risks") or ()),
    )


def _fallback_row(candidate: Mapping[str, Any], context: Mapping[str, Any], news_context: Mapping[str, Any], *, state: str, model: str | None = None) -> MkfAIReviewRow:
    score, observations, risks = _local_score(candidate, context)
    news_status, news_cache_status, fatal_news, attention_news = _news_summary_fields(news_context)
    if fatal_news:
        risks = tuple(list(risks) + ["CNstock新闻致命风险词:" + ",".join(fatal_news[:3])])
    if attention_news:
        risks = tuple(list(risks) + ["CNstock新闻关注词:" + ",".join(attention_news[:3])])
    context_status, patterns, candle_score = _context_summary_fields(context)
    summary = "AI不可用，使用本地MKF、Japanese candlestick/OHLCV与CNstock兼容新闻上下文保守分层。" if state == "ai_unavailable" else "证据不足，保留为标准人工研究复核。"
    if state == "standard_research" and score >= 6.5:
        summary = "本地MKF节奏与蜡烛图上下文较积极，但未经AI与前瞻验证，仅作人工研究优先级参考。"
    return MkfAIReviewRow(
        code=str(candidate["code"]),
        signal_date=str(candidate["signal_date"]),
        review_state=state,
        confidence=0.0 if state == "ai_unavailable" else min(0.65, score / 10.0),
        research_summary=summary,
        technical_observations=observations,
        risk_flags=risks,
        local_score=score,
        model=model,
        source_selection_reason=str(candidate.get("selection_reason") or ""),
        committee_summary=None,
        committee_roles=COMMITTEE_ROLES,
        technical_context_status=context_status,
        candlestick_patterns=patterns,
        candle_confirm_score=candle_score,
        committee_disagreement_flags=(),
        news_context_status=news_status,
        news_cache_status=news_cache_status,
        fatal_news_risks=fatal_news,
        attention_news_risks=attention_news,
    )


def _row_from_ai(candidate: Mapping[str, Any], context: Mapping[str, Any], news_context: Mapping[str, Any], ai_result: Mapping[str, Any], model: str) -> MkfAIReviewRow:
    local_score, local_observations, local_risks = _local_score(candidate, context)
    observations = _string_tuple(ai_result.get("technical_observations")) or local_observations
    risks = _string_tuple(ai_result.get("risk_flags")) or local_risks
    news_status, news_cache_status, fatal_news, attention_news = _news_summary_fields(news_context)
    if fatal_news and not any("CNstock新闻致命风险词" in risk for risk in risks):
        risks = tuple(list(risks) + ["CNstock新闻致命风险词:" + ",".join(fatal_news[:3])])
    if attention_news and not any("CNstock新闻关注词" in risk for risk in risks):
        risks = tuple(list(risks) + ["CNstock新闻关注词:" + ",".join(attention_news[:3])])
    context_status, patterns, candle_score = _context_summary_fields(context)
    committee = ai_result.get("committee") if isinstance(ai_result.get("committee"), Mapping) else None
    return MkfAIReviewRow(
        code=str(candidate["code"]),
        signal_date=str(candidate["signal_date"]),
        review_state=str(ai_result["review_state"]),
        confidence=float(ai_result["confidence"]),
        research_summary=str(ai_result.get("research_summary") or "MKF AI委员会复核未提供摘要")[:1000],
        technical_observations=observations,
        risk_flags=risks,
        local_score=local_score,
        model=model,
        source_selection_reason=str(candidate.get("selection_reason") or ""),
        committee_summary=committee,
        committee_roles=COMMITTEE_ROLES,
        technical_context_status=context_status,
        candlestick_patterns=patterns,
        candle_confirm_score=candle_score,
        committee_disagreement_flags=_string_tuple(ai_result.get("committee_disagreement_flags"), maximum=6),
        news_context_status=news_status,
        news_cache_status=news_cache_status,
        fatal_news_risks=fatal_news,
        attention_news_risks=attention_news,
    )


def run_mkf_ai_review(
    *,
    selection_root: Path,
    output_root: Path,
    config_path: Path,
    selection_run: Path | None = None,
    run_id: str | None = None,
    data_root: Path | None = None,
    max_candidates: int | None = None,
    ai_client: Any | None = None,
    progress: Callable[..., None] | None = None,
) -> MkfAIReviewResult:
    config = load_mkf_ai_config(config_path)
    source_run = resolve_mkf_selection_run(selection_root, selection_run)
    candidates, candidates_sha = validate_mkf_selection_run(source_run)
    review_config = config.get("review") if isinstance(config.get("review"), Mapping) else {}
    yaml_max_candidates = _normalize_max_candidates(review_config)
    max_candidates = yaml_max_candidates if max_candidates is None else max_candidates
    if max_candidates < 1:
        raise ValueError("max_candidates must be at least 1")
    client = ai_client if ai_client is not None else build_ai_client(config)
    rows: list[MkfAIReviewRow] = []
    ai_errors: Counter[str] = Counter()
    ai_attempt_count = 0
    ai_success_count = 0
    contexts: list[dict[str, Any]] = []
    news_contexts: list[dict[str, Any]] = []
    news_config = config.get("news_config") if isinstance(config.get("news_config"), Mapping) else {}
    for index, candidate in enumerate(candidates, start=1):
        code = str(candidate.get("code", ""))
        detail = {
            "close": candidate.get("research_close"),
            "amount_cny": candidate.get("amount_cny"),
            "mkf_momentum": candidate.get("mkf_momentum"),
            "mkf_near": candidate.get("mkf_near"),
            "turn_pct": candidate.get("turn_pct"),
        }
        if progress is not None:
            progress(index, len(candidates), code, "context", detail)
        context = _mkf_technical_context(candidate, data_root, config)
        contexts.append({"code": code, "signal_date": candidate.get("signal_date"), "technical_context": context})
        context_status, patterns, candle_score = _context_summary_fields(context)
        news = build_mkf_news_context(code, news_config)
        news_record = {"code": code, "signal_date": candidate.get("signal_date"), "news_context": news.to_dict()}
        news_contexts.append(news_record)
        news_context = news_record["news_context"]
        news_status, news_cache_status, fatal_news, attention_news = _news_summary_fields(news_context)
        detail = {
            **detail,
            "technical_context_status": context_status,
            "candlestick_patterns": patterns,
            "candle_confirm_score": candle_score,
            "news_context_status": news_status,
            "news_cache_status": news_cache_status,
            "fatal_news_risk_count": len(fatal_news),
            "attention_news_risk_count": len(attention_news),
        }
        if progress is not None:
            progress(index, len(candidates), code, "news", detail)
        if client is None or index > max_candidates:
            row = _fallback_row(candidate, context, news_context, state="ai_unavailable")
        else:
            ai_attempt_count += 1
            if progress is not None:
                progress(index, len(candidates), code, "ai", detail)
            try:
                ai_result, model = client.analyze(candidate, context, news_context)
                row = _row_from_ai(candidate, context, news_context, ai_result, model)
                ai_success_count += 1
            except (MkfAIRequestError, http.client.HTTPException, KeyError, TypeError, ValueError, OSError, urllib.error.URLError) as exc:
                ai_errors[str(exc) if isinstance(exc, MkfAIRequestError) else type(exc).__name__] += 1
                detail = {**detail, "error": str(exc) if isinstance(exc, MkfAIRequestError) else type(exc).__name__}
                row = _fallback_row(candidate, context, news_context, state="ai_unavailable")
        if progress is not None:
            progress(index, len(candidates), code, row.review_state, {**detail, "confidence": row.confidence, "local_score": row.local_score, "risk_flags": row.risk_flags})
        rows.append(row)

    state_order = {"priority_research": 0, "standard_research": 1, "insufficient_evidence": 2, "risk_attention": 3, "ai_unavailable": 4}
    rows.sort(key=lambda row: (state_order[row.review_state], -row.confidence, -row.local_score, row.code))
    actual_run_id = run_id or f"mkf-ai-review-{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    output_root.mkdir(parents=True, exist_ok=True)
    destination = output_root / actual_run_id
    temporary = output_root / f".{actual_run_id}.tmp"
    if destination.exists() or temporary.exists():
        raise FileExistsError(f"MKF AI review run already exists: {destination}")
    temporary.mkdir()
    try:
        generated_at = datetime.now().astimezone()
        reviews_csv_name = f"mkf_ai_reviews_{generated_at.strftime('%Y%m%d_%H%M%S')}.csv"
        reviews_path = temporary / "reviews.json"
        reviews_csv_path = temporary / reviews_csv_name
        technical_contexts_path = temporary / "technical_contexts.json"
        news_contexts_path = temporary / "news_contexts.json"
        summary_path = temporary / "summary.json"
        reviews_path.write_text(json.dumps([asdict(row) for row in rows], ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        technical_contexts_path.write_text(json.dumps(contexts, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        news_contexts_path.write_text(json.dumps(news_contexts, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        with reviews_csv_path.open("w", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=list(CSV_FIELDNAMES))
            writer.writeheader()
            for row in rows:
                values = asdict(row)
                values["technical_observations"] = "|".join(values["technical_observations"])
                values["risk_flags"] = "|".join(values["risk_flags"])
                values["committee_summary"] = json.dumps(values["committee_summary"], ensure_ascii=False, sort_keys=True) if values["committee_summary"] else ""
                values["committee_roles"] = "|".join(values["committee_roles"])
                values["candlestick_patterns"] = "|".join(values["candlestick_patterns"])
                values["committee_disagreement_flags"] = "|".join(values["committee_disagreement_flags"])
                writer.writerow(values)
        counts = {state: sum(row.review_state == state for row in rows) for state in state_order}
        news_cache_counts = Counter(str(item["news_context"].get("cache_status") or "unknown") for item in news_contexts)
        news_source_error_counts: Counter[str] = Counter()
        for item in news_contexts:
            source_status = item["news_context"].get("source_status") or {}
            if isinstance(source_status, Mapping):
                for source, source_state in source_status.items():
                    if str(source_state).startswith("error:"):
                        news_source_error_counts[f"{source}:{source_state}"] += 1
        status = "success" if not candidates or client is None or ai_attempt_count == ai_success_count else ("partial" if ai_success_count else "ai_failed")
        news_config_path = Path(str(config.get("news_config_path") or ""))
        prompt_config = config.get("prompt") or {}
        ai_config = config.get("_ai_provider_config")
        ai_mapping = config.get("ai") or {}
        ai_model = None
        if isinstance(ai_config, AIProviderConfig) and ai_config.provider in ai_config.providers:
            ai_model = ai_config.providers[ai_config.provider].get("model")
        summary = {
            "schema_version": SCHEMA_VERSION,
            "status": status,
            "run_id": actual_run_id,
            "timestamped_reviews_csv": reviews_csv_name,
            "published_at_utc": _utc_now(),
            "source_selection_run": str(source_run),
            "source_candidates_sha256": candidates_sha,
            "config_path": str(config_path),
            "config_sha256": _sha256(config_path),
            "ai_config_path": str(config.get("ai_config_path") or config_path),
            "ai_config_sha256": config.get("ai_config_sha256"),
            "prompt_source": str(prompt_config.get("source") or "module_default_prompt.system"),
            "prompt_sha256": str(prompt_config.get("sha256") or _sha256_text(str(prompt_config.get("system") or DEFAULT_MKF_AI_SYSTEM_PROMPT))),
            "candidate_count": len(candidates),
            "configured_max_candidates": yaml_max_candidates,
            "effective_max_candidates": max_candidates,
            "ai_skipped_by_max_candidates": max(0, len(candidates) - max_candidates) if client is not None else 0,
            "ai_provider": str(ai_mapping.get("provider", "injected_or_disabled")),
            "ai_provider_config_style": str(ai_mapping.get("provider_config_style", "ncn_ai_providers_v1")),
            "ai_provider_schema": str(ai_mapping.get("schema_version", "ncn_ai_providers_v1")),
            "ai_client_status": "injected" if ai_client is not None else ("enabled" if client is not None else "disabled"),
            "ai_model": ai_model,
            "ai_response_format": ai_mapping.get("response_format"),
            "ai_temperature": ai_mapping.get("temperature"),
            "ai_seed": ai_mapping.get("seed"),
            "ai_attempt_count": ai_attempt_count,
            "ai_success_count": ai_success_count,
            "state_counts": counts,
            "ai_error_counts": dict(ai_errors),
            "context_records": [{"code": item["code"], "signal_date": item.get("signal_date"), "status": item["technical_context"].get("status")} for item in contexts],
            "review_order": "state_priority_then_confidence_desc_then_local_score_desc_then_code",
            "decision_boundary": "experimental_mkf_committee_research_priority_not_validated_win_probability",
            "committee": {
                "enabled": True,
                "roles": list(COMMITTEE_ROLES),
                "execution": "single_llm_call_structured_committee_prompt",
            },
            "technical_context": {
                "type": "ncn_english_japanese_candlestick_ohlcv",
                "uses_pmkf_kalman": False,
                "uses_futu_fields": False,
                "uses_cnstock_context": False,
            },
            "news_context": {
                "enabled": bool(news_config.get("ENABLED", True)),
                "source": "cnstock_main_pmkf_scan_deterministic_news_fetcher_compatible",
                "config_path": str(news_config_path),
                "config_sha256": _sha256(news_config_path) if news_config_path.is_file() else None,
                "storage_dir": str(news_config.get("_resolved_news_cache_dir") or ""),
                "cache_schema": "Message/{normalized_code}_{YYYYMMDD}.json with date/news_txt/fatal_risks/attn_risks",
                "news_days": int(news_config.get("NEWS_DAYS", 7) or 7),
                "news_limit": int(news_config.get("NEWS_LIMIT", 5) or 5),
                "fetch_online_by_default": bool(news_config.get("FETCH_ONLINE_BY_DEFAULT", True)),
                "cache_status_counts": dict(news_cache_counts),
                "source_error_counts": dict(news_source_error_counts),
                "fatal_risk_candidate_count": sum(1 for row in rows if row.fatal_news_risks),
                "attention_risk_candidate_count": sum(1 for row in rows if row.attention_news_risks),
                "used_for": "mkf_ai_research_layer_only",
                "uses_ai_web_analyzer": False,
                "subjective_news_invention_allowed": False,
            },
            "boundaries": {
                "read_only": True,
                "production_enabled": False,
                "broker_connected": False,
                "orders_submitted": False,
                "returns_calculated": False,
                "smc_admission_modified": False,
                "smc_ranking_modified": False,
                "watchlist_modified": False,
                "prospective_archive_modified": False,
                "mkf_selection_modified": False,
                "pmkf_kalman_used": False,
                "futu_fields_used": False,
                "news_used_only_for_mkf_ai_layer": True,
            },
            "limitations": [
                "single_llm_call_structured_committee_prompt_not_true_multi_agent_consensus",
                "llm_output_can_be_incorrect_or_non_reproducible",
                "priority_research_has_not_proven_higher_target_touch_precision",
                "read_only_research_not_investment_advice",
                "candlestick_context_uses_local_adjusted_daily_bars_only",
                "news_context_uses_cnstock_compatible_headlines_and_announcements_only",
                "news_fetch_dependencies_can_fail_closed_without_invented_news",
            ],
        }
        summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
        files = {
            name: {"sha256": _sha256(temporary / name)}
            for name in ("reviews.json", reviews_csv_name, "technical_contexts.json", "news_contexts.json", "summary.json")
        }
        manifest = {
            "schema_version": SCHEMA_VERSION,
            "run_id": actual_run_id,
            "source_candidates_sha256": candidates_sha,
            "timestamped_reviews_csv": reviews_csv_name,
            "files": files,
        }
        (temporary / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
        os.replace(temporary, destination)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return MkfAIReviewResult(
        run_directory=destination,
        reviews_path=destination / "reviews.json",
        reviews_csv_path=destination / reviews_csv_name,
        technical_contexts_path=destination / "technical_contexts.json",
        news_contexts_path=destination / "news_contexts.json",
        summary_path=destination / "summary.json",
        manifest_path=destination / "manifest.json",
        priority_research_count=sum(row.review_state == "priority_research" for row in rows),
        risk_attention_count=sum(row.review_state == "risk_attention" for row in rows),
    )
