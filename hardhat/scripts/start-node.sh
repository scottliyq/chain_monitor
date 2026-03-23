#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
CONFIG_PATH="${PROJECT_DIR}/hardhat.config.js"

cd "${PROJECT_DIR}"

HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8545}"

if command -v hardhat >/dev/null 2>&1; then
  exec hardhat --config "${CONFIG_PATH}" node --hostname "${HOST}" --port "${PORT}"
fi

if command -v npx >/dev/null 2>&1; then
  exec npx --no-install hardhat --config "${CONFIG_PATH}" node --hostname "${HOST}" --port "${PORT}"
fi

echo "未找到 hardhat 命令，请先确保 Hardhat 已安装并可在当前 shell 中执行。" >&2
exit 1
