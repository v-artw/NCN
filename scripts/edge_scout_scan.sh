#!/usr/bin/env bash
# ============================================================================
# Edge Scout 一键扫描脚本
# A 股多因子 + 15 日蜡烛图短线研究系统
# ============================================================================
# 项目：独立 NCN Edge Scout
# 数据：默认使用本项目 PFrontStockData/，可用 EDGE_SCOUT_DATA_ROOT 覆盖
# 文档：CLAUDE.md / output/handoff.md
# 边界：只读研究扫描，不连接券商，不提交真实订单，不构成投资建议
# ============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# 路径配置（可根据需要修改）
# ---------------------------------------------------------------------------
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC_ROOT="${PROJECT_ROOT}/src"
NEWS_AI_ENV="${EDGE_SCOUT_NEWS_AI_ENV:-${PROJECT_ROOT}/.env.news_ai}"
if [ -f "${NEWS_AI_ENV}" ]; then
    set -a
    # Local ignored secrets/configuration for the optional AI review endpoint.
    source "${NEWS_AI_ENV}"
    set +a
fi
# 数据目录：本项目内的前复权研究数据；迁移期可通过环境变量覆盖。
DATA_ROOT="${EDGE_SCOUT_DATA_ROOT:-${PROJECT_ROOT}/PFrontStockData}"
CONFIG="${EDGE_SCOUT_CONFIG:-${PROJECT_ROOT}/yaml/edge_scout_v1.yaml}"
NEWS_AI_CONFIG="${EDGE_SCOUT_NEWS_AI_CONFIG:-${PROJECT_ROOT}/yaml/news_ai_review.yaml}"
MKF_AI_CONFIG="${EDGE_SCOUT_MKF_AI_CONFIG:-${PROJECT_ROOT}/yaml/mkf_ai_review.yaml}"
BAOSTOCK_CONFIG="${EDGE_SCOUT_BAOSTOCK_CONFIG:-${PROJECT_ROOT}/yaml/baostock_config.yaml}"
VENV="${VENV_PYTHON:-${PROJECT_ROOT}/.venv/bin/python}"
AUTO_UPDATE="${EDGE_SCOUT_AUTO_UPDATE:-1}"
DOWNLOAD_WORKERS="${EDGE_SCOUT_DOWNLOAD_WORKERS:-}"
MAX_FAILURE_RATE="${EDGE_SCOUT_DOWNLOAD_MAX_FAILURE_RATE:-0.10}"
MINIMUM_LATEST_COVERAGE="${EDGE_SCOUT_MINIMUM_LATEST_COVERAGE:-0.95}"


# 默认输出根目录
DEFAULT_OUTPUT_ROOT="${EDGE_SCOUT_OUTPUT_ROOT:-${PROJECT_ROOT}/output/edge_scout}"

# ---------------------------------------------------------------------------
# 股票代码标准化：支持 sh.600000 / 000001 / 600000，自动补全交易所前缀
# ---------------------------------------------------------------------------
normalize_stock_code() {
  local raw="$1"
  raw="${raw//[[:space:]]/}"
  case "${raw}" in
    sh.[0-9][0-9][0-9][0-9][0-9][0-9]|sz.[0-9][0-9][0-9][0-9][0-9][0-9])
      printf '%s\n' "${raw}"
      ;;
    SH.[0-9][0-9][0-9][0-9][0-9][0-9])
      printf 'sh.%s\n' "${raw#SH.}"
      ;;
    SZ.[0-9][0-9][0-9][0-9][0-9][0-9])
      printf 'sz.%s\n' "${raw#SZ.}"
      ;;
    600[0-9][0-9][0-9]|601[0-9][0-9][0-9]|603[0-9][0-9][0-9]|605[0-9][0-9][0-9])
      printf 'sh.%s\n' "${raw}"
      ;;
    000[0-9][0-9][0-9]|001[0-9][0-9][0-9]|002[0-9][0-9][0-9]|003[0-9][0-9][0-9])
      printf 'sz.%s\n' "${raw}"
      ;;
    *)
      return 1
      ;;
  esac
}

