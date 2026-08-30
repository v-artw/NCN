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
    assert "./main.sh select" in completed.stdout
    assert "./main.sh daily [--top N]" in completed.stdout
    assert "AI委员会CSV" in completed.stdout
    assert "./main.sh select-review [--as-of DATE] [--top N] [--post-smc-analysis]" in completed.stdout
    assert "./main.sh post-smc-analysis --selection-run DIR" in completed.stdout
    assert "手动日期仅复核" in completed.stdout
    assert "./main.sh select-local" in completed.stdout
    assert "./main.sh review-news" in completed.stdout
    assert "./main.sh mkf-review" in completed.stdout
    assert "./main.sh mkf-small" in completed.stdout
    assert "ADV20 降为 5000 万" in completed.stdout
    assert "--top 仅限制终端展示" in completed.stdout
    assert "./main.sh select-mkf" in completed.stdout
    assert "./main.sh select-mkf-local" in completed.stdout
    assert "./main.sh review-mkf-ai" in completed.stdout
    assert "./main.sh archive-smc-news" in completed.stdout
    assert "./main.sh audit-smc-news" in completed.stdout
    assert "./main.sh replay-smc-news" in completed.stdout
    assert "./main.sh select-a-class" in completed.stdout
    assert "./main.sh select-a-class-local" in completed.stdout
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
    select = subprocess.run(
        ["bash", str(MAIN), "select", "--as-of", "2026-08-11"],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=10,
    )
    daily = subprocess.run(
        ["bash", str(MAIN), "daily", "--top", "5"],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=10,
    )
    select_review = subprocess.run(
        ["bash", str(MAIN), "select-review", "--top", "5"],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=10,
    )
    local_select = subprocess.run(
        ["bash", str(MAIN), "select-local"],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=10,
    )
    review_news = subprocess.run(
        ["bash", str(MAIN), "review-news", "--top", "5"],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=10,
    )
    post_smc_analysis = subprocess.run(
        ["bash", str(MAIN), "post-smc-analysis", "--selection-run", "/tmp/select", "--top", "5"],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=10,
    )
    archive_smc_news = subprocess.run(
        ["bash", str(MAIN), "archive-smc-news"],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=10,
    )
    audit_smc_news = subprocess.run(
        ["bash", str(MAIN), "audit-smc-news"],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=10,
    )
    replay_smc_news = subprocess.run(
        ["bash", str(MAIN), "replay-smc-news", "--dry-run"],
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

    assert market.returncode == 0
    assert market.stdout.strip() == "unset|market --as-of 2026-08-04"
    assert local_single.returncode == 0
    assert local_single.stdout.strip() == "0|single 600519"
    assert select.returncode == 0
    assert select.stdout.strip() == "unset|select --as-of 2026-08-11"
    assert daily.returncode == 0
    assert daily.stdout.strip() == "unset|daily --top 5"
    assert select_review.returncode == 0
    assert select_review.stdout.strip() == "unset|select-review --top 5"
    assert local_select.returncode == 0
    assert local_select.stdout.strip() == "0|select"
    assert review_news.returncode == 0
    assert review_news.stdout.strip() == "unset|review-news --top 5"
    assert post_smc_analysis.returncode == 0
    assert post_smc_analysis.stdout.strip() == "unset|post-smc-analysis --selection-run /tmp/select --top 5"
    assert archive_smc_news.returncode == 0
    assert archive_smc_news.stdout.strip() == "unset|archive-smc-news"
    assert audit_smc_news.returncode == 0
    assert audit_smc_news.stdout.strip() == "unset|audit-smc-news"
    assert replay_smc_news.returncode == 0
    assert replay_smc_news.stdout.strip() == "unset|replay-smc-news --dry-run"
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


def test_edge_scout_mkf_commands_invoke_bound_clis(tmp_path: Path) -> None:
    fake_python = tmp_path / "fake_python.sh"
    fake_python.write_text(
        "#!/usr/bin/env bash\n"
        "script=\"$2\"\n"
        "case \"$script\" in\n"
        "  */select_mkf_candidates.py) printf 'mkf_args=%s\\n' \"$*\"; echo 'signal_date=2026-08-21'; echo 'candidate_count=1'; echo 'run_directory=/tmp/mkf-select'; echo 'timestamped_csv=/tmp/mkf-select/mkf.csv' ;;\n"
        "  */review_mkf_ai.py) printf 'mkf_ai_args=%s\\n' \"$*\"; echo 'priority_research_count=1'; echo 'risk_attention_count=0'; echo 'run_directory=/tmp/mkf-ai'; echo 'timestamped_csv=/tmp/mkf-ai/mkf-ai.csv'; echo 'news_contexts=/tmp/mkf-ai/news_contexts.json'; echo 'news_cache_dir=/tmp/Message'; echo 'news_cache_status_counts=refreshed:1' ;;\n"
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


def test_edge_scout_post_smc_analysis_command_invokes_bound_cli(tmp_path: Path) -> None:
    fake_python = tmp_path / "fake_python.sh"
    fake_python.write_text(
        "#!/usr/bin/env bash\n"
        "script=\"$2\"\n"
        "case \"$script\" in\n"
        "  */analyze_post_smc_recommendation.py) printf 'analysis_args=%s\\n' \"$*\"; echo 'post_smc_analysis_csv=/tmp/analysis.csv' ;;\n"
        "  *) echo unknown:$script >&2; exit 7 ;;\n"
        "esac\n",
        encoding="utf-8",
    )
    fake_python.chmod(0o755)
    data_root = tmp_path / "data"
    data_root.mkdir()
    config = tmp_path / "edge.yaml"
    config.write_text("schema_version: edge_scout_v1\n", encoding="utf-8")
    env = {
        **os.environ,
        "VENV_PYTHON": str(fake_python),
        "EDGE_SCOUT_AUTO_UPDATE": "0",
        "EDGE_SCOUT_DATA_ROOT": str(data_root),
        "EDGE_SCOUT_CONFIG": str(config),
        "EDGE_SCOUT_OUTPUT_ROOT": str(tmp_path / "output"),
    }

    completed = subprocess.run(
        [
            "bash",
            str(ROOT / "scripts/edge_scout_scan.sh"),
            "post-smc-analysis",
            "--selection-run",
            "/tmp/select-bound",
            "--news-run",
            "/tmp/news-bound",
            "--top",
            "7",
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "--selection-run /tmp/select-bound --top 7 --news-run /tmp/news-bound" in completed.stdout


def test_edge_scout_select_review_with_post_smc_analysis_binds_exact_artifacts(tmp_path: Path) -> None:
    fake_python = tmp_path / "fake_python.sh"
    fake_python.write_text(
        "#!/usr/bin/env bash\n"
        "script=\"$2\"\n"
        "case \"$script\" in\n"
        "  */select_stocks.py) echo 'status=success'; echo 'run_directory=/tmp/select-analysis' ;;\n"
        "  */review_smc_news.py) printf 'review_args=%s\\n' \"$*\"; echo 'run_directory=/tmp/news-analysis' ;;\n"
        "  */analyze_post_smc_recommendation.py) printf 'analysis_args=%s\\n' \"$*\"; echo 'post_smc_analysis_csv=/tmp/select-analysis/post_smc_recommendation_analysis.csv' ;;\n"
        "  */archive_smc_news_prospective.py) printf 'archive_args=%s\\n' \"$*\" ;;\n"
        "  *) echo unknown:$script >&2; exit 7 ;;\n"
        "esac\n",
        encoding="utf-8",
    )
    fake_python.chmod(0o755)
    data_root = tmp_path / "data"
    data_root.mkdir()
    config = tmp_path / "edge.yaml"
    config.write_text("schema_version: edge_scout_v1\n", encoding="utf-8")
    news = tmp_path / "news.yaml"
    news.write_text("news: {}\n", encoding="utf-8")
    env = {
        **os.environ,
        "VENV_PYTHON": str(fake_python),
        "EDGE_SCOUT_AUTO_UPDATE": "0",
        "EDGE_SCOUT_DATA_ROOT": str(data_root),
        "EDGE_SCOUT_CONFIG": str(config),
        "EDGE_SCOUT_NEWS_AI_CONFIG": str(news),
        "EDGE_SCOUT_OUTPUT_ROOT": str(tmp_path / "output"),
    }

    completed = subprocess.run(
        ["bash", str(ROOT / "scripts/edge_scout_scan.sh"), "select-review", "--top", "5", "--post-smc-analysis"],
        cwd=ROOT,
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


def test_edge_scout_select_review_without_args_uses_yaml_default_top(tmp_path: Path) -> None:
    fake_python = tmp_path / "fake_python.sh"
    fake_python.write_text(
        "#!/usr/bin/env bash\n"
        "script=\"$2\"\n"
        "case \"$script\" in\n"
        "  */select_stocks.py) echo 'status=success'; echo 'run_directory=/tmp/select-default' ;;\n"
        "  */review_smc_news.py) printf 'review_args=%s\\n' \"$*\"; echo 'run_directory=/tmp/news-default' ;;\n"
        "  */archive_smc_news_prospective.py) printf 'archive_args=%s\\n' \"$*\" ;;\n"
        "  *) echo unknown:$script >&2; exit 7 ;;\n"
        "esac\n",
        encoding="utf-8",
    )
    fake_python.chmod(0o755)
    data_root = tmp_path / "data"
    data_root.mkdir()
    config = tmp_path / "edge.yaml"
    config.write_text("schema_version: edge_scout_v1\n", encoding="utf-8")
    news = tmp_path / "news.yaml"
    news.write_text("review:\n  max_candidates: 9\nnews: {}\n", encoding="utf-8")
    env = {
        **os.environ,
        "VENV_PYTHON": str(fake_python),
        "EDGE_SCOUT_AUTO_UPDATE": "0",
        "EDGE_SCOUT_DATA_ROOT": str(data_root),
        "EDGE_SCOUT_CONFIG": str(config),
        "EDGE_SCOUT_NEWS_AI_CONFIG": str(news),
        "EDGE_SCOUT_OUTPUT_ROOT": str(tmp_path / "output"),
    }

    completed = subprocess.run(
        ["bash", str(ROOT / "scripts/edge_scout_scan.sh"), "select-review"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "--top 9 --selection-run /tmp/select-default" in completed.stdout
    assert "--selection-run /tmp/select-default --news-run /tmp/news-default" in completed.stdout


def test_edge_scout_select_review_binds_exact_artifacts(tmp_path: Path) -> None:
    fake_python = tmp_path / "fake_python.sh"
    fake_python.write_text(
        "#!/usr/bin/env bash\n"
        "script=\"$2\"\n"
        "case \"$script\" in\n"
        "  */select_stocks.py) echo 'status=success'; echo 'run_directory=/tmp/select-exact' ;;\n"
        "  */review_smc_news.py) printf 'review_args=%s\\n' \"$*\"; echo 'run_directory=/tmp/news-exact' ;;\n"
        "  */archive_smc_news_prospective.py) printf 'archive_args=%s\\n' \"$*\" ;;\n"
        "  *) echo unknown:$script >&2; exit 7 ;;\n"
        "esac\n",
        encoding="utf-8",
    )
    fake_python.chmod(0o755)
    data_root = tmp_path / "data"
    data_root.mkdir()
    config = tmp_path / "edge.yaml"
    config.write_text("schema_version: edge_scout_v1\n", encoding="utf-8")
    news = tmp_path / "news.yaml"
    news.write_text("news: {}\n", encoding="utf-8")
    env = {
        **os.environ,
        "VENV_PYTHON": str(fake_python),
        "EDGE_SCOUT_AUTO_UPDATE": "0",
        "EDGE_SCOUT_DATA_ROOT": str(data_root),
        "EDGE_SCOUT_CONFIG": str(config),
        "EDGE_SCOUT_NEWS_AI_CONFIG": str(news),
        "EDGE_SCOUT_OUTPUT_ROOT": str(tmp_path / "output"),
    }

    completed = subprocess.run(
        ["bash", str(ROOT / "scripts/edge_scout_scan.sh"), "select-review", "--top", "5"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "--top 5 --selection-run /tmp/select-exact" in completed.stdout
    assert "--selection-run /tmp/select-exact --news-run /tmp/news-exact" in completed.stdout


def test_edge_scout_select_review_manual_as_of_skips_archive(tmp_path: Path) -> None:
    fake_python = tmp_path / "fake_python.sh"
    fake_python.write_text(
        "#!/usr/bin/env bash\n"
        "script=\"$2\"\n"
        "case \"$script\" in\n"
        "  */select_stocks.py) echo 'run_directory=/tmp/select-manual' ;;\n"
        "  */review_smc_news.py) printf 'review_args=%s\\n' \"$*\"; echo 'run_directory=/tmp/news-manual' ;;\n"
        "  */archive_smc_news_prospective.py) echo 'archive_called' ;;\n"
        "  *) echo unknown:$script >&2; exit 7 ;;\n"
        "esac\n",
        encoding="utf-8",
    )
    fake_python.chmod(0o755)
    data_root = tmp_path / "data"
    data_root.mkdir()
    config = tmp_path / "edge.yaml"
    config.write_text("schema_version: edge_scout_v1\n", encoding="utf-8")
    news = tmp_path / "news.yaml"
    news.write_text("news: {}\n", encoding="utf-8")
    env = {
        **os.environ,
        "VENV_PYTHON": str(fake_python),
        "EDGE_SCOUT_AUTO_UPDATE": "0",
        "EDGE_SCOUT_DATA_ROOT": str(data_root),
        "EDGE_SCOUT_CONFIG": str(config),
        "EDGE_SCOUT_NEWS_AI_CONFIG": str(news),
        "EDGE_SCOUT_OUTPUT_ROOT": str(tmp_path / "output"),
    }

    completed = subprocess.run(
        ["bash", str(ROOT / "scripts/edge_scout_scan.sh"), "select-review", "--as-of", "2026-08-19", "--top", "3"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "--top 3 --selection-run /tmp/select-manual" in completed.stdout
    assert "archive_called" not in completed.stdout
    assert "跳过手动 as-of" in completed.stdout


def test_edge_scout_daily_rejects_manual_as_of(tmp_path: Path) -> None:
    fake_python = tmp_path / "fake_python.sh"
    fake_python.write_text("#!/usr/bin/env bash\necho should_not_run >&2; exit 7\n", encoding="utf-8")
    fake_python.chmod(0o755)
    data_root = tmp_path / "data"
    data_root.mkdir()
    config = tmp_path / "edge.yaml"
    config.write_text("schema_version: edge_scout_v1\n", encoding="utf-8")
    env = {
        **os.environ,
        "VENV_PYTHON": str(fake_python),
        "EDGE_SCOUT_AUTO_UPDATE": "0",
        "EDGE_SCOUT_DATA_ROOT": str(data_root),
        "EDGE_SCOUT_CONFIG": str(config),
        "EDGE_SCOUT_OUTPUT_ROOT": str(tmp_path / "output"),
    }

    completed = subprocess.run(
        ["bash", str(ROOT / "scripts/edge_scout_scan.sh"), "daily", "--as-of", "2026-08-20"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert completed.returncode == 2
    assert "daily 仅支持自动日期" in completed.stderr
    assert "should_not_run" not in completed.stderr


def test_edge_scout_daily_runs_new_signal_full_chain(tmp_path: Path) -> None:
    fake_python = tmp_path / "fake_python.sh"
    fake_python.write_text(
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
        encoding="utf-8",
    )
    fake_python.chmod(0o755)
    data_root = tmp_path / "data"
    data_root.mkdir()
    config = tmp_path / "edge.yaml"
    config.write_text("schema_version: edge_scout_v1\n", encoding="utf-8")
    news = tmp_path / "news.yaml"
    news.write_text("news: {}\n", encoding="utf-8")
    env = {
        **os.environ,
        "VENV_PYTHON": str(fake_python),
        "EDGE_SCOUT_AUTO_UPDATE": "0",
        "EDGE_SCOUT_DATA_ROOT": str(data_root),
        "EDGE_SCOUT_CONFIG": str(config),
        "EDGE_SCOUT_NEWS_AI_CONFIG": str(news),
        "EDGE_SCOUT_OUTPUT_ROOT": str(tmp_path / "output"),
    }

    completed = subprocess.run(
        ["bash", str(ROOT / "scripts/edge_scout_scan.sh"), "daily", "--top", "7"],
        cwd=ROOT,
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


def test_edge_scout_daily_without_top_uses_yaml_default_top(tmp_path: Path) -> None:
    fake_python = tmp_path / "fake_python.sh"
    fake_python.write_text(
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
        encoding="utf-8",
    )
    fake_python.chmod(0o755)
    data_root = tmp_path / "data"
    data_root.mkdir()
    config = tmp_path / "edge.yaml"
    config.write_text("schema_version: edge_scout_v1\n", encoding="utf-8")
    news = tmp_path / "news.yaml"
    news.write_text("review:\n  max_candidates: 8\nnews: {}\n", encoding="utf-8")
    env = {
        **os.environ,
        "VENV_PYTHON": str(fake_python),
        "EDGE_SCOUT_AUTO_UPDATE": "0",
        "EDGE_SCOUT_DATA_ROOT": str(data_root),
        "EDGE_SCOUT_CONFIG": str(config),
        "EDGE_SCOUT_NEWS_AI_CONFIG": str(news),
        "EDGE_SCOUT_OUTPUT_ROOT": str(tmp_path / "output"),
    }

    completed = subprocess.run(
        ["bash", str(ROOT / "scripts/edge_scout_scan.sh"), "daily"],
        cwd=ROOT,
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


def test_edge_scout_daily_skips_duplicate_signal_archive(tmp_path: Path) -> None:
    fake_python = tmp_path / "fake_python.sh"
    fake_python.write_text(
        "#!/usr/bin/env bash\n"
        "script=\"$2\"\n"
        "case \"$script\" in\n"
        "  */select_stocks.py) echo 'status=success'; echo 'signal_date=2026-08-20'; echo 'candidate_count=14'; echo 'run_directory=/tmp/select-dup'; echo 'timestamped_csv=/tmp/select.csv'; echo 'human_review_summary_csv=/tmp/select-dup/human_review_summary.csv' ;;\n"
        "  */archive_smc_news_prospective.py) echo 'archive_signal_date=2026-08-20'; echo 'archive_duplicate=1'; echo 'existing_archive_run_id=smc-news-existing'; echo 'existing_archive=/tmp/archive-existing'; echo 'existing_news_run=/tmp/news-existing'; echo 'existing_ai_committee_csv=/tmp/news-existing/ai_committee_reviews_20260820_120000.csv'; echo 'existing_ai_committee_latest_csv=/tmp/news-existing/ai_committee_reviews_latest.csv' ;;\n"
        "  */review_smc_news.py) echo review_should_not_run >&2; exit 7 ;;\n"
        "  */audit_smc_news_prospective.py) echo 'canonical_smc_news_snapshots=2'; echo 'mature_all_smc=0'; echo 'parent_maturity_sufficient=False'; echo 'promotion_evidence_sufficient=False'; echo 'evidence_sufficient=False'; echo 'output=/tmp/audit.json' ;;\n"
        "  *) echo unknown:$script >&2; exit 7 ;;\n"
        "esac\n",
        encoding="utf-8",
    )
    fake_python.chmod(0o755)
    data_root = tmp_path / "data"
    data_root.mkdir()
    config = tmp_path / "edge.yaml"
    config.write_text("schema_version: edge_scout_v1\n", encoding="utf-8")
    news = tmp_path / "news.yaml"
    news.write_text("news: {}\n", encoding="utf-8")
    env = {
        **os.environ,
        "VENV_PYTHON": str(fake_python),
        "EDGE_SCOUT_AUTO_UPDATE": "0",
        "EDGE_SCOUT_DATA_ROOT": str(data_root),
        "EDGE_SCOUT_CONFIG": str(config),
        "EDGE_SCOUT_NEWS_AI_CONFIG": str(news),
        "EDGE_SCOUT_OUTPUT_ROOT": str(tmp_path / "output"),
    }

    completed = subprocess.run(
        ["bash", str(ROOT / "scripts/edge_scout_scan.sh"), "daily"],
        cwd=ROOT,
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


def test_main_menu_daily_option_routes_to_one_key_flow(tmp_path: Path) -> None:
    expect = shutil.which("expect")
    if expect is None:
        return
    fake = tmp_path / "fake_scan.sh"
    fake.write_text(
        "#!/usr/bin/env bash\nprintf '%s|%s\\n' \"${EDGE_SCOUT_AUTO_UPDATE:-unset}\" \"$*\"\n",
        encoding="utf-8",
    )
    fake.chmod(0o755)
    down = "\\033\\[B" * 9
    script = (
        'set timeout 10; spawn env EDGE_SCOUT_SCAN_SCRIPT=' + str(fake) + ' ./main.sh; '
        'expect "启动 Web 监控"; '
        f'send "{down}"; '
        'expect -re {> 每日 SMC\\+新闻一键流程}; send "\\r"; '
        'expect "unset|daily"; exit 0'
    )
    completed = subprocess.run(
        [expect, "-c", script],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_main_menu_local_smc_option_routes_to_selector(tmp_path: Path) -> None:
    expect = shutil.which("expect")
    if expect is None:
        return
    fake = tmp_path / "fake_scan.sh"
    fake.write_text(
        "#!/usr/bin/env bash\nprintf '%s|%s\\n' \"${EDGE_SCOUT_AUTO_UPDATE:-unset}\" \"$*\"\n",
        encoding="utf-8",
    )
    fake.chmod(0o755)
    down = "\\033\\[B" * 11
    script = (
        'set timeout 10; spawn env EDGE_SCOUT_SCAN_SCRIPT=' + str(fake) + ' ./main.sh; '
        'expect "启动 Web 监控"; '
        f'send "{down}"; '
        'expect -re {> SMC 选股（仅本地数据）}; send "\\r"; expect "0|select"; '
        'expect "按回车返回菜单"; send "\\r"; expect "启动 Web 监控"; '
        'send "q"; expect "已退出。"; expect eof'
    )
    completed = subprocess.run(
        [expect, "-c", script],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_main_menu_auto_smc_default_enter_enables_post_smc_analysis(tmp_path: Path) -> None:
    expect = shutil.which("expect")
    if expect is None:
        return
    fake = tmp_path / "fake_scan.sh"
    fake.write_text(
        "#!/usr/bin/env bash\nprintf '%s|%s\\n' \"${EDGE_SCOUT_AUTO_UPDATE:-unset}\" \"$*\"\n",
        encoding="utf-8",
    )
    fake.chmod(0o755)
    down = "\\033\\[B" * 10
    script = (
        'set timeout 10; spawn env EDGE_SCOUT_SCAN_SCRIPT=' + str(fake) + ' ./main.sh; '
        'expect "启动 Web 监控"; '
        f'send "{down}"; '
        'expect -re {> SMC 选股（自动更新数据）}; send "\\r"; '
        'expect "是否进行 SMC 后人工复核建议分析"; send "\\r"; '
        'expect "unset|select-review --post-smc-analysis"; exit 0'
    )
    completed = subprocess.run(
        [expect, "-c", script],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_main_menu_auto_smc_explicit_no_skips_post_smc_analysis(tmp_path: Path) -> None:
    expect = shutil.which("expect")
    if expect is None:
        return
    fake = tmp_path / "fake_scan.sh"
    fake.write_text(
        "#!/usr/bin/env bash\nprintf '%s|%s\\n' \"${EDGE_SCOUT_AUTO_UPDATE:-unset}\" \"$*\"\n",
        encoding="utf-8",
    )
    fake.chmod(0o755)
    down = "\\033\\[B" * 10
    script = (
        'set timeout 10; spawn env EDGE_SCOUT_SCAN_SCRIPT=' + str(fake) + ' ./main.sh; '
        'expect "启动 Web 监控"; '
        f'send "{down}"; '
        'expect -re {> SMC 选股（自动更新数据）}; send "\\r"; '
        'expect "是否进行 SMC 后人工复核建议分析"; send "n\\r"; '
        'expect "unset|select-review --no-post-smc-analysis"; exit 0'
    )
    completed = subprocess.run(
        [expect, "-c", script],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_main_menu_auto_smc_runs_selector_then_news_review(tmp_path: Path) -> None:
    expect = shutil.which("expect")
    if expect is None:
        return
    fake = tmp_path / "fake_scan.sh"
    fake.write_text(
        "#!/usr/bin/env bash\nprintf '%s|%s\\n' \"${EDGE_SCOUT_AUTO_UPDATE:-unset}\" \"$*\"\n",
        encoding="utf-8",
    )
    fake.chmod(0o755)
    down = "\\033\\[B" * 10
    script = (
        'set timeout 10; spawn env EDGE_SCOUT_SCAN_SCRIPT=' + str(fake) + ' ./main.sh; '
        'expect "启动 Web 监控"; '
        f'send "{down}"; '
        'expect -re {> SMC 选股（自动更新数据）}; send "\\r"; '
        'expect "unset|select-review"; exit 0'
    )
    completed = subprocess.run(
        [expect, "-c", script],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=20,
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
    mkf_entry_down = "\\033\\[B" * 17
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
        'expect "unset|review-mkf-ai"; exit 0'
    )
    completed = subprocess.run(
        [expect, "-c", script],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_main_menu_research_evidence_options_route_without_extra_input(tmp_path: Path) -> None:
    expect = shutil.which("expect")
    if expect is None:
        return
    fake = tmp_path / "fake_scan.sh"
    fake.write_text(
        "#!/usr/bin/env bash\nprintf '%s|%s\\n' \"${EDGE_SCOUT_AUTO_UPDATE:-unset}\" \"$*\"\n",
        encoding="utf-8",
    )
    fake.chmod(0o755)
    audit_down = "\\033\\[B" * 14
    replay_down = "\\033\\[B" * 15
    script = (
        'set timeout 10; spawn env EDGE_SCOUT_SCAN_SCRIPT=' + str(fake) + ' ./main.sh; '
        'expect "启动 Web 监控"; '
        f'send "{audit_down}"; '
        'expect -re {> SMC\\+新闻前瞻成熟度审计}; send "\\r"; '
        'expect "unset|audit-smc-news"; '
        'expect "按回车返回菜单"; send "\\r"; expect "启动 Web 监控"; '
        f'send "{replay_down}"; '
        'expect -re {> SMC\\+新闻回放检查（simulation only）}; send "\\r"; '
        'expect "unset|replay-smc-news --dry-run"; exit 0'
    )
    completed = subprocess.run(
        [expect, "-c", script],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=25,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
