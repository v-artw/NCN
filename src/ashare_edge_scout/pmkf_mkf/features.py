"""PMK 特征计算。

移植自 CNstock scan/pmk_features.py，改写为纯函数。
去除 pandas 依赖，核心计算接受 list/tuple/numpy array 输入。
"""

from __future__ import annotations

from typing import Sequence

import numpy as np


def sma(values: Sequence[float], window: int) -> np.ndarray:
    """计算移动平均。

    参数：
      values: 价格序列
      window: 窗口大小

    返回：
      移动平均数组
    """

    arr = np.array(values, dtype=np.float64)
    if window <= 0 or len(arr) == 0:
        return np.full(len(arr), np.nan)

    result = np.full(len(arr), np.nan)
    for i in range(window - 1, len(arr)):
        window_slice = arr[i - window + 1:i + 1]
        if np.any(np.isnan(window_slice)):
            continue
        result[i] = np.mean(window_slice)

    return result


def rsi(close: Sequence[float], period: int = 14) -> np.ndarray:
    """Compute RSI with the established Edge warm-up contract."""

    arr = np.array(close, dtype=np.float64)
    n = len(arr)
    result = np.full(n, np.nan)
    if n < period + 1:
        return result
    diff = np.diff(arr)
    up = np.maximum(diff, 0.0)
    down = np.maximum(-diff, 0.0)
    avg_up = float(np.mean(up[:period]))
    avg_down = float(np.mean(down[:period]))
    for i in range(period, n):
        if i > period:
            avg_up += (up[i - 1] - avg_up) / period
            avg_down += (down[i - 1] - avg_down) / period
        if avg_up == 0.0 and avg_down == 0.0:
            result[i] = 50.0
        elif avg_down == 0.0:
            result[i] = 100.0
        elif avg_up == 0.0:
            result[i] = 0.0
        else:
            result[i] = 100.0 - 100.0 / (1.0 + avg_up / avg_down)
    return np.clip(result, 0.0, 100.0)


def cnstock_rsi(close: Sequence[float], period: int = 14) -> np.ndarray:
    """Compute pandas-EWM-compatible RSI for the migrated discovery layer.

    参数：
      close: 收盘价序列
      period: 周期

    返回：
      RSI 数组（前 period-1 个值为 NaN，其余在 [0, 100]）
    """

    arr = np.array(close, dtype=np.float64)
    n = len(arr)
    if n == 0:
        return arr

    result = np.full(n, 50.0)

    try:
        if n < 2:
            return result
        diff = np.diff(arr)
        up = np.maximum(diff, 0.0)
        down = np.maximum(-diff, 0.0)
        alpha = 1.0 / period
        avg_up = float(up[0])
        avg_down = float(down[0])
        for i in range(1, n):
            if i > 1:
                avg_up = alpha * up[i - 1] + (1.0 - alpha) * avg_up
                avg_down = alpha * down[i - 1] + (1.0 - alpha) * avg_down
            if avg_up == 0.0 and avg_down == 0.0:
                result[i] = 50.0
            elif avg_down == 0.0:
                result[i] = 100.0
            elif avg_up == 0.0:
                result[i] = 0.0
            else:
                rs = avg_up / avg_down
                result[i] = 100.0 - (100.0 / (1.0 + rs))

        return np.clip(result, 0.0, 100.0)
    except Exception:
        return np.full(n, np.nan)


def atr(high: Sequence[float], low: Sequence[float], close: Sequence[float], window: int = 14) -> np.ndarray:
    """计算平均真实波动幅度。

    参数：
      high: 最高价序列
      low: 最低价序列
      close: 收盘价序列
      window: 窗口大小

    返回：
      ATR 数组
    """

    high_arr = np.array(high, dtype=np.float64)
    low_arr = np.array(low, dtype=np.float64)
    close_arr = np.array(close, dtype=np.float64)

    if len(close_arr) == 0:
        return np.array([], dtype=np.float64)

    # 计算真实波动幅度
    tr = np.zeros(len(close_arr))
    tr[0] = high_arr[0] - low_arr[0]

    for i in range(1, len(close_arr)):
        tr[i] = max(
            high_arr[i] - low_arr[i],
            abs(high_arr[i] - close_arr[i - 1]),
            abs(low_arr[i] - close_arr[i - 1]),
        )

    # 计算 ATR
    atr_values = np.zeros(len(close_arr))
    for i in range(window - 1, len(close_arr)):
        window_slice = tr[i - window + 1:i + 1]
        if np.any(np.isnan(window_slice)):
            continue
        atr_values[i] = np.mean(window_slice)

    return atr_values


