"""Paper monitor route payloads for the NCN Web console."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...portfolio.paper_snapshot import paper_data_status_payload
from ...portfolio.paper_state import paper_history_payload, paper_status_payload
from .demo import load_demo_portfolio

if TYPE_CHECKING:
    from ..app import ResearchWebContext


def paper_status_for_portfolio(context: "ResearchWebContext", portfolio_id: str | None = None) -> dict[str, object]:
    portfolio = load_demo_portfolio(context, portfolio_id)
    data_status = paper_data_status_payload(
        portfolio_id=str(portfolio["portfolio_id"]),
        positions=dict(portfolio.get("positions", {})),
        data_root=context.data_root,
        max_snapshot_codes=context.paper_max_snapshot_codes,
    )
    return paper_status_payload(
        portfolio=portfolio,
        paper_state_root=context.paper_state_root,
        audit_root=context.demo_audit_root,
        risk_controls=context.paper_risk_controls,
        freshness_warnings=list(data_status.get("freshness_warnings", [])),
    )


def paper_data_status_for_portfolio(context: "ResearchWebContext", portfolio_id: str | None = None) -> dict[str, object]:
    portfolio = load_demo_portfolio(context, portfolio_id)
    return paper_data_status_payload(
        portfolio_id=str(portfolio["portfolio_id"]),
        positions=dict(portfolio.get("positions", {})),
        data_root=context.data_root,
        max_snapshot_codes=context.paper_max_snapshot_codes,
    )


__all__ = ["paper_data_status_for_portfolio", "paper_history_payload", "paper_status_for_portfolio"]