# ---------------------------------------------------------------------------
# 检查前置条件
# ---------------------------------------------------------------------------
check_runtime_prereqs() {
    if [ ! -d "${PROJECT_ROOT}" ]; then
        echo "ERROR: 项目目录不存在：${PROJECT_ROOT}" >&2
        exit 1
    fi
    if [ ! -x "${VENV}" ]; then
        echo "ERROR: Python 可执行文件不存在或不可执行：${VENV}；请先运行：cd ${PROJECT_ROOT} && ./scripts/setup.sh" >&2
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

auto_update_data() {
    if [ "${AUTO_UPDATE}" != "1" ]; then
        echo " 数据更新：已跳过 (EDGE_SCOUT_AUTO_UPDATE=${AUTO_UPDATE})"
        return
    fi
    if [ ! -f "${BAOSTOCK_CONFIG}" ]; then
        echo "ERROR: BaoStock 配置不存在：${BAOSTOCK_CONFIG}" >&2
        exit 1
    fi

    local update_root="${DEFAULT_OUTPUT_ROOT}/data_updates"
    local check_summary="${update_root}/latest_check.json"
    local download_summary="${update_root}/latest_download.json"
    mkdir -p "${update_root}"

    echo " 数据更新：检查 BaoStock 最新交易日..."
    set +e
    if [ -n "${EDGE_SCOUT_UPDATE_CHECK_COMMAND:-}" ]; then
        DATA_ROOT="${DATA_ROOT}" CHECK_SUMMARY="${check_summary}" \
            bash -c "${EDGE_SCOUT_UPDATE_CHECK_COMMAND}"
    else
        PYTHONNOUSERSITE=1 "${VENV}" -B "${PROJECT_ROOT}/scripts/check_edge_scout_data_update.py" \
            --data-root "${DATA_ROOT}" --summary-json "${check_summary}" \
            --minimum-latest-coverage-ratio "${MINIMUM_LATEST_COVERAGE}"
    fi
    local check_status=$?
    set -e

    if [ "${check_status}" -eq 0 ]; then
        echo " 数据更新：本地数据已是最新，跳过下载。"
        return
    fi
    if [ "${check_status}" -ne 10 ]; then
        echo "ERROR: 无法确认 BaoStock 最新交易日，停止扫描；详情：${check_summary}" >&2
        exit "${check_status}"
    fi

    local remote_latest
    remote_latest="$("${VENV}" -c 'import json,sys; print(json.load(open(sys.argv[1]))["remote_latest_trade_date"])' "${check_summary}")"
    echo " 数据更新：发现远端新交易日 ${remote_latest}，开始增量下载到 ${DATA_ROOT}。"
    if [ -n "${EDGE_SCOUT_DOWNLOADER_COMMAND:-}" ]; then
        DATA_ROOT="${DATA_ROOT}" REMOTE_LATEST="${remote_latest}" DOWNLOAD_SUMMARY="${download_summary}" \
            bash -c "${EDGE_SCOUT_DOWNLOADER_COMMAND}"
    else
        local download_args=(
            "${PROJECT_ROOT}/Autobaostock_download.py"
            --config "${BAOSTOCK_CONFIG}"
            --data-dir "${DATA_ROOT}"
            --end-date "${remote_latest}"
            --stock-list-date "${remote_latest}"
            --no-clean
            --max-failure-rate "${MAX_FAILURE_RATE}"
            --summary-json "${download_summary}"
        )
        if [ -n "${DOWNLOAD_WORKERS}" ]; then
            download_args+=(--workers "${DOWNLOAD_WORKERS}")
        fi
        PYTHONDONTWRITEBYTECODE=1 "${VENV}" "${download_args[@]}"
    fi

    if ! "${VENV}" -c 'import json,sys; data=json.load(open(sys.argv[1])); raise SystemExit(0 if data.get("status")=="success" else 1)' "${download_summary}"; then
        echo "ERROR: BaoStock 增量下载未通过失败率门禁；详情：${download_summary}" >&2
        exit 1
    fi
    local effective_latest
    effective_latest="$(${VENV} -c 'import json,sys; data=json.load(open(sys.argv[1])); print(data.get("effective_end_date") or data.get("locked_trade_date") or data["requested_end_date"])' "${download_summary}")"
    if ! PYTHONNOUSERSITE=1 "${VENV}" -B "${PROJECT_ROOT}/scripts/check_edge_scout_data_update.py" \
        --data-root "${DATA_ROOT}" --remote-date "${effective_latest}" \
        --minimum-latest-coverage-ratio "${MINIMUM_LATEST_COVERAGE}" >/dev/null; then
        echo "ERROR: 下载摘要成功，但本地数据日期仍早于有效下载日期 ${effective_latest}，停止扫描。" >&2
        exit 1
    fi
    if [ "${effective_latest}" != "${remote_latest}" ]; then
        echo " 数据更新：远端查询日 ${remote_latest} 非交易日，已按有效交易日 ${effective_latest} 完成增量下载。"
    else
        echo " 数据更新：增量下载完成。"
    fi
}

# ---------------------------------------------------------------------------
# 全市场扫描
# ---------------------------------------------------------------------------
cmd_market() {
    # $@ 已经是 market 命令之后的参数
    local as_of="$(date +%Y-%m-%d)"
    local as_of_specified=0
    local output_root="${DEFAULT_OUTPUT_ROOT}"

    # 解析可选参数
    while [ $# -gt 0 ]; do
        case "$1" in
            --as-of)
                shift
                if [ $# -gt 0 ]; then
                    as_of="$1"
                    as_of_specified=1
                    shift
                fi
                ;;
            *)
                if [ -n "$1" ]; then
                    output_root="$1"
                    shift
                else
                    shift
                fi
                ;;
        esac
    done

    local run_id="market-$(date +%Y%m%d_%H%M%S)"

    echo "=============================================="
    echo " Edge Scout 全市场扫描"
    echo " 数据目录：${DATA_ROOT}"
    echo " 配置文件：${CONFIG}"
    echo " 输出目录：${output_root}"
    echo " 运行 ID  ：${run_id}"
    if [ "${as_of_specified}" -eq 1 ]; then
        echo " 扫描日期：${as_of} (用户指定，作为 T 信号日；T+1 研究确认、T+2 人工观察)"
    else
        echo " 扫描日期：自动 (T=最新数据日回退 2 个交易日，T+1 研究确认、T+2 人工观察)"
    fi
    echo "=============================================="

    local python_args=(
        --config "${CONFIG}"
        --data-root "${DATA_ROOT}"
        --output-root "${output_root}"
        --run-id "${run_id}"
    )
    if [ "${as_of_specified}" -eq 1 ]; then
        python_args+=(--as-of "${as_of}")
    fi

    if [ -n "${EDGE_SCOUT_SCANNER_COMMAND:-}" ]; then
        DATA_ROOT="${DATA_ROOT}" OUTPUT_ROOT="${output_root}" bash -c "${EDGE_SCOUT_SCANNER_COMMAND}"
    else
        PYTHONPATH="${SRC_ROOT}" \
            PYTHONNOUSERSITE=1 \
            PYTHONSAFEPATH=1 \
            "${VENV}" -B "${PROJECT_ROOT}/scripts/run_edge_scout_scan.py" \
            "${python_args[@]}"
    fi
}

# ---------------------------------------------------------------------------
# 单股扫描
# ---------------------------------------------------------------------------
cmd_single() {
    # $1 可以是 600000 / 000001 / sh.600000 / sz.000001，自动补全交易所前缀
    local raw_code="${1:?用法：edge_scout_scan.sh single <股票代码> [--as-of 日期]}"
    shift

    local code
    if ! code="$(normalize_stock_code "${raw_code}")"; then
        echo "ERROR: 无法识别股票代码 ${raw_code}；请输入沪深主板 6 位代码，如 600000、000001、sh.600000、sz.000001" >&2
        exit 2
    fi

    local as_of="$(date +%Y-%m-%d)"
    local as_of_specified=0
    local output_root="${DEFAULT_OUTPUT_ROOT}"

    # 解析后续参数
    while [ $# -gt 0 ]; do
        case "$1" in
            --as-of)
                shift
                if [ $# -gt 0 ]; then
                    as_of="$1"
                    as_of_specified=1
                    shift
                fi
                ;;
            *)
                if [ -n "$1" ]; then
                    output_root="$1"
                    shift
                else
                    shift
                fi
                ;;
        esac
    done

    local run_id="single-${code}-$(date +%Y%m%d_%H%M%S)"

    echo "=============================================="
    echo " Edge Scout 单股分析"
    echo " 股票代码：${code}"
    echo " 数据目录：${DATA_ROOT}"
    echo " 配置文件：${CONFIG}"
    echo " 输出目录：${output_root}"
    echo " 运行 ID  ：${run_id}"
    if [ "${as_of_specified}" -eq 1 ]; then
        echo " 扫描日期：${as_of} (用户指定，作为 T 信号日；T+1 研究确认、T+2 人工观察)"
    else
        echo " 扫描日期：自动 (T=该股最新数据日回退 2 个交易日，T+1 研究确认、T+2 人工观察)"
    fi
    echo "=============================================="

    local python_args=(
        --code "${code}"
        --config "${CONFIG}"
        --data-root "${DATA_ROOT}"
        --output-root "${output_root}"
        --run-id "${run_id}"
    )
    if [ "${as_of_specified}" -eq 1 ]; then
        python_args+=(--as-of "${as_of}")
    fi

    PYTHONPATH="${SRC_ROOT}" \
        PYTHONNOUSERSITE=1 \
        PYTHONSAFEPATH=1 \
        "${VENV}" -B "${PROJECT_ROOT}/scripts/run_edge_scout_single.py" \
        "${python_args[@]}"
}

cmd_select_review() {
    local prospective_archive=1
    local review_top="20"
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
    set +e
    if [ "${#original_args[@]}" -gt 0 ]; then
        selection_output="$(cmd_select "${original_args[@]}" 2>&1)"
    else
        selection_output="$(cmd_select 2>&1)"
    fi
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
    set +e
    news_output="$(cmd_review_news --selection-run "${selection_run}" --top "${review_top}" 2>&1)"
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
        cmd_post_smc_analysis --selection-run "${selection_run}" --news-run "${news_run}" --top "${review_top}"
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
    PYTHONPATH="${SRC_ROOT}" PYTHONNOUSERSITE=1 PYTHONSAFEPATH=1 \
        "${VENV}" -B "${PROJECT_ROOT}/scripts/select_stocks.py" "${args[@]}"
}

cmd_select_a_class() {
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
                echo "ERROR: unknown select-a-class argument: $1" >&2
                exit 2
                ;;
        esac
    done
    local run_id="a-class-select-$(date +%Y%m%d_%H%M%S)"
    local args=(
        --data-root "${DATA_ROOT}"
        --config "${CONFIG}"
        --output-root "${DEFAULT_OUTPUT_ROOT}/a_class_selections"
        --run-id "${run_id}"
        --top "${top}"
    )
    if [ -n "${as_of}" ]; then
        args+=(--as-of "${as_of}")
    fi
    PYTHONPATH="${SRC_ROOT}" PYTHONNOUSERSITE=1 PYTHONSAFEPATH=1 \
        "${VENV}" -B "${PROJECT_ROOT}/scripts/select_a_class_stocks.py" "${args[@]}"
}

cmd_select_mkf() {
    local as_of=""
    local top="20"
    local min_adv20_cny=""
    local selection_profile="standard"
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
            --min-adv20-cny)
                shift
                min_adv20_cny="${1:?--min-adv20-cny requires a number}"
                shift
                ;;
            --selection-profile)
                shift
                selection_profile="${1:?--selection-profile requires a value}"
                shift
                ;;
            *)
                echo "ERROR: unknown select-mkf argument: $1" >&2
                exit 2
                ;;
        esac
    done
    local run_id="mkf-select-$(date +%Y%m%d_%H%M%S)"
    local args=(
        --data-root "${DATA_ROOT}"
        --config "${CONFIG}"
        --output-root "${DEFAULT_OUTPUT_ROOT}/mkf_candidate_selections"
        --run-id "${run_id}"
        --top "${top}"
        --selection-profile "${selection_profile}"
    )
    if [ -n "${min_adv20_cny}" ]; then
        args+=(--min-adv20-cny "${min_adv20_cny}")
    fi
    if [ -n "${as_of}" ]; then
        args+=(--as-of "${as_of}")
    fi
    PYTHONPATH="${SRC_ROOT}" PYTHONNOUSERSITE=1 PYTHONSAFEPATH=1 \
        "${VENV}" -B "${PROJECT_ROOT}/scripts/select_mkf_candidates.py" "${args[@]}"
}

