#!/usr/bin/env python3
"""Evaluate which 30-minute entry window best hits a 4% target for MKF lag events.

Study question (user-directed): if the next-open price cannot be used as the entry
price, which 30-minute session window is the best time to buy?

Design (frozen before running):
- Event set: identical to the main MKF post-cross lag0..7 target grid
  (scripts/evaluate_mkf_post_cross_lag_target_grid.py): parent red/blue cross
  (mkf_red_blue_cross20_green_exit_under80_mask), lag0..7 stock-tradable signal
  rows, production_gate_mask hard gate at the signal row, entry = next stock-
  tradable day, one event per (lag, entry row), mature = full T+20 window.
  Events are built from local PFrontStockData daily bars, exactly as the
  published grid.
- Entry prices: 9 session prices on the entry day from BaoStock 5m bars
  (adjustflag=2, current-vintage forward adjusted, same price scale as
  PFrontStockData):
    open_0930 = 09:35 bar open (day open)
    w1000  = 10:05 bar open      w1030 = 10:35 bar open
    w1100  = 11:05 bar open      w1130 = 11:30 bar close (morning close)
    w1300  = 13:00 bar open      w1330 = 13:35 bar open
    w1400  = 14:05 bar open      w1430 = 14:35 bar open
- Target: fixed 4%. Hit for horizon T+k = max fresh daily high over T+1..T+k
  (panel dates, stock-tradable days after the entry day) >= entry_price * 1.04.
  Entry-day high is excluded (A-share T+1: a newly bought position cannot be sold
  the same day), non-hit return is fixed at 0% (target-zero method); no fees,
  slippage, stop loss, sizing, or fillability are modeled.
- Price-source consistency: entry prices and outcome highs both come from fresh
  BaoStock downloads (same current-vintage qfq), because PFrontStockData carries
  mixed adjustment vintages from incremental updates. The local baseline
  (panel entry_open + panel future highs) is reported separately as an exact
  replication of the published main grid for pipeline validation.

Subcommands:
  build-events  Build the main-grid event panel from local daily bars.
  fetch         Download BaoStock 5m + daily (adjustflag=2) per code; cached, resumable.
  evaluate      Join events with the caches and compute window hit metrics.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import csv
import hashlib
import json
import os
import sys
import tempfile
import time
from collections import Counter
from collections.abc import Sequence
from pathlib import Path
from typing import Any

for _name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_name] = "1"

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

import numpy as np
import pandas as pd

from ashare_edge_scout.config import load_config
from ashare_edge_scout.pmkf_mkf.mkf_post_cross_lag_comparison import (
    GRID_HORIZONS,
    LAGS,
    STABILITY_GATE_CONFIG,
    _stability_gate_result,
    build_mkf_post_cross_lag_target_grid_panel,
)
from ashare_edge_scout.research_precision70 import PREFIXES
from ashare_edge_scout.research_v2 import summarize_counts

SCHEMA_VERSION = "ncn_mkf_entry_window_30m_v1"
TARGET_PCT = 4
TARGET = TARGET_PCT / 100.0
MINUTE_FIELDS = "date,time,code,open,high,low,close,volume,amount,adjustflag"
DAILY_FIELDS = "date,code,open,high,low,close,preclose,volume,amount,adjustflag,tradestatus"
EXPECTED_5M_BARS = 48

# (window key, session label, 5m bar HHMM, price field: "open" | "close")
WINDOWS: list[tuple[str, str, str, str]] = [
    ("open_0930", "09:30", "0935", "open"),
    ("w1000", "10:00", "1005", "open"),
    ("w1030", "10:30", "1035", "open"),
    ("w1100", "11:00", "1105", "open"),
    ("w1130", "11:30", "1130", "close"),
    ("w1300", "13:00", "1300", "open"),
    ("w1330", "13:30", "1335", "open"),
    ("w1400", "14:00", "1405", "open"),
    ("w1430", "14:30", "1435", "open"),
]
WINDOW_KEYS = [key for key, _, _, _ in WINDOWS]
BASELINE_WINDOW = "open_daily_local"  # panel entry_open + panel (local) future highs
ALL_WINDOWS = [(BASELINE_WINDOW, "daily open (local panel; published main-grid baseline)")] + [
    (key, f"{label} (5m window start)") for key, label, _, _ in WINDOWS
]


# ------------------------------------------------------------------ utilities


def _atomic_write(path: Path, write_fn) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
            write_fn(handle)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def atomic_json(path: Path, value: Any) -> None:
    def write(handle) -> None:
        json.dump(value, handle, indent=2, sort_keys=True, allow_nan=False, default=str)
        handle.write("\n")

    _atomic_write(path, write)


def atomic_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    names = fieldnames or (list(rows[0]) if rows else [])

    def write(handle) -> None:
        if names:
            writer = csv.DictWriter(handle, fieldnames=names, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)

    _atomic_write(path, write)


def main_board_paths(data_root: Path) -> list[Path]:
    return sorted((path for path in data_root.glob("*.parquet") if path.stem.startswith(PREFIXES)), key=lambda path: path.stem)


def cache_file(cache_dir: Path, code: str, frequency: str) -> Path:
    return cache_dir / code.replace(".", "") / f"{frequency}.csv"


def _horizons() -> list[int]:
    return list(range(1, max(GRID_HORIZONS) + 1))


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--data-root", type=Path, default=ROOT / "PFrontStockData")
    common.add_argument("--config", type=Path, default=ROOT / "yaml/edge_scout_v1.yaml")
    common.add_argument("--output-dir", type=Path, required=True)

    p_build = sub.add_parser("build-events", parents=[common], help="Build the main-grid event panel.")
    p_build.add_argument("--start-date", default="2021-01-01")
    p_build.add_argument("--end-date", default=None)
    p_build.add_argument("--workers", type=int, default=min(os.cpu_count() or 1, 8))
    p_build.add_argument("--limit-codes", type=int, default=None)

    p_fetch = sub.add_parser("fetch", parents=[common], help="Fetch BaoStock 5m + daily qfq caches.")
    p_fetch.add_argument("--events", type=Path, required=True)
    p_fetch.add_argument("--start-date", default="2021-01-01")
    p_fetch.add_argument("--end-date", default=None)
    p_fetch.add_argument("--resume", action="store_true", help="Skip cache files that already exist.")
    p_fetch.add_argument("--limit-codes", type=int, default=None)
    p_fetch.add_argument("--sleep", type=float, default=0.2, help="Pause between BaoStock calls, seconds.")

    p_eval = sub.add_parser("evaluate", parents=[common], help="Compute window hit metrics from caches.")
    p_eval.add_argument("--events", type=Path, required=True)
    p_eval.add_argument("--cache-dir", type=Path, required=True)

    args = parser.parse_args(argv)
    if args.command == "build-events" and not 1 <= args.workers <= 16:
        parser.error("--workers must be between 1 and 16")
    return args


# ----------------------------------------------------------------- build-events


def _stock_panel(task: tuple[str, str, str, str | None]) -> tuple[pd.DataFrame, dict[str, int]]:
    path_text, config_json, start_date, end_date = task
    path = Path(path_text)
    frame = pd.read_parquet(path, columns=["date", "open", "high", "low", "close", "preclose", "volume", "amount", "tradestatus", "isST"])
    panel = build_mkf_post_cross_lag_target_grid_panel(path.stem, frame, json.loads(config_json), start_date=start_date, end_date=end_date)
    return panel, {str(key): int(value) for key, value in panel.attrs.get("diagnostics", {}).items()}


def cmd_build_events(args: argparse.Namespace) -> None:
    paths = main_board_paths(args.data_root)
    if args.limit_codes is not None:
        paths = paths[: args.limit_codes]
    if not paths:
        raise SystemExit("no main-board parquet files found")
    config_json = json.dumps(load_config(args.config))
    tasks = [(str(path), config_json, args.start_date, args.end_date) for path in paths]
    panels: list[pd.DataFrame] = []
    diagnostics: Counter[str] = Counter()
    with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers) as executor:
        for completed, (panel, stock_diagnostics) in enumerate(executor.map(_stock_panel, tasks, chunksize=1), start=1):
            panels.append(panel)
            diagnostics.update(stock_diagnostics)
            if completed % 100 == 0 or completed == len(tasks):
                print(f"processed {completed}/{len(tasks)} codes", flush=True)
    panel = pd.concat(panels, ignore_index=True) if panels else pd.DataFrame()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    panel.to_parquet(args.output_dir / "events.parquet", index=False)
    code_list = [path.stem for path in paths]
    atomic_json(args.output_dir / "diagnostics.json", {
        "schema_version": SCHEMA_VERSION,
        "codes": len(code_list),
        "code_list_sha256": hashlib.sha256(("\n".join(code_list) + "\n").encode("ascii")).hexdigest(),
        "start_date": args.start_date,
        "end_date": args.end_date,
        "workers": args.workers,
        "diagnostics": dict(diagnostics),
        "status_counts": {str(key): int(value) for key, value in panel["status"].value_counts().items()},
    })
    print(f"events={len(panel)} mature={int((panel['status'] == 'mature').sum())} codes={len(code_list)}")


# ----------------------------------------------------------------------- fetch


def fetch_baostock(code: str, frequency: str, fields: str, start_date: str, end_date: str, retries: int = 3) -> tuple[list[list[str]], str, str]:
    import baostock as bs

    rs = None
    for attempt in range(1, retries + 1):
        rs = bs.query_history_k_data_plus(code, fields, start_date=start_date, end_date=end_date, frequency=frequency, adjustflag="2")
        if rs.error_code == "0":
            rows = []
            while rs.error_code == "0" and rs.next():
                rows.append(rs.get_row_data())
            return rows, rs.error_code, rs.error_msg
        if attempt < retries:
            time.sleep(1.5 * attempt)
    return [], str(rs.error_code), str(rs.error_msg)


def cmd_fetch(args: argparse.Namespace) -> None:
    try:
        import baostock as bs
    except ImportError:
        raise SystemExit("baostock is not installed in this environment")

    events = pd.read_parquet(args.events)
    mature = events.loc[events["status"].eq("mature")].copy()
    if mature.empty:
        raise SystemExit("no mature events in events file")
    mature["entry_ts"] = pd.to_datetime(mature["entry_date"], errors="coerce")
    by_code = {code: group for code, group in mature.groupby("code")}
    if args.limit_codes is not None:
        by_code = dict(list(by_code.items())[: args.limit_codes])

    max_horizon = max(GRID_HORIZONS)
    summary_rows: list[dict[str, Any]] = []
    login = bs.login()
    if login.error_code != "0":
        raise SystemExit(f"baostock login failed: {login.error_code} {login.error_msg}")
    print(f"baostock login ok; codes={len(by_code)}", flush=True)
    try:
        for number, (code, group) in enumerate(sorted(by_code.items()), start=1):
            minute_end = group["entry_ts"].max().strftime("%Y-%m-%d")
            daily_end = (group["entry_ts"].max() + pd.Timedelta(days=max_horizon * 3 + 20)).strftime("%Y-%m-%d")
            if args.end_date:
                minute_end = min(minute_end, args.end_date)
                daily_end = min(daily_end, args.end_date)
            for frequency, fields, end_date in (("5m", MINUTE_FIELDS, minute_end), ("d", DAILY_FIELDS, daily_end)):
                path = cache_file(args.output_dir / "cache", code, frequency)
                status, error_code, error_msg, row_count = "missing", "", "", 0
                if args.resume and path.is_file() and path.stat().st_size > 0:
                    status = "cache_hit"
                    with path.open(newline="", encoding="utf-8") as handle:
                        row_count = sum(1 for _ in handle) - 1
                else:
                    rows, error_code, error_msg = fetch_baostock(code, "5" if frequency == "5m" else "d", fields, args.start_date, end_date)
                    status = "downloaded" if error_code == "0" else "download_error"
                    row_count = len(rows)
                    if error_code == "0":
                        atomic_csv(path, [dict(zip(fields.split(","), row, strict=True)) for row in rows], fields.split(","))
                        if args.sleep:
                            time.sleep(args.sleep)
                summary_rows.append({
                    "code": code, "frequency": frequency, "status": status,
                    "error_code": error_code, "error_msg": error_msg,
                    "start_date": args.start_date, "end_date": end_date, "row_count": row_count,
                    "cache_path": str(path),
                })
            if number % 25 == 0 or number == len(by_code):
                print(f"fetched {number}/{len(by_code)} codes", flush=True)
    finally:
        try:
            bs.logout()
        except Exception:
            pass
    atomic_csv(args.output_dir / "cache_summary.csv", summary_rows)
    print(json.dumps({"codes": len(by_code), "status_counts": dict(Counter(row["status"] for row in summary_rows))}, ensure_ascii=False))


# -------------------------------------------------------------------- evaluate


def _parse_5m_cache(path: Path) -> dict[str, dict[str, tuple[float, float, float, float]]]:
    if not path.is_file():
        return {}
    rows = pd.read_csv(path, dtype={"time": str}, low_memory=False)
    if rows.empty:
        return {}
    rows["hhmm"] = rows["time"].str[8:12]
    aggregated = rows.groupby(["date", "hhmm"], sort=False).agg(
        open_=("open", "first"), high=("high", "max"), low=("low", "min"), close=("close", "last")
    )
    result: dict[str, dict[str, tuple[float, float, float, float]]] = {}
    for (date_text, hhmm), (open_, high, low, close) in aggregated.iterrows():
        result.setdefault(str(date_text), {})[hhmm] = (float(open_), float(high), float(low), float(close))
    return result


def window_prices(bars: dict[str, tuple[float, float, float, float]]) -> dict[str, float | None]:
    prices: dict[str, float | None] = {}
    for key, _, bar_hhmm, field in WINDOWS:
        bar = bars.get(bar_hhmm)
        if bar is None:
            prices[key] = None
            continue
        value = bar[0] if field == "open" else bar[3]
        prices[key] = float(value) if np.isfinite(value) and value > 0 else None
    return prices


def _parse_daily_cache(path: Path) -> dict[str, tuple[float, str]]:
    if not path.is_file():
        return {}
    rows = pd.read_csv(path, dtype=str, low_memory=False)
    if rows.empty:
        return {}
    result: dict[str, tuple[float, str]] = {}
    for date_text, high, trade in zip(rows["date"], rows["high"], rows.get("tradestatus", [""] * len(rows))):
        try:
            result[str(date_text)] = (float(high), str(trade))
        except (TypeError, ValueError):
            continue
    return result


def _metric_block(n: int, hits: int, entry_dates: int, codes: int) -> dict[str, Any]:
    counts = summarize_counts(n, hits)
    hit_rate = counts["precision"]
    return {
        "n": counts["n"],
        "target_hits": counts["hits"],
        "target_hit_rate": hit_rate,
        "target_hit_wilson_lower_95": counts["wilson_lower_95"],
        "target_hit_wilson_upper_95": counts["wilson_upper_95"],
        "mean_target_zero_return": TARGET * hit_rate if hit_rate is not None else None,
        "entry_dates": entry_dates,
        "codes": codes,
    }


def _period_bounds(frame: pd.DataFrame) -> dict[str, tuple[int, int] | None]:
    years = sorted(int(year) for year in pd.to_datetime(frame["entry_date"], errors="coerce").dropna().dt.year.unique())
    if not years:
        return {"full_period": None}
    return {
        "full_period": None,
        "selection_2021_2023": (2021, 2023),
        "audit_2024_present": (2024, years[-1]),
        **{f"year_{year}": (year, year) for year in years},
    }


def cmd_evaluate(args: argparse.Namespace) -> None:
    horizons = _horizons()
    events = pd.read_parquet(args.events)
    mature = events.loc[events["status"].eq("mature")].copy().reset_index(drop=True)
    if mature.empty:
        raise SystemExit("no mature events")

    entry_ts = pd.to_datetime(mature["entry_date"], errors="coerce")
    entry_date_text = entry_ts.dt.strftime("%Y-%m-%d")
    lags = mature["post_cross_lag"].to_numpy()
    entry_codes = mature["code"].to_numpy()
    entry_dates_u = entry_date_text.to_numpy()
    entry_open_local = pd.to_numeric(mature["entry_open"], errors="coerce").to_numpy(dtype=float)
    date_columns = [f"date_t{step}" for step in horizons]

    # Fresh cumulative max highs: for each event and step, max of fresh daily
    # highs over the panel's T+1..T+k dates (tradable in the fresh daily file).
    fresh_cum = np.full((len(mature), len(horizons)), np.nan)
    missing_steps = np.zeros(len(mature), dtype=int)
    bar_counts = np.zeros(len(mature), dtype=int)
    window_values = np.full((len(mature), len(WINDOW_KEYS)), np.nan)
    day_open_5m = np.full(len(mature), np.nan)
    for code in sorted(mature["code"].unique()):
        mask = (mature["code"] == code).to_numpy()
        indices = np.flatnonzero(mask)
        stem = code.replace(".", "")
        bars_by_date = _parse_5m_cache(args.cache_dir / stem / "5m.csv")
        daily_by_date = _parse_daily_cache(args.cache_dir / stem / "d.csv")
        for position in indices:
            entry_text = entry_date_text.iat[position]
            bars = bars_by_date.get(entry_text, {})
            bar_counts[position] = len(bars)
            prices = window_prices(bars)
            for column, key in enumerate(WINDOW_KEYS):
                window_values[position, column] = prices.get(key) if prices.get(key) is not None else np.nan
            day_open_5m[position] = prices.get("open_0930") if prices.get("open_0930") is not None else np.nan
            running: float = float("nan")
            for step, column in enumerate(horizons):
                date_text = pd.Timestamp(mature.iat[position][date_columns[step]]).strftime("%Y-%m-%d")
                fresh = daily_by_date.get(date_text)
                value = fresh[0] if fresh is not None and fresh[1] == "1" and np.isfinite(fresh[0]) else float("nan")
                running = value if not np.isfinite(running) else max(running, value)
                fresh_cum[position, step] = running
                if not np.isfinite(value):
                    missing_steps[position] += 1

    # Panel (local) cumulative max highs for the published-grid baseline.
    local_highs = pd.concat([pd.to_numeric(mature[f"future_high_t{step}"], errors="coerce") for step in horizons], axis=1).to_numpy(dtype=float)
    local_cum = np.fmax.accumulate(np.where(np.isnan(local_highs), -np.inf, local_highs), axis=1)
    local_cum = np.where(local_cum < -np.inf / 2, np.nan, local_cum)

    # Cross-check: entry-day 5m open vs local panel open (vintage consistency).
    both = np.isfinite(day_open_5m) & np.isfinite(entry_open_local) & (entry_open_local > 0)
    open_ratio = day_open_5m[both] / entry_open_local[both] - 1.0

    entry_years = entry_ts.dt.year.to_numpy()
    years_observed = sorted(int(year) for year in np.unique(entry_years))
    periods = _period_bounds(mature)
    period_masks: dict[str, np.ndarray] = {
        name: (np.ones(len(mature), dtype=bool) if bounds is None else entry_years >= bounds[0]) & (np.ones(len(mature), dtype=bool) if bounds is None else entry_years <= bounds[1])
        for name, bounds in periods.items()
    }
    lag_masks = {lag: lags == lag for lag in LAGS}

    # Entry price array per window; baseline uses the local panel open.
    window_arrays = {key: window_values[:, column] for column, key in enumerate(WINDOW_KEYS)}
    window_arrays[BASELINE_WINDOW] = entry_open_local
    # Outcome array per window: fresh for 5m windows, local for the baseline.
    outcome_arrays = {key: fresh_cum for key in WINDOW_KEYS}
    outcome_arrays[BASELINE_WINDOW] = local_cum

    bar_count_counts = Counter(int(value) for value in bar_counts)
    missing_counts = Counter("0" if value == 0 else f"{value}" for value in missing_steps)

    # Per window: valid denominator (finite entry price and complete fresh/high
    # coverage through T+k) and hit booleans for every horizon.
    summary_rows: list[dict[str, Any]] = []
    per_window_t20: dict[str, dict[str, dict[str, Any]]] = {}
    for window_key, _ in ALL_WINDOWS:
        entry_values = window_arrays[window_key]
        outcomes = outcome_arrays[window_key]
        valid_base = np.isfinite(entry_values) & (entry_values > 0)
        entry_date_arrays = entry_dates_u
        for lag in LAGS:
            per_period: dict[str, dict[str, Any]] = {}
            for period in periods:
                group_mask = lag_masks[lag] & period_masks[period] & valid_base
                metrics_by_period_for_gate: dict[str, dict[str, Any]] = {}
                t20_metrics: dict[str, Any] | None = None
                for horizon, step in enumerate(horizons, start=1):
                    valid = group_mask & np.isfinite(outcomes[:, step])
                    n = int(valid.sum())
                    hits = int((outcomes[:, step][valid] >= entry_values[valid] * (1.0 + TARGET)).sum()) if n else 0
                    entry_dates_n = int(np.unique(entry_date_arrays[valid]).size) if n else 0
                    codes_n = int(np.unique(entry_codes[valid]).size) if n else 0
                    metrics = _metric_block(n, hits, entry_dates_n, codes_n)
                    summary_rows.append({"lag": lag, "period": period, "horizon": f"T+{horizon}", "window": window_key, **metrics})
                    if horizon == 20:
                        t20_metrics = metrics
                if t20_metrics is not None:
                    per_period[period] = t20_metrics
            if per_period:
                gate = _stability_gate_result({period: (per_period.get(period) or _metric_block(0, 0, 0, 0)) for period in periods})
                per_window_t20[window_key] = {"periods": per_period, "gate": gate}

    summary = pd.DataFrame(summary_rows)
    primary_horizons = {f"T+{step}" for step in (5, 10, 20)}
    primary = summary.loc[summary["horizon"].isin(primary_horizons)].copy()

    # Best-window readout at T+20 with the pre-registered stability gates.
    ranked: list[dict[str, Any]] = []
    for window_key, window_label in ALL_WINDOWS:
        state = per_window_t20.get(window_key)
        if not state:
            continue
        full = state["periods"].get("full_period", _metric_block(0, 0, 0, 0))
        ranked.append({
            "window": window_key,
            "window_label": window_label,
            "full_period": full,
            "stability_gate": state["gate"],
        })
    ranked.sort(key=lambda item: (item["full_period"].get("mean_target_zero_return") or -1.0), reverse=True)

    ratio_series = pd.Series(open_ratio, dtype=float)
    report = {
        "schema_version": SCHEMA_VERSION,
        "study": "mkf_entry_window_30m_target4_hit_study",
        "research_only": True,
        "production_enabled": False,
        "broker_orders_enabled": False,
        "watchlist_modified": False,
        "thresholds_tuned": False,
        "original_mkf_selector_modified": False,
        "target_pct": TARGET_PCT,
        "windows": [{"key": key, "label": label, "bar_hhmm": bar, "field": field} for key, label, bar, field in WINDOWS],
        "baseline_window": BASELINE_WINDOW,
        "entry_definition": {
            "entry_prices": "9 session prices on the entry day from BaoStock 5m (adjustflag=2 current-vintage qfq) at window starts; 11:30 uses the 11:30 bar close (morning close)",
            "target_hit": f"max fresh BaoStock daily high over T+1..T+k (panel dates, tradable days) >= entry_price * (1 + {TARGET_PCT}%)",
            "baseline": f"{BASELINE_WINDOW} = panel entry_open with panel (local) future highs; exact replication of the published main grid",
            "entry_day_high": "excluded (A-share T+1 rule, same as main grid)",
            "non_hit_return": "fixed 0% (target-zero method); mean_target_zero_return = 4% * hit_rate",
            "fees_slippage_tax_fillability": "not modeled",
        },
        "source_consistency": {
            "entry_day_5m_open_vs_local_open": {
                "n": int(both.sum()),
                "median_abs_pct": float(np.abs(open_ratio).median() * 100) if both.any() else None,
                "mean_abs_pct": float(np.abs(open_ratio).mean() * 100) if both.any() else None,
                "pct_over_0.2": float((np.abs(open_ratio) > 0.002).mean()) if both.any() else None,
                "pct_over_0.5": float((np.abs(open_ratio) > 0.005).mean()) if both.any() else None,
                "max_abs_pct": float(np.abs(open_ratio).max() * 100) if both.any() else None,
            },
            "note": "Nonzero differences reflect mixed PFrontStockData adjustment vintages from incremental updates; all window comparisons use fresh BaoStock qfq for both entry and outcome prices.",
        },
        "sample": {
            "mature_events": int(len(mature)),
            "codes": int(mature["code"].nunique()),
            "entry_day_5m_bar_count_counts": {str(key): int(value) for key, value in sorted(bar_count_counts.items(), key=lambda item: int(item[0]))},
            "fresh_daily_missing_step_counts": {key: int(value) for key, value in sorted(missing_counts.items())},
        },
        "stability_gates": dict(STABILITY_GATE_CONFIG),
        "best_window_readout_t20": {
            "method": "Rank windows by full-period mean_target_zero_return at T+20; a window may be named only if it passes the pre-registered stability gates.",
            "ranked": ranked,
            "warning": "In-sample descriptive research only; not an execution recommendation or production rule without separate out-of-sample validation.",
        },
        "limitations": [
            "Entry 5m prices are reference prices, not live fill evidence; limit-up fillability, queueing, spread, fees, slippage, tax, sizing, and stop loss are not modeled.",
            "All windows keep the same T+k day window by design (matching the main-grid target-touch definition); a late entry therefore leaves less same-day time, which is part of what is being compared.",
            "Fresh BaoStock qfq outcome highs replace local mixed-vintage highs for all 5m windows; the local baseline window is reported for exact replication of the published main grid.",
            "Current-file survivorship bias of the local parquet universe remains.",
            "Any best window must pass the stability gates and separate out-of-sample validation before production use.",
        ],
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    atomic_csv(args.output_dir / "window_summary_full.csv", summary_rows)
    atomic_csv(args.output_dir / "window_summary_primary.csv", primary.to_dict(orient="records"))
    atomic_json(args.output_dir / "report.json", report)
    print(json.dumps({
        "mature_events": int(len(mature)),
        "primary_rows": int(len(primary)),
        "best_window_t20": ranked[0]["window"] if ranked else None,
    }, ensure_ascii=False, indent=2))


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    dispatch = {
        "build-events": cmd_build_events,
        "fetch": cmd_fetch,
        "evaluate": cmd_evaluate,
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()
