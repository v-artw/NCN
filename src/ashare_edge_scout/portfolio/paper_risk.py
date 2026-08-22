"""Paper-only risk control payloads for NCN Web."""

from __future__ import annotations

from typing import Any, Mapping

DEFAULT_PAPER_RISK = {
    "max_position_pct": 0.20,
    "max_daily_paper_intents": 2,
    "max_hold_positions": 5,
    "t1_sell_lock": True,
    "block_limit_up_entries": True,
    "stop_atr_multiple": 1.5,
    "take_profit_r": 1.5,
}


def normalize_paper_risk(config: Mapping[str, Any] | None) -> dict[str, Any]:
    source = dict(DEFAULT_PAPER_RISK)
    if config:
        source.update(dict(config))
    max_position_pct = float(source["max_position_pct"])
    if not 0 < max_position_pct <= 1:
        raise ValueError("paper_risk.max_position_pct must be within (0, 1]")
    max_daily = int(source["max_daily_paper_intents"])
    max_hold = int(source["max_hold_positions"])
    stop_atr = float(source["stop_atr_multiple"])
    take_profit = float(source["take_profit_r"])
    if max_daily < 0 or max_hold < 1 or stop_atr <= 0 or take_profit <= 0:
        raise ValueError("paper_risk numeric limits are invalid")
    return {
        "max_position_pct": max_position_pct,
        "max_daily_paper_intents": max_daily,
        "max_hold_positions": max_hold,
        "t1_sell_lock": bool(source["t1_sell_lock"]),
        "block_limit_up_entries": bool(source["block_limit_up_entries"]),
        "stop_atr_multiple": stop_atr,
        "take_profit_r": take_profit,
    }


__all__ = ["DEFAULT_PAPER_RISK", "normalize_paper_risk"]
