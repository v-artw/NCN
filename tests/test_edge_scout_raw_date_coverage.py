from __future__ import annotations

from datetime import date

import pandas as pd

from ashare_edge_scout.data_sources import get_parquet_latest_date_coverage, get_parquet_latest_date_coverage_details


def test_raw_date_coverage_counts_files_before_strategy_admission(tmp_path) -> None:
    for code, values in {
        "sh.600000": ["2026-07-31", "2026-08-03"],
        "sh.600001": ["2026-08-03"],
        "sh.600002": ["2026-07-31"],
    }.items():
        pd.DataFrame({"date": pd.to_datetime(values)}).to_parquet(tmp_path / f"{code}.parquet", index=False)

    assert get_parquet_latest_date_coverage(tmp_path) == (date(2026, 8, 3), 2, 3)


def test_raw_date_coverage_reports_readable_and_skipped_counts(tmp_path) -> None:
    pd.DataFrame({"date": pd.to_datetime(["2026-08-03"])}).to_parquet(tmp_path / "sh.600000.parquet", index=False)
    pd.DataFrame({"date": pd.to_datetime(["2026-07-31"])}).to_parquet(tmp_path / "sh.600001.parquet", index=False)
    pd.DataFrame({"close": [1.0]}).to_parquet(tmp_path / "sh.600002.parquet", index=False)

    details = get_parquet_latest_date_coverage_details(
        tmp_path, ["sh.600000", "sh.600001", "sh.600002", "sh.600003"]
    )

    assert details.observed_latest_trade_date == date(2026, 8, 3)
    assert details.latest_file_count == 1
    assert details.expected_file_count == 4
    assert details.readable_file_count == 2
    assert details.skipped_file_count == 2
    assert details.observed_coverage_ratio == 0.25
    assert details.readable_latest_coverage_ratio == 0.5
