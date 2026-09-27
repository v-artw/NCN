#!/usr/bin/env bash
set -euo pipefail

# aismc.sh — SMC 候选源 + MKF 同款一键流程（完全复制 mkf.sh 的成熟逻辑）：
#   股票数据下载  = 主仓 edge_scout_scan.sh 的 BaoStock 自动更新（与 mkf.sh 完全同一代码路径）
#   新闻/公报抓取 = mkf_news_context（Google News RSS / 东财新闻 / 东财公告，Message/ 缓存）
#   AI 分析       = smc/yaml/smc_ai_review.yaml SMC 专用委员会提示词 + smc/yaml/ai_providers.yaml 同一模型，走与 MKF 同一 review-mkf-ai 管线
#   MD 文件       = 主仓 scripts/export_scan_csv_for_web_ai.py（与 MKF "候选CSV导出Web AI Markdown" 同一逻辑）
#   小资金口径    = ADV20 降为 5000 万（复用 smc/yaml/edge_scout_v1.yaml 全部内容，仅覆盖 universe.min_adv20_cny）
# 所有输出保存在仓库根 smc-output/；smc/ 子项目对主仓仅单向只读依赖（smc -> main）。

SMC_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SMC_ROOT}/.." && pwd)"
# 主仓 hub：仅用于 review-mkf-ai / export-mkf-web-ai / update（smc -> main 允许方向）。
SCAN_CONTROL="${EDGE_SCOUT_SCAN_SCRIPT:-${REPO_ROOT}/scripts/edge_scout_scan.sh}"
# SMC 自有控制脚本：select 走这里（smc/scripts/select_stocks.py + smc/src/ashare_smc）。
SMC_CONTROL="${SMC_SCAN_SCRIPT:-${SMC_ROOT}/scripts/smc_scan.sh}"
VENV="${VENV_PYTHON:-${REPO_ROOT}/.venv/bin/python}"
AI_SMC_OUTPUT_ROOT="${EDGE_SCOUT_AI_SMC_OUTPUT_ROOT:-${REPO_ROOT}/smc-output}"
BASE_CONFIG="${EDGE_SCOUT_CONFIG:-${SMC_ROOT}/yaml/edge_scout_v1.yaml}"
SMALL_ADV20_CNY="50000000"
SMALL_CONFIG="${AI_SMC_OUTPUT_ROOT}/config/edge_scout_v1_small_adv20_${SMALL_ADV20_CNY}.yaml"
# SMC 专用 AI 委员会：与 mkf.sh 使用 yaml/mkf_ai_review.yaml 同样的方式，使用 smc/yaml/smc_ai_review.yaml。
AI_SMC_REVIEW_CONFIG="${EDGE_SCOUT_SMC_AI_CONFIG:-${SMC_ROOT}/yaml/smc_ai_review.yaml}"
export EDGE_SCOUT_OUTPUT_ROOT="${AI_SMC_OUTPUT_ROOT}"
ACTION="${1:-menu}"

if [ ! -x "${SCAN_CONTROL}" ]; then
    printf 'ERROR: 底层扫描脚本不存在或不可执行：%s\n' "${SCAN_CONTROL}" >&2
    exit 1
fi
if [ ! -x "${SMC_CONTROL}" ]; then
    printf 'ERROR: SMC 控制脚本不存在或不可执行：%s\n' "${SMC_CONTROL}" >&2
    exit 1
fi
if [ ! -f "${AI_SMC_REVIEW_CONFIG}" ]; then
    printf 'ERROR: SMC 专用 AI 委员会配置不存在：%s\n' "${AI_SMC_REVIEW_CONFIG}" >&2
    exit 1
fi

# 与 edge_scout_scan.sh 相同读取方式：review.max_candidates 来自 yaml/mkf_ai_review.yaml。
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

