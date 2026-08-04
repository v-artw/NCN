"""Edge Scout 数据类定义。

包含：
- EdgeScoutResult: 单只股票扫描结果
- Tier: 候选分层 (A/B/C)
- ScoringResult: 评分对象
- AdmissionResult: 数据准入结果
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class Tier:
    """候选分层。"""

    code: str
    as_of: date
    tier: str  # "production", "watchlist", "near_miss"
    edge_score: float
    base_quality_score: float
    timing_score: float
    risk_score: float
    rejection_warning: str | None = None
    limitations: tuple[str, ...] = ()


@dataclass(frozen=True)
class EdgeScoutResult:
    """单只股票 Edge Scout 扫描结果。"""

    code: str
    as_of: date
    status: str  # "admitted", "rejected", "insufficient_data"
    admission_error_code: str | None = None
    admission_detail: str | None = None
    hard_gate_details: tuple[str, ...] = ()  # P0-7: 具体的硬门槛失败原因列表
    first_date: date | None = None
    last_date: date | None = None
    base_quality_score: float | None = None
    timing_score: float | None = None
    risk_score: float | None = None
    t1_confirmed: bool | None = None
    t1_reason: str | None = None
    t_day_setup_valid: bool | None = None
    t_day_setup_reason: str | None = None
    t_day_patterns: tuple[str, ...] = ()
    t_day_setup_failed_conditions: tuple[str, ...] = ()
    price_volume_confirmed: bool | None = None
    price_volume_confirmation_reason: str | None = None
    price_volume_ratio: float | None = None
    valid_setup_confirmed: bool | None = None
    valid_setup_confirmation_reason: str | None = None
    industry: str | None = None
    research_close: float | None = None
    pct_chg: float | None = None
    ret_5d: float | None = None
    amount_cny: float | None = None
    turn: float | None = None
    volume_ratio_20: float | None = None
    pmk_trend_confirmed: bool | None = None
    pmk_trend_reason: str | None = None
    pmk_shape_score: float | None = None
    pmk_shape_pattern: str | None = None
    pmk_rsi: float | None = None
    pmk_atr_squeeze: bool | None = None
    pmk_macd_confirm: bool | None = None
    pmk_volume_breakout: bool | None = None
    pmk_feature_bonus: float | None = None
    candle_position_zone: str | None = None
    candle_low_position_pct: float | None = None
    candle_close_location: float | None = None
    candle_volume_confirm: bool | None = None
    candle_volume_ratio_20: float | None = None
    candle_upper_shadow_pct: float | None = None
    candle_long_upper_shadow_risk: bool | None = None
    candle_bullish_reversal: bool | None = None
    candle_bullish_continuation: bool | None = None
    candle_box_breakout: bool | None = None
    candle_confirm_score: float | None = None
    candle_confirm_reason: str | None = None
    start_signal_count: int | None = None
    start_signals: tuple[str, ...] = ()
    start_signal_reasons: tuple[str, ...] = ()
    mhpg_buy: bool | None = None
    dxbd_up: bool | None = None
    mfk4_triggered: bool | None = None
    gding_up: bool | None = None
    dingdi_safe_up: bool | None = None
    futu_bonus: float | None = None
    futu_status_codes: tuple[str, ...] = ()
    futu_risk_codes: tuple[str, ...] = ()
    cnstock_base_score: float | None = None
    cnstock_pool: str | None = None
    cnstock_pool_eligible: bool | None = None
    cnstock_pool_rejection_reasons: tuple[str, ...] = ()
    cnstock_discovery_rank: float | None = None
    cnstock_discovery_rank_breakdown: str | None = None
    discovery_tier: str | None = None
    discovery_eligible: bool | None = None
    discovery_rejection_reasons: tuple[str, ...] = ()
    discovery_score: float | None = None
    discovery_score_breakdown: str | None = None
    tier: Tier | None = None
    limitations: tuple[str, ...] = ()
    reference_prices: "ReferencePrices | None" = None


@dataclass(frozen=True)
class ScoringResult:
    """综合评分对象。"""

    edge_score: float
    base_quality_score: float
    timing_score: float
    risk_score: float
    hard_gate_failures: tuple[str, ...] = ()


@dataclass(frozen=True)
class AdmissionResult:
    """数据准入结果。"""

    code: str
    status: str  # "strict_admitted", "research_window_admitted", "rejected"
    records: tuple[dict[str, Any], ...] = ()
    formal_error_code: str | None = None
    detail: str = ""
    dropped_prefix_row_count: int = 0


@dataclass(frozen=True)
class EdgeScoutScanSummary:
    """全市场扫描摘要（含 P0-7 数量守恒审计信息）。"""

    schema_version: str
    status: str
    run_id: str
    as_of: date
    input_code_count: int
    admitted_count: int
    rejected_count: int
    production_candidate_count: int
    watchlist_count: int
    near_miss_count: int
    quality_error_counts: dict[str, int] = field(default_factory=dict)
    hard_gate_rejection_counts: dict[str, int] = field(default_factory=dict)
    hard_gate_rejected_count: int = 0
    data_rejected_count: int = 0
    no_records_before_as_of_count: int = 0
    scored_count: int = 0
    unexpected_error_count: int = 0
    unclassified_count: int = 0
    no_tier_reason_counts: dict[str, int] = field(default_factory=dict)
    tier_counts_before_truncation: dict[str, int] = field(default_factory=dict)
    tier_counts_after_truncation: dict[str, int] = field(default_factory=dict)
    discovery_tier_counts: dict[str, int] = field(default_factory=dict)
    cnstock_pool_counts: dict[str, int] = field(default_factory=dict)
    quantity_conservation_valid: bool = False
    admission_quantity_conservation_valid: bool = False
    scan_quantity_conservation_valid: bool = False
    tier_quantity_conservation_valid: bool = False
    boundaries: dict[str, bool] = field(default_factory=dict)
    inputs: dict[str, str] = field(default_factory=dict)
    limitations: tuple[str, ...] = ()
    freshness_evidence: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TDaySetupResult:
    """T-day setup decision computed without T+1 or later records."""

    valid: bool
    reason: str
    matched_patterns: tuple[str, ...] = ()
    failed_conditions: tuple[str, ...] = ()


@dataclass(frozen=True)
class ReferencePricePublicationRow:
    """Explicit setup/confirmation state for one published reference price."""

    tier: Tier
    prices: "ReferencePrices"
    t_day_setup_valid: bool
    price_volume_confirmed: bool
    valid_setup_confirmed: bool
    discovery_tier: str = "general_observation"
    discovery_score: float = 0.0
    start_signal_count: int = 0
