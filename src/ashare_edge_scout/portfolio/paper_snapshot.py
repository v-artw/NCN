"""Bounded paper monitor data-status snapshots."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence

from ..data.daily_bars import DataValidationError, load_local_daily_bars
from .demo import BOUNDARY_FLAGS, validate_portfolio_id


def paper_data_status_payload(
    *,
    portfolio_id: str,
    positions: Mapping[str, Any],
    data_root: Path,
    max_snapshot_codes: int,
) -> dict[str, Any]:
    safe_id = validate_portfolio_id(portfolio_id)
    codes = list(positions)[: int(max_snapshot_codes)]
    statuses = [_code_data_status(code, data_root) for code in codes]
    warnings = sorted({warning for item in statuses for warning in item.get("warnings", [])})
    return {
        "schema_version": "ncn_paper_data_status_v1",
        "portfolio_id": safe_id,
        **BOUNDARY_FLAGS,
        "data_root": str(data_root),
        "checked_code_count": len(statuses),
        "max_snapshot_codes": int(max_snapshot_codes),
        "codes_truncated": len(positions) > int(max_snapshot_codes),
        "statuses": statuses,
        "freshness_warnings": warnings,
        "limitations": [
            "local_research_parquet_only",
            "not_execution_freshness",
            "no_broker_feed",
        ],
    }


def freshness_warnings_for_positions(
    positions: Mapping[str, Any],
    *,
    data_root: Path,
    max_snapshot_codes: int,
) -> list[str]:
    payload = paper_data_status_payload(
        portfolio_id="default",
        positions=positions,
        data_root=data_root,
        max_snapshot_codes=max_snapshot_codes,
    )
    return list(payload["freshness_warnings"])


def _code_data_status(code: str, data_root: Path) -> dict[str, Any]:
    path = data_root / f"{code}.parquet"
    if not path.is_file():
        return {"code": code, "status": "missing", "latest_date": None, "warnings": ["missing_research_parquet"]}
    try:
        records = list(load_local_daily_bars(code, data_root=data_root))
    except DataValidationError as exc:
        return {"code": code, "status": "invalid", "latest_date": None, "warnings": [exc.code]}
    if not records:
        return {"code": code, "status": "empty", "latest_date": None, "warnings": ["empty_research_parquet"]}
    latest = records[-1]
    return {
        "code": code,
        "status": "available",
        "latest_date": str(latest.get("date")),
        "warnings": ["research_data_only"],
    }


__all__ = [
    "paper_data_status_payload",
    "freshness_warnings_for_positions",
]
