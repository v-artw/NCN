"""Compatibility entrypoint for the NCN Web console.

The implementation lives in :mod:`ashare_edge_scout.web.app` so Web routes can be
split gradually without breaking existing scripts or tests that import this module.
"""

from __future__ import annotations

from .web.app import (
    ResearchWebContext,
    ResearchWebError,
    create_context,
    demo_portfolio_status_payload,
    list_demo_portfolios_payload,
    load_candle_research,
    load_dashboard,
    load_snapshot_research,
    make_handler,
    normalize_a_share_code,
    paper_data_status_for_portfolio,
    paper_status_for_portfolio,
    pmkf_mkf_code_payload,
    pmkf_mkf_reports_payload,
    pmkf_mkf_summary_payload,
    serve,
    main,
    _build_research_alert,
)

__all__ = [
    "ResearchWebContext",
    "ResearchWebError",
    "create_context",
    "demo_portfolio_status_payload",
    "list_demo_portfolios_payload",
    "load_candle_research",
    "load_dashboard",
    "load_snapshot_research",
    "make_handler",
    "normalize_a_share_code",
    "paper_data_status_for_portfolio",
    "paper_status_for_portfolio",
    "pmkf_mkf_code_payload",
    "pmkf_mkf_reports_payload",
    "pmkf_mkf_summary_payload",
    "serve",
    "main",
    "_build_research_alert",
]


if __name__ == "__main__":
    raise SystemExit(main())
