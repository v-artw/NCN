from __future__ import annotations

import os
import socket
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).parents[1]
CONTROL = ROOT / "scripts" / "edge_scout_web_control.sh"


def test_web_control_script_starts_reports_and_stops(tmp_path: Path) -> None:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    environment = {
        **os.environ,
        "EDGE_SCOUT_WEB_PORT": str(port),
        "EDGE_SCOUT_WEB_RUNTIME_DIR": str(tmp_path / "runtime"),
        "VENV_PYTHON": sys.executable,
    }
    try:
        started = _run("start", environment)
        assert started.returncode == 0, started.stderr
        assert "已启动" in started.stdout

        status = _run("status", environment)
        assert status.returncode == 0
        assert "运行中" in status.stdout

        duplicate = _run("start", environment)
        assert duplicate.returncode == 0
        assert "已在运行" in duplicate.stdout
    finally:
        stopped = _run("stop", environment)
    assert stopped.returncode == 0, stopped.stderr
    assert "已关闭" in stopped.stdout or "未运行" in stopped.stdout


def _run(action: str, environment: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(CONTROL), action],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
    )
