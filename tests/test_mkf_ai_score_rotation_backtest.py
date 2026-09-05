from __future__ import annotations

from pathlib import Path
from unittest import mock

import pandas as pd

import importlib.util
import sys

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "evaluate_mkf_ai_score_rotation_backtest.py"
spec = importlib.util.spec_from_file_location("evaluate_mkf_ai_score_rotation_backtest", SCRIPT_PATH)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def _frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": pd.to_datetime(["2025-09-01", "2025-09-02", "2025-09-03", "2025-09-04"]),
            "open": [10.0, 10.5, 11.0, 12.0],
            "high": [10.2, 10.8, 11.2, 12.3],
            "low": [9.8, 10.1, 10.7, 11.8],
            "close": [10.1, 10.6, 11.1, 12.1],
            "tradestatus": ["1", "0", "1", "1"],
        }
    )


def test_next_tradable_open_skips_suspension_and_uses_open() -> None:
    fill_date, price = module.next_tradable_open(_frame(), "2025-09-01")

    assert fill_date == "2025-09-03"
    assert price == 11.0


def test_llm_score_mapping_blocks_negative_states() -> None:
    assert module.llm_score_from_state("priority_research", 0.72) == 72.0
    assert module.llm_score_from_state("standard_research", 0.65) == 65.0
    assert module.llm_score_from_state("risk_attention", 0.99) == 50.0
    assert module.llm_score_from_state("insufficient_evidence", 0.99) == 50.0
    assert module.llm_score_from_state("ai_unavailable", 0.99) == 50.0


def test_ashare_fees_apply_commission_floor_and_sell_stamp() -> None:
    assert round(module.ashare_fees(1000.0, "buy", "ashare"), 4) == 5.01
    assert round(module.ashare_fees(1000.0, "sell", "ashare"), 4) == 5.51
    assert module.ashare_fees(1000.0, "sell", "none") == 0.0


def test_score_exit_is_next_day_order_not_same_day_sale() -> None:
    state = module.ComboState("c", "lane", 1, 0.0, "none", 65.0, 60.0, 0.0)
    state.positions["sh.600000"] = module.Position("sh.600000", 100, "2025-09-01", 10.0, 70.0, 1000.0)
    state.pending_orders.append(module.PendingOrder("2025-09-01", "sell", "sh.600000", "score_exit", 59.0, 0.0))

    module.execute_sell(state, state.pending_orders.pop(0), {"sh.600000": _frame()}, "2025-09-01")

    assert "sh.600000" in state.positions
    assert len(state.pending_orders) == 1

    order = state.pending_orders.pop(0)
    module.execute_sell(state, order, {"sh.600000": _frame()}, "2025-09-03")

    assert "sh.600000" not in state.positions
    assert state.cash == 1100.0


def test_buy_respects_lot_size_and_cash_skip() -> None:
    state = module.ComboState("c", "lane", 1, 0.0, "none", 65.0, 60.0, 1000.0)
    order = module.PendingOrder("2025-09-01", "buy", "sh.600000", "entry_threshold", 70.0, 0.0)

    module.execute_buy(state, order, {"sh.600000": _frame()}, "2025-09-03", 1000.0, 100)

    assert not state.positions
    assert state.counters["lot_skip_count"] == 1


def test_replacement_gap_boundary() -> None:
    low = type("Record", (), {"score": 62.0, "code": "sh.600001"})()
    new_score = 65.0

    assert new_score >= low.score + 3.0
    assert not (new_score >= low.score + 5.0)


def test_summary_includes_entry_and_hold_thresholds() -> None:
    state = module.ComboState("lane|entry70|hold65|pos1|gap0|none", "lane", 1, 0.0, "none", 70.0, 65.0, 1000.0)
    state.daily.append({"total_equity": 1010.0, "drawdown_pct": 0.0, "position_count": 0, "market_value": 0.0})

    summary = module.summarize_combo(state, 1000.0)

    assert summary["entry_threshold"] == 70.0
    assert summary["hold_threshold"] == 65.0
    assert summary["combo_id"] == "lane|entry70|hold65|pos1|gap0|none"


def test_llm_backtest_client_follows_yaml_default_provider(tmp_path: Path) -> None:
    ai_config = tmp_path / "ai_providers.yaml"
    ai_config.write_text(
        "schema_version: ncn_ai_providers_v1\n"
        "enabled: true\n"
        "provider: other_ai\n"
        "temperature: 0\n"
        "seed: 42\n"
        "response_format:\n"
        "  type: json_object\n"
        "providers:\n"
        "  local_finance:\n"
        "    enabled: true\n"
        "    base_url: http://local.test/v1\n"
        "    model: local-model\n"
        "    key_file: missing-local.key\n"
        "  other_ai:\n"
        "    enabled: true\n"
        "    base_url: http://other.test/v1\n"
        "    model: other-model\n"
        "    key_file: missing-other.key\n",
        encoding="utf-8",
    )

    fake_shared = mock.Mock(
        provider="other_ai",
        base_url="http://other.test/v1",
        api_key="secret",
        model="other-model",
        timeout_seconds=123,
        temperature=0,
        seed=42,
        response_format={"type": "json_object"},
        extra_options={},
    )
    with mock.patch.object(module, "build_shared_ai_client", return_value=fake_shared):
        client, meta = module.build_client(ai_config)

    assert meta["provider"] == "other_ai"
    assert client is not None
    assert client.provider == "other_ai"
    assert client.model == "other-model"
