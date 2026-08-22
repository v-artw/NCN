"""Demo portfolio route payloads for the NCN Web console."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import TYPE_CHECKING, Any

from ...portfolio.demo import (
    DemoPortfolioError,
    add_position,
    append_audit_event,
    import_positions,
    list_factors,
    list_portfolios,
    load_portfolio,
    remove_position,
    reset_capital,
    save_portfolio,
    set_settings,
    update_position,
    validate_portfolio_id,
)

if TYPE_CHECKING:
    from ..app import ResearchWebContext


def load_demo_portfolio(context: "ResearchWebContext", portfolio_id: str | None = None) -> dict[str, Any]:
    return load_portfolio(
        context.demo_state_root,
        portfolio_id or context.demo_default_portfolio_id,
        initial_capital=context.demo_initial_capital,
        max_positions=context.demo_max_positions,
    )


def list_demo_portfolios_payload(context: "ResearchWebContext", boundary_payload: Mapping[str, Any]) -> dict[str, Any]:
    portfolios = list_portfolios(context.demo_state_root)
    if not portfolios:
        load_demo_portfolio(context)
        portfolios = list_portfolios(context.demo_state_root)
    return {
        "schema_version": "ncn_demo_portfolio_list_v1",
        "portfolios": portfolios[: context.demo_max_portfolios],
        **dict(boundary_payload),
    }


def demo_portfolio_status_payload(
    context: "ResearchWebContext",
    boundary_payload: Mapping[str, Any],
    portfolio_id: str | None = None,
) -> dict[str, Any]:
    portfolio = load_demo_portfolio(context, portfolio_id)
    return {
        "portfolio": portfolio,
        "factors": list_factors(context.demo_factor_root),
        **dict(boundary_payload),
    }


def demo_factors_payload(context: "ResearchWebContext", boundary_payload: Mapping[str, Any]) -> dict[str, Any]:
    return {"factors": list_factors(context.demo_factor_root), **dict(boundary_payload)}


def handle_demo_portfolio_mutation(
    *,
    context: "ResearchWebContext",
    path: str,
    payload: Mapping[str, Any],
    boundary_payload: Mapping[str, Any],
    normalize_code: Callable[[str], str],
) -> dict[str, Any]:
    portfolio_id = validate_portfolio_id(str(payload.get("portfolio_id") or context.demo_default_portfolio_id))
    portfolio = load_demo_portfolio(context, portfolio_id)
    event_payload: dict[str, Any] = {"portfolio_id": portfolio_id}
    if path == "/api/demo-portfolio/add":
        code = normalize_code(str(payload.get("code", "")))
        portfolio = add_position(
            portfolio,
            code=code,
            state=str(payload.get("state", "WATCH")),
            quantity=float(payload.get("quantity", 0.0) or 0.0),
            reference_price=float(payload.get("reference_price", 0.0) or 0.0),
            note=str(payload.get("note", "")),
        )
        event_type = "demo_position_added"
        event_payload["code"] = code
    elif path == "/api/demo-portfolio/remove":
        code = normalize_code(str(payload.get("code", "")))
        portfolio = remove_position(portfolio, code=code)
        event_type = "demo_position_removed"
        event_payload["code"] = code
    elif path == "/api/demo-portfolio/update":
        code = normalize_code(str(payload.get("code", "")))
        updates = payload.get("updates", {})
        if not isinstance(updates, Mapping):
            raise DemoPortfolioError("invalid_position_update", "updates 必须是对象")
        portfolio = update_position(portfolio, code=code, updates=updates)
        event_type = "demo_position_updated"
        event_payload["code"] = code
    elif path == "/api/demo-portfolio/settings":
        portfolio = set_settings(
            portfolio,
            max_positions=int(payload.get("max_positions", context.demo_max_positions)),
            configured_max_positions=context.demo_max_positions,
        )
        event_type = "demo_settings_updated"
        event_payload["max_positions"] = portfolio["settings"]["max_positions"]
    elif path == "/api/demo-portfolio/import":
        rows = payload.get("positions", [])
        if not isinstance(rows, list):
            raise DemoPortfolioError("invalid_import", "positions 必须是数组")
        portfolio = import_positions(
            portfolio,
            rows,
            max_import_positions=context.demo_max_import_positions,
            normalize_code=normalize_code,
        )
        event_type = "demo_positions_imported"
        event_payload["import_count"] = len(rows)
    elif path == "/api/demo-portfolio/reset-capital":
        portfolio = reset_capital(
            portfolio,
            initial_capital=float(payload.get("initial_capital", context.demo_initial_capital)),
        )
        event_type = "demo_capital_reset"
        event_payload["initial_capital"] = portfolio["initial_capital"]
    else:
        raise DemoPortfolioError("unknown_demo_portfolio_route", "未知 demo portfolio mutation")
    save_portfolio(context.demo_state_root, portfolio)
    append_audit_event(context.demo_audit_root, event_type, event_payload)
    return {"portfolio": portfolio, "event_type": event_type, **dict(boundary_payload)}


__all__ = [
    "demo_factors_payload",
    "demo_portfolio_status_payload",
    "handle_demo_portfolio_mutation",
    "list_demo_portfolios_payload",
    "load_demo_portfolio",
]
