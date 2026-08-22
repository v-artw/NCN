#!/usr/bin/env python3
"""Evaluate exact preregistered Precision 70 Stage 1 classification rules."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import tempfile
from pathlib import Path
from collections.abc import Mapping, Sequence
from typing import Any

BLAS_THREAD_VARIABLES = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS")
for _thread_variable in BLAS_THREAD_VARIABLES:
    os.environ[_thread_variable] = "1"

import pandas as pd

from ashare_edge_scout.config import load_config
from ashare_edge_scout.research_precision70 import (
    CANDIDATES, PERIODS, add_cross_sectional_features, aggregate_metrics,
    build_stock_panel, candidate_masks, evaluate_decision, stable_sample,
)


REQUIRED_COLUMNS = ["date", "open", "high", "low", "close", "preclose", "volume", "amount", "tradestatus", "isST"]


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=Path("PFrontStockData"))
    parser.add_argument("--config", type=Path, default=Path("yaml/edge_scout_v1.yaml"))
    parser.add_argument("--max-codes", type=int, default=400)
    parser.add_argument("--workers", type=int, default=min(os.cpu_count() or 1, 8))
    parser.add_argument("--start-date", default="2021-01-01")
    parser.add_argument("--end-date", default=None)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.max_codes != 400:
        parser.error("--max-codes must equal 400")
    if not 1 <= args.workers <= 8:
        parser.error("--workers must be between 1 and 8")
    return args


def _benchmark_returns(path: Path) -> dict[pd.Timestamp, float]:
    frame = pd.read_parquet(path, columns=["date", "close"])
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame["close"] = pd.to_numeric(frame["close"], errors="coerce")
    frame = frame.dropna().sort_values("date", kind="stable").drop_duplicates("date", keep="last")
    frame["ret20"] = frame["close"].div(frame["close"].shift(20)).sub(1.0)
    return dict(zip(frame["date"], frame["ret20"], strict=True))


def _evaluate_stock(task: tuple[str, dict[str, Any], dict[pd.Timestamp, float], str, str | None]) -> pd.DataFrame:
    path_text, config, benchmark, start_date, end_date = task
    path = Path(path_text)
    frame = pd.read_parquet(path, columns=REQUIRED_COLUMNS)
    return build_stock_panel(path.stem, frame, config, benchmark, start_date=start_date, end_date=end_date)


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="ascii") as handle:
            json.dump(value, handle, indent=2, sort_keys=True, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def _limit_blas_threads() -> None:
    for name in BLAS_THREAD_VARIABLES:
        os.environ[name] = "1"


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    _limit_blas_threads()
    paths = stable_sample(list(args.data_root.glob("*.parquet")), args.max_codes)
    benchmark_path = args.data_root / "sh.000905.parquet"
    if not benchmark_path.is_file():
        raise SystemExit(f"benchmark file not found: {benchmark_path}")
    benchmark = _benchmark_returns(benchmark_path)
    config = load_config(args.config)
    tasks = [(str(path), config, benchmark, args.start_date, args.end_date) for path in paths]
    with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers) as executor:
        stock_panels = list(executor.map(_evaluate_stock, tasks, chunksize=1))
    panel = add_cross_sectional_features(pd.concat(stock_panels, ignore_index=True))
    masks = candidate_masks(panel)
    summaries, sensitivity = aggregate_metrics(panel, masks)
    decisions = evaluate_decision(summaries, sensitivity)
    denominators = panel.loc[panel["daily_denominator"].ge(150)].groupby("date")["daily_denominator"].first()
    report = {
        "study": "precision70_stage1",
        "classification_only": True,
        "sample": {"method": "sha256_code_stem", "codes": len(paths), "code_list": [path.stem for path in paths]},
        "workers": args.workers,
        "periods": PERIODS,
        "candidate_definitions": {
            CANDIDATES[0]: {
                "breadth": "above_sma20>=0.60; above_sma60>=0.50; acceleration_5_panel_dates>=0.05; median_ret5>0",
                "stock": "close>sma20>sma60; both slopes T-5 positive; ret20 pct [0.80,0.98); ret5 pct [0.60,0.95); ret20-benchmark_ret20>0; bullish; close_location>=0.65; upper_shadow<=0.25; volume_ratio [1.0,2.5]",
            },
            CANDIDATES[1]: {
                "breadth": "same as breadth_residual_leadership",
                "stock": "close>sma20>sma60; both slopes T-5 positive; ret20 pct [0.70,0.95); ret_T-3_to_T-1 [-0.06,-0.01]; T return [0.01,0.05]; close>previous_high; bullish; close_location>=0.70; upper_shadow<=0.20; volume_ratio [0.9,2.2]",
            },
            CANDIDATES[2]: {
                "breadth": "none beyond daily denominator>=150",
                "stock": "latest 252 origins matured strictly before T; prior_n>=120; posterior=(hits+10)/(n+30)>=0.45 and daily pct>=0.95; close>sma20; ret5 [-0.03,0.08]",
            },
        },
        "date_coverage": {
            "requested_start": args.start_date, "requested_end": args.end_date,
            "observed_start": panel["date"].min().strftime("%Y-%m-%d") if len(panel) else None,
            "observed_end": panel["date"].max().strftime("%Y-%m-%d") if len(panel) else None,
        },
        "daily_denominator": {
            "valid_dates": len(denominators),
            "min": int(denominators.min()) if len(denominators) else None,
            "median": float(denominators.median()) if len(denominators) else None,
            "max": int(denominators.max()) if len(denominators) else None,
        },
        "summaries": summaries,
        "nonoverlapping_origin_sensitivity": sensitivity,
        "decision": decisions,
        "source_and_caveats": [
            "Adjusted local PFrontStockData Parquet and sh.000905 benchmark; research classification only.",
            "Future labels skip suspension rows; provider data quality and survivorship of current files remain limitations.",
            "Holdout metrics are immutable audit output and are not used to redesign or grant selection eligibility.",
            "Nearby labels overlap; per-stock five-tradable-date spacing is reported separately.",
        ],
    }
    _atomic_json(args.output, report)


if __name__ == "__main__":
    main()
