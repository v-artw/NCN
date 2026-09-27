#!/usr/bin/env bash
# ============================================================================
# SMC 研究控制脚本（smc/ 子项目自有 hub）
# 2026-09-27 从 scripts/edge_scout_scan.sh 中分离；只服务 SMC 流程。
# ============================================================================
# 结构：REPO=../，SMC=本脚本上级目录。
# 数据/venv/Key 复用主仓；SMC 代码在 smc/src/ashare_smc（smc -> main 单向依赖）。
# 边界：只读研究扫描，不连接券商，不提交真实订单，不构成投资建议。
# ============================================================================

set -euo pipefail

SMC_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "${SMC_ROOT}/.." && pwd)"
SRC_ROOT="${REPO_ROOT}/src"
SMC_SRC_ROOT="${SMC_ROOT}/src"
# 主仓 hub：仅用于 update 等共享数据管线委托（smc -> main，允许方向）。
SCAN_CONTROL="${EDGE_SCOUT_SCAN_SCRIPT:-${REPO_ROOT}/scripts/edge_scout_scan.sh}"
NEWS_AI_ENV="${EDGE_SCOUT_NEWS_AI_ENV:-${REPO_ROOT}/.env.news_ai}"
if [ -f "${NEWS_AI_ENV}" ]; then
    set -a
    # Local ignored secrets/configuration for the optional AI review endpoint.
    source "${NEWS_AI_ENV}"
    set +a
fi
# 数据目录与主仓共用同一份前复权研究数据；迁移期可通过环境变量覆盖。
DATA_ROOT="${EDGE_SCOUT_DATA_ROOT:-${REPO_ROOT}/PFrontStockData}"
CONFIG="${SMC_CONFIG:-${EDGE_SCOUT_CONFIG:-${SMC_ROOT}/yaml/edge_scout_v1.yaml}}"
NEWS_AI_CONFIG="${SMC_NEWS_AI_CONFIG:-${EDGE_SCOUT_NEWS_AI_CONFIG:-${SMC_ROOT}/yaml/news_ai_review.yaml}}"
VENV="${VENV_PYTHON:-${REPO_ROOT}/.venv/bin/python}"
AUTO_UPDATE="${EDGE_SCOUT_AUTO_UPDATE:-1}"
SMC_PYTHONPATH="${SMC_SRC_ROOT}:${SRC_ROOT}"

# SMC 输出默认落仓库根 smc-output/（删除 smc/ 后由使用者自行保管历史输出）。
DEFAULT_OUTPUT_ROOT="${SMC_OUTPUT_ROOT:-${EDGE_SCOUT_OUTPUT_ROOT:-${REPO_ROOT}/smc-output}}"

read_review_max_candidates() {
    local config_path="$1"
    local fallback="20"
    local value=""
    if [ -f "${config_path}" ]; then
        value="$(awk '
            /^[^[:space:]]/ { in_review = ($1 == "review:") }
            in_review && /^[[:space:]]+max_candidates:[[:space:]]*/ { print $2; exit }
        ' "${config_path}")"
    fi
    if [[ "${value}" =~ ^[0-9]+$ ]] && [ "${value}" -ge 1 ]; then
        printf '%s\n' "${value}"
    else
        printf '%s\n' "${fallback}"
    fi
}

check_runtime_prereqs() {
    if [ ! -d "${SMC_ROOT}" ]; then
        echo "ERROR: SMC 项目目录不存在：${SMC_ROOT}" >&2
        exit 1
    fi
    if [ ! -x "${VENV}" ]; then
        echo "ERROR: Python 可执行文件不存在或不可执行：${VENV}；请先在主仓运行：cd ${REPO_ROOT} && ./scripts/setup.sh" >&2
        exit 1
    fi
    if [ ! -f "${CONFIG}" ]; then
        echo "ERROR: 配置文件不存在：${CONFIG}" >&2
        exit 1
    fi
}

check_data_root() {
    if [ ! -d "${DATA_ROOT}" ]; then
        echo "ERROR: 数据目录不存在且自动更新未创建目录：${DATA_ROOT}" >&2
        exit 1
    fi
}

