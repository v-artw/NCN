"""蜡烛确认特征计算。

移植自 CNstock scan/candle_confirm.py，改写为纯函数。
去除 pandas 依赖，核心计算接受 list/tuple/numpy array 输入。
"""

from __future__ import annotations

from typing import Sequence

import numpy as np

from .pmk_features import sma


def compute_candle_confirmation_features(
    open_: Sequence[float],
    high: Sequence[float],
    low: Sequence[float],
    close: Sequence[float],
    volume: Sequence[float] | None = None,
) -> dict[str, float | bool | str]:
    """计算蜡烛确认特征。

    参数：
      open_: 开盘价序列
      high: 最高价序列
      low: 最低价序列
      close: 收盘价序列
      volume: 成交量序列（可选）

    返回：
      蜡烛确认特征字典
    """

    empty_features = {
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

    open_arr = np.array(open_, dtype=np.float64)
    high_arr = np.array(high, dtype=np.float64)
    low_arr = np.array(low, dtype=np.float64)
    close_arr = np.array(close, dtype=np.float64)

    if len(close_arr) < 20 or close_arr[-1] <= 0 or high_arr[-1] <= 0 or low_arr[-1] <= 0:
        return empty_features

    if not all(np.isfinite(x[-1]) for x in (open_arr, high_arr, low_arr, close_arr)):
        return empty_features

    # 位置分析
    position_lookback = max(20, 60)
    pos_high = float(np.nanmax(high_arr[-position_lookback:]))
    pos_low = float(np.nanmin(low_arr[-position_lookback:]))

    if pos_high <= pos_low or not np.isfinite(pos_high) or not np.isfinite(pos_low):
        low_position_pct = 1.0
    else:
        low_position_pct = float(np.clip((close_arr[-1] - pos_low) / (pos_high - pos_low), 0.0, 1.0))

    if low_position_pct <= 0.33:
        position_zone = "low"
    elif low_position_pct <= 0.55:
        position_zone = "mid_low"
    elif low_position_pct <= 0.75:
        position_zone = "middle"
    else:
        position_zone = "high"

    # 收盘位置分析
    day_range = max(high_arr[-1] - low_arr[-1], 1e-12)
    close_location = float(np.clip((close_arr[-1] - low_arr[-1]) / day_range, 0.0, 1.0))

    upper_shadow = high_arr[-1] - max(open_arr[-1], close_arr[-1])
    upper_shadow_pct = float(np.clip(upper_shadow / day_range, 0.0, 1.0))
    long_upper_shadow_risk = upper_shadow_pct > 0.40

    # 成交量分析
    volume_ratio_20 = 0.0
    volume_confirm = False

    if volume is not None and len(volume) > 0:
        vol_arr = np.array(volume, dtype=np.float64)
        if len(vol_arr) >= 20:
            vol_ma = np.mean(vol_arr[-20:])
            vol_now = vol_arr[-1]
            volume_ratio_20 = vol_now / vol_ma if vol_ma > 0 else 0.0
            volume_confirm = 1.05 <= volume_ratio_20 <= 2.80

    # Align reversal/continuation semantics with the CNstock source module.
    reversal_lookback = 5
    prior = close_arr[-reversal_lookback - 1:-1] if len(close_arr) > reversal_lookback else close_arr[:-1]

    if len(prior) >= 3:
        prior_soft = close_arr[-2] <= np.nanmean(prior) and close_arr[-2] <= close_arr[-reversal_lookback]
        bullish_body = close_arr[-1] > open_arr[-1]
        candle_bullish_reversal = (
            prior_soft
            and bullish_body
            and close_location >= 0.55
            and low_position_pct <= 0.55
        )
    else:
        candle_bullish_reversal = False

    ma5 = sma(close_arr, 5)
    ma10 = sma(close_arr, 10)
    ma5_rising = len(ma5) >= 3 and np.isfinite(ma5[-1]) and np.isfinite(ma5[-3]) and ma5[-1] > ma5[-3]
    ma_support = len(ma10) > 0 and np.isfinite(ma10[-1]) and close_arr[-1] >= ma10[-1]
    bullish_body = close_arr[-1] > open_arr[-1]
    candle_bullish_continuation = (
        bullish_body
        and ma5_rising
        and ma_support
        and low_position_pct <= 0.75
        and close_location >= 0.55
    )

    # 箱体突破（使用不含当前 bar 的前序 20 日高点）
    # 当前代码错误：box_high 包含当前 bar 的 high，而 close <= high <= box_high，
    # 导致 close > box_high * 1.003 数学上不可达（除非浮点误差）
    # 修复：使用前序 20 日的高点
    box_breakout_lookback = 20
    if len(high_arr) > box_breakout_lookback:
        prior_highs = high_arr[-(box_breakout_lookback + 1):-1]  # 不含当前 bar
        box_high = float(np.nanmax(prior_highs))
        candle_box_breakout = (
            close_arr[-1] > box_high * 1.003
            and volume_confirm
            and close_location >= 0.55
        )
    else:
        candle_box_breakout = False

    # 确认分数
    confirm_score = 0.0
    reason = "insufficient_data"

    reasons: list[str] = []
    if low_position_pct <= 0.55:
        confirm_score += 2.0
        reasons.append(position_zone)
    if close_location >= 0.55:
        confirm_score += 2.0
        reasons.append("strong_close")
    if volume_confirm:
        confirm_score += 2.0
        reasons.append("healthy_volume")
    if not long_upper_shadow_risk:
        confirm_score += 1.0
        reasons.append("no_long_upper_shadow")

    if candle_bullish_reversal:
        confirm_score += 2.0
        reasons.append("bullish_reversal")
    if candle_bullish_continuation:
        confirm_score += 1.5
        reasons.append("bullish_continuation")
    if candle_box_breakout:
        confirm_score += 2.0
        reasons.append("box_breakout")

    if confirm_score == 0:
        reason = "no_confirmation"
    else:
        reason = "+".join(reasons)

    # 限制最大分数
    confirm_score = min(confirm_score, 10.0)

    return {
        "candle_position_zone": position_zone,
        "candle_low_position_pct": low_position_pct,
        "candle_close_location": close_location,
        "candle_volume_confirm": volume_confirm,
        "candle_volume_ratio_20": volume_ratio_20,
        "candle_upper_shadow_pct": upper_shadow_pct,
        "candle_long_upper_shadow_risk": long_upper_shadow_risk,
        "candle_bullish_reversal": bool(candle_bullish_reversal),
        "candle_bullish_continuation": bool(candle_bullish_continuation),
        "candle_box_breakout": bool(candle_box_breakout),
        "candle_confirm_score": float(confirm_score),
        "candle_confirm_reason": reason,
    }
