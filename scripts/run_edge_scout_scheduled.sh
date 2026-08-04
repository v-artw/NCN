#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_PYTHON="${VENV_PYTHON:-${ROOT_DIR}/.venv/bin/python}"
SCHEDULE_ENV="${EDGE_SCOUT_SCHEDULE_ENV:-${ROOT_DIR}/.env.edge_scout_schedule}"
LOG_DIR="${EDGE_SCOUT_SCHEDULE_LOG_DIR:-${ROOT_DIR}/output/edge_scout_scheduler}"
RETAIN_LOGS="${EDGE_SCOUT_SCHEDULE_RETAIN_LOGS:-30}"
TIMEOUT_SECONDS="${EDGE_SCOUT_SCHEDULE_TIMEOUT_SECONDS:-7200}"
RUN_ID="scheduled-$(date +%Y%m%d_%H%M%S)"
LOG_PATH="${LOG_DIR}/${RUN_ID}.log"
SUMMARY_PATH="${LOG_DIR}/${RUN_ID}.summary.json"

mkdir -p "${LOG_DIR}"
exec > >(tee -a "${LOG_PATH}") 2>&1

notify_failure() {
  local message="$1"
  if [[ "${EDGE_SCOUT_DISABLE_LOCAL_ALERT:-0}" != "1" ]] && command -v osascript >/dev/null 2>&1; then
    osascript -e "display notification \"${message//\"/\\\"}\" with title \"Edge Scout failed\"" >/dev/null 2>&1 || true
  fi
  if [[ -n "${EDGE_SCOUT_ALERT_WEBHOOK_URL:-}" ]] && command -v curl >/dev/null 2>&1; then
    ALERT_MESSAGE="${message}" "${VENV_PYTHON}" - <<'PY' | \
      curl --fail --silent --show-error --max-time 15 -H 'Content-Type: application/json' \
        --data-binary @- "${EDGE_SCOUT_ALERT_WEBHOOK_URL}" >/dev/null 2>&1 || true
import json, os
print(json.dumps({"text": os.environ["ALERT_MESSAGE"]}))
PY
  fi
}

write_summary() {
  local status="$1" exit_code="$2" reason="$3"
  STATUS_VALUE="${status}" EXIT_CODE_VALUE="${exit_code}" REASON_VALUE="${reason}" \
  RUN_ID_VALUE="${RUN_ID}" LOG_PATH_VALUE="${LOG_PATH}" SUMMARY_PATH_VALUE="${SUMMARY_PATH}" \
    "${VENV_PYTHON}" - <<'PY'
import json, os
from datetime import datetime, timezone
from pathlib import Path
payload = {
    "schema_version": "edge_scout_scheduled_run_v1",
    "status": os.environ["STATUS_VALUE"],
    "exit_code": int(os.environ["EXIT_CODE_VALUE"]),
    "reason": os.environ["REASON_VALUE"],
    "run_id": os.environ["RUN_ID_VALUE"],
    "log_path": os.environ["LOG_PATH_VALUE"],
    "finished_at_utc": datetime.now(timezone.utc).isoformat(),
}
target = Path(os.environ["SUMMARY_PATH_VALUE"])
temporary = target.with_suffix(".tmp")
temporary.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
temporary.replace(target)
PY
}

run_timed() {
  "${VENV_PYTHON}" - "${TIMEOUT_SECONDS}" "$@" <<'PY'
import subprocess, sys
timeout = int(sys.argv[1])
try:
    raise SystemExit(subprocess.run(sys.argv[2:], timeout=timeout).returncode)
except subprocess.TimeoutExpired:
    print(f"edge_scout_schedule_timeout: command exceeded {timeout}s", file=sys.stderr)
    raise SystemExit(124)
PY
}

preflight_failed() {
  local reason="$1" exit_code="${2:-2}"
  printf 'edge_scout_schedule_failed: %s\n' "${reason}" >&2
  write_summary failed "${exit_code}" "${reason}"
  notify_failure "${RUN_ID} preflight failed: ${reason}; log=${LOG_PATH}"
  exit "${exit_code}"
}

