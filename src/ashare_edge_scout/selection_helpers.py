"""Numeric helpers shared by selection pipelines (MKF, A-class, SMC).

Lifted out of the SMC ``stock_selector`` module during the 2026-09-27 ``smc/``
separation so that main-tree modules never import from the SMC-owned package.
The SMC package imports these helpers back from here (dependency direction is
smc -> main only).
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if np.isfinite(result) else default


def range_position_pct(history: pd.DataFrame, window: int) -> float:
    sample = history.tail(window)
    if sample.empty:
        return 100.0
    close = safe_float(sample.iloc[-1].get("close"), 0.0)
    high = safe_float(pd.to_numeric(sample["high"], errors="coerce").max(), close)
    low = safe_float(pd.to_numeric(sample["low"], errors="coerce").min(), close)
    if high <= low:
        return 100.0
    return float(np.clip((close - low) / (high - low) * 100.0, 0.0, 100.0))


def return_pct(history: pd.DataFrame, current_offset: int, prior_offset: int) -> float:
    if len(history) <= max(current_offset, prior_offset):
        return 0.0
    current = safe_float(history.iloc[-1 - current_offset].get("close"), 0.0)
    prior = safe_float(history.iloc[-1 - prior_offset].get("close"), 0.0)
    if current <= 0.0 or prior <= 0.0:
        return 0.0
    return (current / prior - 1.0) * 100.0