def macd(close: Sequence[float], fast: int = 12, slow: int = 26, signal: int = 9) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """计算 MACD。

    参数：
      close: 收盘价序列
      fast: 快线周期
      slow: 慢线周期
      signal: 信号线周期

    返回：
      (DIF, DEA, MACD 柱状图) 元组
    """

    arr = np.array(close, dtype=np.float64)
    if len(arr) == 0:
        return np.array([]), np.array([]), np.array([])

    try:
        # 计算 EMA
        def ema(values: np.ndarray, period: int) -> np.ndarray:
            result = np.zeros_like(values)
            if len(values) == 0:
                return result

            multiplier = 2.0 / (period + 1)
            result[0] = values[0]

            for i in range(1, len(values)):
                if np.isnan(values[i]):
                    result[i] = result[i - 1]
                else:
                    result[i] = (values[i] - result[i - 1]) * multiplier + result[i - 1]

            return result

        dif = ema(arr, fast) - ema(arr, slow)
        dea = ema(dif, signal)
        hist = (dif - dea) * 2

        return dif, dea, hist
    except Exception:
        return np.array([]), np.array([]), np.array([])


def compute_pmk_features(
    open_: Sequence[float],
    high: Sequence[float],
    low: Sequence[float],
    close: Sequence[float],
    volume: Sequence[float] | None = None,
) -> dict[str, float | bool]:
    """计算 PMK 特征。

    参数：
      open_: 开盘价序列
      high: 最高价序列
      low: 最低价序列
      close: 收盘价序列
      volume: 成交量序列（可选）

    返回：
      PMK 特征字典
    """

    open_arr = np.array(open_, dtype=np.float64)
    high_arr = np.array(high, dtype=np.float64)
    low_arr = np.array(low, dtype=np.float64)
    close_arr = np.array(close, dtype=np.float64)

    if len(close_arr) < 20 or close_arr[-1] <= 0:
        return {
            "pmk_trend_confirmed": False,
            "pmk_trend_reason": "insufficient_data",
            "pmk_shape_score": 0.0,
            "pmk_shape_pattern": "N/A",
            "pmk_rsi": 50.0,
            "pmk_rsi_rebound_zone": False,
            "pmk_atr_squeeze": False,
            "pmk_atr14": 0.0,  # P0-5: 不足数据时 ATR14 为 0
            "pmk_macd_confirm": False,
            "pmk_volume_breakout": False,
            "pmk_feature_bonus": 0.0,
        }

    # 计算 RSI
    rsi_values = cnstock_rsi(close_arr)
    rsi_now = rsi_values[-1] if len(rsi_values) > 0 else 50.0

    # 计算 ATR（真实值，用于风险评分）
    atr_values = atr(high_arr, low_arr, close_arr, 14)
    atr_now = float(atr_values[-1]) if len(atr_values) > 0 and np.isfinite(atr_values[-1]) else 0.0
    atr_squeeze = False
    if len(atr_values) >= 20 and np.isfinite(atr_values[-1]):
        atr_window = atr_values[-20:]
        valid_atr = atr_window[np.isfinite(atr_window) & (atr_window > 0)]
        if len(valid_atr) >= 10:
            atr_rank = float(np.sum(valid_atr < atr_values[-1]) / len(valid_atr))
            atr_squeeze = atr_rank <= 0.45

    # 计算 MACD
    dif, dea, hist = macd(close_arr)
    macd_confirm = False
    if len(hist) >= 2:
        macd_cross = dif[-1] > dea[-1] and dif[-2] <= dea[-2]
        macd_rising = hist[-1] > 0 and hist[-1] > hist[-2]
        macd_confirm = bool(macd_cross or macd_rising)

    # CNstock PMK shape uses an explicit recent 10-bar window.
    y = close_arr[-10:]
    y = y[np.isfinite(y)]
    if len(y) >= 5 and y[0] > 0:
        x = np.arange(len(y), dtype=np.float64)
        poly_result = np.polyfit(x, y, 1)
        slope = float(poly_result[0])
        intercept = float(poly_result[1])
        norm_slope = slope / y[0] * 100
        tail_strength = y[-1] / (np.mean(y[-5:]) + 1e-12) if len(y) >= 5 else 1.0

        # 用 polyfit 的残差计算 r_squared
        y_pred = slope * np.arange(len(y), dtype=np.float64) + intercept
        ss_res = np.sum((y - y_pred) ** 2)
        ss_tot = np.sum((y - np.mean(y)) ** 2)
        r_squared = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0

        score = r_squared * 50
        if norm_slope > 0:
            score += min(norm_slope * 10, 30)
        else:
            score -= 50
        if tail_strength > 1.02:
            score += 20

        score = max(0, min(100, score))

        pattern = "Neutral"
        if norm_slope < 0:
            pattern = "Downtrend"
        elif r_squared > 0.85 and norm_slope > 0.5:
            pattern = "Steady Climber"
        elif tail_strength > 1.04:
            pattern = "Explosive Breakout"
        elif r_squared > 0.6 and 1.0 < tail_strength < 1.02:
            pattern = "Slow Bull"
        elif y[-1] > np.max(y[:-1]):
            pattern = "New High"
    else:
        score = 0.0
        pattern = "N/A"

    # 计算成交量特征（如果有）
    volume_breakout = False
    if volume is not None and len(volume) > 0:
        vol_arr = np.array(volume, dtype=np.float64)
        if len(vol_arr) >= 20:
            vol_ma = np.mean(vol_arr[-20:])
            vol_now = vol_arr[-1]
            volume_breakout = vol_now > vol_ma * 1.5

    # Align the port with CNstock: close>SMA20, MA5>MA10, plus volume or MACD confirmation.
    sma20 = sma(close_arr, 20)
    ma5 = sma(close_arr, 5)
    ma10 = sma(close_arr, 10)
    trend_base = (
        np.isfinite(sma20[-1])
        and np.isfinite(ma5[-1])
        and np.isfinite(ma10[-1])
        and close_arr[-1] > sma20[-1]
        and ma5[-1] > ma10[-1]
    )
    trend_confirmed = bool(trend_base and (volume_breakout or macd_confirm))
    trend_reasons: list[str] = []
    if volume_breakout:
        trend_reasons.append("Vol")
    if macd_confirm:
        trend_reasons.append("MACD")
    trend_reason = f"Trend+{'+'.join(trend_reasons)}" if trend_confirmed else ""

    feature_bonus = 0.0
    if trend_confirmed:
        feature_bonus += 6.0
    if score >= 70.0:
        feature_bonus += 2.0
    rsi_rebound = bool(rsi_now <= 40.0)
    if rsi_rebound and trend_confirmed:
        feature_bonus += 2.0
    if pattern == "Downtrend":
        feature_bonus -= 8.0
    feature_bonus = float(np.clip(feature_bonus, -8.0, 10.0))

    return {
        "pmk_trend_confirmed": bool(trend_confirmed),
        "pmk_trend_reason": trend_reason,
        "pmk_shape_score": float(score),
        "pmk_shape_pattern": pattern,
        "pmk_rsi": float(rsi_now),
        "pmk_rsi_rebound_zone": rsi_rebound,
        "pmk_atr_squeeze": bool(atr_squeeze),
        "pmk_atr14": float(atr_now),  # P0-5 修复：真实 ATR14 值供风险评分使用
        "pmk_macd_confirm": bool(macd_confirm),
        "pmk_volume_breakout": bool(volume_breakout),
        "pmk_feature_bonus": feature_bonus,
    }


__all__ = ["atr", "cnstock_rsi", "compute_pmk_features", "macd", "rsi", "sma"]
