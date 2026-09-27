#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCAN_CONTROL="${EDGE_SCOUT_SCAN_SCRIPT:-${PROJECT_ROOT}/scripts/edge_scout_scan.sh}"
VENV="${VENV_PYTHON:-${PROJECT_ROOT}/.venv/bin/python}"
# 与 mkf.sh 相同的底层扫描/新闻/AI 机制；所有输出改落 smc-output 目录。
SMC_OUTPUT_ROOT="${EDGE_SCOUT_SMC_OUTPUT_ROOT:-${PROJECT_ROOT}/smc-output}"
export EDGE_SCOUT_OUTPUT_ROOT="${SMC_OUTPUT_ROOT}"
ACTION="${1:-menu}"

if [ ! -x "${SCAN_CONTROL}" ]; then
    printf 'ERROR: 底层扫描脚本不存在或不可执行：%s\n' "${SCAN_CONTROL}" >&2
    exit 1
fi

latest_smc_selection_run() {
    find "${SMC_OUTPUT_ROOT}/selections" -maxdepth 1 -type d -name 'select-*' 2>/dev/null | sort | tail -1
}

# 把 SMC 选股 run 桥接成 MKF AI 分层可校验的只读输入（不改原 run，真实来源写入 manifest）。
bridge_smc_run_to_layer_dir() {
    local selection_run="$1"
    local bridge_id="smc-layer-$(date +%Y%m%d_%H%M%S)"
    local bridge_dir="${SMC_OUTPUT_ROOT}/smc_ai_layer_runs/${bridge_id}"
    "${VENV}" -B - "${selection_run}" "${bridge_dir}" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

MKF_SCHEMA = "ncn_mkf_candidate_selector_v6"
run_dir, bridge_dir = Path(sys.argv[1]), Path(sys.argv[2])
candidates = json.loads((run_dir / "candidates.json").read_text(encoding="utf-8"))
origin_manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
signal_date = str(candidates[0].get("signal_date") or "") if candidates else ""
bridge_dir.mkdir(parents=True, exist_ok=False)
payload = json.dumps(candidates, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
(bridge_dir / "candidates.json").write_text(payload, encoding="utf-8")
sha = hashlib.sha256(payload.encode("utf-8")).hexdigest()
summary = {
    "schema_version": MKF_SCHEMA,
    "candidate_count": len(candidates),
    "signal_date": signal_date,
    "selection_origin": origin_manifest.get("schema_version", "unknown"),
    "selection_run": str(run_dir),
    "note": "SMC 扫描候选只读桥接，用于 MKF 同款新闻抓取与 AI 委员会分层；候选本身未被修改。",
}
manifest = {
    "schema_version": MKF_SCHEMA,
    "files": {"candidates.json": {"sha256": sha}},
    "bridge": {
        "origin_schema_version": origin_manifest.get("schema_version", "unknown"),
        "origin_run_directory": str(run_dir),
        "candidates_sha256_of_origin": (origin_manifest.get("files", {}).get("candidates.json", {}) or {}).get("sha256"),
    },
}
(bridge_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
(bridge_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(f"bridge_run_directory={bridge_dir}")
print(f"candidate_count={len(candidates)}")
print(f"signal_date={signal_date}")
PY
}

run_smc_layer() {
    local selection_run=""
    local top_args=()
    while [ $# -gt 0 ]; do
        case "$1" in
            --selection-run)
                selection_run="${2:?--selection-run requires a directory}"
                shift 2
                ;;
            --top)
                top_args=(--top "${2:?--top requires an integer}")
                shift 2
                ;;
            *)
                printf 'ERROR: 未知 SMC AI 分层参数：%s\n' "$1" >&2
                return 2
                ;;
        esac
    done
    if [ -z "${selection_run}" ]; then
        selection_run="$(latest_smc_selection_run || true)"
    fi
    if [ -z "${selection_run}" ] || [ ! -d "${selection_run}" ]; then
        printf 'ERROR: 未找到 SMC 选股结果；请先运行 ./smc.sh smc-select 或使用 --selection-run DIR。\n' >&2
        return 2
    fi
    local bridge_output bridge_dir candidate_count
    bridge_output="$(bridge_smc_run_to_layer_dir "${selection_run}")"
    printf '%s\n' "${bridge_output}"
    bridge_dir="$(printf '%s\n' "${bridge_output}" | awk -F= '/^bridge_run_directory=/ {value=$2} END {print value}')"
    candidate_count="$(printf '%s\n' "${bridge_output}" | awk -F= '/^candidate_count=/ {value=$2} END {print value}')"
    if [ "${candidate_count}" = "0" ]; then
        printf '\nSMC 候选数为 0，跳过 MKF 同款 AI 分层调用。\n'
        return 0
    fi
    printf '\nSMC 候选 AI 研究分层：使用与 mkf.sh 相同的新闻抓取 + AI 委员会机制（只读）...\n'
    "${SCAN_CONTROL}" review-mkf-ai --selection-run "${bridge_dir}" "${top_args[@]}"
}

run_smc_review() {
    local selection_output selection_status selection_run candidate_count
    set +e
    selection_output="$("${SCAN_CONTROL}" select "$@")"
    selection_status=$?
    set -e
    printf '%s\n' "${selection_output}"
    if [ "${selection_status}" -ne 0 ]; then
        return "${selection_status}"
    fi
    selection_run="$(printf '%s\n' "${selection_output}" | awk -F= '/^run_directory=/ {value=$2} END {print value}')"
    candidate_count="$(printf '%s\n' "${selection_output}" | awk -F= '/^candidate_count=/ {value=$2} END {print value}')"
    if [ -z "${selection_run}" ]; then
        printf 'ERROR: 未能从 SMC 选股输出解析 run_directory。\n' >&2
        return 2
    fi
    if [ "${candidate_count}" = "0" ]; then
        printf '\nSMC 候选数为 0，跳过 MKF 同款 AI 分层调用。\n'
    else
        run_smc_layer --selection-run "${selection_run}"
    fi
    printf '\nSMC 一键流程摘要\nselection_run=%s\nsmc_output_root=%s\nboundary=只读研究分层；不改 SMC 入选、排序、watchlist、前瞻归档或生产逻辑。\n' "${selection_run}" "${SMC_OUTPUT_ROOT}"
}

run_menu() {
    if [ ! -t 0 ] || [ ! -t 1 ]; then
        printf 'ERROR: SMC 交互菜单需要在终端中运行；自动化请使用 ./smc.sh help 查看命令。\n' >&2
        return 2
    fi

    local options=(
        "SMC一键流程（自动更新/新闻抓取+AI委员会分层，与mkf.sh同款）"
        "SMC一键流程（自动更新/SMC原生新闻AI复核+前瞻归档）"
        "SMC选股（自动更新数据）"
        "SMC选股（仅本地数据）"
        "SMC候选AI研究分层（最新SMC选股）"
        "退出"
    )
    local actions=(
        "smc-review"
        "smc-review-native"
        "smc-select"
        "smc-select-local"
        "smc-layer"
        "exit"
    )
    local selected=0
    local key sequence

    menu_next_selectable() {
        local current="$1"
        local direction="$2"
        local count="${#actions[@]}"
        current=$(((current + direction + count) % count))
        printf '%s' "${current}"
    }

    while true; do
        printf '\033[2J\033[H'
        printf 'NCN SMC 研究\n'
        printf '使用 ↑/↓ 选择，回车确认，q 退出\n\n'
        local index
        for index in "${!options[@]}"; do
            if [ "${index}" -eq "${selected}" ]; then
                printf '\033[7m  > %s  \033[0m\n' "${options[$index]}"
            else
                printf '    %s\n' "${options[$index]}"
            fi
        done

        IFS= read -rsn1 key
        if [ "${key}" = $'\033' ]; then
            IFS= read -rsn2 sequence || true
            case "${sequence}" in
                "[A"|"OA") selected="$(menu_next_selectable "${selected}" -1)" ;;
                "[B"|"OB") selected="$(menu_next_selectable "${selected}" 1)" ;;
            esac
            continue
        fi
        if [ "${key}" = "q" ] || [ "${key}" = "Q" ]; then
            printf '\033[2J\033[H已退出。\n'
            return 0
        fi
        if [ -z "${key}" ]; then
            printf '\033[2J\033[H'
            local result=0
            local action="${actions[$selected]}"
            execute_menu_choice "${action}" || result=$?
            if [ "${action}" = "exit" ]; then
                return "${result}"
            fi
            printf '\n按回车返回 SMC 菜单...'
            IFS= read -r
        fi
    done
}

