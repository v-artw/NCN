#!/usr/bin/env python3
"""Evaluate the preregistered unified ``futu.md`` indicator ranking."""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

BLAS_THREAD_VARIABLES = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS")
for _name in BLAS_THREAD_VARIABLES:
    os.environ[_name] = "1"

import pandas as pd

from ashare_edge_scout.config import load_config
from ashare_edge_scout.research_futu_ranking import (
    CANDIDATES, PERIODS, aggregate_futu_metrics, build_futu_panel, evaluate_futu_ranking,
)
from ashare_edge_scout.research_precision70 import stable_sample
from ashare_edge_scout.research_precision70 import PREFIXES


REQUIRED_COLUMNS = [
    "date", "open", "high", "low", "close", "preclose", "volume", "amount",
    "tradestatus", "isST",
]


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=Path("PFrontStockData"))
    parser.add_argument("--config", type=Path, default=Path("yaml/edge_scout_v1.yaml"))
    parser.add_argument("--max-codes", type=int, default=400)
    parser.add_argument("--universe", choices=("sample-400", "all-main-board"), default="sample-400")
    parser.add_argument("--workers", type=int, default=min(os.cpu_count() or 1, 8))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.universe == "sample-400" and args.max_codes != 400:
        parser.error("--max-codes must equal 400")
    if args.universe == "all-main-board" and args.max_codes != 400:
        parser.error("--max-codes is not configurable with --universe all-main-board")
    if not 1 <= args.workers <= 8:
        parser.error("--workers must be between 1 and 8")
    return args


def _evaluate_stock(task: tuple[str, dict[str, Any]]) -> pd.DataFrame:
    path_text, config = task
    path = Path(path_text)
    frame = pd.read_parquet(path, columns=REQUIRED_COLUMNS)
    return build_futu_panel(path.stem, frame, config)


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


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    available = list(args.data_root.glob("*.parquet"))
    if args.universe == "sample-400":
        paths = stable_sample(available, args.max_codes)
    else:
        paths = sorted((path for path in available if path.stem.startswith(PREFIXES)), key=lambda path: path.stem)
        if not paths:
            raise SystemExit("no current main-board Parquet files found")
    config = load_config(args.config)
    tasks = [(str(path), config) for path in paths]
    with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers) as executor:
        panels = []
        for completed, panel in enumerate(executor.map(_evaluate_stock, tasks, chunksize=1), start=1):
            panels.append(panel)
            if completed % 100 == 0 or completed == len(tasks):
                print(f"processed {completed}/{len(tasks)} codes", flush=True)
    panel = pd.concat(panels, ignore_index=True)
    primary, all_origin, coverage = aggregate_futu_metrics(panel)
    code_list = [path.stem for path in paths]
    code_list_sha256 = hashlib.sha256(("\n".join(code_list) + "\n").encode("ascii")).hexdigest()
    report = {
        "study": "futu_indicator_family_ranking",
        "classification_only": True,
        "sample": {
            "method": "precision70_sha256_code_stem" if args.universe == "sample-400" else "all_current_main_board_sorted_code",
            "codes": len(paths), "code_list": code_list, "code_list_sha256": code_list_sha256,
        },
        "workers": args.workers,
        "periods": PERIODS,
        "candidates": list(CANDIDATES),
        "primary_observations": "per-stock origins at least five tradable indices apart",
        "baseline": "indicator-specific same-date mature admitted precision, weighted by signal count; dates require at least 150 rows",
        "primary_metrics": primary,
        "all_origin_sensitivity": all_origin,
        "trigger_coverage": coverage,
        "decision": evaluate_futu_ranking(primary, all_origin),
        "caveats": [
            "Adjusted local research data, current-file survivorship, and retrospective formula inspection remain limitations.",
            "The MkF proxy uses its separately frozen project-local mapping.",
            "Shengbei initializes the first valid trailing-wave state short and carries direction through neutral rows.",
            "Classification evidence is not profitability, execution, or personalized investment advice.",
        ],
    }
    _atomic_json(args.output, report)


if __name__ == "__main__":
    main()