cmd_review_news() {
    local selection_run=""
    local top="20"
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
        --top "${top}"
    )
    if [ -n "${selection_run}" ]; then
        args+=(--selection-run "${selection_run}")
    fi
    PYTHONPATH="${SRC_ROOT}" PYTHONNOUSERSITE=1 PYTHONSAFEPATH=1 \
        "${VENV}" -B "${PROJECT_ROOT}/scripts/review_smc_news.py" "${args[@]}"
}

cmd_review_mkf_ai() {
    local selection_run=""
    local top="20"
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
                echo "ERROR: unknown review-mkf-ai argument: $1" >&2
                exit 2
                ;;
        esac
    done
    if [ ! -f "${MKF_AI_CONFIG}" ]; then
        echo "ERROR: MKF AI 配置不存在：${MKF_AI_CONFIG}" >&2
        exit 1
    fi
    local run_id="mkf-ai-review-$(date +%Y%m%d_%H%M%S)"
    local args=(
        --selection-root "${DEFAULT_OUTPUT_ROOT}/mkf_candidate_selections"
        --output-root "${DEFAULT_OUTPUT_ROOT}/mkf_ai_reviews"
        --config "${MKF_AI_CONFIG}"
        --data-root "${DATA_ROOT}"
        --run-id "${run_id}"
        --top "${top}"
    )
    if [ -n "${selection_run}" ]; then
        args+=(--selection-run "${selection_run}")
    fi
    PYTHONPATH="${SRC_ROOT}" PYTHONNOUSERSITE=1 PYTHONSAFEPATH=1 \
        "${VENV}" -B "${PROJECT_ROOT}/scripts/review_mkf_ai.py" "${args[@]}"
}

