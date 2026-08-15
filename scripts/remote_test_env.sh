#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REMOTE_HOST="${NCN_REMOTE_TEST_HOST:-10.20.98.161}"
REMOTE_USER="${NCN_REMOTE_TEST_USER:-adminwsl}"
REMOTE_PORT="${NCN_REMOTE_TEST_PORT:-22}"
REMOTE_DIR="${NCN_REMOTE_TEST_DIR:-/home/${REMOTE_USER}/NCN}"
SSH_KEY="${NCN_REMOTE_TEST_KEY:-${HOME}/.ssh/id_ed25519}"
REMOTE="${REMOTE_USER}@${REMOTE_HOST}"

SSH_OPTIONS=(
  -p "${REMOTE_PORT}"
  -i "${SSH_KEY}"
  -o IdentitiesOnly=yes
  -o StrictHostKeyChecking=accept-new
  -o ConnectTimeout=10
)

usage() {
  cat <<'EOF'
Usage: ./scripts/remote_test_env.sh <command> [pytest arguments...]

Commands:
  check        Check TCP, SSH, CPU, memory, Python, and remote path.
  install-key  Install the local SSH public key using NCN_REMOTE_TEST_PASSWORD.
  sync-code    Synchronize source and configuration without local runtime output.
  sync-data    Synchronize PFrontStockData to the remote Linux filesystem.
  setup        Create the remote .venv and install the project with test dependencies.
  test         Run pytest remotely; optional arguments are passed to pytest.
  study-start  Start/resume a detached checkpointed signal hit-rate study.
  study-status Show detached study PID, progress, and result state.
  study-stop   Stop the detached study process.
  study-fetch  Copy the completed study JSON to the local current directory.
  shell        Open an interactive shell in the remote project directory.
  all          Run check, sync-code, sync-data, setup, and the default test suite.

Environment overrides:
  NCN_REMOTE_TEST_HOST      Default: 10.20.98.161
  NCN_REMOTE_TEST_USER      Default: adminwsl
  NCN_REMOTE_TEST_PORT      Default: 22
  NCN_REMOTE_TEST_DIR       Default: /home/<user>/NCN
  NCN_REMOTE_TEST_KEY       Default: ~/.ssh/id_ed25519
  NCN_REMOTE_TEST_PASSWORD  One-time password used only by install-key.
EOF
}

require_file() {
  if [[ ! -f "$1" ]]; then
    printf 'Required file not found: %s\n' "$1" >&2
    exit 1
  fi
}

ssh_remote() {
  ssh "${SSH_OPTIONS[@]}" "${REMOTE}" "$@"
}

rsync_remote() {
  local ssh_command
  printf -v ssh_command 'ssh -p %q -i %q -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10' \
    "${REMOTE_PORT}" "${SSH_KEY}"
  rsync -az --delete --progress -e "${ssh_command}" "$@"
}

check_tcp() {
  local nc_options=(-z -w 5)
  if [[ "$(uname -s)" == "Darwin" ]]; then
    nc_options=(-z -G 5)
  fi
  if ! nc "${nc_options[@]}" "${REMOTE_HOST}" "${REMOTE_PORT}"; then
    printf 'SSH is unreachable at %s:%s. Start sshd in WSL and expose the port through Windows Firewall/portproxy.\n' \
      "${REMOTE_HOST}" "${REMOTE_PORT}" >&2
    exit 2
  fi
}

check() {
  check_tcp
  ssh_remote "printf 'host='; hostname; printf 'kernel='; uname -sr; printf 'cpu='; nproc; printf 'memory='; free -h | awk 'NR==2 {print \$2}'; printf 'python='; command -v python3 || true; printf 'project='; test -d '${REMOTE_DIR}' && printf 'ready\\n' || printf 'not_synced\\n'"
}

install_key() {
  check_tcp
  require_file "${SSH_KEY}.pub"
  command -v expect >/dev/null || {
    printf 'expect is required for one-time password authentication.\n' >&2
    exit 1
  }
  if [[ -z "${NCN_REMOTE_TEST_PASSWORD:-}" ]]; then
    printf 'Set NCN_REMOTE_TEST_PASSWORD for this command only. The password is not stored.\n' >&2
    exit 1
  fi

  NCN_KEY_CONTENT="$(<"${SSH_KEY}.pub")" \
  NCN_REMOTE_TEST_PASSWORD="${NCN_REMOTE_TEST_PASSWORD}" \
  NCN_REMOTE_TEST_TARGET="${REMOTE}" \
  NCN_REMOTE_TEST_PORT_VALUE="${REMOTE_PORT}" \
  expect <<'EXPECT'
set timeout 20
set password $env(NCN_REMOTE_TEST_PASSWORD)
set target $env(NCN_REMOTE_TEST_TARGET)
set port $env(NCN_REMOTE_TEST_PORT_VALUE)
set key $env(NCN_KEY_CONTENT)
spawn ssh -p $port -o StrictHostKeyChecking=accept-new $target "umask 077; mkdir -p ~/.ssh; touch ~/.ssh/authorized_keys; grep -qxF '$key' ~/.ssh/authorized_keys || printf '%s\\n' '$key' >> ~/.ssh/authorized_keys"
expect {
  -re "(?i)password:" { send -- "$password\r"; exp_continue }
  eof { }
  timeout { exit 124 }
}
catch wait result
exit [lindex $result 3]
EXPECT

  unset NCN_REMOTE_TEST_PASSWORD
  ssh_remote "printf 'SSH key authentication ready: '; hostname"
}

