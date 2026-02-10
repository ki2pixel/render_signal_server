#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../../.." && pwd)"
cd "${REPO_ROOT}"

if [ -f /mnt/venv_ext4/venv_render_signal_server/bin/activate ]; then
  # shellcheck disable=SC1091
  source /mnt/venv_ext4/venv_render_signal_server/bin/activate
else
  echo "[warn] Virtualenv /mnt/venv_ext4/venv_render_signal_server introuvable; utilisation de l'environnement courant." >&2
fi

# Determine test suite based on argument
case "${1:-full}" in
  "unit")
    echo "[info] Running unit tests only"
    pytest -m "not redis and not r2 and not resilience"
    ;;
  "redis")
    echo "[info] Running Redis-related tests"
    pytest -m redis --cov=config.app_config_store
    ;;
  "r2")
    echo "[info] Running R2-related tests"
    pytest -m r2 --cov=services.r2_transfer_service
    ;;
  "resilience")
    echo "[info] Running resilience tests"
    pytest -m "redis or resilience"
    ;;
  "polling")
    echo "[info] Running polling dynamic reload tests"
    pytest tests/test_polling_dynamic_reload.py
    ;;
  "full"|*)
    echo "[info] Running full test suite with coverage"
    pytest --cov=. --maxfail=1 --disable-warnings
    ;;
esac
