"""NCN-native PMKF/MKF research domain with lazy public exports."""

from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS = {
    "apply_pmkf": ("core", "apply_pmkf"),
    "compute_pmkf_slope": ("core", "compute_pmkf_slope"),
    "atr": ("features", "atr"),
    "cnstock_rsi": ("features", "cnstock_rsi"),
    "compute_pmk_features": ("features", "compute_pmk_features"),
    "macd": ("features", "macd"),
    "rsi": ("features", "rsi"),
    "sma": ("features", "sma"),
    "aggregate_mkf_metrics": ("research", "aggregate_mkf_metrics"),
    "build_mkf_panel": ("research", "build_mkf_panel"),
    "evaluate_mkf_decision": ("research", "evaluate_mkf_decision"),
    "mkf_green_exit_mask": ("research", "mkf_green_exit_mask"),
    "mkf_lines": ("research", "mkf_lines"),
    "mkf_red_blue_cross20_lines": ("research", "mkf_red_blue_cross20_lines"),
    "mkf_red_blue_cross20_under80_mask": ("research", "mkf_red_blue_cross20_under80_mask"),
    "mkf_red_blue_cross20_green_exit_under80_mask": ("research", "mkf_red_blue_cross20_green_exit_under80_mask"),
    "mkf_red_blue_cross20_post_lag_mask": ("research", "mkf_red_blue_cross20_post_lag_mask"),
    "mkf_first_red_blue_cross20_after_green_exit_under80_mask": ("research", "mkf_first_red_blue_cross20_after_green_exit_under80_mask"),
}

__all__ = list(_EXPORTS)


def __getattr__(name: str) -> Any:
    try:
        module_name, attribute_name = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(name) from exc
    value = getattr(import_module(f"{__name__}.{module_name}"), attribute_name)
    globals()[name] = value
    return value
