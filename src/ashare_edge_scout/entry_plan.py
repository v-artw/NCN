"""T+2 open entry planning pure functions."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from math import isfinite
from typing import Any

from .confirmations import ConfirmationResult


class EntryPlanInputError(ValueError):
    """Raised when T+2 entry plan inputs are invalid."""


_REQUIRED_OHLCV_FIELDS = ("open", "high", "low", "close", "volume")


@dataclass(frozen=True)
class EntryPlan:
    """A pure T+2 open entry eligibility plan, not an order or fill."""

    pattern_index: int
    confirmation_index: int | None
    entry_index: int | None
    pattern_name: str
    eligible: bool
    reason: str
    planned_entry_open: float | None


def plan_t2_open_entry(ohlcv: Mapping[str, Sequence[Any]], confirmation: ConfirmationResult) -> EntryPlan:
    """Map one confirmed T+1 result to a T+2 open entry plan candidate."""

    _validate_confirmation_type_and_name(confirmation)
    sequences = _get_ohlcv_sequences(ohlcv)
    total_length = len(sequences["open"])
    _validate_confirmation_indices(confirmation, total_length)

    if not confirmation.confirmed:
        return EntryPlan(
            pattern_index=confirmation.pattern_index,
            confirmation_index=confirmation.confirmation_index,
            entry_index=None,
            pattern_name=confirmation.pattern_name,
            eligible=False,
            reason="confirmation_not_confirmed",
            planned_entry_open=None,
        )

    if confirmation.confirmation_index is None:
        return EntryPlan(
            pattern_index=confirmation.pattern_index,
            confirmation_index=None,
            entry_index=None,
            pattern_name=confirmation.pattern_name,
            eligible=False,
            reason="missing_confirmation_index",
            planned_entry_open=None,
        )

    if confirmation.confirmation_index != confirmation.pattern_index + 1:
        return EntryPlan(
            pattern_index=confirmation.pattern_index,
            confirmation_index=confirmation.confirmation_index,
            entry_index=None,
            pattern_name=confirmation.pattern_name,
            eligible=False,
            reason="confirmation_index_mismatch",
            planned_entry_open=None,
        )

    entry_index = confirmation.confirmation_index + 1
    if entry_index >= total_length:
        return EntryPlan(
            pattern_index=confirmation.pattern_index,
            confirmation_index=confirmation.confirmation_index,
            entry_index=None,
            pattern_name=confirmation.pattern_name,
            eligible=False,
            reason="missing_t2_bar",
            planned_entry_open=None,
        )

    entry_bar = _normalize_bar_at(sequences, entry_index)
    if entry_bar["volume"] == 0:
        return EntryPlan(
            pattern_index=confirmation.pattern_index,
            confirmation_index=confirmation.confirmation_index,
            entry_index=entry_index,
            pattern_name=confirmation.pattern_name,
            eligible=False,
            reason="non_trading_entry_bar",
            planned_entry_open=None,
        )

    return EntryPlan(
        pattern_index=confirmation.pattern_index,
        confirmation_index=confirmation.confirmation_index,
        entry_index=entry_index,
        pattern_name=confirmation.pattern_name,
        eligible=True,
        reason="planned",
        planned_entry_open=entry_bar["open"],
    )


def plan_t2_open_entries(
    ohlcv: Mapping[str, Sequence[Any]], confirmations: Sequence[ConfirmationResult]
) -> tuple[EntryPlan, ...]:
    """Map T+1 confirmation results to T+2 entry plans in input order."""

    if isinstance(confirmations, (str, bytes)) or not isinstance(confirmations, Sequence):
        raise EntryPlanInputError("invalid_confirmation: confirmations must be a sequence.")
    return tuple(plan_t2_open_entry(ohlcv, confirmation) for confirmation in confirmations)


def _validate_confirmation_type_and_name(confirmation: ConfirmationResult) -> None:
    if not isinstance(confirmation, ConfirmationResult):
        raise EntryPlanInputError("invalid_confirmation: confirmation must be a ConfirmationResult.")
    if not isinstance(confirmation.pattern_name, str) or not confirmation.pattern_name.strip():
        raise EntryPlanInputError("invalid_confirmation: pattern_name must be a non-empty string.")


def _validate_confirmation_indices(confirmation: ConfirmationResult, total_length: int) -> None:
    if isinstance(confirmation.pattern_index, bool) or not isinstance(confirmation.pattern_index, int):
        raise EntryPlanInputError("invalid_confirmation_index: pattern_index must be a non-bool integer.")
    if confirmation.pattern_index < 0 or confirmation.pattern_index >= total_length:
        raise EntryPlanInputError("invalid_confirmation_index: pattern_index is outside the OHLCV range.")

    confirmation_index = confirmation.confirmation_index
    if confirmation_index is not None:
        if isinstance(confirmation_index, bool) or not isinstance(confirmation_index, int):
            raise EntryPlanInputError("invalid_confirmation_index: confirmation_index must be None or a non-bool integer.")
        if confirmation_index < 0 or confirmation_index >= total_length:
            raise EntryPlanInputError("invalid_confirmation_index: confirmation_index is outside the OHLCV range.")


def _get_ohlcv_sequences(ohlcv: Mapping[str, Sequence[Any]]) -> dict[str, Sequence[Any]]:
    if not isinstance(ohlcv, Mapping):
        raise EntryPlanInputError("empty_ohlcv: OHLCV input must be a non-empty mapping of sequences.")

    missing_fields = [field for field in _REQUIRED_OHLCV_FIELDS if field not in ohlcv]
    if missing_fields:
        raise EntryPlanInputError(f"missing_ohlcv_field: missing fields: {', '.join(missing_fields)}.")

    sequences: dict[str, Sequence[Any]] = {}
    for field in _REQUIRED_OHLCV_FIELDS:
        value = ohlcv[field]
        if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
            raise EntryPlanInputError(f"invalid_ohlcv_value: field {field!r} must be a sequence.")
        sequences[field] = value

    lengths = {len(sequence) for sequence in sequences.values()}
    if lengths == {0}:
        raise EntryPlanInputError("empty_ohlcv: OHLCV sequences must not be empty.")
    if len(lengths) != 1:
        raise EntryPlanInputError("inconsistent_ohlcv_lengths: open, high, low, close, and volume lengths must match.")
    return sequences


def _normalize_bar_at(sequences: Mapping[str, Sequence[Any]], index: int) -> dict[str, float]:
    open_price = _parse_price(sequences["open"][index], "open", index)
    high_price = _parse_price(sequences["high"][index], "high", index)
    low_price = _parse_price(sequences["low"][index], "low", index)
    close_price = _parse_price(sequences["close"][index], "close", index)
    volume = _parse_volume(sequences["volume"][index], index)
    _validate_ohlc(open_price, high_price, low_price, close_price, index)
    return {"open": open_price, "high": high_price, "low": low_price, "close": close_price, "volume": volume}


def _parse_price(value: Any, field: str, index: int) -> float:
    number = _parse_finite_number(value, field, index)
    if number <= 0:
        raise EntryPlanInputError(f"invalid_ohlcv_value: {field}[{index}] must be positive.")
    return number


def _parse_volume(value: Any, index: int) -> float:
    number = _parse_finite_number(value, "volume", index)
    if number < 0:
        raise EntryPlanInputError("invalid_ohlcv_value: volume must be non-negative.")
    return number


def _parse_finite_number(value: Any, field: str, index: int) -> float:
    if value is None:
        raise EntryPlanInputError(f"invalid_ohlcv_value: {field}[{index}] must not be None.")
    if isinstance(value, bool):
        raise EntryPlanInputError(f"invalid_ohlcv_value: {field}[{index}] must be numeric, got bool.")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise EntryPlanInputError(f"invalid_ohlcv_value: {field}[{index}] must be numeric.") from exc
    if not isfinite(number):
        raise EntryPlanInputError(f"invalid_ohlcv_value: {field}[{index}] must be finite.")
    return number


def _validate_ohlc(open_price: float, high_price: float, low_price: float, close_price: float, index: int) -> None:
    if high_price < max(open_price, low_price, close_price):
        raise EntryPlanInputError(
            f"invalid_ohlc_relation: bar {index} high must be greater than or equal to open, low, and close."
        )
    if low_price > min(open_price, high_price, close_price):
        raise EntryPlanInputError(
            f"invalid_ohlc_relation: bar {index} low must be less than or equal to open, high, and close."
        )
