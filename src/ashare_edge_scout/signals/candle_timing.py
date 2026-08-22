"""Standalone Edge Scout candle timing and confirmation wrappers."""

from __future__ import annotations

from datetime import date
from typing import Any, Mapping, Sequence

from .candles import (
    detect_bullish_patterns_from_candle_rules,
    CandleRuleSet,
)
from .confirmations import (
    BullishPattern,
    ConfirmationRule,
    ConfirmationResult,
    confirm_bullish_pattern_t1,
)
from .entry_plan import (
    plan_t2_open_entry,
    EntryPlan,
)
from .indicators import simple_returns, sma

from ..data.contracts import TDaySetupResult


def detect_candle_patterns(
    records: Sequence[Mapping[str, Any]],
    candle_rules: CandleRuleSet,
) -> dict[str, list[bool]]:
    """检测看涨蜡烛图形态。

    复用 V1 的 detect_bullish_patterns_from_candle_rules。

    参数：
      records: 日线记录序列
      candle_rules: 蜡烛图规则集

    返回：
      形态检测结果字典
    """

    return detect_bullish_patterns_from_candle_rules(records, candle_rules)


def observe_t1(
    *,
    records: Sequence[Mapping[str, Any]],
    dates: Sequence[date],
    as_of_index: int,
    signal_high: float,
    volume_ma20_at_signal: float | None,
    min_volume_ratio: float,
) -> ConfirmationResult:
    """观察 T+1 确认。

    复用 V1 的 confirm_bullish_pattern_t1。
    当 T+1 日无记录时，返回 ``confirmed=False`` 且 reason 为 "missing_t1_bar"。

    参数：
      records: 日线记录序列（截断到 as_of）
      dates: 日期序列（仅用于兼容，实际从 records 提取）
      as_of_index: 信号日索引
      signal_high: 信号高点
      volume_ma20_at_signal: 信号日 20 日成交量均线
      min_volume_ratio: 最小成交量比率

    返回：
      V1 ConfirmationResult（containing confirmed flag）
    """

    try:
        rule = ConfirmationRule(
            volume_ma_window=20,
            min_volume_ratio=float(min_volume_ratio),
            require_close_above_pattern_high=True,
            require_bullish_close=True,
        )

        pattern = BullishPattern(
            index=as_of_index,
            name="edge_scout_t1_check",
        )

        return confirm_bullish_pattern_t1(
            ohlcv={
                "open": [float(r["open"]) for r in records],
                "high": [float(r["high"]) for r in records],
                "low": [float(r["low"]) for r in records],
                "close": [float(r["close"]) for r in records],
                "volume": [float(r.get("volume", 0)) for r in records],
            },
            pattern=pattern,
            rule=rule,
        )

    except Exception:
        return ConfirmationResult(
            pattern_index=as_of_index,
            confirmation_index=None,
            pattern_name="edge_scout_t1_check",
            confirmed=False,
            reason="observe_t1_error",
            volume_ratio=None,
        )


