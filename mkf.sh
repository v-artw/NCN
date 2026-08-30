#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCAN_CONTROL="${EDGE_SCOUT_SCAN_SCRIPT:-${PROJECT_ROOT}/scripts/edge_scout_scan.sh}"
ACTION="${1:-menu}"

if [ ! -x "${SCAN_CONTROL}" ]; then
    printf 'ERROR: MKF 底层扫描脚本不存在或不可执行：%s\n' "${SCAN_CONTROL}" >&2
    exit 1
fi

run_menu() {
    if [ ! -t 0 ] || [ ! -t 1 ]; then
        printf 'ERROR: MKF 交互菜单需要在终端中运行；自动化请使用 ./mkf.sh help 查看命令。\n' >&2
        return 2
    fi

    local options=(
        "MKF一键流程（自动更新/AI分层）"
        "MKF小资金一键流程（自动更新/AI分层，ADV20 5000万）"
        "MKF候选源实验（自动更新数据）"
        "MKF候选源实验（仅本地数据）"
        "MKF候选源AI研究分层（最新MKF候选）"
        "退出"
    )
    local actions=(
        "mkf-review"
        "mkf-small"
        "select-mkf"
        "select-mkf-local"
        "review-mkf-ai"
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
        printf 'NCN MKF 研究\n'
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
            printf '\n按回车返回 MKF 菜单...'
            IFS= read -r
        fi
    done
}

execute_menu_choice() {
    local action="$1"
    case "${action}" in
        mkf-review) "${SCAN_CONTROL}" mkf-review ;;
        mkf-small) "${SCAN_CONTROL}" mkf-review-small ;;
        select-mkf) "${SCAN_CONTROL}" select-mkf ;;
        select-mkf-local) EDGE_SCOUT_AUTO_UPDATE=0 "${SCAN_CONTROL}" select-mkf ;;
        review-mkf-ai) "${SCAN_CONTROL}" review-mkf-ai ;;
        exit) printf '已退出。\n' ;;
    esac
}

case "${ACTION}" in
    menu)
        run_menu
        ;;
    mkf-review)
        shift
        exec "${SCAN_CONTROL}" mkf-review "$@"
        ;;
    mkf-small)
        shift
        exec "${SCAN_CONTROL}" mkf-review-small "$@"
        ;;
    select-mkf)
        shift
        exec "${SCAN_CONTROL}" select-mkf "$@"
        ;;
    select-mkf-local)
        shift
        export EDGE_SCOUT_AUTO_UPDATE=0
        exec "${SCAN_CONTROL}" select-mkf "$@"
        ;;
    review-mkf-ai)
        shift
        exec "${SCAN_CONTROL}" review-mkf-ai "$@"
        ;;
    help|-h|--help)
        printf '%s\n' \
            'NCN MKF 研究入口' \
            '' \
            '用法：' \
            '  ./mkf.sh                              打开方向键交互菜单' \
            '  ./mkf.sh menu                         打开方向键交互菜单' \
            '  ./mkf.sh mkf-review [--as-of DATE] [--top N]  MKF候选源+AI分层一键流程' \
            '  ./mkf.sh mkf-small [--as-of DATE] [--top N]  小资金 MKF 一键流程：ADV20 降为 5000 万，候选源+AI分层' \
            '  ./mkf.sh select-mkf [--as-of DATE]   运行独立 MKF 候选源实验，不影响 SMC' \
            '  ./mkf.sh select-mkf-local            仅用本地数据运行独立 MKF 候选源实验' \
            '  ./mkf.sh review-mkf-ai [--selection-run DIR] [--top N]  MKF 候选源 AI 只读研究分层' \
            '' \
            '说明：mkf.sh 不依赖 main.sh；它保留 main.sh 原 MKF 命令名和扫描参数转发行为。'
        ;;
    *)
        printf 'ERROR: 未知 MKF 命令：%s\n请运行 ./mkf.sh help 查看用法。\n' "${ACTION}" >&2
        exit 2
        ;;
esac
