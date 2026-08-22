from __future__ import annotations

from pathlib import Path
import json
import os
import plistlib
import shutil
import subprocess


ROOT = Path(__file__).parents[1]
PLIST = ROOT / "config/launchd/com.vartw.stock-ncn.edge-scout.plist"


def test_launchd_plist_is_valid_and_runs_weekdays_after_close() -> None:
    plutil = shutil.which("plutil")
    if plutil is not None:
        completed = subprocess.run([plutil, "-lint", str(PLIST)], capture_output=True, text=True)
        assert completed.returncode == 0, completed.stderr
    else:
        with PLIST.open("rb") as file:
            plistlib.load(file)
    content = PLIST.read_text(encoding="utf-8")
    assert content.count("<key>Weekday</key>") == 5
    assert "<integer>18</integer>" in content
    assert "<integer>30</integer>" in content
    assert "run_edge_scout_scheduled.sh" in content


def test_scheduler_requires_reviewed_environment_and_has_alerting() -> None:
    content = (ROOT / "scripts/run_edge_scout_scheduled.sh").read_text(encoding="utf-8")
    assert "EDGE_SCOUT_CALENDAR_SHA256" in content
    assert "EDGE_SCOUT_CALENDAR_APPROVAL" in content
    assert "approved_for_read_only_research_production" in content
    assert "EDGE_SCOUT_ALERT_WEBHOOK_URL" in content
    assert "osascript" in content
    assert "TIMEOUT_SECONDS" in content
    assert "RETAIN_LOGS" in content
    assert "preflight_failed" in content
    assert 'TIMEOUT_SECONDS="${EDGE_SCOUT_SCHEDULE_TIMEOUT_SECONDS' in content


def test_scheduler_preflight_failure_is_logged(tmp_path) -> None:
    env = os.environ.copy()
    env.update({
        "EDGE_SCOUT_SCHEDULE_ENV": str(tmp_path / "missing.env"),
        "EDGE_SCOUT_SCHEDULE_LOG_DIR": str(tmp_path / "logs"),
        "EDGE_SCOUT_DISABLE_LOCAL_ALERT": "1",
    })
    completed = subprocess.run(
        ["bash", str(ROOT / "scripts/run_edge_scout_scheduled.sh")],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 2
    summaries = list((tmp_path / "logs").glob("*.summary.json"))
    assert len(summaries) == 1
    assert json.loads(summaries[0].read_text(encoding="utf-8"))["reason"] == "missing_reviewed_environment_file"
