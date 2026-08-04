"""Read-only local web console for published Edge Scout research."""

from __future__ import annotations

import argparse
import csv
import json
import mimetypes
from dataclasses import dataclass
from datetime import date, datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import parse_qs, urlparse

from .candle_rules import CandleRuleSet, HammerRule
from .candles import detect_bullish_patterns_from_candle_rules
from .config import load_config, validate_config
from .daily_bars import DataValidationError, load_local_daily_bars
from .indicators import sma, volume_moving_average
from .intraday_data import (
    IntradayDataClient,
    IntradayDataError,
    SUPPORTED_MINUTE_PERIODS,
    freshness_payload,
)
from .research_watchlist import (
    ResearchWatchlistError,
    add_research_code,
    load_research_watchlist,
    remove_research_code,
)


_STATIC_ROOT = Path(__file__).with_name("web_static")
_STATIC_FILES = {
    "/": "index.html",
    "/index.html": "index.html",
    "/app.js": "app.js",
    "/style.css": "style.css",
}
_PATTERN_LABELS = {
    "hammer": "锤子线",
    "bullish_engulfing": "看涨吞没",
    "piercing": "刺透形态",
    "morning_star": "启明星",
}


class ResearchWebError(ValueError):
    """Stable client-facing error raised by the research web service."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        super().__init__(detail)


@dataclass(frozen=True)
class ResearchWebContext:
    project_root: Path
    data_root: Path
    output_root: Path
    config_path: Path
    candle_rules: CandleRuleSet
    confirmation_volume_ratio: float
    intraday_client: IntradayDataClient
    watchlist_path: Path


def create_context(
    project_root: str | Path,
    *,
    data_root: str | Path | None = None,
    output_root: str | Path | None = None,
    config_path: str | Path | None = None,
    intraday_client: IntradayDataClient | None = None,
    watchlist_path: str | Path | None = None,
) -> ResearchWebContext:
    """Build and validate immutable paths and candle rules for the server."""

    root = Path(project_root).expanduser().resolve()
    config_file = _resolve_from_root(root, config_path or "yaml/edge_scout_v1.yaml")
    config = load_config(config_file)
    validate_config(config, config_file)
    if config.get("mode") != "read_only_research":
        raise ResearchWebError("invalid_mode", "研究台仅允许 read_only_research 模式")

    candle = config["setup"]["candle"]
    hammer = candle["hammer"]
    return ResearchWebContext(
        project_root=root,
        data_root=_resolve_from_root(root, data_root or config["paths"]["data_root"]),
        output_root=_resolve_from_root(root, output_root or config["paths"]["output_root"]),
        config_path=config_file,
        candle_rules=CandleRuleSet(
            enabled_patterns=tuple(candle["enabled"]),
            hammer=HammerRule(
                max_body_to_range=float(hammer["max_body_to_range"]),
                min_lower_shadow_to_body=float(hammer["min_lower_shadow_to_body"]),
                max_upper_shadow_to_body=float(hammer["max_upper_shadow_to_body"]),
                min_close_location=float(hammer["min_close_location"]),
                uses_documented_upper_shadow_range_guard=True,
            ),
        ),
        confirmation_volume_ratio=float(config["setup"]["confirmation"]["min_volume_to_ma20"]),
        intraday_client=intraday_client or IntradayDataClient(),
        watchlist_path=_resolve_from_root(
            root,
            watchlist_path or "config/research_watchlist.json",
        ),
    )


def load_dashboard(context: ResearchWebContext) -> dict[str, Any]:
    """Load the latest immutable publication as a compact dashboard payload."""

    latest_path = context.output_root / "latest.json"
    latest = _read_json_object(latest_path, "latest publication")
    run_directory = _published_run_directory(context.output_root, latest)
    summary = _read_json_object(run_directory / "summary.json", "scan summary")
    published_rows = _read_csv_rows(run_directory / "daily_research_watchlist.csv")
    selected_codes = load_research_watchlist(context.watchlist_path)
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
    context: ResearchWebContext,
    code: str,
    *,
    limit: int = 120,
    period: str = "1d",
) -> dict[str, Any]:
    """Load chart-ready bars and book-derived bullish candle observations."""

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
        "pattern_labels": _PATTERN_LABELS,
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
        "research_alert": _build_research_alert(bars, annotations),
        "research_only": True,
    }


def load_snapshot_research(context: ResearchWebContext, code: str) -> dict[str, Any]:
    """Fetch one read-only HTTPS market snapshot with explicit freshness."""

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


def _load_intraday_candle_research(
    context: ResearchWebContext,
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
    else:
        patterns = {name: [False] * len(records) for name in _PATTERN_LABELS}
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
        "pattern_labels": _PATTERN_LABELS,
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
        "research_alert": _build_research_alert(bars, annotations),
        "research_only": True,
    }


def normalize_a_share_code(raw_code: str) -> str:
    """Normalize supported Shanghai/Shenzhen six-digit research codes."""

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


def make_handler(context: ResearchWebContext) -> type[BaseHTTPRequestHandler]:
    """Create a request handler bound to one validated context."""

    class ResearchRequestHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 - stdlib hook
            parsed = urlparse(self.path)
            try:
                if parsed.path == "/api/dashboard":
                    self._send_json(load_dashboard(context))
                    return
                if parsed.path == "/api/candles":
                    query = parse_qs(parsed.query)
                    code = query.get("code", [""])[0]
                    period = query.get("period", ["1d"])[0]
                    try:
                        limit = int(query.get("limit", ["120"])[0])
                    except ValueError as exc:
                        raise ResearchWebError("invalid_limit", "limit 必须是整数") from exc
                    self._send_json(load_candle_research(context, code, limit=limit, period=period))
                    return
                if parsed.path == "/api/snapshot":
                    query = parse_qs(parsed.query)
                    self._send_json(load_snapshot_research(context, query.get("code", [""])[0]))
                    return
                if parsed.path == "/api/research-watchlist":
                    self._send_json({"codes": list(load_research_watchlist(context.watchlist_path)), "research_only": True})
                    return
                if parsed.path in _STATIC_FILES:
                    self._send_static(_STATIC_FILES[parsed.path])
                    return
                self._send_json({"error": "not_found", "detail": "资源不存在"}, HTTPStatus.NOT_FOUND)
            except ResearchWebError as exc:
                self._send_json({"error": exc.code, "detail": str(exc)}, HTTPStatus.BAD_REQUEST)
            except ResearchWatchlistError as exc:
                self._send_json({"error": exc.code, "detail": str(exc)}, HTTPStatus.BAD_REQUEST)
            except FileNotFoundError as exc:
                self._send_json(
                    {"error": "publication_missing", "detail": str(exc)},
                    HTTPStatus.SERVICE_UNAVAILABLE,
                )
            except Exception:
                self._send_json(
                    {"error": "internal_error", "detail": "研究数据加载失败"},
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                )

        def do_POST(self) -> None:  # noqa: N802 - stdlib hook
            parsed = urlparse(self.path)
            try:
                if parsed.path not in {"/api/research-watchlist/add", "/api/research-watchlist/remove"}:
                    self._send_json({"error": "not_found", "detail": "资源不存在"}, HTTPStatus.NOT_FOUND)
                    return
                payload = self._read_json_body()
                raw_code = payload.get("code", "")
                if parsed.path.endswith("/add"):
                    codes = add_research_code(
                        context.watchlist_path,
                        raw_code,
                        normalize=normalize_a_share_code,
                    )
                else:
                    codes = remove_research_code(
                        context.watchlist_path,
                        raw_code,
                        normalize=normalize_a_share_code,
                    )
                self._send_json({"codes": list(codes), "research_only": True})
            except (ResearchWebError, ResearchWatchlistError) as exc:
                self._send_json({"error": exc.code, "detail": str(exc)}, HTTPStatus.BAD_REQUEST)
            except Exception:
                self._send_json(
                    {"error": "internal_error", "detail": "自选研究列表更新失败"},
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                )

        def _read_json_body(self) -> dict[str, Any]:
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError as exc:
                raise ResearchWebError("invalid_request", "Content-Length 无效") from exc
            if length < 1 or length > 4096:
                raise ResearchWebError("invalid_request", "请求正文大小无效")
            try:
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ResearchWebError("invalid_request", "请求正文必须是 JSON") from exc
            if not isinstance(payload, dict):
                raise ResearchWebError("invalid_request", "请求正文必须是 JSON 对象")
            return payload

        def _send_json(self, payload: Mapping[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
            content = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

        def _send_static(self, filename: str) -> None:
            path = _STATIC_ROOT / filename
            content = path.read_bytes()
            content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", f"{content_type}; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

        def log_message(self, format: str, *args: object) -> None:
            print(f"[research-web] {self.address_string()} {format % args}")

    return ResearchRequestHandler


def serve(context: ResearchWebContext, *, host: str = "127.0.0.1", port: int = 9091) -> None:
    """Run the local read-only research server until interrupted."""

    server = HTTPServer((host, port), make_handler(context))
    print(f"NCN K线研究台: http://{host}:{server.server_port}")
    print("边界: 只读研究，不提供持仓、收益、回测、下单或交易接口。")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="NCN read-only candlestick research web console")
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--data-root", type=Path)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9091)
    args = parser.parse_args(argv)
    context = create_context(
        args.project_root,
        data_root=args.data_root,
        output_root=args.output_root,
        config_path=args.config,
    )
    serve(context, host=args.host, port=args.port)
    return 0


def _resolve_from_root(root: Path, value: str | Path) -> Path:
    path = Path(value).expanduser()
    return (root / path).resolve() if not path.is_absolute() else path.resolve()


def _read_json_object(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ResearchWebError("invalid_publication", f"{label} 不是有效 JSON") from exc
    if not isinstance(payload, dict):
        raise ResearchWebError("invalid_publication", f"{label} 必须是 JSON 对象")
    return payload


def _published_run_directory(output_root: Path, latest: Mapping[str, Any]) -> Path:
    run_name = latest.get("run_directory")
    if not isinstance(run_name, str) or not run_name or Path(run_name).name != run_name:
        raise ResearchWebError("invalid_publication", "latest.json 包含无效 run_directory")
    run_directory = (output_root / run_name).resolve()
    if run_directory.parent != output_root.resolve():
        raise ResearchWebError("invalid_publication", "run_directory 超出发布目录")
    return run_directory


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


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
                    "status": status,
                    "confirmation_date": confirmation_date,
                    "volume_ratio": volume_ratio,
                }
            )
    return annotations


def _build_research_alert(
    bars: Sequence[Mapping[str, Any]],
    annotations: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Build a transparent research state without portfolio or trade semantics."""

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
    if upper_shadow_ratio > 0.40:
        return {
            "state": "risk_observation",
            "title": "长上影风险观察",
            "detail": "最新已完成 K 线上影超过全天振幅 40%",
            "evidence": [f"upper_shadow_ratio={upper_shadow_ratio:.2f}"],
            "research_only": True,
        }

    latest_timestamp = str(latest.get("timestamp") or latest.get("date"))
    confirmed = [
        item
        for item in annotations
        if item.get("status") == "confirmed"
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
    pending = [item for item in annotations if item.get("status") == "pending"]
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


if __name__ == "__main__":
    raise SystemExit(main())
