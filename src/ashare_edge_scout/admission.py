"""数据准入模块。

适配 V1 的数据准入逻辑，输出 AdmissionResult 和稳定错误码。
MVP 中 listing_days 来自 parquet bar count，仅为研究近似。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from collections.abc import Callable
from typing import Any, Mapping, Sequence

from .data.daily_bars import (
    DataValidationError,
    REQUIRED_DAILY_BAR_FIELDS,
    load_local_daily_bars,
    validate_daily_bars,
)


@dataclass(frozen=True)
class AdmissionResult:
    """数据准入结果。"""

    code: str
    status: str  # "strict_admitted", "research_window_admitted", "rejected"
    records: tuple[dict[str, Any], ...] = ()
    formal_error_code: str | None = None
    detail: str = ""
    dropped_prefix_row_count: int = 0


def load_research_window_daily_bars(
    code: str,
    data_root: str | Path,
    minimum_rows: int = 80,
) -> AdmissionResult:
    """加载研究窗口内的日线记录。

    从文件开头或末尾截取满足 minimum_rows 的记录窗口。

    参数：
      code: 股票代码
      data_root: 数据根目录
      minimum_rows: 最小记录数

    返回：
      AdmissionResult
    """

    try:
        records = load_local_daily_bars(code, data_root=data_root)
    except DataValidationError as exc:
        return AdmissionResult(
            code=code,
            status="rejected",
            formal_error_code=exc.code,
            detail=str(exc),
        )

    if len(records) < minimum_rows:
        return AdmissionResult(
            code=code,
            status="rejected",
            formal_error_code="insufficient_data",
            detail=f"记录数 {len(records)} 少于最小要求 {minimum_rows}",
        )

    # 尝试从文件末尾截取满足 minimum_rows 的记录窗口
    for start in range(0, len(records) - minimum_rows + 1):
        window = records[start:]
        try:
            validate_daily_bars(window)
            if start > 0:
                return AdmissionResult(
                    code=code,
                    status="research_window_admitted",
                    records=tuple(window),
                    dropped_prefix_row_count=start,
                )
            return AdmissionResult(
                code=code,
                status="strict_admitted",
                records=tuple(records),
            )
        except DataValidationError:
            continue

    return AdmissionResult(
        code=code,
        status="rejected",
        formal_error_code="window_rejected",
        detail=f"无法找到满足 {minimum_rows} 条记录的有效窗口",
    )


def admission_universe(
    codes: Sequence[str],
    data_root: str | Path,
    research_window_admission: bool = False,
    research_window_minimum_rows: int = 80,
    progress_callback: Callable[[int, int, str], None] | None = None,
) -> tuple[dict[str, AdmissionResult], dict[str, str]]:
    """批量准入处理。

    参数：
      codes: 股票代码序列
      data_root: 数据根目录
      research_window_admission: 是否使用研究窗口准入
      research_window_minimum_rows: 研究窗口最小记录数

    返回：
      (features_by_code, failures_by_code) 元组
    """

    features_by_code: dict[str, AdmissionResult] = {}
    failures_by_code: dict[str, str] = {}

    total = len(codes)
    for processed, code in enumerate(codes, start=1):
        try:
            if research_window_admission:
                result = load_research_window_daily_bars(
                    code, data_root, research_window_minimum_rows
                )
            else:
                records = load_local_daily_bars(code, data_root=data_root)
                result = AdmissionResult(
                    code=code,
                    status="strict_admitted",
                    records=tuple(records),
                )

            if result.status == "strict_admitted" or result.status == "research_window_admitted":
                features_by_code[code] = result
            else:
                failures_by_code[code] = result.formal_error_code or "unknown"
        except DataValidationError as exc:
            failures_by_code[code] = exc.code
        finally:
            if progress_callback is not None:
                progress_callback(processed, total, code)

    return features_by_code, failures_by_code
