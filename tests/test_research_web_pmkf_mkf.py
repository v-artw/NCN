from __future__ import annotations

from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from ashare_edge_scout.research_web import create_context, pmkf_mkf_code_payload

ROOT = Path(__file__).parents[1]


def test_pmkf_mkf_code_uses_ohlcv_when_turn_is_missing(tmp_path: Path) -> None:
    data_root = tmp_path / "bars"
    data_root.mkdir()
    pq.write_table(pa.Table.from_pylist([_bar(index) for index in range(40)]), data_root / "sh.600000.parquet")
    context = create_context(ROOT, data_root=data_root)

    payload = pmkf_mkf_code_payload(context, "600000")

    assert payload["schema_version"] == "ncn_pmkf_mkf_code_v1"
    assert payload["code"] == "sh.600000"
    assert payload["bar_count"] == 40
    assert payload["allow_live_order_submission"] is False
    assert "strict_candle_payload_unavailable:schema_missing_required_field" in payload["provenance"]["warnings"]


def _bar(index: int) -> dict[str, object]:
    return {
        "code": "sh.600000",
        "date": f"2026-07-{index + 1:02d}" if index < 31 else f"2026-08-{index - 30:02d}",
        "open": 10.0 + index * 0.01,
        "high": 10.2 + index * 0.01,
        "low": 9.9 + index * 0.01,
        "close": 10.1 + index * 0.01,
        "volume": 1000.0 + index,
    }