# 数据更新完全复用主仓 BaoStock 管线（smc -> main，允许方向）。
auto_update_data() {
    if [ "${AUTO_UPDATE}" != "1" ]; then
        echo " 数据更新：已跳过 (EDGE_SCOUT_AUTO_UPDATE=${AUTO_UPDATE})"
        return
    fi
    "${SCAN_CONTROL}" update
}

cmd_select() {
    local as_of=""
    local top="20"
    while [ $# -gt 0 ]; do
        case "$1" in
            --as-of)
                shift
                as_of="${1:?--as-of requires YYYY-MM-DD}"
                shift
                ;;
            --top)
                shift
                top="${1:?--top requires an integer}"
                shift
                ;;
            *)
                echo "ERROR: unknown select argument: $1" >&2
                exit 2
                ;;
        esac
    done
    local run_id="select-$(date +%Y%m%d_%H%M%S)"
    local args=(
        --data-root "${DATA_ROOT}"
        --config "${CONFIG}"
        --output-root "${DEFAULT_OUTPUT_ROOT}/selections"
        --run-id "${run_id}"
        --top "${top}"
    )
    if [ -n "${as_of}" ]; then
        args+=(--as-of "${as_of}")
    fi
    PYTHONPATH="${SMC_PYTHONPATH}" PYTHONNOUSERSITE=1 PYTHONSAFEPATH=1 \
        "${VENV}" -B "${SMC_ROOT}/scripts/select_stocks.py" "${args[@]}"
}

cmd_review_news() {
    local selection_run=""
    local top=""
    while [ $# -gt 0 ]; do
        case "$1" in
            --selection-run)
                shift
                selection_run="${1:?--selection-run requires a directory}"
                shift
                ;;
            --top)
                shift
                top="${1:?--top requires an integer}"
                shift
                ;;
            *)
                echo "ERROR: unknown review-news argument: $1" >&2
                exit 2
                ;;
        esac
    done
    if [ ! -f "${NEWS_AI_CONFIG}" ]; then
        echo "ERROR: 新闻 AI 配置不存在：${NEWS_AI_CONFIG}" >&2
        exit 1
    fi
    local run_id="news-review-$(date +%Y%m%d_%H%M%S)"
    local args=(
        --selection-root "${DEFAULT_OUTPUT_ROOT}/selections"
        --output-root "${DEFAULT_OUTPUT_ROOT}/news_reviews"
        --config "${NEWS_AI_CONFIG}"
        --data-root "${DATA_ROOT}"
        --run-id "${run_id}"
    )
    if [ -n "${top}" ]; then
        args+=(--top "${top}")
    fi
    if [ -n "${selection_run}" ]; then
        args+=(--selection-run "${selection_run}")
    fi
    PYTHONPATH="${SMC_PYTHONPATH}" PYTHONNOUSERSITE=1 PYTHONSAFEPATH=1 \
        "${VENV}" -B "${SMC_ROOT}/scripts/review_smc_news.py" "${args[@]}"
}

