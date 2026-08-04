from __future__ import annotations

from datetime import datetime

import pytest

from ashare_edge_scout.intraday_data import (
    IntradayDataClient,
    IntradayDataError,
    SHANGHAI,
    freshness_payload,
    parse_eastmoney_minute_bars,
    parse_sina_snapshot,
)


def test_parse_sina_snapshot_keeps_source_timestamp() -> None:
    fields = ["测试股份", "10.00", "9.80", "10.10", "10.20", "9.90", "0", "0", "1200", "12120"]
    fields.extend(["0"] * 20)
    fields.extend(["2026-08-04", "10:15:03", "00"])
    body = f'var hq_str_sh600000="{",".join(fields)}";'

    snapshot = parse_sina_snapshot(
        body,
        "sh.600000",
        fetched_at=datetime(2026, 8, 4, 10, 15, 10, tzinfo=SHANGHAI),
    )

    assert snapshot.price == 10.1
    assert snapshot.pct_chg == pytest.approx(3.06122449)
    assert snapshot.source_timestamp.isoformat() == "2026-08-04T10:15:03+08:00"


def test_parse_minute_bars_filters_break_and_marks_active_one_minute() -> None:
    payload = {
        "data": {
            "trends": [
                "2026-08-04 11:29,0,10.1,10.2,9.9,100,1010,10.05",
                "2026-08-04 12:00,0,10.1,10.2,10.0,50,505,10.10",
                "2026-08-04 13:00,0,10.2,10.3,10.0,200,2040,10.20",
            ]
        }
    }
    batch = parse_eastmoney_minute_bars(
        payload,
        "sh.600000",
        "1m",
        fetched_at=datetime(2026, 8, 4, 13, 0, 20, tzinfo=SHANGHAI),
        limit=30,
    )

    assert len(batch.bars) == 2
    assert batch.bars[-1].is_forming is True
    assert batch.bars[-1].open == 10.1
    assert "provider_1m_history_limited_to_recent_5_days" in batch.warnings
    assert "provider_1m_open_derived_from_previous_close" in batch.warnings


def test_parse_minute_bars_rejects_duplicate_timestamps() -> None:
    row = "2026-08-04 10:00,10.0,10.1,10.2,9.9,100,1010,1,1,1,1"
    with pytest.raises(IntradayDataError) as error:
        parse_eastmoney_minute_bars(
            {"data": {"klines": [row, row]}},
            "sh.600000",
            "5m",
            fetched_at=datetime(2026, 8, 4, 10, 1, tzinfo=SHANGHAI),
            limit=30,
        )
    assert error.value.code == "duplicate_intraday_bar"


def test_freshness_distinguishes_open_market_and_closed_market() -> None:
    fresh = freshness_payload(
        datetime(2026, 8, 4, 10, 0, tzinfo=SHANGHAI),
        datetime(2026, 8, 4, 10, 0, 10, tzinfo=SHANGHAI),
        expected_interval_seconds=15,
    )
    closed = freshness_payload(
        datetime(2026, 8, 4, 15, 0, tzinfo=SHANGHAI),
        datetime(2026, 8, 4, 18, 0, tzinfo=SHANGHAI),
        expected_interval_seconds=15,
    )
    assert fresh["status"] == "fresh"
    assert closed["status"] == "market_closed"


def test_client_caches_identical_snapshot_request() -> None:
    fields = ["测试股份", "10", "10", "10", "10", "10", "0", "0", "100", "1000"]
    fields.extend(["0"] * 20)
    fields.extend(["2026-08-04", "10:00:00", "00"])
    calls = 0

    def opener(request, timeout):
        nonlocal calls
        calls += 1
        return f'var hq_str_sh600000="{",".join(fields)}";'.encode("gb18030")

    client = IntradayDataClient(
        opener=opener,
        clock=lambda: datetime(2026, 8, 4, 10, 0, 5, tzinfo=SHANGHAI),
    )
    assert client.fetch_snapshot("sh.600000") == client.fetch_snapshot("sh.600000")
    assert calls == 1


def test_client_uses_explicit_last_observation_when_refresh_fails() -> None:
    fields = ["测试股份", "10", "10", "10", "10", "10", "0", "0", "100", "1000"]
    fields.extend(["0"] * 20)
    fields.extend(["2026-08-04", "10:00:00", "00"])
    calls = 0

    def opener(request, timeout):
        nonlocal calls
        calls += 1
        if calls > 1:
            raise OSError("temporary provider failure")
        return f'var hq_str_sh600000="{",".join(fields)}";'.encode("gb18030")

    client = IntradayDataClient(
        opener=opener,
        cache_ttl_seconds=0,
        max_retries=1,
        clock=lambda: datetime(2026, 8, 4, 10, 0, 5, tzinfo=SHANGHAI),
    )
    first = client.fetch_snapshot("sh.600000")
    fallback = client.fetch_snapshot("sh.600000")

    assert fallback.price == first.price
    assert "provider_refresh_failed_using_last_observation" in fallback.warnings