# 复用 yaml/edge_scout_v1.yaml 全部内容，仅把 universe.min_adv20_cny 覆盖为 5000 万。
ensure_small_config() {
    mkdir -p "$(dirname "${SMALL_CONFIG}")"
    "${VENV}" -B - "${BASE_CONFIG}" "${SMALL_CONFIG}" "${SMALL_ADV20_CNY}" <<'PY'
import sys
from pathlib import Path

import yaml

base_path, out_path, adv20 = Path(sys.argv[1]), Path(sys.argv[2]), float(sys.argv[3])
config = yaml.safe_load(base_path.read_text(encoding="utf-8"))
config.setdefault("universe", {})["min_adv20_cny"] = adv20
header = (
    f"# 自动生成：完整复用 {base_path.name} 内容，仅覆盖 universe.min_adv20_cny={adv20:.0f}（aismc.sh 小资金口径）。\n"
    "# 该文件位于 smc-output/，不修改任何已提交配置。\n"
)
out_path.write_text(header + yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8")
print(f"small_config={out_path}")
print(f"effective_min_adv20_cny={adv20:.0f}")
PY
}

latest_smc_selection_run() {
    find "${AI_SMC_OUTPUT_ROOT}/selections" -maxdepth 1 -type d -name 'select-*' 2>/dev/null | sort | tail -1
}

latest_smc_selection_csv() {
    local run_dir
    run_dir="$(latest_smc_selection_run || true)"
    if [ -z "${run_dir}" ] || [ ! -d "${run_dir}" ]; then
        return 0
    fi
    find "${run_dir}" -maxdepth 1 -type f -name 'smc_candidates_*.csv' | sort | tail -1
}

# 把 SMC 选股 run 桥接成 MKF AI 分层可校验的只读输入（候选原样复制，真实来源写入 manifest）。
bridge_smc_run_to_layer_dir() {
    local selection_run="$1"
    local bridge_id="aismc-layer-$(date +%Y%m%d_%H%M%S)"
    local bridge_dir="${AI_SMC_OUTPUT_ROOT}/smc_ai_layer_runs/${bridge_id}"
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

run_layer() {
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
                printf 'ERROR: 未知 AI 分层参数：%s\n' "$1" >&2
                return 2
                ;;
        esac
    done
    if [ -z "${selection_run}" ]; then
        selection_run="$(latest_smc_selection_run || true)"
    fi
    if [ -z "${selection_run}" ] || [ ! -d "${selection_run}" ]; then
        printf 'ERROR: 未找到 SMC 选股结果；请先运行 ./aismc.sh select 或使用 --selection-run DIR。\n' >&2
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
    printf '\nSMC 候选 AI 研究分层：MKF 同款新闻/公报抓取 + SMC 专用 AI 委员会（smc/yaml/smc_ai_review.yaml，只读）...\n'
    EDGE_SCOUT_MKF_AI_CONFIG="${AI_SMC_REVIEW_CONFIG}" "${SCAN_CONTROL}" review-mkf-ai --selection-run "${bridge_dir}" "${top_args[@]}"
}

run_select() {
    local profile="standard"
    local auto_update="1"
    local pass_args=()
    while [ $# -gt 0 ]; do
        case "$1" in
            --small) profile="small_capital"; shift ;;
            --local) auto_update="0"; shift ;;
            *) pass_args+=("$1"); shift ;;
        esac
    done
    local config="${BASE_CONFIG}"
    if [ "${profile}" = "small_capital" ]; then
        ensure_small_config > /dev/null
        config="${SMALL_CONFIG}"
    fi
    if [ "${auto_update}" = "1" ]; then
        EDGE_SCOUT_CONFIG="${config}" "${SMC_CONTROL}" select "${pass_args[@]+"${pass_args[@]}"}"
    else
        EDGE_SCOUT_AUTO_UPDATE=0 EDGE_SCOUT_CONFIG="${config}" "${SMC_CONTROL}" select "${pass_args[@]+"${pass_args[@]}"}"
    fi
}

