"""Market-data route payloads for the NCN Web console."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import date, datetime
from typing import TYPE_CHECKING, Any

from ...candles import detect_bearish_risk_patterns, detect_bullish_patterns_from_candle_rules
from ...data.daily_bars import DataValidationError, load_local_daily_bars
from ...indicators import sma, volume_moving_average
from ...data.intraday_data import IntradayDataError, SUPPORTED_MINUTE_PERIODS, freshness_payload
from ...research_watchlist import load_research_watchlist
from ..errors import ResearchWebError

if TYPE_CHECKING:
    from pathlib import Path
    from ..app import ResearchWebContext

_PATTERN_LABELS = {
    "hammer": "锤子线",
    "bullish_engulfing": "看涨吞没",
    "piercing": "刺透形态",
    "morning_star": "启明星",
}
_BEARISH_RISK_PATTERN_LABELS = {
    "hanging_man": "吊颈线",
    "shooting_star": "流星线",
    "bearish_engulfing": "看跌吞没",
    "dark_cloud_cover": "乌云盖顶",
    "evening_star": "黄昏星",
}


def load_dashboard(
    context: "ResearchWebContext",
    *,
    read_json_object: Callable[["Path", str], dict[str, Any]],
    published_run_directory: Callable[["Path", Mapping[str, Any]], "Path"],
    read_csv_rows: Callable[["Path"], list[dict[str, str]]],
) -> dict[str, Any]:
    latest_path = context.output_root / "latest.json"
    selected_codes = load_research_watchlist(context.watchlist_path)
    if latest_path.is_file():
        latest = read_json_object(latest_path, "latest publication")
        run_directory = published_run_directory(context.output_root, latest)
        summary = read_json_object(run_directory / "summary.json", "scan summary")
        published_rows = read_csv_rows(run_directory / "daily_research_watchlist.csv")
    else:
        latest = {
            "schema_version": "edge_scout_v1",
            "status": "no_publication",
            "run_id": None,
            "run_directory": None,
            "publication_available": False,
        }
        summary = {
            "as_of": None,
            "status": "no_publication",
            "input_code_count": 0,
            "scored_count": 0,
            "watchlist_count": 0,
            "near_miss_count": 0,
            "boundaries": {"read_only": True, "production_enabled": False},
            "limitations": ["manual_watchlist_without_publication"],
            "freshness_evidence": {},
        }
        published_rows = []
    published_by_code = {row.get("code"): row for row in published_rows}
    rows = [
        published_by_code.get(
            code,
            {
                "rank": str(index),
                "code": code,
                "watch_stage": "manual_research",
                "research_only": "True",
                "selection_reason": "manual_research_selection",
            },
        )
        for index, code in enumerate(selected_codes, start=1)
    ]
    return {
        "latest": latest,
        "summary": {
            "as_of": summary.get("as_of"),
            "status": summary.get("status"),
            "input_code_count": summary.get("input_code_count", 0),
            "scored_count": summary.get("scored_count", 0),
            "watchlist_count": summary.get("watchlist_count", 0),
            "near_miss_count": summary.get("near_miss_count", 0),
            "boundaries": summary.get("boundaries", {}),
            "limitations": summary.get("limitations", []),
            "freshness_evidence": summary.get("freshness_evidence", {}),
        },
        "watchlist": rows,
        "selected_codes": list(selected_codes),
        "manual_selection_enabled": True,
        "research_only": True,
    }


def load_candle_research(
    context: "ResearchWebContext",
    code: str,
    *,
    limit: int = 120,
    period: str = "1d",
) -> dict[str, Any]:
    normalized_code = normalize_a_share_code(code)
    if period not in ("1d", *SUPPORTED_MINUTE_PERIODS):
        raise ResearchWebError("invalid_period", f"不支持的 K 线周期: {period}")
    if limit < 30 or limit > 260:
        raise ResearchWebError("invalid_limit", "limit 必须在 30 到 260 之间")
    if period != "1d":
        return _load_intraday_candle_research(
            context,
            normalized_code,
            period=period,
            limit=limit,
        )
    try:
        records = list(load_local_daily_bars(normalized_code, data_root=context.data_root))
    except DataValidationError as exc:
        raise ResearchWebError(exc.code, str(exc)) from exc

    patterns = detect_bullish_patterns_from_candle_rules(records, context.candle_rules)
    bearish_risks = detect_bearish_risk_patterns(records)
    closes = [float(record["close"]) for record in records]
    volumes = [float(record["volume"]) for record in records]
    ma20 = sma(closes, 20)
    ma60 = sma(closes, 60)
    volume_ma20 = volume_moving_average(volumes, 20)
    chart_start = max(0, len(records) - limit)
    annotations = _build_pattern_annotations(
        records,
        patterns,
        volume_ma20,
        min_volume_ratio=context.confirmation_volume_ratio,
        chart_start=chart_start,
    )
    annotations.extend(
        _build_bearish_risk_annotations(records, bearish_risks, chart_start=chart_start)
    )
    bars = [
        {
            "date": _iso_date(record["date"]),
            "timestamp": _iso_date(record["date"]),
            "open": float(record["open"]),
            "high": float(record["high"]),
            "low": float(record["low"]),
            "close": float(record["close"]),
            "volume": float(record["volume"]),
            "ma20": ma20[index],
            "ma60": ma60[index],
            "volume_ma20": volume_ma20[index],
            "is_forming": False,
        }
        for index, record in enumerate(records)
        if index >= chart_start
    ]
    return {
        "code": normalized_code,
        "period": "1d",
        "bars": bars,
        "annotations": annotations,
        "pattern_labels": {**_PATTERN_LABELS, **_BEARISH_RISK_PATTERN_LABELS},
        "provenance": {
            "provider": "local_baostock_parquet",
            "adjustment": "qfq_research_only",
            "source_timestamp": bars[-1]["timestamp"],
            "fetched_at": datetime.now().astimezone().isoformat(),
            "warnings": ["local_adjusted_research_data_only"],
        },
        "freshness": {
            "status": "local_close",
            "source_timestamp": bars[-1]["timestamp"],
            "detail": "本地已发布日线研究数据",
        },
        "methodology": {
            "source": "Japanese Candlestick Charting Techniques (English edition)",
            "principles": [
                "形态必须结合此前趋势位置判断",
                "锤子线下影至少为实体两倍且上影很短",
                "吞没只要求第二根实体覆盖第一根实体",
                "刺透收盘必须进入前一根阴线实体一半以上",
                "启明星由长阴线、小实体星线和深入首根实体的阳线组成",
                "成交量与后一交易日价格仅作确认，不把形态单独视为结论",
            ],
            "confirmation_volume_ratio": context.confirmation_volume_ratio,
        },
        "research_alert": build_research_alert(bars, annotations),
        "research_only": True,
    }


def load_snapshot_research(context: "ResearchWebContext", code: str) -> dict[str, Any]:
    normalized_code = normalize_a_share_code(code)
    try:
        snapshot = context.intraday_client.fetch_snapshot(normalized_code)
    except IntradayDataError as exc:
        raise ResearchWebError(exc.code, str(exc)) from exc
    return {
        "snapshot": snapshot.to_dict(),
        "freshness": freshness_payload(
            snapshot.source_timestamp,
            snapshot.fetched_at,
            expected_interval_seconds=15,
        ),
        "warnings": list(snapshot.warnings),
        "research_only": True,
    }


def normalize_a_share_code(raw_code: str) -> str:
    if not isinstance(raw_code, str):
        raise ResearchWebError("invalid_code", "股票代码必须是字符串")
    value = raw_code.strip().lower()
    if value.startswith(("sh.", "sz.")):
        prefix, digits = value.split(".", 1)
        if len(digits) == 6 and digits.isdigit():
            return f"{prefix}.{digits}"
    if len(value) == 6 and value.isdigit():
        if value.startswith(("5", "6", "9")):
            return f"sh.{value}"
        if value.startswith(("0", "1", "2", "3")):
            return f"sz.{value}"
    raise ResearchWebError("invalid_code", f"无法识别股票代码: {raw_code}")


def _load_intraday_candle_research(
    context: "ResearchWebContext",
    code: str,
    *,
    period: str,
    limit: int,
) -> dict[str, Any]:
    try:
        batch = context.intraday_client.fetch_minute_bars(code, period, limit=limit)
    except IntradayDataError as exc:
        raise ResearchWebError(exc.code, str(exc)) from exc
    records = [
        {
            "date": bar.timestamp.isoformat(),
            "open": bar.open,
            "high": bar.high,
            "low": bar.low,
            "close": bar.close,
            "volume": bar.volume,
            "amount": bar.amount,
            "is_forming": bar.is_forming,
        }
        for bar in batch.bars
    ]
    completed_count = len(records) - (1 if records[-1]["is_forming"] else 0)
    completed_records = records[:completed_count]
    if len(completed_records) >= 4:
        completed_patterns = detect_bullish_patterns_from_candle_rules(
            completed_records,
            context.candle_rules,
        )
        patterns = {
            name: [*matches, *([False] if completed_count < len(records) else [])]
            for name, matches in completed_patterns.items()
        }
        completed_bearish_risks = detect_bearish_risk_patterns(completed_records)
        bearish_risks = {
            name: [*matches, *([False] if completed_count < len(records) else [])]
            for name, matches in completed_bearish_risks.items()
        }
    else:
        patterns = {name: [False] * len(records) for name in _PATTERN_LABELS}
        bearish_risks = {
            name: [False] * len(records) for name in _BEARISH_RISK_PATTERN_LABELS
        }
    closes = [float(record["close"]) for record in records]
    volumes = [float(record["volume"]) for record in records]
    ma20 = sma(closes, 20)
    ma60 = sma(closes, 60)
    volume_ma20 = volume_moving_average(volumes, 20)
    annotations = _build_pattern_annotations(
        records,
        patterns,
        volume_ma20,
        min_volume_ratio=context.confirmation_volume_ratio,
        chart_start=0,
    )
    annotations.extend(_build_bearish_risk_annotations(records, bearish_risks, chart_start=0))
    bars = [
        {
            **record,
            "timestamp": record["date"],
            "ma20": ma20[index],
            "ma60": ma60[index],
            "volume_ma20": volume_ma20[index],
        }
        for index, record in enumerate(records)
    ]
    interval_seconds = int(period[:-1]) * 60
    return {
        "code": code,
        "period": period,
        "bars": bars,
        "annotations": annotations,
        "pattern_labels": {**_PATTERN_LABELS, **_BEARISH_RISK_PATTERN_LABELS},
        "provenance": {
            "provider": batch.provider,
            "adjustment": batch.adjustment,
            "source_timestamp": batch.source_timestamp.isoformat(),
            "fetched_at": batch.fetched_at.isoformat(),
            "warnings": list(batch.warnings),
        },
        "freshness": freshness_payload(
            batch.source_timestamp,
            batch.fetched_at,
            expected_interval_seconds=interval_seconds,
        ),
        "methodology": {
            "source": "Japanese Candlestick Charting Techniques (English edition)",
            "confirmation_scope": "下一根已完成分钟 K 线的价格与成交量确认",
            "forming_bar_excluded": True,
            "confirmation_volume_ratio": context.confirmation_volume_ratio,
        },
        "research_alert": build_research_alert(bars, annotations),
        "research_only": True,
    }


def _iso_date(value: Any) -> str:
    if isinstance(value, (date, datetime)):
        return value.date().isoformat() if isinstance(value, datetime) else value.isoformat()
    return str(value)


def _build_pattern_annotations(
    records: Sequence[Mapping[str, Any]],
    patterns: Mapping[str, Sequence[bool]],
    volume_ma20: Sequence[float | None],
    *,
    min_volume_ratio: float,
    chart_start: int,
) -> list[dict[str, Any]]:
    annotations: list[dict[str, Any]] = []
    for name, matches in patterns.items():
        for index, matched in enumerate(matches):
            if not matched or index < chart_start:
                continue
            status = "pending" if index + 1 >= len(records) else "not_confirmed"
            confirmation_date = None
            volume_ratio = None
            if index + 1 < len(records):
                signal = records[index]
                confirmation = records[index + 1]
                baseline = volume_ma20[index]
                volume_ratio = float(confirmation["volume"]) / baseline if baseline else None
                if (
                    float(confirmation["close"]) > float(signal["high"])
                    and float(confirmation["close"]) > float(confirmation["open"])
                    and volume_ratio is not None
                    and volume_ratio >= min_volume_ratio
                ):
                    status = "confirmed"
                    confirmation_date = _iso_date(confirmation["date"])
            annotations.append(
                {
                    "index": index - chart_start,
                    "date": _iso_date(records[index]["date"]),
                    "pattern": name,
                    "label": _PATTERN_LABELS.get(name, name),
                    "kind": "bullish",
                    "status": status,
                    "confirmation_date": confirmation_date,
                    "volume_ratio": volume_ratio,
                }
            )
    return annotations


def _build_bearish_risk_annotations(
    records: Sequence[Mapping[str, Any]],
    patterns: Mapping[str, Sequence[bool]],
    *,
    chart_start: int,
) -> list[dict[str, Any]]:
    annotations: list[dict[str, Any]] = []
    for name, matches in patterns.items():
        for index, matched in enumerate(matches):
            if not matched or index < chart_start:
                continue
            annotations.append(
                {
                    "index": index - chart_start,
                    "date": _iso_date(records[index]["date"]),
                    "pattern": name,
                    "label": _BEARISH_RISK_PATTERN_LABELS.get(name, name),
                    "kind": "risk",
                    "status": "risk_observation",
                    "confirmation_date": None,
                    "volume_ratio": None,
                }
            )
    return annotations


def build_research_alert(
    bars: Sequence[Mapping[str, Any]],
    annotations: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    completed = [bar for bar in bars if not bool(bar.get("is_forming"))]
    if not completed:
        return {
            "state": "unavailable",
            "title": "研究证据不足",
            "detail": "没有已完成 K 线可供判断",
            "evidence": [],
            "research_only": True,
        }
    latest = completed[-1]
    close = float(latest["close"])
    ma20 = latest.get("ma20")
    ma60 = latest.get("ma60")
    volume_ma20 = latest.get("volume_ma20")
    volume_ratio = (
        float(latest["volume"]) / float(volume_ma20)
        if volume_ma20 not in (None, 0)
        else None
    )
    upper_shadow = float(latest["high"]) - max(float(latest["open"]), close)
    candle_range = float(latest["high"]) - float(latest["low"])
    upper_shadow_ratio = upper_shadow / candle_range if candle_range > 0 else 0.0
    evidence: list[str] = []

    if ma60 is not None and close <= float(ma60):
        evidence.append("latest_close_at_or_below_ma60")
    if ma20 is not None and ma60 is not None and float(ma20) <= float(ma60):
        evidence.append("ma20_at_or_below_ma60")
    if evidence:
        return {
            "state": "risk_observation",
            "title": "结构风险观察",
            "detail": "收盘或均线结构已触及 MA60 风险条件，建议人工复核并降低看涨假设权重",
            "evidence": evidence,
            "research_only": True,
        }
    if ma20 is not None and close < float(ma20) and volume_ratio is not None and volume_ratio >= 1.05:
        return {
            "state": "risk_observation",
            "title": "放量跌破 MA20 观察",
            "detail": "最新已完成 K 线位于 MA20 下方且量比不低于 1.05",
            "evidence": ["close_below_ma20", f"volume_ratio={volume_ratio:.2f}"],
            "research_only": True,
        }
    latest_timestamp = str(latest.get("timestamp") or latest.get("date"))
    latest_bearish_risks = [
        item
        for item in annotations
        if item.get("kind") == "risk" and str(item.get("date")) == latest_timestamp
    ]
    if latest_bearish_risks:
        return {
            "state": "risk_observation",
            "title": "看跌蜡烛风险观察",
            "detail": "最新已完成 K 线出现趋势变化风险形态，仅用于降低看涨假设权重",
            "evidence": [str(item.get("label")) for item in latest_bearish_risks],
            "research_only": True,
        }
    if upper_shadow_ratio > 0.40:
        return {
            "state": "risk_observation",
            "title": "长上影风险观察",
            "detail": "最新已完成 K 线上影超过全天振幅 40%",
            "evidence": [f"upper_shadow_ratio={upper_shadow_ratio:.2f}"],
            "research_only": True,
        }
    confirmed = [
        item
        for item in annotations
        if item.get("kind", "bullish") == "bullish"
        and item.get("status") == "confirmed"
        and str(item.get("confirmation_date")) == latest_timestamp
    ]
    if confirmed:
        labels = [str(item.get("label")) for item in confirmed]
        return {
            "state": "bullish_setup_confirmed",
            "title": "看涨 setup 已确认",
            "detail": "形态已由下一根已完成 K 线的价格与成交量确认",
            "evidence": labels,
            "research_only": True,
        }
    pending = [
        item
        for item in annotations
        if item.get("kind", "bullish") == "bullish" and item.get("status") == "pending"
    ]
    if pending:
        return {
            "state": "setup_watch",
            "title": "看涨形态等待确认",
            "detail": "已识别形态，等待下一根已完成 K 线的价格和量能证据",
            "evidence": [str(item.get("label")) for item in pending],
            "research_only": True,
        }
    if ma20 is not None and ma60 is not None and close > float(ma20) > float(ma60):
        return {
            "state": "trend_watch",
            "title": "多头结构继续观察",
            "detail": "收盘位于 MA20 上方且 MA20 高于 MA60，当前没有新的已确认看涨形态",
            "evidence": ["close_above_ma20_above_ma60"],
            "research_only": True,
        }
    return {
        "state": "neutral",
        "title": "暂无方向提醒",
        "detail": "当前已完成 K 线未满足看涨确认或结构风险条件",
        "evidence": [],
        "research_only": True,
    }


__all__ = [
    "build_research_alert",
    "load_candle_research",
    "load_dashboard",
    "load_snapshot_research",
    "normalize_a_share_code",
]