cmd_mkf_review() {
    local as_of=""
    local review_top="20"
    local min_adv20_cny=""
    local selection_profile="standard"
    while [ $# -gt 0 ]; do
        case "$1" in
            --as-of)
                shift
                as_of="${1:?--as-of requires YYYY-MM-DD}"
                shift
                ;;
            --top)
                shift
                review_top="${1:?--top requires an integer}"
                shift
                ;;
            --min-adv20-cny)
                shift
                min_adv20_cny="${1:?--min-adv20-cny requires a number}"
                shift
                ;;
            --selection-profile)
                shift
                selection_profile="${1:?--selection-profile requires a value}"
                shift
                ;;
            *)
                echo "ERROR: unknown mkf-review argument: $1" >&2
                return 2
                ;;
        esac
    done

    local selection_args=(--top "${review_top}" --selection-profile "${selection_profile}")
    if [ -n "${min_adv20_cny}" ]; then
        selection_args+=(--min-adv20-cny "${min_adv20_cny}")
    fi
    if [ -n "${as_of}" ]; then
        selection_args+=(--as-of "${as_of}")
    fi

    local selection_output selection_status selection_run signal_date candidate_count selection_csv
    set +e
    selection_output="$(cmd_select_mkf "${selection_args[@]}" 2>&1)"
    selection_status=$?
    set -e
    printf '%s
