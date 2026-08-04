from __future__ import annotations

import csv
import json
from datetime import datetime, timedelta
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from ashare_edge_scout.intraday_data import MinuteBar, MinuteBarBatch, QuoteSnapshot, SHANGHAI
from ashare_edge_scout.research_web import (
    ResearchWebError,
    create_context,
    load_candle_research,
    load_dashboard,
    load_snapshot_research,
    normalize_a_share_code,
    _build_research_alert,
)
from ashare_edge_scout.research_watchlist import add_research_code


ROOT = Path(__file__).parents[1]


def test_normalize_a_share_code() -> None:
    assert normalize_a_share_code("600000") == "sh.600000"
    assert normalize_a_share_code("000001") == "sz.000001"
    assert normalize_a_share_code("SH.600000") == "sh.600000"
    with pytest.raises(ResearchWebError, match="无法识别"):
        normalize_a_share_code("../600000")


def test_load_dashboard_reads_only_latest_publication(tmp_path: Path) -> None:
    output_root = tmp_path / "output"
    run = output_root / "run-1"
    run.mkdir(parents=True)
    (output_root / "latest.json").write_text(
        json.dumps({"run_id": "run-1", "run_directory": "run-1", "as_of": "2026-01-02"}),
        encoding="utf-8",
    )
    (run / "summary.json").write_text(
        json.dumps({"as_of": "2026-01-02", "status": "success", "input_code_count": 1}),
        encoding="utf-8",
    )
    with (run / "daily_research_watchlist.csv").open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=["rank", "code"])
        writer.writeheader()
        writer.writerow({"rank": 1, "code": "sh.600000"})

    watchlist_path = tmp_path / "research_watchlist.json"
    add_research_code(watchlist_path, "600000", normalize=normalize_a_share_code)
    context = create_context(ROOT, output_root=output_root, watchlist_path=watchlist_path)
    payload = load_dashboard(context)

    assert payload["research_only"] is True
    assert payload["watchlist"] == [{"rank": "1", "code": "sh.600000"}]
    assert payload["selected_codes"] == ["sh.600000"]


def test_load_dashboard_rejects_run_path_traversal(tmp_path: Path) -> None:
    output_root = tmp_path / "output"
    output_root.mkdir()
    (output_root / "latest.json").write_text(
        json.dumps({"run_directory": "../outside"}), encoding="utf-8"
    )
    context = create_context(ROOT, output_root=output_root)
    with pytest.raises(ResearchWebError, match="run_directory"):
        load_dashboard(context)


def test_candle_payload_marks_confirmed_book_pattern(tmp_path: Path) -> None:
    data_root = tmp_path / "bars"
    data_root.mkdir()
    rows = []
    closes = [12.0, 11.8, 11.5, 11.2, 10.9, 10.7, 10.5, 10.3, 10.1, 9.9,
              9.8, 9.7, 9.6, 9.5, 9.4, 9.3, 9.2, 9.1, 9.0, 8.9,
              8.8, 8.7, 8.6, 8.5, 8.4, 8.3, 8.2, 8.1, 8.0, 7.9]
    for index, close in enumerate(closes):
        open_price = close + 0.1
        rows.append(_bar(index, open_price, open_price + 0.1, close - 0.1, close, 100.0))
    rows.append(_bar(30, 7.75, 7.85, 7.0, 7.8, 100.0))  # hammer after decline
    rows.append(_bar(31, 7.82, 8.2, 7.8, 8.1, 200.0))   # price + volume confirmation
    pq.write_table(pa.Table.from_pylist(rows), data_root / "sh.600000.parquet")

    context = create_context(ROOT, data_root=data_root)
    payload = load_candle_research(context, "600000", limit=30)

    hammer = next(item for item in payload["annotations"] if item["pattern"] == "hammer")
    assert hammer["status"] == "confirmed"
    assert hammer["confirmation_date"] == "2026-02-01"
    assert payload["research_only"] is True
    assert payload["period"] == "1d"
    assert payload["bars"][-1]["is_forming"] is False
    assert len(payload["bars"]) == 30


def test_intraday_payload_uses_provider_metadata_and_excludes_forming_pattern() -> None:
    now = datetime(2026, 8, 4, 10, 1, tzinfo=SHANGHAI)
    client = _FakeIntradayClient(now)
    context = create_context(ROOT, intraday_client=client)

    payload = load_candle_research(context, "600000", period="5m", limit=30)

    assert payload["period"] == "5m"
    assert payload["provenance"]["provider"] == "test_provider"
    assert payload["bars"][-1]["is_forming"] is True
    assert payload["methodology"]["forming_bar_excluded"] is True


