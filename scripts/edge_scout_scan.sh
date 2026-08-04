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
# 数据目录：本项目内的前复权研究数据；迁移期可通过环境变量覆盖。
DATA_ROOT="${EDGE_SCOUT_DATA_ROOT:-${PROJECT_ROOT}/PFrontStockData}"
CONFIG="${EDGE_SCOUT_CONFIG:-${PROJECT_ROOT}/yaml/edge_scout_v1.yaml}"
BAOSTOCK_CONFIG="${EDGE_SCOUT_BAOSTOCK_CONFIG:-${PROJECT_ROOT}/yaml/baostock_config.yaml}"
VENV="${VENV_PYTHON:-${PROJECT_ROOT}/.venv/bin/python}"
AUTO_UPDATE="${EDGE_SCOUT_AUTO_UPDATE:-1}"
DOWNLOAD_WORKERS="${EDGE_SCOUT_DOWNLOAD_WORKERS:-}"
MAX_FAILURE_RATE="${EDGE_SCOUT_DOWNLOAD_MAX_FAILURE_RATE:-0.10}"
MINIMUM_LATEST_COVERAGE="${EDGE_SCOUT_MINIMUM_LATEST_COVERAGE:-0.95}"

# 默认日期（最近交易日），可通过 $1 覆盖
DEFAULT_AS_OF="${1:-}"

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
    if [ ! -f "${VENV}" ]; then
        echo "ERROR: 虚拟环境不存在，请先运行：cd ${PROJECT_ROOT} && python -m venv .venv && source .venv/bin/activate && pip install -e ." >&2
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

  edge_scout_scan.sh test [测试模式]
      运行 Edge Scout 相关测试

  edge_scout_scan.sh update
      只检查并按需增量更新本地数据，不运行扫描

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
  edge_scout_scan.sh test

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
