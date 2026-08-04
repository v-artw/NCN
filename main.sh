#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WEB_CONTROL="${PROJECT_ROOT}/scripts/edge_scout_web_control.sh"
SCAN_CONTROL="${EDGE_SCOUT_SCAN_SCRIPT:-${PROJECT_ROOT}/scripts/edge_scout_scan.sh}"
ACTION="${1:-menu}"

if [ ! -x "${WEB_CONTROL}" ]; then
    printf 'ERROR: Web 控制脚本不存在或不可执行：%s\n' "${WEB_CONTROL}" >&2
    exit 1
fi

run_menu() {
    if [ ! -t 0 ] || [ ! -t 1 ]; then
        printf 'ERROR: 交互菜单需要在终端中运行；自动化请使用 ./main.sh help 查看命令。\n' >&2
        return 2
    fi

    local options=(
        "启动 Web 监控"
        "关闭 Web 监控"
        "重启 Web 监控"
        "查看 Web 状态"
        "全市场扫描（自动更新数据）"
        "全市场扫描（仅本地数据）"
        "单股扫描（自动更新数据）"
        "单股扫描（仅本地数据）"
        "仅更新研究数据"
        "运行测试"
        "退出"
    )
    local selected=0
    local key sequence

    while true; do
        printf '\033[2J\033[H'
        printf 'NCN Web 监控与研究扫描\n'
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
                "[A"|"OA") selected=$((selected > 0 ? selected - 1 : ${#options[@]} - 1)) ;;
                "[B"|"OB") selected=$((selected < ${#options[@]} - 1 ? selected + 1 : 0)) ;;
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
            execute_menu_choice "${selected}" || result=$?
            if [ "${selected}" -eq 10 ]; then
                return "${result}"
            fi
            printf '\n按回车返回菜单...'
            IFS= read -r
        fi
    done
}

execute_menu_choice() {
    local selected="$1"
    local code as_of
    case "${selected}" in
        0) "${WEB_CONTROL}" start ;;
        1) "${WEB_CONTROL}" stop ;;
        2) "${WEB_CONTROL}" restart ;;
        3) "${WEB_CONTROL}" status || true ;;
        4)
            prompt_as_of
            as_of="${PROMPTED_AS_OF}"
            if [ -n "${as_of}" ]; then "${SCAN_CONTROL}" market --as-of "${as_of}"; else "${SCAN_CONTROL}" market; fi
            ;;
        5)
            prompt_as_of
            as_of="${PROMPTED_AS_OF}"
            if [ -n "${as_of}" ]; then EDGE_SCOUT_AUTO_UPDATE=0 "${SCAN_CONTROL}" market --as-of "${as_of}"; else EDGE_SCOUT_AUTO_UPDATE=0 "${SCAN_CONTROL}" market; fi
            ;;
        6|7)
            printf '请输入股票代码（如 600519 或 sh.600519）：'
            IFS= read -r code
            if [ -z "${code}" ]; then printf '已取消：股票代码不能为空。\n'; return 0; fi
            prompt_as_of
            as_of="${PROMPTED_AS_OF}"
            if [ "${selected}" -eq 7 ]; then
                if [ -n "${as_of}" ]; then EDGE_SCOUT_AUTO_UPDATE=0 "${SCAN_CONTROL}" single "${code}" --as-of "${as_of}"; else EDGE_SCOUT_AUTO_UPDATE=0 "${SCAN_CONTROL}" single "${code}"; fi
            else
                if [ -n "${as_of}" ]; then "${SCAN_CONTROL}" single "${code}" --as-of "${as_of}"; else "${SCAN_CONTROL}" single "${code}"; fi
            fi
            ;;
        8) "${SCAN_CONTROL}" update ;;
        9) "${SCAN_CONTROL}" test ;;
        10) printf '已退出。\n' ;;
    esac
}

prompt_as_of() {
    printf '请输入 T 信号日 YYYY-MM-DD（直接回车使用自动日期）：'
    IFS= read -r PROMPTED_AS_OF
}

case "${ACTION}" in
    menu)
        run_menu
        ;;
    start|stop|restart|status|toggle)
        exec "${WEB_CONTROL}" "${ACTION}"
        ;;
    scan)
        shift
        exec "${SCAN_CONTROL}" market "$@"
        ;;
    scan-local)
        shift
        export EDGE_SCOUT_AUTO_UPDATE=0
        exec "${SCAN_CONTROL}" market "$@"
        ;;
    single)
        shift
        exec "${SCAN_CONTROL}" single "$@"
        ;;
    single-local)
        shift
        export EDGE_SCOUT_AUTO_UPDATE=0
        exec "${SCAN_CONTROL}" single "$@"
        ;;
    update)
        shift
        exec "${SCAN_CONTROL}" update "$@"
        ;;
    test)
        shift
        exec "${SCAN_CONTROL}" test "$@"
        ;;
    help|-h|--help)
        printf '%s\n' \
            'NCN Web 监控与研究扫描统一入口' \
            '' \
            '用法：' \
            '  ./main.sh              打开方向键交互菜单' \
            '  ./main.sh menu         打开方向键交互菜单' \
            '  ./main.sh start        启动 Web 监控' \
            '  ./main.sh stop         关闭 Web 监控' \
            '  ./main.sh restart      重启 Web 监控' \
            '  ./main.sh status       查看运行状态' \
            '' \
            '扫描：' \
            '  ./main.sh scan                         更新数据并执行全市场扫描' \
            '  ./main.sh scan --as-of YYYY-MM-DD     指定 T 日执行全市场扫描' \
            '  ./main.sh scan-local                   跳过联网更新，使用本地数据扫描' \
            '  ./main.sh single 600519                更新数据并执行单股扫描' \
            '  ./main.sh single 600519 --as-of DATE  指定 T 日执行单股扫描' \
            '  ./main.sh single-local 600519          使用本地数据执行单股扫描' \
            '  ./main.sh update                       仅检查并增量更新研究数据' \
            '  ./main.sh test                         运行 Edge Scout 测试' \
            '' \
            '  ./main.sh help         显示帮助'
        ;;
    *)
        printf 'ERROR: 未知命令：%s\n请运行 ./main.sh help 查看用法。\n' "${ACTION}" >&2
        exit 2
        ;;
esac
