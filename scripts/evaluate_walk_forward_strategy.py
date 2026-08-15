#!/usr/bin/env python3
"""Leakage-safe daily walk-forward selected-stock classification study.

This is a read-only classification study. It does not model orders, positions,
capital, costs, returns, execution, or personalized recommendations.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
from collections import Counter, defaultdict, deque
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Iterable, Mapping

from ashare_edge_scout.config import load_config
if __package__:
    from scripts.evaluate_joint_strategy import (
        PREFIXES,
        _benchmark_regime,
        _stock_counts,
        wilson_lower,
    )
else:
    from evaluate_joint_strategy import PREFIXES, _benchmark_regime, _stock_counts, wilson_lower


CountCell = list[int]
DailyCounts = Mapping[str, Mapping[str, CountCell]]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=Path("PFrontStockData"))
    parser.add_argument("--config", type=Path, default=Path("yaml/edge_scout_v1.yaml"))
    parser.add_argument("--benchmark", default="sh.000001")
    parser.add_argument("--workers", type=int, default=min(os.cpu_count() or 1, 12))
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--history-start", default="2021-01-01")
    parser.add_argument("--prediction-start", default="2023-01-01")
    parser.add_argument("--end-date", default=None)
    parser.add_argument("--window-days", type=int, default=730)
    parser.add_argument("--min-matured-observations", type=int, default=800)
    parser.add_argument("--min-active-maturity-dates", type=int, default=120)
    parser.add_argument("--max-codes", type=int, default=None)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def _merge_counts(target: dict[str, dict[str, CountCell]], source: DailyCounts) -> None:
    for strategy, dates in source.items():
        for day, values in dates.items():
            cell = target[strategy].setdefault(day, [0, 0])
            cell[0] += int(values[0])
            cell[1] += int(values[1])


def _stock_batch(
    task: tuple[list[str], dict[str, Any], dict[str, bool], str, str | None],
) -> dict[str, Any]:
    paths, config, regime, start_date, end_date = task
    signal_counts: dict[str, dict[str, CountCell]] = defaultdict(dict)
    maturity_counts: dict[str, dict[str, CountCell]] = defaultdict(dict)
    dates: set[str] = set()
    observations = 0
    for path in paths:
        result = _stock_counts((path, config, regime, start_date, end_date, "daily"))
        observations += result["rows"]
        dates.update(result["dates"])
        _merge_counts(signal_counts, result["signal_counts"])
        _merge_counts(maturity_counts, result["maturity_counts"])
    return {
        "stocks": len(paths),
        "observations": observations,
        "dates": sorted(dates),
        "signal_counts": signal_counts,
        "maturity_counts": maturity_counts,
    }


def _strategy_choice(
    history: Mapping[str, tuple[int, int, int]],
    min_observations: int,
    min_active_dates: int,
) -> tuple[str | None, dict[str, Any] | None]:
    baseline_n, baseline_hits, _ = history.get("admitted_baseline", (0, 0, 0))
    if baseline_n == 0:
        return None, None
    baseline_rate = baseline_hits / baseline_n
    eligible: list[dict[str, Any]] = []
    for strategy in sorted(history):
        if strategy == "admitted_baseline":
            continue
        n, hits, active_dates = history[strategy]
        rate = hits / n if n else None
        if (
            n >= min_observations
            and active_dates >= min_active_dates
            and rate is not None
            and rate > baseline_rate
        ):
            eligible.append({
                "strategy": strategy,
                "n": n,
                "hits": hits,
                "active_maturity_dates": active_dates,
                "rate": rate,
                "wilson": wilson_lower(hits, n),
                "lift": rate - baseline_rate,
            })
    eligible.sort(key=lambda item: (-item["wilson"], -item["n"], item["strategy"]))
    if not eligible:
        return None, None
    return eligible[0]["strategy"], eligible[0]


def run_walk_forward(
    signal_counts: DailyCounts,
    maturity_counts: DailyCounts,
    prediction_dates: Iterable[str],
    *,
    window_days: int = 730,
    min_observations: int = 800,
    min_active_dates: int = 120,
) -> list[dict[str, Any]]:
    """Select daily using only labels with fifth-bar maturity strictly before D."""
    if window_days <= 0:
        raise ValueError("window_days must be positive")

    strategies = sorted(set(signal_counts) | set(maturity_counts))
    events: dict[str, list[tuple[date, int, int]]] = {}
    for strategy in strategies:
        events[strategy] = sorted(
            (date.fromisoformat(day), int(cell[0]), int(cell[1]))
            for day, cell in maturity_counts.get(strategy, {}).items()
        )
    positions = {strategy: 0 for strategy in strategies}
    windows: dict[str, deque[tuple[date, int, int]]] = {
        strategy: deque() for strategy in strategies
    }
    totals = {strategy: [0, 0] for strategy in strategies}
    records: list[dict[str, Any]] = []

    for day_text in sorted(set(prediction_dates)):
        day = date.fromisoformat(day_text)
        earliest = day - timedelta(days=window_days)
        for strategy in strategies:
            strategy_events = events[strategy]
            position = positions[strategy]
            while position < len(strategy_events) and strategy_events[position][0] < day:
                event = strategy_events[position]
                windows[strategy].append(event)
                totals[strategy][0] += event[1]
                totals[strategy][1] += event[2]
                position += 1
            positions[strategy] = position
            while windows[strategy] and windows[strategy][0][0] < earliest:
                event = windows[strategy].popleft()
                totals[strategy][0] -= event[1]
                totals[strategy][1] -= event[2]

        history = {
            strategy: (totals[strategy][0], totals[strategy][1], len(windows[strategy]))
            for strategy in strategies
        }
        selected, prior = _strategy_choice(history, min_observations, min_active_dates)
        actual = signal_counts.get(selected, {}).get(day_text, [0, 0]) if selected else [0, 0]
        n, hits = int(actual[0]), int(actual[1])
        baseline_actual = signal_counts.get("admitted_baseline", {}).get(day_text, [0, 0])
        baseline_n, baseline_hits = int(baseline_actual[0]), int(baseline_actual[1])
        false_positives = n - hits
        false_negatives = baseline_hits - hits if selected else 0
        true_negatives = baseline_n - n - false_negatives if selected else 0
        records.append({
            "date": day_text,
            "selected_strategy": selected,
            "prior_n": prior["n"] if prior else None,
            "prior_hits": prior["hits"] if prior else None,
            "prior_active_maturity_dates": prior["active_maturity_dates"] if prior else None,
            "prior_rate": prior["rate"] if prior else None,
            "prior_wilson_lower_95": round(prior["wilson"], 6) if prior else None,
            "prior_lift_vs_admitted": round(prior["lift"], 6) if prior else None,
            "predicted_candidates": n,
            "actual_hits": hits,
            "false_positives": false_positives,
            "admitted_stocks": baseline_n,
            "actual_admitted_hits": baseline_hits,
            "false_negatives": false_negatives,
            "true_negatives": true_negatives,
            "actual_hit_rate": round(hits / n, 6) if n else None,
        })
    return records


def summarize_predictions(records: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    rows = list(records)
    selected_rows = [row for row in rows if row["selected_strategy"] is not None]
    n = sum(int(row["predicted_candidates"]) for row in selected_rows)
    hits = sum(int(row["actual_hits"]) for row in selected_rows)
    false_positives = n - hits
    baseline_n = sum(int(row["admitted_stocks"]) for row in selected_rows)
    baseline_hits = sum(int(row["actual_admitted_hits"]) for row in selected_rows)
    false_negatives = sum(int(row["false_negatives"]) for row in selected_rows)
    true_negatives = sum(int(row["true_negatives"]) for row in selected_rows)
    brier_sum = 0.0
    calibration_sum = 0.0
    for row in selected_rows:
        count = int(row["predicted_candidates"])
        if count == 0:
            continue
        actual_hits = int(row["actual_hits"])
        probability = float(row["prior_rate"])
        brier_sum += actual_hits * (1.0 - probability) ** 2
        brier_sum += (count - actual_hits) * probability**2
        calibration_sum += abs(actual_hits - count * probability)

    selected_names = [str(row["selected_strategy"]) for row in selected_rows]
    switches = sum(left != right for left, right in zip(selected_names, selected_names[1:]))
    recall = hits / baseline_hits if baseline_hits else None
    precision = hits / n if n else None
    return {
        "prediction_dates": len(rows),
        "rule_selected_dates": len(selected_rows),
        "candidate_prediction_dates": sum(int(row["predicted_candidates"]) > 0 for row in selected_rows),
        "empty_candidate_dates": sum(int(row["predicted_candidates"]) == 0 for row in selected_rows),
        "abstained_dates": len(rows) - len(selected_rows),
        "strategy_switch_count": switches,
        "strategy_selection_counts": dict(sorted(Counter(selected_names).items())),
        "n": n,
        "hits": hits,
        "false_positives": false_positives,
        "false_negatives": false_negatives,
        "true_negatives": true_negatives,
        "admitted_stocks": baseline_n,
        "actual_admitted_hits": baseline_hits,
        "admitted_hit_rate": round(baseline_hits / baseline_n, 6) if baseline_n else None,
        "precision": round(precision, 6) if precision is not None else None,
        "recall": round(recall, 6) if recall is not None else None,
        "specificity": round(true_negatives / (true_negatives + false_positives), 6) if true_negatives + false_positives else None,
        "accuracy": round((hits + true_negatives) / baseline_n, 6) if baseline_n else None,
        "f1": round(2 * precision * recall / (precision + recall), 6) if precision and recall else None,
        "hit_rate": round(precision, 6) if precision is not None else None,
        "weighted_brier_score": round(brier_sum / n, 6) if n else None,
        "weighted_absolute_calibration_error": round(calibration_sum / n, 6) if n else None,
    }


def _hindsight_static_diagnostic(
    signal_counts: DailyCounts,
    prediction_dates: Iterable[str],
) -> dict[str, Any]:
    allowed_dates = set(prediction_dates)
    summaries: dict[str, dict[str, Any]] = {}
    for strategy in sorted(signal_counts):
        n = hits = 0
        for day, cell in signal_counts[strategy].items():
            if day in allowed_dates:
                n += int(cell[0])
                hits += int(cell[1])
        summaries[strategy] = {
            "n": n,
            "hits": hits,
            "false_positives": n - hits,
            "hit_rate": round(hits / n, 6) if n else None,
            "wilson_lower_95": round(wilson_lower(hits, n), 6) if n else None,
        }
    candidates = [
        (name, cell) for name, cell in summaries.items()
        if name != "admitted_baseline" and cell["wilson_lower_95"] is not None
    ]
    candidates.sort(key=lambda item: (-item[1]["wilson_lower_95"], -item[1]["n"], item[0]))
    return {
        "hindsight_only_not_used_for_selection": True,
        "best_static_strategy": candidates[0][0] if candidates else None,
        "strategies": summaries,
    }


def _chunks(values: list[str], size: int) -> Iterable[list[str]]:
    if size <= 0:
        raise ValueError("batch_size must be positive")
    for index in range(0, len(values), size):
        yield values[index:index + size]


def main() -> None:
    args = parse_args()
    config = load_config(args.config)
    benchmark_path = args.data_root / f"{args.benchmark}.parquet"
    if not benchmark_path.exists():
        raise SystemExit(f"Benchmark data not found: {benchmark_path}")
    regime = _benchmark_regime(benchmark_path, config)
    paths = sorted(
        str(path) for path in args.data_root.glob("*.parquet")
        if path.stem.startswith(PREFIXES)
    )
    if args.max_codes is not None:
        paths = paths[:args.max_codes]
    batches = list(_chunks(paths, args.batch_size))
    tasks = [(batch, config, regime, args.history_start, args.end_date) for batch in batches]
    workers = max(1, min(args.workers, len(tasks) or 1))
    signal_counts: dict[str, dict[str, CountCell]] = defaultdict(dict)
    maturity_counts: dict[str, dict[str, CountCell]] = defaultdict(dict)
    all_dates: set[str] = set()
    observations = processed = 0
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as executor:
        for result in executor.map(_stock_batch, tasks, chunksize=1):
            processed += result["stocks"]
            observations += result["observations"]
            all_dates.update(result["dates"])
            _merge_counts(signal_counts, result["signal_counts"])
            _merge_counts(maturity_counts, result["maturity_counts"])
            print(
                f"processed={processed}/{len(paths)} observations={observations} workers={workers}",
                flush=True,
            )

    prediction_dates = sorted(
        day for day in all_dates
        if day >= args.prediction_start and day <= (args.end_date or "9999-12-31")
    )
    records = run_walk_forward(
        signal_counts,
        maturity_counts,
        prediction_dates,
        window_days=args.window_days,
        min_observations=args.min_matured_observations,
        min_active_dates=args.min_active_maturity_dates,
    )
    yearly = {
        year: summarize_predictions(row for row in records if row["date"].startswith(year))
        for year in sorted({row["date"][:4] for row in records})
    }
    result = {
        "study": "daily_walk_forward_selected_stock_classification_v1",
        "classification_only": True,
        "read_only": True,
        "label": "within_T_plus_1_to_T_plus_5_close_reaches_3pct_up_without_3pct_close_drawdown",
        "label_definition": "Hit iff max close in the next five stock bars is at least 1.03 times D close and every next-five-bar close is at least 0.97 times D close.",
        "leakage_controls": {
            "daily_selection": "For prediction date D, strategy selection uses prior labeled observations only.",
            "maturity_boundary": "An observation is available only when its fifth future stock-bar date is strictly before D; maturity_date equal to D is excluded.",
            "history_window": f"Trailing {args.window_days} calendar days indexed by maturity_date.",
            "future_outcomes": "Outcomes maturing on or after D cannot affect selection for D.",
        },
        "selection_protocol": {
            "history_start": args.history_start,
            "prediction_start": args.prediction_start,
            "end_date": args.end_date,
            "candidate_library": "All joint-study strategies except admitted_baseline.",
            "min_matured_observations": args.min_matured_observations,
            "min_active_maturity_dates": args.min_active_maturity_dates,
            "eligibility": "Historical hit rate must be strictly above admitted_baseline in the same maturity window.",
            "ranking": "Highest 95% Wilson lower bound, then larger n, then strategy name ascending.",
            "no_eligible_strategy": "Abstain for that prediction date.",
        },
        "metric_definitions": {
            "confusion_matrix": "For dates with a selected rule, admitted stocks are the comparison universe; selected hits are true positives, selected misses are false positives, and unselected admitted hits are false negatives.",
            "weighted_brier_score": "Observation-weighted squared error using that date's prior historical hit rate as predicted probability.",
            "weighted_absolute_calibration_error": "Candidate-count-weighted absolute gap between each selected date's prior probability and realized hit rate.",
        },
        "universe": {"current_main_board_files": len(paths), "all_eligible_dates": True},
        "benchmark_regime": args.benchmark,
        "observations_considered": observations,
        "aggregate": summarize_predictions(records),
        "yearly_summaries": yearly,
        "prediction_records": records,
        "hindsight_static_diagnostic": _hindsight_static_diagnostic(signal_counts, prediction_dates),
        "candidate_set_caveat": "The candidate strategy library was informed by earlier research. This is retrospective walk-forward evidence, not a pristine untouched prospective test.",
        "known_biases": [
            "current-file-universe survivorship and historical-membership bias",
            "forward-adjusted equity history is not point-in-time adjustment-vintage data",
            "no point-in-time industry, event, fundamental, or delisting data",
            "overlapping five-day labels are correlated",
            "strategy-library and threshold research can create selection and multiple-testing bias",
            "provider omissions and stock-specific suspension calendars affect observation and maturity dates",
        ],
        "excluded_domains": [
            "orders", "positions", "capital", "costs", "returns", "execution", "personalized recommendations"
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_name(f".{args.output.name}.tmp")
    temporary.write_text(
        json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(args.output)


if __name__ == "__main__":
    main()
