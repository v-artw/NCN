"""Standalone local daily-bar loading and validation."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from math import isfinite
from pathlib import Path
from typing import Any


class DataValidationError(ValueError):
    """Raised when daily-bar input violates the data contract."""

    def __init__(self, code: str, detail: str) -> None:
        self._code = code
        super().__init__(f"{code}: {detail}")

    @property
    def code(self) -> str:
        """Stable machine-readable data-quality error code."""

        return self._code


REQUIRED_DAILY_BAR_FIELDS = frozenset(
    {
        "code",
        "date",
        "open",
        "high",
        "low",
        "close",
        "preclose",
        "volume",
        "amount",
        "turn",
        "tradestatus",
        "isST",
    }
)

_NUMERIC_FIELDS = ("open", "high", "low", "close", "preclose", "volume", "amount", "turn")
_PRICE_FIELDS = ("open", "high", "low", "close", "preclose")
_NON_NEGATIVE_FIELDS = ("volume", "amount", "turn")
_VALID_BINARY_MARKERS = {"0", "1"}


@dataclass(frozen=True)
class FileAuditResult:
    """Observed quality status for one direct directory entry."""

    code: str | None
    relative_path: Path
    status: str
    error_code: str | None
    detail: str | None
    row_count: int | None
    first_date: date | None
    last_date: date | None


@dataclass(frozen=True)
class CoverageAuditResult:
    """Observed coverage relative to an explicitly supplied expectation."""

    status: str
    coverage_expectation_id: str | None
    expected_code_count: int
    checked_code_count: int
    missing_codes: tuple[str, ...]
    missing_dates_by_code: tuple[tuple[str, tuple[date, ...]], ...]
    download_failure_attribution: str = "unavailable"


@dataclass(frozen=True)
class DirectoryAuditResult:
    """Read-only audit facts for the direct children of one local root."""

    data_root: Path
    scope: str
    read_only: bool
    repair_performed: bool
    candidate_parquet_count: int
    non_parquet_entry_count: int
    passed_count: int
    rejected_count: int
    error_code_counts: tuple[tuple[str, int], ...]
    successful_file_date_ranges: tuple[tuple[date, date], ...]
    file_results: tuple[FileAuditResult, ...]
    coverage: CoverageAuditResult


def validate_daily_bars(records: Sequence[Mapping[str, Any]]) -> None:
    """Validate daily bar records against the minimum A-share data contract."""

    if isinstance(records, (str, bytes)) or not isinstance(records, Sequence):
        raise DataValidationError("invalid_records", "Daily bars must be provided as a non-empty sequence of mapping records.")
    if not records:
        raise DataValidationError("empty_daily_bars", "Daily bars must not be empty.")

    seen_keys: set[tuple[str, date]] = set()
    last_date_by_code: dict[str, date] = {}

    for index, record in enumerate(records):
        if not isinstance(record, Mapping):
            raise DataValidationError("invalid_record", f"Record {index} must be a mapping, got {type(record).__name__}.")

        missing_fields = missing_required_fields(record)
        if missing_fields:
            raise DataValidationError(
                "missing_required_field",
                f"Record {index} is missing required fields: {', '.join(sorted(missing_fields))}.",
            )

        _validate_no_missing_values(record, index)
        code = _parse_code(record["code"], index)
        bar_date = _parse_date(record["date"], index)
        numeric_values = {field: _parse_number(record[field], field, index) for field in _NUMERIC_FIELDS}
        _validate_prices(numeric_values, index, code, bar_date)
        _validate_non_negative_values(numeric_values, index, code, bar_date)
        _parse_binary_marker(record["tradestatus"], "tradestatus", index, code, bar_date)
        _parse_binary_marker(record["isST"], "isST", index, code, bar_date)

        key = (code, bar_date)
        if key in seen_keys:
            raise DataValidationError("duplicate_daily_bar", f"Duplicate daily bar for code={code}, date={bar_date.isoformat()}.")
        seen_keys.add(key)

        previous_date = last_date_by_code.get(code)
        if previous_date is not None and bar_date <= previous_date:
            raise DataValidationError(
                "non_increasing_date",
                "Dates must be strictly increasing within each code: "
                f"code={code}, previous={previous_date.isoformat()}, current={bar_date.isoformat()}.",
            )
        last_date_by_code[code] = bar_date


def load_local_daily_bars(
    code: str,
    *,
    data_root: str | Path = Path("PFrontStockData"),
    expected_bar_dates: Sequence[date | datetime | str] | None = None,
) -> tuple[dict[str, Any], ...]:
    """Read and validate one local security's daily bars without altering source data."""

    requested_code = _validate_requested_code(code)
    root = _validate_data_root(data_root)
    data_file = root / f"{requested_code}.parquet"
    if data_file.is_symlink():
        raise DataValidationError("data_file_not_regular", f"Local daily-bar path is not a regular file: {data_file}.")
    if not data_file.exists():
        raise DataValidationError("data_file_missing", f"Local daily-bar file does not exist: {data_file}.")
    if not data_file.is_file():
        raise DataValidationError("data_file_not_regular", f"Local daily-bar path is not a regular file: {data_file}.")

    return _load_validated_local_daily_bar_file(data_file, requested_code, expected_bar_dates)


