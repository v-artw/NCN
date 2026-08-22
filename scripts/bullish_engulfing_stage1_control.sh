#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNTIME_DIR="${ROOT_DIR}/.runtime"
PYTHON_BIN="${BULLISH_ENGULFING_PYTHON:-${ROOT_DIR}/.venv-doris/bin/python}"
PID_FILE="${RUNTIME_DIR}/bullish-engulfing-stage1.pid"
LOG_FILE="${RUNTIME_DIR}/bullish-engulfing-stage1.log"
RESULT_FILE="${RUNTIME_DIR}/bullish-engulfing-stage1.json"
EXIT_FILE="${RUNTIME_DIR}/bullish-engulfing-stage1.exit.json"

read_pid() { [[ -s "${PID_FILE}" ]] && tr -cd '0-9' < "${PID_FILE}"; }
is_running() { local pid; pid="$(read_pid)"; [[ -n "${pid}" ]] && kill -0 "${pid}" 2>/dev/null; }

start() {
  mkdir -p "${RUNTIME_DIR}"
  if is_running; then printf 'already_running pid=%s\n' "$(read_pid)"; return 0; fi
  [[ -x "${PYTHON_BIN}" ]] || { printf 'Python interpreter not executable: %s\n' "${PYTHON_BIN}" >&2; return 1; }
  [[ ! -e "${RESULT_FILE}" ]] || { printf 'Result already exists; refusing rerun: %s\n' "${RESULT_FILE}" >&2; return 1; }
  : > "${LOG_FILE}"
  rm -f "${EXIT_FILE}" "${PID_FILE}"
  nohup bash -c '
    set +e
    cd "$1" || exit 125
    env OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 \
      "$2" scripts/evaluate_bullish_engulfing_confirmation.py --workers 8 --output "$3"
    status=$?
    temporary="$4.$$.tmp"
    printf "{\"exit_code\":%d,\"finished_at\":\"%s\"}\n" "$status" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$temporary"
    mv "$temporary" "$4"
    exit "$status"
  ' _ "${ROOT_DIR}" "${PYTHON_BIN}" "${RESULT_FILE}" "${EXIT_FILE}" >> "${LOG_FILE}" 2>&1 < /dev/null &
  printf '%s\n' "$!" > "${PID_FILE}"
  sleep 1
  is_running || { printf 'failed_to_start log=%s\n' "${LOG_FILE}" >&2; return 1; }
  printf 'started pid=%s\n' "$(read_pid)"
}

status() {
  local pid=""; pid="$(read_pid)"
  if is_running; then printf 'state=running pid=%s\n' "${pid}"
  elif [[ -s "${EXIT_FILE}" ]]; then printf 'state=finished pid=%s exit=' "${pid:-none}"; tr -d '\n' < "${EXIT_FILE}"; printf '\n'
  else printf 'state=not_running pid=%s\n' "${pid:-none}"; fi
  [[ ! -s "${LOG_FILE}" ]] || { printf '%s\n' '--- recent log ---'; tail -n 20 "${LOG_FILE}"; }
  [[ ! -s "${RESULT_FILE}" ]] || shasum -a 256 "${RESULT_FILE}"
}

case "${1:-}" in start) start ;; status) status ;; *) printf 'Usage: %s start|status\n' "$0" >&2; exit 2 ;; esac
