#!/usr/bin/env python3
"""Create a new immutable maturity audit for prospective watchlist snapshots."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path

from ashare_edge_scout.audit.prospective import build_prospective_audit


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=Path("output/edge_scout"))
    parser.add_argument("--data-root", type=Path, default=Path("PFrontStockData"))
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def _write_new_json(path: Path, value: dict) -> None:
    if path.exists():
        raise FileExistsError(f"prospective audit already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        if path.exists():
            raise FileExistsError(f"prospective audit already exists: {path}")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main() -> int:
    args = parse_args()
    report = build_prospective_audit(args.output_root, args.data_root)
    _write_new_json(args.output, report)
    print(f"canonical_snapshots={report['snapshot_report']['canonical']}")
    print(f"mature_all_watch={report['cohorts']['all_watch']['n']}")
    print(f"pending_all_watch={report['cohorts']['all_watch']['status_counts'].get('pending', 0)}")
    print(f"evidence_sufficient={report['evidence_sufficient']}")
    print(f"output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
