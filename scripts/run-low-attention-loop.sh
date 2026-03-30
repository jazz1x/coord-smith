#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${ROOT}/.venv/bin/python"

if [[ ! -x "${PYTHON_BIN}" ]]; then
  PYTHON_BIN="$(command -v python3)"
fi

export PYTHONPATH="${ROOT}/src${PYTHONPATH:+:${PYTHONPATH}}"

cd "${ROOT}"
exec "${PYTHON_BIN}" -m ez_ax.rag.autoloop_runner "$@"
