"""Research-production operational gate tests."""

from datetime import date, datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from ashare_edge_scout.operations import (
    DirectoryLock,
    FreshnessPolicy,
    OperationsError,
    atomic_write_json,
    load_calendar_file,
    retain_successful_runs,
    validate_freshness,
)


def _calendar() -> list[date]:
    return [date(2026, 7, 29), date(2026, 7, 30), date(2026, 7, 31), date(2026, 8, 3)]


def test_load_calendar_file_binds_content_digest_and_accepts_comments(tmp_path):
    path = tmp_path / "cn_2026.txt"
    path.write_text("# comment\n2026-07-29\n2026-07-30\n", encoding="utf-8")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    version, days = load_calendar_file(path, expected_sha256=digest)
    assert version == f"cn_2026:{digest}"
    assert days == [date(2026, 7, 29), date(2026, 7, 30)]
    with pytest.raises(OperationsError, match="SHA-256 mismatch"):
        load_calendar_file(path, expected_sha256="0" * 64)


def test_freshness_requires_current_enough_data_and_t_plus_two_binding():
    evidence = validate_freshness(
        calendar=_calendar(),
        policy=FreshnessPolicy("cn_2026", max_lag_trading_days=0, minimum_coverage_ratio=0.9),
        scan_as_of=date(2026, 7, 29),
        observed_latest=date(2026, 7, 31),
        covered_count=9,
        input_count=10,
        now=datetime(2026, 8, 1, tzinfo=timezone.utc),
        readable_count=9,
        skipped_count=1,
    )
    assert evidence.lag_trading_days == 0
    assert evidence.observed_coverage_ratio == 0.9
    payload = evidence.as_dict()
    assert payload["coverage_expected_file_count"] == 10
    assert payload["coverage_readable_file_count"] == 9
    assert payload["coverage_skipped_file_count"] == 1
    assert payload["coverage_latest_file_count"] == 9
    assert payload["coverage_denominator"] == "expected_file_count"


def test_freshness_rejects_stale_data_and_insufficient_coverage():
    with pytest.raises(OperationsError, match="stale data"):
        validate_freshness(
            calendar=_calendar(),
            policy=FreshnessPolicy("cn_2026", max_lag_trading_days=0),
            scan_as_of=date(2026, 7, 31),
            observed_latest=date(2026, 7, 30),
            covered_count=10,
            input_count=10,
            now=datetime(2026, 8, 3, tzinfo=timezone.utc),
        )

    with pytest.raises(OperationsError, match="coverage"):
        validate_freshness(
            calendar=_calendar() + [date(2026, 8, 4)],
            policy=FreshnessPolicy("cn_2026", max_lag_trading_days=0, minimum_coverage_ratio=0.95),
            scan_as_of=date(2026, 7, 30),
            observed_latest=date(2026, 8, 3),
            covered_count=9,
            input_count=10,
            now=datetime(2026, 8, 3, tzinfo=timezone.utc),
        )


def test_directory_lock_is_fail_closed_and_releases(tmp_path):
    lock_path = tmp_path / "lock"
    with DirectoryLock(lock_path, run_id="run-1"):
        assert (lock_path / "owner.json").is_file()
        with pytest.raises(OperationsError, match="another research production run"):
            with DirectoryLock(lock_path, run_id="run-2"):
                pass
    assert not lock_path.exists()


def test_atomic_write_and_retention_protect_latest(tmp_path):
    atomic_write_json(tmp_path / "latest.json", {"run_directory": "run-2"})
    for name in ("run-1", "run-2", "run-3"):
        run = tmp_path / name
        run.mkdir()
        (run / "summary.json").write_text("{}", encoding="utf-8")
        (run / "manifest.json").write_text("{}", encoding="utf-8")
    removed = retain_successful_runs(tmp_path, keep=2)
    assert "run-2" not in removed
    assert (tmp_path / "run-2").exists()
    assert len(removed) == 1


def test_production_wrapper_records_failed_run_without_replacing_latest(tmp_path):
    calendar = tmp_path / "reviewed-calendar.txt"
    calendar.write_text("2026-08-03\n", encoding="utf-8")
    digest = hashlib.sha256(calendar.read_bytes()).hexdigest()
    output_root = tmp_path / "output"
    output_root.mkdir()
    latest = output_root / "latest.json"
    latest.write_text('{"run_id":"previous-success"}\n', encoding="utf-8")

    env = os.environ.copy()
    env.update({
        "VENV_PYTHON": sys.executable,
        "EDGE_SCOUT_DATA_ROOT": str(tmp_path / "missing-data"),
        "EDGE_SCOUT_CONFIG": str(tmp_path / "missing-config.yaml"),
        "EDGE_SCOUT_OUTPUT_ROOT": str(output_root),
        "EDGE_SCOUT_CALENDAR": str(calendar),
        "EDGE_SCOUT_CALENDAR_SHA256": digest,
        "EDGE_SCOUT_RUN_ID": "expected-failure",
    })
    completed = subprocess.run(
        ["bash", "scripts/edge_scout_production.sh"],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode != 0
    summary_path = output_root / "operations" / "expected-failure" / "operations_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["status"] == "failed"
    assert summary["exit_code"] != 0
    assert json.loads(latest.read_text(encoding="utf-8")) == {"run_id": "previous-success"}
    assert not (output_root / ".edge_scout_production.lock").exists()


def test_production_cli_is_self_contained_under_safe_path() -> None:
    content = Path("scripts/run_edge_scout_production.py").read_text(encoding="utf-8")
    assert "from run_edge_scout_scan import" not in content
    assert "class ConsoleProgressReporter" in content
