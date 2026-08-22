#!/usr/bin/env python3
"""Evaluate the pre-registered NCN v2 support-reclaim Stage 1 hypothesis.

This is a read-only classification study. It models no orders, positions,
capital, costs, execution, returns, or personalized recommendations.
"""

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

from ashare_edge_scout.signals.candles import detect_bullish_patterns
from ashare_edge_scout.config import load_config
from ashare_edge_scout.research_v2 import (
    CONFIRMED_STATES,
    PERIODS,
    classify_t1_confirmation,
    evaluate_decision,
    evaluate_t_candidates,
    post_confirmation_label,
    summarize_counts,
    t_day_label,
)


PREFIXES = ("sh.600", "sh.601", "sh.603", "sh.605", "sz.000", "sz.001", "sz.002", "sz.003")
STRATEGIES = (
    "legacy_setup_t_horizon",
    "legacy_setup_post_confirmation_horizon",
    "support_reclaim_t_t_horizon",
    "support_reclaim_t_post_confirmation_horizon",
    "support_reclaim_confirmed_post_confirmation_horizon",
)


def stable_sample(paths: list[Path], max_codes: int) -> list[Path]:
    """Use the established SHA-256 code sampling contract."""

    eligible = [path for path in paths if path.stem.startswith(PREFIXES)]
    eligible.sort(key=lambda path: hashlib.sha256(path.stem.encode()).hexdigest())
    return sorted(eligible[:max_codes], key=lambda path: path.stem)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=Path("PFrontStockData"))
    parser.add_argument("--config", type=Path, default=Path("yaml/edge_scout_v1.yaml"))
    parser.add_argument("--max-codes", type=int, default=400)
    parser.add_argument("--workers", type=int, default=min(os.cpu_count() or 1, 8))
    parser.add_argument("--start-date", default="2021-01-01")
    parser.add_argument("--end-date", default=None)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def _period_for_year(year: int) -> str | None:
    for name, (first, last) in PERIODS.items():
        if first <= year <= last:
            return name
    return None


def evaluate_code(task: tuple[str, dict[str, Any], str, str | None]) -> dict[str, Any]:
    path_text, config, start_date, end_date = task
    path = Path(path_text)
    columns = [
        "date", "open", "high", "low", "close", "preclose", "volume",
        "amount", "turn", "tradestatus", "isST",
    ]
    frame = pd.read_parquet(path, columns=columns).sort_values("date").reset_index(drop=True)
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame = frame.dropna(subset=["date"]).reset_index(drop=True)
    records = frame.to_dict("records")
    if len(records) < 66:
        return {"code": path.stem, "counts": {}, "diagnostics": {}}
    patterns = detect_bullish_patterns(records)
    counts: dict[str, Counter[str]] = defaultdict(Counter)
    diagnostics: dict[str, Counter[str]] = defaultdict(Counter)
    dates = frame["date"]
    minimum_history = max(65, int(config.get("universe", {}).get("min_listing_days", 252)))

    for index in range(minimum_history - 1, len(records) - 5):
        signal_date = dates.iat[index]
        date_text = signal_date.strftime("%Y-%m-%d")
        if date_text < start_date or (end_date and date_text > end_date):
            continue
        period = _period_for_year(int(signal_date.year))
        if period is None:
            continue
        matched = [name for name, values in patterns.items() if bool(values[index])]
        if not matched:
            continue
        history = records[:index + 1]
        patterns_through_t = {name: values[:index + 1] for name, values in patterns.items()}
        candidate = evaluate_t_candidates(path.stem, history, config, patterns_through_t)
        hit_t = t_day_label(records, index)
        if candidate["legacy_setup"]:
            counts["legacy_setup_t_horizon"][period] += 1
            counts["legacy_setup_t_horizon"][f"{period}_hits"] += int(hit_t)
            if index + 6 < len(records):
                hit_post = post_confirmation_label(records, index)
                counts["legacy_setup_post_confirmation_horizon"][period] += 1
                counts["legacy_setup_post_confirmation_horizon"][f"{period}_hits"] += int(hit_post)
        if not candidate["support_reclaim_t"]:
            continue

        counts["support_reclaim_t_t_horizon"][period] += 1
        counts["support_reclaim_t_t_horizon"][f"{period}_hits"] += int(hit_t)
        diagnostics["support_reason_codes"].update(candidate["support_reason_codes"])
        diagnostics["matched_patterns"].update(candidate["matched_patterns"])
        confirmation = classify_t1_confirmation(
            history, records[index + 1], candidate["matched_patterns"], candidate["reclaimed_supports"]
        )
        diagnostics["confirmation_states"].update((confirmation["state"],))
        diagnostics["confirmation_patterns"].update((confirmation["pattern"] or "none",))

        if index + 6 >= len(records):
            continue
        hit_post = post_confirmation_label(records, index)
        counts["support_reclaim_t_post_confirmation_horizon"][period] += 1
        counts["support_reclaim_t_post_confirmation_horizon"][f"{period}_hits"] += int(hit_post)
        if confirmation["state"] in CONFIRMED_STATES:
            counts["support_reclaim_confirmed_post_confirmation_horizon"][period] += 1
            counts["support_reclaim_confirmed_post_confirmation_horizon"][f"{period}_hits"] += int(hit_post)
    return {
        "code": path.stem,
        "counts": {name: dict(values) for name, values in counts.items()},
        "diagnostics": {name: dict(values) for name, values in diagnostics.items()},
    }


