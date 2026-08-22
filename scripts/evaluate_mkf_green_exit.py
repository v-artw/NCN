#!/usr/bin/env python3
"""Evaluate the preregistered strict MkF all-lines-above-20 transition."""

from __future__ import annotations

import argparse
import concurrent.futures
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
from ashare_edge_scout.research_mkf import (
    PERIODS, aggregate_mkf_metrics, build_mkf_panel, evaluate_mkf_decision,
)
from ashare_edge_scout.research_precision70 import stable_sample


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
    return build_mkf_panel(path.stem, frame, config)


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
    paths = stable_sample(list(args.data_root.glob("*.parquet")))
    config = load_config(args.config)
    with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers) as executor:
        panels = list(executor.map(_evaluate_stock, [(str(path), config) for path in paths], chunksize=1))
    panel = pd.concat(panels, ignore_index=True)
    summaries, sensitivity = aggregate_mkf_metrics(panel)
    decision = evaluate_mkf_decision(summaries, sensitivity)
    report = {
        "study": "strict_mkf_green_zone_exit_stage1",
        "classification_only": True,
        "sample": {"method": "sha256_code_stem", "codes": 400, "code_list": [path.stem for path in paths]},
        "workers": args.workers,
        "periods": PERIODS,
        "formula": {
            "transition": "T-1 momentum/inter/near <=20; T all three >20",
            "momentum": "(close-LLV(low,2))/(HHV(high,4)-LLV(low,4))*100",
            "inter": "MA(range_position_20,5)",
            "near": "MA(range_position_15,2)",
            "rolling_rows": "tradable stock rows only",
        },
        "label": "next five tradable closes reach +3pct and never close below -3pct",
        "baseline": "all production-admitted stocks on dates with at least one signal",
        "summaries": summaries,
        "nonoverlapping_origin_sensitivity": sensitivity,
        "decision": decision,
        "caveats": [
            "MkF source formula omitted numeric lengths; this run uses the project-local 20/15 and 2/4 mapping frozen before outcomes.",
            "Current-file survivorship, adjusted-data vintage, and overlapping labels remain limitations.",
            "Classification evidence is not profitability, execution, or personalized investment advice.",
        ],
    }
    _atomic_json(args.output, report)


if __name__ == "__main__":
    main()
