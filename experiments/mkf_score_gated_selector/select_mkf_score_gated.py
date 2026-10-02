#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

import numpy as np
import pandas as pd

SCHEMA_VERSION = "isolated_mkf_score_gated_selector_v1"
RULE_VERSION = "doris_k_local_lag_v1_2026-09-23"
DEFAULT_PREFIXES = ("sh.600", "sh.601", "sh.603", "sh.605", "sz.000", "sz.001", "sz.002", "sz.003", "sz.300", "sz.301")
REQUIRED_COLUMNS = ("date", "open", "high", "low", "close", "volume", "amount", "tradestatus", "isST")
ALLOWED_SHARED_INPUTS = ("virtualenv", "Key", "PFrontStockData")
CHOP_EXCLUDE_SCORE = 4
CHOP_THRESHOLDS = {
    "efficiency20_max": 0.25,
    "range20_pct_max": 0.12,
    "net_return20_abs_max": 0.04,
    "overlap10_min": 0.55,
    "atr14_pct_max": 0.035,
}

RULES = (
    {
        "rule_id": "strong_k9_l8_lag0",
        "rule_label": "K线9.0-9.9 + 本地分8.0-8.4 + lag0",
        "rule_priority": 1,
        "k_min": 9.0,
        "k_max_exclusive": 10.0,
        "local_min": 8.0,
        "local_max_exclusive": 8.5,
        "lags": {0},
        "t20_3pct": 0.839080459770115,
        "t20_4pct": 0.7739463601532567,
    },
    {
        "rule_id": "watch_k8_l6_lag2",
        "rule_label": "K线8.0-8.9 + 本地分6.0-6.4 + lag2",
        "rule_priority": 2,
        "k_min": 8.0,
        "k_max_exclusive": 9.0,
        "local_min": 6.0,
        "local_max_exclusive": 6.5,
        "lags": {2},
        "t20_3pct": 0.7889344262295082,
        "t20_4pct": 0.7295081967213115,
    },
    {
        "rule_id": "slow_repair_k4_l_lt6_lag1_lag3",
        "rule_label": "K线4.0-4.9 + 本地分<6.0 + lag1/lag3",
        "rule_priority": 3,
        "k_min": 4.0,
        "k_max_exclusive": 5.0,
        "local_lt": 6.0,
        "lags": {1, 3},
        "t20_3pct": 0.7902973395931141,
        "t20_4pct": 0.7347417840375586,
    },
)


@dataclass(frozen=True)
class NearMissRow:
    schema_version: str
    run_id: str
    as_of: str
    code: str
    signal_date: str
    cross_date: str
    post_cross_lag: int
    reject_reason: str
    nearest_rule_id: str
    nearest_rule_label: str
    nearest_rule_gap: float
    research_close: float
    entry_next_open_date: str | None
    entry_next_open_price: float | None
    amount_cny: float
    mkf_momentum: float
    mkf_near: float
    mkf_inter: float
    candle_confirm_score: float
    candle_confirm_reason: str
    local_score: float
    local_observations: str
    local_risks: str
    chop_available: bool
    chop_score: int | None
    chop_efficiency20: float | None
    chop_range20_pct: float | None
    chop_net_return20_abs: float | None
    chop_overlap10: float | None
    chop_atr14_pct: float | None
    chop_is_sideways_ge4: bool
    research_only: bool
    production_enabled: bool
    broker_connected: bool
    orders_submitted: bool
    source_path: str


@dataclass(frozen=True)
class CandidateRow:
    schema_version: str
    run_id: str
    as_of: str
    code: str
    signal_date: str
    cross_date: str
    post_cross_lag: int
    rule_id: str
    rule_label: str
    rule_priority: int
    research_close: float
    entry_next_open_date: str | None
    entry_next_open_price: float | None
    amount_cny: float
    mkf_momentum: float
    mkf_near: float
    mkf_inter: float
    candle_confirm_score: float
    candle_confirm_reason: str
    local_score: float
    local_observations: str
    local_risks: str
    chop_available: bool
    chop_score: int | None
    chop_efficiency20: float | None
    chop_range20_pct: float | None
    chop_net_return20_abs: float | None
    chop_overlap10: float | None
    chop_atr14_pct: float | None
    chop_is_sideways_ge4: bool
    expected_t20_3pct_hit_rate: float
    expected_t20_4pct_hit_rate: float
    research_only: bool
    production_enabled: bool
    broker_connected: bool
    orders_submitted: bool
    source_path: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Isolated MKF K-score/local-score gated selector experiment")
    parser.add_argument("--data-root", type=Path, default=Path("PFrontStockData"))
    parser.add_argument("--output-root", type=Path, default=Path(".runtime/mkf_score_gated_selector"))
    parser.add_argument("--as-of", type=date.fromisoformat)
    parser.add_argument("--run-id")
    parser.add_argument("--top", type=int, default=50)
    parser.add_argument("--limit-codes", type=int)
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [json_safe(item) for item in value]
    if isinstance(value, (pd.Timestamp, datetime, date)):
        return value.isoformat()
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value) if math.isfinite(float(value)) else None
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    return value


