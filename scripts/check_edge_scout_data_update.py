#!/usr/bin/env python3
"""Compare the latest local research bar date with BaoStock's latest trade date."""

from __future__ import annotations

import argparse
from datetime import date, timedelta
import json
import os
from pathlib import Path
import sys

import baostock as bs
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from ashare_edge_scout.data_sources import get_parquet_latest_date_coverage


CURRENT = 0
UPDATE_REQUIRED = 10
CHECK_FAILED = 2


def local_date_state(data_root: Path) -> tuple[date | None, int, int]:
    """Return latest date, files on that date, and readable parquet file count."""
    return get_parquet_latest_date_coverage(data_root)


def latest_local_date(data_root: Path) -> date | None:
    return local_date_state(data_root)[0]


def latest_remote_trade_date(*, today: date, lookback_days: int = 45) -> date:
    """Query BaoStock's calendar and return the latest trading day through today."""

    login = bs.login()
    if login.error_code != "0":
        raise RuntimeError(f"baostock login failed: {login.error_msg}")
    try:
        result = bs.query_trade_dates(
            start_date=(today - timedelta(days=lookback_days)).isoformat(),
            end_date=today.isoformat(),
        )
        if result.error_code != "0":
            raise RuntimeError(f"baostock trade-date query failed: {result.error_msg}")
        rows: list[list[str]] = []
        while result.next():
            rows.append(result.get_row_data())
        if not rows:
            raise RuntimeError("baostock trade-date query returned no rows")
        fields = list(result.fields)
        date_index = fields.index("calendar_date")
        trading_index = fields.index("is_trading_day")
        trading_days = [
            date.fromisoformat(row[date_index])
            for row in rows
            if row[trading_index] == "1"
        ]
        if not trading_days:
            raise RuntimeError("baostock trade-date query returned no trading day")
        return max(trading_days)
    finally:
        bs.logout()


def update_decision(
    local_latest: date | None,
    remote_latest: date,
    *,
    latest_coverage_ratio: float = 1.0,
    minimum_latest_coverage_ratio: float = 0.95,
) -> str:
    if local_latest is None or local_latest < remote_latest:
        return "update_required"
    if local_latest == remote_latest:
        return "current" if latest_coverage_ratio >= minimum_latest_coverage_ratio else "update_required"
    raise RuntimeError(
        f"local data is newer than BaoStock calendar: local={local_latest}, remote={remote_latest}"
    )


def write_summary(path: Path | None, payload: dict[str, object]) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", required=True, type=Path)
    parser.add_argument("--summary-json", type=Path)
    parser.add_argument("--today", type=date.fromisoformat, default=date.today())
    parser.add_argument("--minimum-latest-coverage-ratio", type=float, default=0.95)
    parser.add_argument(
        "--remote-date",
        type=date.fromisoformat,
        help="use a previously verified remote date instead of querying BaoStock",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if not 0.0 <= args.minimum_latest_coverage_ratio <= 1.0:
            raise ValueError("minimum latest coverage ratio must be between 0 and 1")
        local_latest, latest_count, readable_count = local_date_state(args.data_root)
        coverage_ratio = latest_count / readable_count if readable_count else 0.0
        remote_latest = args.remote_date or latest_remote_trade_date(today=args.today)
        action = update_decision(
            local_latest,
            remote_latest,
            latest_coverage_ratio=coverage_ratio,
            minimum_latest_coverage_ratio=args.minimum_latest_coverage_ratio,
        )
        payload = {
            "schema_version": "edge_scout_data_update_check_v1",
            "status": "success",
            "action": action,
            "data_root": str(args.data_root),
            "local_latest_trade_date": local_latest.isoformat() if local_latest else None,
            "local_latest_file_count": latest_count,
            "local_readable_file_count": readable_count,
            "local_latest_coverage_ratio": coverage_ratio,
            "minimum_latest_coverage_ratio": args.minimum_latest_coverage_ratio,
            "remote_latest_trade_date": remote_latest.isoformat(),
        }
        write_summary(args.summary_json, payload)
        print(json.dumps(payload, sort_keys=True))
        return UPDATE_REQUIRED if action == "update_required" else CURRENT
    except Exception as exc:
        payload = {
            "schema_version": "edge_scout_data_update_check_v1",
            "status": "failed",
            "error": str(exc),
            "data_root": str(args.data_root),
        }
        write_summary(args.summary_json, payload)
        print(f"edge_scout_data_update_check_failed: {exc}", file=sys.stderr)
        return CHECK_FAILED


if __name__ == "__main__":
    raise SystemExit(main())