def _merge(results: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any]]:
    totals: dict[str, Counter[str]] = defaultdict(Counter)
    diagnostics: dict[str, Counter[str]] = defaultdict(Counter)
    for result in results:
        for strategy, values in result["counts"].items():
            totals[strategy].update(values)
        for name, values in result["diagnostics"].items():
            diagnostics[name].update(values)
    summaries: dict[str, Any] = {}
    for strategy in STRATEGIES:
        summaries[strategy] = {}
        for period in PERIODS:
            summaries[strategy][period] = summarize_counts(
                totals[strategy][period], totals[strategy][f"{period}_hits"]
            )
    return summaries, {name: dict(sorted(values.items())) for name, values in diagnostics.items()}


def _compare(candidate: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    baseline_fpr = baseline["fpr"]
    candidate_fpr = candidate["fpr"]
    return {
        "candidate_retention": candidate["n"] / baseline["n"] if baseline["n"] else None,
        "precision_lift": (
            candidate["precision"] - baseline["precision"]
            if candidate["precision"] is not None and baseline["precision"] is not None
            else None
        ),
        "relative_fpr_reduction": (
            (baseline_fpr - candidate_fpr) / baseline_fpr
            if baseline_fpr not in (None, 0) and candidate_fpr is not None
            else None
        ),
        "wilson_lower_change": (
            candidate["wilson_lower_95"] - baseline["wilson_lower_95"]
            if candidate["wilson_lower_95"] is not None and baseline["wilson_lower_95"] is not None
            else None
        ),
    }


def main() -> None:
    args = parse_args()
    if not 1 <= args.workers <= 8:
        raise SystemExit("--workers must be between 1 and 8")
    paths = stable_sample(list(args.data_root.glob("*.parquet")), args.max_codes)
    config = load_config(args.config)
    tasks = [(str(path), config, args.start_date, args.end_date) for path in paths]
    with concurrent.futures.ProcessPoolExecutor(max_workers=min(args.workers, len(tasks) or 1)) as executor:
        results = list(executor.map(evaluate_code, tasks))
    summaries, diagnostics = _merge(results)
    decision = evaluate_decision(summaries)
    comparisons = {
        "support_reclaim_t_vs_legacy_same_t_horizon": {
            period: _compare(
                summaries["support_reclaim_t_t_horizon"][period],
                summaries["legacy_setup_t_horizon"][period],
            )
            for period in PERIODS
        },
        "confirmed_vs_legacy_same_post_confirmation_horizon": decision["comparisons"],
    }
    report = {
        "study": "ncn_v2_support_reclaim_stage1",
        "classification_only": True,
        "historical_research_only": True,
        "not_prospective_evidence": True,
        "no_execution_or_pnl": True,
        "raw_future_rows_exposed": False,
        "label_inputs_ephemeral": True,
        "sample": {"method": "sha256_stable_code_sample", "requested": args.max_codes, "codes": len(paths)},
        "periods": PERIODS,
        "workers": args.workers,
        "support_definition": {
            "included": ["prior_20_bar_swing_low", "sma20_t_minus_1", "sma60_t_minus_1"],
            "changed_polarity_support": "omitted_due_to_ambiguous_breakout_window",
        },
        "label_note": (
            "T-day and legacy use T+1..T+5 relative to T close. Confirmation observes T+1; "
            "confirmed evaluation therefore uses T+2..T+6 relative to T+1 close. The confirmed "
            "acceptance comparison uses the same T+2..T+6 horizon for legacy and confirmed candidates."
        ),
        "summaries": summaries,
        "comparisons": comparisons,
        "diagnostics": diagnostics,
        "decision": decision,
        "legacy_comparison_note": "Confirmed-versus-legacy acceptance uses an equal post-confirmation horizon.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
