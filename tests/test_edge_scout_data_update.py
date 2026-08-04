from __future__ import annotations

from datetime import date
import importlib.util
from pathlib import Path
import sys

import pandas as pd
import pytest


SCRIPT = Path(__file__).parents[1] / "scripts/check_edge_scout_data_update.py"
SPEC = importlib.util.spec_from_file_location("edge_scout_data_update_test", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = module
SPEC.loader.exec_module(module)


def test_latest_local_date_reads_parquet_maximum(tmp_path: Path) -> None:
    pd.DataFrame({"date": pd.to_datetime(["2026-07-30", "2026-07-31"])}).to_parquet(
        tmp_path / "sh.600000.parquet", index=False
    )
    pd.DataFrame({"date": pd.to_datetime(["2026-08-01"])}).to_parquet(
        tmp_path / "broken-name.parquet", index=False
    )

    assert module.local_date_state(tmp_path) == (date(2026, 8, 1), 1, 2)


def test_update_decision_skips_equal_and_requires_newer_remote() -> None:
    assert module.update_decision(date(2026, 7, 31), date(2026, 7, 31)) == "current"
    assert module.update_decision(date(2026, 7, 30), date(2026, 7, 31)) == "update_required"
    assert module.update_decision(None, date(2026, 7, 31)) == "update_required"
    assert module.update_decision(
        date(2026, 7, 31),
        date(2026, 7, 31),
        latest_coverage_ratio=0.94,
    ) == "update_required"
    with pytest.raises(RuntimeError, match="local data is newer"):
        module.update_decision(date(2026, 8, 1), date(2026, 7, 31))


def test_latest_remote_trade_date_uses_baostock_calendar(monkeypatch: pytest.MonkeyPatch) -> None:
    class Login:
        error_code = "0"
        error_msg = ""

    class Result:
        error_code = "0"
        error_msg = ""
        fields = ["calendar_date", "is_trading_day"]

        def __init__(self) -> None:
            self.rows = iter([
                ["2026-07-31", "1"],
                ["2026-08-01", "0"],
                ["2026-08-03", "1"],
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

    assert module.latest_remote_trade_date(today=date(2026, 8, 3)) == date(2026, 8, 3)
