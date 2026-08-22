from __future__ import annotations

from pathlib import Path

from ashare_edge_scout.demo_portfolio_state import add_position, append_audit_event, load_portfolio
from ashare_edge_scout.paper_risk import normalize_paper_risk
from ashare_edge_scout.paper_trading_state import paper_history_payload, paper_status_payload


def test_paper_status_has_simulation_boundaries(tmp_path: Path) -> None:
    portfolio = load_portfolio(tmp_path / "demo", "default", initial_capital=20000.0, max_positions=5)
    portfolio = add_position(portfolio, code="sh.600000", state="PAPER_HOLD")

    payload = paper_status_payload(
        portfolio=portfolio,
        paper_state_root=tmp_path / "paper",
        audit_root=tmp_path / "audit",
        risk_controls=normalize_paper_risk({"max_position_pct": 0.1}),
        freshness_warnings=["research_data_only"],
    )

    assert payload["schema_version"] == "ncn_paper_status_v1"
    assert payload["paper_only"] is True
    assert payload["live_execution_enabled"] is False
    assert payload["allow_live_order_submission"] is False
    assert payload["broker_connection"] == "none"
    assert payload["simulated_positions"][0]["state"] == "PAPER_HOLD"
    assert "no_broker_connection" in payload["limitations"]


def test_paper_history_reads_ncn_audit_jsonl(tmp_path: Path) -> None:
    append_audit_event(tmp_path, "demo_position_added", {"portfolio_id": "default", "code": "sh.600000"})

    payload = paper_history_payload(audit_root=tmp_path, portfolio_id="default")

    assert payload["source"] == "ncn_demo_portfolio_audit_jsonl"
    assert payload["events"][0]["event_type"] == "demo_position_added"
    assert payload["live_execution_enabled"] is False
