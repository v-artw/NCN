"""Read-only candidate scoring, universe gates, and research tiers.

The three score components are contribution points with nominal caps of
45/35/20. V1 adds them directly; it does not apply a second set of weights.
Several originally reserved inputs are unavailable, so each component's
implemented evidence is documented explicitly below.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Mapping, Sequence

from .contracts import EdgeScoutResult, ScoringResult, Tier
from .candle_confirm import compute_candle_confirmation_features
from .pmkf import apply_pmkf, compute_pmkf_slope
from .pmk_features import compute_pmk_features


def compute_base_quality_score(
    pmk_features: dict[str, Any],
    industry: str | None = None,
    alpha_score: float = 0.0,
) -> float:
    """Compute implemented base-quality evidence within the 0-45 contract.

    子项：
      - PMKF 趋势质量：10 分
      - 相对强度：8 分
      - 波动控制：6 分
      - 数据质量：2 分

    参数：
      pmk_features: PMK 特征字典
      industry: 行业（可选）
      alpha_score: Alpha 分数（MVP 暂不使用）

    返回：
      基础质量分数（0-45）
    """

    score = 0.0

    # PMKF 趋势质量（10 分）
    if pmk_features.get("pmk_trend_confirmed"):
        score += 10.0
        if pmk_features.get("pmk_shape_pattern") in ("Steady Climber", "Explosive Breakout", "New High"):
            score += 3.0  # 额外加分

    # 相对强度（8 分）
    if pmk_features.get("pmk_rsi", 50) > 60:
        score += 8.0
    elif pmk_features.get("pmk_rsi", 50) > 50:
        score += 4.0

    # 波动控制（6 分）
    if pmk_features.get("pmk_atr_squeeze"):
        score += 6.0

    # 数据质量（2 分）
    if pmk_features.get("pmk_trend_confirmed"):
        score += 2.0

    return min(score, 45.0)


def compute_timing_score(
    candle_features: dict[str, Any],
    candle_patterns: dict[str, list[bool]] | None = None,
    t1_observation: Any = None,
    futu_bonus: float = 0.0,
) -> tuple[float, str]:
    """计算时机分数（0-35 分）。

    子项：
      - V1 蜡烛图形态：8 分
      - 趋势回踩位置：7 分
      - T+1 价格确认：8 分
      - T+1 量能确认：5 分
      - PMK/candle confirmation：4 分
      - 收盘位置与上影风险：3 分

    参数：
      candle_features: 蜡烛确认特征字典
      candle_patterns: V1 蜡烛图形态检测结果（可选）
      t1_observation: T+1 观察结果（可选）

    返回：
      (分数，详细分解字符串)
    """

    score = 0.0
    breakdown_parts: list[str] = []

    # V1 蜡烛图形态（8 分）
    if candle_patterns is not None:
        matched_patterns = [
            name for name, values in candle_patterns.items() if values and values[-1]
        ]
        if matched_patterns:
            score += 8.0
            breakdown_parts.append(f"patterns={','.join(matched_patterns)}")

    # 趋势回踩位置（7 分）
    if candle_features.get("candle_position_zone") in ("low", "mid_low"):
        score += 7.0
        breakdown_parts.append("pullback_position")

    # PMK/candle confirmation（4 分）
    if candle_features.get("candle_confirm_score", 0) >= 3.0:
        score += 4.0
        breakdown_parts.append(f"confirm_score={candle_features['candle_confirm_score']:.1f}")

    # 收盘位置与上影风险（3 分）
    close_location = candle_features.get("candle_close_location", 0.5)
    if 0.4 <= close_location <= 0.7:
        score += 3.0
        breakdown_parts.append("good_close_location")

    if bool(getattr(t1_observation, "confirmed", False)):
        score += 13.0
        breakdown_parts.append("t1_price_volume_confirmed")

    bounded_futu_bonus = min(max(float(futu_bonus), 0.0), 6.0)
    if bounded_futu_bonus:
        score += bounded_futu_bonus
        breakdown_parts.append(f"futu={bounded_futu_bonus:.1f}")

    return min(score, 35.0), ";".join(breakdown_parts)


def compute_risk_score(
    signal_high: float,
    signal_low: float,
    atr14: float,
    close_now: float,
    min_risk_distance: float = 0.025,
    max_risk_distance: float = 0.060,
    risk_codes: Sequence[str] = (),
) -> tuple[float, str]:
    """Compute implemented risk-quality evidence within the 0-20 contract.

    子项：
      - 止损距离合理：6 分（2.5%-6.0% 最优）
      - ATR 风险：4 分
      - 数据来源可信度：2 分

    参数：
      signal_high: 信号高点
      signal_low: 信号低点
      atr14: 14 日 ATR
      close_now: 当前收盘价
      min_risk_distance: 最小风险距离
      max_risk_distance: 最大风险距离

    返回：
      (分数，详细分解字符串)
    """

    score = 0.0
    breakdown_parts: list[str] = []

    # 止损距离合理（6 分）
    if signal_high > 0 and signal_low > 0:
        risk_distance = (signal_high - signal_low) / signal_high
        if min_risk_distance <= risk_distance <= max_risk_distance:
            score += 6.0
            breakdown_parts.append(f"risk_distance={risk_distance:.4f}")
        elif risk_distance < min_risk_distance:
            score += 2.0  # 部分加分
            breakdown_parts.append(f"risk_distance_too_tight={risk_distance:.4f}")
        else:
            score += 0.0
            breakdown_parts.append(f"risk_distance_too_wide={risk_distance:.4f}")

    # ATR 风险（4 分）
    if atr14 > 0 and close_now > 0:
        atr_pct = atr14 / close_now
        if 0.01 <= atr_pct <= 0.05:
            score += 4.0
            breakdown_parts.append(f"atr_pct={atr_pct:.4f}")

    # 数据来源可信度（2 分）
    score += 2.0  # MVP 假设数据可信

    risk_penalties = {
        "clear_signal": 6.0,
        "mhpg_outflow": 4.0,
        "bear_divergence": 3.0,
        "overbought_risk": 3.0,
        "high_position_risk": 2.0,
        "bearish_candle_risk": 4.0,
    }
    applied_risks = sorted(set(risk_codes) & risk_penalties.keys())
    if applied_risks:
        penalty = min(sum(risk_penalties[code] for code in applied_risks), 10.0)
        score -= penalty
        breakdown_parts.append(f"evidence_risk=-{penalty:.1f}({','.join(applied_risks)})")

    return min(max(score, 0.0), 20.0), ";".join(breakdown_parts)


def compute_edge_score(
    base_quality_score: float,
    timing_score: float,
    risk_score: float,
) -> float:
    """计算综合边缘分数。

    规格：分项本身就是 45/35/20 的贡献分，直接加和即为 0–100 的 edge_score。
    不再使用 0.45/0.35/0.20 二次加权，否则理论最大值为 45*0.45+35*0.35+20*0.20=36.5，
    低于 classify_tier 的 production 阈值 70，数学上 A 级不可达。

    参数：
      base_quality_score: 基础质量分数（0-45）
      timing_score: 时机分数（0-35）
      risk_score: 风险分数（0-20）

    返回：
      综合边缘分数（0-100）
    """

    return base_quality_score + timing_score + risk_score


def compute_discovery_score(
    edge_score: float,
    pmk_features: Mapping[str, Any],
    candle_features: Mapping[str, Any],
    start_signal_count: int,
    pct_chg: float,
    ret_5d: float,
    volume_ratio: float,
) -> tuple[float, str]:
    """CNstock-inspired soft ranking for research discovery, never production eligibility."""

    score = float(edge_score)
    parts = [f"edge={edge_score:.2f}"]
    start_bonus = float(start_signal_count) * 8.0
    score += start_bonus
    parts.append(f"start={start_bonus:.2f}")

    candle_score = float(candle_features.get("candle_confirm_score", 0.0))
    candle_bonus = candle_score * 1.2
    score += candle_bonus
    parts.append(f"candle={candle_bonus:.2f}")

    close_location = float(candle_features.get("candle_close_location", 0.0))
    position = float(candle_features.get("candle_low_position_pct", 1.0))
    pmk_bonus = float(pmk_features.get("pmk_feature_bonus", 0.0))
    shape_bonus = float(pmk_features.get("pmk_shape_score", 0.0)) / 100.0 * 3.0
    contextual = close_location * 3.0 + max(0.0, 0.75 - position) * 6.0 + pmk_bonus + shape_bonus
    score += contextual
    parts.append(f"context={contextual:.2f}")

    penalties = (
        float(candle_features.get("candle_upper_shadow_pct", 0.0)) * 5.0
        + max(0.0, position - 0.60) * 8.0
        + max(0.0, ret_5d - 8.0) * 0.8
        + max(0.0, pct_chg - 5.0)
        + max(0.0, volume_ratio - 3.5)
    )
    score -= penalties
    parts.append(f"penalty=-{penalties:.2f}")
    return round(score, 6), ";".join(parts)


def classify_discovery_tier(start_signal_count: int) -> str:
    """Research-only lifecycle tier modeled after CNstock's 4/5, 3/5 and 2/5 pools."""

    if start_signal_count >= 4:
        return "strong_start"
    if start_signal_count == 3:
        return "profit_shadow"
    if start_signal_count == 2:
        return "early_low_position"
    return "general_observation"


