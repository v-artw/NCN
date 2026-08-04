"""Regression tests for Edge Scout's research-only terminal tables."""

from __future__ import annotations

import csv
import importlib.util
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "run_edge_scout_scan.py"
SPEC = importlib.util.spec_from_file_location("run_edge_scout_scan", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _write_csv(path: Path, fieldnames: list[str], row: dict[str, object]) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerow(row)


def test_reference_and_discovery_tables_are_printed_independently(tmp_path, capsys):
    reference_path = tmp_path / "reference_prices.csv"
    _write_csv(
        reference_path,
        [
            "rank", "code", "tier", "edge_score", "valid_setup_confirmed",
            "buy_reference", "stop_reference", "partial_take_profit_reference",
            "take_profit_reference", "risk_distance_pct",
        ],
        {
            "rank": 1,
            "code": "sh.600001",
            "tier": "near_miss",
            "edge_score": "40.000000",
            "valid_setup_confirmed": True,
            "buy_reference": "10.5000",
            "stop_reference": "10.0000",
            "partial_take_profit_reference": "11.2500",
            "take_profit_reference": "11.5000",
            "risk_distance_pct": "0.047619",
        },
    )
    discovery_path = tmp_path / "discovery.csv"
    _write_csv(
        discovery_path,
        [
            "code", "discovery_tier", "discovery_eligible", "start_signal_count",
            "discovery_score", "pct_chg", "ret_5d", "start_signals",
            "pmk_trend_reason", "pmk_shape_pattern", "candle_confirm_reason",
        ],
        {
            "code": "sh.600002",
            "discovery_tier": "profit_shadow",
            "discovery_eligible": True,
            "start_signal_count": 3,
            "discovery_score": "88.0",
            "pct_chg": "2.0",
            "ret_5d": "4.0",
            "start_signals": "dxbd_up|gding_up|dingdi_safe_up",
            "pmk_trend_reason": "Trend+MACD",
            "pmk_shape_pattern": "Steady Climber",
            "candle_confirm_reason": "healthy_volume",
        },
    )

    MODULE.print_top_reference_prices(reference_path)
    MODULE.print_top_discovery(discovery_path)
    output = capsys.readouterr().out

    assert "TOP 10 研究观察样本" in output
    assert "sh.600001" in output
    assert "CNstock 风格发现层 TOP" in output
    assert "sh.600002" in output
    assert output.index("sh.600001") < output.index("sh.600002")


def test_console_progress_reports_stage_interval_and_completion(capsys):
    reporter = MODULE.ConsoleProgressReporter()

    reporter.update("data_admission", 0, 250, None)
    reporter.update("data_admission", 99, 250, "sh.600099")
    reporter.update("data_admission", 100, 250, "sh.600100")
    reporter.update("data_admission", 250, 250, "sh.600250")
    reporter.update("signal_scan", 0, 250, None)

    out, err = capsys.readouterr()
    assert out == ""
    assert "stage=data_admission processed=0/250" in err
    assert "processed=99/250" not in err
    assert "stage=data_admission processed=100/250" in err
    assert "stage=data_admission processed=250/250" in err
    assert "stage=signal_scan processed=0/250" in err


def test_daily_watchlist_print_is_independent(tmp_path, capsys):
    path = tmp_path / "daily_research_watchlist.csv"
    _write_csv(
        path,
        [
            "rank", "code", "watch_stage", "cnstock_pool", "start_signal_count",
            "cnstock_discovery_rank",
        ],
        {
            "rank": 1,
            "code": "sh.600003",
            "watch_stage": "cnstock_pool_watch",
            "cnstock_pool": "profit_shadow",
            "start_signal_count": 3,
            "cnstock_discovery_rank": 88.0,
        },
    )

    MODULE.print_daily_research_watchlist(path)
    output = capsys.readouterr().out
    assert "每日统一研究观察 TOP" in output
    assert "sh.600003" in output
    assert "profit_shadow" in output
