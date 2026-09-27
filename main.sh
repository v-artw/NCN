#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WEB_CONTROL="${PROJECT_ROOT}/scripts/edge_scout_web_control.sh"
SCAN_CONTROL="${EDGE_SCOUT_SCAN_SCRIPT:-${PROJECT_ROOT}/scripts/edge_scout_scan.sh}"
MKF_CONTROL="${PROJECT_ROOT}/mkf.sh"
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
        "── Web 监控 ──"
        "启动 Web 监控"
        "关闭 Web 监控"
        "重启 Web 监控"
        "查看 Web 状态"
        "── 全市场 / 单股 ──"
        "全市场扫描（自动更新数据）"
        "全市场扫描（仅本地数据）"
        "单股扫描（自动更新数据）"
        "单股扫描（仅本地数据）"
        "仅更新研究数据"
        "── A 类扫描 ──"
        "A类低位启动扫描（自动更新数据）"
        "A类低位启动扫描（仅本地数据）"
        "── MKF 研究 ──"
        "MKF 研究入口"
        "── 系统 ──"
        "运行测试"
        "退出"
    )
    local actions=(
        ""
        "web-start"
        "web-stop"
        "web-restart"
        "web-status"
        ""
        "market-auto"
        "market-local"
        "single-auto"
        "single-local"
        "update-data"
        ""
        "a-class-auto"
        "a-class-local"
        ""
        "mkf-menu"
        ""
        "test"
        "exit"
    )
    local selected=1
    local key sequence

    menu_next_selectable() {
        local current="$1"
        local direction="$2"
        local count="${#actions[@]}"
        while true; do
            current=$(((current + direction + count) % count))
            if [ -n "${actions[$current]}" ]; then
                printf '%s' "${current}"
                return 0
            fi
        done
    }

    while true; do
        printf '\033[2J\033[H'
        printf 'NCN Web 监控与研究扫描\n'
        printf '使用 ↑/↓ 选择，回车确认，q 退出\n\n'
        local index
        for index in "${!options[@]}"; do
            if [ -z "${actions[$index]}" ]; then
                if [ "${index}" -gt 0 ]; then printf '\n'; fi
                printf '  %s\n' "${options[$index]}"
            elif [ "${index}" -eq "${selected}" ]; then
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
            printf '\n按回车返回菜单...'
            IFS= read -r
        fi
    done
}

execute_menu_choice() {
    local action="$1"
    local code as_of
    case "${action}" in
        web-start) "${WEB_CONTROL}" start ;;
        web-stop) "${WEB_CONTROL}" stop ;;
        web-restart) "${WEB_CONTROL}" restart ;;
        web-status) "${WEB_CONTROL}" status || true ;;
        market-auto)
            prompt_as_of
            as_of="${PROMPTED_AS_OF}"
            if [ -n "${as_of}" ]; then "${SCAN_CONTROL}" market --as-of "${as_of}"; else "${SCAN_CONTROL}" market; fi
            ;;
        market-local)
            prompt_as_of
            as_of="${PROMPTED_AS_OF}"
            if [ -n "${as_of}" ]; then EDGE_SCOUT_AUTO_UPDATE=0 "${SCAN_CONTROL}" market --as-of "${as_of}"; else EDGE_SCOUT_AUTO_UPDATE=0 "${SCAN_CONTROL}" market; fi
            ;;
        a-class-auto) "${SCAN_CONTROL}" select-a-class ;;
        a-class-local) EDGE_SCOUT_AUTO_UPDATE=0 "${SCAN_CONTROL}" select-a-class ;;
        mkf-menu) "${MKF_CONTROL}" menu ;;
        single-auto|single-local)
            printf '请输入股票代码（如 600519 或 sh.600519）：'
            IFS= read -r code
            if [ -z "${code}" ]; then printf '已取消：股票代码不能为空。\n'; return 0; fi
            prompt_as_of
            as_of="${PROMPTED_AS_OF}"
            if [ "${action}" = "single-local" ]; then
                if [ -n "${as_of}" ]; then EDGE_SCOUT_AUTO_UPDATE=0 "${SCAN_CONTROL}" single "${code}" --as-of "${as_of}"; else EDGE_SCOUT_AUTO_UPDATE=0 "${SCAN_CONTROL}" single "${code}"; fi
            else
                if [ -n "${as_of}" ]; then "${SCAN_CONTROL}" single "${code}" --as-of "${as_of}"; else "${SCAN_CONTROL}" single "${code}"; fi
            fi
            ;;
        update-data) "${SCAN_CONTROL}" update ;;
        test) "${SCAN_CONTROL}" test ;;
        exit) printf '已退出。\n' ;;
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
    mkf|mkf-menu)
        shift
        exec "${MKF_CONTROL}" menu "$@"
        ;;
    mkf-review)
        shift
        exec "${MKF_CONTROL}" mkf-review "$@"
        ;;
    mkf-small)
        shift
        exec "${MKF_CONTROL}" mkf-small "$@"
        ;;
    select-mkf)
        shift
        exec "${MKF_CONTROL}" select-mkf "$@"
        ;;
    select-mkf-local)
        shift
        exec "${MKF_CONTROL}" select-mkf-local "$@"
        ;;
    review-mkf-ai)
        shift
        exec "${MKF_CONTROL}" review-mkf-ai "$@"
        ;;
    select-a-class)
        shift
        exec "${SCAN_CONTROL}" select-a-class "$@"
        ;;
    select-a-class-local)
        shift
        export EDGE_SCOUT_AUTO_UPDATE=0
        exec "${SCAN_CONTROL}" select-a-class "$@"
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
    audit)
        shift
        exec "${SCAN_CONTROL}" audit "$@"
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
            '  ./main.sh mkf                         打开 MKF 对话入口（包含原 main.sh 全部 MKF 功能）' \
            '  ./mkf.sh                              打开 MKF 方向键菜单；自动化参数请用下方 MKF 命令追加' \
            '  ./main.sh mkf-review                  兼容旧 MKF 一键流程命令；高级自动化参数仍可追加' \
            '  ./main.sh mkf-small                   兼容旧小资金 MKF 命令：ADV20 降为 5000 万；高级自动化参数仍可追加' \
            '  ./main.sh select-mkf                  兼容旧 MKF 候选源实验命令；高级自动化参数仍可追加' \
            '  ./main.sh select-mkf-local            兼容旧本地 MKF 候选源实验命令；高级自动化参数仍可追加' \
            '  ./main.sh review-mkf-ai               兼容旧 MKF AI 分层命令；高级自动化参数仍可追加' \
            '  ./main.sh select-a-class [--as-of DATE] 运行 A 类低位启动只读扫描' \
            '  ./main.sh select-a-class-local        仅用本地数据运行 A 类低位启动扫描' \
            '  ./main.sh single 600519                更新数据并执行单股扫描' \
            '  ./main.sh single 600519 --as-of DATE  指定 T 日执行单股扫描' \
            '  ./main.sh single-local 600519          使用本地数据执行单股扫描' \
            '  ./main.sh update                       仅检查并增量更新研究数据' \
            '  ./main.sh audit                        生成新的前瞻观察成熟度审计' \
            '  ./main.sh test                         运行 Edge Scout 测试' \
            '' \
            '  SMC 选股/新闻复核/前瞻归档等已分离为独立子项目：./smc/smc.sh 与 ./smc/aismc.sh' \
            '' \
            '  ./main.sh help         显示帮助'
        ;;
    *)
        printf 'ERROR: 未知命令：%s\n请运行 ./main.sh help 查看用法。\n' "${ACTION}" >&2
        exit 2
        ;;
esac
