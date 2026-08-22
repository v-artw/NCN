#!/usr/bin/env python3
"""Evaluate the frozen Shengbei-long-state plus KDJ-buy combination."""

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

for _name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[_name] = "1"

import pandas as pd

from ashare_edge_scout.config import load_config
from ashare_edge_scout.research_futu_combination import (
    COMBINATION, PARENT, aggregate_combination_metrics, attach_combination, evaluate_combination,
)
from ashare_edge_scout.research_futu_ranking import PERIODS, build_futu_panel
from ashare_edge_scout.research_precision70 import PREFIXES


EXPECTED_CODE_LIST_SHA256 = "42796131b236f1e11a0fc85fdaf2270241e8208c2c62530c7f664f6728f9232e"
REQUIRED_COLUMNS = [
    "date", "open", "high", "low", "close", "preclose", "volume", "amount",
    "tradestatus", "isST",
]


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=Path("PFrontStockData"))
    parser.add_argument("--config", type=Path, default=Path("yaml/edge_scout_v1.yaml"))
    parser.add_argument("--workers", type=int, default=min(os.cpu_count() or 1, 8))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if not 1 <= args.workers <= 8:
        parser.error("--workers must be between 1 and 8")
    return args


def _evaluate_stock(task: tuple[str, dict[str, Any]]) -> pd.DataFrame:
    path_text, config = task
    path = Path(path_text)
    frame = pd.read_parquet(path, columns=REQUIRED_COLUMNS)
    return attach_combination(build_futu_panel(path.stem, frame, config))


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
    paths = sorted(
        (path for path in args.data_root.glob("*.parquet") if path.stem.startswith(PREFIXES)),
        key=lambda path: path.stem,
    )
    code_list = [path.stem for path in paths]
    code_list_sha256 = hashlib.sha256(("\n".join(code_list) + "\n").encode("ascii")).hexdigest()
    if code_list_sha256 != EXPECTED_CODE_LIST_SHA256:
        raise SystemExit(
            f"frozen code-list SHA-256 mismatch: expected {EXPECTED_CODE_LIST_SHA256}, got {code_list_sha256}"
        )
    config = load_config(args.config)
    tasks = [(str(path), config) for path in paths]
    panels = []
    with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers) as executor:
        for completed, panel in enumerate(executor.map(_evaluate_stock, tasks, chunksize=1), start=1):
            panels.append(panel)
            if completed % 100 == 0 or completed == len(tasks):
                print(f"processed {completed}/{len(tasks)} codes", flush=True)
    primary, all_origin = aggregate_combination_metrics(pd.concat(panels, ignore_index=True))
    report = {
        "study": "shengbei_long_state_plus_kdj_buy",
        "classification_only": True,
        "signal": "T-1 shengbei_state == 1 AND T kdj_trend_pro_buy",
        "combination": COMBINATION,
        "parent": PARENT,
        "sample": {
            "method": "all_current_main_board_sorted_code",
            "codes": len(paths),
            "code_list": code_list,
            "code_list_sha256": code_list_sha256,
        },
        "workers": args.workers,
        "periods": PERIODS,
        "primary_observations": "per-stock origins at least five tradable indices apart",
        "market_baseline": "combination-count-weighted same-date mature admitted precision; dates require at least 150 rows",
        "parent_baseline": "KDJ triggers on combination dates, weighted by combination count",
        "primary_metrics": primary,
        "all_origin_sensitivity": all_origin,
        "decision": evaluate_combination(primary, all_origin),
        "caveats": [
            "Adjusted local research data, current-file survivorship, and retrospective formula inspection remain limitations.",
            "Passing retrospective gates would authorize only unchanged prospective observation.",
            "Classification evidence is not profitability, execution, or personalized investment advice.",
        ],
    }
    _atomic_json(args.output, report)


if __name__ == "__main__":
    main()