def csv_value(value: Any) -> Any:
    if isinstance(value, (list, tuple, dict, set)):
        return json.dumps(json_safe(value), ensure_ascii=False, sort_keys=True)
    if isinstance(value, float):
        return round(value, 8) if math.isfinite(value) else ""
    if value is None:
        return ""
    return value


def normalise_frame(frame: pd.DataFrame, as_of: date | None) -> pd.DataFrame:
    data = frame.copy()
    data["date"] = pd.to_datetime(data.get("date"), errors="coerce").dt.normalize()
    data = data.dropna(subset=["date"]).sort_values("date", kind="stable").drop_duplicates("date", keep="last")
    if as_of is not None:
        data = data.loc[data["date"].le(pd.Timestamp(as_of))]
    return data.reset_index(drop=True)


def tradable_mask(frame: pd.DataFrame) -> pd.Series:
    return frame.get("tradestatus", pd.Series(index=frame.index, dtype=object)).astype("string").eq("1").fillna(False)


def numeric(frame: pd.DataFrame, column: str) -> pd.Series:
    return pd.to_numeric(frame.get(column, pd.Series(index=frame.index, dtype=float)), errors="coerce")


def sma(values: Iterable[float], window: int) -> np.ndarray:
    arr = np.asarray(list(values), dtype=float)
    out = np.full(len(arr), np.nan, dtype=float)
    if window <= 0 or len(arr) < window:
        return out
    series = pd.Series(arr)
    out[:] = series.rolling(window, min_periods=window).mean().to_numpy(dtype=float)
    return out


def mkf_red_blue_cross20_lines(frame: pd.DataFrame) -> pd.DataFrame:
    trading = frame.loc[tradable_mask(frame)].copy()
    high = numeric(trading, "high")
    low = numeric(trading, "low")
    close = numeric(trading, "close")

    def rolling_rsv(window: int) -> pd.Series:
        minimum = low.rolling(window, min_periods=window).min()
        maximum = high.rolling(window, min_periods=window).max()
        denominator = maximum - minimum
        return close.sub(minimum).div(denominator.where(denominator.gt(0))).mul(100.0)

    momentum_minimum = low.rolling(2, min_periods=2).min()
    momentum_base_minimum = low.rolling(4, min_periods=4).min()
    momentum_maximum = high.rolling(4, min_periods=4).max()
    denominator = momentum_maximum - momentum_base_minimum
    momentum = close.sub(momentum_minimum).div(denominator.where(denominator.gt(0))).mul(100.0)
    result = pd.DataFrame(index=frame.index, columns=["momentum", "inter", "near"], dtype=float)
    result.loc[trading.index, "momentum"] = momentum
    result.loc[trading.index, "inter"] = rolling_rsv(31).rolling(5, min_periods=5).mean()
    result.loc[trading.index, "near"] = rolling_rsv(5).rolling(2, min_periods=2).mean()
    return result


def parent_cross_mask(frame: pd.DataFrame) -> pd.Series:
    lines = mkf_red_blue_cross20_lines(frame)
    trading = tradable_mask(frame)
    trading_lines = lines.loc[trading]
    prior = trading_lines.shift(1)
    prior_bullcluster = prior[["momentum", "inter", "near"]].le(20.0).all(axis=1)
    red_blue_cross = (
        prior["momentum"].lt(20.0)
        & trading_lines["momentum"].ge(20.0)
        & prior["near"].lt(20.0)
        & trading_lines["near"].ge(20.0)
    )
    under_80 = trading_lines["momentum"].lt(80.0) & trading_lines["near"].lt(80.0)
    signal = pd.Series(False, index=frame.index, dtype=bool)
    signal.loc[trading_lines.index] = (prior_bullcluster & red_blue_cross & under_80).fillna(False)
    return signal


