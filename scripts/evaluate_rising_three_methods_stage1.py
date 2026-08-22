#!/usr/bin/env python3
"""Evaluate preregistered strict rising-three-methods Stage 1 classification."""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import pandas as pd

from ashare_edge_scout.config import load_config
from ashare_edge_scout.research_rising_three import (
    AGGREGATE,
    CALIBRATION,
    HOLDOUT,
    YEARS,
    benchmark_regime_through_t,
    classify_t,
    evaluate_decision,
    five_close_label,
    next_five_trading_closes,
    summarize_counts,
)


PREFIXES = ("sh.600", "sh.601", "sh.603", "sh.605", "sz.000", "sz.001", "sz.002", "sz.003")
COLUMNS = ("date", "open", "high", "low", "close", "preclose", "volume", "amount", "turn", "tradestatus", "isST")


def stable_sample(paths: list[Path], max_codes: int) -> list[Path]:
    eligible = [path for path in paths if path.stem.startswith(PREFIXES)]
    eligible.sort(key=lambda path: hashlib.sha256(path.stem.encode()).hexdigest())
    return sorted(eligible[:max_codes], key=lambda path: path.stem)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=Path("PFrontStockData"))
    parser.add_argument("--config", type=Path, default=Path("yaml/edge_scout_v1.yaml"))
    parser.add_argument("--max-codes", type=int, default=400)
    parser.add_argument("--workers", type=int, default=min(os.cpu_count() or 1, 8))
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def load_benchmark_regimes(path: Path) -> dict[str, bool]:
    frame = pd.read_parquet(path, columns=["date", "close"]).sort_values("date").reset_index(drop=True)
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame = frame.dropna(subset=["date"]).reset_index(drop=True)
    records = frame.to_dict("records")
    return {
        frame.at[index, "date"].strftime("%Y-%m-%d"): benchmark_regime_through_t(records[:index + 1])
        for index in range(len(records))
    }


def _keys_for_year(year: int) -> tuple[str, str, str]:
    period = CALIBRATION if year <= 2024 else HOLDOUT
    return period, AGGREGATE, f"year_{year}"


def evaluate_code(task: tuple[str, dict[str, Any], dict[str, bool]]) -> dict[str, Any]:
    path_text, config, benchmark_regimes = task
    path = Path(path_text)
    frame = pd.read_parquet(path, columns=list(COLUMNS)).sort_values("date").reset_index(drop=True)
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame = frame.dropna(subset=["date"]).reset_index(drop=True)
    records = frame.to_dict("records")
    counts: dict[str, Counter[str]] = defaultdict(Counter)
    diagnostics: dict[str, Counter[str]] = defaultdict(Counter)
    minimum_history = max(65, int(config.get("universe", {}).get("min_listing_days", 252)))
    for index in range(minimum_history - 1, len(records)):
        signal_date = frame.at[index, "date"]
        year = int(signal_date.year)
        if year not in YEARS:
            continue
        date_text = signal_date.strftime("%Y-%m-%d")
        history = records[:index + 1]
        candidate = classify_t(
            path.stem,
            history,
            (),
            config,
            benchmark_regime=benchmark_regimes.get(date_text, False),
        )
        if not candidate["gate_passed"]:
            diagnostics["rejection_stage"]["production_gate"] += 1
            diagnostics["production_gate_failures"].update(candidate["gate_failures"])
            continue
        if not candidate["market_regime"]:
            diagnostics["rejection_stage"]["market_regime"] += 1
            continue
        if not candidate["stock_trend"]:
            diagnostics["rejection_stage"]["stock_trend"] += 1
            continue
        future_closes = next_five_trading_closes(records, index)
        if future_closes is None:
            continue
        label = five_close_label(float(records[index]["close"]), future_closes)
        for key in _keys_for_year(year):
            counts["trend_context_baseline"][key] += 1
            counts["trend_context_baseline"][f"{key}_hits"] += int(label)
        if not candidate["strict_pattern"]:
            diagnostics["rejection_stage"]["strict_pattern"] += 1
            continue
        diagnostics["pattern_length"].update((str(candidate["consolidation_length"]),))
        for key in _keys_for_year(year):
            counts["strict_pattern"][key] += 1
            counts["strict_pattern"][f"{key}_hits"] += int(label)
    return {
        "counts": {name: dict(values) for name, values in counts.items()},
        "diagnostics": {name: dict(values) for name, values in diagnostics.items()},
    }


def merge_results(results: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any]]:
    totals: dict[str, Counter[str]] = defaultdict(Counter)
    diagnostics: dict[str, Counter[str]] = defaultdict(Counter)
    for result in results:
        for strategy, values in result["counts"].items():
            totals[strategy].update(values)
        for name, values in result["diagnostics"].items():
            diagnostics[name].update(values)
    keys = (CALIBRATION, HOLDOUT, AGGREGATE, *(f"year_{year}" for year in YEARS))
    summaries = {
        strategy: {
            key: summarize_counts(totals[strategy][key], totals[strategy][f"{key}_hits"])
            for key in keys
        }
        for strategy in ("trend_context_baseline", "strict_pattern")
    }
    return summaries, {name: dict(sorted(values.items())) for name, values in diagnostics.items()}


def main() -> None:
    args = parse_args()
    if args.max_codes != 400:
        raise SystemExit("Stage 1 requires --max-codes=400")
    if not 1 <= args.workers <= 8:
        raise SystemExit("--workers must be between 1 and 8")
    paths = stable_sample(list(args.data_root.glob("*.parquet")), args.max_codes)
    if len(paths) != 400:
        raise SystemExit(f"Stage 1 requires exactly 400 eligible code files; found {len(paths)}")
    config = load_config(args.config)
    benchmark_path = args.data_root / "sh.000001.parquet"
    benchmark_regimes = load_benchmark_regimes(benchmark_path)
    tasks = [(str(path), config, benchmark_regimes) for path in paths]
    with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers) as executor:
        results = list(executor.map(evaluate_code, tasks))
    summaries, diagnostics = merge_results(results)
    report = {
        "study": "strict_rising_three_methods_stage1",
        "classification_only": True,
        "sample": {"method": "sha256_stable_code_sample", "requested": 400, "codes": len(paths)},
        "benchmark": "sh.000001",
        "date_range": {"start": "2021-01-01", "observed_end": max(benchmark_regimes)},
        "workers": args.workers,
        "summaries": summaries,
        "diagnostics": diagnostics,
        "decision": evaluate_decision(summaries),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_name(f".{args.output.name}.tmp")
    temporary.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(args.output)


if __name__ == "__main__":
    main()