run_export_md() {
    local csv_path=""
    local pass_args=()
    while [ $# -gt 0 ]; do
        case "$1" in
            --csv)
                csv_path="${2:?--csv requires a path}"
                shift 2
                ;;
            *) pass_args+=("$1"); shift ;;
        esac
    done
    if [ -z "${csv_path}" ]; then
        csv_path="$(latest_smc_selection_csv || true)"
    fi
    if [ -z "${csv_path}" ] || [ ! -f "${csv_path}" ]; then
        printf 'ERROR: 未找到 SMC 候选 CSV；请先运行 ./aismc.sh select 或使用 --csv PATH。\n' >&2
        return 2
    fi
    # 与 mkf.sh "MKF候选CSV导出Web AI Markdown" 完全同一脚本，仅输入换成 SMC 候选 CSV。
    "${SCAN_CONTROL}" export-mkf-web-ai --csv "${csv_path}" --max-bytes 4000 "${pass_args[@]+"${pass_args[@]}"}"
}

run_one_key() {
    local profile="standard"
    local review_top=""
    local pass_args=()
    while [ $# -gt 0 ]; do
        case "$1" in
            --small) profile="small_capital"; shift ;;
            --top)
                review_top="${2:?--top requires an integer}"
                shift 2
                ;;
            *) pass_args+=("$1"); shift ;;
        esac
    done
    local effective_top="${review_top:-$(read_review_max_candidates "${AI_SMC_REVIEW_CONFIG}")}"
    local select_args=(--top "${effective_top}")
    if [ "${profile}" = "small_capital" ]; then
        select_args=(--small "${select_args[@]}")
    fi

    local selection_output selection_status selection_output_file
    if [ "${profile}" = "small_capital" ]; then
        printf '\n[1/3] SMC 小资金选股：检查数据更新并扫描全主板（小资金口径，约需2-3分钟，进度实时显示）...\n'
    else
        printf '\n[1/3] SMC 标准选股：检查数据更新并扫描全主板（约需2-3分钟，进度实时显示）...\n'
    fi
    selection_output_file="$(mktemp "${TMPDIR:-/tmp}/aismc-select.XXXXXX")"
    set +e
    run_select "${select_args[@]}" "${pass_args[@]+"${pass_args[@]}"}" 2>&1 | tee "${selection_output_file}"
    selection_status=${PIPESTATUS[0]}
    set -e
    selection_output="$(<"${selection_output_file}")"
    rm -f "${selection_output_file}"
    if [ "${selection_status}" -ne 0 ]; then
        return "${selection_status}"
    fi
    local selection_run candidate_count signal_date selection_csv
    signal_date="$(printf '%s\n' "${selection_output}" | awk -F= '/^signal_date=/ {value=$2} END {print value}')"
    candidate_count="$(printf '%s\n' "${selection_output}" | awk -F= '/^candidate_count=/ {value=$2} END {print value}')"
    selection_run="$(printf '%s\n' "${selection_output}" | awk -F= '/^run_directory=/ {value=$2} END {print value}')"
    selection_csv="$(printf '%s\n' "${selection_output}" | awk -F= '/^timestamped_csv=/ {value=$2} END {print value}')"
    if [ -z "${selection_run}" ] || [ -z "${candidate_count}" ]; then
        printf 'ERROR: 一键流程未能从 SMC 候选源输出解析 run_directory/candidate_count，拒绝回退到 latest。\n' >&2
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
        printf '\n[2/3] SMC AI 研究分层：MKF 同款新闻/公报抓取 + AI 委员会逐只分析（约30-60秒/只，共 %s 只，请耐心等待）...\n' "${candidate_count}"
        review_output_file="$(mktemp "${TMPDIR:-/tmp}/aismc-review-ai.XXXXXX")"
        set +e
        run_layer --selection-run "${selection_run}" --top "${effective_top}" 2>&1 | tee "${review_output_file}"
        review_status=${PIPESTATUS[0]}
        set -e
        review_output="$(<"${review_output_file}")"
        rm -f "${review_output_file}"
        local review_summary_status
        review_summary_status="$(printf '%s\n' "${review_output}" | awk -F= '/^status=/ {value=$2} END {print value}')"
        review_run="$(printf '%s\n' "${review_output}" | awk -F= '/^run_directory=/ {value=$2} END {print value}')"
        review_csv="$(printf '%s\n' "${review_output}" | awk -F= '/^timestamped_csv=/ {value=$2} END {print value}')"
        news_contexts="$(printf '%s\n' "${review_output}" | awk -F= '/^news_contexts=/ {value=$2} END {print value}')"
        news_cache_dir="$(printf '%s\n' "${review_output}" | awk -F= '/^news_cache_dir=/ {value=$2} END {print value}')"
        news_cache_status_counts="$(printf '%s\n' "${review_output}" | awk -F= '/^news_cache_status_counts=/ {value=$2} END {print value}')"
        priority_count="$(printf '%s\n' "${review_output}" | awk -F= '/^priority_research_count=/ {value=$2} END {print value}')"
        risk_count="$(printf '%s\n' "${review_output}" | awk -F= '/^risk_attention_count=/ {value=$2} END {print value}')"
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
        printf '\nSMC AI 研究分层：本次 SMC 候选数为 0，跳过 AI 调用。\n'
    fi

    local md_status_text="skipped_no_candidates"
    local md_file=""
    if [ -n "${selection_csv}" ] && [ -f "${selection_csv}" ]; then
        local md_output md_status md_output_file
        printf '\n[3/3] 生成 Web AI Markdown（与 MKF 同一 md 生成逻辑）...\n'
        md_output_file="$(mktemp "${TMPDIR:-/tmp}/aismc-md.XXXXXX")"
        set +e
        run_export_md --csv "${selection_csv}" 2>&1 | tee "${md_output_file}"
        md_status=$?
        set -e
        md_output="$(<"${md_output_file}")"
        rm -f "${md_output_file}"
        md_file="$(printf '%s\n' "${md_output}" | awk -F= '/^web_ai_prompt_md=/ {value=$2} END {print value}')"
        if [ "${md_status}" -ne 0 ]; then
            printf '%s\n' "${md_output}"
            return "${md_status}"
        fi
        md_status_text="completed"
        printf 'markdown_path=%s\n' "${md_file}"
    fi

    printf '\nSMC 候选源一键流程摘要\n'
    printf 'signal_date=%s\n' "${signal_date}"
    printf 'selection_profile=%s\n' "${profile}"
    if [ "${profile}" = "small_capital" ]; then printf 'effective_min_adv20_cny=%s\n' "${SMALL_ADV20_CNY}"; fi
    printf 'smc_candidate_count=%s\n' "${candidate_count}"
    printf 'smc_selection_run=%s\n' "${selection_run}"
    printf 'smc_selection_csv=%s\n' "${selection_csv}"
    printf 'aismc_ai_review=%s\n' "${review_status_text}"
    printf 'priority_research_count=%s\n' "${priority_count}"
    printf 'risk_attention_count=%s\n' "${risk_count}"
    printf 'aismc_ai_run=%s\n' "${review_run}"
    printf 'aismc_ai_csv=%s\n' "${review_csv}"
    printf 'aismc_news_context=enabled\n'
    printf 'aismc_news_contexts=%s\n' "${news_contexts}"
    printf 'aismc_news_cache_dir=%s\n' "${news_cache_dir}"
    printf 'aismc_news_cache_status_counts=%s\n' "${news_cache_status_counts}"
    printf 'aismc_markdown=%s\n' "${md_status_text}"
    printf 'aismc_markdown_file=%s\n' "${md_file}"
    printf 'ai_smc_output_root=%s\n' "${AI_SMC_OUTPUT_ROOT}"
    printf 'boundary=SMC 候选源 + MKF 同款一键流程均为独立只读研究；不改变 SMC 入选、排序、watchlist、前瞻归档或生产逻辑；不连接券商、不提交订单。\n'
}

