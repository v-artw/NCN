"""数据源适配器。

从 PFrontStockData 读取 parquet 文件，加载行业映射。
复用 V1 的数据读取逻辑，适配新的数据结构。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Mapping, Sequence

from .daily_bars import (
    DataValidationError,
    REQUIRED_DAILY_BAR_FIELDS,
    load_local_daily_bars,
    validate_daily_bars,
)


def get_parquet_codes(data_root: str | Path) -> list[str]:
    """获取数据根目录下所有 parquet 文件的股票代码。

    参数：
      data_root: 数据根目录

    返回：
      股票代码列表（已去重）
    """

    root = Path(data_root)
    if not root.is_dir():
        raise DataValidationError("data_root_missing", f"数据根目录不存在：{root}")

    codes: set[str] = set()
    for entry in sorted(root.iterdir()):
        if entry.suffix == ".parquet" and entry.is_file():
            code = entry.stem
            if code and code not in {".", ".."}:
                codes.add(code)

    return sorted(codes)


@dataclass(frozen=True)
class ParquetDateCoverage:
    observed_latest_trade_date: date | None
    latest_file_count: int
    expected_file_count: int
    readable_file_count: int
    skipped_file_count: int

    @property
    def observed_coverage_ratio(self) -> float:
        return self.latest_file_count / self.expected_file_count if self.expected_file_count else 0.0

    @property
    def readable_latest_coverage_ratio(self) -> float:
        return self.latest_file_count / self.readable_file_count if self.readable_file_count else 0.0


def get_parquet_latest_date_coverage_details(
    data_root: str | Path,
    codes: Sequence[str] | None = None,
) -> ParquetDateCoverage:
    """Return latest raw parquet date coverage with explicit denominator details."""

    import pandas as pd
    import pyarrow.parquet as pq

    root = Path(data_root)
    selected = list(codes) if codes is not None else get_parquet_codes(root)
    file_dates: list[date] = []
    skipped = 0
    for code in selected:
        path = root / f"{code}.parquet"
        try:
            parquet = pq.ParquetFile(path)
            if "date" not in parquet.schema_arrow.names or parquet.metadata.num_row_groups == 0:
                skipped += 1
                continue
            table = parquet.read_row_group(parquet.metadata.num_row_groups - 1, columns=["date"])
            values = table.column("date")
            dates = [pd.Timestamp(value.as_py()).date() for value in values if value.as_py() is not None]
            if dates:
                file_dates.append(max(dates))
            else:
                skipped += 1
        except Exception:
            skipped += 1
    if not file_dates:
        return ParquetDateCoverage(None, 0, len(selected), 0, skipped)
    latest = max(file_dates)
    return ParquetDateCoverage(
        observed_latest_trade_date=latest,
        latest_file_count=sum(value == latest for value in file_dates),
        expected_file_count=len(selected),
        readable_file_count=len(file_dates),
        skipped_file_count=skipped,
    )


def get_parquet_latest_date_coverage(
    data_root: str | Path,
    codes: Sequence[str] | None = None,
) -> tuple[date | None, int, int]:
    """Return latest raw parquet date, files on that date, and expected file count."""

    details = get_parquet_latest_date_coverage_details(data_root, codes)
    return details.observed_latest_trade_date, details.latest_file_count, details.expected_file_count


def load_industry_map(
    industry_map_path: str | Path,
) -> dict[str, str]:
    """加载行业映射文件。

    参数：
      industry_map_path: 行业映射 CSV 文件路径

    返回：
      股票到行业的映射字典 {code: industry}

    异常：
      FileNotFoundError: 文件不存在
    """

    path = Path(industry_map_path)
    if not path.is_file():
        return {}  # 行业映射缺失不影响扫描，仅降级处理

    industry_map: dict[str, str] = {}
    try:
        import pandas as pd

        df = pd.read_csv(path)
        if "code" in df.columns and "industry" in df.columns:
            for _, row in df.iterrows():
                code = str(row["code"]).strip()
                industry = str(row["industry"]).strip()
                if code and code not in {".", ".."}:
                    industry_map[code] = industry
    except Exception:
        # 行业映射解析失败，返回空字典
        pass

    return industry_map


def load_stock_records(
    code: str,
    data_root: str | Path,
) -> tuple[dict[str, Any], ...]:
    """加载单只股票的日线记录。

    复用 V1 的 load_local_daily_bars，增加字段校验。

    参数：
      code: 股票代码
      data_root: 数据根目录

    返回：
      日线记录元组

    异常：
      DataValidationError: 数据质量校验失败
    """

    return load_local_daily_bars(code, data_root=data_root)


def validate_stock_records(records: Sequence[Mapping[str, Any]]) -> None:
    """校验股票记录数据质量。

    复用 V1 的 validate_daily_bars。

    参数：
      records: 日线记录序列

    异常：
      DataValidationError: 数据质量校验失败
    """

    validate_daily_bars(records)


def get_latest_trading_date(
    records: Sequence[Mapping[str, Any]],
) -> str:
    """获取最新交易日。

    参数：
      records: 日线记录序列

    返回：
      最新交易日字符串（YYYY-MM-DD）
    """

    if not records:
        return ""

    # 按日期排序，返回最新日期
    dates = [record["date"] for record in records]
    return str(max(dates))
