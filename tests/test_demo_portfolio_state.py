from __future__ import annotations

import json
from pathlib import Path

import pytest

from ashare_edge_scout.demo_portfolio_state import (
    DemoPortfolioError,
    add_position,
    append_audit_event,
    import_positions,
    list_factors,
    load_portfolio,
    remove_position,
    reset_capital,
    save_portfolio,
    set_settings,
    update_position,
    validate_factor_filename,
    validate_portfolio_id,
)


def test_missing_demo_portfolio_creates_default_schema(tmp_path: Path) -> None:
    portfolio = load_portfolio(tmp_path, "default", initial_capital=20000.0, max_positions=5)

    assert portfolio["schema_version"] == "ncn_demo_portfolio_v1"
    assert portfolio["paper_only"] is True
    assert portfolio["live_execution_enabled"] is False
    assert portfolio["allow_live_order_submission"] is False
    assert portfolio["broker_account_id"] is None
    assert portfolio["demo_cash"] == 20000.0
    assert (tmp_path / "default.json").is_file()


def test_portfolio_id_and_factor_filename_reject_traversal() -> None:
    assert validate_portfolio_id("alpha_1") == "alpha_1"
    assert validate_factor_filename("factor_1.txt") == "factor_1.txt"
    for value in ("../x", ".hidden", "a/b", "x..y"):
        with pytest.raises(DemoPortfolioError):
            validate_portfolio_id(value)
    for value in ("../x.txt", ".x.txt", "x.json", "a/b.txt"):
        with pytest.raises(DemoPortfolioError):
            validate_factor_filename(value)


def test_add_update_remove_and_settings_enforce_schema(tmp_path: Path) -> None:
    portfolio = load_portfolio(tmp_path, "default", initial_capital=10000.0, max_positions=2)
    portfolio = add_position(portfolio, code="sh.600000", state="WATCH", quantity=100, reference_price=10.5)
    portfolio = update_position(portfolio, code="sh.600000", updates={"state": "PAPER_PRE_BUY", "note": "review"})

    assert portfolio["positions"]["sh.600000"]["state"] == "PAPER_PRE_BUY"
    assert portfolio["positions"]["sh.600000"]["note"] == "review"
    with pytest.raises(DemoPortfolioError, match="不允许字段"):
        update_position(portfolio, code="sh.600000", updates={"broker_account_id": "x"})
    with pytest.raises(DemoPortfolioError, match="position state"):
        add_position(portfolio, code="sh.600001", state="BUY")
    portfolio = set_settings(portfolio, max_positions=2, configured_max_positions=2)
    portfolio = remove_position(portfolio, code="sh.600000")
    assert portfolio["positions"] == {}


def test_import_positions_enforces_caps_and_normalizes_codes(tmp_path: Path) -> None:
    portfolio = load_portfolio(tmp_path, "default", initial_capital=10000.0, max_positions=2)
    portfolio = import_positions(
        portfolio,
        [{"code": "600000", "state": "WATCH"}],
        max_import_positions=2,
        normalize_code=lambda code: f"sh.{code}" if code.isdigit() else code,
    )

    assert "sh.600000" in portfolio["positions"]
    with pytest.raises(DemoPortfolioError, match="导入 positions 超出上限"):
        import_positions(portfolio, [{"code": "1"}, {"code": "2"}, {"code": "3"}], max_import_positions=2, normalize_code=str)


def test_reset_capital_preserves_positions_and_audit_jsonl(tmp_path: Path) -> None:
    state_root = tmp_path / "state"
    audit_root = tmp_path / "audit"
    portfolio = load_portfolio(state_root, "default", initial_capital=10000.0, max_positions=5)
    portfolio = add_position(portfolio, code="sh.600000")
    portfolio = reset_capital(portfolio, initial_capital=50000.0)
    save_portfolio(state_root, portfolio)
    append_audit_event(audit_root, "demo_capital_reset", {"portfolio_id": "default"})

    assert portfolio["positions"]
    event = json.loads((audit_root / "demo_portfolio_events.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert event["event_type"] == "demo_capital_reset"
    assert event["paper_only"] is True
    assert event["live_execution_enabled"] is False


def test_list_factors_only_returns_safe_txt_files(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("x", encoding="utf-8")
    (tmp_path / "b.json").write_text("x", encoding="utf-8")

    assert list_factors(tmp_path) == [{"filename": "a.txt", "size_bytes": 1}]