' "${selection_output}"
    if [ "${selection_status}" -ne 0 ]; then
        return "${selection_status}"
    fi
    signal_date="$(printf '%s
' "${selection_output}" | awk -F= '/^signal_date=/ {value=$2} END {print value}')"
    candidate_count="$(printf '%s
' "${selection_output}" | awk -F= '/^candidate_count=/ {value=$2} END {print value}')"
    selection_run="$(printf '%s
' "${selection_output}" | awk -F= '/^run_directory=/ {value=$2} END {print value}')"
    selection_csv="$(printf '%s
' "${selection_output}" | awk -F= '/^timestamped_csv=/ {value=$2} END {print value}')"
    if [ -z "${selection_run}" ] || [ -z "${candidate_count}" ]; then
        echo "ERROR: MKF 一键流程未能从候选源输出解析 run_directory/candidate_count，拒绝回退到 latest。" >&2
        return 2
    fi

    local review_status_text="skipped_no_candidates"
    local review_run=""
    local review_csv=""
    local news_contexts=""
    local news_cache_dir=""
    local news_cache_status_counts=""
    local priority_count="0"
    local risk_count="0"
    if [ "${candidate_count}" != "0" ]; then
        local review_output review_status review_output_file
        echo
        echo "MKF AI 研究分层：基于本次 MKF 候选源结果生成只读分层..."
        review_output_file="$(mktemp "${TMPDIR:-/tmp}/mkf-review-ai.XXXXXX")"
        set +e
        cmd_review_mkf_ai --selection-run "${selection_run}" --top "${review_top}" 2>&1 | tee "${review_output_file}"
        review_status=${PIPESTATUS[0]}
        set -e
        review_output="$(<"${review_output_file}")"
        rm -f "${review_output_file}"
        local review_summary_status
        review_summary_status="$(printf '%s
' "${review_output}" | awk -F= '/^status=/ {value=$2} END {print value}')"
        review_run="$(printf '%s
' "${review_output}" | awk -F= '/^run_directory=/ {value=$2} END {print value}')"
        review_csv="$(printf '%s
' "${review_output}" | awk -F= '/^timestamped_csv=/ {value=$2} END {print value}')"
        news_contexts="$(printf '%s
' "${review_output}" | awk -F= '/^news_contexts=/ {value=$2} END {print value}')"
        news_cache_dir="$(printf '%s
' "${review_output}" | awk -F= '/^news_cache_dir=/ {value=$2} END {print value}')"
        news_cache_status_counts="$(printf '%s
' "${review_output}" | awk -F= '/^news_cache_status_counts=/ {value=$2} END {print value}')"
        priority_count="$(printf '%s
' "${review_output}" | awk -F= '/^priority_research_count=/ {value=$2} END {print value}')"
        risk_count="$(printf '%s
