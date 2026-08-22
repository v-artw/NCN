from __future__ import annotations

from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from ashare_edge_scout.paper_trading_snapshot import paper_data_status_payload


def test_paper_data_status_reports_missing_as_warning(tmp_path: Path) -> None:
    payload = paper_data_status_payload(
        portfolio_id="default",
        positions={"sh.600000": {}},
        data_root=tmp_path,
        max_snapshot_codes=20,
    )

    assert payload["statuses"][0]["status"] == "missing"
    assert "missing_research_parquet" in payload["freshness_warnings"]
    assert "not_execution_freshness" in payload["limitations"]


def test_paper_data_status_reads_local_research_parquet(tmp_path: Path) -> None:
    pq.write_table(pa.Table.from_pylist([_bar()]), tmp_path / "sh.600000.parquet")

    payload = paper_data_status_payload(
        portfolio_id="default",
        positions={"sh.600000": {}},
        data_root=tmp_path,
        max_snapshot_codes=20,
    )

    assert payload["statuses"][0]["status"] == "available"
    assert payload["statuses"][0]["latest_date"] == "2026-08-21"
    assert payload["paper_only"] is True


def _bar() -> dict[str, object]:
    return {
        "code": "sh.600000",
        "date": "2026-08-21",
        "open": 10.0,
        "high": 10.5,
        "low": 9.8,
        "close": 10.2,
        "preclose": 10.0,
        "volume": 1000.0,
        "amount": 10200.0,
        "turn": 1.0,
        "tradestatus": "1",
        "isST": "0",
    }