run_menu() {
    if [ ! -t 0 ] || [ ! -t 1 ]; then
        printf 'ERROR: aismc 交互菜单需要在终端中运行；自动化请使用 ./aismc.sh help 查看命令。\n' >&2
        return 2
    fi

    local options=(
        "SMC小资金一键流程（自动更新/AI分层+MD，ADV20 5000万）"
        "SMC标准一键流程（自动更新/AI分层+MD，复用yaml门槛）"
        "SMC候选源（自动更新数据）"
        "SMC候选源（仅本地数据）"
        "SMC候选AI研究分层（最新SMC候选）"
        "SMC候选CSV导出Web AI Markdown"
        "退出"
    )
    local actions=(
        "aismc-small"
        "aismc-review"
        "select"
        "select-local"
        "layer"
        "export-md"
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
        printf 'NCN AI-SMC 研究（SMC候选 × MKF同款一键流程）\n'
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
            printf '\n按回车返回 AI-SMC 菜单...'
            IFS= read -r
        fi
    done
}

execute_menu_choice() {
    local action="$1"
    case "${action}" in
        aismc-small) run_one_key --small ;;
        aismc-review) run_one_key ;;
        select) run_select ;;
        select-local) run_select --local ;;
        layer) run_layer ;;
        export-md) run_export_md ;;
        exit) printf '已退出。\n' ;;
    esac
}

