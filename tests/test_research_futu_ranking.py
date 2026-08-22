from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from ashare_edge_scout.research_futu_ranking import (
    CANDIDATES,
    _shengbei_state,
    aggregate_futu_metrics,
    candidate_masks_from_values,
    evaluate_futu_ranking,
    indicator_masks,
)
from ashare_edge_scout.research_v2 import summarize_counts


def _trigger_values() -> pd.DataFrame:
    columns = {
        "dxbd": [-1.0, 1.0], "ribbon": [9.0, 11.0], "ribbon_signal": [10.0, 10.0],
        "ema20": [11.0, 11.0], "ema60": [9.0, 10.0], "mhpg_k": [10.0, 20.0], "mhpg_d": [11.0, 19.0],
        "kdj_k": [10.0, 20.0], "kdj_d": [11.0, 19.0], "close": [11.0, 12.0],
        "prior_high30": [np.nan, 11.5], "prior_close": [np.nan, 11.0], "body_ratio": [0.8, 0.8],
        "mkf_momentum": [20.0, 21.0], "mkf_inter": [19.0, 21.0], "mkf_near": [18.0, 21.0],
        "shengbei_state": [-1.0, 1.0], "gding_fast": [9.0, 11.0], "gding_signal": [10.0, 10.0],
        "cpgw_main": [9.0, 11.0], "cpgw_long": [10.0, 10.0],
    }
    return pd.DataFrame(columns)


@pytest.mark.parametrize("candidate", CANDIDATES)
def test_each_frozen_formula_trigger(candidate: str) -> None:
    masks = candidate_masks_from_values(_trigger_values())
    assert not masks[candidate].iat[0]
    assert masks[candidate].iat[1]


def test_crosses_are_strict_and_invalid_ranges_cannot_trigger() -> None:
    values = _trigger_values()
    values.loc[1, "dxbd"] = 0.0
    values.loc[1, "ribbon_signal"] = 30.0
    values.loc[1, "body_ratio"] = 0.70
    values.loc[1, "cpgw_long"] = 50.0
    masks = candidate_masks_from_values(values)
    assert not masks["dxbd_cross_zero"].iat[1]
    assert not masks["ribbon1_strict_buy"].iat[1]
    assert not masks["smc_strong_buy"].iat[1]
    assert not masks["cpgw_main_long_cross"].iat[1]

    frame = pd.DataFrame({
        "open": [10.0] * 80, "high": [10.0] * 80, "low": [10.0] * 80,
        "close": [10.0] * 80, "tradestatus": ["1"] * 80,
    })
    assert not any(mask.any() for mask in indicator_masks(frame).values())


def test_shengbei_initializes_short_carries_neutral_and_flips_long() -> None:
    close = pd.Series([10.0] * 22 + [20.0, 20.0])
    high = close + 1.0
    low = close - 1.0
    state = _shengbei_state(close, high, low)
    assert state.iat[21] == -1.0
    assert state.iat[22] == 1.0
    assert state.iat[23] == 1.0


def test_suspension_rows_do_not_enter_formula_timeline_or_signal() -> None:
    base = pd.DataFrame({
        "open": np.linspace(10, 20, 90), "high": np.linspace(10.5, 20.5, 90),
        "low": np.linspace(9.5, 19.5, 90), "close": np.linspace(10, 20, 90),
        "tradestatus": ["1"] * 90,
    })
    inserted = pd.concat((base.iloc[:45], pd.DataFrame({
        "open": [999.0], "high": [1000.0], "low": [998.0], "close": [999.0], "tradestatus": ["0"],
    }), base.iloc[45:]), ignore_index=True)
    original = indicator_masks(base)
    changed = indicator_masks(inserted)
    for name in CANDIDATES:
        assert not changed[name].iat[45]
        assert changed[name].drop(index=45).reset_index(drop=True).equals(original[name])


def test_future_bar_changes_do_not_alter_past_indicator_triggers() -> None:
    close = 10.0 + np.sin(np.arange(120) / 4.0) + np.arange(120) * 0.02
    frame = pd.DataFrame({
        "open": close - 0.1, "high": close + 0.4, "low": close - 0.4,
        "close": close, "tradestatus": ["1"] * 120,
    })
    original = indicator_masks(frame)
    changed = frame.copy()
    changed.loc[100:, ["open", "high", "low", "close"]] *= 5.0
    recalculated = indicator_masks(changed)
    for name in CANDIDATES:
        assert recalculated[name].iloc[:100].equals(original[name].iloc[:100])


def _panel_for_baseline() -> pd.DataFrame:
    rows = []
    for date, baseline_hits, signal_codes in (
        (pd.Timestamp("2023-01-02"), 100, (0,)),
        (pd.Timestamp("2023-01-03"), 50, (0, 1, 2)),
        (pd.Timestamp("2023-01-04"), 149, (0,)),
    ):
        for number in range(150):
            row = {
                "date": date, "code": f"c{number:03d}", "trading_index": int(date.day) * 10,
                "admitted": True, "label": number < baseline_hits,
            }
            row.update({name: number in signal_codes if name == CANDIDATES[0] else False for name in CANDIDATES})
            rows.append(row)
    panel = pd.DataFrame(rows)
    panel["label"] = pd.array(panel["label"], dtype="boolean")
    panel.loc[(panel["date"] == pd.Timestamp("2023-01-04")) & (panel["code"] == "c149"), "label"] = pd.NA
    return panel