cmd_select_review() {
    local prospective_archive=1
    local review_top=""
    local post_smc_analysis=0
    local original_args=()
    while [ $# -gt 0 ]; do
        case "$1" in
            --as-of)
                prospective_archive=0
                original_args+=("$1" "${2:?--as-of requires YYYY-MM-DD}")
                shift 2
                ;;
            --top)
                review_top="${2:?--top requires an integer}"
                original_args+=("$1" "$2")
                shift 2
                ;;
            --post-smc-analysis)
                post_smc_analysis=1
                shift
                ;;
            --no-post-smc-analysis)
                post_smc_analysis=0
                shift
                ;;
            *)
                echo "ERROR: unknown select-review argument: $1" >&2
                return 2
                ;;
        esac
    done
    local selection_output selection_run news_output news_run
    local effective_top="${review_top:-$(read_review_max_candidates "${NEWS_AI_CONFIG}")}"
    local selection_args=()
    if [ "${#original_args[@]}" -gt 0 ]; then
        selection_args+=("${original_args[@]}")
    fi
    if [ -z "${review_top}" ]; then
        selection_args+=(--top "${effective_top}")
    fi
    set +e
    selection_output="$(cmd_select "${selection_args[@]}" 2>&1)"
    local selection_status=$?
    set -e
    printf '%s\n' "${selection_output}"
    if [ "${selection_status}" -ne 0 ]; then
        return "${selection_status}"
    fi
    selection_run="$(printf '%s\n' "${selection_output}" | awk -F= '/^run_directory=/ {value=$2} END {print value}')"
    if [ -z "${selection_run}" ]; then
        echo "ERROR: 未能从 SMC 选股输出解析 run_directory，拒绝回退到 latest。" >&2
        return 2
    fi
    echo
    echo "SMC 新闻 AI 二次复核：开始分析最新选股结果..."
    local review_args=(--selection-run "${selection_run}" --top "${effective_top}")
    set +e
    news_output="$(cmd_review_news "${review_args[@]}" 2>&1)"
    local news_status=$?
    set -e
    printf '%s\n' "${news_output}"
    if [ "${news_status}" -ne 0 ]; then
        return "${news_status}"
    fi
    news_run="$(printf '%s\n' "${news_output}" | awk -F= '/^run_directory=/ {value=$2} END {print value}')"
    if [ -z "${news_run}" ]; then
        echo "ERROR: 未能从新闻复核输出解析 run_directory，拒绝回退到 latest。" >&2
        return 2
    fi
    if [ "${post_smc_analysis}" -eq 1 ]; then
        echo
        echo "SMC 后人工复核建议分析：基于本次选股和新闻复核生成只读 CSV..."
        local analysis_args=(--selection-run "${selection_run}" --top "${effective_top}" --news-run "${news_run}")
        cmd_post_smc_analysis "${analysis_args[@]}"
    fi
    if [ "${prospective_archive}" -eq 1 ]; then
        echo
        echo "SMC 新闻前瞻证据归档：冻结本次选股和复核状态..."
        cmd_archive_smc_news_prospective --selection-run "${selection_run}" --news-run "${news_run}"
    else
        echo
        echo "SMC 新闻前瞻证据归档：跳过手动 as-of 结果。"
    fi
}

cmd_post_smc_analysis() {
    local selection_run=""
    local news_run=""
    local top="20"
    while [ $# -gt 0 ]; do
        case "$1" in
            --selection-run)
                shift
                selection_run="${1:?--selection-run requires a directory}"
                shift
                ;;
            --news-run)
                shift
                news_run="${1:?--news-run requires a directory}"
                shift
                ;;
            --top)
                shift
                top="${1:?--top requires an integer}"
                shift
                ;;
            *)
                echo "ERROR: unknown post-smc-analysis argument: $1" >&2
                exit 2
                ;;
        esac
    done
    if [ -z "${selection_run}" ]; then
        echo "ERROR: post-smc-analysis requires --selection-run DIR" >&2
        exit 2
    fi
    local args=(--selection-run "${selection_run}" --top "${top}")
    if [ -n "${news_run}" ]; then
        args+=(--news-run "${news_run}")
    fi
    PYTHONPATH="${SMC_PYTHONPATH}" PYTHONNOUSERSITE=1 PYTHONSAFEPATH=1 \
        "${VENV}" -B "${SMC_ROOT}/scripts/analyze_post_smc_recommendation.py" "${args[@]}"
}

cmd_archive_smc_news_prospective() {
    local run_id="smc-news-$(date +%Y%m%d_%H%M%S)"
    local args=(
        --selection-root "${DEFAULT_OUTPUT_ROOT}/selections"
        --news-root "${DEFAULT_OUTPUT_ROOT}/news_reviews"
        --output-root "${DEFAULT_OUTPUT_ROOT}/smc_news_prospective"
        --run-id "${run_id}"
    )
    args+=("$@")
    PYTHONPATH="${SMC_PYTHONPATH}" \
        PYTHONNOUSERSITE=1 \
        PYTHONSAFEPATH=1 \
        "${VENV}" -B "${SMC_ROOT}/scripts/archive_smc_news_prospective.py" "${args[@]}"
}

