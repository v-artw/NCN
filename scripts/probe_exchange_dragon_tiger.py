#!/usr/bin/env python3
"""Run the frozen official-exchange Dragon-Tiger institutional coverage probe."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import tempfile
import time
import urllib.parse
import urllib.request
from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any


START_DATE = "2021-01-01"
END_DATE = "2026-08-15"
INSTITUTION = "机构专用"
SSE_CODES = (
    "600000", "600021", "600025", "600031", "600052", "600055", "600085",
    "600096", "600100", "600105", "600132", "600148", "600161", "600162",
    "600166", "600169", "600176", "600192", "600196", "600216",
)
SZSE_CODES = (
    "000016", "000020", "000032", "000045", "000061", "000089", "000156",
    "000166", "000401", "000429", "000505", "000514", "000519", "000531",
    "000532", "000534", "000536", "000539", "000557", "000564",
)
SSE_TIMELINE_URL = "https://query.sse.com.cn/commonSoaQuery.do"
SSE_DETAIL_URL = "https://query.sse.com.cn/marketdata/tradedata/queryTradeOpenInfo.do"
SZSE_URL = "https://www.szse.cn/api/report/ShowReport/data"
DETAIL_RE = re.compile(r"DQRQ=([0-9-]+)&ZQDM=(\d{6})&ZBDM=([^'&]+)")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, default=Path(".runtime/dragon-tiger-coverage-probe"))
    parser.add_argument("--timeout", type=float, default=15.0)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--max-requests", type=int, default=1200)
    parser.add_argument("--max-bytes", type=int, default=250_000_000)
    args = parser.parse_args(argv)
    if args.timeout <= 0 or not 0 <= args.retries <= 2:
        parser.error("timeout must be positive and retries must be between 0 and 2")
    if args.max_requests > 1200 or args.max_bytes > 250_000_000:
        parser.error("requested budget exceeds the frozen ceiling")
    return args


def _canonical_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


class BoundedArchiveClient:
    def __init__(self, root: Path, *, timeout: float, retries: int, max_requests: int, max_bytes: int) -> None:
        self.root = root
        self.timeout = timeout
        self.retries = retries
        self.max_requests = max_requests
        self.max_bytes = max_bytes
        self.requests = 0
        self.bytes = 0
        self.manifest: list[dict[str, Any]] = []
        root.mkdir(parents=True, exist_ok=True)

    def get(self, source: str, url: str, params: Mapping[str, Any], key: str) -> Any:
        query = urllib.parse.urlencode([(name, str(value)) for name, value in params.items()])
        full_url = f"{url}?{query}"
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            if self.requests >= self.max_requests:
                raise RuntimeError("frozen request budget exceeded")
            self.requests += 1
            request = urllib.request.Request(
                full_url,
                headers={
                    "Accept": "application/json,text/javascript,*/*;q=0.1",
                    "Referer": "https://www.sse.com.cn/" if source == "sse" else "https://www.szse.cn/",
                    "User-Agent": "Mozilla/5.0 NCN-noncommercial-coverage-probe",
                },
            )
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    raw = response.read()
                if self.bytes + len(raw) > self.max_bytes:
                    raise RuntimeError("frozen response-byte budget exceeded")
                self.bytes += len(raw)
                digest = hashlib.sha256(raw).hexdigest()
                path = self.root / "raw" / source / f"{key}.json"
                path.parent.mkdir(parents=True, exist_ok=True)
                if path.exists() and hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                    raise RuntimeError(f"immutable archive collision: {path}")
                if not path.exists():
                    path.write_bytes(raw)
                retrieved_at = datetime.now(timezone.utc).isoformat()
                self.manifest.append({
                    "source": source, "url": url, "params": dict(params), "key": key,
                    "retrieved_at": retrieved_at, "bytes": len(raw), "sha256": digest,
                })
                return _parse_payload(raw)
            except Exception as error:  # bounded retries cover transient official-site failures
                last_error = error
                if attempt < self.retries:
                    time.sleep(0.5 * (attempt + 1))
        assert last_error is not None
        raise last_error


def _parse_payload(raw: bytes) -> Any:
    text = raw.decode("utf-8-sig").strip()
    if text.startswith("jsonpCallback(") and text.endswith(")"):
        text = text[len("jsonpCallback("):-1]
    elif text.startswith("(") and text.endswith(")"):
        text = text[1:-1]
    return json.loads(text)


def _decimal(value: Any) -> Decimal:
    try:
        result = Decimal(str(value).replace(",", "").strip())
    except (InvalidOperation, AttributeError):
        raise ValueError(f"invalid amount: {value!r}") from None
    if not result.is_finite() or result < 0:
        raise ValueError(f"invalid amount: {value!r}")
    return result


def _iso_date(value: Any) -> str:
    text = str(value)
    if re.fullmatch(r"\d{8}", text):
        text = f"{text[:4]}-{text[4:6]}-{text[6:]}"
    datetime.strptime(text, "%Y-%m-%d")
    if not START_DATE <= text <= END_DATE:
        raise ValueError(f"date outside frozen range: {text}")
    return text


def _sse_timeline(client: BoundedArchiveClient, code: str, suffix: str = "") -> list[dict[str, str]]:
    params = {
        "jsonCallBack": "jsonpCallback", "isPagination": "true", "token": "QUERY",
        "sqlId": "JYGKXX_ZL", "tradeDateStart": START_DATE, "tradeDateEnd": END_DATE,
        "secCode": code, "pageHelp.pageSize": "100", "fields": "tradeDate,refType",
    }
    payload = client.get("sse", SSE_TIMELINE_URL, params, f"timeline-{code}{suffix}")
    page = payload.get("pageHelp") or {}
    rows = page.get("data") or payload.get("result") or []
    if int(page.get("total", len(rows))) != len(rows):
        raise ValueError(f"SSE pagination mismatch for {code}")
    result = [{"date": _iso_date(row["tradeDate"]), "reason": str(row["refType"])} for row in rows]
    if any(not row["reason"] for row in result):
        raise ValueError(f"SSE missing reason for {code}")
    return sorted(result, key=lambda row: (row["date"], row["reason"]))


def _sse_detail(client: BoundedArchiveClient, code: str, date: str, reason: str, suffix: str = "") -> dict[str, Any]:
    compact_date = date.replace("-", "")
    params = {
        "jsonCallBack": "jsonpCallback", "token": "QUERY", "tradeDate": compact_date,
        "refType": reason, "secCode": code, "orderB": "desc", "orderS": "desc",
    }
    payload = client.get("sse", SSE_DETAIL_URL, params, f"detail-{compact_date}-{code}-{reason}{suffix}")
    rows = ((payload.get("pageHelp") or {}).get("data") or [])
    if not rows:
        raise ValueError("empty SSE detail")
    buy = Decimal(0)
    sell = Decimal(0)
    institutional_rows = 0
    for row in rows:
        if str(row.get("secCode")) != code or _iso_date(row.get("tradeDate")) != date or str(row.get("refType")) != reason:
            raise ValueError("SSE detail identity mismatch")
        side = str(row.get("bsType"))
        if side not in {"B", "S"}:
            raise ValueError("SSE invalid side")
        amount = _decimal(row.get("branchTxAmt"))
        if str(row.get("branchName", "")).strip() == INSTITUTION:
            institutional_rows += 1
            if side == "B":
                buy += amount
            else:
                sell += amount
    return _event("sse", date, code, reason, buy, sell, institutional_rows)


def _szse_list(client: BoundedArchiveClient, code: str, suffix: str = "") -> list[dict[str, str]]:
    rows: list[dict[str, Any]] = []
    page_number = 1
    page_count = 1
    while page_number <= page_count:
        params = {
            "SHOWTYPE": "JSON", "CATALOGID": "1842_xxpl", "TABKEY": "tab1",
            "txtDMorJC": code, "txtStart": START_DATE, "txtEnd": END_DATE,
            "PAGENO": page_number,
        }
        payload = client.get("szse", SZSE_URL, params, f"list-{code}-p{page_number}{suffix}")
        if not isinstance(payload, list) or len(payload) != 1:
            raise ValueError("invalid SZSE list envelope")
        metadata = payload[0].get("metadata") or {}
        page_count = int(metadata.get("pagecount", 0))
        rows.extend(payload[0].get("data") or [])
        page_number += 1
    expected = int(metadata.get("recordcount", len(rows))) if page_count else 0
    if expected != len(rows):
        raise ValueError(f"SZSE pagination mismatch for {code}: {len(rows)}/{expected}")
    result: list[dict[str, str]] = []
    for row in rows:
        match = DETAIL_RE.search(str(row.get("bz", "")))
        if not match:
            raise ValueError("SZSE list row missing exact detail contract")
        date, detail_code, reason = match.groups()
        date = _iso_date(date)
        if detail_code != code or str(row.get("zqdm")) != code or _iso_date(row.get("dqrq")) != date or not reason:
            raise ValueError("SZSE list identity mismatch")
        result.append({"date": date, "reason": reason})
    return sorted(result, key=lambda row: (row["date"], row["reason"]))


def _szse_detail(client: BoundedArchiveClient, code: str, date: str, reason: str, suffix: str = "") -> dict[str, Any]:
    params = {
        "SHOWTYPE": "JSON", "CATALOGID": "1842_detal", "TABKEY": "tab1,tab2",
        "DQRQ": date, "ZQDM": code, "ZBDM": reason,
    }
    payload = client.get("szse", SZSE_URL, params, f"detail-{date}-{code}-{reason}{suffix}")
    if not isinstance(payload, list) or len(payload) != 2:
        raise ValueError("invalid SZSE detail envelope")
    header_rows = payload[0].get("data") or []
    seat_rows = payload[1].get("data") or []
    if len(header_rows) != 1 or not seat_rows or _iso_date(header_rows[0].get("dqrq")) != date:
        raise ValueError("SZSE detail identity mismatch")
    unique: set[tuple[str, Decimal, Decimal]] = set()
    for row in seat_rows:
        seat = str(row.get("zsmc", "")).strip()
        unique.add((seat, _decimal(row.get("mrje")), _decimal(row.get("mcje"))))
    institutional = [row for row in unique if row[0] == INSTITUTION]
    buy = sum((row[1] for row in institutional), Decimal(0))
    sell = sum((row[2] for row in institutional), Decimal(0))
    return _event("szse", date, code, reason, buy, sell, len(institutional))


def _event(exchange: str, date: str, code: str, reason: str, buy: Decimal, sell: Decimal, rows: int) -> dict[str, Any]:
    net = buy - sell
    return {
        "exchange": exchange, "event_date": date, "code": code, "reason_reference": reason,
        "institutional_rows": rows, "institutional_buy": str(buy),
        "institutional_sell": str(sell), "institutional_net": str(net), "positive_net": net > 0,
        "availability": "next_stock_tradable_date_after_event_date",
    }


def _evaluate(events: list[dict[str, Any]], discovered: int, invalid: list[dict[str, str]], repeat_stable: bool) -> dict[str, Any]:
    positives = [event for event in events if event["positive_net"]]
    years = Counter(int(event["event_date"][:4]) for event in positives)
    codes_with_detail = {event["code"] for event in events}
    positive_codes = {event["code"] for event in positives}
    completeness = len(events) / discovered if discovered else 0.0
    selection = sum(event["event_date"][:4] in {"2023", "2024"} for event in positives)
    holdout = sum(event["event_date"][:4] in {"2025", "2026"} for event in positives)
    failures: list[str] = []
    if invalid or len(events) != discovered:
        failures.append("incomplete_or_invalid_details")
    if completeness < 0.95:
        failures.append("completeness_below_0.95")
    if not repeat_stable:
        failures.append("repeated_query_hash_mismatch")
    if any(years[year] < 1 for year in range(2021, 2027)):
        failures.append("positive_event_annual_coverage_failed")
    if any(years[year] < 5 for year in (2023, 2024, 2025)) or years[2026] < 3:
        failures.append("positive_event_yearly_minimum_failed")
    if selection < 30:
        failures.append("selection_positive_events_below_30")
    if holdout < 30:
        failures.append("holdout_positive_events_below_30")
    if len(codes_with_detail) < 16:
        failures.append("codes_with_detail_below_16")
    if len(codes_with_detail & set(SSE_CODES)) < 8 or len(codes_with_detail & set(SZSE_CODES)) < 8:
        failures.append("exchange_code_coverage_below_8")
    if len(positive_codes) < 8:
        failures.append("positive_event_codes_below_8")
    return {
        "passed": not failures, "failure_codes": failures, "discovered_reason_events": discovered,
        "valid_reason_events": len(events), "invalid_reason_events": len(invalid),
        "required_field_completeness": completeness, "positive_events": len(positives),
        "positive_events_by_year": {str(year): years[year] for year in range(2021, 2027)},
        "selection_2023_2024_positive_events": selection, "holdout_2025_2026_positive_events": holdout,
        "codes_with_detail": len(codes_with_detail),
        "sse_codes_with_detail": len(codes_with_detail & set(SSE_CODES)),
        "szse_codes_with_detail": len(codes_with_detail & set(SZSE_CODES)),
        "codes_with_positive_event": len(positive_codes), "repeated_query_hash_equal": repeat_stable,
    }


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    client = BoundedArchiveClient(
        args.archive, timeout=args.timeout, retries=args.retries,
        max_requests=args.max_requests, max_bytes=args.max_bytes,
    )
    lists: dict[tuple[str, str], list[dict[str, str]]] = {}
    for code in SSE_CODES:
        lists[("sse", code)] = _sse_timeline(client, code)
    for code in SZSE_CODES:
        lists[("szse", code)] = _szse_list(client, code)

    discovered_rows = [
        (exchange, code, row["date"], row["reason"])
        for (exchange, code), rows in lists.items() for row in rows
    ]
    discovered_rows = sorted(set(discovered_rows))
    events: list[dict[str, Any]] = []
    invalid: list[dict[str, str]] = []
    for exchange, code, date, reason in discovered_rows:
        try:
            event = (_sse_detail if exchange == "sse" else _szse_detail)(client, code, date, reason)
            events.append(event)
        except Exception as error:
            invalid.append({"exchange": exchange, "code": code, "date": date, "reason": reason, "error": str(error)})

    repeat_hashes: dict[str, dict[str, str]] = {}
    repeat_stable = True
    for exchange in ("sse", "szse"):
        nonempty = next(((code, rows[0]) for (item_exchange, code), rows in lists.items() if item_exchange == exchange and rows), None)
        if nonempty is None:
            repeat_stable = False
            continue
        code, row = nonempty
        repeated_list = (_sse_timeline if exchange == "sse" else _szse_list)(client, code, "-repeat")
        repeated_detail = (_sse_detail if exchange == "sse" else _szse_detail)(client, code, row["date"], row["reason"], "-repeat")
        original_event = next((event for event in events if event["exchange"] == exchange and event["code"] == code and event["event_date"] == row["date"] and event["reason_reference"] == row["reason"]), None)
        values = {
            "list_first": _canonical_hash(lists[(exchange, code)]), "list_repeat": _canonical_hash(repeated_list),
            "detail_first": _canonical_hash(original_event), "detail_repeat": _canonical_hash(repeated_detail),
        }
        values["equal"] = str(values["list_first"] == values["list_repeat"] and values["detail_first"] == values["detail_repeat"]).lower()
        repeat_hashes[exchange] = values
        repeat_stable &= values["equal"] == "true"

    events.sort(key=lambda row: (row["event_date"], row["exchange"], row["code"], row["reason_reference"]))
    decision = _evaluate(events, len(discovered_rows), invalid, repeat_stable)
    report = {
        "probe": "official_exchange_dragon_tiger_institutional_coverage",
        "retrieved_at": datetime.now(timezone.utc).isoformat(), "range": [START_DATE, END_DATE],
        "sample": {"sse_codes": SSE_CODES, "szse_codes": SZSE_CODES},
        "source_contracts": {
            "sse_list": SSE_TIMELINE_URL, "sse_detail": SSE_DETAIL_URL,
            "szse_list_and_detail": SZSE_URL,
        },
        "field_policy": "official date/code/reason/exact seat/buy/sell only; no Eastmoney or future-derived fields",
        "requests": client.requests, "response_bytes": client.bytes,
        "repeat_hashes": repeat_hashes, "decision": decision,
        "invalid_events": invalid, "events": events,
    }
    _atomic_json(args.archive / "manifest.json", client.manifest)
    _atomic_json(args.archive / "result.json", report)
    print(json.dumps({**decision, "requests": client.requests, "response_bytes": client.bytes}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