sync_code() {
  require_file "${SSH_KEY}"
  ssh_remote "mkdir -p '${REMOTE_DIR}'"
  rsync_remote \
    --exclude '/.git/' \
    --exclude '/.venv/' \
    --exclude '/.venv-playwright/' \
    --exclude '/.pytest_cache/' \
    --exclude '/.runtime/' \
    --exclude '/.opencode/' \
    --exclude '/PFrontStockData/' \
    --exclude '/output/' \
    --exclude '/config/research_watchlist.json' \
    --exclude '/.env*' \
    "${ROOT_DIR}/" "${REMOTE}:${REMOTE_DIR}/"
}

sync_data() {
  require_file "${SSH_KEY}"
  if [[ ! -d "${ROOT_DIR}/PFrontStockData" ]]; then
    printf 'Local data directory not found: %s/PFrontStockData\n' "${ROOT_DIR}" >&2
    exit 1
  fi
  ssh_remote "mkdir -p '${REMOTE_DIR}/PFrontStockData'"
  rsync_remote "${ROOT_DIR}/PFrontStockData/" "${REMOTE}:${REMOTE_DIR}/PFrontStockData/"
}

setup_remote() {
  ssh_remote "cd '${REMOTE_DIR}' && test -x scripts/setup.sh && PYTHON_BIN=python3 ./scripts/setup.sh"
}

run_tests() {
  local quoted_args=""
  if (($#)); then
    printf -v quoted_args ' %q' "$@"
  else
    quoted_args=' -q'
  fi
  ssh_remote "cd '${REMOTE_DIR}' && .venv/bin/python -m pytest${quoted_args}"
}

study_start() {
  local result="${NCN_REMOTE_STUDY_RESULT:-.runtime/signal-study-2018-2026.json}"
  local log="${NCN_REMOTE_STUDY_LOG:-.runtime/signal-study-2018-2026.log}"
  local pidfile="${NCN_REMOTE_STUDY_PID:-.runtime/signal-study-2018-2026.pid}"
  local args=""
  printf -v args ' %q' "$@"
  ssh_remote "cd '${REMOTE_DIR}' && mkdir -p .runtime && if test -s '${pidfile}' && kill -0 \"\$(cat '${pidfile}')\" 2>/dev/null; then echo 'study already running pid='\$(cat '${pidfile}'); exit 0; fi; nohup env OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 .venv/bin/python scripts/evaluate_signal_hit_rates.py --output '${result}' --checkpoint-dir '${result}.checkpoint' --resume${args} >'${log}' 2>&1 < /dev/null & echo \$! >'${pidfile}'; echo study_started_or_resumed pid=\$(cat '${pidfile}') result='${result}' checkpoint='${result}.checkpoint' log='${log}'"
}

study_status() {
  local result="${NCN_REMOTE_STUDY_RESULT:-.runtime/signal-study-2018-2026.json}"
  local log="${NCN_REMOTE_STUDY_LOG:-.runtime/signal-study-2018-2026.log}"
  local pidfile="${NCN_REMOTE_STUDY_PID:-.runtime/signal-study-2018-2026.pid}"
  ssh_remote "cd '${REMOTE_DIR}' && pid=\$(cat '${pidfile}' 2>/dev/null || true); if test -n \"\$pid\" && kill -0 \"\$pid\" 2>/dev/null; then echo study_running pid=\$pid; else echo study_not_running pid=\${pid:-none}; fi; test -s '${result}' && echo result_ready='${result}' || echo result_pending='${result}'; test -f '${result}.checkpoint/manifest.json' && cat '${result}.checkpoint/manifest.json'; test -f '${log}' && tail -n 5 '${log}' || true"
}

study_stop() {
  local pidfile="${NCN_REMOTE_STUDY_PID:-.runtime/signal-study-2018-2026.pid}"
  ssh_remote "cd '${REMOTE_DIR}' && pid=\$(cat '${pidfile}' 2>/dev/null || true); if test -n \"\$pid\" && kill -0 \"\$pid\" 2>/dev/null; then kill \"\$pid\"; echo study_stopped pid=\$pid; else echo study_not_running; fi"
}

study_fetch() {
  local result="${NCN_REMOTE_STUDY_RESULT:-.runtime/signal-study-2018-2026.json}"
  local destination="${1:-signal-study-2018-2026.json}"
  scp \
    -P "${REMOTE_PORT}" \
    -i "${SSH_KEY}" \
    -o IdentitiesOnly=yes \
    -o StrictHostKeyChecking=accept-new \
    -o ConnectTimeout=10 \
    "${REMOTE}:${REMOTE_DIR}/${result}" "${destination}"
}

open_shell() {
  ssh -t "${SSH_OPTIONS[@]}" "${REMOTE}" "cd '${REMOTE_DIR}' && exec bash -l"
}

command_name="${1:-}"
if [[ -z "${command_name}" ]]; then
  usage
  exit 1
fi
shift

case "${command_name}" in
  check) check ;;
  install-key) install_key ;;
  sync-code) sync_code ;;
  sync-data) sync_data ;;
  setup) setup_remote ;;
  test) run_tests "$@" ;;
  study-start) study_start "$@" ;;
  study-status) study_status ;;
  study-stop) study_stop ;;
  study-fetch) study_fetch "$@" ;;
  shell) open_shell ;;
  all)
    check
    sync_code
    sync_data
    setup_remote
    run_tests -q
    ;;
  -h|--help|help) usage ;;
  *)
    printf 'Unknown command: %s\n' "${command_name}" >&2
    usage >&2
    exit 1
    ;;
esac
