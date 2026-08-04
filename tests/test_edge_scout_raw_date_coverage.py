from __future__ import annotations

from datetime import date

import pandas as pd

from ashare_edge_scout.data_sources import get_parquet_latest_date_coverage


def test_raw_date_coverage_counts_files_before_strategy_admission(tmp_path) -> None:
    for code, values in {
        "sh.600000": ["2026-07-31", "2026-08-03"],
        "sh.600001": ["2026-08-03"],
        "sh.600002": ["2026-07-31"],
    }.items():
        pd.DataFrame({"date": pd.to_datetime(values)}).to_parquet(tmp_path / f"{code}.parquet", index=False)

    assert get_parquet_latest_date_coverage(tmp_path) == (date(2026, 8, 3), 2, 3)
