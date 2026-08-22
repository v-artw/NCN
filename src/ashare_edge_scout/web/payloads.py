"""Web payload-builder facade for gradual route extraction."""

from __future__ import annotations

from .app import (
    demo_portfolio_status_payload,
    list_demo_portfolios_payload,
    load_candle_research,
    load_dashboard,
    load_snapshot_research,
    paper_data_status_for_portfolio,
    paper_status_for_portfolio,
    pmkf_mkf_code_payload,
    pmkf_mkf_reports_payload,
    pmkf_mkf_summary_payload,
)

__all__ = [
    "demo_portfolio_status_payload",
    "list_demo_portfolios_payload",
    "load_candle_research",
    "load_dashboard",
    "load_snapshot_research",
    "paper_data_status_for_portfolio",
    "paper_status_for_portfolio",
    "pmkf_mkf_code_payload",
    "pmkf_mkf_reports_payload",
    "pmkf_mkf_summary_payload",
]
