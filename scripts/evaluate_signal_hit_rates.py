#!/usr/bin/env python3
"""Leakage-aware T-day signal hit-rate study for the read-only research scanner.

This is a classification study, not a trading/backtest engine. It does not
model orders, positions, capital, costs, returns, or execution.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
import time
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from ashare_edge_scout.signals.candle_timing import evaluate_t_day_setup
from ashare_edge_scout.signals.candles import detect_bullish_patterns
from ashare_edge_scout.config import load_config
from ashare_edge_scout.signals.start_signals import compute_start_signals


PREFIXES = ("sh.600", "sh.601", "sh.603", "sh.605", "sz.000", "sz.001", "sz.002", "sz.003")
PATTERNS = ("hammer", "bullish_engulfing", "piercing", "morning_star")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=Path("PFrontStockData"))
    parser.add_argument("--config", type=Path, default=Path("yaml/edge_scout_v1.yaml"))
    parser.add_argument("--max-codes", type=int, default=400)
    parser.add_argument("--step", type=int, default=5)
    parser.add_argument("--workers", type=int, default=min(os.cpu_count() or 1, 12))
    parser.add_argument("--start-date", default="2018-01-01")
    parser.add_argument("--end-date", default=None)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--checkpoint-dir", type=Path, default=None)
    parser.add_argument("--resume", action="store_true", default=False)
    return parser.parse_args()


def stable_sample(paths: list[Path], max_codes: int) -> list[Path]:
    paths = [p for p in paths if p.stem.startswith(PREFIXES)]
    paths.sort(key=lambda p: hashlib.sha256(p.stem.encode()).hexdigest())
    return sorted(paths[:max_codes], key=lambda p: p.stem)


def numeric(frame: pd.DataFrame, name: str) -> list[float]:
    return pd.to_numeric(frame[name], errors="coerce").astype(float).tolist()


def observe(code: str, frame: pd.DataFrame, config: dict[str, Any], step: int, start: str, end: str | None) -> list[dict[str, Any]]:
    frame = frame.sort_values("date").reset_index(drop=True)
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.date
    frame = frame.dropna(subset=["date"])
    if len(frame) < 335:
        return []
    all_open = numeric(frame, "open")
    all_high = numeric(frame, "high")
    all_low = numeric(frame, "low")
    all_close = numeric(frame, "close")
    all_volume = numeric(frame, "volume")
    rows: list[dict[str, Any]] = []
    start_date = date.fromisoformat(start)
    end_date = date.fromisoformat(end) if end else None
    for index in range(330, len(frame) - 5, max(1, step)):
        signal_date = frame.at[index, "date"]
        if signal_date < start_date or (end_date and signal_date > end_date):
            continue
        close_t = all_close[index]
        future = all_close[index + 1:index + 6]
        if close_t <= 0 or len(future) != 5 or any(value <= 0 for value in future):
            continue
        history = [
            {"date": frame.at[i, "date"].isoformat(), "open": all_open[i], "high": all_high[i],
             "low": all_low[i], "close": all_close[i], "volume": all_volume[i]}
            for i in range(index + 1)
        ]
        patterns = detect_bullish_patterns(history)
        setup = evaluate_t_day_setup(history, config, patterns)
        starts = compute_start_signals(
            all_high[:index + 1], all_low[:index + 1], all_close[:index + 1], all_volume[:index + 1]
        )
        label = bool(max(future) >= close_t * 1.03 and min(future) >= close_t * 0.97)
        t5_up = bool(future[-1] > close_t)
        pattern_flags = {name: bool(patterns[name][-1]) for name in PATTERNS}
        rows.append({
            "code": code,
            "date": signal_date.isoformat(),
            "year": signal_date.year,
            "hit": label,
            "t5_up": t5_up,
            "any_pattern": any(pattern_flags.values()),
            **pattern_flags,
            "setup": bool(setup.valid),
            "start_count": starts.count,
            "dxbd_up": starts.dxbd_up,
            "gding_up": starts.gding_up,
            "dingdi_safe_up": starts.dingdi_safe_up,
            "mfk4_triggered": starts.mfk4_triggered,
            "mhpg_buy": starts.mhpg_buy,
        })
    return rows


def process_code(task: tuple[str, dict[str, Any], int, str, str | None]) -> list[dict[str, Any]]:
    code, config, step, start, end = task
    path = Path(code)
    frame = pd.read_parquet(path, columns=["date", "open", "high", "low", "close", "volume"])
    return observe(path.stem, frame, config, step, start, end)


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    features = [
        "any_pattern", *PATTERNS, "setup", "dxbd_up", "gding_up", "dingdi_safe_up",
        "mfk4_triggered", "mhpg_buy", "start_count_ge_2", "start_count_ge_3",
    ]
    for row in rows:
        row["start_count_ge_2"] = row["start_count"] >= 2
        row["start_count_ge_3"] = row["start_count"] >= 3

    def cell(items: list[dict[str, Any]]) -> dict[str, Any]:
        if not items:
            return {"n": 0, "hit_rate": None, "t5_rate": None}
        return {
            "n": len(items),
            "hit_rate": round(sum(bool(x["hit"]) for x in items) / len(items), 6),
            "t5_rate": round(sum(bool(x["t5_up"]) for x in items) / len(items), 6),
        }

    years: dict[str, Any] = {}
    for year in sorted({row["year"] for row in rows}):
        subset = [row for row in rows if row["year"] == year]
        baseline = cell(subset)
        signals: dict[str, Any] = {"baseline": baseline}
        for feature in features:
            signals[feature] = cell([row for row in subset if row[feature]])
        years[str(year)] = signals
    return {"observations": len(rows), "years": years}


def main() -> None:
    args = parse_args()
    paths = stable_sample(list(args.data_root.glob("*.parquet")), args.max_codes)
    config = load_config(args.config)
    rows: list[dict[str, Any]] = []
    output = args.output
    checkpoint_dir = args.checkpoint_dir or (output.parent / f".{output.name}.checkpoint" if output else Path(".runtime/signal-study.checkpoint"))
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = checkpoint_dir / "manifest.json"
    completed: set[str] = set()
    if args.resume and manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        completed = set(manifest.get("completed_codes", []))
        for code in sorted(completed):
            shard = checkpoint_dir / f"{code.replace('.', '_')}.json"
            if shard.exists():
                rows.extend(json.loads(shard.read_text(encoding="utf-8")))
            else:
                completed.discard(code)
    paths = [path for path in paths if path.stem not in completed]
    total_paths = len(paths) + len(completed)
    workers = max(1, min(args.workers, len(paths) or 1))
    tasks = [(str(path), config, args.step, args.start_date, args.end_date) for path in paths]
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(process_code, task): task[0]
            for task in tasks
        }
        for position, future in enumerate(concurrent.futures.as_completed(futures), start=1):
            code_rows = future.result()
            rows.extend(code_rows)
            code = Path(futures[future]).stem
            shard = checkpoint_dir / f"{code.replace('.', '_')}.json"
            shard_tmp = shard.with_suffix(".tmp")
            shard_tmp.write_text(json.dumps(code_rows, ensure_ascii=False), encoding="utf-8")
            shard_tmp.replace(shard)
            completed.add(code)
            if position % 10 == 0 or position == len(paths):
                manifest_tmp = manifest_path.with_suffix(".tmp")
                manifest_tmp.write_text(json.dumps({
                    "version": 1,
                    "updated_at": time.time(),
                    "completed_codes": sorted(completed),
                    "total_codes": total_paths,
                    "observations": len(rows),
                }, sort_keys=True), encoding="utf-8")
                manifest_tmp.replace(manifest_path)
                print(f"processed={len(completed)}/{total_paths} observations={len(rows)} workers={workers}", flush=True)
    result = {
        "study": "t_day_signal_hit_rate",
        "classification_only": True,
        "historical_research_only": True,
        "not_prospective_evidence": True,
        "no_execution_or_pnl": True,
        "raw_future_rows_exposed": False,
        "label_inputs_ephemeral": True,
        "label": "within_T_plus_1_to_T_plus_5_close_reaches_3pct_up_without_3pct_close_drawdown",
        "sampling": {"max_codes": args.max_codes, "actual_codes": len(paths), "step": args.step},
        "date_range": {"start": args.start_date, "end": args.end_date},
        "summary": summarize(rows),
    }
    rendered = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_name(f".{output.name}.tmp")
        temporary.write_text(rendered + "\n", encoding="utf-8")
        temporary.replace(output)
    else:
        print(rendered)


if __name__ == "__main__":
    main()