def evaluate_t_day_setup(
    records: Sequence[Mapping[str, Any]],
    config: Mapping[str, Any],
    candle_patterns: Mapping[str, Sequence[bool]],
) -> TDaySetupResult:
    """Evaluate the configured trend, pullback and candle setup using T-only data."""

    trend = config.get("setup", {}).get("trend", {})
    pullback = config.get("setup", {}).get("pullback", {})
    fast_ma = int(trend.get("fast_ma", 20))
    slow_ma = int(trend.get("slow_ma", 60))
    slope_lookback = int(trend.get("ma_slope_lookback", 5))
    high_lookback = int(pullback.get("high_lookback", 10))
    minimum_rows = max(slow_ma, fast_ma + slope_lookback, 21)
    matched_patterns = tuple(
        name for name, values in candle_patterns.items() if values and bool(values[-1])
    )
    if len(records) < minimum_rows:
        return TDaySetupResult(
            valid=False,
            reason="insufficient_t_history",
            matched_patterns=matched_patterns,
            failed_conditions=("insufficient_t_history",),
        )

    highs = [float(record["high"]) for record in records]
    lows = [float(record["low"]) for record in records]
    closes = [float(record["close"]) for record in records]
    ma_fast = sma(closes, fast_ma)
    ma_slow = sma(closes, slow_ma)
    returns_20 = simple_returns(closes, 20)
    index = len(records) - 1
    fast_now = ma_fast[index]
    fast_past = ma_fast[index - slope_lookback]
    slow_now = ma_slow[index]
    return_20 = returns_20[index]
    close_now = closes[index]
    highest = max(highs[-high_lookback:])
    lowest = min(lows[-high_lookback:])
    drawdown = (highest - close_now) / highest
    low_to_slow_ma = lowest / slow_now if slow_now else None

    failures: list[str] = []
    if not (fast_now is not None and slow_now is not None and close_now > fast_now > slow_now):
        failures.append("close_not_above_ma20_above_ma60")
    if not (fast_now is not None and fast_past is not None and fast_now >= fast_past):
        failures.append("ma20_slope_negative")
    if not (
        return_20 is not None
        and float(trend.get("min_return_20d", 0.03))
        <= return_20
        <= float(trend.get("max_return_20d", 0.30))
    ):
        failures.append("return_20d_out_of_range")
    if not (
        float(pullback.get("min_drawdown_from_high", 0.03))
        <= drawdown
        <= float(pullback.get("max_drawdown_from_high", 0.10))
    ):
        failures.append("pullback_drawdown_out_of_range")
    if not (
        low_to_slow_ma is not None
        and low_to_slow_ma >= float(pullback.get("min_low_to_ma60_ratio", 0.98))
    ):
        failures.append("pullback_below_ma60_floor")
    if not matched_patterns:
        failures.append("no_enabled_bullish_pattern_on_t")

    return TDaySetupResult(
        valid=not failures,
        reason="valid_setup" if not failures else "setup_conditions_failed",
        matched_patterns=matched_patterns,
        failed_conditions=tuple(failures),
    )


def compute_t2_entry_plan(
    *,
    records: Sequence[Mapping[str, Any]],
    confirmation: ConfirmationResult,
) -> EntryPlan:
    """计算 T+2 开盘入场计划。

    复用 V1 的 plan_t2_open_entry。

    参数：
      code: 股票代码
      as_of: 信号日
      signal_high: 信号高点
      signal_low: 信号低点
      atr14: 14 日 ATR
      volume_ma20: 20 日成交量均线
      t1_confirmation: T+1 确认结果
      risk_per_trade_cny: 每笔风险金额
      max_position_notional_cny: 最大持仓名义金额
      cash_reserve_cny: 现金储备
      min_position_notional_cny: 最小持仓名义金额
      stop_atr_multiple: 止损 ATR 倍数
      stop_signal_low_atr_buffer: 止损信号低点 ATR 缓冲
      planned_risk_cny: 计划风险金额
      records: 日线记录序列（T 日数据，用于获取 OHLCV）

    返回：
      入场计划或 None（如果无法生成）
    """

    return plan_t2_open_entry(
        ohlcv={
            "open": [float(r["open"]) for r in records],
            "high": [float(r["high"]) for r in records],
            "low": [float(r["low"]) for r in records],
            "close": [float(r["close"]) for r in records],
            "volume": [float(r.get("volume", 0)) for r in records],
        },
        confirmation=confirmation,
    )


def has_bullish_pattern(
    records: Sequence[Mapping[str, Any]],
    candle_rules: CandleRuleSet,
) -> bool:
    """检查是否有看涨形态。

    包装 V1 的 detect_bullish_patterns_from_candle_rules。

    参数：
      records: 日线记录序列
      candle_rules: 蜡烛图规则集

    返回：
      是否有看涨形态
    """

    patterns = detect_bullish_patterns_from_candle_rules(records, candle_rules)
    return any(any(values) for values in patterns.values())