cmd_archive_smc_news_preflight() {
    local selection_run="${1:?selection run required}"
    PYTHONPATH="${SMC_PYTHONPATH}" \
        PYTHONNOUSERSITE=1 \
        PYTHONSAFEPATH=1 \
        "${VENV}" -B "${SMC_ROOT}/scripts/archive_smc_news_prospective.py" \
        --selection-root "${DEFAULT_OUTPUT_ROOT}/selections" \
        --output-root "${DEFAULT_OUTPUT_ROOT}/smc_news_prospective" \
        --selection-run "${selection_run}" \
        --check-existing-signal-date
}

cmd_audit_smc_news_prospective() {
    local audit_dir="${DEFAULT_OUTPUT_ROOT}/smc_news_prospective_audits"
    local audit_path="${audit_dir}/smc-news-audit-$(date -u +%Y%m%dT%H%M%SZ).json"
    mkdir -p "${audit_dir}"
    PYTHONPATH="${SMC_PYTHONPATH}" \
        PYTHONNOUSERSITE=1 \
        PYTHONSAFEPATH=1 \
        "${VENV}" -B "${SMC_ROOT}/scripts/audit_smc_news_prospective.py" \
        --output-root "${DEFAULT_OUTPUT_ROOT}" \
        --data-root "${DATA_ROOT}" \
        --output "${audit_path}"
}

cmd_replay_smc_news() {
    local args=(
        --selection-root "${DEFAULT_OUTPUT_ROOT}/selections"
        --news-root "${DEFAULT_OUTPUT_ROOT}/news_reviews"
        --cache-root "${SMC_ROOT}/.runtime/news_cache"
        --data-root "${DATA_ROOT}"
        --output-root "${DEFAULT_OUTPUT_ROOT}/smc_news_replay"
    )
    args+=("$@")
    PYTHONPATH="${SMC_PYTHONPATH}" \
        PYTHONNOUSERSITE=1 \
        PYTHONSAFEPATH=1 \
        "${VENV}" -B "${SMC_ROOT}/scripts/replay_smc_news.py" "${args[@]}"
}

