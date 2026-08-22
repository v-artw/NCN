#!/usr/bin/env python3
"""Evaluate full-sample D-open T+1 barrier path quality."""

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
from ashare_edge_scout.research_barrier_quality import DEFAULT_START_DATE, build_barrier_panel, build_barrier_report
from ashare_edge_scout.research_precision70 import PREFIXES

REQUIRED_COLUMNS = ["date", "open", "high", "low", "close", "preclose", "volume", "amount", "tradestatus", "isST"]


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=Path("PFrontStockData"))
    parser.add_argument("--config", type=Path, default=Path("yaml/edge_scout_v1.yaml"))
    parser.add_argument("--start-date", default=DEFAULT_START_DATE)
    parser.add_argument("--end-date", default=None)
    parser.add_argument("--workers", type=int, default=min(os.cpu_count() or 1, 8))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if not 1 <= args.workers <= 8:
        parser.error("--workers must be between 1 and 8")
    return args


def _stock(task: tuple[str, dict[str, Any], str, str | None]) -> pd.DataFrame:
    path_text, config, start_date, end_date = task
    path = Path(path_text)
    frame = pd.read_parquet(path, columns=REQUIRED_COLUMNS)
    return build_barrier_panel(path.stem, frame, config, start_date=start_date, end_date=end_date)


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
    paths = sorted((path for path in args.data_root.glob("*.parquet") if path.stem.startswith(PREFIXES)), key=lambda path: path.stem)
    if not paths:
        raise SystemExit("no current main-board Parquet files found")
    config = load_config(args.config)
    tasks = [(str(path), config, args.start_date, args.end_date) for path in paths]
    with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers) as executor:
        panels = []
        for completed, panel in enumerate(executor.map(_stock, tasks, chunksize=1), start=1):
            panels.append(panel)
            if completed % 100 == 0 or completed == len(tasks):
                print(f"processed {completed}/{len(tasks)} codes", flush=True)
    code_list = [path.stem for path in paths]
    report = build_barrier_report(
        panel=pd.concat(panels, ignore_index=True),
        code_list=code_list,
        code_list_sha256=hashlib.sha256(("\n".join(code_list) + "\n").encode("ascii")).hexdigest(),
        start_date=args.start_date,
        end_date=args.end_date,
        workers=args.workers,
    )
    _atomic_json(args.output, report)


if __name__ == "__main__":
    main()