def latest_cross_context(frame: pd.DataFrame, row_index: int, allowed_lags: set[int]) -> tuple[int, int] | None:
    base = parent_cross_mask(frame)
    tradable_indexes = list(frame.index[tradable_mask(frame)])
    if row_index not in tradable_indexes:
        return None
    position = tradable_indexes.index(row_index)
    for lag in sorted(allowed_lags):
        cross_position = position - lag
        if cross_position >= 0 and bool(base.loc[tradable_indexes[cross_position]]):
            return int(tradable_indexes[cross_position]), int(lag)
    return None


def missing_chop_features() -> dict[str, Any]:
    return {
        "chop_available": False,
        "chop_score": None,
        "chop_efficiency20": None,
        "chop_range20_pct": None,
        "chop_net_return20_abs": None,
        "chop_overlap10": None,
        "chop_atr14_pct": None,
        "chop_is_sideways_ge4": False,
    }


def finite_window(values: np.ndarray) -> bool:
    return bool(len(values)) and bool(np.isfinite(values).all())


def compute_sideways_chop_features_at(data: pd.DataFrame, row_index: int) -> dict[str, Any]:
    close = numeric(data, "close").to_numpy(dtype=float)
    high = numeric(data, "high").to_numpy(dtype=float)
    low = numeric(data, "low").to_numpy(dtype=float)
    if row_index < 20 or row_index >= len(close):
        return missing_chop_features()
    close_window = close[row_index - 20:row_index + 1]
    high_window = high[row_index - 19:row_index + 1]
    low_window = low[row_index - 19:row_index + 1]
    if not (finite_window(close_window) and finite_window(high_window) and finite_window(low_window)):
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
    if not (finite_window(overlap_high) and finite_window(overlap_low)):
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
    if not (finite_window(atr_high) and finite_window(atr_low) and finite_window(atr_close)):
        return missing_chop_features()
    true_ranges = []
    for offset in range(14):
        previous_close = atr_close[offset]
        true_ranges.append(max(atr_high[offset] - atr_low[offset], abs(atr_high[offset] - previous_close), abs(atr_low[offset] - previous_close)))
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
        "chop_is_sideways_ge4": score >= CHOP_EXCLUDE_SCORE,
    }