cmd_daily() {
    local review_top=""
    while [ $# -gt 0 ]; do
        case "$1" in
            --top)
                shift
                review_top="${1:?--top requires an integer}"
                shift
                ;;
            --as-of)
                echo "ERROR: daily 仅支持自动日期；历史/手动复核请使用 select-review --as-of DATE，且不会进入前瞻归档。" >&2
                return 2
                ;;
            *)
                echo "ERROR: unknown daily argument: $1" >&2
                return 2
                ;;
        esac
    done

    auto_update_data
    check_data_root

    local effective_top="${review_top:-$(read_review_max_candidates "${NEWS_AI_CONFIG}")}"
    local selection_output selection_status selection_run signal_date selection_count selection_csv human_review_summary_csv
    set +e
    selection_output="$(cmd_select --top "${effective_top}" 2>&1)"
    selection_status=$?
    set -e
    printf '%s\n' "${selection_output}"
    if [ "${selection_status}" -ne 0 ]; then
        return "${selection_status}"
    fi
    signal_date="$(printf '%s\n' "${selection_output}" | awk -F= '/^signal_date=/ {value=$2} END {print value}')"
    selection_count="$(printf '%s\n' "${selection_output}" | awk -F= '/^candidate_count=/ {value=$2} END {print value}')"
    selection_run="$(printf '%s\n' "${selection_output}" | awk -F= '/^run_directory=/ {value=$2} END {print value}')"
    selection_csv="$(printf '%s\n' "${selection_output}" | awk -F= '/^timestamped_csv=/ {value=$2} END {print value}')"
    human_review_summary_csv="$(printf '%s\n' "${selection_output}" | awk -F= '/^human_review_summary_csv=/ {value=$2} END {print value}')"
    if [ -z "${signal_date}" ] || [ -z "${selection_run}" ]; then
        echo "ERROR: daily 未能从 SMC 选股输出解析 signal_date/run_directory，拒绝回退到 latest。" >&2
        return 2
    fi

    local preflight_output preflight_status archive_duplicate existing_archive existing_archive_run_id
    set +e
    preflight_output="$(cmd_archive_smc_news_preflight "${selection_run}" 2>&1)"
    preflight_status=$?
    set -e
    printf '%s\n' "${preflight_output}"
    if [ "${preflight_status}" -ne 0 ]; then
        return "${preflight_status}"
    fi
    archive_duplicate="$(printf '%s\n' "${preflight_output}" | awk -F= '/^archive_duplicate=/ {value=$2} END {print value}')"
    existing_archive="$(printf '%s\n' "${preflight_output}" | awk -F= '/^existing_archive=/ {value=$2} END {print value}')"
    existing_archive_run_id="$(printf '%s\n' "${preflight_output}" | awk -F= '/^existing_archive_run_id=/ {value=$2} END {print value}')"

    local news_status_text="skipped_existing_prospective_archive"
    local news_run=""
    local news_csv=""
    local ai_committee_csv=""
    local ai_committee_latest_csv=""
    local priority_count="0"
    local risk_count="0"
    local archive_status="skipped_existing_signal_date"
    local archive_path="${existing_archive}"
    if [ "${archive_duplicate}" = "1" ]; then
        news_run="$(printf '%s\n' "${preflight_output}" | awk -F= '/^existing_news_run=/ {value=$2} END {print value}')"
        ai_committee_csv="$(printf '%s\n' "${preflight_output}" | awk -F= '/^existing_ai_committee_csv=/ {value=$2} END {print value}')"
        ai_committee_latest_csv="$(printf '%s\n' "${preflight_output}" | awk -F= '/^existing_ai_committee_latest_csv=/ {value=$2} END {print value}')"
    fi
    if [ "${archive_duplicate}" != "1" ]; then
        local news_output news_status archive_output archive_exit
        echo
        echo "SMC 新闻 AI 二次复核：开始分析本次 daily 选股结果..."
        local review_args=(--selection-run "${selection_run}" --top "${effective_top}")
        set +e
        news_output="$(cmd_review_news "${review_args[@]}" 2>&1)"
        news_status=$?
        set -e
        printf '%s\n' "${news_output}"
        if [ "${news_status}" -ne 0 ]; then
            return "${news_status}"
        fi
        news_status_text="$(printf '%s\n' "${news_output}" | awk -F= '/^status=/ {value=$2} END {print value}')"
        priority_count="$(printf '%s\n' "${news_output}" | awk -F= '/^priority_review_count=/ {value=$2} END {print value}')"
        risk_count="$(printf '%s\n' "${news_output}" | awk -F= '/^risk_excluded_count=/ {value=$2} END {print value}')"
        news_run="$(printf '%s\n' "${news_output}" | awk -F= '/^run_directory=/ {value=$2} END {print value}')"
        news_csv="$(printf '%s\n' "${news_output}" | awk -F= '/^timestamped_csv=/ {value=$2} END {print value}')"
        ai_committee_csv="$(printf '%s\n' "${news_output}" | awk -F= '/^ai_committee_csv=/ {value=$2} END {print value}')"
        ai_committee_latest_csv="$(printf '%s\n' "${news_output}" | awk -F= '/^ai_committee_latest_csv=/ {value=$2} END {print value}')"
        human_review_summary_csv="$(printf '%s\n' "${news_output}" | awk -F= '/^human_review_summary_csv=/ {value=$2} END {print value}')"
        if [ -z "${news_run}" ]; then
            echo "ERROR: daily 未能从新闻复核输出解析 run_directory，拒绝回退到 latest。" >&2
            return 2
        fi
        echo
        echo "SMC 新闻前瞻证据归档：冻结本次 daily 选股和复核状态..."
        set +e
        archive_output="$(cmd_archive_smc_news_prospective --selection-run "${selection_run}" --news-run "${news_run}" 2>&1)"
        archive_exit=$?
        set -e
        printf '%s\n' "${archive_output}"
        if [ "${archive_exit}" -ne 0 ]; then
            return "${archive_exit}"
        fi
        archive_status="$(printf '%s\n' "${archive_output}" | awk -F= '/^smc_news_prospective_archive_status=/ {value=$2} END {print value}')"
        archive_path="$(printf '%s\n' "${archive_output}" | awk -F= '/^smc_news_prospective_archive=/ {value=$2} /^existing_archive=/ {value=$2} END {print value}')"
        if [ -z "${archive_status}" ]; then archive_status="created"; fi
    fi

    local audit_output audit_status audit_canonical audit_mature parent_ok promotion_ok evidence_ok audit_path
    echo
    echo "SMC 新闻前瞻成熟度审计：检查 canonical snapshots 和成熟度..."
    set +e
    audit_output="$(cmd_audit_smc_news_prospective 2>&1)"
    audit_status=$?
    set -e
    printf '%s\n' "${audit_output}"
    if [ "${audit_status}" -ne 0 ]; then
        return "${audit_status}"
    fi
    audit_canonical="$(printf '%s\n' "${audit_output}" | awk -F= '/^canonical_smc_news_snapshots=/ {value=$2} END {print value}')"
    audit_mature="$(printf '%s\n' "${audit_output}" | awk -F= '/^mature_all_smc=/ {value=$2} END {print value}')"
    parent_ok="$(printf '%s\n' "${audit_output}" | awk -F= '/^parent_maturity_sufficient=/ {value=$2} END {print value}')"
    promotion_ok="$(printf '%s\n' "${audit_output}" | awk -F= '/^promotion_evidence_sufficient=/ {value=$2} END {print value}')"
    evidence_ok="$(printf '%s\n' "${audit_output}" | awk -F= '/^evidence_sufficient=/ {value=$2} END {print value}')"
    audit_path="$(printf '%s\n' "${audit_output}" | awk -F= '/^output=/ {value=$2} END {print value}')"

    echo
    echo "每日 SMC+新闻人工复核摘要"
    echo "signal_date=${signal_date}"
    echo "selection_candidates=${selection_count}"
    echo "selection_run=${selection_run}"
    echo "selection_csv=${selection_csv}"
    echo "news_review=${news_status_text}"
    echo "priority_review_count=${priority_count}"
    echo "risk_excluded_count=${risk_count}"
    echo "news_run=${news_run}"
    echo "news_csv=${news_csv}"
    echo "ai_committee_csv=${ai_committee_csv}"
    echo "ai_committee_latest_csv=${ai_committee_latest_csv}"
    echo "human_review_summary_csv=${human_review_summary_csv}"
    echo "existing_archive_run_id=${existing_archive_run_id}"
    echo "existing_archive=${existing_archive}"
    echo "archive_status=${archive_status}"
    echo "archive_path=${archive_path}"
    echo "canonical_smc_news_snapshots=${audit_canonical}"
    echo "mature_all_smc=${audit_mature}"
    echo "parent_maturity_sufficient=${parent_ok}"
    echo "promotion_evidence_sufficient=${promotion_ok}"
    echo "evidence_sufficient=${evidence_ok}"
    echo "audit_output=${audit_path}"
    echo "human_review_note=新闻/日K AI委员会CSV仅供人工复核参考，未验证，不改变 SMC 入选、排序、阈值或生产逻辑。"
    echo "boundary=只读研究扫描；不连接券商；不提交订单；不计算 P&L/收益；不构成个性化建议。"
}

