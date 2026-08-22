"""Leakage-safe classification primitives for Precision 70 Stage 1."""

from __future__ import annotations

import hashlib
import math
from collections import deque
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .research_v2 import summarize_counts


PREFIXES = ("sh.600", "sh.601", "sh.603", "sh.605", "sz.000", "sz.001", "sz.002", "sz.003")
CANDIDATES = ("breadth_residual_leadership", "breadth_pullback_reacceleration", "barrier_suitability_prior")
PERIODS = {
    "calibration_2021_2022": (2021, 2022),
    "selection_2023_2024": (2023, 2024),
    "holdout_2025_2026": (2025, 2026),
    "aggregate_2021_2026": (2021, 2026),
}
YEARS = tuple(range(2021, 2027))
PANEL_COLUMNS = (
    "code", "date", "trading_index", "admitted", "mhpg_buy", "close", "sma20", "sma60",
    "sma20_t5", "sma60_t5", "ret5", "ret20", "close_location",
    "upper_shadow_ratio", "volume_ratio_ma20", "bullish_t", "t_return",
    "previous_high", "ret_t3_to_t1", "benchmark_ret20", "prior_n", "prior_hits",
    "posterior", "maturity_date", "label",
)


def stable_sample(paths: Sequence[Path], max_codes: int = 400) -> list[Path]:
    """Return the exact SHA-256 sample of 400 current main-board files."""

    if max_codes != 400:
        raise ValueError("max_codes must equal 400")
    eligible = [path for path in paths if path.stem.startswith(PREFIXES)]
    eligible.sort(key=lambda path: (hashlib.sha256(path.stem.encode("ascii")).hexdigest(), path.stem))
    if len(eligible) < 400:
        raise ValueError(f"exactly 400 main-board files required; found {len(eligible)}")
    return sorted(eligible[:400], key=lambda path: path.stem)


def _numeric(frame: pd.DataFrame, name: str) -> pd.Series:
    values = pd.to_numeric(frame[name], errors="coerce") if name in frame else pd.Series(np.nan, index=frame.index)
    return values.where(np.isfinite(values))


def _ema(values: pd.Series, span: int) -> pd.Series:
    return values.ewm(span=span, adjust=False, min_periods=1).mean()


def _tdx_sma(values: pd.Series, n: int, m: int) -> pd.Series:
    result = np.full(len(values), np.nan, dtype=float)
    previous = np.nan
    for index, value in enumerate(values.to_numpy(dtype=float)):
        if not math.isfinite(value):
            continue
        previous = value if not math.isfinite(previous) else (m * value + (n - m) * previous) / n
        result[index] = previous
    return pd.Series(result, index=values.index)


def production_gate_mask(code: str, frame: pd.DataFrame, config: Mapping[str, Any]) -> pd.Series:
    """Vectorize the current ``apply_hard_gates`` contract at every row.

    Unlike the production function's exception-level fallback, malformed or
    missing values fail their individual gate. Valid rows are parity-equivalent.
    """

    universe = config.get("universe", {})
    prefixes = tuple(str(value) for value in universe.get("include_prefixes", PREFIXES))
    mask = pd.Series(bool(prefixes and code.startswith(prefixes)), index=frame.index, dtype=bool)
    close = _numeric(frame, "close")
    preclose = _numeric(frame, "preclose")
    amount = _numeric(frame, "amount")
    trade = frame.get("tradestatus", pd.Series(index=frame.index, dtype=object)).astype("string")
    st = frame.get("isST", pd.Series(index=frame.index, dtype=object)).astype("string")

    if bool(universe.get("exclude_st", True)):
        mask &= st.eq("0").fillna(False)
    mask &= pd.Series(np.arange(1, len(frame) + 1), index=frame.index).ge(int(universe.get("min_listing_days", 252)))
    mask &= close.ge(float(universe.get("min_close_cny", 5.0))) & close.le(float(universe.get("max_close_cny", 80.0)))
    if bool(universe.get("block_suspensions", True)):
        mask &= trade.eq("1").fillna(False)
    trading_count = trade.eq("1").astype(int).rolling(60, min_periods=1).sum()
    mask &= trading_count.ge(int(universe.get("min_trading_days_60", 55)))
    minimum_adv20 = float(universe.get("min_adv20_cny", 0.0))
    if minimum_adv20 > 0:
        mask &= amount.rolling(20, min_periods=20).mean().ge(minimum_adv20)
    if bool(universe.get("block_limit_up_entries", True)):
        mask &= preclose.gt(0) & (close.div(preclose).sub(1.0) < 0.095)
    return mask.fillna(False)


