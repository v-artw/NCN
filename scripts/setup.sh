#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"

"${PYTHON_BIN}" -m venv "${ROOT_DIR}/.venv"
"${ROOT_DIR}/.venv/bin/python" -m pip install --upgrade pip
"${ROOT_DIR}/.venv/bin/python" -m pip install -e "${ROOT_DIR}[dev]"
printf 'NCN setup complete: %s\n' "${ROOT_DIR}/.venv/bin/python"
