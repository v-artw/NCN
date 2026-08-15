#!/usr/bin/env python3
"""Full-universe, leakage-aware joint strategy precision study.

This is a read-only classification study. It does not model orders, positions,
capital, costs, returns, execution, or personalized recommendations.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import math
import os
from collections import defaultdict
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd

from ashare_edge_scout.candles import detect_bullish_patterns
from ashare_edge_scout.config import load_config


PREFIXES = ("sh.600", "sh.601", "sh.603", "sh.605", "sz.000", "sz.001", "sz.002", "sz.003")
SPLITS = {
    "calibration": (2021, 2022),
    "validation": (2023, 2024),
    "holdout": (2025, 2026),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=Path("PFrontStockData"))
    parser.add_argument("--config", type=Path, default=Path("yaml/edge_scout_v1.yaml"))
    parser.add_argument("--benchmark", default="sh.000001")
    parser.add_argument("--workers", type=int, default=min(os.cpu_count() or 1, 12))
    parser.add_argument("--start-date", default="2021-01-01")
    parser.add_argument("--end-date", default=None)
    parser.add_argument("--max-codes", type=int, default=None)
    parser.add_argument("--min-validation-observations", type=int, default=800)
    parser.add_argument("--min-validation-year-observations", type=int, default=250)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def _ema(values: np.ndarray, period: int) -> np.ndarray:
    return pd.Series(values).ewm(span=period, adjust=False).mean().to_numpy()


def _tdx_sma(values: np.ndarray, period: int, weight: int) -> np.ndarray:
    clean = np.where(np.isfinite(values), values, 0.0)
    result = np.empty_like(clean)
    result[0] = clean[0]
    for index in range(1, len(clean)):
        result[index] = (weight * clean[index] + (period - weight) * result[index - 1]) / period
    return result


def _rolling(values: np.ndarray, window: int, operation: str) -> np.ndarray:
    rolling = pd.Series(values).rolling(window, min_periods=window)
    return getattr(rolling, operation)().to_numpy()


def _shift(values: np.ndarray, periods: int) -> np.ndarray:
    result = np.full(len(values), np.nan)
    if periods < len(values):
        result[periods:] = values[:-periods]
    return result


def _future_label(close: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    future = np.column_stack([np.roll(close, -offset) for offset in range(1, 6)])
    valid = np.arange(len(close)) < len(close) - 5
    hit = valid & (np.max(future, axis=1) >= close * 1.03) & (np.min(future, axis=1) >= close * 0.97)
    t5_up = valid & (future[:, -1] > close)
    return hit, t5_up


def _benchmark_regime(path: Path, config: Mapping[str, Any]) -> dict[str, bool]:
    frame = pd.read_parquet(path, columns=["date", "close"]).sort_values("date")
    close = pd.to_numeric(frame["close"], errors="coerce")
    ma20 = close.rolling(20, min_periods=20).mean()
    trend = config.get("setup", {}).get("trend", {})
    regime_config = config.get("research_market_regime", {})
    lookback = int(trend.get("ma_slope_lookback", 5))
    max_drawdown = float(regime_config.get("max_5d_benchmark_drawdown", -0.03))
    regime = (close > ma20) & (ma20 >= ma20.shift(lookback)) & (close.pct_change(5) >= max_drawdown)
    dates = pd.to_datetime(frame["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    return dict(zip(dates, regime.fillna(False).astype(bool), strict=True))


def _strategy_masks(features: Mapping[str, np.ndarray]) -> dict[str, np.ndarray]:
    admitted = features["admitted"]
    mhpg = admitted & features["mhpg_buy"]
    stable = features["regime"] & features["no_start_risk"]
    liquid = features["adv20"] >= 100_000_000.0
    quality_close = (features["close_location"] >= 0.55) & (features["upper_shadow_pct"] <= 0.35)
    healthy_volume = (features["volume_ratio"] >= 0.80) & (features["volume_ratio"] <= 2.80)
    not_extended = features["ret5"] <= 0.08
    return {
        "admitted_baseline": admitted,
        "mhpg": mhpg,
        "mhpg_regime": mhpg & features["regime"],
        "mhpg_regime_no_risk": mhpg & stable,
        "mhpg_regime_no_risk_liquid": mhpg & stable & liquid,
        "mhpg_regime_no_risk_quality_close": mhpg & stable & quality_close,
        "mhpg_regime_no_risk_healthy_volume": mhpg & stable & healthy_volume,
        "mhpg_regime_no_risk_not_extended": mhpg & stable & not_extended,
        "mhpg_confirmed_quality": mhpg & stable & liquid & quality_close & healthy_volume & not_extended,
        "start2_regime_no_risk_liquid": admitted & (features["start_count"] >= 2) & stable & liquid,
        "setup": admitted & features["setup"],
    }


def _stock_counts(task: tuple[Any, ...]) -> dict[str, Any]:
    path_text, config, regime_by_date, start_date, end_date = task[:5]
    daily = len(task) > 5 and task[5] == "daily"
    path = Path(path_text)
    columns = ["date", "open", "high", "low", "close", "preclose", "volume", "amount", "turn", "tradestatus", "isST"]
    frame = pd.read_parquet(path, columns=columns).sort_values("date").reset_index(drop=True)
    if len(frame) < 335:
        if daily:
            return {
                "code": path.stem,
                "rows": 0,
                "dates": [],
                "signal_counts": {},
                "maturity_counts": {},
            }
        return {"code": path.stem, "rows": 0, "counts": {}}

    dates = pd.to_datetime(frame["date"], errors="coerce")
    open_ = pd.to_numeric(frame["open"], errors="coerce").to_numpy(float)
    high = pd.to_numeric(frame["high"], errors="coerce").to_numpy(float)
    low = pd.to_numeric(frame["low"], errors="coerce").to_numpy(float)
    close = pd.to_numeric(frame["close"], errors="coerce").to_numpy(float)
    volume = pd.to_numeric(frame["volume"], errors="coerce").fillna(0).to_numpy(float)
    amount = pd.to_numeric(frame["amount"], errors="coerce").fillna(0).to_numpy(float)
    turn = pd.to_numeric(frame["turn"], errors="coerce").fillna(0).to_numpy(float)
    tradestatus = frame["tradestatus"].astype(str).to_numpy()
    is_st = frame["isST"].astype(str).to_numpy()
    n = len(frame)

    ma5 = _rolling(close, 5, "mean")
    ma10 = _rolling(close, 10, "mean")
    ma20 = _rolling(close, 20, "mean")
    ma60 = _rolling(close, 60, "mean")
    adv20 = _rolling(amount, 20, "mean")
    trading60 = _rolling((tradestatus == "1").astype(float), 60, "sum")
    ret5 = close / _shift(close, 5) - 1.0
    ret20 = close / _shift(close, 20) - 1.0
    volume_ma20 = _rolling(volume, 20, "mean")
    volume_ratio = volume / np.where(volume_ma20 > 0, volume_ma20, np.nan)

    low30 = _rolling(low, 30, "min")
    high30 = _rolling(high, 30, "max")
    rsv30 = (close - low30) / (high30 - low30 + 1e-6) * 100.0
    k = _tdx_sma(rsv30, 3, 1)
    d = _tdx_sma(k, 3, 1)
    ema20 = _ema(close, 20)
    ema60 = _ema(close, 60)
    mhpg = (ema20 > ema60) & (ema60 > _shift(ema60, 2)) & (k > d) & (_shift(k, 1) <= _shift(d, 1)) & (k < 60)

    low8 = _rolling(low, 8, "min")
    high8 = _rolling(high, 8, "max")
    dxbd = (_ema((close - low8) / (high8 - low8 + 1e-6) * 100.0, 3) - 50.0) * 2.0
    dxbd_up = (dxbd > 0) & (_shift(dxbd, 1) <= 0)

    momentum = (close - _rolling(low, 2, "min")) / (_rolling(high, 4, "max") - _rolling(low, 4, "min") + 1e-6) * 100
    inter = _rolling((close - _rolling(low, 20, "min")) / (_rolling(high, 20, "max") - _rolling(low, 20, "min") + 1e-6) * 100, 5, "mean")
    near = _rolling((close - _rolling(low, 15, "min")) / (_rolling(high, 15, "max") - _rolling(low, 15, "min") + 1e-6) * 100, 2, "mean")
    leaving = ((_shift(momentum, 1) <= 20) & (momentum > _shift(momentum, 1))).astype(int)
    leaving += ((_shift(inter, 1) <= 20) & (inter > _shift(inter, 1))).astype(int)
    leaving += ((_shift(near, 1) <= 20) & (near > _shift(near, 1))).astype(int)
    low_zone = (leaving >= 2) & ((momentum <= 30) | (inter <= 30) | (near <= 30))
    current_spread = (np.maximum.reduce([ma5, ma10, ma20, ma60]) - np.minimum.reduce([ma5, ma10, ma20, ma60])) / ((ma5 + ma10 + ma20 + ma60) / 4 + 1e-6)
    mfk4 = low_zone | ((ma5 > ma20) & (ma10 > ma60) & (current_spread > _shift(current_spread, 1)) & (current_spread < 0.15))

    low9 = _rolling(low, 9, "min")
    high9 = _rolling(high, 9, "max")
    dingdi = _tdx_sma(_tdx_sma((close - low9) / (high9 - low9 + 1e-6) * 100, 3, 1), 3, 1)
    dingdi -= _tdx_sma(100 * (high9 - close) / (high9 - low9 + 1e-6), 9, 1) - 50
    dingdi_up = (dingdi < 50) & (dingdi > _shift(dingdi, 1))

    low17 = _rolling(low, 17, "min")
    low_diff = np.abs(np.diff(low, prepend=low[0]))
    low_up = np.maximum(np.diff(low, prepend=low[0]), 0)
    ratio = _tdx_sma(low_diff, 17, 1) / (_tdx_sma(low_up, 17, 2) + 1e-6)
    q = -np.where(low <= low17, ratio, -3.0)
    typical = (close + low + high) / 3
    d2 = _ema(typical, 6)
    d3 = _ema(d2, 5)
    gding = ((_shift(q, 1) <= 0) & (q > 0)) | ((_shift(d2, 1) <= _shift(d3, 1)) & (d2 > d3))
    start_count = mhpg.astype(int) + dxbd_up.astype(int) + mfk4.astype(int) + dingdi_up.astype(int) + gding.astype(int)

    bars = frame[["open", "high", "low", "close"]].to_dict("records")
    patterns = detect_bullish_patterns(bars)
    any_pattern = np.logical_or.reduce([np.asarray(values, dtype=bool) for values in patterns.values()])
    day_range = np.maximum(high - low, 1e-12)
    close_location = np.clip((close - low) / day_range, 0, 1)
    upper_shadow_pct = np.clip((high - np.maximum(open_, close)) / day_range, 0, 1)
    highest10 = _rolling(high, 10, "max")
    lowest10 = _rolling(low, 10, "min")
    drawdown10 = (highest10 - close) / highest10
    setup = (
        (close > ma20) & (ma20 > ma60) & (ma20 >= _shift(ma20, 5))
        & (ret20 >= 0.03) & (ret20 <= 0.30) & (drawdown10 >= 0.03) & (drawdown10 <= 0.10)
        & (lowest10 / ma60 >= 0.98) & any_pattern
    )
    money_flow = _ema(np.where(high == low, volume, (2 * close - high - low) / (high - low + 1e-6) * volume), 10)
    volume_ma60 = _rolling(volume, 60, "mean")
    no_start_risk = ~((dxbd > 60) | ((money_flow < 0) & (volume > volume_ma60)))

    date_strings = dates.dt.strftime("%Y-%m-%d").to_numpy()
    regime = np.asarray([regime_by_date.get(value, False) for value in date_strings], dtype=bool)
    universe = config["universe"]
    admitted = (
        (np.arange(n) + 1 >= int(universe["min_listing_days"]))
        & (close >= float(universe["min_close_cny"]))
        & (close <= float(universe["max_close_cny"]))
        & (adv20 >= float(universe["min_adv20_cny"]))
        & (trading60 >= float(universe["min_trading_days_60"]))
    )
    if bool(universe["block_suspensions"]):
        admitted &= tradestatus == "1"
    if bool(universe["exclude_st"]):
        admitted &= is_st == "0"
    if bool(universe["block_limit_up_entries"]):
        preclose = pd.to_numeric(frame["preclose"], errors="coerce").to_numpy(float)
        admitted &= ~((preclose > 0) & (close / preclose - 1.0 >= 0.095))
    features = {
        "admitted": admitted, "mhpg_buy": mhpg, "regime": regime, "no_start_risk": no_start_risk,
        "adv20": adv20, "close_location": close_location, "upper_shadow_pct": upper_shadow_pct,
        "volume_ratio": volume_ratio, "ret5": ret5, "start_count": start_count, "setup": setup,
    }
    masks = _strategy_masks(features)
    hit, t5_up = _future_label(close)
    years = dates.dt.year.to_numpy()
    in_dates = (date_strings >= start_date) & (date_strings <= (end_date or "9999-12-31"))
    valid = in_dates & (np.arange(n) < n - 5) & np.isfinite(close)
    if daily:
        maturity_dates = np.roll(date_strings, -5)
        signal_counts: dict[str, dict[str, list[int]]] = defaultdict(dict)
        maturity_counts: dict[str, dict[str, list[int]]] = defaultdict(dict)
        for strategy, strategy_mask in masks.items():
            for index in np.flatnonzero(valid & strategy_mask):
                signal_date = str(date_strings[index])
                maturity_date = str(maturity_dates[index])
                signal_counts[strategy][signal_date] = [1, int(hit[index])]
                maturity_cell = maturity_counts[strategy].setdefault(maturity_date, [0, 0])
                maturity_cell[0] += 1
                maturity_cell[1] += int(hit[index])
        return {
            "code": path.stem,
            "rows": int(valid.sum()),
            "dates": sorted(set(date_strings[valid])),
            "signal_counts": signal_counts,
            "maturity_counts": maturity_counts,
        }
    counts: dict[str, dict[str, list[int]]] = defaultdict(dict)
    for strategy, strategy_mask in masks.items():
        selected = valid & strategy_mask
        for split, (first_year, last_year) in SPLITS.items():
            mask = selected & (years >= first_year) & (years <= last_year)
            counts[strategy][split] = [int(mask.sum()), int(hit[mask].sum()), int(t5_up[mask].sum())]
        for year in range(2021, 2027):
            mask = selected & (years == year)
            counts[strategy][str(year)] = [int(mask.sum()), int(hit[mask].sum()), int(t5_up[mask].sum())]
    return {"code": path.stem, "rows": int(valid.sum()), "counts": counts}


def wilson_lower(hits: int, observations: int, z: float = 1.96) -> float | None:
    if observations == 0:
        return None
    rate = hits / observations
    denominator = 1 + z * z / observations
    centre = rate + z * z / (2 * observations)
    margin = z * math.sqrt(rate * (1 - rate) / observations + z * z / (4 * observations * observations))
    return (centre - margin) / denominator


def select_strategy(
    summaries: Mapping[str, Mapping[str, Mapping[str, Any]]],
    min_validation: int,
    min_year: int,
) -> tuple[str | None, list[dict[str, Any]]]:
    ranking: list[dict[str, Any]] = []
    baseline = summaries["admitted_baseline"]
    for name, periods in summaries.items():
        if name == "admitted_baseline":
            continue
        validation = periods["validation"]
        year_counts = [periods[str(year)]["n"] for year in (2023, 2024)]
        validation_year_lifts = [
            periods[str(year)]["hit_rate"] - baseline[str(year)]["hit_rate"]
            for year in (2023, 2024)
        ]
        calibration_lift = periods["calibration"]["hit_rate"] - baseline["calibration"]["hit_rate"]
        eligible = (
            validation["n"] >= min_validation
            and min(year_counts) >= min_year
            and min(validation_year_lifts) > 0
            and calibration_lift >= 0
        )
        ranking.append({
            "strategy": name,
            "eligible": eligible,
            "calibration_lift": round(calibration_lift, 6),
            "validation_n": validation["n"],
            "validation_hit_rate": validation["hit_rate"],
            "validation_wilson_lower_95": validation["wilson_lower_95"],
            "minimum_validation_year_lift": round(min(validation_year_lifts), 6),
            "minimum_validation_year_n": min(year_counts),
        })
    ranking.sort(key=lambda item: (
        bool(item["eligible"]),
        item["validation_wilson_lower_95"] if item["validation_wilson_lower_95"] is not None else -1,
        item["validation_n"],
    ), reverse=True)
    winner = ranking[0]["strategy"] if ranking and ranking[0]["eligible"] else None
    return winner, ranking


def _summarize(aggregate: Mapping[str, Mapping[str, list[int]]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for strategy, periods in aggregate.items():
        result[strategy] = {}
        for period, (n, hits, t5_hits) in periods.items():
            result[strategy][period] = {
                "n": n,
                "hits": hits,
                "false_positives": n - hits,
                "hit_rate": round(hits / n, 6) if n else None,
                "false_positive_rate": round(1 - hits / n, 6) if n else None,
                "t5_up_rate": round(t5_hits / n, 6) if n else None,
                "wilson_lower_95": round(wilson_lower(hits, n), 6) if n else None,
            }
    baseline = result["admitted_baseline"]
    for strategy, periods in result.items():
        for period, cell in periods.items():
            base_rate = baseline[period]["hit_rate"]
            cell["lift_vs_admitted"] = round(cell["hit_rate"] - base_rate, 6) if cell["hit_rate"] is not None and base_rate is not None else None
    return result


def main() -> None:
    args = parse_args()
    config = load_config(args.config)
    benchmark_path = args.data_root / f"{args.benchmark}.parquet"
    if not benchmark_path.exists():
        raise SystemExit(f"Benchmark data not found: {benchmark_path}")
    regime = _benchmark_regime(benchmark_path, config)
    paths = sorted(path for path in args.data_root.glob("*.parquet") if path.stem.startswith(PREFIXES))
    if args.max_codes is not None:
        paths = paths[:args.max_codes]
    tasks = [(str(path), config, regime, args.start_date, args.end_date) for path in paths]
    workers = max(1, min(args.workers, len(tasks) or 1))
    aggregate: dict[str, dict[str, list[int]]] = defaultdict(lambda: defaultdict(lambda: [0, 0, 0]))
    observations = 0
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as executor:
        for position, result in enumerate(executor.map(_stock_counts, tasks, chunksize=1), start=1):
            observations += result["rows"]
            for strategy, periods in result["counts"].items():
                for period, values in periods.items():
                    for index, value in enumerate(values):
                        aggregate[strategy][period][index] += value
            if position % 100 == 0 or position == len(tasks):
                print(f"processed={position}/{len(tasks)} observations={observations} workers={workers}", flush=True)
    summaries = _summarize(aggregate)
    selected, ranking = select_strategy(
        summaries,
        args.min_validation_observations,
        args.min_validation_year_observations,
    )
    result = {
        "study": "full_universe_joint_strategy_precision_v1",
        "classification_only": True,
        "label": "within_T_plus_1_to_T_plus_5_close_reaches_3pct_up_without_3pct_close_drawdown",
        "selection_protocol": {
            "calibration": "2021-2022 candidate design and sanity check",
            "validation": "2023-2024 strategy selection by 95pct Wilson lower bound",
            "holdout": "2025-2026 final one-time evaluation; not used for selection",
            "stability_gate": "positive lift in each validation year and nonnegative aggregate calibration lift",
            "min_validation_observations": args.min_validation_observations,
            "min_validation_year_observations": args.min_validation_year_observations,
        },
        "universe": {"current_main_board_files": len(paths), "all_eligible_dates": True},
        "benchmark_regime": args.benchmark,
        "date_range": {"start": args.start_date, "end": args.end_date},
        "observations_considered": observations,
        "selected_strategy": selected,
        "validation_ranking": ranking,
        "strategies": summaries,
        "known_biases": [
            "current-file-universe survivorship and historical-membership bias",
            "forward-adjusted equity history is not point-in-time adjustment-vintage data",
            "no point-in-time industry, event, fundamental, or delisting data",
            "overlapping five-day labels are correlated",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_name(f".{args.output.name}.tmp")
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(args.output)


if __name__ == "__main__":
    main()
