from __future__ import annotations

import subprocess
import os
import shutil
from pathlib import Path


ROOT = Path(__file__).parents[1]
MAIN = ROOT / "main.sh"


def test_main_script_help_lists_control_commands() -> None:
    completed = subprocess.run(
        ["bash", str(MAIN), "help"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert completed.returncode == 0
    assert "./main.sh start" in completed.stdout
    assert "./main.sh stop" in completed.stdout
    assert "./main.sh restart" in completed.stdout
    assert "./main.sh status" in completed.stdout
    assert "./main.sh scan" in completed.stdout
    assert "./main.sh scan-local" in completed.stdout
    assert "./main.sh single 600519" in completed.stdout
    assert "./main.sh update" in completed.stdout
    assert "方向键交互菜单" in completed.stdout


def test_main_script_delegates_scan_arguments(tmp_path: Path) -> None:
    fake = tmp_path / "fake_scan.sh"
    fake.write_text(
        "#!/usr/bin/env bash\nprintf '%s|%s\\n' \"${EDGE_SCOUT_AUTO_UPDATE:-unset}\" \"$*\"\n",
        encoding="utf-8",
    )
    fake.chmod(0o755)
    environment = {**os.environ, "EDGE_SCOUT_SCAN_SCRIPT": str(fake)}

    market = subprocess.run(
        ["bash", str(MAIN), "scan", "--as-of", "2026-08-04"],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=10,
    )
    local_single = subprocess.run(
        ["bash", str(MAIN), "single-local", "600519"],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert market.returncode == 0
    assert market.stdout.strip() == "unset|market --as-of 2026-08-04"
    assert local_single.returncode == 0
    assert local_single.stdout.strip() == "0|single 600519"


def test_main_script_rejects_unknown_command() -> None:
    completed = subprocess.run(
        ["bash", str(MAIN), "unknown"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert completed.returncode == 2
    assert "未知命令" in completed.stderr


def test_main_script_requires_terminal_for_menu() -> None:
    completed = subprocess.run(
        ["bash", str(MAIN)],
        cwd=ROOT,
        input="q",
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert completed.returncode == 2
    assert "交互菜单需要在终端中运行" in completed.stderr


def test_main_menu_handles_macos_bash_arrow_sequence() -> None:
    expect = shutil.which("expect")
    if expect is None:
        return
    script = (
        'set timeout 5; spawn ./main.sh; '
        'expect "启动 Web 监控"; send "\\033\\[B"; '
        'expect -re {> 关闭 Web 监控}; send "q"; expect "已退出。"; expect eof'
    )
    completed = subprocess.run(
        [expect, "-c", script],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
