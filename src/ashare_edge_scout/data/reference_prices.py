"""研究参考价计算。

基于 T 日信号链（signal_high / signal_low / ATR14）与 V1 风控规则，
推算出参考买入价、参考止损价和参考止盈价。

边界声明：
- 输出仅为研究近似参考价，不是可执行价格、真实成交价或投资建议。
- T+1 价格/量能研究确认后只进入 T+2 人工观察阶段，不代表可成交或应入场；
  本模块以 signal_high 作为 T 日研究触发参考，不是 T+2 开盘价。
- 涨跌停、停牌、滑点与费用未纳入本近似计算。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from math import isfinite
from typing import Any, Mapping, Sequence

from ..pmkf_mkf.features import atr


@dataclass(frozen=True)
class ReferencePrices:
    """单只股票的研究参考价（research-only，非执行价）。"""

    code: str
    as_of: date
    close_now: float
    signal_high: float
    signal_low: float
    atr14: float
    buy_reference: float
    stop_reference: float
    partial_take_profit_reference: float
    take_profit_reference: float
    risk_distance_pct: float
    methodology: str = (
        "buy=signal_high; stop=min(signal_low-buffer*atr14, buy-stop_atr_multiple*atr14); "
        "tp1=buy+1.5R; tp2=buy+2.0R; research-only approximation"
    )


def compute_reference_prices(
    code: str,
    records: Sequence[Mapping[str, Any]],
    config: Mapping[str, Any],
    *,
    as_of: date,
) -> ReferencePrices | None:
    """从 T 日截断记录计算研究参考价。

    参数：
      code: 股票代码
      records: 截断到 as_of 的日线记录（含 T 日）
      config: 策略配置
      as_of: 信号日

    返回：
      参考价对象，或 None（数据不足 / ATR 无效 / 无法计算）
    """

    if not records:
        return None

    try:
        high = [float(r.get("high", 0)) for r in records]
        low = [float(r.get("low", 0)) for r in records]
        close = [float(r.get("close", 0)) for r in records]
    except (TypeError, ValueError):
        return None

    if not high or not low or not close:
        return None

    signal_high = float(high[-1])
    signal_low = float(low[-1])
    close_now = float(close[-1])

    if signal_high <= 0 or signal_low <= 0 or close_now <= 0:
        return None

    atr_values = atr(high, low, close, 14)
    if len(atr_values) == 0 or not isfinite(atr_values[-1]) or atr_values[-1] <= 0:
        return None
    atr14 = float(atr_values[-1])

    risk_cfg = config.get("risk", {}) if isinstance(config, Mapping) else {}
    stop_atr_multiple = float(risk_cfg.get("stop_atr_multiple", 1.5))
    stop_signal_low_atr_buffer = float(risk_cfg.get("stop_signal_low_atr_buffer", 0.10))
    partial_take_profit_r = float(risk_cfg.get("partial_take_profit_r", 1.5))
    final_take_profit_r = float(risk_cfg.get("final_take_profit_r", 2.0))

    buy_reference = signal_high
    stop_reference = min(
        signal_low - stop_signal_low_atr_buffer * atr14,
        buy_reference - stop_atr_multiple * atr14,
    )

    risk_per_share = buy_reference - stop_reference
    if risk_per_share <= 0:
        return None

    return ReferencePrices(
        code=code,
        as_of=as_of,
        close_now=close_now,
        signal_high=signal_high,
        signal_low=signal_low,
        atr14=atr14,
        buy_reference=buy_reference,
        stop_reference=stop_reference,
        partial_take_profit_reference=buy_reference + partial_take_profit_r * risk_per_share,
        take_profit_reference=buy_reference + final_take_profit_r * risk_per_share,
        risk_distance_pct=risk_per_share / buy_reference,
    )


def within_v1_risk_range(
    risk_distance_pct: float,
    config: Mapping[str, Any],
) -> bool:
    """判断参考风险距是否落在 V1 研究展示范围 [risk_distance_min, risk_distance_max]。

    默认区间 [0.025, 0.060]（对应 V1 hard_gates risk_distance_min/max）。
    超出该区间的研究参考价仅供观察，不满足 V1 研究展示约束，
    不应进入 TOP 参考价展示表。
    """

    hard_gates = config.get("hard_gates", {}) if isinstance(config, Mapping) else {}
    min_risk = float(hard_gates.get("risk_distance_min", 0.025))
    max_risk = float(hard_gates.get("risk_distance_max", 0.060))
    return min_risk <= risk_distance_pct <= max_risk