def audit_local_daily_bar_directory(
    *,
    data_root: str | Path,
    expected_bar_dates_by_code: Mapping[str, Sequence[date | datetime | str]] | None = None,
    coverage_expectation_id: str | None = None,
) -> DirectoryAuditResult:
    """Audit direct local entries without modifying source files or inferring coverage."""

    expected_dates_by_code = _validate_coverage_expectation(
        expected_bar_dates_by_code,
        coverage_expectation_id,
    )
    root = _validate_audit_data_root(data_root)
    entries = sorted(root.iterdir(), key=lambda entry: entry.name)
    file_results: list[FileAuditResult] = []
    actual_dates_by_code: dict[str, set[date]] = {}

    for entry in entries:
        relative_path = Path(entry.name)
        if entry.suffix != ".parquet":
            file_results.append(
                FileAuditResult(None, relative_path, "excluded", "non_parquet_entry", None, None, None, None)
            )
            continue

        try:
            code = _validate_requested_code(entry.stem)
        except DataValidationError as exc:
            file_results.append(
                FileAuditResult(None, relative_path, "rejected", exc.code, str(exc), None, None, None)
            )
            continue

        if entry.is_symlink() or not entry.is_file():
            detail = f"Local daily-bar path is not a regular file: {entry}."
            file_results.append(
                FileAuditResult(code, relative_path, "rejected", "data_file_not_regular", detail, None, None, None)
            )
            continue

        try:
            records = _load_validated_local_daily_bar_file(entry, code)
        except DataValidationError as exc:
            file_results.append(
                FileAuditResult(code, relative_path, "rejected", exc.code, str(exc), None, None, None)
            )
            continue

        parsed_dates = tuple(_parse_date(record["date"], index) for index, record in enumerate(records))
        actual_dates_by_code[code] = set(parsed_dates)
        file_results.append(
            FileAuditResult(
                code,
                relative_path,
                "passed",
                None,
                None,
                len(records),
                parsed_dates[0],
                parsed_dates[-1],
            )
        )

    coverage = _build_coverage_audit_result(
        actual_dates_by_code,
        expected_dates_by_code,
        coverage_expectation_id,
    )
    error_counts = Counter(result.error_code for result in file_results if result.error_code is not None)
    successful_ranges = tuple(
        (result.first_date, result.last_date)
        for result in file_results
        if result.status == "passed" and result.first_date is not None and result.last_date is not None
    )
    candidate_count = sum(1 for entry in entries if entry.suffix == ".parquet")
    return DirectoryAuditResult(
        data_root=root,
        scope="direct_children_only",
        read_only=True,
        repair_performed=False,
        candidate_parquet_count=candidate_count,
        non_parquet_entry_count=len(entries) - candidate_count,
        passed_count=sum(result.status == "passed" for result in file_results),
        rejected_count=sum(result.status == "rejected" for result in file_results),
        error_code_counts=tuple(sorted(error_counts.items())),
        successful_file_date_ranges=successful_ranges,
        file_results=tuple(file_results),
        coverage=coverage,
    )


