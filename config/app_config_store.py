"""
config.app_config_store
~~~~~~~~~~~~~~~~~~~~~~~~

Key-Value configuration store with External JSON backend and file fallback.
- Provides get_config_json()/set_config_json() for dict payloads.
- External backend configured via env vars: EXTERNAL_CONFIG_BASE_URL, CONFIG_API_TOKEN.
- If external backend is unavailable, falls back to per-key JSON files provided by callers.

Security: no secrets are logged; errors are swallowed and caller can fallback.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

try:
    import requests  # type: ignore
except Exception:  # requests may be unavailable in some test contexts
    requests = None  # type: ignore

def get_config_json(key: str, *, file_fallback: Optional[Path] = None) -> Dict[str, Any]:
    """Fetch config dict for a key from External JSON backend, with file fallback.
    Returns empty dict on any error.
    """
    # External backend (PHP)
    base_url = os.environ.get("EXTERNAL_CONFIG_BASE_URL")
    api_token = os.environ.get("CONFIG_API_TOKEN")
    if base_url and api_token and requests is not None:
        try:
            data = _external_config_get(base_url, api_token, key)
            if isinstance(data, dict):
                return data
        except Exception:
            pass

    # File fallback
    if file_fallback and file_fallback.exists():
        try:
            with open(file_fallback, "r", encoding="utf-8") as f:
                data = json.load(f) or {}
                if isinstance(data, dict):
                    return data
        except Exception:
            pass
    return {}


def set_config_json(key: str, value: Dict[str, Any], *, file_fallback: Optional[Path] = None) -> bool:
    """Persist config dict for a key into External backend, fallback to file if needed."""
    # External backend (PHP)
    base_url = os.environ.get("EXTERNAL_CONFIG_BASE_URL")
    api_token = os.environ.get("CONFIG_API_TOKEN")
    if base_url and api_token and requests is not None:
        try:
            ok = _external_config_set(base_url, api_token, key, value)
            if ok:
                return True
        except Exception:
            pass

    # File fallback
    if file_fallback is not None:
        try:
            file_fallback.parent.mkdir(parents=True, exist_ok=True)
            with open(file_fallback, "w", encoding="utf-8") as f:
                json.dump(value, f, indent=2, ensure_ascii=False)
            return True
        except Exception:
            return False
    return False


# ---------------------------------------------------------------------------
# External JSON backend helpers
# ---------------------------------------------------------------------------
def _external_config_get(base_url: str, token: str, key: str) -> Dict[str, Any]:
    """GET config JSON from external PHP service. Raises on error."""
    url = base_url.rstrip('/') + '/config_api.php'
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    params = {"key": key}
    # Small timeout for robustness
    resp = requests.get(url, headers=headers, params=params, timeout=6)  # type: ignore
    if resp.status_code != 200:
        raise RuntimeError(f"external get http={resp.status_code}")
    data = resp.json()
    if not isinstance(data, dict) or not data.get("success"):
        raise RuntimeError("external get failed")
    cfg = data.get("config") or {}
    return cfg if isinstance(cfg, dict) else {}


def _external_config_set(base_url: str, token: str, key: str, value: Dict[str, Any]) -> bool:
    """POST config JSON to external PHP service. Returns True on success."""
    url = base_url.rstrip('/') + '/config_api.php'
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json", "Accept": "application/json"}
    body = {"key": key, "config": value}
    resp = requests.post(url, headers=headers, data=json.dumps(body), timeout=8)  # type: ignore
    if resp.status_code != 200:
        return False
    try:
        data = resp.json()
    except Exception:
        return False
    return bool(isinstance(data, dict) and data.get("success"))
