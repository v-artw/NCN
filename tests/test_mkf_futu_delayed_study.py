from __future__ import annotations

import pandas as pd
import pytest

from ashare_edge_scout.pmkf_mkf.mkf_futu_delayed_study import (
    aggregate_delayed_metrics,
    build_delayed_report,
    build_delayed_stock_panels,
    evaluate_delayed_decisions,
)
from ashare_edge_scout.pmkf_mkf.mkf_futu_overlay_study import OVERLAYS


def _frame(rows: int = 20) -> pd.DataFrame:
    close = [100.0 + index for index in range(rows)]
    return pd.DataFrame({
        "date": pd.bdate_range("2025-01-01", periods=rows),
        "open": [90.0 + index for index in range(rows)],
        "high": [value + 1.0 for value in close],
        "low": [value - 1.0 for value in close],
        "close": close,
        "preclose": [close[0], *close[:-1]],
        "volume": [1_000_000.0] * rows,
        "amount": [200_000_000.0] * rows,
        "tradestatus": ["1"] * rows,
        "isST": ["0"] * rows,
    })


def _config() -> dict:
    return {"universe": {
        "include_prefixes": ["sh.600"], "exclude_st": True,
        "min_listing_days": 1, "min_close_cny": 1.0, "max_close_cny": 200.0,
        "min_adv20_cny": 0.0, "min_trading_days_60": 1,
        "block_limit_up_entries": False, "block_suspensions": True,
    }}


def _patch(monkeypatch, frame: pd.DataFrame, origins: list[int], triggers: dict[str, list[int]]) -> None:
    parent = pd.DataFrame({"code": ["sh.600001"] * len(origins), "mkf_date": frame.loc[origins, "date"].tolist()})
    monkeypatch.setattr(
        "ashare_edge_scout.pmkf_mkf.mkf_futu_delayed_study.build_mkf_next_open_panel",
        lambda *args, **kwargs: parent,
    )
    parent_mask = pd.Series(False, index=frame.index)
    parent_mask.loc[origins] = True
    monkeypatch.setattr(
        "ashare_edge_scout.pmkf_mkf.mkf_futu_delayed_study.production_gate_mask",
        lambda code, data, config: pd.Series(True, index=data.index),
    )
    monkeypatch.setattr(
        "ashare_edge_scout.pmkf_mkf.mkf_futu_delayed_study.mkf_red_blue_cross20_green_exit_under80_mask",
        lambda data: parent_mask.reindex(data.index, fill_value=False),
    )
    values = pd.DataFrame(index=frame.index)
    monkeypatch.setattr(
        "ashare_edge_scout.pmkf_mkf.mkf_futu_delayed_study.tradable_indicator_values",
        lambda data: values.loc[data.index[data["tradestatus"].astype(str).eq("1")]],
    )
    def masks(values_frame):
        result = {name: pd.Series(False, index=values_frame.index) for name in OVERLAYS}
        for name, indexes in triggers.items():
            for index in indexes:
                if index in result[name].index:
                    result[name].loc[index] = True
        return result
    monkeypatch.setattr(
        "ashare_edge_scout.pmkf_mkf.mkf_futu_delayed_study.candidate_masks_from_values", masks,
    )


def test_lag_zero_excluded_and_lag_one_selected(monkeypatch) -> None:
    frame = _frame()
    _patch(monkeypatch, frame, [0], {name: [0, 1] for name in OVERLAYS})

    _, panels, _ = build_delayed_stock_panels("sh.600001", frame, _config())

    for panel in panels.values():
        assert len(panel) == 1
        assert panel.loc[0, "confirmation_lag"] == 1
        assert panel.loc[0, "entry_date"] == frame.loc[2, "date"]
        assert panel.loc[0, "date_t1"] == frame.loc[3, "date"]
        assert panel.loc[0, "ret_t1_close"] == pytest.approx(frame.loc[3, "close"] / frame.loc[2, "open"] - 1.0)


def test_lag_five_matches_but_lag_six_does_not(monkeypatch) -> None:
    frame = _frame()
    triggers = {name: [5] for name in OVERLAYS}
    triggers["mhpg_buy"] = [6]
    _patch(monkeypatch, frame, [0], triggers)

    _, panels, _ = build_delayed_stock_panels("sh.600001", frame, _config())

    assert panels["kdj_trend_pro_buy"].loc[0, "confirmation_lag"] == 5
    assert panels["mhpg_buy"].empty


def test_suspension_does_not_consume_lag(monkeypatch) -> None:
    frame = _frame()
    frame.loc[1, "tradestatus"] = "0"
    _patch(monkeypatch, frame, [0], {name: [6] for name in OVERLAYS})

    _, panels, _ = build_delayed_stock_panels("sh.600001", frame, _config())

    for panel in panels.values():
        assert panel.loc[0, "confirmation_lag"] == 5


def test_overlapping_origins_deduplicate_per_candidate(monkeypatch) -> None:
    frame = _frame()
    _patch(monkeypatch, frame, [0, 1], {name: [2] for name in OVERLAYS})

    _, panels, diagnostics = build_delayed_stock_panels("sh.600001", frame, _config())

    for name in OVERLAYS:
        assert len(panels[name]) == 1
        assert diagnostics[name]["duplicate_entry"] == 1


def _decision_frames() -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    parent_rows = []
    candidate_rows = {name: [] for name in OVERLAYS}
    for year in range(2021, 2027):
        for index in range(100):
            row = {"code": f"c{year}{index:03d}", "entry_date": pd.Timestamp(year, 1, 3)}
            for horizon in range(1, 11):
                row[f"ret_t{horizon}_close"] = 0.01 if index < 50 else -0.01
            parent_rows.append(row)
            if index < 20:
                candidate = dict(row)
                for horizon in range(1, 11):
                    candidate[f"ret_t{horizon}_close"] = 0.01 if index < 8 else -0.01
                candidate_rows[OVERLAYS[index % len(OVERLAYS)]].append(candidate)
    columns = list(parent_rows[0])
    return pd.DataFrame(parent_rows), {
        name: pd.DataFrame(candidate_rows[name], columns=columns) for name in OVERLAYS
    }


def test_decision_stops_failed_delayed_direction() -> None:
    parent, candidates = _decision_frames()
    aggregated = aggregate_delayed_metrics(parent, candidates)
    decision = evaluate_delayed_decisions(aggregated)

    assert decision["accepted_candidates"] == []
    assert decision["stop_direction"] is True


def test_report_metadata_excludes_lag_zero() -> None:
    parent, candidates = _decision_frames()
    report = build_delayed_report(
        parent=parent, candidates=candidates,
        diagnostics={name: {} for name in OVERLAYS},
        code_list=["sh.600001"], code_list_sha256="abc",
        start_date="2021-01-01", end_date=None, workers=1,
    )

    assert report["research_only"] is True
    assert report["original_mkf_v3_modified"] is False
    assert "lag 1..5" in report["candidate_definitions"]["window"]
    assert "lag0 excluded" in report["candidate_definitions"]["window"]
