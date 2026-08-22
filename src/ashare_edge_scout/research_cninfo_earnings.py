"""Conservative CNInfo earnings forecast/express PDF text parsing."""

from __future__ import annotations

import re
from typing import Any


REPORT_TYPES = {"业绩预告": "forecast", "业绩快报": "express"}
CORRECTION_WORDS = ("更正公告", "修正公告", "补充公告", "更正后", "修正后")
PERIOD_RE = re.compile(r"(20\d{2})\s*年\s*(年度|半年度|第一季度|前三季度|第三季度)")
PARENT_PROFIT_RE = re.compile(r"归属于(?:上市公司股东|母公司(?:所有者)?|母公司股东)的净利润")
NUMBER = r"[-+]?\d[\d,]*(?:\.\d+)?"
AMOUNT_RE = re.compile(
    rf"(?:为|约为|预计为|预计)?\s*({NUMBER})\s*(亿元|万元|元)\s*(?:至|到|—|-|~|～)\s*({NUMBER})\s*\2"
)
SINGLE_LOWER_RE = re.compile(rf"(?:不低于|至少|超过)\s*({NUMBER})\s*(亿元|万元|元)")
GROWTH_RE = re.compile(
    rf"(?:同比|比上年同期)[^。；;\n]{{0,24}}?(?:增长|增加|上升)\s*({NUMBER})\s*%\s*(?:至|到|—|-|~|～)\s*({NUMBER})\s*%"
)
SINGLE_GROWTH_RE = re.compile(
    rf"(?:同比|比上年同期)[^。；;\n]{{0,24}}?(?:增长|增加|上升)(?:不低于|至少|超过)?\s*({NUMBER})\s*%\s*(?:以上)?"
)


def _number(value: str) -> float:
    return float(value.replace(",", ""))


def _yuan(value: str, unit: str) -> float:
    multipliers = {"元": 1.0, "万元": 10_000.0, "亿元": 100_000_000.0}
    return _number(value) * multipliers[unit]


def classify_title(title: str) -> dict[str, Any]:
    report_types = {kind for label, kind in REPORT_TYPES.items() if label in title}
    return {
        "report_type": next(iter(report_types)) if len(report_types) == 1 else None,
        "is_correction": any(word in title for word in CORRECTION_WORDS),
    }


def parse_earnings_text(title: str, text: str) -> dict[str, Any]:
    """Return parsed fields or a stable rejection reason; never infer missing values."""
    classified = classify_title(title)
    if classified["report_type"] is None:
        return {**classified, "parseable": False, "rejection_reason": "ambiguous_report_type"}

    normalized = re.sub(r"[ \t\r\f\v]+", "", text)
    periods = {f"{year}-{label}" for year, label in PERIOD_RE.findall(f"{title}\n{normalized}")}
    if len(periods) != 1:
        return {**classified, "parseable": False, "rejection_reason": "ambiguous_reporting_period"}

    profit_values: set[float] = set()
    for match in PARENT_PROFIT_RE.finditer(normalized):
        context = normalized[match.start() : match.end() + 180]
        if any(word in context[:100] for word in ("亏损", "为负值", "减少", "下降")):
            continue
        amount = AMOUNT_RE.search(context)
        if amount:
            profit_values.add(min(_yuan(amount.group(1), amount.group(2)), _yuan(amount.group(3), amount.group(2))))
            continue
        lower = SINGLE_LOWER_RE.search(context)
        if lower:
            profit_values.add(_yuan(lower.group(1), lower.group(2)))
    if len(profit_values) != 1:
        return {**classified, "reporting_period": next(iter(periods)), "parseable": False,
                "rejection_reason": "ambiguous_parent_profit_lower_bound"}

    growth_values: set[float] = set()
    for match in PARENT_PROFIT_RE.finditer(normalized):
        context = normalized[match.start() : match.end() + 260]
        growth = GROWTH_RE.search(context)
        if growth:
            growth_values.add(min(_number(growth.group(1)), _number(growth.group(2))))
            continue
        single = SINGLE_GROWTH_RE.search(context)
        if single:
            growth_values.add(_number(single.group(1)))
    if len(growth_values) != 1:
        return {**classified, "reporting_period": next(iter(periods)), "parseable": False,
                "rejection_reason": "ambiguous_yoy_growth_lower_bound"}

    return {
        **classified,
        "parseable": True,
        "rejection_reason": None,
        "reporting_period": next(iter(periods)),
        "parent_net_profit_lower_yuan": next(iter(profit_values)),
        "yoy_growth_lower_pct": next(iter(growth_values)),
    }


def link_correction_chains(events: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Link only corrections with exactly one earlier first-publication candidate."""
    chains: list[dict[str, str]] = []
    ordered = sorted(events, key=lambda row: (row.get("timestamp_ms", 0), row.get("announcement_id", "")))
    for correction in ordered:
        parsed = correction.get("parsed", {})
        if not parsed.get("is_correction") or not parsed.get("reporting_period") or not parsed.get("report_type"):
            continue
        candidates = [
            event for event in ordered
            if event.get("code") == correction.get("code")
            and event.get("timestamp_ms", 0) < correction.get("timestamp_ms", 0)
            and not event.get("parsed", {}).get("is_correction")
            and event.get("parsed", {}).get("reporting_period") == parsed["reporting_period"]
            and event.get("parsed", {}).get("report_type") == parsed["report_type"]
        ]
        if len(candidates) == 1:
            chains.append({
                "original_announcement_id": candidates[0]["announcement_id"],
                "correction_announcement_id": correction["announcement_id"],
            })
    return chains
