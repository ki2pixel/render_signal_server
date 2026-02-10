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

echo "[info] Running R2 transfer service tests"
pytest tests/test_r2_transfer_service.py

echo "\n[info] Running R2-specific orchestrator tests"
pytest tests/email_processing/test_routing_rules_orchestrator.py -k r2

echo "\n[info] Testing PHP diagnostics (if available)"
if [ -f deployment/public_html/test-direct.php ]; then
  echo "PHP test page available at deployment/public_html/test-direct.php"
else
  echo "[warn] PHP test page not found"
fi
