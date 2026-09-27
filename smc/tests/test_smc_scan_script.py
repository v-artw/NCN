"""SMC hub（smc/scripts/smc_scan.sh）与入口（smc/smc.sh）的行为测试。

2026-09-27 自 tests/test_main_script.py 移植：select / daily / select-review /
post-smc-analysis 等流程随 SMC 分离迁入 smc/ 子项目自有 hub，断言保持不变，
仅目标脚本路径换为 smc_scan.sh（EDGE_SCOUT_* 环境变量在 hub 内继续作为回退生效）。
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

SMC_ROOT = Path(__file__).parents[1]
REPO_ROOT = SMC_ROOT.parent
SMC_SCAN = SMC_ROOT / "scripts" / "smc_scan.sh"


def _fake_python(tmp_path: Path, body: str) -> Path:
    fake_python = tmp_path / "fake_python.sh"
    fake_python.write_text(body, encoding="utf-8")
    fake_python.chmod(0o755)
    return fake_python


def _base_env(tmp_path: Path, fake_python: Path) -> dict[str, str]:
    data_root = tmp_path / "data"
    data_root.mkdir()
    config = tmp_path / "edge.yaml"
    config.write_text("schema_version: edge_scout_v1\n", encoding="utf-8")
    return {
        **os.environ,
        "VENV_PYTHON": str(fake_python),
        "EDGE_SCOUT_AUTO_UPDATE": "0",
        "EDGE_SCOUT_DATA_ROOT": str(data_root),
        "EDGE_SCOUT_CONFIG": str(config),
        "EDGE_SCOUT_OUTPUT_ROOT": str(tmp_path / "output"),
    }


def test_smc_scan_rejects_unknown_command() -> None:
    completed = subprocess.run(
        ["bash", str(SMC_SCAN), "definitely-not-an-smc-command"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert completed.returncode == 2
    assert "unknown smc_scan command" in completed.stderr


def test_smc_scan_post_smc_analysis_command_invokes_bound_cli(tmp_path: Path) -> None:
    fake_python = _fake_python(
        tmp_path,
        "#!/usr/bin/env bash\n"
        "script=\"$2\"\n"
        "case \"$script\" in\n"
        "  */analyze_post_smc_recommendation.py) printf 'analysis_args=%s\\n' \"$*\"; echo 'post_smc_analysis_csv=/tmp/analysis.csv' ;;\n"
        "  *) echo unknown:$script >&2; exit 7 ;;\n"
        "esac\n",
    )
    env = _base_env(tmp_path, fake_python)

    completed = subprocess.run(
        [
            "bash",
            str(SMC_SCAN),
            "post-smc-analysis",
            "--selection-run",
            "/tmp/select-bound",
            "--news-run",
            "/tmp/news-bound",
            "--top",
            "7",
        ],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "--selection-run /tmp/select-bound --top 7 --news-run /tmp/news-bound" in completed.stdout


def test_smc_scan_select_review_with_post_smc_analysis_binds_exact_artifacts(tmp_path: Path) -> None:
    fake_python = _fake_python(
        tmp_path,
        "#!/usr/bin/env bash\n"
        "script=\"$2\"\n"
        "case \"$script\" in\n"
        "  */select_stocks.py) echo 'status=success'; echo 'run_directory=/tmp/select-analysis' ;;\n"
        "  */review_smc_news.py) printf 'review_args=%s\\n' \"$*\"; echo 'run_directory=/tmp/news-analysis' ;;\n"
        "  */analyze_post_smc_recommendation.py) printf 'analysis_args=%s\\n' \"$*\"; echo 'post_smc_analysis_csv=/tmp/select-analysis/post_smc_recommendation_analysis.csv' ;;\n"
        "  */archive_smc_news_prospective.py) printf 'archive_args=%s\\n' \"$*\" ;;\n"
        "  *) echo unknown:$script >&2; exit 7 ;;\n"
        "esac\n",
    )
    env = _base_env(tmp_path, fake_python)
    news = tmp_path / "news.yaml"
    news.write_text("news: {}\n", encoding="utf-8")
    env["EDGE_SCOUT_NEWS_AI_CONFIG"] = str(news)

    completed = subprocess.run(
        ["bash", str(SMC_SCAN), "select-review", "--top", "5", "--post-smc-analysis"],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "--top 5 --selection-run /tmp/select-analysis" in completed.stdout
    assert "--selection-run /tmp/select-analysis --top 5 --news-run /tmp/news-analysis" in completed.stdout
    assert "post_smc_analysis_csv=/tmp/select-analysis/post_smc_recommendation_analysis.csv" in completed.stdout
    assert "--selection-run /tmp/select-analysis --news-run /tmp/news-analysis" in completed.stdout


def test_smc_scan_select_review_without_args_uses_yaml_default_top(tmp_path: Path) -> None:
    fake_python = _fake_python(
        tmp_path,
        "#!/usr/bin/env bash\n"
        "script=\"$2\"\n"
        "case \"$script\" in\n"
        "  */select_stocks.py) echo 'status=success'; echo 'run_directory=/tmp/select-default' ;;\n"
        "  */review_smc_news.py) printf 'review_args=%s\\n' \"$*\"; echo 'run_directory=/tmp/news-default' ;;\n"
        "  */archive_smc_news_prospective.py) printf 'archive_args=%s\\n' \"$*\" ;;\n"
        "  *) echo unknown:$script >&2; exit 7 ;;\n"
        "esac\n",
    )
    env = _base_env(tmp_path, fake_python)
    news = tmp_path / "news.yaml"
    news.write_text("review:\n  max_candidates: 9\nnews: {}\n", encoding="utf-8")
    env["EDGE_SCOUT_NEWS_AI_CONFIG"] = str(news)

    completed = subprocess.run(
        ["bash", str(SMC_SCAN), "select-review"],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "--top 9 --selection-run /tmp/select-default" in completed.stdout
    assert "--selection-run /tmp/select-default --news-run /tmp/news-default" in completed.stdout


def test_smc_scan_select_review_binds_exact_artifacts(tmp_path: Path) -> None:
    fake_python = _fake_python(
        tmp_path,
        "#!/usr/bin/env bash\n"
        "script=\"$2\"\n"
        "case \"$script\" in\n"
        "  */select_stocks.py) echo 'status=success'; echo 'run_directory=/tmp/select-exact' ;;\n"
        "  */review_smc_news.py) printf 'review_args=%s\\n' \"$*\"; echo 'run_directory=/tmp/news-exact' ;;\n"
        "  */archive_smc_news_prospective.py) printf 'archive_args=%s\\n' \"$*\" ;;\n"
        "  *) echo unknown:$script >&2; exit 7 ;;\n"
        "esac\n",
    )
    env = _base_env(tmp_path, fake_python)
    news = tmp_path / "news.yaml"
    news.write_text("news: {}\n", encoding="utf-8")
    env["EDGE_SCOUT_NEWS_AI_CONFIG"] = str(news)

    completed = subprocess.run(
        ["bash", str(SMC_SCAN), "select-review", "--top", "5"],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "--top 5 --selection-run /tmp/select-exact" in completed.stdout
    assert "--selection-run /tmp/select-exact --news-run /tmp/news-exact" in completed.stdout


def test_smc_scan_select_review_manual_as_of_skips_archive(tmp_path: Path) -> None:
    fake_python = _fake_python(
        tmp_path,
        "#!/usr/bin/env bash\n"
        "script=\"$2\"\n"
        "case \"$script\" in\n"
        "  */select_stocks.py) echo 'run_directory=/tmp/select-manual' ;;\n"
        "  */review_smc_news.py) printf 'review_args=%s\\n' \"$*\"; echo 'run_directory=/tmp/news-manual' ;;\n"
        "  */archive_smc_news_prospective.py) echo 'archive_called' ;;\n"
        "  *) echo unknown:$script >&2; exit 7 ;;\n"
        "esac\n",
    )
    env = _base_env(tmp_path, fake_python)
    news = tmp_path / "news.yaml"
    news.write_text("news: {}\n", encoding="utf-8")
    env["EDGE_SCOUT_NEWS_AI_CONFIG"] = str(news)

    completed = subprocess.run(
        ["bash", str(SMC_SCAN), "select-review", "--as-of", "2026-08-19", "--top", "3"],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "--top 3 --selection-run /tmp/select-manual" in completed.stdout
    assert "archive_called" not in completed.stdout
    assert "跳过手动 as-of" in completed.stdout


def test_smc_scan_daily_rejects_manual_as_of(tmp_path: Path) -> None:
    fake_python = _fake_python(tmp_path, "#!/usr/bin/env bash\necho should_not_run >&2; exit 7\n")
    env = _base_env(tmp_path, fake_python)

    completed = subprocess.run(
        ["bash", str(SMC_SCAN), "daily", "--as-of", "2026-08-20"],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert completed.returncode == 2
    assert "daily 仅支持自动日期" in completed.stderr
    assert "should_not_run" not in completed.stderr


def test_smc_scan_daily_runs_new_signal_full_chain(tmp_path: Path) -> None:
    fake_python = _fake_python(
        tmp_path,
        "#!/usr/bin/env bash\n"
        "script=\"$2\"\n"
        "case \"$script\" in\n"
        "  */select_stocks.py) echo 'status=success'; echo 'signal_date=2026-08-21'; echo 'candidate_count=2'; echo 'run_directory=/tmp/select-daily'; echo 'timestamped_csv=/tmp/select.csv'; echo 'human_review_summary_csv=/tmp/select-daily/human_review_summary.csv' ;;\n"
        "  */archive_smc_news_prospective.py)\n"
        "    joined=\"$*\"\n"
        "    if [[ \"$joined\" == *--check-existing-signal-date* ]]; then echo 'archive_signal_date=2026-08-21'; echo 'archive_duplicate=0';\n"
        "    else printf 'archive_args=%s\\n' \"$*\"; echo 'smc_news_prospective_archive_status=created'; echo 'archive_signal_date=2026-08-21'; echo 'smc_news_prospective_archive=/tmp/archive-daily'; fi ;;\n"
        "  */review_smc_news.py) printf 'review_args=%s\\n' \"$*\"; echo 'status=success'; echo 'priority_review_count=1'; echo 'risk_excluded_count=1'; echo 'run_directory=/tmp/news-daily'; echo 'timestamped_csv=/tmp/news.csv'; echo 'ai_committee_csv=/tmp/news-daily/ai_committee_reviews_20260821_120000.csv'; echo 'ai_committee_latest_csv=/tmp/news-daily/ai_committee_reviews_latest.csv'; echo 'human_review_summary_csv=/tmp/select-daily/human_review_summary.csv' ;;\n"
        "  */audit_smc_news_prospective.py) echo 'canonical_smc_news_snapshots=3'; echo 'mature_all_smc=0'; echo 'parent_maturity_sufficient=False'; echo 'promotion_evidence_sufficient=False'; echo 'evidence_sufficient=False'; echo 'output=/tmp/audit.json' ;;\n"
        "  *) echo unknown:$script >&2; exit 7 ;;\n"
        "esac\n",
    )
    env = _base_env(tmp_path, fake_python)
    news = tmp_path / "news.yaml"
    news.write_text("news: {}\n", encoding="utf-8")
    env["EDGE_SCOUT_NEWS_AI_CONFIG"] = str(news)

    completed = subprocess.run(
        ["bash", str(SMC_SCAN), "daily", "--top", "7"],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "--top 7 --selection-run /tmp/select-daily" in completed.stdout
    assert "--selection-run /tmp/select-daily --news-run /tmp/news-daily" in completed.stdout
    assert "signal_date=2026-08-21" in completed.stdout
    assert "selection_candidates=2" in completed.stdout
    assert "priority_review_count=1" in completed.stdout
    assert "archive_status=created" in completed.stdout
    assert "evidence_sufficient=False" in completed.stdout
    assert "ai_committee_csv=/tmp/news-daily/ai_committee_reviews_20260821_120000.csv" in completed.stdout
    assert "ai_committee_latest_csv=/tmp/news-daily/ai_committee_reviews_latest.csv" in completed.stdout
    assert "human_review_summary_csv=/tmp/select-daily/human_review_summary.csv" in completed.stdout


def test_smc_scan_daily_without_top_uses_yaml_default_top(tmp_path: Path) -> None:
    fake_python = _fake_python(
        tmp_path,
        "#!/usr/bin/env bash\n"
        "script=\"$2\"\n"
        "case \"$script\" in\n"
        "  */select_stocks.py) printf 'select_args=%s\\n' \"$*\"; echo 'status=success'; echo 'signal_date=2026-08-21'; echo 'candidate_count=2'; echo 'run_directory=/tmp/select-daily-yaml'; echo 'timestamped_csv=/tmp/select.csv'; echo 'human_review_summary_csv=/tmp/select-daily-yaml/human_review_summary.csv' ;;\n"
        "  */archive_smc_news_prospective.py)\n"
        "    joined=\"$*\"\n"
        "    if [[ \"$joined\" == *--check-existing-signal-date* ]]; then echo 'archive_signal_date=2026-08-21'; echo 'archive_duplicate=0';\n"
        "    else echo 'smc_news_prospective_archive_status=created'; echo 'smc_news_prospective_archive=/tmp/archive-daily-yaml'; fi ;;\n"
        "  */review_smc_news.py) printf 'review_args=%s\\n' \"$*\"; echo 'status=success'; echo 'priority_review_count=1'; echo 'risk_excluded_count=0'; echo 'run_directory=/tmp/news-daily-yaml'; echo 'timestamped_csv=/tmp/news.csv'; echo 'ai_committee_csv=/tmp/news/ai.csv'; echo 'ai_committee_latest_csv=/tmp/news/latest.csv'; echo 'human_review_summary_csv=/tmp/select-daily-yaml/human_review_summary.csv' ;;\n"
        "  */audit_smc_news_prospective.py) echo 'canonical_smc_news_snapshots=3'; echo 'mature_all_smc=0'; echo 'parent_maturity_sufficient=False'; echo 'promotion_evidence_sufficient=False'; echo 'evidence_sufficient=False'; echo 'output=/tmp/audit.json' ;;\n"
        "  *) echo unknown:$script >&2; exit 7 ;;\n"
        "esac\n",
    )
    env = _base_env(tmp_path, fake_python)
    news = tmp_path / "news.yaml"
    news.write_text("review:\n  max_candidates: 8\nnews: {}\n", encoding="utf-8")
    env["EDGE_SCOUT_NEWS_AI_CONFIG"] = str(news)

    completed = subprocess.run(
        ["bash", str(SMC_SCAN), "daily"],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "--top 8" in next(line for line in completed.stdout.splitlines() if line.startswith("select_args="))
    review_line = next(line for line in completed.stdout.splitlines() if line.startswith("review_args="))
    assert "--selection-run /tmp/select-daily-yaml" in review_line
    assert "--top 8" in review_line


def test_smc_scan_daily_skips_duplicate_signal_archive(tmp_path: Path) -> None:
    fake_python = _fake_python(
        tmp_path,
        "#!/usr/bin/env bash\n"
        "script=\"$2\"\n"
        "case \"$script\" in\n"
        "  */select_stocks.py) echo 'status=success'; echo 'signal_date=2026-08-20'; echo 'candidate_count=14'; echo 'run_directory=/tmp/select-dup'; echo 'timestamped_csv=/tmp/select.csv'; echo 'human_review_summary_csv=/tmp/select-dup/human_review_summary.csv' ;;\n"
        "  */archive_smc_news_prospective.py) echo 'archive_signal_date=2026-08-20'; echo 'archive_duplicate=1'; echo 'existing_archive_run_id=smc-news-existing'; echo 'existing_archive=/tmp/archive-existing'; echo 'existing_news_run=/tmp/news-existing'; echo 'existing_ai_committee_csv=/tmp/news-existing/ai_committee_reviews_20260820_120000.csv'; echo 'existing_ai_committee_latest_csv=/tmp/news-existing/ai_committee_reviews_latest.csv' ;;\n"
        "  */review_smc_news.py) echo review_should_not_run >&2; exit 7 ;;\n"
        "  */audit_smc_news_prospective.py) echo 'canonical_smc_news_snapshots=2'; echo 'mature_all_smc=0'; echo 'parent_maturity_sufficient=False'; echo 'promotion_evidence_sufficient=False'; echo 'evidence_sufficient=False'; echo 'output=/tmp/audit.json' ;;\n"
        "  *) echo unknown:$script >&2; exit 7 ;;\n"
        "esac\n",
    )
    env = _base_env(tmp_path, fake_python)
    news = tmp_path / "news.yaml"
    news.write_text("news: {}\n", encoding="utf-8")
    env["EDGE_SCOUT_NEWS_AI_CONFIG"] = str(news)

    completed = subprocess.run(
        ["bash", str(SMC_SCAN), "daily"],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "review_should_not_run" not in completed.stderr
    assert "news_review=skipped_existing_prospective_archive" in completed.stdout
    assert "archive_status=skipped_existing_signal_date" in completed.stdout
    assert "news_run=/tmp/news-existing" in completed.stdout
    assert "ai_committee_csv=/tmp/news-existing/ai_committee_reviews_20260820_120000.csv" in completed.stdout
    assert "ai_committee_latest_csv=/tmp/news-existing/ai_committee_reviews_latest.csv" in completed.stdout
    assert "existing_archive=/tmp/archive-existing" in completed.stdout
    assert "human_review_summary_csv=/tmp/select-dup/human_review_summary.csv" in completed.stdout
    assert "canonical_smc_news_snapshots=2" in completed.stdout


def _fake_scan_hub(tmp_path: Path) -> Path:
    fake = tmp_path / "fake_smc_scan.sh"
    fake.write_text(
        "#!/usr/bin/env bash\nprintf '%s|%s\\n' \"${EDGE_SCOUT_AUTO_UPDATE:-unset}\" \"$*\"\n",
        encoding="utf-8",
    )
    fake.chmod(0o755)
    return fake


def test_smc_sh_menu_native_review_routes_to_smc_control(tmp_path: Path) -> None:
    expect = shutil.which("expect")
    if expect is None:
        return
    fake = _fake_scan_hub(tmp_path)
    script = (
        'set timeout 10; spawn env SMC_SCAN_SCRIPT=' + str(fake) + ' bash ' + str(SMC_ROOT / "smc.sh") + '; '
        'expect "NCN SMC 研究"; '
        'send "\\033\\[B"; '
        'expect "> SMC一键流程（自动更新/SMC原生新闻AI复核+前瞻归档）"; send "\\r"; '
        'expect "unset|select-review"; exit 0'
    )
    completed = subprocess.run(
        [expect, "-c", script],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_smc_sh_menu_local_select_option_routes_to_selector(tmp_path: Path) -> None:
    expect = shutil.which("expect")
    if expect is None:
        return
    fake = _fake_scan_hub(tmp_path)
    down = "\\033\\[B" * 3
    script = (
        'set timeout 10; spawn env SMC_SCAN_SCRIPT=' + str(fake) + ' bash ' + str(SMC_ROOT / "smc.sh") + '; '
        'expect "NCN SMC 研究"; '
        f'send "{down}"; '
        'expect -re {> SMC选股（仅本地数据）}; send "\\r"; expect "0|select"; '
        'expect "按回车返回 SMC 菜单"; send "\\r"; expect "NCN SMC 研究"; '
        'send "q"; expect "已退出。"; expect eof'
    )
    completed = subprocess.run(
        [expect, "-c", script],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