if [[ ! -f "${SCHEDULE_ENV}" ]]; then
  preflight_failed "missing_reviewed_environment_file" 2
fi
set -a
# shellcheck disable=SC1090
source "${SCHEDULE_ENV}"
set +a
TIMEOUT_SECONDS="${EDGE_SCOUT_SCHEDULE_TIMEOUT_SECONDS:-${TIMEOUT_SECONDS}}"
RETAIN_LOGS="${EDGE_SCOUT_SCHEDULE_RETAIN_LOGS:-${RETAIN_LOGS}}"

for required in EDGE_SCOUT_CALENDAR EDGE_SCOUT_CALENDAR_SHA256 EDGE_SCOUT_CALENDAR_APPROVAL; do
  if [[ -z "${!required:-}" ]]; then
    preflight_failed "missing_${required}" 2
  fi
done

set +e
EDGE_SCOUT_CALENDAR_VALUE="${EDGE_SCOUT_CALENDAR}" \
EDGE_SCOUT_CALENDAR_SHA256_VALUE="${EDGE_SCOUT_CALENDAR_SHA256}" \
EDGE_SCOUT_CALENDAR_APPROVAL_VALUE="${EDGE_SCOUT_CALENDAR_APPROVAL}" \
  "${VENV_PYTHON}" - <<'PY'
import hashlib, json, os
from pathlib import Path
calendar = Path(os.environ["EDGE_SCOUT_CALENDAR_VALUE"]).resolve()
approval_path = Path(os.environ["EDGE_SCOUT_CALENDAR_APPROVAL_VALUE"])
approval = json.loads(approval_path.read_text(encoding="utf-8"))
digest = hashlib.sha256(calendar.read_bytes()).hexdigest()
expected = os.environ["EDGE_SCOUT_CALENDAR_SHA256_VALUE"].lower()
if approval.get("review_status") != "approved_for_read_only_research_production":
    raise SystemExit("calendar approval status is not valid for read-only research production")
if approval.get("approved_scope") != "edge_scout_read_only_research_production_only":
    raise SystemExit("calendar approval scope mismatch")
if approval.get("calendar_sha256") != expected or digest != expected:
    raise SystemExit("calendar approval digest mismatch")
approval_calendar = (approval_path.parents[2] / approval["calendar_path"]).resolve()
if approval_calendar != calendar:
    raise SystemExit("calendar approval path mismatch")
PY
approval_status=$?
set -e
if [[ ${approval_status} -ne 0 ]]; then
  preflight_failed calendar_approval_validation_failed "${approval_status}"
fi

set +e
run_timed /bin/bash "${ROOT_DIR}/scripts/edge_scout_scan.sh" update
status=$?
if [[ ${status} -eq 0 ]]; then
  export EDGE_SCOUT_RUN_ID="${RUN_ID}"
  run_timed /bin/bash "${ROOT_DIR}/scripts/edge_scout_production.sh"
  status=$?
fi
set -e

if [[ ${status} -eq 0 ]]; then
  write_summary success 0 completed
else
  write_summary failed "${status}" scheduled_command_failed
  notify_failure "${RUN_ID} failed with exit code ${status}; log=${LOG_PATH}"
fi

LOG_DIR_VALUE="${LOG_DIR}" RETAIN_LOGS_VALUE="${RETAIN_LOGS}" "${VENV_PYTHON}" - <<'PY'
import os
from pathlib import Path
root = Path(os.environ["LOG_DIR_VALUE"])
keep = max(1, int(os.environ["RETAIN_LOGS_VALUE"]))
logs = sorted(root.glob("scheduled-*.log"), key=lambda path: path.stat().st_mtime, reverse=True)
for log in logs[keep:]:
    summary = log.with_name(log.stem + ".summary.json")
    log.unlink(missing_ok=True)
    summary.unlink(missing_ok=True)
PY

exit "${status}"
