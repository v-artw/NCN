"""Deterministic CNstock-inspired OHLCV start-signal observations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np


@dataclass(frozen=True)
class StartSignalResult:
    mhpg_buy: bool
    dxbd_up: bool
    mfk4_triggered: bool
    gding_up: bool
    dingdi_safe_up: bool
    reasons: tuple[str, ...]
    futu_bonus: float = 0.0
    status_codes: tuple[str, ...] = ()
    risk_codes: tuple[str, ...] = ()

    @property
    def count(self) -> int:
        return sum((self.mhpg_buy, self.dxbd_up, self.mfk4_triggered, self.gding_up, self.dingdi_safe_up))

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(
            name
            for name, active in (
                ("mhpg_buy", self.mhpg_buy),
                ("dxbd_up", self.dxbd_up),
                ("mfk4_triggered", self.mfk4_triggered),
                ("gding_up", self.gding_up),
                ("dingdi_safe_up", self.dingdi_safe_up),
            )
            if active
        )


def compute_start_signals(
    high: Sequence[float],
    low: Sequence[float],
    close: Sequence[float],
    volume: Sequence[float] | None = None,
) -> StartSignalResult:
    """Compute five start flags using only the supplied T-day history."""

    h = np.asarray(high, dtype=np.float64)
    l = np.asarray(low, dtype=np.float64)
    c = np.asarray(close, dtype=np.float64)
    if len(c) < 60 or not (len(h) == len(l) == len(c)) or not np.all(np.isfinite(c[-60:])):
        return StartSignalResult(False, False, False, False, False, ("insufficient_start_signal_history",))

    reasons: list[str] = []
    statuses: list[str] = []
    risks: list[str] = []
    bonus = 0.0

    if volume is not None:
        v = np.asarray(volume, dtype=np.float64)
        if len(v) == len(c):
            money_flow_raw = np.where(
                h == l,
                v,
                (2.0 * c - h - l) / (h - l + 1e-6) * v,
            )
            money_flow = _ema(money_flow_raw, 10)
            volume_ma60 = _rolling_mean(v, 60)
            if money_flow[-1] > 0 and v[-1] > volume_ma60[-1]:
                bonus += 5.0
                statuses.append("mhpg_inflow_confirmed")
            elif money_flow[-1] < 0 and v[-1] > volume_ma60[-1]:
                bonus -= 3.0
                statuses.append("mhpg_outflow_warning")
                risks.append("mhpg_outflow")

    ema20 = _ema(c, 20)
    ema60 = _ema(c, 60)
    low30 = _rolling_min(l, 30)
    high30 = _rolling_max(h, 30)
    rsv30 = (c - low30) / (high30 - low30 + 1e-6) * 100.0
    k = _tdx_sma(rsv30, 3, 1)
    d = _tdx_sma(k, 3, 1)
    mhpg_buy = bool(
        ema20[-1] > ema60[-1]
        and ema60[-1] > ema60[-3]
        and k[-2] <= d[-2]
        and k[-1] > d[-1]
        and k[-1] < 60.0
    )
    if mhpg_buy:
        reasons.append(f"MHPG_KD_cross(K={k[-1]:.1f})")
        statuses.append("mhpg_bull_kd_cross")
        bonus += 5.0

    low8 = _rolling_min(l, 8)
    high8 = _rolling_max(h, 8)
    cs = (c - low8) / (high8 - low8 + 1e-6) * 100.0
    dxbd = (_ema(cs, 3) - 50.0) * 2.0
    dxbd_up = False
    if dxbd[-1] > 78.0:
        bonus -= 25.0
        statuses.append("dxbd_extreme_overbought")
        risks.extend(("clear_signal", "overbought_risk"))
    elif dxbd[-1] > 60.0 and dxbd[-2] <= 60.0:
        bonus += 3.0
        statuses.append("dxbd_strong_breakout")
    elif dxbd[-1] > 60.0:
        bonus -= 8.0
        statuses.append("dxbd_high_risk")
        risks.append("high_position_risk")
    elif dxbd[-1] > 0.0 and dxbd[-2] <= 0.0:
        dxbd_up = True
        bonus += 2.0
        statuses.append("dxbd_cross_zero")
    elif dxbd[-1] > dxbd[-2] and dxbd[-2] < -80.0:
        bonus += 12.0
        statuses.append("dxbd_extreme_accumulation")
    elif dxbd[-1] > dxbd[-2] and dxbd[-2] < -60.0:
        bonus += 6.0
        statuses.append("dxbd_weak_rebound")
    elif dxbd[-1] < -60.0 and dxbd[-2] < -60.0:
        bonus -= 5.0
        statuses.append("dxbd_persistent_weakness")
    if dxbd_up:
        reasons.append("DXBD_cross_zero")

    momentum = (c - _rolling_min(l, 2)) / (
        _rolling_max(h, 4) - _rolling_min(l, 4) + 1e-6
    ) * 100.0
    inter = _rolling_mean((c - _rolling_min(l, 20)) / (_rolling_max(h, 20) - _rolling_min(l, 20) + 1e-6) * 100.0, 5)
    near = _rolling_mean((c - _rolling_min(l, 15)) / (_rolling_max(h, 15) - _rolling_min(l, 15) + 1e-6) * 100.0, 2)
    leaving = sum(
        previous <= 20.0 and current > previous
        for previous, current in ((momentum[-2], momentum[-1]), (inter[-2], inter[-1]), (near[-2], near[-1]))
    )
    low_zone_triggered = bool(leaving >= 2 and any(value <= 30.0 for value in (momentum[-1], inter[-1], near[-1])))
    all_low = all(value <= 20.0 for value in (momentum[-1], inter[-1], near[-1]))
    all_high = all(value >= 80.0 for value in (momentum[-1], inter[-1], near[-1]))
    if all_low:
        bonus += 3.0
        statuses.append("bullcluster_oversold")
    elif all_high:
        bonus -= 3.0
        statuses.append("bullcluster_overbought")
        risks.append("overbought_risk")

    ma5 = _rolling_mean(c, 5)
    ma10 = _rolling_mean(c, 10)
    ma20 = _rolling_mean(c, 20)
    ma60 = _rolling_mean(c, 60)
    current_values = np.array((ma5[-1], ma10[-1], ma20[-1], ma60[-1]))
    previous_values = np.array((ma5[-2], ma10[-2], ma20[-2], ma60[-2]))
    current_spread = (np.max(current_values) - np.min(current_values)) / (np.mean(current_values) + 1e-6)
    previous_spread = (np.max(previous_values) - np.min(previous_values)) / (np.mean(previous_values) + 1e-6)
    ma_dispersion_triggered = bool(
        ma5[-1] > ma20[-1]
        and ma10[-1] > ma60[-1]
        and current_spread > previous_spread
        and current_spread < 0.15
    )
    mfk4_triggered = low_zone_triggered or ma_dispersion_triggered
    if mfk4_triggered:
        if low_zone_triggered:
            reasons.append(f"MFK4_low_zone_lift({leaving})")
            statuses.append("mfk4_low_zone_start")
            bonus += 5.0
        if ma_dispersion_triggered:
            reasons.append("MFK4_ma_dispersion")
            statuses.append("mfk4_ma_dispersion")
            bonus += 6.0

    low9 = _rolling_min(l, 9)
    high9 = _rolling_max(h, 9)
    rsv_a1 = (c - low9) / (high9 - low9 + 1e-6) * 100.0
    rsv_a2 = 100.0 * (high9 - c) / (high9 - low9 + 1e-6)
    dingdi = (_tdx_sma(_tdx_sma(rsv_a1, 3, 1), 3, 1) + 100.0) - (_tdx_sma(rsv_a2, 9, 1) + 100.0) + 50.0
    dingdi_safe_up = bool(dingdi[-1] < 50.0 and dingdi[-1] > dingdi[-2])
    if dingdi[-1] > dingdi[-2]:
        bonus += 3.0
        statuses.append("dingdi_rising")
    elif dingdi[-1] < dingdi[-2]:
        bonus -= 3.0
        statuses.append("dingdi_falling")
    if dingdi[-1] > 80.0:
        bonus -= 2.0
        statuses.append("dingdi_high_risk")
        risks.append("high_position_risk")
    elif dingdi[-1] < 20.0:
        bonus += 2.0
        statuses.append("dingdi_safe_zone")
    if dingdi_safe_up:
        reasons.append(f"Dingdi_low_zone_rising({dingdi[-1]:.1f})")
        statuses.append("dingdi_safe_up")
        bonus += 2.0

    if len(l) >= 330:
        low330 = _rolling_min(l, 330)
        high210 = _rolling_max(h, 210)
        var4 = _ema((c - low330) / (high210 - low330 + 1e-6) * 100.0, 10) * -1.0 + 100.0
        trend = 100.0 - (0.191 * np.roll(var4, 1) + 0.809 * var4)
        trend[0] = 100.0 - var4[0]
        if trend[-1] > trend[-2] and dingdi[-1] < dingdi[-2]:
            bonus += 4.0
            statuses.append("bull_divergence")
        elif trend[-1] < trend[-2] and dingdi[-1] > dingdi[-2]:
            bonus -= 4.0
            statuses.append("bear_divergence")
            risks.append("bear_divergence")

    low17 = _rolling_min(l, 17)
    low_diff = np.abs(np.diff(l, prepend=l[0]))
    low_up = np.maximum(np.diff(l, prepend=l[0]), 0.0)
    ratio = _tdx_sma(low_diff, 17, 1) / (_tdx_sma(low_up, 17, 2) + 1e-6)
    q = -np.where(l <= low17, ratio, -3.0)
    typ = (c + l + h) / 3.0
    d2 = _ema(typ, 6)
    d3 = _ema(d2, 5)
    strong_pull = bool(q[-2] <= 0.0 < q[-1])
    bbuy_cross = bool(d2[-2] <= d3[-2] and d2[-1] > d3[-1])
    gding_up = strong_pull or bbuy_cross
    if gding_up:
        reasons.append("GDing_or_BBUY_cross")
        if strong_pull:
            statuses.append("gding_strong_pull")
            bonus += 4.0
        if bbuy_cross:
            statuses.append("bbuy_cross")
            bonus += 3.0

    return StartSignalResult(
        mhpg_buy,
        dxbd_up,
        mfk4_triggered,
        gding_up,
        dingdi_safe_up,
        tuple(reasons),
        round(bonus, 6),
        tuple(dict.fromkeys(statuses)),
        tuple(dict.fromkeys(risks)),
    )


def _ema(values: np.ndarray, period: int) -> np.ndarray:
    result = np.full_like(values, np.nan)
    finite_indices = np.flatnonzero(np.isfinite(values))
    if not len(finite_indices):
        return result
    start = int(finite_indices[0])
    result[start] = values[start]
    alpha = 2.0 / (period + 1.0)
    for index in range(start + 1, len(values)):
        if np.isfinite(values[index]):
            result[index] = alpha * values[index] + (1.0 - alpha) * result[index - 1]
        else:
            result[index] = result[index - 1]
    return result


def _tdx_sma(values: np.ndarray, period: int, weight: int) -> np.ndarray:
    clean = np.where(np.isfinite(values), values, 0.0)
    result = np.empty_like(clean)
    result[0] = clean[0]
    for index in range(1, len(clean)):
        result[index] = (weight * clean[index] + (period - weight) * result[index - 1]) / period
    return result


def _rolling_mean(values: np.ndarray, window: int) -> np.ndarray:
    result = np.full(len(values), np.nan)
    for index in range(window - 1, len(values)):
        current = values[index - window + 1:index + 1]
        finite = current[np.isfinite(current)]
        if len(finite):
            result[index] = np.mean(finite)
    return result


def _rolling_min(values: np.ndarray, window: int) -> np.ndarray:
    result = np.full(len(values), np.nan)
    for index in range(window - 1, len(values)):
        result[index] = np.nanmin(values[index - window + 1:index + 1])
    return result


def _rolling_max(values: np.ndarray, window: int) -> np.ndarray:
    result = np.full(len(values), np.nan)
    for index in range(window - 1, len(values)):
        result[index] = np.nanmax(values[index - window + 1:index + 1])
    return result
