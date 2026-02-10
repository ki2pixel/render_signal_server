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

echo "[info] Running routing rules service tests"
pytest tests/test_routing_rules_service.py

echo "\n[info] Running routing rules API tests"
pytest tests/routes/test_api_routing_rules.py

echo "\n[info] Running routing rules orchestrator tests"
pytest tests/email_processing/test_routing_rules_orchestrator.py

echo "\n[info] Testing stop_processing scenarios"
pytest tests/email_processing/test_routing_rules_orchestrator.py -k stop_processing
