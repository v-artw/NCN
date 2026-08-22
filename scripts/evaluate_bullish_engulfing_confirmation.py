#!/usr/bin/env python3
"""Evaluate the frozen bullish-engulfing confirmation hypothesis."""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
import tempfile
from collections import defaultdict
from collections.abc import Sequence
from pathlib import Path
from typing import Any

for _name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[_name] = "1"

import pandas as pd

from ashare_edge_scout.config import load_config
from ashare_edge_scout.research_bullish_engulfing import (
    PERIODS, aggregate, confirmed_at_t, context_at_t, engulfing_at_t, evaluate_decision,
)
from ashare_edge_scout.research_precision70 import PREFIXES, production_gate_mask, stable_sample


COLUMNS = ["date", "open", "high", "low", "close", "preclose", "volume", "amount", "tradestatus", "isST"]


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


def _label(frame: pd.DataFrame, index: int) -> bool | None:
    if index + 6 >= len(frame):
        return None
    future = frame.iloc[index + 2:index + 7]
    if len(future) != 5 or not future["tradestatus"].eq("1").all():
        return None
    reference = float(frame.iloc[index + 1]["close"])
    closes = future["close"].astype(float)
    return bool(closes.max() >= reference * 1.03 and closes.min() >= reference * 0.97)


def evaluate_code(task: tuple[str, dict[str, Any]]) -> pd.DataFrame:
    path_text, config = task
    path = Path(path_text)
    frame = pd.read_parquet(path, columns=COLUMNS)
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame = frame.dropna(subset=["date"]).sort_values("date", kind="stable").drop_duplicates("date", keep="last").reset_index(drop=True)
    records = frame.to_dict("records")
    admitted = production_gate_mask(path.stem, frame, config)
    rows = []
    for index in range(65, len(frame) - 6):
        if not bool(admitted.iat[index]) or _label(frame, index) is None:
            continue
        if not context_at_t(records, index):
            continue
        rows.append({
            "code": path.stem,
            "date": frame.at[index, "date"],
            "trading_index": int(frame["tradestatus"].eq("1").iloc[: index + 1].sum() - 1),
            "label": _label(frame, index),
            "candidate": confirmed_at_t(records, index),
            "pattern": engulfing_at_t(records, index),
        })
    return pd.DataFrame(rows, columns=["code", "date", "trading_index", "label", "candidate", "pattern"])


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
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
    code_list = [path.stem for path in paths]
    code_hash = hashlib.sha256(("\n".join(code_list) + "\n").encode("ascii")).hexdigest()
    config = load_config(args.config)
    with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers) as executor:
        panels = list(executor.map(evaluate_code, [(str(path), config) for path in paths], chunksize=1))
    rows = pd.concat(panels, ignore_index=True) if panels else pd.DataFrame()
    primary, all_origin = aggregate(rows)
    report = {
        "study": "bullish_engulfing_confirmation_stage1",
        "classification_only": True,
        "historical_research_only": True,
        "not_prospective_evidence": True,
        "no_execution_or_pnl": True,
        "raw_future_rows_exposed": False,
        "label_inputs_ephemeral": True,
        "sample": {"method": "precision70_sha256_code_stem", "codes": len(paths), "code_list_sha256": code_hash},
        "workers": args.workers,
        "periods": PERIODS,
        "primary_metrics": primary,
        "all_origin_sensitivity": all_origin,
        "decision": evaluate_decision(primary, all_origin),
        "caveats": ["Adjusted research OHLCV, current-file survivorship, and retrospective classification limitations remain."],
    }
    _atomic_json(args.output, report)


if __name__ == "__main__":
    main()
