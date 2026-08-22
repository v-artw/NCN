#!/usr/bin/env python3
"""Run the frozen CNInfo share-repurchase metadata count probe."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
import urllib.parse
import urllib.request
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ashare_edge_scout.research_repurchase import classify_title, normalize_title


STOCK_MAP_URL = "https://www.cninfo.com.cn/new/data/szse_stock.json"
QUERY_URL = "https://www.cninfo.com.cn/new/hisAnnouncement/query"
PDF_BASE_URL = "https://static.cninfo.com.cn/"
DATE_RANGE = "2021-01-01~2026-08-15"
DEFAULT_SAMPLE_PATH = Path("docs/research/results/stage1/precision70-stage1-2021-2026.json")
MAX_REQUESTS = 1_800
MAX_BYTES = 100 * 1024**2
MAX_SECONDS = 30 * 60


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample", type=Path, default=DEFAULT_SAMPLE_PATH)
    parser.add_argument("--archive", type=Path, default=Path(".runtime/share-repurchase-count-probe"))
    parser.add_argument("--timeout", type=int, default=15)
    parser.add_argument("--retries", type=int, default=2)
    return parser.parse_args()


def canonical_hash(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{time.time_ns()}.tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.chmod(0o600)
    temporary.replace(path)


class Collector:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.started = time.monotonic()
        self.requests = 0
        self.response_bytes = 0

    def request(self, url: str, *, data: bytes | None, raw_path: Path) -> bytes:
        headers = {"Referer": "https://www.cninfo.com.cn/", "User-Agent": "Mozilla/5.0"}
        if data is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        error: Exception | None = None
        for attempt in range(self.args.retries + 1):
            self.requests += 1
            if self.requests > MAX_REQUESTS:
                raise RuntimeError("frozen request budget exceeded")
            if time.monotonic() - self.started > MAX_SECONDS:
                raise RuntimeError("frozen wall-time budget exceeded")
            try:
                request = urllib.request.Request(url, data=data, headers=headers)
                with urllib.request.urlopen(request, timeout=self.args.timeout) as response:
                    raw = response.read()
                self.response_bytes += len(raw)
                if self.response_bytes > MAX_BYTES:
                    raise RuntimeError("frozen metadata byte budget exceeded")
                raw_path.parent.mkdir(parents=True, exist_ok=True)
                raw_path.write_bytes(raw)
                raw_path.chmod(0o600)
                return raw
            except Exception as caught:
                error = caught
                if attempt < self.args.retries:
                    time.sleep(1 + attempt)
        assert error is not None
        raise error


def normalize_row(row: dict[str, Any]) -> dict[str, Any]:
    title = str(row.get("announcementTitle") or "")
    adjunct = str(row.get("adjunctUrl") or "")
    return {
        "announcement_id": str(row.get("announcementId") or ""),
        "code": str(row.get("secCode") or ""),
        "org_id": str(row.get("orgId") or ""),
        "title": normalize_title(title),
        "timestamp_ms": int(row.get("announcementTime") or 0),
        "pdf_url": urllib.parse.urljoin(PDF_BASE_URL, adjunct),
        "state": classify_title(title),
    }


def fetch_pass(
    collector: Collector, codes: list[str], organizations: dict[str, str], pass_number: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows_by_id: dict[str, dict[str, Any]] = {}
    query_audit: list[dict[str, Any]] = []
    for index, code in enumerate(codes, start=1):
        org_id = organizations[code]
        base = {
            "pageSize": "30", "column": "szse", "tabName": "fulltext", "plate": "",
            "stock": f"{code},{org_id}", "searchkey": "回购", "secid": "", "category": "",
            "trade": "", "seDate": DATE_RANGE, "sortName": "", "sortType": "", "isHLtitle": "true",
        }
        found: list[dict[str, Any]] = []
        total: int | None = None
        page = 1
        while total is None or len(found) < total:
            payload = urllib.parse.urlencode({"pageNum": str(page), **base}).encode()
            raw_path = collector.args.archive / "raw" / f"pass-{pass_number}" / code / f"page-{page}.json"
            raw = collector.request(QUERY_URL, data=payload, raw_path=raw_path)
            value = json.loads(raw)
            page_total = int(value.get("totalAnnouncement", -1))
            if page_total < 0 or (total is not None and total != page_total):
                raise RuntimeError(f"invalid/changing totalAnnouncement for {code}")
            total = page_total
            page_rows = list(value.get("announcements") or [])
            if total and not page_rows:
                raise RuntimeError(f"empty intermediate page for {code}/{page}")
            found.extend(page_rows)
            page += 1
        if len(found) != total:
            raise RuntimeError(f"pagination mismatch for {code}: {len(found)}/{total}")
        normalized = [normalize_row(row) for row in found]
        query_audit.append({"code": code, "total": total, "pages": max(1, page - 1), "hash": canonical_hash(normalized)})
        for row in normalized:
            event_id = row["announcement_id"]
            previous = rows_by_id.get(event_id)
            if previous is not None and previous != row:
                raise RuntimeError(f"conflicting duplicate announcement ID {event_id}")
            rows_by_id[event_id] = row
        if index % 50 == 0:
            print(f"pass {pass_number}: queried {index}/{len(codes)} codes", flush=True)
    return sorted(rows_by_id.values(), key=lambda row: row["announcement_id"]), query_audit


def valid_row(row: dict[str, Any], codes: set[str]) -> bool:
    return bool(
        row["announcement_id"] and row["code"] in codes and row["org_id"] and row["title"]
        and row["timestamp_ms"] > 0 and row["pdf_url"].lower().endswith(".pdf")
    )


def main() -> None:
    args = parse_args()
    sample = json.loads(args.sample.read_text(encoding="utf-8"))
    code_list = sample.get("sample", {}).get("code_list")
    if not isinstance(code_list, list) or len(code_list) != 400:
        raise SystemExit("sample must contain exactly 400 sample.code_list entries")
    codes = [str(code).split(".", 1)[-1] for code in code_list]
    if len(set(codes)) != 400:
        raise SystemExit("sample codes must be unique")

    collector = Collector(args)
    stock_map_raw = collector.request(STOCK_MAP_URL, data=None, raw_path=args.archive / "raw" / "stock-map.json")
    stock_map = json.loads(stock_map_raw)
    organizations = {str(row["code"]): str(row["orgId"]) for row in stock_map["stockList"]}
    missing_codes = sorted(set(codes) - organizations.keys())
    if missing_codes:
        raise RuntimeError(f"official stock map missing {len(missing_codes)} codes")

    first, first_audit = fetch_pass(collector, codes, organizations, 1)
    second, second_audit = fetch_pass(collector, codes, organizations, 2)
    first_hash, second_hash = canonical_hash(first), canonical_hash(second)
    initial = [row for row in first if row["state"] == "initial"]
    valid_initial = [row for row in initial if valid_row(row, set(codes))]

    # Generic same-code/date initial notices are one proposal for this upper bound.
    distinct_events: dict[tuple[str, int, str], dict[str, Any]] = {}
    for row in valid_initial:
        day = datetime.fromtimestamp(row["timestamp_ms"] / 1000, UTC).year * 10_000 + int(
            datetime.fromtimestamp(row["timestamp_ms"] / 1000, UTC).strftime("%m%d")
        )
        subject = row["title"]
        for generic in ("关于回购股份方案的公告", "关于回购公司股份方案的公告", "股份回购方案"):
            if generic in subject:
                subject = "generic_proposal"
                break
        distinct_events.setdefault((row["code"], day, subject), row)
    events = sorted(distinct_events.values(), key=lambda row: (row["timestamp_ms"], row["code"], row["announcement_id"]))
    annual = Counter(datetime.fromtimestamp(row["timestamp_ms"] / 1000, UTC).year for row in events)
    selection = sum(annual[year] for year in (2023, 2024))
    holdout = sum(annual[year] for year in (2025, 2026))
    state_counts = Counter(row["state"] for row in first)
    complete_ratio = len(valid_initial) / len(initial) if initial else 0.0
    gates = {
        "all_400_codes_in_stock_map": not missing_codes,
        "repeated_metadata_hash_stable": first_hash == second_hash,
        "repeated_query_audit_stable": canonical_hash(first_audit) == canonical_hash(second_audit),
        "initial_metadata_completeness_at_least_95pct": complete_ratio >= 0.95,
        "initial_events_every_year_2021_2026": all(annual[year] > 0 for year in range(2021, 2027)),
        "selection_2023_2024_at_least_300": selection >= 300,
        "selection_annual_floors": annual[2023] >= 50 and annual[2024] >= 50,
        "holdout_2025_2026_at_least_300": holdout >= 300,
        "holdout_annual_floors": annual[2025] >= 50 and annual[2026] >= 25,
        "codes_with_initial_event_at_least_120": len({row["code"] for row in events}) >= 120,
        "within_request_budget": collector.requests <= MAX_REQUESTS,
        "within_metadata_byte_budget": collector.response_bytes <= MAX_BYTES,
        "within_wall_time_budget": time.monotonic() - collector.started <= MAX_SECONDS,
    }
    passed = all(gates.values())
    result = {
        "probe": "cninfo_quantified_share_repurchase_initial_count_upper_bound",
        "retrieved_at": datetime.now(UTC).isoformat(),
        "source_url": QUERY_URL,
        "source_adapter_commit": "1248fdd05a2dda92937d4cd39c0957825f2f7f6e",
        "sample_sha256": hashlib.sha256(args.sample.read_bytes()).hexdigest(),
        "sample_codes": len(codes),
        "date_range": DATE_RANGE.split("~"),
        "metadata_sha256": first_hash,
        "repeat_metadata_sha256": second_hash,
        "requests": collector.requests,
        "metadata_response_bytes": collector.response_bytes,
        "wall_seconds": round(time.monotonic() - collector.started, 3),
        "pdf_requests": 0,
        "pdf_bytes": 0,
        "metadata_announcements": len(first),
        "title_state_counts": dict(sorted(state_counts.items())),
        "raw_initial_candidates": len(initial),
        "valid_initial_candidates": len(valid_initial),
        "distinct_initial_events": len(events),
        "codes_with_initial_event": len({row["code"] for row in events}),
        "annual_initial_events": {str(year): annual[year] for year in range(2021, 2027)},
        "selection_2023_2024": selection,
        "holdout_2025_2026": holdout,
        "initial_metadata_completeness": complete_ratio,
        "gates": gates,
        "passed": passed,
        "decision": "permit_pdf_source_probe" if passed else "stop_before_pdfs_and_labels",
        "events": events,
    }
    atomic_json(args.archive / "result.json", result)
    print(json.dumps({key: result[key] for key in (
        "passed", "decision", "requests", "metadata_response_bytes", "metadata_announcements",
        "title_state_counts", "distinct_initial_events", "codes_with_initial_event",
        "annual_initial_events", "selection_2023_2024", "holdout_2025_2026", "gates",
    )}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
