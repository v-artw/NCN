#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PLIST="${ROOT_DIR}/config/launchd/com.vartw.stock-ncn.edge-scout.plist"
ENV_FILE="${ROOT_DIR}/.env.edge_scout_schedule"
DOMAIN="gui/$(id -u)"
LABEL="com.vartw.stock-ncn.edge-scout"

if [[ ! -f "${ENV_FILE}" ]]; then
  printf 'launchd_install_failed: create and review %s first\n' "${ENV_FILE}" >&2
  exit 2
fi
plutil -lint "${PLIST}"
mkdir -p "${ROOT_DIR}/output/edge_scout_scheduler"
launchctl bootout "${DOMAIN}/${LABEL}" >/dev/null 2>&1 || true
launchctl bootstrap "${DOMAIN}" "${PLIST}"
launchctl enable "${DOMAIN}/${LABEL}"
launchctl print "${DOMAIN}/${LABEL}"
