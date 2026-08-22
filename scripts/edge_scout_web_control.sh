#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNTIME_DIR="${EDGE_SCOUT_WEB_RUNTIME_DIR:-${PROJECT_ROOT}/.runtime}"
PID_FILE="${RUNTIME_DIR}/edge_scout_web.pid"
LOG_FILE="${RUNTIME_DIR}/edge_scout_web.log"
HOST="${EDGE_SCOUT_WEB_HOST:-127.0.0.1}"
PORT="${EDGE_SCOUT_WEB_PORT:-9091}"
PYTHON="${VENV_PYTHON:-${PROJECT_ROOT}/.venv/bin/python}"
ACTION="${1:-toggle}"

mkdir -p "${RUNTIME_DIR}"

read_pid() {
    if [ -f "${PID_FILE}" ]; then
        tr -d '[:space:]' < "${PID_FILE}"
    fi
}

is_managed_process() {
    local pid="${1:-}"
    local command_line
    if [[ ! "${pid}" =~ ^[0-9]+$ ]] || ! kill -0 "${pid}" 2>/dev/null; then
        return 1
    fi
    command_line="$(ps -p "${pid}" -o command= 2>/dev/null || true)"
    [[ "${command_line}" == *"ashare_edge_scout.research_web"* ]] && \
        [[ "${command_line}" == *"--project-root ${PROJECT_ROOT}"* ]]
}

managed_pid() {
    local pid
    pid="$(read_pid)"
    if is_managed_process "${pid}"; then
        printf '%s\n' "${pid}"
        return 0
    fi
    if [ -f "${PID_FILE}" ]; then
        rm -f "${PID_FILE}"
    fi
    return 1
}

health_check() {
    "${PYTHON}" -c \
        'import sys, urllib.request; urllib.request.urlopen(sys.argv[1], timeout=1).read(1)' \
        "http://${HOST}:${PORT}/api/health" >/dev/null 2>&1
}

start_web() {
    local pid
    if pid="$(managed_pid)"; then
        printf 'NCN Web 监控已在运行：PID=%s，地址=http://%s:%s\n' "${pid}" "${HOST}" "${PORT}"
        return 0
    fi
    if [ ! -x "${PYTHON}" ]; then
        printf 'ERROR: Python 环境不存在，请先运行 ./scripts/setup.sh\n' >&2
        return 1
    fi

    EDGE_SCOUT_WEB_HOST="${HOST}" EDGE_SCOUT_WEB_PORT="${PORT}" VENV_PYTHON="${PYTHON}" \
        nohup "${PROJECT_ROOT}/scripts/edge_scout_web.sh" >>"${LOG_FILE}" 2>&1 &
    pid=$!
    printf '%s\n' "${pid}" > "${PID_FILE}"

    for _ in {1..30}; do
        if ! kill -0 "${pid}" 2>/dev/null; then
            rm -f "${PID_FILE}"
            printf 'ERROR: NCN Web 监控启动失败，日志：%s\n' "${LOG_FILE}" >&2
            return 1
        fi
        if is_managed_process "${pid}" && health_check; then
            printf 'NCN Web 监控已启动：PID=%s\n地址：http://%s:%s\n日志：%s\n' \
                "${pid}" "${HOST}" "${PORT}" "${LOG_FILE}"
            return 0
        fi
        sleep 0.5
    done

    if is_managed_process "${pid}"; then
        kill "${pid}" 2>/dev/null || true
    fi
    rm -f "${PID_FILE}"
    printf 'ERROR: NCN Web 监控健康检查超时，日志：%s\n' "${LOG_FILE}" >&2
    return 1
}

stop_web() {
    local pid
    if ! pid="$(managed_pid)"; then
        printf 'NCN Web 监控未运行。\n'
        return 0
    fi
    kill "${pid}"
    for _ in {1..40}; do
        if ! kill -0 "${pid}" 2>/dev/null; then
            rm -f "${PID_FILE}"
            printf 'NCN Web 监控已关闭：PID=%s\n' "${pid}"
            return 0
        fi
        sleep 0.25
    done
    printf 'ERROR: NCN Web 监控未能在 10 秒内关闭：PID=%s\n' "${pid}" >&2
    return 1
}

show_status() {
    local pid
    if pid="$(managed_pid)"; then
        printf '运行中：PID=%s，地址=http://%s:%s，日志=%s\n' "${pid}" "${HOST}" "${PORT}" "${LOG_FILE}"
        return 0
    fi
    printf '已停止。\n'
    return 1
}

case "${ACTION}" in
    start) start_web ;;
    stop) stop_web ;;
    restart) stop_web && start_web ;;
    status) show_status ;;
    toggle)
        if managed_pid >/dev/null; then
            stop_web
        else
            start_web
        fi
        ;;
    *)
        printf '用法：%s [start|stop|restart|status|toggle]\n' "$0" >&2
        exit 2
        ;;
esac
