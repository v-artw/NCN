from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

import pandas as pd


SCRIPT = Path(__file__).parents[1] / "scripts/edge_scout_scan.sh"
CONFIG = Path(__file__).parents[1] / "yaml/edge_scout_v1.yaml"


def _base_env(tmp_path: Path) -> dict[str, str]:
    data_root = tmp_path / "data"
    data_root.mkdir()
    env = os.environ.copy()
    env.update({
        "VENV_PYTHON": sys.executable,
        "EDGE_SCOUT_DATA_ROOT": str(data_root),
        "EDGE_SCOUT_CONFIG": str(CONFIG),
        "EDGE_SCOUT_OUTPUT_ROOT": str(tmp_path / "output"),
        "EDGE_SCOUT_AUTO_UPDATE": "1",
    })
    return env


def test_current_data_skips_download_and_runs_scanner(tmp_path: Path) -> None:
    marker = tmp_path / "scanner-ran"
    env = _base_env(tmp_path)
    env["EDGE_SCOUT_UPDATE_CHECK_COMMAND"] = (
        "mkdir -p \"$(dirname \"$CHECK_SUMMARY\")\"; "
        "printf '%s\\n' '{\"status\":\"success\",\"action\":\"current\","
        "\"remote_latest_trade_date\":\"2026-07-31\"}' > \"$CHECK_SUMMARY\"; exit 0"
    )
    env["EDGE_SCOUT_DOWNLOADER_COMMAND"] = "exit 99"
    env["EDGE_SCOUT_SCANNER_COMMAND"] = f"touch {marker}"

    result = subprocess.run(["bash", str(SCRIPT), "market"], env=env, text=True, capture_output=True)

    assert result.returncode == 0, result.stderr
    assert marker.is_file()
    assert "本地数据已是最新，跳过下载" in result.stdout


def test_new_remote_date_downloads_before_scanner(tmp_path: Path) -> None:
    marker = tmp_path / "scanner-ran"
    env = _base_env(tmp_path)
    env["EDGE_SCOUT_UPDATE_CHECK_COMMAND"] = (
        "mkdir -p \"$(dirname \"$CHECK_SUMMARY\")\"; "
        "printf '%s\\n' '{\"status\":\"success\",\"action\":\"update_required\","
        "\"remote_latest_trade_date\":\"2026-07-31\"}' > \"$CHECK_SUMMARY\"; exit 10"
    )
    env["EDGE_SCOUT_DOWNLOADER_COMMAND"] = (
        f"{sys.executable} -c 'import json,os,pathlib,pandas as pd; "
        "root=pathlib.Path(os.environ[\"DATA_ROOT\"]); "
        "pd.DataFrame({\"date\":pd.to_datetime([os.environ[\"REMOTE_LATEST\"]])}).to_parquet(root/\"sh.600000.parquet\",index=False); "
        "path=pathlib.Path(os.environ[\"DOWNLOAD_SUMMARY\"]); path.parent.mkdir(parents=True,exist_ok=True); "
        "path.write_text(json.dumps({\"status\":\"success\",\"requested_end_date\":\"2026-07-31\",\"effective_end_date\":\"2026-07-31\"})+\"\\n\")'"
    )
    env["EDGE_SCOUT_SCANNER_COMMAND"] = f"touch {marker}"

    result = subprocess.run(["bash", str(SCRIPT), "market"], env=env, text=True, capture_output=True)

    assert result.returncode == 0, result.stderr
    assert marker.is_file()
    assert "发现远端新交易日 2026-07-31" in result.stdout
    assert "增量下载完成" in result.stdout


def test_non_trading_remote_date_uses_effective_download_date(tmp_path: Path) -> None:
    marker = tmp_path / "scanner-ran"
    env = _base_env(tmp_path)
    env["EDGE_SCOUT_UPDATE_CHECK_COMMAND"] = (
        "mkdir -p \"$(dirname \"$CHECK_SUMMARY\")\"; "
        "printf '%s\\n' '{\"status\":\"success\",\"action\":\"update_required\","
        "\"remote_latest_trade_date\":\"2026-08-04\"}' > \"$CHECK_SUMMARY\"; exit 10"
    )
    env["EDGE_SCOUT_DOWNLOADER_COMMAND"] = (
        f"{sys.executable} -c 'import json,os,pathlib,pandas as pd; "
        "root=pathlib.Path(os.environ[\"DATA_ROOT\"]); "
        "pd.DataFrame({\"date\":pd.to_datetime([\"2026-08-03\"])}).to_parquet(root/\"sh.600000.parquet\",index=False); "
        "path=pathlib.Path(os.environ[\"DOWNLOAD_SUMMARY\"]); path.parent.mkdir(parents=True,exist_ok=True); "
        "path.write_text(json.dumps({\"status\":\"success\",\"requested_end_date\":\"2026-08-04\",\"effective_end_date\":\"2026-08-03\"})+\"\\n\")'"
    )
    env["EDGE_SCOUT_SCANNER_COMMAND"] = f"touch {marker}"

    result = subprocess.run(["bash", str(SCRIPT), "market"], env=env, text=True, capture_output=True)

    assert result.returncode == 0, result.stderr
    assert marker.is_file()
    assert "有效交易日 2026-08-03" in result.stdout


def test_update_check_failure_blocks_scanner(tmp_path: Path) -> None:
    marker = tmp_path / "scanner-ran"
    env = _base_env(tmp_path)
    env["EDGE_SCOUT_UPDATE_CHECK_COMMAND"] = "exit 2"
    env["EDGE_SCOUT_SCANNER_COMMAND"] = f"touch {marker}"

    result = subprocess.run(["bash", str(SCRIPT), "market"], env=env, text=True, capture_output=True)

    assert result.returncode == 2
    assert not marker.exists()
    assert "无法确认 BaoStock 最新交易日" in result.stderr


def test_auto_update_is_incremental_and_never_clean() -> None:
    script = SCRIPT.read_text(encoding="utf-8")
    assert "--no-clean" in script
    assert "--clean " not in script