' "${review_output}" | awk -F= '/^risk_attention_count=/ {value=$2} END {print value}')"
        if [ "${review_status}" -ne 0 ]; then
            if [ "${review_status}" -eq 3 ] && [ -n "${review_run}" ] && [ -n "${review_csv}" ]; then
                review_status_text="${review_summary_status:-partial}"
            else
                return "${review_status}"
            fi
        else
            review_status_text="completed"
        fi
    else
        echo
        echo "MKF AI 研究分层：本次 MKF 候选数为 0，跳过 AI 调用。"
    fi

    echo
    echo "MKF候选源一键流程摘要"
    echo "signal_date=${signal_date}"
    echo "selection_profile=${selection_profile}"
    if [ -n "${min_adv20_cny}" ]; then echo "effective_min_adv20_cny=${min_adv20_cny}"; fi
    echo "mkf_candidate_count=${candidate_count}"
    echo "mkf_selection_run=${selection_run}"
    echo "mkf_selection_csv=${selection_csv}"
    echo "mkf_ai_review=${review_status_text}"
    echo "priority_research_count=${priority_count}"
    echo "risk_attention_count=${risk_count}"
    echo "mkf_ai_run=${review_run}"
    echo "mkf_ai_csv=${review_csv}"
    echo "mkf_news_context=enabled"
    echo "mkf_news_contexts=${news_contexts}"
    echo "mkf_news_cache_dir=${news_cache_dir}"
    echo "mkf_news_cache_status_counts=${news_cache_status_counts}"
    echo "boundary=MKF候选源和AI分层均为独立只读研究实验；不改变 SMC 入选、排序、watchlist、前瞻归档或生产逻辑。"
}

cmd_mkf_review_small() {
    cmd_mkf_review --selection-profile small_capital --min-adv20-cny 50000000 "$@"
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
    PYTHONPATH="${SRC_ROOT}" PYTHONNOUSERSITE=1 PYTHONSAFEPATH=1 \
        "${VENV}" -B "${PROJECT_ROOT}/scripts/analyze_post_smc_recommendation.py" "${args[@]}"
}

# ---------------------------------------------------------------------------
# 测试
# ---------------------------------------------------------------------------
cmd_test() {
    echo "=============================================="
    echo " Edge Scout 测试"
    echo "=============================================="

    local pattern="${1:-}"
    # 确保 pytest 在 src 目录查找测试文件
    cd "${PROJECT_ROOT}"
    shift 2>/dev/null || true
    if [ -z "${pattern}" ]; then
        PYTHONPATH="${SRC_ROOT}" \
            PYTHONNOUSERSITE=1 \
            "${VENV}" -B -m pytest tests/test_edge_scout_*.py -q --tb=short
    else
        PYTHONPATH="${SRC_ROOT}" \
            PYTHONNOUSERSITE=1 \
            "${VENV}" -B -m pytest "${pattern}" -q --tb=short "$@"
    fi
}

cmd_audit() {
    local audit_dir="${DEFAULT_OUTPUT_ROOT}/prospective_audits"
    local audit_path="${audit_dir}/audit-$(date -u +%Y%m%dT%H%M%SZ).json"
    mkdir -p "${audit_dir}"
    PYTHONPATH="${SRC_ROOT}" \
        PYTHONNOUSERSITE=1 \
        PYTHONSAFEPATH=1 \
        "${VENV}" -B "${PROJECT_ROOT}/scripts/audit_prospective_watchlist.py" \
        --output-root "${DEFAULT_OUTPUT_ROOT}" \
        --data-root "${DATA_ROOT}" \
        --output "${audit_path}"
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
    PYTHONPATH="${SRC_ROOT}" \
        PYTHONNOUSERSITE=1 \
        PYTHONSAFEPATH=1 \
        "${VENV}" -B "${PROJECT_ROOT}/scripts/archive_smc_news_prospective.py" "${args[@]}"
}

cmd_archive_smc_news_preflight() {
    local selection_run="${1:?selection run required}"
    PYTHONPATH="${SRC_ROOT}" \
        PYTHONNOUSERSITE=1 \
        PYTHONSAFEPATH=1 \
        "${VENV}" -B "${PROJECT_ROOT}/scripts/archive_smc_news_prospective.py" \
        --selection-root "${DEFAULT_OUTPUT_ROOT}/selections" \
        --output-root "${DEFAULT_OUTPUT_ROOT}/smc_news_prospective" \
        --selection-run "${selection_run}" \
        --check-existing-signal-date
}

cmd_daily() {
    local review_top="20"
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

    local selection_output selection_status selection_run signal_date selection_count selection_csv human_review_summary_csv
    set +e
    selection_output="$(cmd_select --top "${review_top}" 2>&1)"
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
    local priority_count="0"
    local risk_count="0"
    local archive_status="skipped_existing_signal_date"
    local archive_path="${existing_archive}"
    if [ "${archive_duplicate}" != "1" ]; then
        local news_output news_status archive_output archive_exit
        echo
        echo "SMC 新闻 AI 二次复核：开始分析本次 daily 选股结果..."
        set +e
        news_output="$(cmd_review_news --selection-run "${selection_run}" --top "${review_top}" 2>&1)"
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
    echo "human_review_note=新闻 AI 仅供人工复核参考，未验证，不改变 SMC 入选、排序、阈值或生产逻辑。"
    echo "boundary=只读研究扫描；不连接券商；不提交订单；不计算 P&L/收益；不构成个性化建议。"
}