def test_matched_baseline_is_signal_count_weighted_and_requires_150_mature_rows() -> None:
    primary, all_origin, coverage = aggregate_futu_metrics(_panel_for_baseline())
    metric = primary[CANDIDATES[0]]["year_2023"]
    expected = ((1 * 100 / 150) + (3 * 50 / 150)) / 4
    assert metric["same_date_baseline"]["precision"] == pytest.approx(expected)
    assert metric["same_date_baseline"]["weighted_n"] == 4
    assert metric["n"] == 4
    assert coverage[CANDIDATES[0]]["year_2023"]["raw_triggers"] == 5
    assert all_origin[CANDIDATES[0]]["year_2023"]["n"] == 4


def test_primary_observations_are_nonoverlapping_but_all_origin_is_not() -> None:
    panel = _panel_for_baseline()
    panel.loc[panel["code"].eq("c000"), "trading_index"] = [10, 14, 15]
    primary, all_origin, _ = aggregate_futu_metrics(panel)
    assert primary[CANDIDATES[0]]["year_2023"]["n"] == 3
    assert all_origin[CANDIDATES[0]]["year_2023"]["n"] == 4


def _metric(n: int, precision: float, baseline: float, *, dates: int = 130, codes: int = 60) -> dict:
    result = summarize_counts(n, round(n * precision))
    result.update({
        "signal_dates": dates, "codes": codes,
        "same_date_baseline": {"precision": baseline},
        "precision_lift": precision - baseline,
    })
    return result


def _ranking_inputs() -> tuple[dict, dict]:
    primary = {}
    all_origin = {}
    for offset, name in enumerate(CANDIDATES):
        precision = 0.40 - offset * 0.001
        primary[name] = {
            "selection_2023_2024": _metric(400, precision, 0.30),
            "audit_2025_2026": _metric(400, precision, 0.30),
            "year_2023": _metric(200, precision, 0.30), "year_2024": _metric(200, precision, 0.30),
            "year_2025": _metric(200, precision, 0.30), "year_2026": _metric(100, precision, 0.30),
        }
        all_origin[name] = {
            "selection_2023_2024": _metric(500, precision, 0.30),
            "audit_2025_2026": _metric(500, precision, 0.30),
        }
    return primary, all_origin


def test_gates_ranking_and_failed_top_audit_do_not_promote_runner_up() -> None:
    primary, all_origin = _ranking_inputs()
    decision = evaluate_futu_ranking(primary, all_origin)
    assert decision["ranking"] == list(CANDIDATES)
    assert decision["accepted_winner"] == CANDIDATES[0]

    primary[CANDIDATES[0]]["year_2026"] = _metric(24, 0.40, 0.30)
    decision = evaluate_futu_ranking(primary, all_origin)
    assert decision["top_ranked"] == CANDIDATES[0]
    assert decision["accepted_winner"] is None
    assert "year_2026_n_below_25" in decision["candidates"][CANDIDATES[0]]["audit_failure_codes"]

    primary[CANDIDATES[1]]["selection_2023_2024"] = _metric(299, 0.60, 0.30)
    decision = evaluate_futu_ranking(primary, all_origin)
    assert decision["ranking"].index(CANDIDATES[1]) > decision["ranking"].index(CANDIDATES[-1])


def _load_cli_module():
    path = Path(__file__).parents[1] / "scripts" / "evaluate_futu_indicator_ranking.py"
    spec = importlib.util.spec_from_file_location("evaluate_futu_indicator_ranking", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("arguments", [["--output", "x", "--max-codes", "399"], ["--output", "x", "--workers", "0"], ["--output", "x", "--workers", "9"]])
def test_cli_rejects_nonfixed_sample_and_worker_limits(arguments: list[str]) -> None:
    with pytest.raises(SystemExit) as error:
        _load_cli_module().parse_args(arguments)
    assert error.value.code == 2


def test_cli_accepts_exact_sample_and_worker_cap() -> None:
    module = _load_cli_module()
    args = module.parse_args(["--output", "x", "--max-codes", "400", "--workers", "8"])
    assert (args.max_codes, args.workers) == (400, 8)


def test_cli_accepts_frozen_all_main_board_mode() -> None:
    module = _load_cli_module()
    args = module.parse_args(["--output", "x", "--universe", "all-main-board", "--workers", "8"])
    assert args.universe == "all-main-board"
    assert args.max_codes == 400


def test_cli_json_writer_atomically_publishes_valid_json(tmp_path: Path) -> None:
    module = _load_cli_module()
    output = tmp_path / "result.json"
    module._atomic_json(output, {"candidates": list(CANDIDATES)})
    assert json.loads(output.read_text(encoding="ascii"))["candidates"] == list(CANDIDATES)
    assert list(tmp_path.iterdir()) == [output]
