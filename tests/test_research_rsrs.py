from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from ashare_edge_scout.research_rsrs import (
    CANDIDATE,
    _matched_parent_summary,
    _parent_failures,
    evaluate_rsrs_filter,
    rsrs_values,
)
from ashare_edge_scout.research_v2 import summarize_counts


def _rsrs_frame(length: int = 700) -> pd.DataFrame:
    low = 10.0 + np.arange(length) * 0.01 + np.sin(np.arange(length) / 7.0) * 0.2
    high = 1.25 * low + np.sin(np.arange(length) / 5.0) * 0.03
    return pd.DataFrame({"low": low, "high": high, "tradestatus": ["1"] * length})


def test_rsrs_requires_complete_18_and_600_windows() -> None:
    values = rsrs_values(_rsrs_frame())
    assert values["rsrs_slope"].iloc[:17].isna().all()
    assert values["rsrs_z"].iloc[:616].isna().all()
    assert values["rsrs_z"].iloc[616:].notna().all()
    assert values["rsrs_r2"].dropna().between(0.8, 1.0).all()


def test_suspension_does_not_enter_rsrs_timeline() -> None:
    base = _rsrs_frame()
    inserted = pd.concat((base.iloc[:350], pd.DataFrame({
        "low": [1.0], "high": [1000.0], "tradestatus": ["0"],
    }), base.iloc[350:]), ignore_index=True)
    original = rsrs_values(base)
    changed = rsrs_values(inserted)
    assert 350 not in changed.index
    assert np.allclose(
        original[["rsrs_slope", "rsrs_r2", "rsrs_z"]].to_numpy(),
        changed[["rsrs_slope", "rsrs_r2", "rsrs_z"]].to_numpy(),
        equal_nan=True,
    )


def test_future_changes_do_not_alter_past_rsrs() -> None:
    frame = _rsrs_frame(800)
    original = rsrs_values(frame)
    changed = frame.copy()
    changed.loc[750:, "high"] *= 2.0
    recalculated = rsrs_values(changed)
    assert np.allclose(
        original.loc[:749, ["rsrs_slope", "rsrs_r2", "rsrs_z"]].to_numpy(),
        recalculated.loc[:749, ["rsrs_slope", "rsrs_r2", "rsrs_z"]].to_numpy(),
        equal_nan=True,
    )


def test_parent_comparison_uses_only_dates_with_spaced_parent_observations() -> None:
    signal = pd.DataFrame({
        "date": pd.to_datetime(["2023-01-02", "2023-01-03"]),
        "label": pd.array([True, False], dtype="boolean"),
    })
    parent = pd.DataFrame({
        "date": pd.to_datetime(["2023-01-02", "2023-01-02"]),
        "label": pd.array([True, False], dtype="boolean"),
    })
    result = _matched_parent_summary(signal, parent)
    assert result["candidate_observations"] == 1
    assert result["weighted_n"] == 1
    assert result["precision"] == pytest.approx(0.5)
    assert result["combination_precision_delta"] == pytest.approx(0.5)


def _metric(n: int, precision: float, baseline: float, parent: float) -> dict:
    result = summarize_counts(n, round(n * precision))
    result.update({
        "signal_dates": 130,
        "codes": 60,
        "same_date_baseline": {"precision": baseline},
        "precision_lift": precision - baseline,
        "parent_mhpg": {
            "precision": parent,
            "combination_precision_delta": precision - parent,
        },
    })
    return result


def _gate_inputs() -> tuple[dict, dict]:
    primary = {
        "selection_2023_2024": _metric(400, 0.40, 0.30, 0.34),
        "audit_2025_2026": _metric(400, 0.40, 0.30, 0.34),
        "year_2023": _metric(200, 0.40, 0.30, 0.34),
        "year_2024": _metric(200, 0.40, 0.30, 0.34),
        "year_2025": _metric(200, 0.40, 0.30, 0.34),
        "year_2026": _metric(100, 0.40, 0.30, 0.34),
    }
    all_origin = {
        "selection_2023_2024": _metric(500, 0.40, 0.30, 0.34),
        "audit_2025_2026": _metric(500, 0.40, 0.30, 0.34),
    }
    return primary, all_origin


def test_gates_require_three_point_parent_lift_and_positive_annual_lifts() -> None:
    primary, all_origin = _gate_inputs()
    decision = evaluate_rsrs_filter(primary, all_origin)
    assert decision["accepted_for_prospective_observation"]

    primary["selection_2023_2024"]["parent_mhpg"]["combination_precision_delta"] = 0.029
    decision = evaluate_rsrs_filter(primary, all_origin)
    assert "parent_mhpg_lift_below_0.03" in decision["selection_failure_codes"]

    primary, all_origin = _gate_inputs()
    primary["year_2023"]["parent_mhpg"]["combination_precision_delta"] = 0.0
    assert "year_2023_parent_mhpg_lift_not_positive" in _parent_failures(
        primary, all_origin, audit=False
    )


def _load_cli_module():
    path = Path(__file__).parents[1] / "scripts" / "evaluate_rsrs_mhpg_filter.py"
    spec = importlib.util.spec_from_file_location("evaluate_rsrs_mhpg_filter", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("workers", [0, 9])
def test_cli_rejects_invalid_worker_limits(workers: int) -> None:
    with pytest.raises(SystemExit) as error:
        _load_cli_module().parse_args(["--output", "x", "--workers", str(workers)])
    assert error.value.code == 2


def test_cli_writer_atomically_preserves_result(tmp_path: Path) -> None:
    module = _load_cli_module()
    output = tmp_path / "result.json"
    module._atomic_json(output, {"candidate": CANDIDATE})
    assert json.loads(output.read_text(encoding="ascii"))["candidate"] == CANDIDATE
    assert list(tmp_path.iterdir()) == [output]
