#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_PYTHON="${VENV_PYTHON:-${ROOT_DIR}/.venv/bin/python}"
DATA_ROOT="${EDGE_SCOUT_DATA_ROOT:-${ROOT_DIR}/PFrontStockData}"
CONFIG="${EDGE_SCOUT_CONFIG:-${ROOT_DIR}/yaml/edge_scout_v1.yaml}"
OUTPUT_ROOT="${EDGE_SCOUT_OUTPUT_ROOT:-${ROOT_DIR}/output/edge_scout_production}"
APPROVED_CALENDAR="${ROOT_DIR}/config/review_candidates/baostock_calendar_2026_candidate.txt"
CALENDAR="${EDGE_SCOUT_CALENDAR:-${APPROVED_CALENDAR}}"
CALENDAR_SHA256="${EDGE_SCOUT_CALENDAR_SHA256:-fd77a04f5268efd4803ca99877a0de4b126a51ad01a45b24c443afc8f8aa3ee7}"
RUN_ID="${EDGE_SCOUT_RUN_ID:-production-$(date +%Y%m%d_%H%M%S)}"
RUN_DIR="${OUTPUT_ROOT}/operations/${RUN_ID}"
LOCK_DIR="${OUTPUT_ROOT}/.edge_scout_production.lock"
LOG_PATH="${RUN_DIR}/run.log"
SUMMARY_PATH="${RUN_DIR}/operations_summary.json"

if [[ ! -x "${VENV_PYTHON}" ]]; then
  printf 'edge_scout_production_failed: missing python %s\n' "${VENV_PYTHON}" >&2
  exit 2
fi
mkdir -p "${OUTPUT_ROOT}"
if ! mkdir "${LOCK_DIR}" 2>/dev/null; then
  printf 'edge_scout_production_failed: lock held at %s\n' "${LOCK_DIR}" >&2
  exit 3
fi
RUN_ID_VALUE="${RUN_ID}" LOCK_DIR_VALUE="${LOCK_DIR}" OWNER_PID="$$" "${VENV_PYTHON}" - <<'PY'
import json, os, socket
from datetime import datetime, timezone
from pathlib import Path
payload = {
    "schema_version": 1,
    "pid": int(os.environ["OWNER_PID"]),
    "hostname": socket.gethostname(),
    "run_id": os.environ["RUN_ID_VALUE"],
    "started_at_utc": datetime.now(timezone.utc).isoformat(),
}
Path(os.environ["LOCK_DIR_VALUE"], "owner.json").write_text(
    json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8"
)
PY
cleanup() { rm -rf "${LOCK_DIR}"; }
trap cleanup EXIT INT TERM
mkdir -p "${RUN_DIR}"
cd "${ROOT_DIR}"

set +e
PYTHONPATH="${ROOT_DIR}/src" PYTHONNOUSERSITE=1 PYTHONSAFEPATH=1 \
  "${VENV_PYTHON}" -B scripts/run_edge_scout_production.py \
  --data-root "${DATA_ROOT}" --config "${CONFIG}" --output-root "${OUTPUT_ROOT}" \
  --calendar "${CALENDAR}" --calendar-sha256 "${CALENDAR_SHA256}" \
  --run-id "${RUN_ID}" 2>&1 | tee "${LOG_PATH}"
STATUS=${PIPESTATUS[0]}
set -e

STATUS_VALUE="$( [[ "${STATUS}" -eq 0 ]] && printf success || printf failed )" \
RUN_ID_VALUE="${RUN_ID}" LOG_PATH_VALUE="${LOG_PATH}" OUTPUT_ROOT_VALUE="${OUTPUT_ROOT}" \
SUMMARY_PATH_VALUE="${SUMMARY_PATH}" STATUS_CODE="${STATUS}" "${VENV_PYTHON}" - <<'PY'
import json, os
from datetime import datetime, timezone
from pathlib import Path
payload = {
    "schema_version": "edge_scout_research_operations_v1",
    "status": os.environ["STATUS_VALUE"],
    "exit_code": int(os.environ["STATUS_CODE"]),
    "run_id": os.environ["RUN_ID_VALUE"],
    "log_path": os.environ["LOG_PATH_VALUE"],
    "latest_path": str(Path(os.environ["OUTPUT_ROOT_VALUE"]) / "latest.json"),
    "finished_at_utc": datetime.now(timezone.utc).isoformat(),
}
target = Path(os.environ["SUMMARY_PATH_VALUE"])
temporary = target.with_suffix(".tmp")
temporary.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
os.replace(temporary, target)
PY
exit "${STATUS}"
