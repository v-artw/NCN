"""Trading calendar pure functions."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime
from typing import Any


class CalendarError(ValueError):
    """Raised when an explicit trading calendar is invalid or insufficient."""


def normalize_trading_days(trading_days: Sequence[Any]) -> list[date]:
    """Return validated trading days as dates in strictly increasing order."""

    if isinstance(trading_days, (str, bytes)) or not isinstance(trading_days, Sequence):
        raise CalendarError("Trading days must be provided as a non-empty sequence.")
    if not trading_days:
        raise CalendarError("Trading days must not be empty.")

    normalized: list[date] = []
    previous_day: date | None = None
    seen_days: set[date] = set()

    for index, value in enumerate(trading_days):
        trading_day = _parse_trading_day(value, index)
        if trading_day in seen_days:
            raise CalendarError(f"Duplicate trading day: {trading_day.isoformat()}.")
        if previous_day is not None and trading_day <= previous_day:
            raise CalendarError(
                "Trading days must be strictly increasing: "
                f"previous={previous_day.isoformat()}, current={trading_day.isoformat()}."
            )
        normalized.append(trading_day)
        seen_days.add(trading_day)
        previous_day = trading_day

    return normalized


def offset_trading_day(trading_days: Sequence[Any], start_day: Any, offset: int) -> date:
    """Return the trading day at offset from start_day, where offset 0 is T."""

    if isinstance(offset, bool) or not isinstance(offset, int):
        raise CalendarError("Trading day offset must be an integer.")

    normalized = normalize_trading_days(trading_days)
    start = _parse_trading_day(start_day, "start_day")
    try:
        start_index = normalized.index(start)
    except ValueError as exc:
        raise CalendarError(f"Start day {start.isoformat()} is not in the trading calendar.") from exc

    target_index = start_index + offset
    if target_index < 0 or target_index >= len(normalized):
        raise CalendarError(
            f"Trading day offset is out of range: start={start.isoformat()}, offset={offset}."
        )
    return normalized[target_index]


def count_holding_trading_days(trading_days: Sequence[Any], entry_day: Any, exit_day: Any) -> int:
    """Count holding trading days, with the entry fill day counted as day 1."""

    normalized = normalize_trading_days(trading_days)
    entry = _parse_trading_day(entry_day, "entry_day")
    exit_ = _parse_trading_day(exit_day, "exit_day")

    try:
        entry_index = normalized.index(entry)
    except ValueError as exc:
        raise CalendarError(f"Entry day {entry.isoformat()} is not in the trading calendar.") from exc
    try:
        exit_index = normalized.index(exit_)
    except ValueError as exc:
        raise CalendarError(f"Exit day {exit_.isoformat()} is not in the trading calendar.") from exc

    if exit_index < entry_index:
        raise CalendarError(
            f"Exit day {exit_.isoformat()} must not be before entry day {entry.isoformat()}."
        )
    return exit_index - entry_index + 1


def _parse_trading_day(value: Any, index: int | str) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError as exc:
            raise CalendarError(f"Trading day {index} must use YYYY-MM-DD format, got {value!r}.") from exc
    raise CalendarError(f"Trading day {index} must be YYYY-MM-DD text or a date object.")
