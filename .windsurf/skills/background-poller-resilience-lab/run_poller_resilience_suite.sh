#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
cd "${REPO_ROOT}"

if [ -f /mnt/venv_ext4/venv_render_signal_server/bin/activate ]; then
  # shellcheck disable=SC1091
  source /mnt/venv_ext4/venv_render_signal_server/bin/activate
else
  echo "[warn] Virtualenv /mnt/venv_ext4/venv_render_signal_server introuvable, utilisation de l'environnement courant." >&2
fi

pytest \
  tests/test_background_lock.py \
  tests/test_background_lock_extra.py \
  tests/test_lock_redis.py \
  tests/test_polling_dynamic_reload.py
pytest -m "redis or resilience"