def test_snapshot_payload_exposes_freshness() -> None:
    now = datetime(2026, 8, 4, 10, 1, tzinfo=SHANGHAI)
    context = create_context(ROOT, intraday_client=_FakeIntradayClient(now))

    payload = load_snapshot_research(context, "600000")

    assert payload["snapshot"]["provider"] == "test_snapshot"
    assert payload["freshness"]["status"] == "fresh"
    assert payload["research_only"] is True


def test_invalid_candle_period_is_rejected() -> None:
    context = create_context(ROOT)
    with pytest.raises(ResearchWebError) as error:
        load_candle_research(context, "600000", period="2m")
    assert error.value.code == "invalid_period"


def test_web_assets_include_visibility_aware_auto_refresh() -> None:
    static_root = ROOT / "src" / "ashare_edge_scout" / "web_static"
    script = (static_root / "app.js").read_text(encoding="utf-8")
    markup = (static_root / "index.html").read_text(encoding="utf-8")

    assert "SNAPSHOT_REFRESH_MS = 15000" in script
    assert "INTRADAY_REFRESH_MS = 15000" in script
    assert "DAILY_REFRESH_MS = 60000" in script
    assert 'addEventListener("visibilitychange"' in script
    assert "setInterval(refreshScheduler, 1000)" in script
    assert 'id="refreshStatus"' in markup
    assert 'id="addStockForm"' in markup
    assert 'id="researchAlert"' in markup


def test_research_alert_prioritizes_ma60_risk_over_pattern() -> None:
    bars = [_alert_bar(close=9.0, ma20=10.0, ma60=9.5)]
    alert = _build_research_alert(
        bars,
        [{"status": "confirmed", "confirmation_date": "2026-08-04", "label": "看涨吞没"}],
    )
    assert alert["state"] == "risk_observation"
    assert "latest_close_at_or_below_ma60" in alert["evidence"]


def test_research_alert_reports_confirmed_pattern_with_healthy_structure() -> None:
    bars = [_alert_bar(close=11.0, ma20=10.5, ma60=10.0)]
    alert = _build_research_alert(
        bars,
        [{"status": "confirmed", "confirmation_date": "2026-08-04", "label": "看涨吞没"}],
    )
    assert alert["state"] == "bullish_setup_confirmed"
    assert alert["research_only"] is True


def _alert_bar(*, close: float, ma20: float, ma60: float) -> dict[str, object]:
    return {
        "date": "2026-08-04",
        "timestamp": "2026-08-04",
        "open": close - 0.1,
        "high": close + 0.1,
        "low": close - 0.2,
        "close": close,
        "volume": 100.0,
        "volume_ma20": 100.0,
        "ma20": ma20,
        "ma60": ma60,
        "is_forming": False,
    }


def _bar(index: int, open_price: float, high: float, low: float, close: float, volume: float) -> dict[str, object]:
    day = index + 1
    return {
        "code": "sh.600000",
        "date": f"2026-01-{day:02d}" if day <= 31 else "2026-02-01",
        "open": open_price,
        "high": high,
        "low": low,
        "close": close,
        "preclose": close,
        "volume": volume,
        "amount": volume * close,
        "turn": 1.0,
        "tradestatus": "1",
        "isST": "0",
    }


class _FakeIntradayClient:
    def __init__(self, now: datetime) -> None:
        self.now = now

    def fetch_snapshot(self, code: str) -> QuoteSnapshot:
        return QuoteSnapshot(
            code=code,
            name="测试股份",
            price=10.1,
            open=10.0,
            high=10.2,
            low=9.9,
            pre_close=10.0,
            volume=1000,
            amount=10100,
            pct_chg=1.0,
            source_timestamp=self.now - timedelta(seconds=5),
            fetched_at=self.now,
            provider="test_snapshot",
        )

    def fetch_minute_bars(self, code: str, period: str, *, limit: int) -> MinuteBarBatch:
        bars = tuple(
            MinuteBar(
                timestamp=self.now - timedelta(minutes=(31 - index) * 5),
                open=10 + index * 0.01,
                high=10.2 + index * 0.01,
                low=9.9 + index * 0.01,
                close=10.1 + index * 0.01,
                volume=100 + index,
                amount=1000 + index,
                is_forming=index == 31,
            )
            for index in range(32)
        )
        return MinuteBarBatch(
            code=code,
            period=period,
            bars=bars[-limit:],
            source_timestamp=bars[-1].timestamp,
            fetched_at=self.now,
            provider="test_provider",
        )
