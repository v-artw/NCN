"""Minimal immutable candle-rule contracts used by Edge Scout."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HammerRule:
    max_body_to_range: float
    min_lower_shadow_to_body: float
    max_upper_shadow_to_body: float
    min_close_location: float
    uses_documented_upper_shadow_range_guard: bool


@dataclass(frozen=True)
class CandleRuleSet:
    enabled_patterns: tuple[str, ...]
    hammer: HammerRule
