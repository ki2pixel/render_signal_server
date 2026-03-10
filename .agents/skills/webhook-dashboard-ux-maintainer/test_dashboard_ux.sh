#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
cd "${REPO_ROOT}"

echo "[info] Dashboard UX manual test checklist"
echo "1. Open dashboard.html in browser"
echo "2. Check console for errors (should be clean)"
echo "3. Test keyboard navigation (Tab through panels)"
echo "4. Verify responsive design (<480px)"
echo "5. Test auto-save flows (modify webhook panel, wait 2-3s)"
echo "6. Verify ARIA roles (tablist, tabpanel, aria-expanded)"
echo "7. Test toast notifications (generate magic link)"

if [ -f /mnt/venv_ext4/venv_render_signal_server/bin/activate ]; then
  # shellcheck disable=SC1091
  source /mnt/venv_ext4/venv_render_signal_server/bin/activate
  echo "\n[info] Running backend tests that affect dashboard UX"
  pytest tests/test_api_admin_migrate_configs.py tests/routes/test_api_routing_rules.py
else
  echo "[warn] Virtualenv not available, skipping backend tests"
fi