def _load_validated_local_daily_bar_file(
    data_file: Path,
    requested_code: str,
    expected_bar_dates: Sequence[date | datetime | str] | None = None,
) -> tuple[dict[str, Any], ...]:
    table = _read_parquet_table(data_file)
    _validate_parquet_schema(table, data_file)
    records = _normalize_table_records(table)
    _validate_requested_code_matches_records(records, requested_code)
    validate_daily_bars(records)
    if expected_bar_dates is not None:
        _validate_expected_dates_for_single_code(records, requested_code, expected_bar_dates)
    return tuple(records)


def missing_required_fields(record: Mapping[str, Any]) -> set[str]:
    """Return the required daily bar fields absent from a record."""

    return set(REQUIRED_DAILY_BAR_FIELDS.difference(record.keys()))


def _validate_requested_code(code: str) -> str:
    if not isinstance(code, str):
        raise DataValidationError("invalid_code", "Requested code must be a non-empty string.")
    if code != code.strip() or not code or code in {".", ".."}:
        raise DataValidationError("invalid_code", "Requested code must not be blank, '.' or '..'.")
    if "\x00" in code:
        raise DataValidationError("invalid_code", "Requested code must not contain NUL characters.")
    if "/" in code or "\\" in code:
        raise DataValidationError("invalid_code", "Requested code must not contain path separators.")
    return code


def _validate_data_root(data_root: str | Path) -> Path:
    try:
        root = Path(data_root)
    except TypeError as exc:
        raise DataValidationError("invalid_data_root", "data_root must be a path-like value.") from exc
    if not root.exists():
        raise DataValidationError("data_root_missing", f"Local daily-bar root does not exist: {root}.")
    if not root.is_dir():
        raise DataValidationError("data_root_not_directory", f"Local daily-bar root is not a directory: {root}.")
    return root


def _validate_audit_data_root(data_root: str | Path) -> Path:
    try:
        root = Path(data_root)
    except TypeError as exc:
        raise DataValidationError("invalid_data_root", "data_root must be a path-like value.") from exc
    if root.is_symlink():
        raise DataValidationError(
            "data_root_not_directory",
            f"Local daily-bar audit root must not be a symbolic link: {root}.",
        )
    if not root.exists():
        raise DataValidationError("data_root_missing", f"Local daily-bar root does not exist: {root}.")
    if not root.is_dir():
        raise DataValidationError("data_root_not_directory", f"Local daily-bar root is not a directory: {root}.")
    return root


def _validate_coverage_expectation(
    expected_bar_dates_by_code: Mapping[str, Sequence[date | datetime | str]] | None,
    coverage_expectation_id: str | None,
) -> dict[str, frozenset[date]] | None:
    if expected_bar_dates_by_code is None:
        if coverage_expectation_id is not None:
            raise DataValidationError(
                "invalid_coverage_expectation",
                "coverage_expectation_id requires expected_bar_dates_by_code.",
            )
        return None
    if not isinstance(coverage_expectation_id, str) or not coverage_expectation_id.strip():
        raise DataValidationError(
            "invalid_coverage_expectation",
            "coverage_expectation_id must be a non-empty, non-blank string when expected bar dates are provided.",
        )
    return _validate_expected_bar_dates_by_code(expected_bar_dates_by_code)


def _validate_expected_bar_dates_by_code(
    expected_bar_dates_by_code: Mapping[str, Sequence[date | datetime | str]],
) -> dict[str, frozenset[date]]:
    if not isinstance(expected_bar_dates_by_code, Mapping):
        raise DataValidationError(
            "invalid_expected_bar_dates",
            "Expected bar dates by code must be a mapping of requested codes to date sequences.",
        )

    parsed_dates_by_code: dict[str, frozenset[date]] = {}
    for code, expected_dates in expected_bar_dates_by_code.items():
        requested_code = _validate_requested_code(code)
        if isinstance(expected_dates, (str, bytes)) or not isinstance(expected_dates, Sequence):
            raise DataValidationError(
                "invalid_expected_bar_dates",
                f"Expected bar dates for code={requested_code} must be a sequence of date values.",
            )
        parsed_dates: set[date] = set()
        for index, expected_value in enumerate(expected_dates):
            try:
                expected_date = _parse_date(expected_value, index)
            except DataValidationError as exc:
                raise DataValidationError(
                    "invalid_expected_bar_dates",
                    f"Expected date {index} is invalid for code={requested_code}: {exc}.",
                ) from exc
            if expected_date in parsed_dates:
                raise DataValidationError(
                    "invalid_expected_bar_dates",
                    f"Expected date {expected_date.isoformat()} is duplicated for code={requested_code}.",
                )
            parsed_dates.add(expected_date)
        parsed_dates_by_code[requested_code] = frozenset(parsed_dates)
    return parsed_dates_by_code


