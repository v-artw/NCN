"""Native CNstock-compatible research discovery pools and ranking."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

import numpy as np


@dataclass(frozen=True)
class DiscoveryPoolDecision:
    pool: str
    eligible: bool
    rejection_reasons: tuple[str, ...]


def compute_price_volume_base_score(
    high: Sequence[float],
    low: Sequence[float],
    close: Sequence[float],
    volume: Sequence[float],
    *,
    futu_bonus: float,
) -> float:
    """Local OHLCV-only compatibility score; no Alpha or fundamental inputs."""

    h = np.asarray(high, dtype=np.float64)
    l = np.asarray(low, dtype=np.float64)
    c = np.asarray(close, dtype=np.float64)
    v = np.asarray(volume, dtype=np.float64)
    if len(c) < 60 or not (len(h) == len(l) == len(v) == len(c)):
        return 0.0
    smoothed = _kalman_prices(c)
    momentum = (smoothed[-1] / (smoothed[-20] + 1e-12) - 1.0) * 100.0
    if momentum < 0:
        return 0.0
    lower_bound = np.mean(smoothed[-20:]) - 1.5 * np.std(c[-20:], ddof=1)
    pit_hit = np.min(l[-3:]) < lower_bound
    volume_ratio_5 = v[-1] / (np.mean(v[-5:]) + 1e-6)
    penalty = 0.0
    if not pit_hit:
        penalty += 10.0
    if momentum < 5.0:
        penalty += min((5.0 - momentum) * 2.0, 20.0)
    elif momentum > 80.0:
        penalty += min((momentum - 80.0) * 3.0, 30.0)
    if volume_ratio_5 < 1.0:
        penalty += min((1.0 - volume_ratio_5) * 10.0, 15.0)
    volume_penalty = volume_ratio_5 * 12.0 if volume_ratio_5 > 3.0 else 0.0
    score = 40.0 + min(momentum, 50.0) + 20.0 - volume_penalty - penalty
    ret_5d = (c[-1] / c[-6] - 1.0) * 100.0
    if ret_5d < -5.0:
        score -= min((abs(ret_5d) - 5.0) * 2.0, 15.0)
    return round(score + futu_bonus, 6)


def evaluate_discovery_pool(
    *,
    start_count: int,
    base_score: float,
    pct_chg: float,
    ret_5d: float,
    amount_cny: float,
    risk_codes: Sequence[str],
    config: Mapping[str, Any],
) -> DiscoveryPoolDecision:
    """Apply CNstock-compatible 4+/5, 3/5 and exact 2/5 research pool gates."""

    discovery = config.get("cnstock_discovery", {})
    risks = set(risk_codes)
    if start_count >= 4:
        pool = "strong_start"
        cfg = discovery.get("strong_start", {})
        reasons = _numeric_rejections(
            base_score=base_score,
            pct_chg=pct_chg,
            ret_5d=ret_5d,
            amount_cny=amount_cny,
            min_score=float(cfg.get("min_base_score", 60.0)),
            max_pct=float(cfg.get("max_pct_chg", 7.0)),
            max_ret=float(cfg.get("max_ret_5d", 12.0)),
            min_amount=float(cfg.get("min_amount_cny", 30_000_000.0)),
        )
        rejected_risks = {"clear_signal", "high_position_risk", "overbought_risk", "mhpg_outflow"}
    elif start_count == 3:
        pool = "profit_shadow"
        cfg = discovery.get("profit_shadow", {})
        reasons = _numeric_rejections(
            base_score=base_score,
            pct_chg=pct_chg,
            ret_5d=ret_5d,
            amount_cny=amount_cny,
            min_score=float(cfg.get("min_base_score", 75.0)),
            max_pct=float(cfg.get("max_pct_chg", 7.0)),
            max_ret=float(cfg.get("max_ret_5d", 8.0)),
            min_amount=float(cfg.get("min_amount_cny", 30_000_000.0)),
        )
        rejected_risks = {"clear_signal", "high_position_risk", "overbought_risk", "mhpg_outflow"}
    elif start_count == 2:
        pool = "low_position_discovery"
        cfg = discovery.get("low_position", {})
        reasons = _numeric_rejections(
            base_score=base_score,
            pct_chg=pct_chg,
            ret_5d=ret_5d,
            amount_cny=amount_cny,
            min_score=float(cfg.get("min_base_score", 75.0)),
            max_pct=float(cfg.get("max_pct_chg", 5.0)),
            max_ret=float(cfg.get("max_ret_5d", 6.0)),
            min_amount=float(cfg.get("min_amount_cny", 30_000_000.0)),
        )
        rejected_risks = {"mhpg_outflow", "bear_divergence", "clear_signal", "high_position_risk", "overbought_risk"}
    else:
        return DiscoveryPoolDecision("not_in_cnstock_pool", False, ("start_signal_count_below_2",))
    reasons.extend(f"risk:{risk}" for risk in sorted(risks & rejected_risks))
    return DiscoveryPoolDecision(pool, not reasons, tuple(reasons))


def compute_cnstock_discovery_rank(
    base_score: float,
    pmk: Mapping[str, Any],
    candle: Mapping[str, Any],
    pct_chg: float,
    ret_5d: float,
    volume_ratio: float,
) -> tuple[float, str]:
    """CNstock V4/V5 soft rank, kept separate from Edge discovery score."""

    positive = (
        1.2 * float(candle.get("candle_confirm_score", 0.0))
        + 3.0 * float(candle.get("candle_close_location", 0.0))
        + max(0.0, 0.75 - float(candle.get("candle_low_position_pct", 1.0))) * 6.0
        + float(pmk.get("pmk_feature_bonus", 0.0))
        + np.clip(float(pmk.get("pmk_shape_score", 0.0)), 0.0, 100.0) / 100.0 * 3.0
        + (3.0 if pmk.get("pmk_trend_confirmed") else 0.0)
        + (1.5 if pmk.get("pmk_macd_confirm") else 0.0)
        + (1.0 if pmk.get("pmk_volume_breakout") else 0.0)
        + (2.0 if candle.get("candle_bullish_reversal") else 0.0)
        + (1.5 if candle.get("candle_bullish_continuation") else 0.0)
        + (2.0 if candle.get("candle_box_breakout") else 0.0)
    )
    position = float(candle.get("candle_low_position_pct", 1.0))
    penalty = (
        5.0 * float(candle.get("candle_upper_shadow_pct", 0.0))
        + max(0.0, position - 0.60) * 8.0
        + max(0.0, ret_5d - 8.0) * 0.8
        + max(0.0, pct_chg - 5.0)
        + max(0.0, volume_ratio - 3.5)
    )
    score = float(base_score) + positive - penalty
    return round(score, 6), f"base={base_score:.2f};positive={positive:.2f};penalty=-{penalty:.2f}"


def _numeric_rejections(*, base_score, pct_chg, ret_5d, amount_cny, min_score, max_pct, max_ret, min_amount):
    reasons: list[str] = []
    if base_score < min_score:
        reasons.append(f"base_score_below_{min_score:g}")
    if pct_chg > max_pct:
        reasons.append(f"pct_chg_above_{max_pct:g}")
    if ret_5d > max_ret:
        reasons.append(f"ret_5d_above_{max_ret:g}")
    if amount_cny < min_amount:
        reasons.append(f"amount_below_{min_amount:g}")
    return reasons


def _kalman_prices(prices: np.ndarray) -> np.ndarray:
    x = np.array((prices[0], 0.0), dtype=np.float64)
    covariance = np.eye(2, dtype=np.float64)
    transition = np.array(((1.0, 1.0), (0.0, 1.0)))
    process_noise = np.array(((0.01, 0.01), (0.01, 0.01)))
    output = np.zeros_like(prices)
    for index, value in enumerate(prices):
        x = transition @ x
        covariance = transition @ covariance @ transition.T + process_noise
        pseudo_gain = covariance[:, 1] / (covariance[1, 1] + 1e-5)
        x = x + pseudo_gain * (0.0 - x[1])
        # CNstock applies the pseudo constraint to state only, then lets the
        # ordinary price observation update covariance through FilterPy.
        gain = covariance[:, 0] / (covariance[0, 0] + 1.0)
        x = x + gain * (value - x[0])
        identity_minus_kh = np.eye(2) - np.outer(gain, (1.0, 0.0))
        covariance = identity_minus_kh @ covariance @ identity_minus_kh.T + np.outer(gain, gain)
        output[index] = x[0]
    return output
