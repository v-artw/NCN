"""Read-only intraday market-data adapters for research display.

The adapters intentionally expose provenance, source timestamps, freshness and
forming-bar state. They do not provide execution, portfolio or return inputs.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass, replace
from datetime import datetime, time as wall_time, timedelta
from math import isfinite
from threading import Lock
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo


SHANGHAI = ZoneInfo("Asia/Shanghai")
SUPPORTED_MINUTE_PERIODS = ("1m", "5m", "15m", "30m", "60m")
_SINA_URL = "https://hq.sinajs.cn/list={symbols}"
_EASTMONEY_KLINE_URL = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
_EASTMONEY_TRENDS_URL = "https://push2his.eastmoney.com/api/qt/stock/trends2/get"
_EASTMONEY_UT = "7eea3edcaed734bea9cbfc24409ed989"


class IntradayDataError(ValueError):
    """Stable provider or validation error for intraday research data."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        super().__init__(detail)


@dataclass(frozen=True)
class QuoteSnapshot:
    code: str
    name: str
    price: float
    open: float
    high: float
    low: float
    pre_close: float
    volume: float
    amount: float
    pct_chg: float
    source_timestamp: datetime
    fetched_at: datetime
    provider: str = "sina_https_snapshot"
    adjustment: str = "unadjusted"
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["source_timestamp"] = self.source_timestamp.isoformat()
        payload["fetched_at"] = self.fetched_at.isoformat()
        return payload


@dataclass(frozen=True)
class MinuteBar:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    amount: float
    is_forming: bool

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["timestamp"] = self.timestamp.isoformat()
        return payload


@dataclass(frozen=True)
class MinuteBarBatch:
    code: str
    period: str
    bars: tuple[MinuteBar, ...]
    source_timestamp: datetime
    fetched_at: datetime
    provider: str = "eastmoney_https"
    adjustment: str = "qfq_research_only"
    warnings: tuple[str, ...] = ()


