"""T+1 price and volume confirmation pure functions."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from math import isfinite
from typing import Any


class ConfirmationInputError(ValueError):
    """Raised when T+1 confirmation inputs are invalid."""


_REQUIRED_OHLCV_FIELDS = ("open", "high", "low", "close", "volume")


@dataclass(frozen=True)
class BullishPattern:
    """A bullish candlestick pattern detected on a T-day bar."""

    index: int
    name: str

    def __post_init__(self) -> None:
        if isinstance(self.index, bool) or not isinstance(self.index, int):
            raise ConfirmationInputError("invalid_pattern_index: pattern index must be a non-bool integer.")
        if not isinstance(self.name, str) or not self.name.strip():
            raise ConfirmationInputError("invalid_pattern_name: pattern name must be a non-empty string.")


@dataclass(frozen=True)
class ConfirmationRule:
    """T+1 confirmation rule parameters for a pure function check."""

    volume_ma_window: int = 5
    min_volume_ratio: float = 1.2
    require_close_above_pattern_high: bool = True
    require_bullish_close: bool = True

    def __post_init__(self) -> None:
        if isinstance(self.volume_ma_window, bool) or not isinstance(self.volume_ma_window, int):
            raise ConfirmationInputError("invalid_rule: volume_ma_window must be a non-bool positive integer.")
        if self.volume_ma_window < 1:
            raise ConfirmationInputError("invalid_rule: volume_ma_window must be positive.")
        if isinstance(self.min_volume_ratio, bool):
            raise ConfirmationInputError("invalid_rule: min_volume_ratio must be a positive finite number.")
        try:
            ratio = float(self.min_volume_ratio)
        except (TypeError, ValueError) as exc:
            raise ConfirmationInputError("invalid_rule: min_volume_ratio must be a positive finite number.") from exc
        if not isfinite(ratio) or ratio <= 0:
            raise ConfirmationInputError("invalid_rule: min_volume_ratio must be a positive finite number.")
        if not isinstance(self.require_close_above_pattern_high, bool):
            raise ConfirmationInputError("invalid_rule: require_close_above_pattern_high must be bool.")
        if not isinstance(self.require_bullish_close, bool):
            raise ConfirmationInputError("invalid_rule: require_bullish_close must be bool.")


@dataclass(frozen=True)
class ConfirmationResult:
    """Result of checking a detected T-day pattern against its T+1 bar."""

    pattern_index: int
    confirmation_index: int | None
    pattern_name: str
    confirmed: bool
    reason: str
    volume_ratio: float | None


def confirm_bullish_pattern_t1(
    ohlcv: Mapping[str, Sequence[Any]],
    pattern: BullishPattern,
    *,
    rule: ConfirmationRule = ConfirmationRule(),
) -> ConfirmationResult:
    """Confirm one T-day bullish pattern using only T+1 and historical data."""

    if not isinstance(rule, ConfirmationRule):
        raise ConfirmationInputError("invalid_rule: rule must be a ConfirmationRule.")
    if not isinstance(pattern, BullishPattern):
        raise ConfirmationInputError("invalid_pattern: pattern must be a BullishPattern.")

    sequences = _get_ohlcv_sequences(ohlcv)
    total_length = len(sequences["close"])
    _validate_pattern_index(pattern.index, total_length)

    confirmation_index = pattern.index + 1
    if confirmation_index >= total_length:
        _normalize_ohlcv_until(sequences, pattern.index)
        return ConfirmationResult(
            pattern_index=pattern.index,
            confirmation_index=None,
            pattern_name=pattern.name,
            confirmed=False,
            reason="missing_t1_bar",
            volume_ratio=None,
        )

    normalized = _normalize_ohlcv_until(sequences, confirmation_index)
    pattern_volume = normalized["volume"][pattern.index]
    confirmation_volume = normalized["volume"][confirmation_index]
    if pattern_volume == 0 or confirmation_volume == 0:
        return ConfirmationResult(
            pattern_index=pattern.index,
            confirmation_index=confirmation_index,
            pattern_name=pattern.name,
            confirmed=False,
            reason="non_trading_bar",
            volume_ratio=None,
        )

    if pattern.index + 1 < rule.volume_ma_window:
        return ConfirmationResult(
            pattern_index=pattern.index,
            confirmation_index=confirmation_index,
            pattern_name=pattern.name,
            confirmed=False,
            reason="insufficient_volume_history",
            volume_ratio=None,
        )

    window_start = pattern.index - rule.volume_ma_window + 1
    historical_volumes = normalized["volume"][window_start : pattern.index + 1]
    historical_volume_ma = sum(historical_volumes) / rule.volume_ma_window
    volume_ratio = confirmation_volume / historical_volume_ma

    if volume_ratio < rule.min_volume_ratio:
        return ConfirmationResult(
            pattern_index=pattern.index,
            confirmation_index=confirmation_index,
            pattern_name=pattern.name,
            confirmed=False,
            reason="volume_not_confirmed",
            volume_ratio=volume_ratio,
        )

    if rule.require_close_above_pattern_high and normalized["close"][confirmation_index] <= normalized["high"][pattern.index]:
        return ConfirmationResult(
            pattern_index=pattern.index,
            confirmation_index=confirmation_index,
            pattern_name=pattern.name,
            confirmed=False,
            reason="price_not_confirmed",
            volume_ratio=volume_ratio,
        )

    if rule.require_bullish_close and normalized["close"][confirmation_index] <= normalized["open"][confirmation_index]:
        return ConfirmationResult(
            pattern_index=pattern.index,
            confirmation_index=confirmation_index,
            pattern_name=pattern.name,
            confirmed=False,
            reason="not_bullish_t1_close",
            volume_ratio=volume_ratio,
        )

    return ConfirmationResult(
        pattern_index=pattern.index,
        confirmation_index=confirmation_index,
        pattern_name=pattern.name,
        confirmed=True,
        reason="confirmed",
        volume_ratio=volume_ratio,
    )


def confirm_bullish_patterns_t1(
    ohlcv: Mapping[str, Sequence[Any]],
    patterns: Sequence[BullishPattern],
    *,
    rule: ConfirmationRule = ConfirmationRule(),
) -> tuple[ConfirmationResult, ...]:
    """Confirm multiple T-day bullish patterns in the same order as provided."""

    if isinstance(patterns, (str, bytes)) or not isinstance(patterns, Sequence):
        raise ConfirmationInputError("invalid_patterns: patterns must be a sequence of BullishPattern objects.")
    return tuple(confirm_bullish_pattern_t1(ohlcv, pattern, rule=rule) for pattern in patterns)


def _get_ohlcv_sequences(ohlcv: Mapping[str, Sequence[Any]]) -> dict[str, Sequence[Any]]:
    if not isinstance(ohlcv, Mapping):
        raise ConfirmationInputError("empty_ohlcv: OHLCV input must be a non-empty mapping of sequences.")

    missing_fields = [field for field in _REQUIRED_OHLCV_FIELDS if field not in ohlcv]
    if missing_fields:
        raise ConfirmationInputError(f"missing_ohlcv_field: missing fields: {', '.join(missing_fields)}.")

    sequences: dict[str, Sequence[Any]] = {}
    for field in _REQUIRED_OHLCV_FIELDS:
        value = ohlcv[field]
        if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
            raise ConfirmationInputError(f"invalid_ohlcv_value: field {field!r} must be a sequence.")
        sequences[field] = value

    lengths = {len(sequence) for sequence in sequences.values()}
    if lengths == {0}:
        raise ConfirmationInputError("empty_ohlcv: OHLCV sequences must not be empty.")
    if len(lengths) != 1:
        raise ConfirmationInputError("inconsistent_ohlcv_lengths: open, high, low, close, and volume lengths must match.")
    return sequences


def _validate_pattern_index(index: int, total_length: int) -> None:
    if index < 0 or index >= total_length:
        raise ConfirmationInputError("pattern_index_out_of_range: pattern index is outside the OHLCV range.")


def _normalize_ohlcv_until(sequences: Mapping[str, Sequence[Any]], end_index: int) -> dict[str, list[float]]:
    normalized: dict[str, list[float]] = {field: [] for field in _REQUIRED_OHLCV_FIELDS}
    for index in range(end_index + 1):
        open_price = _parse_price(sequences["open"][index], "open", index)
        high_price = _parse_price(sequences["high"][index], "high", index)
        low_price = _parse_price(sequences["low"][index], "low", index)
        close_price = _parse_price(sequences["close"][index], "close", index)
        volume = _parse_volume(sequences["volume"][index], index)
        _validate_ohlc(open_price, high_price, low_price, close_price, index)

        normalized["open"].append(open_price)
        normalized["high"].append(high_price)
        normalized["low"].append(low_price)
        normalized["close"].append(close_price)
        normalized["volume"].append(volume)
    return normalized


def _parse_price(value: Any, field: str, index: int) -> float:
    number = _parse_finite_number(value, field, index)
    if number <= 0:
        raise ConfirmationInputError(f"invalid_ohlcv_value: {field}[{index}] must be positive.")
    return number


def _parse_volume(value: Any, index: int) -> float:
    number = _parse_finite_number(value, "volume", index)
    if number < 0:
        raise ConfirmationInputError("invalid_ohlcv_value: volume must be non-negative.")
    return number


def _parse_finite_number(value: Any, field: str, index: int) -> float:
    if value is None:
        raise ConfirmationInputError(f"invalid_ohlcv_value: {field}[{index}] must not be None.")
    if isinstance(value, bool):
        raise ConfirmationInputError(f"invalid_ohlcv_value: {field}[{index}] must be numeric, got bool.")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ConfirmationInputError(f"invalid_ohlcv_value: {field}[{index}] must be numeric.") from exc
    if not isfinite(number):
        raise ConfirmationInputError(f"invalid_ohlcv_value: {field}[{index}] must be finite.")
    return number


def _validate_ohlc(open_price: float, high_price: float, low_price: float, close_price: float, index: int) -> None:
    if high_price < max(open_price, low_price, close_price):
        raise ConfirmationInputError(
            f"invalid_ohlc_relation: bar {index} high must be greater than or equal to open, low, and close."
        )
    if low_price > min(open_price, high_price, close_price):
        raise ConfirmationInputError(
            f"invalid_ohlc_relation: bar {index} low must be less than or equal to open, high, and close."
        )