execute_menu_choice() {
    local action="$1"
    case "${action}" in
        smc-review) run_smc_review ;;
        smc-review-native) "${SCAN_CONTROL}" select-review ;;
        smc-select) "${SCAN_CONTROL}" select ;;
        smc-select-local) EDGE_SCOUT_AUTO_UPDATE=0 "${SCAN_CONTROL}" select ;;
        smc-layer) run_smc_layer ;;
        exit) printf '已退出。\n' ;;
    esac
}

case "${ACTION}" in
    menu)
        run_menu
        ;;
    smc-review)
        shift
        run_smc_review "$@"
        ;;
    smc-review-native)
        shift
        exec "${SCAN_CONTROL}" select-review "$@"
        ;;
    smc-select)
        shift
        exec "${SCAN_CONTROL}" select "$@"
        ;;
    smc-select-local)
        shift
        export EDGE_SCOUT_AUTO_UPDATE=0
        exec "${SCAN_CONTROL}" select "$@"
        ;;
    smc-layer)
        shift
        run_smc_layer "$@"
        ;;
    review-news)
        shift
        exec "${SCAN_CONTROL}" review-news "$@"
        ;;
    help|-h|--help)
        printf '%s\n' \
            'NCN SMC 研究入口（输出全部保存在 smc-output/）' \
            '' \
            '用法：' \
            '  ./smc.sh                              打开方向键交互菜单' \
            '  ./smc.sh smc-review [--as-of DATE] [--top N]  SMC选股+MKF同款新闻抓取+AI委员会分层 一键流程（自动更新）' \
            '  ./smc.sh smc-review-native            SMC一键流程（SMC原生新闻AI复核+前瞻归档）' \
            '  ./smc.sh smc-select [--as-of DATE]    仅运行 SMC 选股（自动更新数据）' \
            '  ./smc.sh smc-select-local             仅用本地数据运行 SMC 选股' \
            '  ./smc.sh smc-layer [--selection-run DIR] [--top N]  对最新（或指定）SMC 选股运行 MKF 同款 AI 分层' \
            '  ./smc.sh review-news [--selection-run DIR] [--top N]  SMC 原生新闻 AI 复核（Google新闻+东财公告）' \
            '' \
            '机制说明：' \
            '  AI 使用 yaml/ai_providers.yaml（与 mkf.sh 的分层同一 provider/model 选择）；' \
            '  新闻抓取使用与 mkf.sh 相同的 MKF 新闻通道（Google News RSS/东财，Message/ 缓存），SMC 原生复核走 review-news 同款来源。' \
            '输出目录：' \
            '  smc-output/selections           SMC 选股不可变 run' \
            '  smc-output/smc_ai_layer_runs    SMC→AI分层只读桥接 run' \
            '  smc-output/mkf_ai_reviews       MKF 同款 AI 委员会分层结果' \
            '  smc-output/news_reviews         SMC 原生新闻 AI 复核结果' \
            '  smc-output/smc_news_prospective  新闻前瞻证据归档（select-review）' \
            '' \
            '边界：只读研究分层；不改 SMC 入选、排序、watchlist、前瞻归档或生产逻辑；不连接券商、不提交订单。'
        ;;
    *)
        printf 'ERROR: 未知 SMC 命令：%s\n请运行 ./smc.sh help 查看用法。\n' "${ACTION}" >&2
        exit 2
        ;;
esac
