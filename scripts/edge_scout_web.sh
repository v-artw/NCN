#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${VENV_PYTHON:-${PROJECT_ROOT}/.venv/bin/python}"
HOST="${EDGE_SCOUT_WEB_HOST:-127.0.0.1}"
PORT="${EDGE_SCOUT_WEB_PORT:-9091}"

if [ ! -x "${PYTHON}" ]; then
    printf 'ERROR: Python 环境不存在，请先运行 ./scripts/setup.sh\n' >&2
    exit 1
fi

exec env PYTHONPATH="${PROJECT_ROOT}/src" PYTHONNOUSERSITE=1 PYTHONSAFEPATH=1 \
    "${PYTHON}" -B -m ashare_edge_scout.research_web \
    --project-root "${PROJECT_ROOT}" --host "${HOST}" --port "${PORT}" "$@"
