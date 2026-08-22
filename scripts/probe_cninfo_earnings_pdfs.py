#!/usr/bin/env python3
"""Bounded, research-only CNInfo earnings forecast/express PDF coverage probe."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import tempfile
import time
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ashare_edge_scout.research_cninfo_earnings import link_correction_chains, parse_earnings_text


CODES = [
    "600000", "600021", "600025", "600031", "600052", "600055", "600085", "600096",
    "600100", "600105", "600132", "600148", "600161", "600162", "600166", "600169",
    "600176", "600192", "600196", "600216", "600223", "600229", "600248", "600255",
    "600276", "600282", "600284", "600295", "600301", "600307", "600323", "600339",
    "600340", "600348", "600354", "600356", "600360", "600368", "600375", "600397",
]
STOCK_MAP_URL = "https://www.cninfo.com.cn/new/data/szse_stock.json"
QUERY_URL = "https://www.cninfo.com.cn/new/hisAnnouncement/query"
PDF_BASE_URL = "https://static.cninfo.com.cn/"
KEYWORDS = ("业绩预告", "业绩快报")
DATE_RANGE = "2021-01-01~2026-08-15"
MAX_PDFS = 500
MAX_BYTES = 2 * 1024**3


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, default=Path(".runtime/cninfo-earnings-pdf-probe"))
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--retries", type=int, default=2)
    return parser.parse_args()


def canonical_hash(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def request(url: str, *, data: bytes | None, timeout: int, retries: int) -> bytes:
    headers = {"Referer": "https://www.cninfo.com.cn/", "User-Agent": "Mozilla/5.0"}
    if data is not None:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, data=data, headers=headers), timeout=timeout) as response:
                return response.read()
        except Exception as caught:  # provider/network failures are reported in the audit result
            error = caught
            if attempt < retries:
                time.sleep(1 + attempt)
    assert error is not None
    raise error


def fetch_stock_map(args: argparse.Namespace) -> tuple[dict[str, str], str]:
    raw = request(STOCK_MAP_URL, data=None, timeout=args.timeout, retries=args.retries)
    value = json.loads(raw)
    organizations = {str(row["code"]): str(row["orgId"]) for row in value["stockList"]}
    return organizations, hashlib.sha256(raw).hexdigest()


def fetch_page(code: str, org_id: str, keyword: str, page: int, args: argparse.Namespace) -> dict[str, Any]:
    payload = urllib.parse.urlencode({
        "pageNum": page, "pageSize": 30, "column": "szse", "tabName": "fulltext",
        "plate": "", "stock": f"{code},{org_id}", "searchkey": keyword, "secid": "",
        "category": "", "trade": "", "seDate": DATE_RANGE, "sortName": "", "sortType": "",
        "isHLtitle": "true",
    }).encode()
    return json.loads(request(QUERY_URL, data=payload, timeout=args.timeout, retries=args.retries))


def normalize_row(row: dict[str, Any]) -> dict[str, Any]:
    adjunct = str(row.get("adjunctUrl") or "")
    return {
        "announcement_id": str(row.get("announcementId") or ""),
        "code": str(row.get("secCode") or ""),
        "org_id": str(row.get("orgId") or ""),
        "title": re.sub(r"<[^>]+>", "", str(row.get("announcementTitle") or "")),
        "timestamp_ms": int(row.get("announcementTime") or 0),
        "pdf_url": urllib.parse.urljoin(PDF_BASE_URL, adjunct),
        "provider_size_kb": row.get("adjunctSize"),
    }


def fetch_metadata(organizations: dict[str, str], args: argparse.Namespace) -> list[dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for code in CODES:
        if code not in organizations:
            raise RuntimeError(f"provider stock map missing {code}")
        for keyword in KEYWORDS:
            first = fetch_page(code, organizations[code], keyword, 1, args)
            total = int(first.get("totalAnnouncement", -1))
            pages = (total + 29) // 30
            found = list(first.get("announcements") or [])
            for page in range(2, pages + 1):
                found.extend(fetch_page(code, organizations[code], keyword, page, args).get("announcements") or [])
            if len(found) != total:
                raise RuntimeError(f"pagination mismatch for {code}/{keyword}: {len(found)}/{total}")
            for raw in found:
                row = normalize_row(raw)
                if keyword in row["title"]:
                    rows[row["announcement_id"]] = row
    normalized = sorted(rows.values(), key=lambda row: row["announcement_id"])
    if not all(row["announcement_id"] and row["code"] in CODES and row["org_id"]
               and row["timestamp_ms"] > 0 and row["pdf_url"].lower().endswith(".pdf") for row in normalized):
        raise RuntimeError("invalid normalized metadata row")
    return normalized


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{time.time_ns()}.tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.chmod(0o600)
    temporary.replace(path)


def extract_text(pdf: Path) -> str:
    with tempfile.NamedTemporaryFile(suffix=".txt") as output:
        completed = subprocess.run(
            ["pdftotext", "-layout", "-enc", "UTF-8", str(pdf), output.name],
            check=False, capture_output=True, text=True, timeout=60,
        )
        if completed.returncode != 0:
            raise RuntimeError(completed.stderr.strip() or f"pdftotext exited {completed.returncode}")
        return Path(output.name).read_text(encoding="utf-8", errors="strict")


def main() -> None:
    args = parse_args()
    organizations, stock_map_hash = fetch_stock_map(args)
    first = fetch_metadata(organizations, args)
    second = fetch_metadata(organizations, args)
    first_hash, second_hash = canonical_hash(first), canonical_hash(second)
    args.archive.mkdir(parents=True, exist_ok=True)
    atomic_json(args.archive / "metadata.json", {
        "source_url": QUERY_URL, "stock_map_url": STOCK_MAP_URL, "stock_map_sha256": stock_map_hash,
        "retrieved_at": datetime.now(UTC).isoformat(), "codes": CODES, "keywords": KEYWORDS,
        "date_range": DATE_RANGE, "metadata_sha256": first_hash, "repeat_metadata_sha256": second_hash,
        "repeated_metadata_hash_stable": first_hash == second_hash, "announcements": first,
    })

    if len(first) > MAX_PDFS:
        raise RuntimeError(f"metadata returned {len(first)} PDFs, exceeding frozen maximum {MAX_PDFS}")
    events: list[dict[str, Any]] = []
    total_bytes = 0
    pdf_dir = args.archive / "pdfs"
    pdf_dir.mkdir(exist_ok=True)
    for index, row in enumerate(first, start=1):
        raw = request(row["pdf_url"], data=None, timeout=args.timeout, retries=args.retries)
        total_bytes += len(raw)
        if total_bytes > MAX_BYTES:
            raise RuntimeError(f"PDF bytes exceed frozen maximum {MAX_BYTES}")
        pdf = pdf_dir / f"{row['announcement_id']}.pdf"
        if pdf.exists() and hashlib.sha256(pdf.read_bytes()).hexdigest() != hashlib.sha256(raw).hexdigest():
            raise RuntimeError(f"archived PDF hash changed for {row['announcement_id']}")
        if not pdf.exists():
            pdf.write_bytes(raw)
            pdf.chmod(0o600)
        event = dict(row)
        event.update({"retrieved_at": datetime.now(UTC).isoformat(), "pdf_bytes": len(raw),
                      "pdf_sha256": hashlib.sha256(raw).hexdigest()})
        try:
            text = extract_text(pdf)
            event["text_sha256"] = hashlib.sha256(text.encode()).hexdigest()
            event["parsed"] = parse_earnings_text(row["title"], text)
        except Exception as error:
            event["parsed"] = {"parseable": False, "rejection_reason": f"pdftotext_error:{error}"}
        events.append(event)
        if index % 25 == 0:
            print(f"processed {index}/{len(first)}", flush=True)

    chains = link_correction_chains(events)
    first_publications = [event for event in events if not event["parsed"].get("is_correction")]
    parseable = [event for event in first_publications if event["parsed"].get("parseable")]
    codes_covered = sorted({event["code"] for event in events})
    years = sorted({datetime.fromtimestamp(event["timestamp_ms"] / 1000, UTC).year for event in parseable})
    complete = [event for event in events if event["timestamp_ms"] > 0 and event["parsed"].get("parseable")]
    completeness = len(complete) / len(events) if events else 0.0
    gates = {
        "codes_at_least_30": len(codes_covered) >= 30,
        "full_years_2021_2025": all(year in years for year in range(2021, 2026)),
        "parseable_first_publications_at_least_120": len(parseable) >= 120,
        "retained_correction_chains_at_least_10": len(chains) >= 10,
        "timestamp_field_completeness_at_least_95pct": completeness >= 0.95,
        "repeated_metadata_hash_stable": first_hash == second_hash,
    }
    result = {
        "probe": "cninfo_earnings_forecast_express_pdf_coverage", "source_url": QUERY_URL,
        "source_adapter": "AKShare stock_zh_a_disclosure_report_cninfo request contract",
        "source_adapter_commit": "1248fdd05a2dda92937d4cd39c0957825f2f7f6e",
        "retrieved_at": datetime.now(UTC).isoformat(), "codes": CODES, "request_range": DATE_RANGE.split("~"),
        "limits": {"workers": 1, "max_pdfs": MAX_PDFS, "max_bytes": MAX_BYTES},
        "metadata_sha256": first_hash, "repeat_metadata_sha256": second_hash,
        "announcements": len(events), "pdf_bytes": total_bytes, "codes_covered": len(codes_covered),
        "parseable_first_publications": len(parseable), "parseable_years": years,
        "retained_correction_chains": len(chains), "timestamp_field_completeness": completeness,
        "gates": gates, "passed": all(gates.values()), "decision": "pass" if all(gates.values()) else "stop",
        "correction_chains": chains, "events": events,
    }
    atomic_json(args.archive / "result.json", result)
    print(json.dumps({key: result[key] for key in (
        "passed", "decision", "announcements", "pdf_bytes", "codes_covered",
        "parseable_first_publications", "parseable_years", "retained_correction_chains",
        "timestamp_field_completeness", "gates",
    )}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
