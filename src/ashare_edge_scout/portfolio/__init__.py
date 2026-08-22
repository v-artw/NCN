"""NCN demo portfolio and paper-only state boundaries."""

from .demo import (
    ALLOWED_POSITION_STATES,
    BOUNDARY_FLAGS,
    DemoPortfolioError,
    add_position,
    append_audit_event,
    default_portfolio,
    import_positions,
    list_factors,
    list_portfolios,
    load_portfolio,
    read_audit_events,
    remove_position,
    reset_capital,
    save_portfolio,
    set_settings,
    update_position,
    validate_factor_filename,
    validate_portfolio_id,
)
from .paper_risk import DEFAULT_PAPER_RISK, normalize_paper_risk
from .paper_snapshot import freshness_warnings_for_positions, paper_data_status_payload
from .paper_state import PaperTradingError, paper_history_payload, paper_status_payload

__all__ = [
    "ALLOWED_POSITION_STATES",
    "BOUNDARY_FLAGS",
    "DEFAULT_PAPER_RISK",
    "DemoPortfolioError",
    "PaperTradingError",
    "add_position",
    "append_audit_event",
    "default_portfolio",
    "freshness_warnings_for_positions",
    "import_positions",
    "list_factors",
    "list_portfolios",
    "load_portfolio",
    "normalize_paper_risk",
    "paper_data_status_payload",
    "paper_history_payload",
    "paper_status_payload",
    "read_audit_events",
    "remove_position",
    "reset_capital",
    "save_portfolio",
    "set_settings",
    "update_position",
    "validate_factor_filename",
    "validate_portfolio_id",
]
