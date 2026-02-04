#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
cd "${REPO_ROOT}"

if [ -f /mnt/venv_ext4/venv_render_signal_server/bin/activate ]; then
  # shellcheck disable=SC1091
  source /mnt/venv_ext4/venv_render_signal_server/bin/activate
else
  echo "[warn] Virtualenv /mnt/venv_ext4/venv_render_signal_server introuvable; utilisation de l'environnement courant." >&2
fi

echo "[info] Inspecting Redis configs"
python -m scripts.check_config_store --keys magic_link_tokens routing_rules processing_prefs webhook_config --raw

echo "\n[info] Comparing with debug/*.json fallbacks"
for key in magic_link_tokens routing_rules processing_prefs webhook_config; do
  echo "--- $key ---"
  if [ -f "debug/${key}.json" ]; then
    diff -u "debug/${key}.json" <(python -c "import json, sys; from config import app_config_store; print(json.dumps(app_config_store.get_config_json('$key'), indent=2))") || true
  else
    echo "debug/${key}.json not found"
  fi
done