def compute_candle_confirmation_features(open_: Iterable[float], high: Iterable[float], low: Iterable[float], close: Iterable[float], volume: Iterable[float] | None) -> dict[str, Any]:
    open_arr = np.asarray(list(open_), dtype=float)
    high_arr = np.asarray(list(high), dtype=float)
    low_arr = np.asarray(list(low), dtype=float)
    close_arr = np.asarray(list(close), dtype=float)
    empty = {
        "candle_position_zone": "N/A",
        "candle_low_position_pct": 1.0,
        "candle_close_location": 0.0,
        "candle_volume_confirm": False,
        "candle_volume_ratio_20": 0.0,
        "candle_upper_shadow_pct": 1.0,
        "candle_long_upper_shadow_risk": True,
        "candle_bullish_reversal": False,
        "candle_bullish_continuation": False,
        "candle_box_breakout": False,
        "candle_confirm_score": 0.0,
        "candle_confirm_reason": "insufficient_data",
    }
    if len(close_arr) < 20 or close_arr[-1] <= 0 or high_arr[-1] <= 0 or low_arr[-1] <= 0:
        return empty
    if not all(np.isfinite(arr[-1]) for arr in (open_arr, high_arr, low_arr, close_arr)):
        return empty
    pos_high = float(np.nanmax(high_arr[-60:]))
    pos_low = float(np.nanmin(low_arr[-60:]))
    low_position_pct = 1.0 if pos_high <= pos_low or not np.isfinite(pos_high) or not np.isfinite(pos_low) else float(np.clip((close_arr[-1] - pos_low) / (pos_high - pos_low), 0.0, 1.0))
    if low_position_pct <= 0.33:
        position_zone = "low"
    elif low_position_pct <= 0.55:
        position_zone = "mid_low"
    elif low_position_pct <= 0.75:
        position_zone = "middle"
    else:
        position_zone = "high"
    day_range = max(high_arr[-1] - low_arr[-1], 1e-12)
    close_location = float(np.clip((close_arr[-1] - low_arr[-1]) / day_range, 0.0, 1.0))
    upper_shadow_pct = float(np.clip((high_arr[-1] - max(open_arr[-1], close_arr[-1])) / day_range, 0.0, 1.0))
    long_upper_shadow_risk = upper_shadow_pct > 0.40
    volume_ratio_20 = 0.0
    volume_confirm = False
    if volume is not None:
        vol_arr = np.asarray(list(volume), dtype=float)
        if len(vol_arr) >= 20:
            vol_ma = float(np.mean(vol_arr[-20:]))
            volume_ratio_20 = float(vol_arr[-1] / vol_ma) if vol_ma > 0 else 0.0
            volume_confirm = 1.05 <= volume_ratio_20 <= 2.80
    reversal_lookback = 5
    prior = close_arr[-reversal_lookback - 1:-1] if len(close_arr) > reversal_lookback else close_arr[:-1]
    candle_bullish_reversal = False
    if len(prior) >= 3:
        prior_soft = close_arr[-2] <= np.nanmean(prior) and close_arr[-2] <= close_arr[-reversal_lookback]
        candle_bullish_reversal = bool(prior_soft and close_arr[-1] > open_arr[-1] and close_location >= 0.55 and low_position_pct <= 0.55)
    ma5 = sma(close_arr, 5)
    ma10 = sma(close_arr, 10)
    ma5_rising = len(ma5) >= 3 and np.isfinite(ma5[-1]) and np.isfinite(ma5[-3]) and ma5[-1] > ma5[-3]
    ma_support = len(ma10) > 0 and np.isfinite(ma10[-1]) and close_arr[-1] >= ma10[-1]
    candle_bullish_continuation = bool(close_arr[-1] > open_arr[-1] and ma5_rising and ma_support and low_position_pct <= 0.75 and close_location >= 0.55)
    candle_box_breakout = False
    if len(high_arr) > 20:
        box_high = float(np.nanmax(high_arr[-21:-1]))
        candle_box_breakout = bool(close_arr[-1] > box_high * 1.003 and volume_confirm and close_location >= 0.55)
    score = 0.0
    reasons: list[str] = []
    if low_position_pct <= 0.55:
        score += 2.0
        reasons.append(position_zone)
    if close_location >= 0.55:
        score += 2.0
        reasons.append("strong_close")
    if volume_confirm:
        score += 2.0
        reasons.append("healthy_volume")
    if not long_upper_shadow_risk:
        score += 1.0
        reasons.append("no_long_upper_shadow")
    if candle_bullish_reversal:
        score += 2.0
        reasons.append("bullish_reversal")
    if candle_bullish_continuation:
        score += 1.5
        reasons.append("bullish_continuation")
    if candle_box_breakout:
        score += 2.0
        reasons.append("box_breakout")
    return {
        "candle_position_zone": position_zone,
        "candle_low_position_pct": low_position_pct,
        "candle_close_location": close_location,
        "candle_volume_confirm": volume_confirm,
        "candle_volume_ratio_20": volume_ratio_20,
        "candle_upper_shadow_pct": upper_shadow_pct,
        "candle_long_upper_shadow_risk": long_upper_shadow_risk,
        "candle_bullish_reversal": candle_bullish_reversal,
        "candle_bullish_continuation": candle_bullish_continuation,
        "candle_box_breakout": candle_box_breakout,
        "candle_confirm_score": float(min(score, 10.0)),
        "candle_confirm_reason": "+".join(reasons) if reasons else "no_confirmation",
    }


def pct_change(series: pd.Series, days: int) -> float | None:
    values = pd.to_numeric(series, errors="coerce")
    if len(values) <= days or not np.isfinite(values.iloc[-days - 1]) or values.iloc[-days - 1] == 0 or not np.isfinite(values.iloc[-1]):
        return None
    return round((float(values.iloc[-1]) / float(values.iloc[-days - 1]) - 1.0) * 100.0, 4)


def ratio_to_tail(series: pd.Series, days: int) -> float | None:
    values = pd.to_numeric(series, errors="coerce")
    if len(values) < days + 1:
        return None
    base = values.iloc[-days - 1:-1].mean()
    now = values.iloc[-1]
    if not np.isfinite(base) or base <= 0 or not np.isfinite(now):
        return None
    return round(float(now / base), 4)