cmd_audit_smc_news_prospective() {
    local audit_dir="${DEFAULT_OUTPUT_ROOT}/smc_news_prospective_audits"
    local audit_path="${audit_dir}/smc-news-audit-$(date -u +%Y%m%dT%H%M%SZ).json"
    mkdir -p "${audit_dir}"
    PYTHONPATH="${SRC_ROOT}" \
        PYTHONNOUSERSITE=1 \
        PYTHONSAFEPATH=1 \
        "${VENV}" -B "${PROJECT_ROOT}/scripts/audit_smc_news_prospective.py" \
        --output-root "${DEFAULT_OUTPUT_ROOT}" \
        --data-root "${DATA_ROOT}" \
        --output "${audit_path}"
}

cmd_replay_smc_news() {
    local args=(
        --selection-root "${DEFAULT_OUTPUT_ROOT}/selections"
        --news-root "${DEFAULT_OUTPUT_ROOT}/news_reviews"
        --cache-root "${PROJECT_ROOT}/.runtime/news_cache"
        --data-root "${DATA_ROOT}"
        --output-root "${DEFAULT_OUTPUT_ROOT}/smc_news_replay"
    )
    args+=("$@")
    PYTHONPATH="${SRC_ROOT}" \
        PYTHONNOUSERSITE=1 \
        PYTHONSAFEPATH=1 \
        "${VENV}" -B "${PROJECT_ROOT}/scripts/replay_smc_news.py" "${args[@]}"
}

# ---------------------------------------------------------------------------
# 帮助
# ---------------------------------------------------------------------------
cmd_help() {
    cat <<'HELP'

Edge Scout 一键扫描脚本
A 股多因子 + 15 日蜡烛图短线研究系统

用法：
  edge_scout_scan.sh                        # 先按需增量更新，再执行全市场扫描
  edge_scout_scan.sh market [--as-of YYYY-MM-DD] [输出目录]
      全市场扫描，输出只读研究观察样本（有效 setup 确认优先）

  edge_scout_scan.sh single <股票代码> [--as-of YYYY-MM-DD]
  edge_scout_scan.sh <股票代码> [--as-of YYYY-MM-DD]
      单股分析，输出该股票的评分与分层（默认自动回退 2 个交易日）

  edge_scout_scan.sh select [--as-of YYYY-MM-DD] [--top N]
      使用现有本地日线运行 SMC 只读选股，不需要分钟或付费数据

  edge_scout_scan.sh daily [--top N]
      每日 SMC+新闻一键流程：自动更新/选股/去重/复核/归档/审计，并输出人工复核摘要

  edge_scout_scan.sh select-review [--as-of YYYY-MM-DD] [--top N] [--post-smc-analysis|--no-post-smc-analysis]
      自动日期运行会冻结前瞻证据；手动 --as-of 仅做选股和复核，不进入前瞻归档

  edge_scout_scan.sh post-smc-analysis --selection-run DIR [--news-run DIR] [--top N]
      基于已冻结 SMC/可选新闻复核结果生成只读人工复核建议分析 CSV

  edge_scout_scan.sh select-a-class [--as-of YYYY-MM-DD] [--top N]
      运行独立 A 类低位启动只读扫描，不影响 SMC 候选

  edge_scout_scan.sh mkf-review [--as-of YYYY-MM-DD] [--top N]
      MKF 一键流程：候选源扫描后对本次候选做 AI 只读研究分层；无候选则跳过 AI

  edge_scout_scan.sh mkf-review-small [--as-of YYYY-MM-DD] [--top N]
      MKF 小资金一键流程：主板/非ST等硬门槛不变，ADV20 降为 5000 万

  edge_scout_scan.sh select-mkf [--as-of YYYY-MM-DD] [--top N]
      运行独立 MKF 红蓝线上穿20候选源实验，不影响 SMC 候选

  edge_scout_scan.sh review-mkf-ai [--selection-run DIR] [--top N]
      对指定或最新 MKF 候选源实验做只读 AI 研究分层，不写入 SMC 流程

  edge_scout_scan.sh review-news [--selection-run DIR] [--top N]
      复核指定或最新 SMC 结果；--top 仅限制终端展示，JSON/CSV 保存完整候选复核

  edge_scout_scan.sh test [测试模式]
      运行 Edge Scout 相关测试

  edge_scout_scan.sh update
      只检查并按需增量更新本地数据，不运行扫描

  edge_scout_scan.sh archive-smc-news
      冻结最新 SMC 选股和新闻 AI 复核状态，供未来成熟度审计使用

  edge_scout_scan.sh audit-smc-news
      生成新的 SMC 选股 + 新闻 AI 复核前瞻成熟度审计 JSON

  edge_scout_scan.sh replay-smc-news [--dry-run] [--start-date YYYY-MM-DD] [--end-date YYYY-MM-DD]
      生成 simulation_only SMC+新闻历史回放，不写前瞻归档、不声明前瞻证据

  edge_scout_scan.sh audit
      生成新的不可覆盖前瞻观察成熟度审计 JSON

参数：
  股票代码格式：600519（自动补全为 sh.600519）、000858（自动补全为 sz.000858），
  也可直接输入 sh.600519、sz.000858
  数据目录    ：默认 <项目>/PFrontStockData/，可用 EDGE_SCOUT_DATA_ROOT 覆盖
  自动更新    ：默认开启；EDGE_SCOUT_AUTO_UPDATE=0 可跳过联网检查和下载
  最新覆盖率  ：默认至少 95%；可用 EDGE_SCOUT_MINIMUM_LATEST_COVERAGE 覆盖

说明：
  默认扫描日期 = 最新数据日回退 2 个交易日（T 信号日）。
  TOP 表中的 ✓ 仅表示 T 日 setup 有效且 T+1 价格/量能研究观察通过。
  T+2 仅进入人工观察阶段，不代表可成交或应入场。
  触发参考为 T 日 signal_high 前复权研究近似价，非执行价，不构成投资建议。

示例：
  edge_scout_scan.sh                        # 远端有新交易日才增量下载，然后扫描
  edge_scout_scan.sh 600519                 # 单股分析，自动补全为 sh.600519
  edge_scout_scan.sh 000001 --as-of 2026-07-24  # 单股分析，自动补全为 sz.000001，覆盖 T 信号日
  edge_scout_scan.sh single sh.600519
  edge_scout_scan.sh single sh.600519 --as-of 2026-07-24  # 可选：覆盖日期
  edge_scout_scan.sh market                                # 默认自动回退 2 个交易日
  edge_scout_scan.sh market --as-of 2026-07-24             # 可选：覆盖 T 信号日
  edge_scout_scan.sh daily --top 10                        # 每日 SMC+新闻一键流程，重复信号日自动跳过归档
  edge_scout_scan.sh select-review --post-smc-analysis      # 选股+新闻复核后额外保存只读人工复核建议分析CSV
  edge_scout_scan.sh mkf-review --top 10                    # MKF 候选源 + AI 分层一键流程
  edge_scout_scan.sh mkf-review-small --top 10              # MKF 小资金候选源 + AI 分层一键流程
  edge_scout_scan.sh select-mkf --top 10                    # 独立 MKF 候选源实验
  edge_scout_scan.sh review-mkf-ai --selection-run <DIR>    # MKF 候选源 AI 研究分层
  edge_scout_scan.sh test
  edge_scout_scan.sh archive-smc-news
  edge_scout_scan.sh audit-smc-news
  edge_scout_scan.sh replay-smc-news --dry-run
  edge_scout_scan.sh audit

边界：
  - 只读研究扫描
  - 不连接券商
  - 不提交真实订单
  - 不构成投资建议

HELP
}

# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------
main() {
    local first="${1:-}"

    case "${first}" in
        market)
            check_runtime_prereqs
            auto_update_data
            check_data_root
            shift
            cmd_market "$@"
            ;;
        single)
            check_runtime_prereqs
            auto_update_data
            check_data_root
            shift
            cmd_single "$@"
            ;;
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
        select-a-class)
            check_runtime_prereqs
            auto_update_data
            check_data_root
            shift
            cmd_select_a_class "$@"
            ;;
        mkf-review)
            check_runtime_prereqs
            auto_update_data
            check_data_root
            shift
            cmd_mkf_review "$@"
            ;;
        mkf-review-small)
            check_runtime_prereqs
            auto_update_data
            check_data_root
            shift
            cmd_mkf_review_small "$@"
            ;;
        select-mkf)
            check_runtime_prereqs
            auto_update_data
            check_data_root
            shift
            cmd_select_mkf "$@"
            ;;
        review-mkf-ai)
            check_runtime_prereqs
            check_data_root
            shift
            cmd_review_mkf_ai "$@"
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
        test)
            check_runtime_prereqs
            shift
            cmd_test "$@"
            ;;
        update)
            check_runtime_prereqs
            auto_update_data
            check_data_root
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
        audit)
            check_runtime_prereqs
            check_data_root
            cmd_audit
            ;;
        help|-h|--help)
            cmd_help
            ;;
        "")
            check_runtime_prereqs
            auto_update_data
            check_data_root
            cmd_market
            ;;
        *)
            check_runtime_prereqs
            auto_update_data
            check_data_root
            cmd_single "$@"
            ;;
    esac
}

main "$@"
