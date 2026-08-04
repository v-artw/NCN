"""Edge Scout 数据准入测试。"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from ashare_edge_scout.admission import admission_universe, load_research_window_daily_bars


def test_load_research_window_daily_bars():
    """测试研究窗口日线加载。"""

    from ashare_edge_scout.daily_bars import DataValidationError

    # 模拟数据验证失败
    with patch("ashare_edge_scout.admission.load_local_daily_bars") as mock_loader:
        mock_loader.side_effect = DataValidationError("test_code", "test error")

        result = load_research_window_daily_bars("test_code", Path("test_root"))

        assert result.status == "rejected"
        assert result.formal_error_code == "test_code"


def test_admission_universe():
    """测试批量准入处理。"""

    from ashare_edge_scout.daily_bars import DataValidationError

    with patch("ashare_edge_scout.admission.load_local_daily_bars") as mock_loader:
        # 模拟成功和失败的情况
        def side_effect(code, **kwargs):
            if code == "good_code":
                return [{"date": "2026-07-24", "code": code, "open": 10.0, "high": 11.0,
                         "low": 9.0, "close": 10.5, "preclose": 10.0, "volume": 1000,
                         "amount": 10000, "turn": 1.0, "tradestatus": "1", "isST": "0"}]
            else:
                raise DataValidationError("bad_code", "bad error")

        mock_loader.side_effect = side_effect

        features, failures = admission_universe(
            ["good_code", "bad_code"],
            Path("test_root"),
        )

        assert "good_code" in features
        assert "bad_code" in failures


def test_admission_universe_reports_progress_for_success_and_failure():
    """Progress must advance even when a source record is rejected."""

    from ashare_edge_scout.daily_bars import DataValidationError

    events = []
    with patch("ashare_edge_scout.admission.load_local_daily_bars") as mock_loader:
        mock_loader.side_effect = [
            [{"date": "2026-07-24"}],
            DataValidationError("bad_code", "bad error"),
        ]
        admission_universe(
            ["good_code", "bad_code"],
            Path("test_root"),
            progress_callback=lambda processed, total, code: events.append(
                (processed, total, code)
            ),
        )

    assert events == [
        (1, 2, "good_code"),
        (2, 2, "bad_code"),
    ]
