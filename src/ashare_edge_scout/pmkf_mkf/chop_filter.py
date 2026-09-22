from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from .quality import _numeric

CHOP_EXCLUDE_SCORE = 4
CHOP_FILTER_RULE = "exclude_chop_ge_4"
CHOP_THRESHOLDS = {
    "efficiency20_max": 0.25,
    "range20_pct_max": 0.12,
    "net_return20_abs_max": 0.04,
    "overlap10_min": 0.55,
    "atr14_pct_max": 0.035,
}


def missing_chop_features() -> dict[str, Any]:
    return {
        "chop_available": False,
        "chop_score": None,
        "chop_efficiency20": None,
        "chop_range20_pct": None,
        "chop_net_return20_abs": None,
        "chop_overlap10": None,
        "chop_atr14_pct": None,
        "chop_is_sideways_ge3": False,
        "chop_is_sideways_ge4": False,
    }


def _finite_window(values: np.ndarray) -> bool:
    return bool(len(values)) and bool(np.isfinite(values).all())


def compute_sideways_chop_features_at(data: pd.DataFrame, row_index: int) -> dict[str, Any]:
    close = _numeric(data, "close").to_numpy(dtype=float)
    high = _numeric(data, "high").to_numpy(dtype=float)
    low = _numeric(data, "low").to_numpy(dtype=float)
    if row_index < 20 or row_index >= len(close):
        return missing_chop_features()

    close_window = close[row_index - 20:row_index + 1]
    high_window = high[row_index - 19:row_index + 1]
    low_window = low[row_index - 19:row_index + 1]
    if not (_finite_window(close_window) and _finite_window(high_window) and _finite_window(low_window)):
        return missing_chop_features()
    if np.any(close_window <= 0) or np.any(high_window <= 0) or np.any(low_window <= 0):
        return missing_chop_features()

    daily_returns = close_window[1:] / close_window[:-1] - 1.0
    abs_return_sum = float(np.sum(np.abs(daily_returns)))
    net_return20_abs = float(abs(close_window[-1] / close_window[0] - 1.0))
    efficiency20 = 1.0 if abs_return_sum == 0.0 else net_return20_abs / abs_return_sum
    range20_pct = float((np.max(high_window) - np.min(low_window)) / close_window[-1])

    overlap_high = high[row_index - 10:row_index + 1]
    overlap_low = low[row_index - 10:row_index + 1]
    if not (_finite_window(overlap_high) and _finite_window(overlap_low)):
        return missing_chop_features()
    overlap_ratios: list[float] = []
    for index in range(1, len(overlap_high)):
        overlap = max(0.0, min(overlap_high[index], overlap_high[index - 1]) - max(overlap_low[index], overlap_low[index - 1]))
        denominator = max(overlap_high[index], overlap_high[index - 1]) - min(overlap_low[index], overlap_low[index - 1])
        overlap_ratios.append(0.0 if denominator <= 0.0 else overlap / denominator)
    overlap10 = float(np.mean(overlap_ratios)) if overlap_ratios else 0.0

    atr_high = high[row_index - 13:row_index + 1]
    atr_low = low[row_index - 13:row_index + 1]
    atr_close = close[row_index - 14:row_index + 1]
    if not (_finite_window(atr_high) and _finite_window(atr_low) and _finite_window(atr_close)):
        return missing_chop_features()
    true_ranges = []
    for offset in range(14):
        previous_close = atr_close[offset]
        true_ranges.append(max(
            atr_high[offset] - atr_low[offset],
            abs(atr_high[offset] - previous_close),
            abs(atr_low[offset] - previous_close),
        ))
    atr14_pct = float(np.mean(true_ranges) / close[row_index])

    score = int(efficiency20 <= CHOP_THRESHOLDS["efficiency20_max"])
    score += int(range20_pct <= CHOP_THRESHOLDS["range20_pct_max"])
    score += int(net_return20_abs <= CHOP_THRESHOLDS["net_return20_abs_max"])
    score += int(overlap10 >= CHOP_THRESHOLDS["overlap10_min"])
    score += int(atr14_pct <= CHOP_THRESHOLDS["atr14_pct_max"])
    return {
        "chop_available": True,
        "chop_score": score,
        "chop_efficiency20": efficiency20,
        "chop_range20_pct": range20_pct,
        "chop_net_return20_abs": net_return20_abs,
        "chop_overlap10": overlap10,
        "chop_atr14_pct": atr14_pct,
        "chop_is_sideways_ge3": score >= 3,
        "chop_is_sideways_ge4": score >= 4,
    }
