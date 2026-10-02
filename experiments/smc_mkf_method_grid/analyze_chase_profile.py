#!/usr/bin/env python3
"""Quantify how "chasing highs" SMC parent signals are vs MKF parent signals.

For every parent-signal row in 2015-01-01..2026-09-22 (main board), compute the
signal-day position: same-day jump, prior 20-day run-up, distance above the
prior 20-day high, 52-week range position, and the next tradable open gap we
would pay to enter. SMC parent = production_smc_mask (gate AND smc_medium_buy,
same as the lag-grid arm). MKF parent = mkf_red_blue_cross20_green_exit_under80_mask.
Read-only research; local PFrontStockData.
"""

from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from ashare_edge_scout.config import load_config  # noqa: E402
from ashare_edge_scout.pmkf_mkf.mkf_smc_annual_comparison import production_smc_mask  # noqa: E402
from ashare_edge_scout.pmkf_mkf.research import mkf_red_blue_cross20_green_exit_under80_mask  # noqa: E402
from ashare_edge_scout.pmkf_mkf.quality import normalise_stock_frame  # noqa: E402
from ashare_edge_scout.research_precision70 import PREFIXES  # noqa: E402

START = "2015-01-01"
END = "2026-09-22"
METRIC_KEYS = ("day_ret", "runup20", "above_hh20", "range_pos_252", "entry_gap")


def _stats_for_signal_rows(data: pd.DataFrame, signal: pd.Series) -> dict[str, np.ndarray]:
    rows = data.index[signal.fillna(False)]
    if len(rows) == 0:
        return {k: np.array([], dtype=float) for k in METRIC_KEYS}
    close = pd.to_numeric(data["close"], errors="coerce")
    preclose = pd.to_numeric(data["preclose"], errors="coerce")
    high = pd.to_numeric(data["high"], errors="coerce")
    low = pd.to_numeric(data["low"], errors="coerce")
    open_ = pd.to_numeric(data["open"], errors="coerce")
    trade = data.get("tradestatus", pd.Series(index=data.index, dtype=object)).astype("string")
    tradable = trade.eq("1").fillna(False)
    day_ret = (close / preclose - 1.0).to_numpy(dtype=float)
    runup20 = (close / close.shift(20) - 1.0).to_numpy(dtype=float)
    hh20_prior = high.rolling(20, min_periods=15).max().shift(1).to_numpy(dtype=float)
    close_np = close.to_numpy(dtype=float)
    above_hh20 = np.where(np.isfinite(hh20_prior) & (hh20_prior > 0), close_np / hh20_prior - 1.0, np.nan)
    lo252 = low.rolling(252, min_periods=120).min().to_numpy(dtype=float)
    hi252 = high.rolling(252, min_periods=120).max().to_numpy(dtype=float)
    with np.errstate(invalid="ignore", divide="ignore"):
        range_pos = np.where(hi252 > lo252, (close_np - lo252) / (hi252 - lo252), np.nan)
    # next tradable row after the signal row (entry bar used by the lag0 arm)
    idx = pd.Series(np.arange(len(data)), index=data.index)
    tradable_positions_sorted = np.flatnonzero(tradable.to_numpy())
    entry_gap = np.full(len(data), np.nan, dtype=float)
    open_np = open_.to_numpy(dtype=float)
    for r in rows:
        pos = int(idx.iat[r])
        j = np.searchsorted(tradable_positions_sorted, pos + 1, side="left")
        if j < len(tradable_positions_sorted):
            e = int(tradable_positions_sorted[j])
            if np.isfinite(open_np[e]) and open_np[e] > 0 and np.isfinite(close_np[r]) and close_np[r] > 0:
                entry_gap[r] = open_np[e] / close_np[r] - 1.0
    return {
        "day_ret": day_ret[rows],
        "runup20": runup20[rows],
        "above_hh20": above_hh20[rows],
        "range_pos_252": range_pos[rows],
        "entry_gap": entry_gap[rows],
    }


def analyse_file(args: tuple[str, dict[str, Any]]) -> dict[str, dict[str, np.ndarray]]:
    path_text, config = args
    code = Path(path_text).stem
    try:
        frame = pd.read_parquet(path_text)
        data = normalise_stock_frame(frame)
    except Exception:
        return {}
    dates = pd.to_datetime(data["date"], errors="coerce")
    window = (dates >= pd.Timestamp(START)) & (dates <= pd.Timestamp(END))
    out: dict[str, dict[str, np.ndarray]] = {}
    for family, signal in (
        ("smc", production_smc_mask(code, data, config)),
        ("mkf", mkf_red_blue_cross20_green_exit_under80_mask(data)),
    ):
        sig = signal.copy()
        sig[~window.fillna(False)] = False
        out[family] = _stats_for_signal_rows(data, sig)
    return out


def summarize(values: np.ndarray) -> dict[str, Any]:
    v = values[np.isfinite(values)]
    if len(v) == 0:
        return {"n": 0}
    return {
        "n": int(len(v)),
        "mean_pct": round(float(np.mean(v)) * 100, 2),
        "median_pct": round(float(np.median(v)) * 100, 2),
        "p75_pct": round(float(np.percentile(v, 75)) * 100, 2),
        "p90_pct": round(float(np.percentile(v, 90)) * 100, 2),
        "share_gt_3pct": round(float(np.mean(v > 0.03)) * 100, 1),
        "share_gt_5pct": round(float(np.mean(v > 0.05)) * 100, 1),
    }


def summarize_pos(values: np.ndarray) -> dict[str, Any]:
    v = values[np.isfinite(values)]
    if len(v) == 0:
        return {"n": 0}
    return {
        "n": int(len(v)),
        "mean": round(float(np.mean(v)), 3),
        "median": round(float(np.median(v)), 3),
        "share_above_0.9": round(float(np.mean(v > 0.9)) * 100, 1),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=Path("PFrontStockData"))
    parser.add_argument("--config", type=Path, default=Path("yaml/edge_scout_v1.yaml"))
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    paths = sorted(str(p) for p in args.data_root.glob("*.parquet") if p.stem.split(".")[-1].startswith(tuple(PREFIXES)) or p.stem.startswith(tuple(PREFIXES)))
    config = load_config(args.config)
    collected: dict[str, dict[str, list[np.ndarray]]] = {
        fam: {k: [] for k in METRIC_KEYS} for fam in ("smc", "mkf")
    }
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for res in pool.map(analyse_file, ((p, config) for p in paths), chunksize=8):
            for fam, metrics in res.items():
                for k, arr in metrics.items():
                    if len(arr):
                        collected[fam][k].append(arr)

    report: dict[str, Any] = {"window": [START, END], "files": len(paths), "families": {}}
    for fam, metrics in collected.items():
        joined = {k: np.concatenate(v) if v else np.array([], dtype=float) for k, v in metrics.items()}
        fam_report = {"signals": int(len(joined["day_ret"]))}
        for k in ("day_ret", "runup20", "entry_gap", "above_hh20"):
            fam_report[k] = summarize(joined[k])
        fam_report["range_pos_252"] = summarize_pos(joined["range_pos_252"])
        report["families"][fam] = fam_report

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