def local_score(candidate: Mapping[str, Any], confirmation: Mapping[str, Any], ohlcv: Mapping[str, Any]) -> tuple[float, list[str], list[str]]:
    score = 5.0
    observations: list[str] = []
    risks: list[str] = []
    momentum = float(candidate.get("mkf_momentum") or 0.0)
    near = float(candidate.get("mkf_near") or 0.0)
    inter = float(candidate.get("mkf_inter") or 0.0)
    if 20.0 <= momentum <= 45.0 and 20.0 <= near <= 45.0:
        score += 1.0
        observations.append("MKF红蓝线上穿后仍未过热")
    if inter >= 20.0:
        score += 0.5
        observations.append("MKF中线同步改善")
    if momentum >= 70.0 or near >= 70.0:
        score -= 1.0
        risks.append("MKF线接近高位区")
    volume_ratio = ohlcv.get("volume_ratio_5d")
    if isinstance(volume_ratio, (int, float)):
        if 1.1 <= float(volume_ratio) <= 3.0:
            score += 0.5
            observations.append("5日量能温和放大")
        elif float(volume_ratio) > 5.0:
            score -= 0.8
            risks.append("量能异常放大")
    ret5 = ohlcv.get("recent_close_return_5d_pct")
    if isinstance(ret5, (int, float)) and float(ret5) > 18.0:
        score -= 0.8
        risks.append("近5日涨幅偏热")
    ret10 = ohlcv.get("recent_close_return_10d_pct")
    if isinstance(ret10, (int, float)) and float(ret10) > 30.0:
        score -= 0.6
        risks.append("近10日涨幅偏热")
    if confirmation.get("candle_close_location") is not None and float(confirmation.get("candle_close_location") or 0.0) >= 0.65:
        score += 0.4
        observations.append("信号日收盘位置偏强")
    if confirmation.get("candle_long_upper_shadow_risk"):
        score -= 0.8
        risks.append("长上影风险")
    elif confirmation:
        score += 0.3
        observations.append("无明显长上影风险")
    if confirmation.get("candle_bullish_reversal"):
        score += 0.6
        observations.append("bullish reversal context")
    if confirmation.get("candle_bullish_continuation"):
        score += 0.5
        observations.append("bullish continuation context")
    if confirmation.get("candle_box_breakout"):
        score += 0.5
        observations.append("box breakout confirmation")
    if confirmation.get("candle_volume_confirm"):
        score += 0.3
        observations.append("20日量能确认健康")
    if float(confirmation.get("candle_close_location") or 1.0) <= 0.25:
        score -= 0.6
        risks.append("信号日收盘接近日内低位")
    if not observations:
        observations.append("仅满足隔离MKF基础候选条件")
    return max(1.0, min(10.0, round(score, 4))), observations, risks


def classify_rule(candle_score: float, score: float, lag: int) -> Mapping[str, Any] | None:
    for rule in RULES:
        if lag not in rule["lags"]:
            continue
        if not (float(rule["k_min"]) <= candle_score < float(rule["k_max_exclusive"])):
            continue
        if "local_lt" in rule:
            if score < float(rule["local_lt"]):
                return rule
        elif float(rule["local_min"]) <= score < float(rule["local_max_exclusive"]):
            return rule
    return None


def range_gap(value: float, minimum: float | None, maximum_exclusive: float | None) -> float:
    if minimum is not None and value < minimum:
        return minimum - value
    if maximum_exclusive is not None and value >= maximum_exclusive:
        return value - maximum_exclusive + 0.0001
    return 0.0


def nearest_rule(candle_score: float, score: float, lag: int) -> tuple[Mapping[str, Any], float, str]:
    best: tuple[Mapping[str, Any], float, str] | None = None
    for rule in RULES:
        lag_gap = 0.0 if lag in rule["lags"] else min(abs(lag - int(candidate_lag)) for candidate_lag in rule["lags"])
        candle_gap = range_gap(candle_score, float(rule["k_min"]), float(rule["k_max_exclusive"]))
        if "local_lt" in rule:
            local_gap = 0.0 if score < float(rule["local_lt"]) else score - float(rule["local_lt"]) + 0.0001
        else:
            local_gap = range_gap(score, float(rule["local_min"]), float(rule["local_max_exclusive"]))
        total_gap = lag_gap * 10.0 + candle_gap + local_gap
        misses = []
        if lag_gap:
            misses.append(f"lag不匹配: 当前lag{lag}, 规则允许{sorted(rule['lags'])}")
        if candle_gap:
            misses.append(f"K线分不匹配: 当前{candle_score:.2f}, 规则[{rule['k_min']},{rule['k_max_exclusive']})")
        if local_gap:
            if "local_lt" in rule:
                misses.append(f"本地分不匹配: 当前{score:.2f}, 规则< {rule['local_lt']}")
            else:
                misses.append(f"本地分不匹配: 当前{score:.2f}, 规则[{rule['local_min']},{rule['local_max_exclusive']})")
        reason = "; ".join(misses) if misses else "unknown_rule_reject"
        if best is None or total_gap < best[1]:
            best = (rule, float(total_gap), reason)
    if best is None:
        raise AssertionError("RULES must not be empty")
    return best