cmd_test() {
    echo "=============================================="
    echo " SMC 研究测试（smc/tests）"
    echo "=============================================="
    cd "${REPO_ROOT}"
    PYTHONPATH="${SMC_PYTHONPATH}" \
        PYTHONNOUSERSITE=1 \
        "${VENV}" -B -m pytest smc/tests -q --tb=short "$@"
}

cmd_help() {
    cat <<'HELP'

SMC 研究控制脚本（smc/ 子项目）
A 股 SMC 强势突破选股 + 新闻 AI 复核只读研究流程

用法：
  smc_scan.sh select [--as-of YYYY-MM-DD] [--top N]
      使用现有本地日线运行 SMC 只读选股，不需要分钟或付费数据

  smc_scan.sh daily [--top N]
      每日 SMC+新闻一键流程：自动更新(委托主仓)/选股/去重/AI委员会CSV/归档/审计

  smc_scan.sh select-review [--as-of YYYY-MM-DD] [--top N] [--post-smc-analysis|--no-post-smc-analysis]
      自动日期运行会冻结前瞻证据；手动 --as-of 仅做选股和复核，不进入前瞻归档

  smc_scan.sh review-news [--selection-run DIR] [--top N]
      复核指定或最新 SMC 结果；--top 仅限制终端展示，JSON/CSV 保存完整候选复核

  smc_scan.sh post-smc-analysis --selection-run DIR [--news-run DIR] [--top N]
      基于已冻结 SMC/可选新闻复核结果生成只读人工复核建议分析 CSV

  smc_scan.sh archive-smc-news
      冻结最新 SMC 选股和新闻 AI 复核状态，供未来成熟度审计使用

  smc_scan.sh audit-smc-news
      生成新的 SMC 选股 + 新闻 AI 复核前瞻成熟度审计 JSON

  smc_scan.sh replay-smc-news [--dry-run] [--start-date YYYY-MM-DD] [--end-date YYYY-MM-DD]
      生成 simulation_only SMC+新闻历史回放，不写前瞻归档、不声明前瞻证据

  smc_scan.sh update
      数据检查与增量更新（委托主仓 edge_scout_scan.sh update，共用 PFrontStockData）

  smc_scan.sh test
      运行 SMC 测试（smc/tests）

结构：
  SMC 代码      ：smc/src/ashare_smc/（依赖主仓 ashare_edge_scout，方向仅 smc -> main）
  SMC 配置      ：smc/yaml/（smc_ai_review.yaml、news_ai_review.yaml、ai_providers.yaml 等副本）
  SMC 输出      ：<仓库根>/smc-output/（默认，可用 SMC_OUTPUT_ROOT 覆盖）
  删除或移走 smc/ 对主仓 MKF 流程零影响。

边界：
  - 只读研究扫描
  - 不连接券商
  - 不提交真实订单
  - 不构成投资建议

HELP
}