class IntradayDataClient:
    """Small cached client for Sina snapshots and Eastmoney minute bars."""

    def __init__(
        self,
        *,
        timeout_seconds: float = 8.0,
        cache_ttl_seconds: float = 12.0,
        max_retries: int = 3,
        opener: Callable[[Request, float], bytes] | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.cache_ttl_seconds = cache_ttl_seconds
        self.max_retries = max(1, max_retries)
        self._opener = opener or _read_url
        self._clock = clock or (lambda: datetime.now(SHANGHAI))
        self._cache: dict[tuple[str, ...], tuple[float, Any]] = {}
        self._last_good: dict[tuple[str, ...], Any] = {}
        self._lock = Lock()

    def fetch_snapshot(self, code: str) -> QuoteSnapshot:
        key = ("snapshot", code)
        cached = self._cached(key)
        if cached is not None:
            return cached
        symbol = code.replace(".", "")
        request = Request(
            _SINA_URL.format(symbols=symbol),
            headers={"User-Agent": "Mozilla/5.0", "Referer": "https://finance.sina.com.cn/"},
        )
        try:
            body = self._open_with_retries(request).decode("gb18030")
            snapshot = parse_sina_snapshot(body, code, fetched_at=self._clock())
        except IntradayDataError:
            raise
        except Exception as exc:
            fallback = self._last_good.get(key)
            if fallback is None:
                raise IntradayDataError("snapshot_unavailable", f"新浪行情快照不可用: {exc}") from exc
            return replace(
                fallback,
                fetched_at=self._clock(),
                warnings=(*fallback.warnings, "provider_refresh_failed_using_last_observation"),
            )
        self._store(key, snapshot)
        return snapshot

    def fetch_minute_bars(self, code: str, period: str, *, limit: int = 120) -> MinuteBarBatch:
        validate_minute_period(period)
        key = ("minutes", code, period, str(limit))
        cached = self._cached(key)
        if cached is not None:
            return cached
        now = self._clock()
        try:
            payload = self._fetch_eastmoney_payload(code, period, limit)
            batch = parse_eastmoney_minute_bars(payload, code, period, fetched_at=now, limit=limit)
        except IntradayDataError:
            raise
        except Exception as exc:
            fallback = self._last_good.get(key)
            if fallback is None:
                raise IntradayDataError("intraday_unavailable", f"东方财富分钟数据不可用: {exc}") from exc
            return replace(
                fallback,
                fetched_at=self._clock(),
                warnings=(*fallback.warnings, "provider_refresh_failed_using_last_observation"),
            )
        self._store(key, batch)
        return batch

    def _fetch_eastmoney_payload(self, code: str, period: str, limit: int) -> Mapping[str, Any]:
        market = "1" if code.startswith("sh.") else "0"
        symbol = code.split(".", 1)[1]
        if period == "1m":
            url = _EASTMONEY_TRENDS_URL
            params = {
                "fields1": "f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11,f12,f13",
                "fields2": "f51,f52,f53,f54,f55,f56,f57,f58",
                "ut": _EASTMONEY_UT,
                "ndays": "5",
                "iscr": "0",
                "secid": f"{market}.{symbol}",
            }
        else:
            url = _EASTMONEY_KLINE_URL
            params = {
                "fields1": "f1,f2,f3,f4,f5,f6",
                "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
                "ut": _EASTMONEY_UT,
                "klt": period[:-1],
                "fqt": "1",
                "secid": f"{market}.{symbol}",
                "beg": "0",
                "end": "20500000",
                "lmt": str(max(limit, 120)),
            }
        request = Request(f"{url}?{urlencode(params)}", headers={"User-Agent": "Mozilla/5.0"})
        raw = self._open_with_retries(request)
        decoded = json.loads(raw.decode("utf-8"))
        if not isinstance(decoded, Mapping):
            raise IntradayDataError("invalid_intraday_response", "分钟数据响应不是 JSON 对象")
        return decoded

    def _open_with_retries(self, request: Request) -> bytes:
        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                return self._opener(request, self.timeout_seconds)
            except Exception as exc:
                last_error = exc
                if attempt + 1 < self.max_retries:
                    time.sleep(0.35 * (2**attempt))
        assert last_error is not None
        raise last_error

    def _cached(self, key: tuple[str, ...]) -> Any | None:
        with self._lock:
            item = self._cache.get(key)
            if item is None or time.monotonic() - item[0] > self.cache_ttl_seconds:
                self._cache.pop(key, None)
                return None
            return item[1]

    def _store(self, key: tuple[str, ...], value: Any) -> None:
        with self._lock:
            self._cache[key] = (time.monotonic(), value)
            self._last_good[key] = value


def parse_sina_snapshot(body: str, code: str, *, fetched_at: datetime) -> QuoteSnapshot:
    """Parse one Sina quote while retaining the provider's date and time."""

    match = re.search(r'="(.*)";?\s*$', body.strip())
    if not match or not match.group(1):
        raise IntradayDataError("snapshot_missing", f"新浪未返回 {code} 行情")
    fields = match.group(1).split(",")
    if len(fields) < 32:
        raise IntradayDataError("invalid_snapshot_response", "新浪行情字段不完整")
    try:
        source_timestamp = datetime.strptime(
            f"{fields[30]} {fields[31]}", "%Y-%m-%d %H:%M:%S"
        ).replace(tzinfo=SHANGHAI)
        values = [_finite_non_negative(fields[index], f"snapshot[{index}]") for index in (1, 2, 3, 4, 5, 8, 9)]
    except ValueError as exc:
        raise IntradayDataError("invalid_snapshot_response", f"新浪行情字段无效: {exc}") from exc
    open_price, pre_close, price, high, low, volume, amount = values
    if price <= 0 or pre_close <= 0 or high < low:
        raise IntradayDataError("invalid_snapshot_response", "新浪行情价格范围无效或证券停牌")
    return QuoteSnapshot(
        code=code,
        name=fields[0],
        price=price,
        open=open_price,
        high=high,
        low=low,
        pre_close=pre_close,
        volume=volume,
        amount=amount,
        pct_chg=(price / pre_close - 1.0) * 100.0,
        source_timestamp=source_timestamp,
        fetched_at=_aware_shanghai(fetched_at),
    )


def parse_eastmoney_minute_bars(
    payload: Mapping[str, Any],
    code: str,
    period: str,
    *,
    fetched_at: datetime,
    limit: int,
) -> MinuteBarBatch:
    """Normalize and strictly validate an Eastmoney minute response."""

    validate_minute_period(period)
    data = payload.get("data")
    if not isinstance(data, Mapping):
        raise IntradayDataError("intraday_missing", f"东方财富未返回 {code} 分钟数据")
    raw_rows = data.get("trends" if period == "1m" else "klines")
    if not isinstance(raw_rows, Sequence) or isinstance(raw_rows, (str, bytes)) or not raw_rows:
        raise IntradayDataError("intraday_missing", f"东方财富未返回 {code} {period} K线")

    parsed: list[tuple[datetime, float, float, float, float, float, float]] = []
    derived_one_minute_open = False
    for index, raw in enumerate(raw_rows):
        if not isinstance(raw, str):
            raise IntradayDataError("invalid_intraday_response", f"分钟数据第 {index} 行不是字符串")
        fields = raw.split(",")
        if len(fields) < 7:
            raise IntradayDataError("invalid_intraday_response", f"分钟数据第 {index} 行字段不完整")
        try:
            timestamp = datetime.strptime(fields[0], "%Y-%m-%d %H:%M").replace(tzinfo=SHANGHAI)
        except ValueError as exc:
            raise IntradayDataError("invalid_intraday_timestamp", f"分钟数据时间无效: {fields[0]}") from exc
        if not is_a_share_session_time(timestamp.time()):
            continue
        close = _finite_positive(fields[2], "close")
        raw_open = _finite_non_negative(fields[1], "open")
        if period == "1m" and raw_open == 0:
            open_price = parsed[-1][4] if parsed else close
            derived_one_minute_open = True
        elif raw_open > 0:
            open_price = raw_open
        else:
            raise IntradayDataError("invalid_intraday_value", "open 必须为正数")
        high = _finite_positive(fields[3], "high")
        low = _finite_positive(fields[4], "low")
        if period == "1m" and raw_open == 0:
            high = max(high, open_price)
            low = min(low, open_price)
        volume = _finite_non_negative(fields[5], "volume")
        amount = _finite_non_negative(fields[6], "amount")
        if high < max(open_price, close, low) or low > min(open_price, close, high):
            raise IntradayDataError("invalid_intraday_ohlc", f"分钟数据 {fields[0]} OHLC 范围无效")
        parsed.append((timestamp, open_price, high, low, close, volume, amount))
    if not parsed:
        raise IntradayDataError("intraday_missing", "分钟响应中没有有效 A 股交易时段 K线")
    parsed.sort(key=lambda item: item[0])
    timestamps = [item[0] for item in parsed]
    if len(set(timestamps)) != len(timestamps):
        raise IntradayDataError("duplicate_intraday_bar", "分钟数据包含重复时间戳")

    now = _aware_shanghai(fetched_at)
    selected = parsed[-limit:]
    bars = tuple(
        MinuteBar(
            timestamp=item[0],
            open=item[1],
            high=item[2],
            low=item[3],
            close=item[4],
            volume=item[5],
            amount=item[6],
            is_forming=(position == len(selected) - 1 and _is_forming_bar(item[0], period, now)),
        )
        for position, item in enumerate(selected)
    )
    warnings: list[str] = []
    if period == "1m":
        warnings.append("provider_1m_history_limited_to_recent_5_days")
    if derived_one_minute_open:
        warnings.append("provider_1m_open_derived_from_previous_close")
    if bars[-1].is_forming:
        warnings.append("latest_bar_is_forming")
    return MinuteBarBatch(
        code=code,
        period=period,
        bars=bars,
        source_timestamp=bars[-1].timestamp,
        fetched_at=now,
        warnings=tuple(warnings),
    )


def freshness_payload(
    source_timestamp: datetime,
    fetched_at: datetime,
    *,
    expected_interval_seconds: int,
) -> dict[str, Any]:
    """Classify observable age without claiming an exchange latency SLA."""

    source = _aware_shanghai(source_timestamp)
    fetched = _aware_shanghai(fetched_at)
    lag = max(0.0, (fetched - source).total_seconds())
    if not is_market_open(fetched):
        status = "market_closed"
        detail = "当前不在 A 股连续竞价时段"
    elif lag <= expected_interval_seconds * 2:
        status = "fresh"
        detail = "数据时间在研究刷新阈值内"
    elif lag <= max(expected_interval_seconds * 5, 300):
        status = "delayed"
        detail = "数据有延迟，请核对源时间"
    else:
        status = "stale"
        detail = "数据已过期，不应作为当前盘中状态"
    return {
        "status": status,
        "source_timestamp": source.isoformat(),
        "fetched_at": fetched.isoformat(),
        "lag_seconds": lag,
        "detail": detail,
    }


def validate_minute_period(period: str) -> None:
    if period not in SUPPORTED_MINUTE_PERIODS:
        raise IntradayDataError("invalid_period", f"不支持的分钟周期: {period}")


def is_a_share_session_time(value: wall_time) -> bool:
    return wall_time(9, 30) <= value <= wall_time(11, 30) or wall_time(13, 0) <= value <= wall_time(15, 0)


def is_market_open(value: datetime) -> bool:
    local = _aware_shanghai(value)
    return local.weekday() < 5 and is_a_share_session_time(local.time())


def _is_forming_bar(timestamp: datetime, period: str, now: datetime) -> bool:
    if timestamp.date() != now.date() or not is_market_open(now):
        return False
    minutes = int(period[:-1])
    # Eastmoney timestamps completed multi-minute bars by their interval end;
    # 1m trends label the active minute, so it remains forming for one minute.
    bar_end = timestamp + timedelta(minutes=1) if minutes == 1 else timestamp
    return now < bar_end


def _finite_positive(value: Any, name: str) -> float:
    parsed = _finite_non_negative(value, name)
    if parsed <= 0:
        raise IntradayDataError("invalid_intraday_value", f"{name} 必须为正数")
    return parsed


def _finite_non_negative(value: Any, name: str) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise IntradayDataError("invalid_intraday_value", f"{name} 必须是数值") from exc
    if not isfinite(parsed) or parsed < 0:
        raise IntradayDataError("invalid_intraday_value", f"{name} 必须是有限非负数")
    return parsed


def _aware_shanghai(value: datetime) -> datetime:
    return value.replace(tzinfo=SHANGHAI) if value.tzinfo is None else value.astimezone(SHANGHAI)


def _read_url(request: Request, timeout: float) -> bytes:
    with urlopen(request, timeout=timeout) as response:
        return response.read()
