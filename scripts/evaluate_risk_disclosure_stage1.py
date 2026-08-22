#!/usr/bin/env python3
"""Evaluate the preregistered CNInfo risk-disclosure exclusion Stage 1."""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
import tempfile
from collections import defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

for _name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[_name] = "1"

import pandas as pd

from ashare_edge_scout.config import load_config
from ashare_edge_scout.research_precision70 import build_stock_panel, stable_sample
from ashare_edge_scout.research_risk_disclosure import (
    PERIODS,
    aggregate_risk_metrics,
    apply_risk_events,
    evaluate_risk_decision,
)


REQUIRED_COLUMNS = [
    "date", "open", "high", "low", "close", "preclose", "volume", "amount",
    "tradestatus", "isST",
]
CATEGORY_IDS = {
    "category_bcgz_szsh", "category_cqdq_szsh", "category_fxts_szsh",
    "category_tbclts_szsh",
}


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=Path("PFrontStockData"))
    parser.add_argument("--config", type=Path, default=Path("yaml/edge_scout_v1.yaml"))
    parser.add_argument("--events", type=Path, required=True)
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
    return build_stock_panel(path.stem, frame, config, start_date="2021-01-01")


def _load_events(path: Path, expected_codes: Sequence[str]) -> tuple[dict[str, list[int]], dict[str, Any]]:
    raw = path.read_bytes()
    value = json.loads(raw)
    codes = [str(code) for code in value.get("codes", [])]
    expected_digits = [code.split(".", 1)[1] for code in expected_codes]
    if codes != expected_digits:
        raise ValueError("event cache codes do not match the frozen sample")
    if set(value.get("category_ids", [])) != CATEGORY_IDS:
        raise ValueError("event cache categories do not match preregistration")
    if value.get("request_range") != ["2021-01-01", "2026-08-15"]:
        raise ValueError("event cache date range does not match preregistration")
    events: dict[str, list[int]] = defaultdict(list)
    seen: set[str] = set()
    for item in value.get("per_code", []):
        code = str(item.get("code", ""))
        for row in item.get("announcements", []):
            announcement_id = str(row.get("announcement_id", ""))
            timestamp = row.get("timestamp_ms")
            if not announcement_id or announcement_id in seen:
                continue
            if str(row.get("code", "")) != code or not isinstance(timestamp, (int, float)):
                raise ValueError("invalid event cache row")
            seen.add(announcement_id)
            prefix = "sh" if code.startswith("6") else "sz"
            events[f"{prefix}.{code}"].append(int(timestamp))
    metadata = {
        "path": str(path),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "retrieved_at": value.get("retrieved_at"),
        "distinct_announcements": len(seen),
        "source_url": value.get("source_url"),
        "source_adapter": value.get("source_adapter"),
        "source_adapter_commit": value.get("source_adapter_commit"),
    }
    return dict(events), metadata


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
    codes = [path.stem for path in paths]
    events, event_metadata = _load_events(args.events, codes)
    config = load_config(args.config)
    tasks = [(str(path), config) for path in paths]
    with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers) as executor:
        panels = list(executor.map(_evaluate_stock, tasks, chunksize=1))
    panel = apply_risk_events(pd.concat(panels, ignore_index=True), events)
    summaries, sensitivity = aggregate_risk_metrics(panel)
    decision = evaluate_risk_decision(summaries, sensitivity)
    risk_rows = panel.loc[panel["recent_risk_disclosure"]]
    report = {
        "study": "cninfo_risk_disclosure_exclusion_stage1",
        "classification_only": True,
        "sample": {"method": "sha256_code_stem", "codes": 400, "code_list": codes},
        "workers": args.workers,
        "periods": PERIODS,
        "event_cache": event_metadata,
        "candidate": {
            "baseline": "production_admitted AND mhpg_buy",
            "rule": "baseline AND no fixed-category CNInfo announcement available in latest 10 tradable stock dates",
            "availability": "next tradable stock date after provider Asia/Shanghai calendar date",
            "categories": sorted(CATEGORY_IDS),
        },
        "risk_window_coverage": {
            "stock_dates": int(len(risk_rows)),
            "codes": int(risk_rows["code"].nunique()),
            "first_date": risk_rows["date"].min().strftime("%Y-%m-%d") if len(risk_rows) else None,
            "last_date": risk_rows["date"].max().strftime("%Y-%m-%d") if len(risk_rows) else None,
        },
        "summaries": summaries,
        "nonoverlapping_origin_sensitivity": sensitivity,
        "decision": decision,
        "source_and_caveats": [
            "CNInfo historical category responses are archived at one retrieval vintage; exact exchange publication time is conservatively shifted to the next tradable stock date.",
            "Current-file universe survivorship, adjusted-data vintage, and overlapping labels remain limitations.",
            "Holdout output is an immutable audit and cannot be used to redesign this stopped candidate if any gate fails.",
        ],
    }
    _atomic_json(args.output, report)


if __name__ == "__main__":
    main()