def _build_coverage_audit_result(
    actual_dates_by_code: Mapping[str, set[date]],
    expected_dates_by_code: Mapping[str, frozenset[date]] | None,
    coverage_expectation_id: str | None,
) -> CoverageAuditResult:
    if expected_dates_by_code is None:
        return CoverageAuditResult("not_assessed", coverage_expectation_id, 0, 0, (), ())

    missing_codes = tuple(sorted(set(expected_dates_by_code).difference(actual_dates_by_code)))
    missing_dates_by_code = tuple(
        (code, tuple(sorted(expected_dates.difference(actual_dates_by_code[code]))))
        for code, expected_dates in expected_dates_by_code.items()
        if code in actual_dates_by_code and expected_dates.difference(actual_dates_by_code[code])
    )
    complete = not missing_codes and not missing_dates_by_code
    return CoverageAuditResult(
        "assessed_complete" if complete else "assessed_incomplete",
        coverage_expectation_id,
        len(expected_dates_by_code),
        len(set(expected_dates_by_code).intersection(actual_dates_by_code)),
        missing_codes,
        missing_dates_by_code,
    )


def _read_parquet_table(data_file: Path) -> Any:
    try:
        import pyarrow.parquet as parquet
    except ImportError as exc:
        raise DataValidationError(
            "parquet_reader_unavailable",
            "PyArrow is required to read local Parquet daily-bar files.",
        ) from exc

    try:
        return parquet.read_table(data_file)
    except Exception as exc:
        raise DataValidationError("unreadable_parquet", f"Cannot read local daily-bar file: {data_file}.") from exc


def _validate_parquet_schema(table: Any, data_file: Path) -> None:
    try:
        column_names = set(table.column_names)
    except AttributeError as exc:
        raise DataValidationError("unreadable_parquet", f"Reader returned no column schema for: {data_file}.") from exc

    missing_fields = REQUIRED_DAILY_BAR_FIELDS.difference(column_names)
    if missing_fields:
        raise DataValidationError(
            "schema_missing_required_field",
            f"Local daily-bar file {data_file} is missing required fields: {', '.join(sorted(missing_fields))}.",
        )


def _normalize_table_records(table: Any) -> list[dict[str, Any]]:
    try:
        raw_records = table.to_pylist()
    except Exception as exc:
        raise DataValidationError("unreadable_parquet", "Cannot convert local daily-bar table into records.") from exc

    records = [{field: record[field] for field in REQUIRED_DAILY_BAR_FIELDS} for record in raw_records]
    if not records:
        raise DataValidationError("empty_daily_bars", "Local daily-bar file contains no rows.")
    return records


def _validate_requested_code_matches_records(records: Sequence[Mapping[str, Any]], requested_code: str) -> None:
    for index, record in enumerate(records):
        if record["code"] != requested_code:
            raise DataValidationError(
                "code_mismatch",
                f"Record {index} code={record['code']!r} does not match requested code={requested_code!r}.",
            )


def _validate_expected_dates_for_single_code(
    records: Sequence[Mapping[str, Any]],
    code: str,
    expected_bar_dates: Sequence[date | datetime | str],
) -> None:
    if isinstance(expected_bar_dates, (str, bytes)) or not isinstance(expected_bar_dates, Sequence):
        raise DataValidationError(
            "invalid_expected_bar_dates",
            "Expected bar dates must be a sequence of date values for one security.",
        )

    expected_dates: set[date] = set()
    for index, expected_value in enumerate(expected_bar_dates):
        try:
            expected_date = _parse_date(expected_value, index)
        except DataValidationError as exc:
            raise DataValidationError(
                "invalid_expected_bar_dates",
                f"Expected date {index} is invalid: {exc}.",
            ) from exc
        if expected_date in expected_dates:
            raise DataValidationError(
                "invalid_expected_bar_dates",
                f"Expected date {expected_date.isoformat()} is duplicated for code={code}.",
            )
        expected_dates.add(expected_date)

    actual_dates = {_parse_date(record["date"], index) for index, record in enumerate(records)}
    missing_dates = sorted(expected_dates.difference(actual_dates))
    if missing_dates:
        formatted_dates = ", ".join(day.isoformat() for day in missing_dates)
        raise DataValidationError("date_gap", f"code={code} is missing expected daily-bar dates: {formatted_dates}.")


