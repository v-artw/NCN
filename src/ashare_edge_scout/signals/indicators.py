"""Technical indicator pure functions without lookahead."""

from __future__ import annotations

from collections.abc import Sequence
from math import isfinite
from typing import Any


class IndicatorError(ValueError):
    """Raised when indicator inputs are invalid."""


def sma(values: Sequence[Any], window: int) -> list[float | None]:
    """Return simple moving average values; insufficient windows are None."""

    normalized = _normalize_number_sequence(values, "values")
    _validate_window(window, "window")
    result: list[float | None] = [None] * len(normalized)
    if len(normalized) < window:
        return result

    rolling_sum = 0.0
    for index, value in enumerate(normalized):
        rolling_sum += value
        if index >= window:
            rolling_sum -= normalized[index - window]
        if index >= window - 1:
            result[index] = rolling_sum / window
    return result


def ema(values: Sequence[Any], period: int) -> list[float | None]:
    """Return EMA values initialized by the first period SMA and Wilder-free smoothing."""

    normalized = _normalize_number_sequence(values, "values")
    _validate_window(period, "period")
    result: list[float | None] = [None] * len(normalized)
    if len(normalized) < period:
        return result

    first_ema = sum(normalized[:period]) / period
    result[period - 1] = first_ema
    alpha = 2.0 / (period + 1.0)
    previous_ema = first_ema

    for index in range(period, len(normalized)):
        current_ema = normalized[index] * alpha + previous_ema * (1.0 - alpha)
        result[index] = current_ema
        previous_ema = current_ema
    return result


def volume_moving_average(volumes: Sequence[Any], window: int) -> list[float | None]:
    """Return moving average of non-negative volume values."""

    normalized = _normalize_number_sequence(volumes, "volumes")
    for index, volume in enumerate(normalized):
        if volume < 0:
            raise IndicatorError(f"volumes[{index}] must be non-negative.")
    return sma(normalized, window)


def simple_returns(values: Sequence[Any], periods: int = 1) -> list[float | None]:
    """Return simple returns using current and historical values only."""

    normalized = _normalize_number_sequence(values, "values")
    _validate_window(periods, "periods")
    _validate_positive_values(normalized, "values")

    result: list[float | None] = [None] * len(normalized)
    for index in range(periods, len(normalized)):
        previous = normalized[index - periods]
        result[index] = normalized[index] / previous - 1.0
    return result


def true_range(highs: Sequence[Any], lows: Sequence[Any], closes: Sequence[Any]) -> list[float]:
    """Return true range values, using prior close after the first bar."""

    normalized_highs = _normalize_number_sequence(highs, "highs")
    normalized_lows = _normalize_number_sequence(lows, "lows")
    normalized_closes = _normalize_number_sequence(closes, "closes")
    _validate_equal_lengths(normalized_highs, normalized_lows, normalized_closes)
    _validate_ohlc_parts(normalized_highs, normalized_lows, normalized_closes)

    result: list[float] = []
    for index, high in enumerate(normalized_highs):
        low = normalized_lows[index]
        if index == 0:
            result.append(high - low)
            continue
        previous_close = normalized_closes[index - 1]
        result.append(max(high - low, abs(high - previous_close), abs(low - previous_close)))
    return result


def atr(highs: Sequence[Any], lows: Sequence[Any], closes: Sequence[Any], period: int) -> list[float | None]:
    """Return ATR initialized with TR SMA and then smoothed with Wilder's formula."""

    _validate_window(period, "period")
    ranges = true_range(highs, lows, closes)
    result: list[float | None] = [None] * len(ranges)
    if len(ranges) < period:
        return result

    first_atr = sum(ranges[:period]) / period
    result[period - 1] = first_atr
    previous_atr = first_atr

    for index in range(period, len(ranges)):
        current_atr = (previous_atr * (period - 1) + ranges[index]) / period
        result[index] = current_atr
        previous_atr = current_atr
    return result


def _normalize_number_sequence(values: Sequence[Any], name: str) -> list[float]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise IndicatorError(f"{name} must be provided as a non-empty sequence.")
    if not values:
        raise IndicatorError(f"{name} must not be empty.")

    normalized: list[float] = []
    for index, value in enumerate(values):
        if isinstance(value, bool):
            raise IndicatorError(f"{name}[{index}] must be numeric, got bool.")
        try:
            number = float(value)
        except (TypeError, ValueError) as exc:
            raise IndicatorError(f"{name}[{index}] must be numeric, got {value!r}.") from exc
        if not isfinite(number):
            raise IndicatorError(f"{name}[{index}] must be finite, got {value!r}.")
        normalized.append(number)
    return normalized


def _validate_window(window: int, name: str) -> None:
    if isinstance(window, bool) or not isinstance(window, int):
        raise IndicatorError(f"{name} must be a positive integer.")
    if window < 1:
        raise IndicatorError(f"{name} must be a positive integer.")


def _validate_positive_values(values: Sequence[float], name: str) -> None:
    for index, value in enumerate(values):
        if value <= 0:
            raise IndicatorError(f"{name}[{index}] must be positive.")


def _validate_equal_lengths(*series: Sequence[float]) -> None:
    lengths = {len(item) for item in series}
    if len(lengths) != 1:
        raise IndicatorError("highs, lows, and closes must have the same length.")


def _validate_ohlc_parts(highs: Sequence[float], lows: Sequence[float], closes: Sequence[float]) -> None:
    for index, (high, low, close) in enumerate(zip(highs, lows, closes, strict=True)):
        if high <= 0:
            raise IndicatorError(f"highs[{index}] must be positive.")
        if low <= 0:
            raise IndicatorError(f"lows[{index}] must be positive.")
        if close <= 0:
            raise IndicatorError(f"closes[{index}] must be positive.")
        if high < low:
            raise IndicatorError(f"highs[{index}] must be greater than or equal to lows[{index}].")
        if close > high or close < low:
            raise IndicatorError(f"closes[{index}] must be between low and high.")