def classify_tier(
    edge_score: float,
    t1_confirmed: bool,
    hard_gate_failures: tuple[str, ...] = (),
    *,
    production_enabled: bool = False,
) -> str:
    """分类候选层级。

    规格：
      A 级：edge_score >= 70 且 T+1 确认为真
      B 级：edge_score >= 50
      C 级：edge_score < 50（near-miss）

    production tier 在 V1 中显式关闭。即使分数达到阈值，本函数也拒绝
    production_enabled=True；未来启用必须通过新的版本化策略实现。

    参数：
      edge_score: 综合边缘分数
      t1_confirmed: 是否 T+1 确认为真
      hard_gate_failures: 硬门槛失败列表

    返回：
      层级字符串（"production", "watchlist", "near_miss"）
    """

    if production_enabled:
        raise ValueError("Edge Scout V1 production tier is disabled")
    if edge_score >= 50:
        return "watchlist"
    return "near_miss"


def apply_hard_gates(
    code: str,
    records: Sequence[Mapping[str, Any]],
    config: Mapping[str, Any],
) -> tuple[bool, list[str]]:
    """应用硬门槛检查。

    参数：
      code: 股票代码
      records: 日线记录序列
      config: 配置字典

    返回：
      (通过检查，失败原因列表)
    """

    failures: list[str] = []

    universe = config.get("universe", {})
    prefixes = tuple(
        str(prefix)
        for prefix in universe.get(
            "include_prefixes",
            ("sh.600", "sh.601", "sh.603", "sh.605", "sz.000", "sz.001", "sz.002", "sz.003"),
        )
    )

    if not prefixes or not code.startswith(prefixes):
        failures.append("not_main_board_a_share")

    # Point-in-time status: historical ST periods must not permanently reject a recovered stock.
    if bool(universe.get("exclude_st", True)) and records and str(records[-1].get("isST", "0")) == "1":
        failures.append("is_st_stock")

    minimum_listing_days = int(universe.get("min_listing_days", 252))
    if len(records) < minimum_listing_days:
        failures.append("insufficient_listing_days")

    if records:
        try:
            latest = records[-1]
            close = float(latest.get("close", 0))
            if close < float(universe.get("min_close_cny", 5.0)):
                failures.append("close_too_low")
            if close > float(universe.get("max_close_cny", 80.0)):
                failures.append("close_too_high")

            if bool(universe.get("block_suspensions", True)) and str(latest.get("tradestatus", "0")) != "1":
                failures.append("suspended_on_signal_date")

            recent_60 = records[-60:]
            trading_days_60 = sum(str(record.get("tradestatus", "0")) == "1" for record in recent_60)
            if trading_days_60 < int(universe.get("min_trading_days_60", 55)):
                failures.append("insufficient_trading_days_60")

            minimum_adv20 = float(universe.get("min_adv20_cny", 0.0))
            if minimum_adv20 > 0:
                recent_amounts = [float(record.get("amount", 0) or 0) for record in records[-20:]]
                if len(recent_amounts) < 20:
                    failures.append("insufficient_adv20_history")
                elif sum(recent_amounts) / 20.0 < minimum_adv20:
                    failures.append("adv20_too_low")

            preclose = float(latest.get("preclose", 0) or 0)
            if (
                bool(universe.get("block_limit_up_entries", True))
                and preclose > 0
                and close / preclose - 1.0 >= 0.095
            ):
                failures.append("near_limit_up_on_signal_date")
        except (ValueError, TypeError):
            failures.append("invalid_universe_gate_value")

    return len(failures) == 0, failures