def next_tradable_open(frame: pd.DataFrame, row_index: int) -> tuple[str | None, float | None]:
    trading = tradable_mask(frame)
    open_ = numeric(frame, "open")
    dates = pd.to_datetime(frame["date"], errors="coerce")
    after = [idx for idx in frame.index if idx > row_index and bool(trading.loc[idx]) and np.isfinite(open_.loc[idx]) and open_.loc[idx] > 0]
    if not after:
        return None, None
    idx = int(after[0])
    return dates.loc[idx].date().isoformat(), float(open_.loc[idx])


def evaluate_stock(path: Path, as_of: date | None) -> tuple[CandidateRow | None, NearMissRow | None, str]:
    code = path.stem
    if not code.startswith(DEFAULT_PREFIXES):
        return None, None, "prefix_skipped"
    try:
        frame = pd.read_parquet(path)
    except Exception:
        return None, None, "read_error"
    missing = [col for col in REQUIRED_COLUMNS if col not in frame.columns]
    if missing:
        return None, None, "missing_columns"
    data = normalise_frame(frame, as_of)
    if data.empty:
        return None, None, "empty"
    target_date = pd.Timestamp(as_of) if as_of is not None else pd.Timestamp(data["date"].max())
    if data.iloc[-1]["date"] != target_date:
        return None, None, "missing_as_of_bar"
    row_index = int(data.index[-1])
    if not bool(tradable_mask(data).loc[row_index]):
        return None, None, "not_tradable"
    is_st = str(data.loc[row_index].get("isST", "0")).lower()
    if is_st in {"1", "true", "t", "yes"}:
        return None, None, "st_rejected"
    context = latest_cross_context(data, row_index, {0, 1, 2, 3})
    if context is None:
        return None, None, "signal_absent"
    chop = compute_sideways_chop_features_at(data, row_index)
    if chop["chop_available"] and int(chop["chop_score"] or 0) >= CHOP_EXCLUDE_SCORE:
        return None, None, "chop_ge4_rejected"
    cross_index, lag = context
    lines = mkf_red_blue_cross20_lines(data)
    current = lines.loc[row_index]
    history = data.iloc[: row_index + 1].tail(120).reset_index(drop=True)
    open_ = numeric(history, "open")
    high = numeric(history, "high")
    low = numeric(history, "low")
    close = numeric(history, "close")
    volume = numeric(history, "volume")
    amount = numeric(history, "amount")
    confirmation = compute_candle_confirmation_features(open_, high, low, close, volume)
    ohlcv = {
        "recent_close_return_5d_pct": pct_change(close, 5),
        "recent_close_return_10d_pct": pct_change(close, 10),
        "volume_ratio_5d": ratio_to_tail(volume, 5),
        "volume_ratio_20d": ratio_to_tail(volume, 20),
        "amount_ratio_5d": ratio_to_tail(amount, 5),
    }
    candidate = {
        "mkf_momentum": float(current.get("momentum") or 0.0),
        "mkf_inter": float(current.get("inter") or 0.0),
        "mkf_near": float(current.get("near") or 0.0),
    }
    score, observations, risks = local_score(candidate, confirmation, ohlcv)
    candle_score = float(confirmation.get("candle_confirm_score") or 0.0)
    entry_date, entry_open = next_tradable_open(data, row_index)
    latest = data.loc[row_index]
    rule = classify_rule(candle_score, score, lag)
    if rule is None:
        near_rule, gap, reason = nearest_rule(candle_score, score, lag)
        return None, NearMissRow(
            schema_version=SCHEMA_VERSION,
            run_id="",
            as_of=target_date.date().isoformat(),
            code=code,
            signal_date=target_date.date().isoformat(),
            cross_date=pd.Timestamp(data.loc[cross_index, "date"]).date().isoformat(),
            post_cross_lag=int(lag),
            reject_reason=reason,
            nearest_rule_id=str(near_rule["rule_id"]),
            nearest_rule_label=str(near_rule["rule_label"]),
            nearest_rule_gap=round(float(gap), 4),
            research_close=float(latest.get("close")),
            entry_next_open_date=entry_date,
            entry_next_open_price=entry_open,
            amount_cny=float(latest.get("amount")),
            mkf_momentum=float(current.get("momentum") or 0.0),
            mkf_near=float(current.get("near") or 0.0),
            mkf_inter=float(current.get("inter") or 0.0),
            candle_confirm_score=candle_score,
            candle_confirm_reason=str(confirmation.get("candle_confirm_reason") or ""),
            local_score=float(score),
            local_observations=";".join(observations),
            local_risks=";".join(risks),
            chop_available=bool(chop["chop_available"]),
            chop_score=None if chop["chop_score"] is None else int(chop["chop_score"]),
            chop_efficiency20=chop["chop_efficiency20"],
            chop_range20_pct=chop["chop_range20_pct"],
            chop_net_return20_abs=chop["chop_net_return20_abs"],
            chop_overlap10=chop["chop_overlap10"],
            chop_atr14_pct=chop["chop_atr14_pct"],
            chop_is_sideways_ge4=bool(chop["chop_is_sideways_ge4"]),
            research_only=True,
            production_enabled=False,
            broker_connected=False,
            orders_submitted=False,
            source_path=str(path),
        ), "rule_rejected"
    return CandidateRow(
        schema_version=SCHEMA_VERSION,
        run_id="",
        as_of=target_date.date().isoformat(),
        code=code,
        signal_date=target_date.date().isoformat(),
        cross_date=pd.Timestamp(data.loc[cross_index, "date"]).date().isoformat(),
        post_cross_lag=int(lag),
        rule_id=str(rule["rule_id"]),
        rule_label=str(rule["rule_label"]),
        rule_priority=int(rule["rule_priority"]),
        research_close=float(latest.get("close")),
        entry_next_open_date=entry_date,
        entry_next_open_price=entry_open,
        amount_cny=float(latest.get("amount")),
        mkf_momentum=float(current.get("momentum") or 0.0),
        mkf_near=float(current.get("near") or 0.0),
        mkf_inter=float(current.get("inter") or 0.0),
        candle_confirm_score=candle_score,
        candle_confirm_reason=str(confirmation.get("candle_confirm_reason") or ""),
        local_score=float(score),
        local_observations=";".join(observations),
        local_risks=";".join(risks),
        chop_available=bool(chop["chop_available"]),
        chop_score=None if chop["chop_score"] is None else int(chop["chop_score"]),
        chop_efficiency20=chop["chop_efficiency20"],
        chop_range20_pct=chop["chop_range20_pct"],
        chop_net_return20_abs=chop["chop_net_return20_abs"],
        chop_overlap10=chop["chop_overlap10"],
        chop_atr14_pct=chop["chop_atr14_pct"],
        chop_is_sideways_ge4=bool(chop["chop_is_sideways_ge4"]),
        expected_t20_3pct_hit_rate=float(rule["t20_3pct"]),
        expected_t20_4pct_hit_rate=float(rule["t20_4pct"]),
        research_only=True,
        production_enabled=False,
        broker_connected=False,
        orders_submitted=False,
        source_path=str(path),
    ), None, "selected"


