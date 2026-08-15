from __future__ import annotations

from scripts.evaluate_joint_strategy import select_strategy, wilson_lower


def _period(n: int, rate: float) -> dict[str, float | int]:
    hits = round(n * rate)
    return {
        "n": n,
        "hit_rate": hits / n,
        "wilson_lower_95": wilson_lower(hits, n),
    }


def test_wilson_lower_penalizes_tiny_samples():
    assert wilson_lower(8, 10) < wilson_lower(800, 1000)
    assert wilson_lower(0, 0) is None


def test_strategy_selection_uses_validation_only_and_enforces_coverage():
    summaries = {
        "admitted_baseline": {
            "calibration": _period(10000, 0.30),
            "validation": _period(10000, 0.30),
            "2023": _period(5000, 0.30),
            "2024": _period(5000, 0.30),
        },
        "tiny_apparent_winner": {
            "calibration": _period(1000, 0.80),
            "validation": _period(20, 0.95),
            "2023": _period(10, 0.90),
            "2024": _period(10, 1.00),
            "holdout": _period(1000, 0.99),
        },
        "stable": {
            "calibration": _period(1000, 0.40),
            "validation": _period(1000, 0.60),
            "2023": _period(500, 0.60),
            "2024": _period(500, 0.60),
            "holdout": _period(1000, 0.10),
        },
        "lower_bound_loser": {
            "calibration": _period(1000, 0.40),
            "validation": _period(1000, 0.55),
            "2023": _period(500, 0.55),
            "2024": _period(500, 0.55),
            "holdout": _period(1000, 0.95),
        },
    }

    selected, ranking = select_strategy(summaries, min_validation=800, min_year=250)

    assert selected == "stable"
    assert ranking[0]["strategy"] == "stable"
    assert not next(item for item in ranking if item["strategy"] == "tiny_apparent_winner")["eligible"]


def test_strategy_selection_rejects_yearly_regime_dependence():
    summaries = {
        "admitted_baseline": {
            "calibration": _period(10000, 0.30),
            "validation": _period(10000, 0.30),
            "2023": _period(5000, 0.30),
            "2024": _period(5000, 0.30),
        },
        "one_year_only": {
            "calibration": _period(1000, 0.35),
            "validation": _period(1000, 0.50),
            "2023": _period(500, 0.29),
            "2024": _period(500, 0.71),
        },
        "stable": {
            "calibration": _period(1000, 0.35),
            "validation": _period(1000, 0.40),
            "2023": _period(500, 0.39),
            "2024": _period(500, 0.41),
        },
    }

    selected, ranking = select_strategy(summaries, min_validation=800, min_year=250)

    assert selected == "stable"
    rejected = next(item for item in ranking if item["strategy"] == "one_year_only")
    assert not rejected["eligible"]
    assert rejected["minimum_validation_year_lift"] < 0