def score_single_stock(
    code: str,
    records: Sequence[Mapping[str, Any]],
    config: Mapping[str, Any],
    candle_patterns: dict[str, list[bool]] | None = None,
    t1_observation: Any = None,
    futu_bonus: float = 0.0,
    futu_risk_codes: Sequence[str] = (),
) -> tuple[ScoringResult, str | None]:
    """对单只股票计算综合评分。

    参数：
      code: 股票代码
      records: 日线记录序列
      config: 配置字典
      candle_patterns: V1 蜡烛图形态检测结果（可选）
      t1_observation: T+1 观察结果（可选）

    返回：
      (评分结果，拒绝原因)
    """

    # 应用硬门槛
    gates_passed, gate_failures = apply_hard_gates(code, records, config)
    if not gates_passed:
        return (
            ScoringResult(
                edge_score=0.0,
                base_quality_score=0.0,
                timing_score=0.0,
                risk_score=0.0,
                hard_gate_failures=tuple(gate_failures),
            ),
            "hard_gate_failure",
        )

    # 计算 PMK 特征
    if len(records) >= 20:
        open_ = [float(r.get("open", 0)) for r in records]
        high = [float(r.get("high", 0)) for r in records]
        low = [float(r.get("low", 0)) for r in records]
        close = [float(r.get("close", 0)) for r in records]
        volume = [float(r.get("volume", 0)) for r in records]

        pmk_features = compute_pmk_features(open_, high, low, close, volume)
    else:
        pmk_features = {}

    # 计算蜡烛确认特征
    if len(records) >= 20:
        candle_features = compute_candle_confirmation_features(
            open_=open_,
            high=high,
            low=low,
            close=close,
            volume=volume,
        )
    else:
        candle_features = {}

    # 计算各分数
    base_quality = compute_base_quality_score(pmk_features)
    timing, timing_breakdown = compute_timing_score(
        candle_features,
        candle_patterns,
        t1_observation,
        futu_bonus,
    )

    # 使用真实 ATR14 而非布尔值替代（P0-5 修复）
    _atr14_raw = pmk_features.get("pmk_atr14", None)
    if _atr14_raw is None or not isinstance(_atr14_raw, (int, float)) or _atr14_raw <= 0:
        # 回退：使用 low[-1] 到 high[-1] 的简单范围作为近似
        _atr14_real = max(float(high[-1] - low[-1]) if high and low else 0.0, 1e-6)
    else:
        _atr14_real = float(_atr14_raw)

    risk, risk_breakdown = compute_risk_score(
        signal_high=float(high[-1]) if high else 0,
        signal_low=float(low[-1]) if low else 0,
        atr14=_atr14_real,
        close_now=float(close[-1]) if close else 0,
        risk_codes=futu_risk_codes,
    )

    edge = compute_edge_score(base_quality, timing, risk)

    return (
        ScoringResult(
            edge_score=edge,
            base_quality_score=base_quality,
            timing_score=timing,
            risk_score=risk,
        ),
        None,
    )
