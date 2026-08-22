from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd
import pytest

from ashare_edge_scout.research_futu_combination import (
    COMBINATION, PARENT, aggregate_combination_metrics, attach_combination, evaluate_combination,
)
from ashare_edge_scout.research_v2 import summarize_counts


def test_combination_requires_prior_long_state_and_current_kdj_trigger() -> None:
    panel = pd.DataFrame({
        "code": ["a"] * 4 + ["b"] * 2,
        "shengbei_state": [-1.0, 1.0, 1.0, -1.0, 1.0, 1.0],
        PARENT: [False, True, True, True, True, True],
    })
    result = attach_combination(panel)
    assert result[COMBINATION].tolist() == [False, False, True, True, False, True]


def _panel() -> pd.DataFrame:
    rows = []
    for date, combo_codes, parent_codes in (
        (pd.Timestamp("2023-01-02"), {0}, {0, 1, 2, 3}),
        (pd.Timestamp("2023-01-03"), {0, 1, 2}, {0, 1, 2, 3}),
    ):
        for number in range(150):
            rows.append({
                "date": date,
                "code": f"c{number:03d}",
                "trading_index": date.day * 10,
                "admitted": True,
                "label": number in ({0, 1} if date.day == 2 else {0, 3}),
                COMBINATION: number in combo_codes,
                PARENT: number in parent_codes,
            })
    return pd.DataFrame(rows)


def test_metrics_weight_market_and_parent_by_combination_count() -> None:
    primary, all_origin = aggregate_combination_metrics(_panel())
    metric = primary["year_2023"]
    assert metric["n"] == 4
    assert metric["precision"] == pytest.approx(0.5)
    assert metric["parent_kdj"]["precision"] == pytest.approx((1 * 0.5 + 3 * 0.5) / 4)
    assert metric["parent_kdj"]["weighted_n"] == 4
    assert all_origin["year_2023"]["n"] == 4


def _metric(n: int, precision: float, baseline: float, parent: float, *, dates: int = 130, codes: int = 60) -> dict:
    result = summarize_counts(n, round(n * precision))
    result.update({
        "signal_dates": dates,
        "codes": codes,
        "same_date_baseline": {"precision": baseline},
        "precision_lift": precision - baseline,
        "parent_kdj": {"precision": parent, "combination_precision_delta": precision - parent},
    })
    return result


def test_decision_requires_one_point_over_parent_in_both_periods() -> None:
    primary = {
        "selection_2023_2024": _metric(400, 0.40, 0.30, 0.38),
        "audit_2025_2026": _metric(400, 0.40, 0.30, 0.38),
        "year_2023": _metric(200, 0.40, 0.30, 0.38),
        "year_2024": _metric(200, 0.40, 0.30, 0.38),
        "year_2025": _metric(200, 0.40, 0.30, 0.38),
        "year_2026": _metric(100, 0.40, 0.30, 0.38),
    }
    all_origin = {
        "selection_2023_2024": _metric(500, 0.40, 0.30, 0.38),
        "audit_2025_2026": _metric(500, 0.40, 0.30, 0.38),
    }
    assert evaluate_combination(primary, all_origin)["accepted_for_prospective_observation"]
    primary["audit_2025_2026"]["parent_kdj"]["combination_precision_delta"] = 0.009
    decision = evaluate_combination(primary, all_origin)
    assert not decision["audit_accepted"]
    assert "parent_kdj_lift_below_0.01" in decision["audit_failure_codes"]


def _load_cli_module():
    path = Path(__file__).parents[1] / "scripts" / "evaluate_shengbei_kdj_combination.py"
    spec = importlib.util.spec_from_file_location("evaluate_shengbei_kdj_combination", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_cli_enforces_worker_cap() -> None:
    module = _load_cli_module()
    assert module.parse_args(["--output", "x", "--workers", "8"]).workers == 8
    with pytest.raises(SystemExit):
        module.parse_args(["--output", "x", "--workers", "9"])
