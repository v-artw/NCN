#!/usr/bin/env python3
"""Backtest SMC scan signals with the frozen MKF v3 post-cross lag/target/horizon grid.

Caliber (matches scripts/evaluate_mkf_post_cross_lag_target_grid.py one-to-one, only the
parent signal changes):
- parent signal: production_smc_mask = production_gate_mask AND smc_medium_buy (SMC scan day).
- cohorts: lag0..lag5 stock-tradable rows after the parent signal, evaluated independently.
- hard gate: production_gate_mask re-applied at each lag signal row (MKF method rule).
- entry: next stock-tradable open after the lag signal row.
- target hit: any high from T+1..T+n after entry >= entry_open * (1 + pct/100), pct in {3, 4}.
- horizons: T+1..T+20; non-tradable rows consume no lag or horizon windows.
- dedup: one event per (code, lag, entry row), same as the MKF builder.

Research only: no production selector, watchlist, or order path is touched.
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
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

for _name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_name] = "1"

import numpy as np
import pandas as pd

from ashare_edge_scout.config import load_config
from ashare_edge_scout.pmkf_mkf.chop_filter import compute_sideways_chop_features_at
from ashare_edge_scout.pmkf_mkf.mkf_post_cross_lag_comparison import (
    CHOP_FILTER_VARIANTS,
    GRID_HORIZONS,
    GRID_SCHEMA_VERSION,
    _grid_columns,
    build_lag_target_grid_report,
    lag_target_grid_summary_csv_rows,
)
from ashare_edge_scout.pmkf_mkf.mkf_smc_annual_comparison import production_smc_mask
from ashare_edge_scout.pmkf_mkf.quality import _numeric, normalise_stock_frame
from ashare_edge_scout.research_precision70 import PREFIXES, production_gate_mask

REQUIRED_COLUMNS = ["date", "open", "high", "low", "close", "preclose", "volume", "amount", "tradestatus", "isST"]

SMC_LAGS = tuple(range(0, 6))
SMC_TARGET_PCTS = (3, 4)
STUDY_NAME = "smc_post_signal_lag0_to_lag5_target_grid_mkf_method_v1"
SCHEMA_VERSION = "ncn_smc_lag_target_grid_v1"


def build_smc_post_signal_lag_target_grid_panel(
    code: str,
    frame: pd.DataFrame,
    config: Mapping[str, Any],
    *,
    start_date: str = "2021-01-01",
    end_date: str | None = None,
    lags: tuple[int, ...] = SMC_LAGS,
    horizons: tuple[int, ...] = GRID_HORIZONS,
) -> pd.DataFrame:
    """Clone of build_mkf_post_cross_lag_target_grid_panel with the SMC scan mask as parent.

    The `cross_date` column holds the SMC parent signal date so that the shared MKF
    aggregation and report helpers can be reused verbatim.
    """
    data = normalise_stock_frame(frame)
    parent = production_smc_mask(code, data, config).reindex(data.index, fill_value=False).astype(bool)
    admitted = production_gate_mask(code, data, config).reindex(data.index, fill_value=False).astype(bool)
    trade = data.get("tradestatus", pd.Series(index=data.index, dtype=object)).astype("string")
    tradable = list(np.flatnonzero(trade.eq("1").fillna(False).to_numpy()))
    positions = {row_index: position for position, row_index in enumerate(tradable)}
    dates = pd.to_datetime(data["date"], errors="coerce")
    open_ = _numeric(data, "open").to_numpy(dtype=float)
    high = _numeric(data, "high").to_numpy(dtype=float)
    start = pd.Timestamp(start_date)
    end = pd.Timestamp(end_date) if end_date is not None else None
    max_horizon = max(horizons)

    rows: list[dict[str, Any]] = []
    diagnostics: Counter[str] = Counter()
    used_entry_by_lag: dict[int, set[int]] = {lag: set() for lag in lags}
    parent_indexes = [
        int(index)
        for index in data.index[parent.fillna(False)]
        if dates.iat[int(index)] >= start and (end is None or dates.iat[int(index)] <= end)
    ]
    diagnostics["parent_smc_signals"] = len(parent_indexes)
    diagnostics["parent_crosses"] = len(parent_indexes)  # alias so the shared MKF retention math keeps working
    for parent_index in parent_indexes:
        parent_position = positions.get(parent_index)
        if parent_position is None:
            diagnostics["nontradable_parent_signal"] += 1
            continue
        for lag in lags:
            target_position = parent_position + lag
            if target_position >= len(tradable):
                diagnostics[f"lag_{lag}_missing_signal_row"] += 1
                continue
            signal_index = tradable[target_position]
            signal_date = dates.iat[signal_index]
            if end is not None and signal_date > end:
                diagnostics[f"lag_{lag}_after_end_date"] += 1
                continue
            if not bool(admitted.loc[signal_index]):
                diagnostics[f"lag_{lag}_hard_gate_rejected"] += 1
                continue
            entry_position = target_position + 1
            if entry_position >= len(tradable):
                diagnostics[f"lag_{lag}_missing_entry_row"] += 1
                continue
            entry_index = tradable[entry_position]
            if entry_index in used_entry_by_lag[lag]:
                diagnostics[f"lag_{lag}_duplicate_entry_row"] += 1
                continue
            entry_open = open_[entry_index]
            if not np.isfinite(entry_open) or entry_open <= 0:
                diagnostics[f"lag_{lag}_invalid_entry_open"] += 1
                continue
            used_entry_by_lag[lag].add(entry_index)
            future = tradable[entry_position + 1:entry_position + 1 + max_horizon]
            row: dict[str, Any] = {
                "code": code,
                "cross_date": dates.iat[parent_index],
                "signal_date": signal_date,
                "entry_date": dates.iat[entry_index],
                "post_cross_lag": int(lag),
                "entry_open": float(entry_open),
                "status": "mature" if len(future) >= max_horizon else "partial",
                **compute_sideways_chop_features_at(data, signal_index),
            }
            for horizon in range(1, max_horizon + 1):
                if len(future) < horizon:
                    row[f"date_t{horizon}"] = pd.NaT
                    row[f"future_high_t{horizon}"] = np.nan
                    continue
                future_index = future[horizon - 1]
                if not np.isfinite(high[future_index]):
                    row["status"] = "invalid"
                row[f"date_t{horizon}"] = dates.iat[future_index]
                row[f"future_high_t{horizon}"] = float(high[future_index]) if np.isfinite(high[future_index]) else np.nan
            rows.append(row)
            diagnostics[f"lag_{lag}_events"] += 1

    result = pd.DataFrame(rows, columns=_grid_columns(horizons))
    result.attrs["diagnostics"] = dict(diagnostics)
    return result


def _smc_report(
    *,
    panel: pd.DataFrame,
    diagnostics: Mapping[str, Any],
    code_list: list[str],
    code_list_sha256: str,
    start_date: str,
    end_date: str | None,
    workers: int,
    horizons: tuple[int, ...],
    target_pcts: tuple[int, ...],
    chop_variants: tuple[str, ...],
) -> dict[str, Any]:
    report = build_lag_target_grid_report(
        panel=panel,
        diagnostics=diagnostics,
        code_list=code_list,
        code_list_sha256=code_list_sha256,
        start_date=start_date,
        end_date=end_date,
        workers=workers,
        horizons=horizons,
        target_pcts=target_pcts,
        chop_variants=chop_variants,
    )
    report["schema_version"] = SCHEMA_VERSION
    report["study"] = STUDY_NAME
    report["method_source_schema"] = GRID_SCHEMA_VERSION
    report["signal_source"] = (
        "production_smc_mask(code, frame, config) = production_gate_mask AND smc_medium_buy, "
        "replayed over current-vintage normalised history; the cross_date column holds the SMC parent signal date."
    )
    report["grid"]["lags"] = list(SMC_LAGS)
    report["candidate_definition"] = {
        "parent_signal": "production_smc_mask row (SMC scan selection day) inside the requested window",
        "lag_signal": "lag0..5 stock-tradable rows from the parent signal, evaluated as independent cohorts",
        "hard_gate": "production_gate_mask re-applied at each lag signal row (same rule as the MKF method)",
        "suspension_handling": "non-tradable rows do not consume lag or horizon windows",
    }
    if "parent_crosses" in report["sample"]:
        report["sample"]["parent_smc_signals"] = int(report["sample"].pop("parent_crosses"))
    report["naming_note"] = (
        "Aggregated tables keep the MKF column names (cross_date/parent fields) for method reuse; "
        "in this study they refer to the SMC parent signal day."
    )
    report["limitations"] = [
        *report["limitations"],
        "SMC parent signals are replayed from the current SMC formula over history, not read from archived daily scan selection files.",
    ]
    return report


def _parse_int_csv(value: str) -> tuple[int, ...]:
    try:
        parsed = tuple(int(item.strip()) for item in value.split(",") if item.strip())
    except ValueError as exc:
        raise argparse.ArgumentTypeError("expected comma-separated integers") from exc
    if not parsed:
        raise argparse.ArgumentTypeError("at least one integer is required")
    return parsed


def _parse_str_csv(value: str) -> tuple[str, ...]:
    parsed = tuple(item.strip() for item in value.split(",") if item.strip())
    if not parsed:
        raise argparse.ArgumentTypeError("at least one value is required")
    return parsed


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=Path("PFrontStockData"))
    parser.add_argument("--config", type=Path, default=Path("yaml/edge_scout_v1.yaml"))
    parser.add_argument("--start-date", default="2021-01-01")
    parser.add_argument("--end-date", default=None)
    parser.add_argument("--workers", type=int, default=min(os.cpu_count() or 1, 8))
    parser.add_argument("--horizons", type=_parse_int_csv, default=GRID_HORIZONS)
    parser.add_argument("--target-pcts", type=_parse_int_csv, default=SMC_TARGET_PCTS)
    parser.add_argument("--chop-variants", type=_parse_str_csv, default=("baseline", "exclude_chop_ge_4"))
    parser.add_argument("--limit-codes", type=int, default=None)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--summary-csv", type=Path, default=None)
    args = parser.parse_args(argv)
    if not 1 <= args.workers <= 16:
        parser.error("--workers must be between 1 and 16")
    invalid_horizons = [horizon for horizon in args.horizons if horizon < 1 or horizon > 20]
    if invalid_horizons:
        parser.error("--horizons values must be between 1 and 20")
    invalid_targets = [target for target in args.target_pcts if target < 1 or target > 20]
    if invalid_targets:
        parser.error("--target-pcts values must be between 1 and 20")
    invalid_variants = [variant for variant in args.chop_variants if variant not in CHOP_FILTER_VARIANTS]
    if invalid_variants:
        parser.error(f"unknown --chop-variants: {','.join(invalid_variants)}")
    return args


def _stock(task: tuple[str, dict[str, Any], str, str | None]) -> tuple[pd.DataFrame, dict[str, int]]:
    path_text, config, start_date, end_date = task
    path = Path(path_text)
    frame = pd.read_parquet(path, columns=REQUIRED_COLUMNS)
    panel = build_smc_post_signal_lag_target_grid_panel(path.stem, frame, config, start_date=start_date, end_date=end_date)
    return panel, {str(key): int(value) for key, value in panel.attrs.get("diagnostics", {}).items()}


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


def _atomic_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
            if rows:
                writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    paths = sorted((path for path in args.data_root.glob("*.parquet") if path.stem.startswith(PREFIXES)), key=lambda path: path.stem)
    if not paths:
        raise SystemExit("no current main-board Parquet files found")
    if args.limit_codes is not None:
        paths = paths[: args.limit_codes]
    config = load_config(args.config)
    tasks = [(str(path), config, args.start_date, args.end_date) for path in paths]
    panels: list[pd.DataFrame] = []
    diagnostics: Counter[str] = Counter()
    with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers) as executor:
        for completed, (panel, stock_diagnostics) in enumerate(executor.map(_stock, tasks, chunksize=1), start=1):
            panels.append(panel)
            diagnostics.update(stock_diagnostics)
            if completed % 100 == 0 or completed == len(tasks):
                print(f"processed {completed}/{len(paths)} codes", flush=True)
    code_list = [path.stem for path in paths]
    report = _smc_report(
        panel=pd.concat(panels, ignore_index=True),
        diagnostics=dict(diagnostics),
        code_list=code_list,
        code_list_sha256=hashlib.sha256(("\n".join(code_list) + "\n").encode("ascii")).hexdigest(),
        start_date=args.start_date,
        end_date=args.end_date,
        workers=args.workers,
        horizons=args.horizons,
        target_pcts=args.target_pcts,
        chop_variants=args.chop_variants,
    )
    _atomic_json(args.output, report)
    if args.summary_csv is not None:
        _atomic_csv(args.summary_csv, lag_target_grid_summary_csv_rows(report))
    print(f"status=ok codes={len(code_list)} events={report['sample']['lag_events']} output={args.output}", flush=True)


def self_test() -> None:
    """Patch module-level mask functions and verify lag alignment, gating, suspensions, report reuse."""
    failures: list[str] = []

    def _check(name: str, condition: bool) -> None:
        if not condition:
            failures.append(name)

    def _frame(rows: int, *, suspend: int | None = None) -> pd.DataFrame:
        dates = pd.bdate_range("2025-01-01", periods=rows)
        trade_status = ["1"] * rows
        if suspend is not None:
            trade_status[suspend] = "0"
        return pd.DataFrame(
            {
                "date": dates.strftime("%Y-%m-%d"),
                "open": [100.0] * rows,
                "high": [101.0] * rows,
                "low": [99.0] * rows,
                "close": [100.0] * rows,
                "preclose": [100.0] * rows,
                "volume": [1_000_000] * rows,
                "amount": [100_000_000] * rows,
                "tradestatus": trade_status,
                "isST": ["0"] * rows,
            }
        )

    def _mask(frame: pd.DataFrame, indexes: Sequence[int]) -> pd.Series:
        series = pd.Series(False, index=frame.index)
        for index in indexes:
            series.iloc[int(index)] = True
        return series

    config: dict[str, Any] = {}
    gate_backup = production_gate_mask
    smc_backup = production_smc_mask
    try:
        globals()["production_gate_mask"] = lambda code, data, cfg: pd.Series(True, index=data.index)

        # Case 1: two adjacent parents -> 6 lag cohorts each, entries shifted one row per lag.
        frame = _frame(30)
        globals()["production_smc_mask"] = lambda code, data, cfg: _mask(data, [5, 6]).reindex(data.index, fill_value=False)
        panel = build_smc_post_signal_lag_target_grid_panel("600000", frame, config, start_date="2025-01-01")
        diagnostics = panel.attrs["diagnostics"]
        _check("case1_lags", sorted(panel["post_cross_lag"].unique().tolist()) == [0, 1, 2, 3, 4, 5])
        _check("case1_events", len(panel) == 12)
        _check("case1_parents", diagnostics.get("parent_smc_signals", 0) == 2)
        first_parent = panel[panel["cross_date"] == pd.Timestamp("2025-01-08")].sort_values("post_cross_lag")
        _check("case1_lag0_entry", first_parent.iloc[0]["entry_date"] == pd.Timestamp("2025-01-09"))
        _check("case1_lag5_entry", first_parent.iloc[5]["entry_date"] == pd.Timestamp("2025-01-16"))
        _check("case1_no_lag67", not (panel["post_cross_lag"] >= 6).any())
        _check("case1_partial", (panel["status"] == "partial").any())

        # Case 2: hard gate rejected only at lag signal rows; lag L signal row = parent row + L
        # (lag0 re-checks the parent day itself, exactly as the MKF builder does).
        gate = pd.Series(True, index=frame.index)
        gate.iloc[5] = False  # lag0 signal row == parent day
        gate.iloc[7] = False  # lag2 signal row
        globals()["production_gate_mask"] = lambda code, data, cfg: gate.reindex(data.index, fill_value=False)
        globals()["production_smc_mask"] = lambda code, data, cfg: _mask(data, [5]).reindex(data.index, fill_value=False)
        panel2 = build_smc_post_signal_lag_target_grid_panel("600000", frame, config, start_date="2025-01-01")
        diagnostics2 = panel2.attrs["diagnostics"]
        _check("case2_rejected", diagnostics2.get("lag_0_hard_gate_rejected", 0) == 1 and diagnostics2.get("lag_2_hard_gate_rejected", 0) == 1)
        _check("case2_events", len(panel2) == 4 and sorted(panel2["post_cross_lag"].tolist()) == [1, 3, 4, 5])

        # Case 3: suspended row is skipped and does not consume lag windows.
        globals()["production_gate_mask"] = lambda code, data, cfg: pd.Series(True, index=data.index)
        frame3 = _frame(30, suspend=6)
        globals()["production_smc_mask"] = lambda code, data, cfg: _mask(data, [5]).reindex(data.index, fill_value=False)
        panel3 = build_smc_post_signal_lag_target_grid_panel("600000", frame3, config, start_date="2025-01-01")
        lag0 = panel3[panel3["post_cross_lag"] == 0].iloc[0]
        lag1 = panel3[panel3["post_cross_lag"] == 1].iloc[0]
        _check("case3_lag0_entry_skips_suspension", lag0["entry_date"] == pd.Timestamp("2025-01-10"))
        _check("case3_lag1_signal", lag1["signal_date"] == pd.Timestamp("2025-01-10"))

        # Case 4: shared MKF report/aggregation reuse produces the SMC-labelled grid.
        report = _smc_report(
            panel=panel,
            diagnostics=diagnostics,
            code_list=["600000"],
            code_list_sha256="0" * 64,
            start_date="2025-01-01",
            end_date=None,
            workers=1,
            horizons=GRID_HORIZONS,
            target_pcts=SMC_TARGET_PCTS,
            chop_variants=("baseline", "exclude_chop_ge_4"),
        )
        _check("case4_study", report["study"] == STUDY_NAME)
        _check("case4_lags", report["grid"]["lags"] == [0, 1, 2, 3, 4, 5])
        _check("case4_parent_renamed", "parent_smc_signals" in report["sample"] and "parent_crosses" not in report["sample"])
        variants = report["variant_metrics"]
        _check("case4_variants", set(variants) == {"baseline", "exclude_chop_ge_4"})
        _check("case4_parent_alias", diagnostics.get("parent_crosses", 0) == 2)
        lag0_full = variants["baseline"]["grid_metrics"]["0"]["full_period"]
        _check("case4_periods", "T+5" in lag0_full and "T+20" in lag0_full)
        _check("case4_target_cells", set(lag0_full["T+5"]) == {"target_3pct", "target_4pct"})
        cell = lag0_full["T+5"]["target_3pct"]
        _check("case4_cell_counts", cell["n"] == 2 and cell["target_hits"] == 0 and cell["codes"] == 1)
    finally:
        globals()["production_gate_mask"] = gate_backup
        globals()["production_smc_mask"] = smc_backup
    if failures:
        raise SystemExit(f"self-test failures: {failures}")
    print("self-test=ok", flush=True)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--self-test":
        self_test()
        sys.exit(0)
    main()
