"""Full-universe rolling next-day validation primitives.

Candidates are computed with data visible through origin date T. Outcomes are
anchored on the next tradable row D and compare D close directly with T close.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
import pandas as pd

from .signals.candles import detect_bearish_risk_patterns, detect_bullish_patterns
from .research_futu_ranking import CANDIDATES as FUTU_RANKING_CANDIDATES
from .research_futu_ranking import candidate_masks_from_values, tradable_indicator_values
from .research_precision70 import (
    nonoverlapping_origins,
    production_gate_mask,
)
from .research_v2 import summarize_counts

SCHEMA_VERSION = "ncn_next_trading_day_direction_v2"
STUDY_NAME = "full_universe_rolling_next_day_validation"
DEFAULT_START_DATE = "1900-01-01"
MIN_BASELINE_ROWS = 150


@dataclass(frozen=True)
class CandidateSpec:
    name: str
    family: str
    direction: str
    implementability: str
    source: str
    primary_selectable: bool
    description: str

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


FUTU_BASE_SPECS = tuple(
    CandidateSpec(name, "futu", "bullish", "objective", "futu.md", True, "Frozen Futu family trigger")
    for name in FUTU_RANKING_CANDIDATES
)

FUTU_EXPANDED_SPECS = (
    CandidateSpec("alphagpt_cross_001", "futu", "bullish", "objective", "futu.md", True, "ALPHAGPT factor crosses above 0.01"),
    CandidateSpec("dxbd_surge_cross_60", "futu", "annotation", "objective", "futu.md", False, "DXBD crosses above 60"),
    CandidateSpec("dxbd_clear_cross_78", "futu", "risk", "objective", "futu.md", False, "DXBD crosses above 78"),
    CandidateSpec("dxbd_replenish_cross_minus60", "futu", "bullish", "objective", "futu.md", True, "DXBD crosses above -60"),
    CandidateSpec("dxbd_accumulate_cross_minus80", "futu", "bullish", "objective", "futu.md", True, "DXBD crosses above -80"),
    CandidateSpec("ribbon1_strict_sell", "futu", "risk", "objective", "futu.md", False, "Ribbon crosses below signal in high zone"),
    CandidateSpec("kdj_trend_pro_sell", "futu", "risk", "objective", "futu.md", False, "KDJ K crosses below D while below EMA60"),
    CandidateSpec("mkf_bullcluster", "futu", "annotation", "objective", "futu.md", False, "MkF momentum/inter/near all in low zone"),
    CandidateSpec("mkf_bearcluster", "futu", "risk", "objective", "futu.md", False, "MkF momentum/inter/near all in high zone"),
    CandidateSpec("shengbei_long_state", "futu", "annotation", "objective", "futu.md", False, "Shengbei state is long"),
    CandidateSpec("shengbei_short_flip", "futu", "risk", "objective", "futu.md", False, "Shengbei flips from long to short"),
    CandidateSpec("gding_fast_cross_down", "futu", "risk", "objective", "futu.md", False, "GDING fast line crosses below signal"),
    CandidateSpec("cpgw_main_cross_down_long", "futu", "risk", "objective", "futu.md", False, "CPGW main line crosses below long line"),
    CandidateSpec("smc_bull_bos", "futu", "bullish", "objective", "futu.md", True, "SMC close crosses above prior 30-row swing high"),
    CandidateSpec("smc_bull_choch", "futu", "bullish", "objective", "futu.md", True, "SMC EMA20/EMA50 bullish change with structure break"),
    CandidateSpec("smc_medium_buy", "futu", "bullish", "objective", "futu.md", True, "SMC bullish FVG aligned with EMA20 above EMA50"),
    CandidateSpec("smc_touch_liquidity_low", "futu", "annotation", "objective", "futu.md", False, "SMC touches a new 10-row liquidity low"),
)

FUTU_EXCLUDED_SPECS = (
    CandidateSpec("unnamed_kd_block", "futu", "annotation", "underdefined", "futu.md", False, "Excluded: P1/P2/P3 parameters are unspecified"),
    CandidateSpec("kdq_prose_strategy", "futu", "annotation", "underdefined", "futu.md", False, "Excluded: prose stop/second-cross/trend-line mechanics are not deterministic"),
)

CANDLE_SPECS = (
    CandidateSpec("candle_hammer", "candlestick", "bullish", "objective", "Japanese Candlestick Charting Techniques", True, "Existing hammer detector"),
    CandidateSpec("candle_bullish_engulfing", "candlestick", "bullish", "objective", "Japanese Candlestick Charting Techniques", True, "Existing bullish engulfing detector"),
    CandidateSpec("candle_piercing", "candlestick", "bullish", "objective", "Japanese Candlestick Charting Techniques", True, "Existing piercing detector"),
    CandidateSpec("candle_morning_star", "candlestick", "bullish", "objective", "Japanese Candlestick Charting Techniques", True, "Existing morning star detector"),
    CandidateSpec("candle_inverted_hammer", "candlestick", "bullish", "objective", "Japanese Candlestick Charting Techniques", True, "Project-defined inverted hammer geometry after decline"),
    CandidateSpec("candle_doji", "candlestick", "annotation", "objective", "Japanese Candlestick Charting Techniques", False, "Project-defined doji geometry"),
    CandidateSpec("candle_dragonfly_doji", "candlestick", "bullish", "objective", "Japanese Candlestick Charting Techniques", True, "Project-defined dragonfly doji after decline"),
    CandidateSpec("candle_gravestone_doji", "candlestick", "risk", "objective", "Japanese Candlestick Charting Techniques", False, "Project-defined gravestone doji after rise"),
    CandidateSpec("candle_spinning_top", "candlestick", "annotation", "objective", "Japanese Candlestick Charting Techniques", False, "Project-defined spinning top"),
    CandidateSpec("candle_bullish_harami", "candlestick", "bullish", "objective", "Japanese Candlestick Charting Techniques", True, "Project-defined bullish harami after decline"),
    CandidateSpec("candle_bearish_harami", "candlestick", "risk", "objective", "Japanese Candlestick Charting Techniques", False, "Project-defined bearish harami after rise"),
    CandidateSpec("candle_tweezer_bottom", "candlestick", "bullish", "objective", "Japanese Candlestick Charting Techniques", True, "Project-defined tweezer bottom after decline"),
    CandidateSpec("candle_tweezer_top", "candlestick", "risk", "objective", "Japanese Candlestick Charting Techniques", False, "Project-defined tweezer top after rise"),
    CandidateSpec("candle_three_white_soldiers", "candlestick", "bullish", "objective", "Japanese Candlestick Charting Techniques", True, "Project-defined three white soldiers"),
    CandidateSpec("candle_three_black_crows", "candlestick", "risk", "objective", "Japanese Candlestick Charting Techniques", False, "Project-defined three black crows"),
    CandidateSpec("candle_hanging_man", "candlestick", "risk", "objective", "Japanese Candlestick Charting Techniques", False, "Existing hanging man risk detector"),
    CandidateSpec("candle_shooting_star", "candlestick", "risk", "objective", "Japanese Candlestick Charting Techniques", False, "Existing shooting star risk detector"),
    CandidateSpec("candle_bearish_engulfing", "candlestick", "risk", "objective", "Japanese Candlestick Charting Techniques", False, "Existing bearish engulfing risk detector"),
    CandidateSpec("candle_dark_cloud_cover", "candlestick", "risk", "objective", "Japanese Candlestick Charting Techniques", False, "Existing dark cloud cover risk detector"),
    CandidateSpec("candle_evening_star", "candlestick", "risk", "objective", "Japanese Candlestick Charting Techniques", False, "Existing evening star risk detector"),
)

CANDIDATE_SPECS = FUTU_BASE_SPECS + FUTU_EXPANDED_SPECS + FUTU_EXCLUDED_SPECS + CANDLE_SPECS
CANDIDATE_REGISTRY = {spec.name: spec for spec in CANDIDATE_SPECS}
IMPLEMENTED_CANDIDATES = tuple(
    spec.name for spec in CANDIDATE_SPECS if spec.implementability == "objective"
)
PRIMARY_CANDIDATES = tuple(
    spec.name for spec in CANDIDATE_SPECS if spec.implementability == "objective" and spec.primary_selectable
)
ANNOTATION_CANDIDATES = tuple(
    spec.name for spec in CANDIDATE_SPECS if spec.implementability == "objective" and not spec.primary_selectable
)
EXCLUDED_CANDIDATES = tuple(
    spec.name for spec in CANDIDATE_SPECS if spec.implementability != "objective"
)


def registry_json() -> dict[str, Any]:
    return {name: CANDIDATE_REGISTRY[name].to_json() for name in CANDIDATE_REGISTRY}


def _numeric(frame: pd.DataFrame, name: str) -> pd.Series:
    values = pd.to_numeric(frame.get(name, pd.Series(np.nan, index=frame.index)), errors="coerce")
    return values.where(np.isfinite(values))


def _cross_up(left: pd.Series, right: pd.Series | float) -> pd.Series:
    other = right if isinstance(right, pd.Series) else pd.Series(float(right), index=left.index)
    return left.shift(1).le(other.shift(1)) & left.gt(other)


def _cross_down(left: pd.Series, right: pd.Series | float) -> pd.Series:
    other = right if isinstance(right, pd.Series) else pd.Series(float(right), index=left.index)
    return left.shift(1).ge(other.shift(1)) & left.lt(other)


def _short_decline(close: pd.Series) -> pd.Series:
    return close.shift(1).lt(close.shift(3)).fillna(False)


def _short_rise(close: pd.Series) -> pd.Series:
    return close.shift(1).gt(close.shift(3)).fillna(False)


def _prefixed(prefix: str, masks: Mapping[str, list[bool]], index: pd.Index) -> dict[str, pd.Series]:
    return {f"{prefix}_{name}": pd.Series(values, index=index, dtype=bool) for name, values in masks.items()}


def expanded_futu_masks_from_values(values: pd.DataFrame) -> dict[str, pd.Series]:
    mkf_columns = [f"mkf_{name}" for name in ("momentum", "inter", "near")]
    masks = {
        "alphagpt_cross_001": _cross_up(values["alphagpt_factor"], 0.01),
        "dxbd_surge_cross_60": _cross_up(values["dxbd"], 60.0),
        "dxbd_clear_cross_78": _cross_up(values["dxbd"], 78.0),
        "dxbd_replenish_cross_minus60": _cross_up(values["dxbd"], -60.0),
        "dxbd_accumulate_cross_minus80": _cross_up(values["dxbd"], -80.0),
        "ribbon1_strict_sell": _cross_down(values["ribbon"], values["ribbon_signal"]) & values["ribbon_signal"].gt(70.0),
        "kdj_trend_pro_sell": _cross_down(values["kdj_k"], values["kdj_d"]) & values["close"].lt(values["ema60"]),
        "mkf_bullcluster": values[mkf_columns].le(20.0).all(axis=1),
        "mkf_bearcluster": values[mkf_columns].ge(80.0).all(axis=1),
        "shengbei_long_state": values["shengbei_state"].eq(1.0),
        "shengbei_short_flip": values["shengbei_state"].shift(1).eq(1.0) & values["shengbei_state"].eq(-1.0),
        "gding_fast_cross_down": _cross_down(values["gding_fast"], values["gding_signal"]),
        "cpgw_main_cross_down_long": _cross_down(values["cpgw_main"], values["cpgw_long"]),
        "smc_bull_bos": values["close"].gt(values["prior_high30"]) & values["prior_close"].le(values["prior_high30"]),
        "smc_bull_choch": (
            values["ema20"].gt(values["ema50"]) & values["ema20"].shift(1).lt(values["ema50"].shift(1))
            & values["close"].gt(values["prior_high30"])
        ),
        "smc_medium_buy": values["low"].gt(values["high"].shift(2)) & values["ema20"].gt(values["ema50"]),
        "smc_touch_liquidity_low": (
            values["low"].le(values["liquidity_low10"])
            & values["low"].shift(1).gt(values["liquidity_low10"].shift(1))
        ),
    }
    return {name: mask.fillna(False).astype(bool) for name, mask in masks.items()}


def _project_candle_masks(trading: pd.DataFrame) -> dict[str, pd.Series]:
    close, open_, high, low = (_numeric(trading, name) for name in ("close", "open", "high", "low"))
    candle_range = high - low
    body = close.sub(open_).abs()
    body_high = pd.concat((open_, close), axis=1).max(axis=1)
    body_low = pd.concat((open_, close), axis=1).min(axis=1)
    upper = high - body_high
    lower = body_low - low
    close_location = close.sub(low).div(candle_range.where(candle_range.gt(0)))
    body_ratio = body.div(candle_range.where(candle_range.gt(0)))
    doji = body_ratio.le(0.10)
    decline = _short_decline(close)
    rise = _short_rise(close)
    prior_body_high = body_high.shift(1)
    prior_body_low = body_low.shift(1)
    prior_body = body.shift(1)
    prior_range = candle_range.shift(1)
    low_match = low.sub(low.shift(1)).abs().le(pd.concat((close, close.shift(1)), axis=1).min(axis=1).mul(0.003))
    high_match = high.sub(high.shift(1)).abs().le(pd.concat((close, close.shift(1)), axis=1).min(axis=1).mul(0.003))
    bullish = close.gt(open_)
    bearish = close.lt(open_)
    masks = {
        "candle_inverted_hammer": (
            decline & upper.ge(2.0 * body) & lower.le(np.maximum(0.5 * body, 0.1 * candle_range))
            & body_ratio.le(0.40) & body_low.sub(low).div(candle_range.where(candle_range.gt(0))).le(0.35)
        ),
        "candle_doji": doji,
        "candle_dragonfly_doji": decline & doji & close_location.ge(0.75) & lower.ge(0.60 * candle_range),
        "candle_gravestone_doji": rise & doji & close_location.le(0.25) & upper.ge(0.60 * candle_range),
        "candle_spinning_top": body_ratio.gt(0.10) & body_ratio.le(0.30) & upper.ge(0.5 * body) & lower.ge(0.5 * body),
        "candle_bullish_harami": decline & close.shift(1).lt(open_.shift(1)) & bullish & body_high.lt(prior_body_high) & body_low.gt(prior_body_low) & body.lt(0.75 * prior_body),
        "candle_bearish_harami": rise & close.shift(1).gt(open_.shift(1)) & bearish & body_high.lt(prior_body_high) & body_low.gt(prior_body_low) & body.lt(0.75 * prior_body),
        "candle_tweezer_bottom": decline & low_match & close.shift(1).lt(open_.shift(1)) & bullish,
        "candle_tweezer_top": rise & high_match & close.shift(1).gt(open_.shift(1)) & bearish,
        "candle_three_white_soldiers": (
            decline.shift(2).fillna(False) & bullish & bullish.shift(1).fillna(False) & bullish.shift(2).fillna(False)
            & close.gt(close.shift(1)) & close.shift(1).gt(close.shift(2))
            & open_.between(body_low.shift(1), body_high.shift(1), inclusive="both")
            & open_.shift(1).between(body_low.shift(2), body_high.shift(2), inclusive="both")
            & body_ratio.ge(0.45) & body_ratio.shift(1).ge(0.45) & body_ratio.shift(2).ge(0.45)
        ),
        "candle_three_black_crows": (
            rise.shift(2).fillna(False) & bearish & bearish.shift(1).fillna(False) & bearish.shift(2).fillna(False)
            & close.lt(close.shift(1)) & close.shift(1).lt(close.shift(2))
            & open_.between(body_low.shift(1), body_high.shift(1), inclusive="both")
            & open_.shift(1).between(body_low.shift(2), body_high.shift(2), inclusive="both")
            & body_ratio.ge(0.45) & body_ratio.shift(1).ge(0.45) & body_ratio.shift(2).ge(0.45)
        ),
    }
    return {name: mask.fillna(False).astype(bool) for name, mask in masks.items()}


def indicator_masks(frame: pd.DataFrame) -> dict[str, pd.Series]:
    values = tradable_indicator_values(frame)
    trading_masks = {**candidate_masks_from_values(values), **expanded_futu_masks_from_values(values)}
    result: dict[str, pd.Series] = {}
    for name, mask in trading_masks.items():
        result[name] = pd.Series(False, index=frame.index, dtype=bool)
        result[name].loc[values.index] = mask
    return result


def candlestick_masks(frame: pd.DataFrame) -> dict[str, pd.Series]:
    trade = frame.get("tradestatus", pd.Series(index=frame.index, dtype=object)).astype("string")
    trading = frame.loc[trade.eq("1").fillna(False)].copy()
    result = {spec.name: pd.Series(False, index=frame.index, dtype=bool) for spec in CANDLE_SPECS if spec.implementability == "objective"}
    if trading.empty:
        return result
    records = trading.to_dict("records")
    existing = {
        **_prefixed("candle", detect_bullish_patterns(records), trading.index),
        **_prefixed("candle", detect_bearish_risk_patterns(records), trading.index),
    }
    project = _project_candle_masks(trading)
    for name, mask in {**existing, **project}.items():
        if name in result:
            result[name].loc[trading.index] = mask.fillna(False).astype(bool)
    return result


def candidate_masks(frame: pd.DataFrame) -> dict[str, pd.Series]:
    return {**indicator_masks(frame), **candlestick_masks(frame)}


def _target_outcomes(data: pd.DataFrame) -> dict[pd.Timestamp, dict[str, Any]]:
    records = data.to_dict("records")
    outcomes: dict[pd.Timestamp, dict[str, Any]] = {}
    for origin_index, origin in enumerate(records):
        origin_date = pd.Timestamp(origin["date"])
        try:
            origin_close = float(origin["close"])
        except (TypeError, ValueError, KeyError):
            origin_close = np.nan
        target_index = next(
            (index for index in range(origin_index + 1, len(records)) if str(records[index].get("tradestatus", "")) == "1"),
            None,
        )
        if target_index is None:
            outcomes[origin_date] = {"target_status": "pending", "target_date": pd.NaT, "target_close": np.nan, "target_up": pd.NA, "target_down": pd.NA}
            continue
        target = records[target_index]
        target_date = pd.Timestamp(target["date"])
        try:
            target_close = float(target["close"])
        except (TypeError, ValueError, KeyError):
            outcomes[origin_date] = {"target_status": "target_invalid", "target_date": target_date, "target_close": np.nan, "target_up": pd.NA, "target_down": pd.NA}
            continue
        if not np.isfinite(origin_close) or origin_close <= 0 or not np.isfinite(target_close) or target_close <= 0:
            outcomes[origin_date] = {"target_status": "target_invalid", "target_date": target_date, "target_close": target_close, "target_up": pd.NA, "target_down": pd.NA}
            continue
        outcomes[origin_date] = {
            "target_status": "mature",
            "target_date": target_date,
            "target_close": target_close,
            "target_up": target_close > origin_close,
            "target_down": target_close < origin_close,
        }
    return outcomes


def build_nextday_panel(
    code: str,
    frame: pd.DataFrame,
    config: Mapping[str, Any],
    *,
    start_date: str = DEFAULT_START_DATE,
    end_date: str | None = None,
) -> pd.DataFrame:
    data = frame.copy()
    data["date"] = pd.to_datetime(data.get("date"), errors="coerce").dt.normalize()
    data = data.dropna(subset=["date"]).sort_values("date", kind="stable").drop_duplicates("date", keep="last").reset_index(drop=True)
    masks = candidate_masks(data)
    trade = data.get("tradestatus", pd.Series(index=data.index, dtype=object)).astype("string")
    selected = data["date"].ge(pd.Timestamp(start_date))
    if end_date is not None:
        selected &= data["date"].le(pd.Timestamp(end_date))
    panel = pd.DataFrame({
        "code": code,
        "date": data["date"],
        "trading_index": trade.eq("1").astype(int).cumsum().sub(1).where(trade.eq("1"), np.nan),
        "admitted": production_gate_mask(code, data, config),
    }).loc[selected].reset_index(drop=True)
    by_date = data["date"]
    for name in IMPLEMENTED_CANDIDATES:
        if name in masks:
            panel[name] = panel["date"].map(dict(zip(by_date, masks[name], strict=True))).fillna(False).astype(bool)
    outcomes = _target_outcomes(data)
    outcome_rows = panel["date"].map(outcomes)
    panel["origin_date"] = panel["date"]
    panel["target_date"] = pd.to_datetime(outcome_rows.map(lambda value: value["target_date"] if isinstance(value, Mapping) else pd.NaT))
    panel["target_close"] = pd.to_numeric(outcome_rows.map(lambda value: value["target_close"] if isinstance(value, Mapping) else np.nan), errors="coerce")
    panel["target_status"] = outcome_rows.map(lambda value: value["target_status"] if isinstance(value, Mapping) else "target_missing")
    panel["target_up"] = pd.array(outcome_rows.map(lambda value: value["target_up"] if isinstance(value, Mapping) else pd.NA), dtype="boolean")
    panel["target_down"] = pd.array(outcome_rows.map(lambda value: value["target_down"] if isinstance(value, Mapping) else pd.NA), dtype="boolean")
    return panel


def _periods(rows: pd.DataFrame) -> dict[str, tuple[int, int]]:
    years = sorted(int(year) for year in rows["target_date"].dropna().dt.year.unique())
    if not years:
        return {"full_available_history": (1900, 9999)}
    return {"full_available_history": (years[0], years[-1]), **{f"year_{year}": (year, year) for year in years}}


def _summarize(signal_rows: pd.DataFrame, baseline: pd.DataFrame, *, direction: str) -> dict[str, Any]:
    label_column = "target_down" if direction == "risk" else "target_up"
    signal = signal_rows.loc[signal_rows["target_status"].eq("mature") & signal_rows[label_column].notna()]
    result = summarize_counts(len(signal), int(signal[label_column].astype(bool).sum()))
    result["origin_dates"] = int(signal["origin_date"].nunique())
    result["target_dates"] = int(signal["target_date"].nunique())
    result["codes"] = int(signal["code"].nunique())
    counts = signal.groupby("target_date").size()
    matched = baseline.loc[baseline["target_date"].isin(counts.index)]
    by_date = matched.groupby("target_date")[label_column].agg(["count", "sum"])
    weights = counts.reindex(by_date.index).astype(float)
    weighted_n = float(weights.sum())
    weighted_hits = float((weights * by_date["sum"].div(by_date["count"])).sum()) if weighted_n else 0.0
    baseline_precision = weighted_hits / weighted_n if weighted_n else None
    result["same_target_date_baseline"] = {
        "admitted_n": int(by_date["count"].sum()) if not by_date.empty else 0,
        "admitted_hits": int(by_date["sum"].sum()) if not by_date.empty else 0,
        "weighted_n": int(weighted_n),
        "weighted_hits": weighted_hits,
        "precision": baseline_precision,
    }
    result["precision_lift"] = None if result["precision"] is None or baseline_precision is None else result["precision"] - baseline_precision
    return result


def _coverage(raw: pd.DataFrame) -> dict[str, Any]:
    status_counts = {str(key): int(value) for key, value in raw["target_status"].value_counts(dropna=False).sort_index().items()}
    admitted = raw.loc[raw["admitted"].fillna(False)]
    return {
        "raw_triggers": int(len(raw)),
        "origin_admitted_triggers": int(len(admitted)),
        "status_counts": status_counts,
        "mature_triggers": int(raw["target_status"].eq("mature").sum()),
    }


def aggregate_nextday_metrics(panel: pd.DataFrame) -> dict[str, Any]:
    mature_admitted = panel.loc[
        panel["admitted"].fillna(False) & panel["target_status"].eq("mature") & panel["target_up"].notna()
    ].copy()
    mature_counts = mature_admitted.groupby("target_date").size()
    valid_target_dates = set(mature_counts[mature_counts.ge(MIN_BASELINE_ROWS)].index)
    baseline = mature_admitted.loc[mature_admitted["target_date"].isin(valid_target_dates)]
    periods = _periods(panel)
    primary: dict[str, Any] = {}
    annotation: dict[str, Any] = {}
    all_origin: dict[str, Any] = {}
    nonoverlap: dict[str, Any] = {}
    coverage: dict[str, Any] = {}
    for name in IMPLEMENTED_CANDIDATES:
        if name not in panel:
            continue
        raw = panel.loc[panel[name].fillna(False)].copy()
        usable = raw.loc[raw["admitted"].fillna(False) & raw["target_status"].eq("mature") & raw["target_date"].isin(valid_target_dates)]
        spaced = nonoverlapping_origins(usable)
        destination = primary if CANDIDATE_REGISTRY[name].primary_selectable else annotation
        destination[name] = {}
        all_origin[name] = {}
        nonoverlap[name] = {}
        coverage[name] = {}
        for key, (first, last) in periods.items():
            in_period = lambda rows: rows.loc[rows["target_date"].dt.year.between(first, last)]
            direction = CANDIDATE_REGISTRY[name].direction
            destination[name][key] = _summarize(in_period(usable), in_period(baseline), direction=direction)
            all_origin[name][key] = _summarize(in_period(usable), in_period(baseline), direction=direction)
            nonoverlap[name][key] = _summarize(in_period(spaced), in_period(baseline), direction=direction)
            coverage[name][key] = _coverage(in_period(raw))
    return {
        "periods": periods,
        "baseline_dates": int(len(valid_target_dates)),
        "primary_metrics": primary,
        "annotation_metrics": annotation,
        "all_origin_metrics": all_origin,
        "nonoverlap_sensitivity": nonoverlap,
        "coverage": coverage,
    }


def _combined_period(year_metrics: Mapping[str, Mapping[str, Any]], years: range) -> dict[str, Any]:
    cells = [year_metrics[f"year_{year}"] for year in years if f"year_{year}" in year_metrics]
    n = sum(int(cell["n"]) for cell in cells)
    hits = sum(int(cell["hits"]) for cell in cells)
    result = summarize_counts(n, hits)
    baseline_hits = sum(float(cell["same_target_date_baseline"]["weighted_hits"]) for cell in cells)
    baseline_n = sum(int(cell["same_target_date_baseline"]["weighted_n"]) for cell in cells)
    baseline_precision = baseline_hits / baseline_n if baseline_n else None
    result["target_dates"] = sum(int(cell["target_dates"]) for cell in cells)
    result["same_target_date_baseline"] = {
        "weighted_n": baseline_n,
        "weighted_hits": baseline_hits,
        "precision": baseline_precision,
    }
    result["precision_lift"] = (
        result["precision"] - baseline_precision
        if result["precision"] is not None and baseline_precision is not None
        else None
    )
    return result


def evaluate_stability(metrics: Mapping[str, Mapping[str, Any]], last_year: int) -> dict[str, Any]:
    selection_years = range(2021, 2024)
    audit_years = range(2024, last_year + 1)
    complete_audit_years = range(2024, last_year if last_year == 2026 else last_year + 1)
    periods = {
        "selection_2021_2023": _combined_period(metrics, selection_years),
        "audit_2024_present": _combined_period(metrics, audit_years),
    }
    failures: list[str] = []
    for name, cell in periods.items():
        baseline = cell["same_target_date_baseline"]["precision"]
        if int(cell["n"]) < 300:
            failures.append(f"{name}:n_below_300")
        if int(cell["target_dates"]) < 120:
            failures.append(f"{name}:target_dates_below_120")
        if cell["precision_lift"] is None or cell["precision_lift"] < 0.03:
            failures.append(f"{name}:lift_below_0.03")
        if cell["wilson_lower_95"] is None or baseline is None or cell["wilson_lower_95"] <= baseline:
            failures.append(f"{name}:wilson_lower_not_above_baseline")
    for year in complete_audit_years:
        cell = metrics.get(f"year_{year}")
        if cell is None or cell["precision_lift"] is None or cell["precision_lift"] <= 0:
            failures.append(f"year_{year}:lift_not_positive")
    return {"passed": not failures, "failure_codes": failures, "decision_periods": periods}


def build_report(
    *,
    panel: pd.DataFrame,
    code_list: list[str],
    code_list_sha256: str,
    start_date: str,
    end_date: str | None,
    workers: int,
) -> dict[str, Any]:
    metrics = aggregate_nextday_metrics(panel)
    available_years = [value[0] for key, value in metrics["periods"].items() if key.startswith("year_")]
    last_year = max(available_years) if available_years else 2026
    decisions = {
        name: evaluate_stability(candidate_metrics, last_year)
        for group in (metrics["primary_metrics"], metrics["annotation_metrics"])
        for name, candidate_metrics in group.items()
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "study": STUDY_NAME,
        "research_only": True,
        "classification_only": True,
        "production_enabled": False,
        "default_preference": True,
        "date_range": {"start_date": start_date, "end_date": end_date},
        "sample": {
            "method": "all_current_main_board_sorted_code",
            "codes": len(code_list),
            "code_list": code_list,
            "code_list_sha256": code_list_sha256,
        },
        "workers": workers,
        "alignment": {
            "origin_date": "candidate computed using data visible through T",
            "target_date": "next tradable stock row after T; suspension rows are skipped and target OHLCV is outcome-only",
            "label_anchor": "target_date_close_vs_origin_date_close",
            "label": "bullish hits iff D close > T close; risk hits iff D close < T close; flat is a miss",
            "baseline": "same target-date origin-admitted direction rate weighted by candidate count; target dates require at least 150 baseline rows",
        },
        "candidate_registry": registry_json(),
        "implemented_candidates": list(IMPLEMENTED_CANDIDATES),
        "primary_candidates": list(PRIMARY_CANDIDATES),
        "annotation_candidates": list(ANNOTATION_CANDIDATES),
        "excluded_candidates": list(EXCLUDED_CANDIDATES),
        "decision": {
            "gates": "Both 2021-2023 and 2024-present require n>=300, >=120 target dates, >=3pp lift, and Wilson lower above baseline; every complete audit year requires positive lift.",
            "candidates": decisions,
            "passed_candidates": sorted(name for name, value in decisions.items() if value["passed"]),
        },
        **metrics,
        "limitations": [
            "Adjusted local research data and current-file survivorship remain limitations.",
            "This is classification evidence only, not profitability, execution, or personalized investment advice.",
            "Underdefined Futu and candlestick items are excluded or annotation-only rather than approximated post hoc.",
            "No scanner, production gate, watchlist, order, return, P&L, or portfolio behavior is changed by this report.",
        ],
    }
