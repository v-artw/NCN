"""Paper-only state helpers for NCN Web monitor snapshots."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from .demo import BOUNDARY_FLAGS, read_audit_events, validate_portfolio_id

SCHEMA_VERSION = "ncn_paper_status_v1"


class PaperTradingError(ValueError):
    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        super().__init__(detail)


def paper_status_payload(
    *,
    portfolio: Mapping[str, Any],
    paper_state_root: Path,
    audit_root: Path,
    risk_controls: Mapping[str, Any],
    freshness_warnings: list[str] | None = None,
) -> dict[str, Any]:
    portfolio_id = validate_portfolio_id(str(portfolio.get("portfolio_id", "default")))
    paper_state_root.mkdir(parents=True, exist_ok=True)
    positions = dict(portfolio.get("positions", {}))
    return {
        "schema_version": SCHEMA_VERSION,
        "portfolio_id": portfolio_id,
        **BOUNDARY_FLAGS,
        "live_broker_enabled": False,
        "broker_connection": "none",
        "paper_state_root": str(paper_state_root),
        "simulated_cash": float(portfolio.get("demo_cash", 0.0)),
        "simulated_initial_capital": float(portfolio.get("initial_capital", 0.0)),
        "simulated_max_equity_high": float(portfolio.get("demo_max_equity_high", 0.0)),
        "simulated_positions": list(positions.values()),
        "risk_controls": dict(risk_controls),
        "freshness_warnings": list(freshness_warnings or []),
        "limitations": [
            "paper_simulation_only",
            "no_broker_connection",
            "not_execution_feed",
            "not_investment_advice",
        ],
        "recent_events": read_audit_events(audit_root, limit=20),
    }


def paper_history_payload(*, audit_root: Path, portfolio_id: str, limit: int = 50) -> dict[str, Any]:
    safe_id = validate_portfolio_id(portfolio_id)
    events = [
        event
        for event in read_audit_events(audit_root, limit=limit)
        if event.get("payload", {}).get("portfolio_id") in (safe_id, None)
    ]
    return {
        "schema_version": "ncn_paper_history_v1",
        "portfolio_id": safe_id,
        **BOUNDARY_FLAGS,
        "events": events,
        "source": "ncn_demo_portfolio_audit_jsonl",
    }


__all__ = [
    "BOUNDARY_FLAGS",
    "PaperTradingError",
    "SCHEMA_VERSION",
    "paper_history_payload",
    "paper_status_payload",
]
