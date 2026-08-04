from __future__ import annotations

from datetime import date
import importlib.util
from pathlib import Path
import sys


SCRIPT = Path(__file__).parents[1] / "scripts/generate_baostock_calendar_candidate.py"
SPEC = importlib.util.spec_from_file_location("edge_scout_calendar_candidate_test", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = module
SPEC.loader.exec_module(module)


def test_query_trading_days_normalizes_baostock_response(monkeypatch) -> None:
    class Login:
        error_code = "0"
        error_msg = ""

    class Result:
        error_code = "0"
        error_msg = ""
        fields = ["calendar_date", "is_trading_day"]

        def __init__(self) -> None:
            self.rows = iter([
                ["2026-01-02", "0"],
                ["2026-01-05", "1"],
                ["2026-01-06", "1"],
            ])

        def next(self) -> bool:
            try:
                self.current = next(self.rows)
                return True
            except StopIteration:
                return False

        def get_row_data(self) -> list[str]:
            return self.current

    monkeypatch.setattr(module.bs, "login", lambda: Login())
    monkeypatch.setattr(module.bs, "logout", lambda: None)
    monkeypatch.setattr(module.bs, "query_trade_dates", lambda **_: Result())

    assert module.query_trading_days(date(2026, 1, 1), date(2026, 12, 31)) == [
        date(2026, 1, 5),
        date(2026, 1, 6),
    ]
