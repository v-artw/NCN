"""Research-production operational gates and filesystem primitives."""

from __future__ import annotations

import json
import hashlib
import os
import re
import socket
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .calendar import CalendarError, normalize_trading_days


class OperationsError(RuntimeError):
    """Raised when a research-production operational gate fails."""


@dataclass(frozen=True)
class FreshnessPolicy:
    calendar_version: str
    max_lag_trading_days: int = 0
    minimum_coverage_ratio: float = 0.95


@dataclass(frozen=True)
class FreshnessEvidence:
    calendar_version: str
    expected_latest_trade_date: date
    observed_latest_trade_date: date
    scan_as_of: date
    observed_coverage_ratio: float
    minimum_coverage_ratio: float
    lag_trading_days: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "calendar_version": self.calendar_version,
            "expected_latest_trade_date": self.expected_latest_trade_date.isoformat(),
            "observed_latest_trade_date": self.observed_latest_trade_date.isoformat(),
            "scan_as_of": self.scan_as_of.isoformat(),
            "observed_coverage_ratio": self.observed_coverage_ratio,
            "minimum_coverage_ratio": self.minimum_coverage_ratio,
            "lag_trading_days": self.lag_trading_days,
        }


def load_calendar_file(
    path: str | Path,
    *,
    expected_sha256: str | None = None,
) -> tuple[str, list[date]]:
    """Load an explicit newline-delimited YYYY-MM-DD exchange calendar."""

    calendar_path = Path(path)
    if not calendar_path.is_file():
        raise OperationsError(f"trading calendar not found: {calendar_path}")
    content = calendar_path.read_bytes()
    digest = hashlib.sha256(content).hexdigest()
    if expected_sha256 is not None:
        normalized_digest = expected_sha256.strip().lower()
        if not re.fullmatch(r"[0-9a-f]{64}", normalized_digest):
            raise OperationsError("approved trading calendar SHA-256 must contain 64 hexadecimal characters")
        if digest != normalized_digest:
            raise OperationsError(
                f"trading calendar SHA-256 mismatch: expected={normalized_digest}, actual={digest}"
            )
    version = f"{calendar_path.stem}:{digest}"
    values: list[str] = []
    for line in content.decode("utf-8").splitlines():
        value = line.split("#", 1)[0].strip()
        if value:
            values.append(value)
    try:
        return version, normalize_trading_days(values)
    except CalendarError as exc:
        raise OperationsError(f"invalid trading calendar {calendar_path}: {exc}") from exc


def validate_freshness(
    *,
    calendar: list[date],
    policy: FreshnessPolicy,
    scan_as_of: date,
    observed_latest: date,
    covered_count: int,
    input_count: int,
    now: datetime,
) -> FreshnessEvidence:
    """Fail closed on future, stale, incomplete, or calendar-inconsistent data."""

    if now.tzinfo is None:
        raise OperationsError("freshness validation requires a timezone-aware clock")
    if policy.max_lag_trading_days < 0:
        raise OperationsError("max_lag_trading_days must be non-negative")
    if not 0.0 <= policy.minimum_coverage_ratio <= 1.0:
        raise OperationsError("minimum_coverage_ratio must be between 0 and 1")
    today = now.astimezone(timezone.utc).date()
    available = [day for day in calendar if day <= today]
    if not available:
        raise OperationsError("trading calendar has no day at or before current date")
    expected = available[-1]
    if observed_latest > expected:
        raise OperationsError(
            f"observed data is from the future: observed={observed_latest}, expected_latest={expected}"
        )
    try:
        expected_index = calendar.index(expected)
        observed_index = calendar.index(observed_latest)
        as_of_index = calendar.index(scan_as_of)
    except ValueError as exc:
        raise OperationsError(f"scan dates must be present in the trading calendar: {exc}") from exc
    lag = expected_index - observed_index
    if lag > policy.max_lag_trading_days:
        raise OperationsError(
            f"stale data: observed_latest={observed_latest}, expected_latest={expected}, lag={lag}"
        )
    if as_of_index > observed_index or observed_index - as_of_index != 2:
        raise OperationsError(
            f"scan T/T+2 binding invalid: as_of={scan_as_of}, observed_latest={observed_latest}"
        )
    ratio = covered_count / input_count if input_count else 0.0
    if ratio < policy.minimum_coverage_ratio:
        raise OperationsError(
            f"insufficient latest-date coverage: covered={covered_count}, input={input_count}, ratio={ratio:.4f}"
        )
    return FreshnessEvidence(
        calendar_version=policy.calendar_version,
        expected_latest_trade_date=expected,
        observed_latest_trade_date=observed_latest,
        scan_as_of=scan_as_of,
        observed_coverage_ratio=ratio,
        minimum_coverage_ratio=policy.minimum_coverage_ratio,
        lag_trading_days=lag,
    )


_RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")


def validate_run_id(run_id: str) -> None:
    if not _RUN_ID_RE.fullmatch(run_id):
        raise OperationsError(f"invalid run_id: {run_id!r}")


class DirectoryLock(AbstractContextManager["DirectoryLock"]):
    """Conservative mkdir lock with inspectable owner metadata."""

    def __init__(self, path: str | Path, *, run_id: str) -> None:
        self.path = Path(path)
        self.run_id = run_id

    def __enter__(self) -> "DirectoryLock":
        validate_run_id(self.run_id)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self.path.mkdir()
        except FileExistsError as exc:
            metadata = self.path / "owner.json"
            detail = metadata.read_text(encoding="utf-8") if metadata.is_file() else "owner metadata unavailable"
            raise OperationsError(f"another research production run holds {self.path}: {detail}") from exc
        payload = {
            "schema_version": 1,
            "pid": os.getpid(),
            "hostname": socket.gethostname(),
            "run_id": self.run_id,
            "started_at_utc": datetime.now(timezone.utc).isoformat(),
        }
        (self.path / "owner.json").write_text(
            json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8"
        )
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        owner = self.path / "owner.json"
        if owner.exists():
            owner.unlink()
        try:
            self.path.rmdir()
        except FileNotFoundError:
            pass


def atomic_write_json(path: str | Path, payload: Mapping[str, Any]) -> None:
    target = Path(path)
    temporary = target.with_name(f".{target.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, target)


def retain_successful_runs(output_root: str | Path, *, keep: int) -> list[str]:
    """Remove only old validated run directories; always protect latest."""

    if keep < 1:
        raise OperationsError("retention keep must be at least 1")
    root = Path(output_root)
    latest_path = root / "latest.json"
    latest_run = None
    if latest_path.is_file():
        latest_run = json.loads(latest_path.read_text(encoding="utf-8")).get("run_directory")
    candidates: list[tuple[datetime, Path]] = []
    for child in root.iterdir() if root.is_dir() else ():
        if not child.is_dir() or child.name.startswith(".") or child.name == latest_run:
            continue
        summary = child / "summary.json"
        manifest = child / "manifest.json"
        if not summary.is_file() or not manifest.is_file():
            continue
        try:
            published = datetime.fromtimestamp(child.stat().st_mtime, timezone.utc)
        except OSError:
            continue
        candidates.append((published, child))
    candidates.sort(reverse=True)
    protected = max(0, keep - (1 if latest_run else 0))
    removed: list[str] = []
    for _, child in candidates[protected:]:
        import shutil
        shutil.rmtree(child)
        removed.append(child.name)
    return removed