main() {
    local first="${1:-}"

    case "${first}" in
        select)
            check_runtime_prereqs
            auto_update_data
            check_data_root
            shift
            cmd_select "$@"
            ;;
        daily)
            check_runtime_prereqs
            shift
            cmd_daily "$@"
            ;;
        select-review)
            check_runtime_prereqs
            auto_update_data
            check_data_root
            shift
            cmd_select_review "$@"
            ;;
        review-news)
            check_runtime_prereqs
            shift
            cmd_review_news "$@"
            ;;
        post-smc-analysis)
            check_runtime_prereqs
            shift
            cmd_post_smc_analysis "$@"
            ;;
        archive-smc-news)
            check_runtime_prereqs
            shift
            cmd_archive_smc_news_prospective "$@"
            ;;
        audit-smc-news)
            check_runtime_prereqs
            check_data_root
            shift
            cmd_audit_smc_news_prospective "$@"
            ;;
        replay-smc-news)
            check_runtime_prereqs
            check_data_root
            shift
            cmd_replay_smc_news "$@"
            ;;
        update)
            check_runtime_prereqs
            auto_update_data
            check_data_root
            ;;
        test)
            check_runtime_prereqs
            shift
            cmd_test "$@"
            ;;
        help|-h|--help)
            cmd_help
            ;;
        *)
            echo "ERROR: unknown smc_scan command: ${first}；运行 smc_scan.sh help 查看用法。" >&2
            exit 2
            ;;
    esac
}

main "$@"