def five_close_label(reference_close: float, future_closes: Sequence[float]) -> bool:
    """Apply the fixed +3% reach and -3% close-floor classification label."""

    values = np.asarray(future_closes, dtype=float)
    if not math.isfinite(float(reference_close)) or reference_close <= 0 or len(values) != 5 or not np.isfinite(values).all():
        raise ValueError("label requires a positive finite reference and exactly five finite future closes")
    return bool(values.max() >= reference_close * 1.03 and values.min() >= reference_close * 0.97)


def next_five_trading_closes_and_maturity(
    records: Sequence[Mapping[str, Any]], t_index: int
) -> tuple[list[float], pd.Timestamp] | None:
    """Return five post-origin tradable closes and the fifth bar's date."""

    closes: list[float] = []
    maturity: pd.Timestamp | None = None
    for record in records[t_index + 1:]:
        if str(record.get("tradestatus", "")) != "1":
            continue
        try:
            close = float(record["close"])
            date = pd.Timestamp(record["date"])
        except (KeyError, TypeError, ValueError):
            return None
        if not math.isfinite(close) or pd.isna(date):
            return None
        closes.append(close)
        maturity = date
        if len(closes) == 5:
            return closes, maturity
    return None


def causal_barrier_prior(
    dates: Sequence[Any], maturities: Sequence[Any], labels: Sequence[Any], eligible_origins: Sequence[bool]
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Compute the latest-252 posterior using only maturities strictly before T."""

    n_rows = len(dates)
    if not (len(maturities) == len(labels) == len(eligible_origins) == n_rows):
        raise ValueError("prior inputs must have equal lengths")
    date_values = pd.to_datetime(pd.Series(dates), errors="coerce").to_numpy()
    maturity_values = pd.to_datetime(pd.Series(maturities), errors="coerce").to_numpy()
    pending = 0
    history: deque[int] = deque(maxlen=252)
    prior_n = np.zeros(n_rows, dtype=np.int16)
    prior_hits = np.zeros(n_rows, dtype=np.int16)
    posterior = np.full(n_rows, np.nan, dtype=float)
    for index, current_date in enumerate(date_values):
        while pending < index:
            maturity = maturity_values[pending]
            if np.isnat(maturity) or not bool(eligible_origins[pending]) or pd.isna(labels[pending]):
                pending += 1
                continue
            if maturity >= current_date:
                break
            history.append(int(bool(labels[pending])))
            pending += 1
        prior_n[index] = len(history)
        prior_hits[index] = sum(history)
        if len(history) >= 120:
            posterior[index] = (prior_hits[index] + 10.0) / (len(history) + 30.0)
    return prior_n, prior_hits, posterior


def build_stock_panel(
    code: str,
    frame: pd.DataFrame,
    config: Mapping[str, Any],
    benchmark_ret20: Mapping[pd.Timestamp, float] | None = None,
    *,
    start_date: str = "2021-01-01",
    end_date: str | None = None,
) -> pd.DataFrame:
    """Build compact causal stock rows; only labels inspect post-T observations."""

    data = frame.copy()
    data["date"] = pd.to_datetime(data.get("date"), errors="coerce").dt.normalize()
    data = data.dropna(subset=["date"]).sort_values("date", kind="stable").drop_duplicates("date", keep="last").reset_index(drop=True)
    close, open_, high, low = (_numeric(data, field) for field in ("close", "open", "high", "low"))
    volume = _numeric(data, "volume")
    preclose = _numeric(data, "preclose")
    trade = data.get("tradestatus", pd.Series(index=data.index, dtype=object)).astype("string")
    sma20 = close.rolling(20, min_periods=20).mean()
    sma60 = close.rolling(60, min_periods=60).mean()
    candle_range = high - low
    volume_ma20 = volume.rolling(20, min_periods=20).mean()
    ema20 = _ema(close, 20)
    ema60 = _ema(close, 60)
    low30 = low.rolling(30, min_periods=1).min()
    high30 = high.rolling(30, min_periods=1).max()
    k = _tdx_sma(close.sub(low30).div(high30.sub(low30).add(1e-6)).mul(100.0), 3, 1)
    d = _tdx_sma(k, 3, 1)

    records = data.to_dict("records")
    labels: list[Any] = [pd.NA] * len(data)
    maturities: list[Any] = [pd.NaT] * len(data)
    origin_eligible = trade.eq("1").fillna(False) & close.gt(0)
    for index in range(len(data)):
        future = next_five_trading_closes_and_maturity(records, index)
        if future is not None and bool(origin_eligible.iat[index]):
            closes, maturity = future
            labels[index] = five_close_label(float(close.iat[index]), closes)
            maturities[index] = maturity
    prior_n, prior_hits, posterior = causal_barrier_prior(data["date"], maturities, labels, origin_eligible)
    trading_index = trade.eq("1").astype(int).cumsum().sub(1).where(trade.eq("1"), np.nan)

    panel = pd.DataFrame({
        "code": code,
        "date": data["date"],
        "trading_index": trading_index,
        "admitted": production_gate_mask(code, data, config),
        "mhpg_buy": (
            ema20.gt(ema60) & ema60.gt(ema60.shift(2))
            & k.shift(1).le(d.shift(1)) & k.gt(d) & k.lt(60.0)
        ).fillna(False),
        "close": close,
        "sma20": sma20,
        "sma60": sma60,
        "sma20_t5": sma20.shift(5),
        "sma60_t5": sma60.shift(5),
        "ret5": close.div(close.shift(5)).sub(1.0),
        "ret20": close.div(close.shift(20)).sub(1.0),
        "close_location": close.sub(low).div(candle_range).where(candle_range.gt(0)),
        "upper_shadow_ratio": high.sub(pd.concat((open_, close), axis=1).max(axis=1)).div(candle_range).where(candle_range.gt(0)),
        "volume_ratio_ma20": volume.div(volume_ma20).where(volume_ma20.gt(0)),
        "bullish_t": close.gt(open_) & close.notna() & open_.notna(),
        "t_return": close.div(preclose).sub(1.0).where(preclose.gt(0)),
        "previous_high": high.shift(1),
        "ret_t3_to_t1": close.shift(1).div(close.shift(3)).sub(1.0),
        "prior_n": prior_n,
        "prior_hits": prior_hits,
        "posterior": posterior,
        "maturity_date": pd.to_datetime(maturities),
        "label": pd.array(labels, dtype="boolean"),
    })
    benchmark = benchmark_ret20 or {}
    panel["benchmark_ret20"] = panel["date"].map(benchmark)
    selected = panel["date"].ge(pd.Timestamp(start_date))
    if end_date is not None:
        selected &= panel["date"].le(pd.Timestamp(end_date))
    return panel.loc[selected, PANEL_COLUMNS].reset_index(drop=True)


def add_cross_sectional_features(panel: pd.DataFrame, *, min_denominator: int = 150) -> pd.DataFrame:
    """Add frozen daily breadth and deterministic average percentile ranks."""

    result = panel.copy().sort_values(["date", "code"], kind="stable").reset_index(drop=True)
    result["daily_denominator"] = 0
    for name in ("breadth_sma20", "breadth_sma60", "median_ret5", "breadth_acceleration", "ret20_pct", "ret5_pct", "posterior_pct"):
        result[name] = np.nan
    valid_dates: list[pd.Timestamp] = []
    breadth20_by_date: dict[pd.Timestamp, float] = {}
    for date, indices in result.groupby("date", sort=True).groups.items():
        admitted_indices = [index for index in indices if bool(result.at[index, "admitted"])]
        denominator = len(admitted_indices)
        result.loc[list(indices), "daily_denominator"] = denominator
        if denominator < min_denominator:
            continue
        admitted = result.loc[admitted_indices]
        breadth20 = float((admitted["close"] > admitted["sma20"]).fillna(False).mean())
        breadth60 = float((admitted["close"] > admitted["sma60"]).fillna(False).mean())
        median_ret5 = float(admitted["ret5"].median())
        prior_breadth = breadth20_by_date[valid_dates[-5]] if len(valid_dates) >= 5 else np.nan
        result.loc[list(indices), ["breadth_sma20", "breadth_sma60", "median_ret5"]] = (breadth20, breadth60, median_ret5)
        result.loc[list(indices), "breadth_acceleration"] = breadth20 - prior_breadth
        result.loc[admitted_indices, "ret20_pct"] = admitted["ret20"].rank(method="average", pct=True)
        result.loc[admitted_indices, "ret5_pct"] = admitted["ret5"].rank(method="average", pct=True)
        adequate = admitted.index[admitted["prior_n"].ge(120) & admitted["posterior"].notna()]
        result.loc[adequate, "posterior_pct"] = result.loc[adequate, "posterior"].rank(method="average", pct=True)
        valid_dates.append(pd.Timestamp(date))
        breadth20_by_date[pd.Timestamp(date)] = breadth20
    return result


def candidate_masks(panel: pd.DataFrame) -> dict[str, pd.Series]:
    """Classify exactly the three frozen candidates, independently."""

    valid = panel["admitted"].fillna(False) & panel["daily_denominator"].ge(150)
    breadth = (
        panel["breadth_sma20"].ge(0.60) & panel["breadth_sma60"].ge(0.50)
        & panel["breadth_acceleration"].ge(0.05) & panel["median_ret5"].gt(0)
    )
    trend = (
        panel["close"].gt(panel["sma20"]) & panel["sma20"].gt(panel["sma60"])
        & panel["sma20"].gt(panel["sma20_t5"]) & panel["sma60"].gt(panel["sma60_t5"])
    )
    leadership = (
        valid & breadth & trend
        & panel["ret20_pct"].ge(0.80) & panel["ret20_pct"].lt(0.98)
        & panel["ret5_pct"].ge(0.60) & panel["ret5_pct"].lt(0.95)
        & panel["ret20"].sub(panel["benchmark_ret20"]).gt(0)
        & panel["bullish_t"].fillna(False) & panel["close_location"].ge(0.65)
        & panel["upper_shadow_ratio"].le(0.25)
        & panel["volume_ratio_ma20"].between(1.0, 2.5, inclusive="both")
    )
    pullback = (
        valid & breadth & trend
        & panel["ret20_pct"].ge(0.70) & panel["ret20_pct"].lt(0.95)
        & panel["ret_t3_to_t1"].between(-0.06, -0.01, inclusive="both")
        & panel["t_return"].between(0.01, 0.05, inclusive="both")
        & panel["close"].gt(panel["previous_high"])
        & panel["bullish_t"].fillna(False) & panel["close_location"].ge(0.70)
        & panel["upper_shadow_ratio"].le(0.20)
        & panel["volume_ratio_ma20"].between(0.9, 2.2, inclusive="both")
    )
    prior = (
        valid & panel["prior_n"].ge(120) & panel["posterior_pct"].ge(0.95)
        & panel["posterior"].ge(0.45) & panel["close"].gt(panel["sma20"])
        & panel["ret5"].between(-0.03, 0.08, inclusive="both")
    )
    return dict(zip(CANDIDATES, (leadership.fillna(False), pullback.fillna(False), prior.fillna(False)), strict=True))


def nonoverlapping_origins(rows: pd.DataFrame) -> pd.DataFrame:
    """Causally retain per-stock origins at least five tradable dates apart."""

    selected: list[int] = []
    last: dict[str, int] = {}
    for index, row in rows.sort_values(["date", "code"], kind="stable").iterrows():
        if pd.isna(row["trading_index"]):
            continue
        position = int(row["trading_index"])
        if row["code"] not in last or position - last[row["code"]] >= 5:
            selected.append(index)
            last[str(row["code"])] = position
    return rows.loc[selected].sort_values(["date", "code"], kind="stable").reset_index(drop=True)


def _summary(rows: pd.DataFrame) -> dict[str, Any]:
    mature = rows.loc[rows["label"].notna()]
    result = summarize_counts(len(mature), int(mature["label"].astype(bool).sum()))
    result["signal_dates"] = int(mature["date"].nunique())
    return result


def aggregate_metrics(panel: pd.DataFrame, masks: Mapping[str, pd.Series]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Aggregate baseline/candidates and candidate non-overlap sensitivity."""

    strategies = {"admitted_baseline": panel["admitted"].fillna(False) & panel["daily_denominator"].ge(150), **masks}
    summaries: dict[str, Any] = {}
    sensitivity: dict[str, Any] = {}
    keys = {**PERIODS, **{f"year_{year}": (year, year) for year in YEARS}}
    for name, mask in strategies.items():
        rows = panel.loc[mask]
        summaries[name] = {
            key: _summary(rows.loc[rows["date"].dt.year.between(first, last)])
            for key, (first, last) in keys.items()
        }
        if name in CANDIDATES:
            spaced = nonoverlapping_origins(rows)
            sensitivity[name] = {
                key: _summary(spaced.loc[spaced["date"].dt.year.between(first, last)])
                for key, (first, last) in keys.items()
            }
    return summaries, sensitivity


def evaluate_decision(summaries: Mapping[str, Any], sensitivity: Mapping[str, Any]) -> dict[str, Any]:
    """Apply selection first, then frozen holdout gates, with stable codes."""

    decisions: dict[str, Any] = {}
    for candidate in CANDIDATES:
        selection = summaries[candidate]["selection_2023_2024"]
        selection_failures: list[str] = []
        if selection["precision"] is None or selection["precision"] < 0.70:
            selection_failures.append("selection_precision_below_0.70")
        if int(selection["n"]) < 300:
            selection_failures.append("selection_n_below_300")
        for year in (2023, 2024):
            if int(summaries[candidate][f"year_{year}"]["n"]) < 50:
                selection_failures.append(f"selection_year_{year}_n_below_50")
        if selection["wilson_lower_95"] is None or selection["wilson_lower_95"] < 0.60:
            selection_failures.append("selection_wilson_lower_below_0.60")
        selection_eligible = not selection_failures

        holdout = summaries[candidate]["holdout_2025_2026"]
        holdout_failures: list[str] = []
        if holdout["precision"] is None or holdout["precision"] < 0.70:
            holdout_failures.append("holdout_precision_below_0.70")
        if int(holdout["n"]) < 300:
            holdout_failures.append("holdout_n_below_300")
        if int(summaries[candidate]["year_2025"]["n"]) < 50:
            holdout_failures.append("holdout_year_2025_n_below_50")
        if int(summaries[candidate]["year_2026"]["n"]) < 25:
            holdout_failures.append("holdout_year_2026_n_below_25")
        if holdout["wilson_lower_95"] is None or holdout["wilson_lower_95"] < 0.60:
            holdout_failures.append("holdout_wilson_lower_below_0.60")
        nonoverlap = sensitivity[candidate]["holdout_2025_2026"]
        if nonoverlap["precision"] is None or nonoverlap["precision"] < 0.70:
            holdout_failures.append("holdout_nonoverlap_precision_below_0.70")
        decisions[candidate] = {
            "selection_eligible": selection_eligible,
            "selection_failure_codes": selection_failures,
            "holdout_audit_only_unless_selection_eligible": not selection_eligible,
            "holdout_failure_codes": holdout_failures,
            "final_pass": bool(selection_eligible and not holdout_failures),
        }
    return {"candidates": decisions, "stage1_passed": any(item["final_pass"] for item in decisions.values())}
