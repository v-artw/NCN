#!/usr/bin/env python3
"""Generate a review-pending A-share trading calendar candidate from BaoStock."""

from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys

import baostock as bs


def query_trading_days(start: date, end: date) -> list[date]:
    login = bs.login()
    if login.error_code != "0":
        raise RuntimeError(f"baostock login failed: {login.error_msg}")
    try:
        result = bs.query_trade_dates(start_date=start.isoformat(), end_date=end.isoformat())
        if result.error_code != "0":
            raise RuntimeError(f"baostock trade-date query failed: {result.error_msg}")
        fields = list(result.fields)
        date_index = fields.index("calendar_date")
        trading_index = fields.index("is_trading_day")
        days: list[date] = []
        while result.next():
            row = result.get_row_data()
            if row[trading_index] == "1":
                days.append(date.fromisoformat(row[date_index]))
        normalized = sorted(set(days))
        if not normalized:
            raise RuntimeError("baostock trade-date query returned no trading day")
        return normalized
    finally:
        bs.logout()


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    os.replace(temporary, path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", required=True, type=int)
    parser.add_argument("--calendar-output", required=True, type=Path)
    parser.add_argument("--manifest-output", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    start = date(args.year, 1, 1)
    end = date(args.year, 12, 31)
    days = query_trading_days(start, end)
    content = "".join(f"{day.isoformat()}\n" for day in days)
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    manifest = {
        "schema_version": "edge_scout_calendar_review_candidate_v1",
        "review_status": "pending_human_approval",
        "provider": "BaoStock",
        "provider_query": "query_trade_dates",
        "requested_start_date": start.isoformat(),
        "requested_end_date": end.isoformat(),
        "first_trading_day": days[0].isoformat(),
        "last_trading_day": days[-1].isoformat(),
        "trading_day_count": len(days),
        "calendar_sha256": digest,
        "calendar_path": str(args.calendar_output),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "limitations": [
            "provider_response_not_exchange_signed",
            "must_be_human_reviewed_before_research_production_use",
        ],
    }
    atomic_write(args.calendar_output, content)
    atomic_write(args.manifest_output, json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps(manifest, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"calendar_candidate_generation_failed: {exc}", file=sys.stderr)
        raise SystemExit(2)
