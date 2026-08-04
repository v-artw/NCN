from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[1] / "Autobaostock_download.py"
SPEC = importlib.util.spec_from_file_location("autobaostock_download_test", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = module
SPEC.loader.exec_module(module)


def test_download_summary_passes_below_failure_threshold() -> None:
    summary = module.build_download_summary(
        requested_end_date="2026-07-23",
        effective_end_date="2026-07-23",
        stock_list_date="2026-07-23",
        locked_trade_date="2026-07-23",
        total=100,
        updated_count=10,
        failed_count=5,
        timeout_count=4,
        data_dir="PFrontStockData",
        max_failure_rate=0.10,
    )

    assert summary["status"] == "success"
    assert summary["failure_count"] == 9
    assert summary["failure_rate"] == pytest.approx(0.09)
    assert summary["incremental"] is True
    assert summary["clean_before_download"] is False


def test_download_summary_fails_above_threshold_and_on_zero_total() -> None:
    failed = module.build_download_summary(
        requested_end_date="2026-07-23",
        effective_end_date="2026-07-23",
        stock_list_date="2026-07-23",
        locked_trade_date="2026-07-23",
        total=100,
        updated_count=0,
        failed_count=11,
        timeout_count=0,
        data_dir="PFrontStockData",
        max_failure_rate=0.10,
    )
    empty = module.build_download_summary(
        requested_end_date="2026-07-23",
        effective_end_date="2026-07-23",
        stock_list_date="2026-07-23",
        locked_trade_date="",
        total=0,
        updated_count=0,
        failed_count=0,
        timeout_count=0,
        data_dir="PFrontStockData",
        max_failure_rate=0.10,
    )

    assert failed["status"] == "failed"
    assert empty["status"] == "failed"
    assert empty["failure_rate"] == 1.0


def test_write_summary_json_is_atomic(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "summary.json"
    module.write_summary_json(path, {"status": "success", "total": 10})

    assert json.loads(path.read_text(encoding="utf-8")) == {"status": "success", "total": 10}
    assert not (path.parent / "summary.json.tmp").exists()


def test_parse_args_supports_stock_list_date_and_summary(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(SCRIPT),
            "--stock-list-date",
            "2026-07-23",
            "--max-failure-rate",
            "0.05",
            "--summary-json",
            str(tmp_path / "summary.json"),
            "--no-clean",
        ],
    )

    args = module.parse_args()

    assert args.stock_list_date == "2026-07-23"
    assert args.max_failure_rate == pytest.approx(0.05)
    assert args.summary_json.endswith("summary.json")
    assert args.no_clean is True
    assert args.clean is False
