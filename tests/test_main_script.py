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
    assert "./main.sh mkf-review" in completed.stdout
    assert "./main.sh mkf-small" in completed.stdout
    assert "ADV20 降为 5000 万" in completed.stdout
    assert "./main.sh select-mkf" in completed.stdout
    assert "./main.sh select-mkf-local" in completed.stdout
    assert "./main.sh review-mkf-ai" in completed.stdout
    assert "./main.sh select-a-class" in completed.stdout
    assert "./main.sh select-a-class-local" in completed.stdout
    assert "./main.sh single 600519" in completed.stdout
    assert "./main.sh update" in completed.stdout
    assert "方向键交互菜单" in completed.stdout
    # 2026-09-28 SMC 归档：主仓 help 只保留归档去向指引，不再暴露 SMC 命令入口。
    assert "归档移出本仓" in completed.stdout
    assert "./smc/smc.sh" not in completed.stdout
    assert "./main.sh daily" not in completed.stdout
    assert "./main.sh select-review" not in completed.stdout
    assert "./main.sh review-news" not in completed.stdout
    assert "./main.sh archive-smc-news" not in completed.stdout
    assert "./main.sh audit-smc-news" not in completed.stdout
    assert "./main.sh replay-smc-news" not in completed.stdout


def test_mkf_script_help_lists_web_ai_export_command() -> None:
    completed = subprocess.run(
        ["bash", str(ROOT / "mkf.sh"), "help"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert completed.returncode == 0
    assert "交互菜单功能" in completed.stdout
    assert "MKF候选CSV导出Web AI Markdown" in completed.stdout
    assert "默认高亮最新 MKF CSV" in completed.stdout
    assert "4000 bytes 以内 Markdown" in completed.stdout
    assert "./mkf.sh export-mkf-web-ai" not in completed.stdout



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
    a_class = subprocess.run(
        ["bash", str(MAIN), "select-a-class", "--as-of", "2026-08-11"],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=10,
    )
    local_a_class = subprocess.run(
        ["bash", str(MAIN), "select-a-class-local"],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=10,
    )
    mkf_review = subprocess.run(
        ["bash", str(MAIN), "mkf-review", "--top", "6"],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=10,
    )
    mkf_small = subprocess.run(
        ["bash", str(MAIN), "mkf-small", "--top", "6"],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=10,
    )
    mkf = subprocess.run(
        ["bash", str(MAIN), "select-mkf", "--as-of", "2026-08-11"],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=10,
    )
    local_mkf = subprocess.run(
        ["bash", str(MAIN), "select-mkf-local"],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=10,
    )
    review_mkf_ai = subprocess.run(
        ["bash", str(MAIN), "review-mkf-ai", "--selection-run", "/tmp/mkf", "--top", "4"],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=10,
    )
    export_mkf_web_ai = subprocess.run(
        ["bash", str(ROOT / "mkf.sh"), "export-mkf-web-ai", "--latest", "--top", "3"],
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
    assert a_class.returncode == 0
    assert a_class.stdout.strip() == "unset|select-a-class --as-of 2026-08-11"
    assert local_a_class.returncode == 0
    assert local_a_class.stdout.strip() == "0|select-a-class"
    assert mkf_review.returncode == 0
    assert mkf_review.stdout.strip() == "unset|mkf-review --top 6"
    assert mkf_small.returncode == 0
    assert mkf_small.stdout.strip() == "unset|mkf-review-small --top 6"
    assert mkf.returncode == 0
    assert mkf.stdout.strip() == "unset|select-mkf --as-of 2026-08-11"
    assert local_mkf.returncode == 0
    assert local_mkf.stdout.strip() == "0|select-mkf"
    assert review_mkf_ai.returncode == 0
    assert review_mkf_ai.stdout.strip() == "unset|review-mkf-ai --selection-run /tmp/mkf --top 4"
    assert export_mkf_web_ai.returncode == 0
    assert export_mkf_web_ai.stdout.strip() == "unset|export-mkf-web-ai --latest --top 3"


def test_main_script_rejects_separated_smc_aliases(tmp_path: Path) -> None:
    fake = tmp_path / "fake_scan.sh"
    fake.write_text("#!/usr/bin/env bash\nprintf 'should_not_run|%s\\n' \"$*\"\n", encoding="utf-8")
    fake.chmod(0o755)
    environment = {**os.environ, "EDGE_SCOUT_SCAN_SCRIPT": str(fake)}

    for alias in ("select", "daily", "select-review", "review-news", "post-smc-analysis", "select-local"):
        completed = subprocess.run(
            ["bash", str(MAIN), alias],
            cwd=ROOT,
            env=environment,
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert completed.returncode == 2, alias
        assert "未知命令" in completed.stderr, alias
        assert "should_not_run" not in completed.stdout, alias


def test_edge_scout_mkf_commands_invoke_bound_clis(tmp_path: Path) -> None:
    fake_python = tmp_path / "fake_python.sh"
    fake_python.write_text(
        "#!/usr/bin/env bash\n"
        "script=\"$2\"\n"
        "case \"$script\" in\n"
        "  */select_mkf_candidates.py) printf 'mkf_args=%s\\n' \"$*\"; echo 'signal_date=2026-08-21'; echo 'candidate_count=1'; echo 'run_directory=/tmp/mkf-select'; echo 'timestamped_csv=/tmp/mkf-select/mkf.csv' ;;\n"
        "  */review_mkf_ai.py) printf 'mkf_ai_args=%s\\n' \"$*\"; echo 'priority_research_count=1'; echo 'risk_attention_count=0'; echo 'run_directory=/tmp/mkf-ai'; echo 'timestamped_csv=/tmp/mkf-ai/mkf-ai.csv'; echo 'news_contexts=/tmp/mkf-ai/news_contexts.json'; echo 'news_cache_dir=/tmp/Message'; echo 'news_cache_status_counts=refreshed:1' ;;\n"
        "  */export_scan_csv_for_web_ai.py) printf 'web_ai_export_args=%s\\n' \"$*\"; echo 'web_ai_prompt_md=/tmp/mkf.md'; echo 'candidate_rows=1'; echo 'research_only=true' ;;\n"
        "  *) echo unknown:$script >&2; exit 7 ;;\n"
        "esac\n",
        encoding="utf-8",
    )
    fake_python.chmod(0o755)
    data_root = tmp_path / "data"
    data_root.mkdir()
    config = tmp_path / "edge.yaml"
    config.write_text("schema_version: edge_scout_v1\n", encoding="utf-8")
    mkf_ai = tmp_path / "mkf_ai.yaml"
    mkf_ai.write_text("review:\n  max_candidates: 4\nai: {enabled: false}\n", encoding="utf-8")
    env = {
        **os.environ,
        "VENV_PYTHON": str(fake_python),
        "EDGE_SCOUT_AUTO_UPDATE": "0",
        "EDGE_SCOUT_DATA_ROOT": str(data_root),
        "EDGE_SCOUT_CONFIG": str(config),
        "EDGE_SCOUT_MKF_AI_CONFIG": str(mkf_ai),
        "EDGE_SCOUT_OUTPUT_ROOT": str(tmp_path / "output"),
    }

    selected = subprocess.run(
        ["bash", str(ROOT / "scripts/edge_scout_scan.sh"), "select-mkf", "--as-of", "2026-08-21", "--top", "6"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )
    reviewed = subprocess.run(
        ["bash", str(ROOT / "scripts/edge_scout_scan.sh"), "review-mkf-ai", "--selection-run", "/tmp/mkf-select", "--top", "3"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )
    small_reviewed = subprocess.run(
        ["bash", str(ROOT / "scripts/edge_scout_scan.sh"), "mkf-review-small", "--as-of", "2026-08-21", "--top", "3"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )
    default_reviewed = subprocess.run(
        ["bash", str(ROOT / "scripts/edge_scout_scan.sh"), "mkf-review"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )
    exported = subprocess.run(
        ["bash", str(ROOT / "scripts/edge_scout_scan.sh"), "export-mkf-web-ai", "--latest", "--top", "3"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )
    exported_select = subprocess.run(
        ["bash", str(ROOT / "scripts/edge_scout_scan.sh"), "export-mkf-web-ai", "--select"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert selected.returncode == 0, selected.stdout + selected.stderr
    assert "--output-root " + str(tmp_path / "output" / "mkf_candidate_selections") in selected.stdout
    assert "--as-of 2026-08-21" in selected.stdout
    assert reviewed.returncode == 0, reviewed.stdout + reviewed.stderr
    assert "--selection-root " + str(tmp_path / "output" / "mkf_candidate_selections") in reviewed.stdout
    assert "--output-root " + str(tmp_path / "output" / "mkf_ai_reviews") in reviewed.stdout
    assert "--selection-run /tmp/mkf-select" in reviewed.stdout
    assert small_reviewed.returncode == 0, small_reviewed.stdout + small_reviewed.stderr
    assert "--selection-profile small_capital" in small_reviewed.stdout
    assert "--min-adv20-cny 50000000" in small_reviewed.stdout
    assert "--as-of 2026-08-21" in small_reviewed.stdout
    assert "--top 3" in small_reviewed.stdout
    assert "--selection-run /tmp/mkf-select" in small_reviewed.stdout
    assert default_reviewed.returncode == 0, default_reviewed.stdout + default_reviewed.stderr
    assert "--top 4 --selection-profile standard" in default_reviewed.stdout
    default_ai_line = next(line for line in default_reviewed.stdout.splitlines() if line.startswith("mkf_ai_args="))
    assert "--selection-run /tmp/mkf-select" in default_ai_line
    assert "--top 4" in default_ai_line
    ai_line = next(line for line in small_reviewed.stdout.splitlines() if line.startswith("mkf_ai_args="))
    assert "--selection-profile" not in ai_line
    assert "--min-adv20-cny" not in ai_line
    assert "selection_profile=small_capital" in small_reviewed.stdout
    assert "effective_min_adv20_cny=50000000" in small_reviewed.stdout
    assert "mkf_ai_review=completed" in small_reviewed.stdout
    assert "mkf_news_context=enabled" in small_reviewed.stdout
    assert "mkf_news_contexts=/tmp/mkf-ai/news_contexts.json" in small_reviewed.stdout
    assert "mkf_news_cache_dir=/tmp/Message" in small_reviewed.stdout
    assert "boundary=MKF候选源和AI分层均为独立只读研究实验" in small_reviewed.stdout
    assert exported.returncode == 0, exported.stdout + exported.stderr
    assert "--mkf-selection-root " + str(tmp_path / "output" / "mkf_candidate_selections") in exported.stdout
    assert "--output-root " + str(tmp_path / "output" / "mdfile") in exported.stdout
    assert "--latest" in exported.stdout
    assert "--top 3" in exported.stdout
    assert "boundary=MKF CSV Web AI Markdown 导出仅转换只读研究文件" in exported.stdout
    assert exported_select.returncode == 0, exported_select.stdout + exported_select.stderr
    assert "--mkf-selection-root " + str(tmp_path / "output" / "mkf_candidate_selections") in exported_select.stdout
    assert "--output-root " + str(tmp_path / "output" / "mdfile") in exported_select.stdout
    assert "--select" in exported_select.stdout
    assert "--latest" not in exported_select.stdout


def test_mkf_review_small_streams_ai_output_before_summary(tmp_path: Path) -> None:
    fake_python = tmp_path / "fake_python.sh"
    fake_python.write_text(
        "#!/usr/bin/env bash\n"
        "script=\"$2\"\n"
        "case \"$script\" in\n"
        "  */select_mkf_candidates.py) echo 'signal_date=2026-08-21'; echo 'candidate_count=1'; echo 'run_directory=/tmp/mkf-select'; echo 'timestamped_csv=/tmp/mkf-select/mkf.csv' ;;\n"
        "  */review_mkf_ai.py) echo 'MKF AI复核进度：1/1 sh.600001 - 构建本地日K上下文'; echo 'status=success'; echo 'priority_research_count=1'; echo 'risk_attention_count=0'; echo 'run_directory=/tmp/mkf-ai'; echo 'timestamped_csv=/tmp/mkf-ai/mkf-ai.csv'; echo 'news_contexts=/tmp/mkf-ai/news_contexts.json'; echo 'news_cache_dir=/tmp/Message'; echo 'news_cache_status_counts=refreshed:1' ;;\n"
        "  *) echo unknown:$script >&2; exit 7 ;;\n"
        "esac\n",
        encoding="utf-8",
    )
    fake_python.chmod(0o755)
    data_root = tmp_path / "data"
    data_root.mkdir()
    config = tmp_path / "edge.yaml"
    config.write_text("schema_version: edge_scout_v1\n", encoding="utf-8")
    mkf_ai = tmp_path / "mkf_ai.yaml"
    mkf_ai.write_text("ai: {enabled: true}\n", encoding="utf-8")
    env = {
        **os.environ,
        "VENV_PYTHON": str(fake_python),
        "EDGE_SCOUT_AUTO_UPDATE": "0",
        "EDGE_SCOUT_DATA_ROOT": str(data_root),
        "EDGE_SCOUT_CONFIG": str(config),
        "EDGE_SCOUT_MKF_AI_CONFIG": str(mkf_ai),
        "EDGE_SCOUT_OUTPUT_ROOT": str(tmp_path / "output"),
    }

    completed = subprocess.run(
        ["bash", str(ROOT / "scripts/edge_scout_scan.sh"), "mkf-review-small", "--top", "3"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    progress_index = completed.stdout.index("MKF AI复核进度：1/1")
    summary_index = completed.stdout.index("MKF候选源一键流程摘要")
    assert progress_index < summary_index
    assert "mkf_ai_review=completed" in completed.stdout
    assert "mkf_news_contexts=/tmp/mkf-ai/news_contexts.json" in completed.stdout


def test_review_mkf_ai_excludes_unavailable_rows_from_scored_display(tmp_path: Path) -> None:
    fake_python = tmp_path / "fake_python.sh"
    fake_python.write_text(
        "#!/usr/bin/env bash\n"
        "script=\"$2\"\n"
        "case \"$script\" in\n"
        "  */review_mkf_ai.py) echo 'status=partial'; echo 'priority_research_count=1'; echo 'risk_attention_count=0'; echo 'run_directory=/tmp/mkf-ai'; echo 'timestamped_csv=/tmp/mkf-ai/mkf-ai.csv'; echo 'news_contexts=/tmp/mkf-ai/news_contexts.json'; echo 'news_cache_dir=/tmp/Message'; echo 'news_cache_status_counts=refreshed:1'; echo 'MKF AI 评分排序（仅展示AI有效评分；只读研究，未经胜率验证）'; echo ' 1. sh.600001  优先研究  置信度=0.80 本地分=7.00'; echo 'AI未评分清单（不参与上方AI排序）：sh.600002'; exit 3 ;;\n"
        "  *) echo unknown:$script >&2; exit 7 ;;\n"
        "esac\n",
        encoding="utf-8",
    )
    fake_python.chmod(0o755)
    data_root = tmp_path / "data"
    data_root.mkdir()
    mkf_ai = tmp_path / "mkf_ai.yaml"
    mkf_ai.write_text("ai: {enabled: true}\n", encoding="utf-8")
    env = {
        **os.environ,
        "VENV_PYTHON": str(fake_python),
        "EDGE_SCOUT_DATA_ROOT": str(data_root),
        "EDGE_SCOUT_MKF_AI_CONFIG": str(mkf_ai),
        "EDGE_SCOUT_OUTPUT_ROOT": str(tmp_path / "output"),
    }

    completed = subprocess.run(
        ["bash", str(ROOT / "scripts/edge_scout_scan.sh"), "review-mkf-ai", "--selection-run", "/tmp/mkf-select", "--top", "3"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert completed.returncode == 3
    scored_section = completed.stdout.split("AI未评分清单", 1)[0]
    assert "sh.600001" in scored_section
    assert "sh.600002" not in scored_section
    assert "AI未评分清单（不参与上方AI排序）：sh.600002" in completed.stdout


def test_mkf_review_small_keeps_partial_ai_artifact_summary(tmp_path: Path) -> None:
    fake_python = tmp_path / "fake_python.sh"
    fake_python.write_text(
        "#!/usr/bin/env bash\n"
        "script=\"$2\"\n"
        "case \"$script\" in\n"
        "  */select_mkf_candidates.py) echo 'signal_date=2026-08-21'; echo 'candidate_count=1'; echo 'run_directory=/tmp/mkf-select'; echo 'timestamped_csv=/tmp/mkf-select/mkf.csv' ;;\n"
        "  */review_mkf_ai.py) echo 'status=partial'; echo 'priority_research_count=0'; echo 'risk_attention_count=0'; echo 'run_directory=/tmp/mkf-ai'; echo 'timestamped_csv=/tmp/mkf-ai/mkf-ai.csv'; echo 'news_contexts=/tmp/mkf-ai/news_contexts.json'; echo 'news_cache_dir=/tmp/Message'; echo 'news_cache_status_counts=refreshed:1'; exit 3 ;;\n"
        "  *) echo unknown:$script >&2; exit 7 ;;\n"
        "esac\n",
        encoding="utf-8",
    )
    fake_python.chmod(0o755)
    data_root = tmp_path / "data"
    data_root.mkdir()
    config = tmp_path / "edge.yaml"
    config.write_text("schema_version: edge_scout_v1\n", encoding="utf-8")
    mkf_ai = tmp_path / "mkf_ai.yaml"
    mkf_ai.write_text("ai: {enabled: true}\n", encoding="utf-8")
    env = {
        **os.environ,
        "VENV_PYTHON": str(fake_python),
        "EDGE_SCOUT_AUTO_UPDATE": "0",
        "EDGE_SCOUT_DATA_ROOT": str(data_root),
        "EDGE_SCOUT_CONFIG": str(config),
        "EDGE_SCOUT_MKF_AI_CONFIG": str(mkf_ai),
        "EDGE_SCOUT_OUTPUT_ROOT": str(tmp_path / "output"),
    }

    completed = subprocess.run(
        ["bash", str(ROOT / "scripts/edge_scout_scan.sh"), "mkf-review-small", "--top", "3"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "status=partial" in completed.stdout
    assert "MKF候选源一键流程摘要" in completed.stdout
    assert "mkf_ai_review=partial" in completed.stdout
    assert "mkf_ai_run=/tmp/mkf-ai" in completed.stdout
    assert "mkf_ai_csv=/tmp/mkf-ai/mkf-ai.csv" in completed.stdout
    assert "mkf_news_contexts=/tmp/mkf-ai/news_contexts.json" in completed.stdout


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


def test_main_menu_mkf_entry_opens_independent_menu(tmp_path: Path) -> None:
    expect = shutil.which("expect")
    if expect is None:
        return
    fake = tmp_path / "fake_scan.sh"
    fake.write_text(
        "#!/usr/bin/env bash\nprintf '%s|%s\\n' \"${EDGE_SCOUT_AUTO_UPDATE:-unset}\" \"$*\"\n",
        encoding="utf-8",
    )
    fake.chmod(0o755)
    # SMC 菜单项分离后，主菜单可选项序列为 web-start…exit；MKF 研究入口需要 11 次下移。
    mkf_entry_down = "\\033\\[B" * 11
    script = (
        'set timeout 10; spawn env EDGE_SCOUT_SCAN_SCRIPT=' + str(fake) + ' ./main.sh; '
        'expect "启动 Web 监控"; '
        f'send "{mkf_entry_down}"; '
        'expect -re {> MKF 研究入口}; send "\r"; '
        'expect "NCN MKF 研究"; '
        'expect -re {> MKF一键流程}; send "\r"; '
        'expect "unset|mkf-review"; exit 0'
    )
    completed = subprocess.run(
        [expect, "-c", script],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_mkf_menu_options_route_to_scan_commands(tmp_path: Path) -> None:
    expect = shutil.which("expect")
    if expect is None:
        return
    fake = tmp_path / "fake_scan.sh"
    fake.write_text(
        "#!/usr/bin/env bash\nprintf '%s|%s\\n' \"${EDGE_SCOUT_AUTO_UPDATE:-unset}\" \"$*\"\n",
        encoding="utf-8",
    )
    fake.chmod(0o755)
    down = "\\033\\[B"
    script = (
        'set timeout 10; spawn env EDGE_SCOUT_SCAN_SCRIPT=' + str(fake) + ' ./mkf.sh; '
        'expect "NCN MKF 研究"; '
        'expect -re {> MKF一键流程}; send "\r"; '
        'expect "unset|mkf-review"; '
        'expect "按回车返回 MKF 菜单"; send "\r"; expect "NCN MKF 研究"; '
        f'send "{down}"; '
        'expect -re {> MKF小资金一键流程}; send "\r"; '
        'expect "unset|mkf-review-small"; '
        'expect "按回车返回 MKF 菜单"; send "\r"; expect "NCN MKF 研究"; '
        f'send "{down}"; '
        'expect -re {> MKF候选源实验（自动更新数据）}; send "\r"; '
        'expect "unset|select-mkf"; '
        'expect "按回车返回 MKF 菜单"; send "\r"; expect "NCN MKF 研究"; '
        f'send "{down}"; '
        'expect -re {> MKF候选源实验（仅本地数据）}; send "\r"; '
        'expect "0|select-mkf"; '
        'expect "按回车返回 MKF 菜单"; send "\r"; expect "NCN MKF 研究"; '
        f'send "{down}"; '
        'expect -re {> MKF候选源AI研究分层}; send "\r"; '
        'expect "unset|review-mkf-ai"; '
        'expect "按回车返回 MKF 菜单"; send "\r"; expect "NCN MKF 研究"; '
        f'send "{down}"; '
        'expect -re {> MKF候选CSV导出Web AI Markdown}; send "\r"; '
        'expect "unset|export-mkf-web-ai --select --max-bytes 4000"; exit 0'
    )
    completed = subprocess.run(
        [expect, "-c", script],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