def write_dataclass_rows(path: Path, rows: list[Any], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: csv_value(value) for key, value in asdict(row).items()})


def write_outputs(rows: list[CandidateRow], near_misses: list[NearMissRow], output_root: Path, run_id: str, summary: Mapping[str, Any]) -> Path:
    destination = output_root / run_id
    destination.mkdir(parents=True, exist_ok=False)
    fixed_rows = [CandidateRow(**{**asdict(row), "run_id": run_id}) for row in rows]
    fixed_near_misses = [NearMissRow(**{**asdict(row), "run_id": run_id}) for row in near_misses]
    csv_path = destination / "candidates.csv"
    near_csv_path = destination / "near_misses.csv"
    candidates_json_path = destination / "candidates.json"
    near_json_path = destination / "near_misses.json"
    summary_path = destination / "summary.json"
    write_dataclass_rows(csv_path, fixed_rows, list(CandidateRow.__dataclass_fields__))
    write_dataclass_rows(near_csv_path, fixed_near_misses, list(NearMissRow.__dataclass_fields__))
    candidates_json_path.write_text(json.dumps([json_safe(asdict(row)) for row in fixed_rows], ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    near_json_path.write_text(json.dumps([json_safe(asdict(row)) for row in fixed_near_misses], ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary_path.write_text(json.dumps(json_safe(summary), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest = {
        "schema_version": f"{SCHEMA_VERSION}_manifest",
        "run_id": run_id,
        "rule_version": RULE_VERSION,
        "files": {
            "candidates.csv": {"sha256": sha256(csv_path)},
            "candidates.json": {"sha256": sha256(candidates_json_path)},
            "near_misses.csv": {"sha256": sha256(near_csv_path)},
            "near_misses.json": {"sha256": sha256(near_json_path)},
            "summary.json": {"sha256": sha256(summary_path)},
        },
        "script_sha256": sha256(Path(__file__).resolve()),
    }
    (destination / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return destination


def run_self_test() -> None:
    cases = [
        (9.0, 8.0, 0, "strong_k9_l8_lag0"),
        (9.9, 8.4, 0, "strong_k9_l8_lag0"),
        (10.0, 8.4, 0, None),
        (8.0, 6.0, 2, "watch_k8_l6_lag2"),
        (8.9, 6.4, 2, "watch_k8_l6_lag2"),
        (9.0, 6.4, 2, None),
        (4.0, 5.99, 1, "slow_repair_k4_l_lt6_lag1_lag3"),
        (4.9, 5.0, 3, "slow_repair_k4_l_lt6_lag1_lag3"),
        (5.0, 5.0, 3, None),
        (4.5, 6.0, 1, None),
    ]
    for candle, score, lag, expected in cases:
        actual = classify_rule(candle, score, lag)
        actual_id = None if actual is None else actual["rule_id"]
        if actual_id != expected:
            raise AssertionError((candle, score, lag, expected, actual_id))
    source = Path(__file__).read_text(encoding="utf-8")
    forbidden = ("ashare" + "_edge_scout", "sys" + ".path", "scripts" + ".select_mkf_candidates")
    for token in forbidden:
        if token in source:
            raise AssertionError(f"forbidden token present: {token}")
    print("self_test=passed")


def main() -> int:
    args = parse_args()
    if args.self_test:
        run_self_test()
        return 0
    paths = sorted(args.data_root.glob("*.parquet"))
    if args.limit_codes is not None:
        paths = paths[: args.limit_codes]
    run_id = args.run_id or f"mkf-score-gated-{(args.as_of or date.today()).isoformat()}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    rows: list[CandidateRow] = []
    near_misses: list[NearMissRow] = []
    counters: Counter[str] = Counter()
    for index, path in enumerate(paths, start=1):
        row, near_miss, status = evaluate_stock(path, args.as_of)
        counters[status] += 1
        if row is not None:
            rows.append(row)
        if near_miss is not None:
            near_misses.append(near_miss)
        if index % 500 == 0 or index == len(paths):
            print(f"progress={index}/{len(paths)} selected={len(rows)} near_misses={len(near_misses)}", flush=True)
    rows.sort(key=lambda row: (row.rule_priority, -row.local_score, -row.candle_confirm_score, -row.amount_cny, row.code))
    near_misses.sort(key=lambda row: (row.nearest_rule_gap, row.nearest_rule_id, -row.local_score, -row.candle_confirm_score, -row.amount_cny, row.code))
    bucket_counts = Counter(row.rule_id for row in rows)
    near_miss_counts = Counter(row.nearest_rule_id for row in near_misses)
    summary = {
        "schema_version": SCHEMA_VERSION,
        "rule_version": RULE_VERSION,
        "status": "success",
        "run_id": run_id,
        "as_of": (args.as_of.isoformat() if args.as_of else "latest_available_per_code"),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "data_root": str(args.data_root),
        "output_root": str(args.output_root),
        "input_file_count": len(paths),
        "candidate_count": len(rows),
        "near_miss_count": len(near_misses),
        "bucket_counts": dict(sorted(bucket_counts.items())),
        "near_miss_counts": dict(sorted(near_miss_counts.items())),
        "status_counts": dict(sorted(counters.items())),
        "rules": [{key: sorted(value) if isinstance(value, set) else value for key, value in rule.items()} for rule in RULES],
        "boundaries": {
            "isolated_experiment": True,
            "imports_production_src": False,
            "uses_production_scripts": False,
            "shared_production_files_modified": False,
            "production_enabled": False,
            "watchlist_modified": False,
            "smc_modified": False,
            "broker_connected": False,
            "orders_submitted": False,
            "allowed_shared_inputs": list(ALLOWED_SHARED_INPUTS),
        },
        "limitations": [
            "research_only_candidate_screen",
            "no_live_broker_or_order_integration",
            "isolated_formula_copy_may_drift_from_future_production_changes",
            "current_parquet_snapshot_may_differ_from_doris_backtest_snapshot",
        ],
    }
    output_dir = write_outputs(rows, near_misses, args.output_root, run_id, summary)
    print("status=success")
    print(f"run_id={run_id}")
    print(f"candidate_count={len(rows)}")
    print(f"near_miss_count={len(near_misses)}")
    print(f"output_dir={output_dir}")
    print("production_enabled=false")
    print("broker_connected=false")
    print("orders_submitted=false")
    for row in rows[: args.top]:
        print(f"{row.rule_id}\t{row.code}\tlag{row.post_cross_lag}\tK={row.candle_confirm_score:.1f}\tL={row.local_score:.2f}\tclose={row.research_close:.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