case "${ACTION}" in
    menu)
        run_menu
        ;;
    aismc-review)
        shift
        run_one_key "$@"
        ;;
    aismc-small)
        shift
        run_one_key --small "$@"
        ;;
    select)
        shift
        run_select "$@"
        ;;
    select-small)
        shift
        run_select --small "$@"
        ;;
    select-local)
        shift
        run_select --local "$@"
        ;;
    select-small-local)
        shift
        run_select --small --local "$@"
        ;;
    layer)
        shift
        run_layer "$@"
        ;;
    export-md)
        shift
        run_export_md "$@"
        ;;
    help|-h|--help)
        printf '%s\n' \
            'NCN AI-SMC 研究入口（smc/ 子项目；SMC 候选源 × MKF 同款一键流程）' \
            '' \
            '用法（仓库根执行）：' \
            '  ./smc/aismc.sh                                打开方向键交互菜单' \
            '  ./smc/aismc.sh aismc-small [--as-of DATE] [--top N]  SMC小资金一键：自动更新+选股(ADV20 5000万)+AI分层+MD' \
            '  ./smc/aismc.sh aismc-review [--as-of DATE] [--top N] SMC标准一键：自动更新+选股+AI分层+MD（门槛复用yaml）' \
            '  ./smc/aismc.sh select [--as-of DATE] [--top N]        仅 SMC 选股（自动更新，标准门槛）' \
            '  ./smc/aismc.sh select-small ...                        仅 SMC 选股（自动更新，ADV20 5000万）' \
            '  ./smc/aismc.sh select-local / select-small-local       同上但跳过联网更新' \
            '  ./smc/aismc.sh layer [--selection-run DIR] [--top N]   MKF同款新闻/公报抓取 + AI 委员会分层（最新SMC候选）' \
            '  ./smc/aismc.sh export-md [--csv PATH]                  SMC 候选 CSV 导出 Web AI Markdown（MKF 同一 md 逻辑）' \
            '' \
            '输出目录：仓库根 smc-output/{selections, smc_ai_layer_runs, mkf_ai_reviews, mdfile, config}（全部未跟踪）' \
            '数据下载/股票信息与 mkf.sh 完全相同（BaoStock 自动更新，PFrontStockData）；AI 委员会使用 smc/yaml/smc_ai_review.yaml（SMC 专用提示词，同构于 yaml/mkf_ai_review.yaml），模型/新闻复用 smc/yaml/ai_providers.yaml + smc/yaml/mkf_news_context.yaml（主仓共享 yaml 的分离副本，路径已按 smc/ 根改写）；小资金口径复用 smc/yaml/edge_scout_v1.yaml 全部内容，仅覆盖 universe.min_adv20_cny=50000000。' \
            '只读研究：不改 SMC/MKF 入选、排序、watchlist、前瞻归档或生产逻辑；不连接券商、不提交订单。'
        ;;
    *)
        printf 'ERROR: 未知 AI-SMC 命令：%s\n请运行 ./aismc.sh help 查看用法。\n' "${ACTION}" >&2
        exit 2
        ;;
esac