def _validate_no_missing_values(record: Mapping[str, Any], index: int) -> None:
    for field in REQUIRED_DAILY_BAR_FIELDS:
        value = record[field]
        if value is None:
            raise DataValidationError("missing_value", f"Record {index} field '{field}' must not be None.")
        if isinstance(value, str) and value.strip() == "":
            raise DataValidationError("missing_value", f"Record {index} field '{field}' must not be empty.")


def _parse_code(value: Any, index: int) -> str:
    if not isinstance(value, str):
        raise DataValidationError("invalid_code", f"Record {index} field 'code' must be a non-empty string.")
    code = value.strip()
    if not code:
        raise DataValidationError("invalid_code", f"Record {index} field 'code' must be a non-empty string.")
    return code


def _parse_date(value: Any, index: int) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError as exc:
            raise DataValidationError(
                "invalid_date",
                f"Record {index} field 'date' must use YYYY-MM-DD format, got {value!r}.",
            ) from exc
    raise DataValidationError("invalid_date", f"Record {index} field 'date' must be YYYY-MM-DD text or a date object.")


def _parse_number(value: Any, field: str, index: int) -> float:
    if isinstance(value, bool):
        raise DataValidationError("invalid_numeric_value", f"Record {index} field '{field}' must be numeric, got bool.")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise DataValidationError(
            "invalid_numeric_value",
            f"Record {index} field '{field}' must be numeric, got {value!r}.",
        ) from exc
    if not isfinite(number):
        raise DataValidationError(
            "invalid_numeric_value",
            f"Record {index} field '{field}' must be finite, got {value!r}.",
        )
    return number


def _validate_prices(values: Mapping[str, float], index: int, code: str, bar_date: date) -> None:
    for field in _PRICE_FIELDS:
        if values[field] <= 0:
            raise DataValidationError(
                "non_positive_price",
                f"Record {index} code={code} date={bar_date.isoformat()} field '{field}' must be positive.",
            )

    open_price = values["open"]
    high_price = values["high"]
    low_price = values["low"]
    close_price = values["close"]

    if high_price < max(open_price, low_price, close_price):
        raise DataValidationError(
            "invalid_ohlc",
            f"Record {index} code={code} date={bar_date.isoformat()} has illegal OHLC: "
            "high must be greater than or equal to open, low, and close.",
        )
    if low_price > min(open_price, high_price, close_price):
        raise DataValidationError(
            "invalid_ohlc",
            f"Record {index} code={code} date={bar_date.isoformat()} has illegal OHLC: "
            "low must be less than or equal to open, high, and close.",
        )


def _validate_non_negative_values(values: Mapping[str, float], index: int, code: str, bar_date: date) -> None:
    for field in _NON_NEGATIVE_FIELDS:
        if values[field] < 0:
            raise DataValidationError(
                "negative_value",
                f"Record {index} code={code} date={bar_date.isoformat()} field '{field}' must be non-negative.",
            )


def _parse_binary_marker(value: Any, field: str, index: int, code: str, bar_date: date) -> str:
    if isinstance(value, bool):
        marker = "1" if value else "0"
    elif isinstance(value, int):
        marker = str(value)
    elif isinstance(value, str):
        marker = value.strip()
    else:
        raise DataValidationError(
            "invalid_status_marker",
            f"Record {index} code={code} date={bar_date.isoformat()} field '{field}' must be 0 or 1.",
        )

    if marker not in _VALID_BINARY_MARKERS:
        raise DataValidationError(
            "invalid_status_marker",
            f"Record {index} code={code} date={bar_date.isoformat()} field '{field}' must be 0 or 1, got {value!r}.",
        )
    return marker
