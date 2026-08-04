"""Bullish candlestick pattern recognition pure functions."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from math import isfinite
from numbers import Real
from typing import Any

from .candle_rules import CandleRuleSet, HammerRule


class CandleError(ValueError):
    """Raised when candle inputs are invalid."""


class CandleRuleAdapterError(ValueError):
    """Raised when a CandleRuleSet cannot safely drive candlestick detection."""


_PATTERN_KEYS = ("hammer", "bullish_engulfing", "piercing", "morning_star")
_REQUIRED_OHLC_FIELDS = ("open", "high", "low", "close")


@dataclass(frozen=True)
class _Bar:
    open: float
    high: float
    low: float
    close: float

    @property
    def range(self) -> float:
        return self.high - self.low

    @property
    def body(self) -> float:
        return abs(self.close - self.open)

    @property
    def upper_shadow(self) -> float:
        return self.high - max(self.open, self.close)

    @property
    def lower_shadow(self) -> float:
        return min(self.open, self.close) - self.low

    @property
    def body_high(self) -> float:
        return max(self.open, self.close)

    @property
    def body_low(self) -> float:
        return min(self.open, self.close)

    @property
    def is_bullish(self) -> bool:
        return self.close > self.open

    @property
    def is_bearish(self) -> bool:
        return self.close < self.open


def detect_hammer(bars: Sequence[Mapping[str, Any]]) -> list[bool]:
    """Detect hammer geometry with conservative book-derived trend filter."""

    return _detect_hammer_normalized(_normalize_bars(bars))


def detect_bullish_engulfing(bars: Sequence[Mapping[str, Any]]) -> list[bool]:
    """Detect bullish engulfing with conservative book-derived quality filters."""

    return _detect_bullish_engulfing_normalized(_normalize_bars(bars))


def detect_piercing(bars: Sequence[Mapping[str, Any]]) -> list[bool]:
    """Detect piercing pattern with conservative book-derived quality filters."""

    return _detect_piercing_normalized(_normalize_bars(bars))


def detect_morning_star(bars: Sequence[Mapping[str, Any]]) -> list[bool]:
    """Detect morning star geometry with conservative book-derived quality filters."""

    return _detect_morning_star_normalized(_normalize_bars(bars))


def detect_bullish_patterns(bars: Sequence[Mapping[str, Any]]) -> dict[str, list[bool]]:
    """Detect all fixed V1 bullish candlestick geometry patterns."""

    normalized = _normalize_bars(bars)
    return {
        "hammer": _detect_hammer_normalized(normalized),
        "bullish_engulfing": _detect_bullish_engulfing_normalized(normalized),
        "piercing": _detect_piercing_normalized(normalized),
        "morning_star": _detect_morning_star_normalized(normalized),
    }


def detect_bearish_risk_patterns(bars: Sequence[Mapping[str, Any]]) -> dict[str, list[bool]]:
    """Detect high-value bearish reversal warnings in an established rise."""

    normalized = _normalize_bars(bars)
    return {
        "hanging_man": _detect_hanging_man_normalized(normalized),
        "shooting_star": _detect_shooting_star_normalized(normalized),
        "bearish_engulfing": _detect_bearish_engulfing_normalized(normalized),
        "dark_cloud_cover": _detect_dark_cloud_cover_normalized(normalized),
        "evening_star": _detect_evening_star_normalized(normalized),
    }


def detect_bullish_patterns_from_candle_rules(
    bars: Sequence[Mapping[str, Any]],
    rules: CandleRuleSet,
) -> dict[str, list[bool]]:
    """Detect bullish patterns through an explicit CandleRuleSet."""

    _validate_candle_rule_set(rules)
    normalized = _normalize_bars(bars)
    enabled_patterns = set(rules.enabled_patterns)
    disabled = [False] * len(normalized)
    return {
        "hammer": (
            _detect_hammer_normalized_with_rule(normalized, rules.hammer)
            if "hammer" in enabled_patterns
            else disabled.copy()
        ),
        "bullish_engulfing": (
            _detect_bullish_engulfing_normalized(normalized)
            if "bullish_engulfing" in enabled_patterns
            else disabled.copy()
        ),
        "piercing": (
            _detect_piercing_normalized(normalized)
            if "piercing" in enabled_patterns
            else disabled.copy()
        ),
        "morning_star": (
            _detect_morning_star_normalized(normalized)
            if "morning_star" in enabled_patterns
            else disabled.copy()
        ),
    }


def _detect_hammer_normalized(bars: Sequence[_Bar]) -> list[bool]:
    return _detect_hammer_normalized_with_thresholds(
        bars,
        max_body_to_range=0.40,
        min_lower_shadow_to_body=2.0,
        max_upper_shadow_to_body=0.5,
        min_close_location=0.65,
    )


def _detect_hammer_normalized_with_rule(bars: Sequence[_Bar], rule: HammerRule) -> list[bool]:
    return _detect_hammer_normalized_with_thresholds(
        bars,
        max_body_to_range=rule.max_body_to_range,
        min_lower_shadow_to_body=rule.min_lower_shadow_to_body,
        max_upper_shadow_to_body=rule.max_upper_shadow_to_body,
        min_close_location=rule.min_close_location,
    )


def _detect_hammer_normalized_with_thresholds(
    bars: Sequence[_Bar],
    *,
    max_body_to_range: float,
    min_lower_shadow_to_body: float,
    max_upper_shadow_to_body: float,
    min_close_location: float,
) -> list[bool]:
    result: list[bool] = []
    for index, bar in enumerate(bars):
        if bar.range == 0:
            result.append(False)
            continue
        close_location = (bar.close - bar.low) / bar.range
        result.append(
            _short_term_decline_before(bars, index)
            and bar.lower_shadow >= min_lower_shadow_to_body * bar.body
            and bar.upper_shadow <= max(max_upper_shadow_to_body * bar.body, 0.1 * bar.range)
            and bar.body / bar.range <= max_body_to_range
            and close_location >= min_close_location
        )
    return result


def _detect_bullish_engulfing_normalized(bars: Sequence[_Bar]) -> list[bool]:
    result = [False] * len(bars)
    for index in range(1, len(bars)):
        previous = bars[index - 1]
        current = bars[index]
        result[index] = (
            _short_term_decline_before(bars, index - 1)
            and previous.is_bearish
            and previous.range > 0
            and previous.body / previous.range >= 0.35
            and current.is_bullish
            and current.body >= 1.10 * previous.body
            and current.body_low <= previous.body_low
            and current.body_high >= previous.body_high
            and current.close >= previous.open
        )
    return result


def _detect_piercing_normalized(bars: Sequence[_Bar]) -> list[bool]:
    result = [False] * len(bars)
    for index in range(1, len(bars)):
        previous = bars[index - 1]
        current = bars[index]
        previous_midpoint = (previous.open + previous.close) / 2.0
        penetration = (current.close - previous.close) / previous.body if previous.body > 0 else 0.0
        result[index] = (
            _short_term_decline_before(bars, index - 1)
            and previous.is_bearish
            and previous.range > 0
            and previous.body / previous.range >= 0.50
            and current.is_bullish
            and current.open <= previous.close
            and current.low <= previous.low
            and penetration >= 0.50
            and current.close > previous_midpoint
            and current.close < previous.open
        )
    return result


def _detect_morning_star_normalized(bars: Sequence[_Bar]) -> list[bool]:
    result = [False] * len(bars)
    for index in range(2, len(bars)):
        first = bars[index - 2]
        second = bars[index - 1]
        third = bars[index]
        if first.range == 0 or second.range == 0 or third.range == 0:
            continue
        first_midpoint = (first.open + first.close) / 2.0
        result[index] = (
            _short_term_decline_before(bars, index - 2)
            and first.is_bearish
            and first.body / first.range >= 0.55
            and second.body / second.range <= 0.25
            and second.body_high < first.body_low
            and third.is_bullish
            and third.body / third.range >= 0.45
            and third.close > first_midpoint
        )
    return result


def _detect_hanging_man_normalized(bars: Sequence[_Bar]) -> list[bool]:
    result: list[bool] = []
    for index, bar in enumerate(bars):
        if bar.range == 0:
            result.append(False)
            continue
        close_location = (bar.close - bar.low) / bar.range
        result.append(
            _short_term_rise_before(bars, index)
            and bar.lower_shadow >= 2.0 * bar.body
            and bar.upper_shadow <= max(0.5 * bar.body, 0.1 * bar.range)
            and bar.body / bar.range <= 0.40
            and close_location >= 0.65
        )
    return result


def _detect_shooting_star_normalized(bars: Sequence[_Bar]) -> list[bool]:
    result: list[bool] = []
    for index, bar in enumerate(bars):
        if bar.range == 0:
            result.append(False)
            continue
        body_location = (bar.body_low - bar.low) / bar.range
        result.append(
            _short_term_rise_before(bars, index)
            and bar.upper_shadow >= 2.0 * bar.body
            and bar.lower_shadow <= max(0.5 * bar.body, 0.1 * bar.range)
            and bar.body / bar.range <= 0.40
            and body_location <= 0.35
        )
    return result


def _detect_bearish_engulfing_normalized(bars: Sequence[_Bar]) -> list[bool]:
    result = [False] * len(bars)
    for index in range(1, len(bars)):
        previous = bars[index - 1]
        current = bars[index]
        result[index] = (
            _short_term_rise_before(bars, index - 1)
            and previous.is_bullish
            and previous.range > 0
            and previous.body / previous.range >= 0.35
            and current.is_bearish
            and current.body >= 1.10 * previous.body
            and current.body_low <= previous.body_low
            and current.body_high >= previous.body_high
            and current.close <= previous.open
        )
    return result


def _detect_dark_cloud_cover_normalized(bars: Sequence[_Bar]) -> list[bool]:
    result = [False] * len(bars)
    for index in range(1, len(bars)):
        previous = bars[index - 1]
        current = bars[index]
        midpoint = (previous.open + previous.close) / 2.0
        result[index] = (
            _short_term_rise_before(bars, index - 1)
            and previous.is_bullish
            and previous.range > 0
            and previous.body / previous.range >= 0.50
            and current.is_bearish
            and current.open >= previous.close
            and current.high >= previous.high
            and current.close < midpoint
            and current.close > previous.open
        )
    return result


def _detect_evening_star_normalized(bars: Sequence[_Bar]) -> list[bool]:
    result = [False] * len(bars)
    for index in range(2, len(bars)):
        first = bars[index - 2]
        second = bars[index - 1]
        third = bars[index]
        if first.range == 0 or second.range == 0 or third.range == 0:
            continue
        first_midpoint = (first.open + first.close) / 2.0
        result[index] = (
            _short_term_rise_before(bars, index - 2)
            and first.is_bullish
            and first.body / first.range >= 0.55
            and second.body / second.range <= 0.25
            and second.body_low > first.body_high
            and third.is_bearish
            and third.body / third.range >= 0.45
            and third.close < first_midpoint
        )
    return result


def _short_term_decline_before(bars: Sequence[_Bar], index: int) -> bool:
    if index < 3:
        return False
    prior_close = bars[index - 3].close
    recent_close = bars[index - 1].close
    return recent_close < prior_close


def _short_term_rise_before(bars: Sequence[_Bar], index: int) -> bool:
    if index < 3:
        return False
    prior_close = bars[index - 3].close
    recent_close = bars[index - 1].close
    return recent_close > prior_close


def _validate_candle_rule_set(rules: CandleRuleSet) -> None:
    if not isinstance(rules, CandleRuleSet):
        raise CandleRuleAdapterError("invalid_candle_rule_set: rules must be a CandleRuleSet.")
    if not isinstance(rules.enabled_patterns, tuple):
        raise CandleRuleAdapterError("invalid_enabled_patterns: enabled_patterns must be a tuple.")
    for pattern_name in rules.enabled_patterns:
        if not isinstance(pattern_name, str) or not pattern_name:
            raise CandleRuleAdapterError(
                "invalid_enabled_patterns: enabled_patterns must contain non-empty strings."
            )
        if pattern_name not in _PATTERN_KEYS:
            raise CandleRuleAdapterError(f"unknown_candle_pattern: {pattern_name!r} is not supported.")
    _validate_hammer_rule(rules.hammer)


def _validate_hammer_rule(rule: HammerRule) -> None:
    if not isinstance(rule, HammerRule):
        raise CandleRuleAdapterError("invalid_hammer_rule: hammer must be a HammerRule.")
    _validate_hammer_threshold(
        rule.max_body_to_range,
        "max_body_to_range",
        lambda value: value > 0,
    )
    _validate_hammer_threshold(
        rule.min_lower_shadow_to_body,
        "min_lower_shadow_to_body",
        lambda value: value > 0,
    )
    _validate_hammer_threshold(
        rule.max_upper_shadow_to_body,
        "max_upper_shadow_to_body",
        lambda value: value >= 0,
    )
    _validate_hammer_threshold(
        rule.min_close_location,
        "min_close_location",
        lambda value: 0 <= value <= 1,
    )
    if rule.uses_documented_upper_shadow_range_guard is not True:
        raise CandleRuleAdapterError(
            "invalid_hammer_guard: uses_documented_upper_shadow_range_guard must be True."
        )


def _validate_hammer_threshold(value: Any, name: str, predicate: Any) -> None:
    if isinstance(value, bool) or not isinstance(value, Real) or not isfinite(value) or not predicate(value):
        raise CandleRuleAdapterError(f"invalid_hammer_threshold: {name} is invalid.")


def _normalize_bars(bars: Sequence[Mapping[str, Any]]) -> list[_Bar]:
    if isinstance(bars, (str, bytes)) or not isinstance(bars, Sequence):
        raise CandleError("Candles must be provided as a non-empty sequence of mapping bars.")
    if not bars:
        raise CandleError("Candles must not be empty.")

    normalized: list[_Bar] = []
    for index, bar in enumerate(bars):
        if not isinstance(bar, Mapping):
            raise CandleError(f"Bar {index} must be a mapping, got {type(bar).__name__}.")
        missing_fields = [field for field in _REQUIRED_OHLC_FIELDS if field not in bar]
        if missing_fields:
            raise CandleError(f"Bar {index} is missing required OHLC fields: {', '.join(missing_fields)}.")
        values = {field: _parse_price(bar[field], field, index) for field in _REQUIRED_OHLC_FIELDS}
        normalized_bar = _Bar(
            open=values["open"],
            high=values["high"],
            low=values["low"],
            close=values["close"],
        )
        _validate_ohlc(normalized_bar, index)
        normalized.append(normalized_bar)
    return normalized


def _parse_price(value: Any, field: str, index: int) -> float:
    if value is None:
        raise CandleError(f"Bar {index} field '{field}' must not be None.")
    if isinstance(value, bool):
        raise CandleError(f"Bar {index} field '{field}' must be numeric, got bool.")
    try:
        price = float(value)
    except (TypeError, ValueError) as exc:
        raise CandleError(f"Bar {index} field '{field}' must be numeric, got {value!r}.") from exc
    if not isfinite(price):
        raise CandleError(f"Bar {index} field '{field}' must be finite, got {value!r}.")
    if price <= 0:
        raise CandleError(f"Bar {index} field '{field}' must be positive.")
    return price


def _validate_ohlc(bar: _Bar, index: int) -> None:
    if bar.high < max(bar.open, bar.low, bar.close):
        raise CandleError(
            f"Bar {index} has illegal OHLC: high must be greater than or equal to open, low, and close."
        )
    if bar.low > min(bar.open, bar.high, bar.close):
        raise CandleError(
            f"Bar {index} has illegal OHLC: low must be less than or equal to open, high, and close."
        )
