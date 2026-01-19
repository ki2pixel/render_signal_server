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


_REDIS_CLIENT = None


def _get_redis_client():
    global _REDIS_CLIENT

    if _REDIS_CLIENT is not None:
        return _REDIS_CLIENT

    redis_url = os.environ.get("REDIS_URL")
    if not isinstance(redis_url, str) or not redis_url.strip():
        return None

    try:
        import redis  # type: ignore

        _REDIS_CLIENT = redis.Redis.from_url(redis_url, decode_responses=True)
        return _REDIS_CLIENT
    except Exception:
        return None


def _config_redis_key(key: str) -> str:
    prefix = os.environ.get("CONFIG_STORE_REDIS_PREFIX", "r:ss:config:")
    return f"{prefix}{key}"


def _store_mode() -> str:
    mode = os.environ.get("CONFIG_STORE_MODE", "redis_first")
    if not isinstance(mode, str):
        return "redis_first"
    mode = mode.strip().lower()
    return mode if mode in {"redis_first", "php_first"} else "redis_first"


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return bool(default)
    return str(raw).strip().lower() in {"1", "true", "yes", "y", "on"}


def _redis_get_json(key: str) -> Optional[Dict[str, Any]]:
    if _env_bool("CONFIG_STORE_DISABLE_REDIS", False):
        return None

    client = _get_redis_client()
    if client is None:
        return None

    try:
        raw = client.get(_config_redis_key(key))
        if not raw:
            return None
        data = json.loads(raw)
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _redis_set_json(key: str, value: Dict[str, Any]) -> bool:
    if _env_bool("CONFIG_STORE_DISABLE_REDIS", False):
        return False

    client = _get_redis_client()
    if client is None:
        return False

    try:
        client.set(_config_redis_key(key), json.dumps(value, ensure_ascii=False))
        return True
    except Exception:
        return False

def get_config_json(key: str, *, file_fallback: Optional[Path] = None) -> Dict[str, Any]:
    """Fetch config dict for a key from External JSON backend, with file fallback.
    Returns empty dict on any error.
    """
    mode = _store_mode()

    if mode == "redis_first":
        data = _redis_get_json(key)
        if isinstance(data, dict):
            return data

    base_url = os.environ.get("EXTERNAL_CONFIG_BASE_URL")
    api_token = os.environ.get("CONFIG_API_TOKEN")
    if base_url and api_token and requests is not None:
        try:
            data = _external_config_get(base_url, api_token, key)
            if isinstance(data, dict):
                return data
        except Exception:
            pass

    if mode == "php_first":
        data = _redis_get_json(key)
        if isinstance(data, dict):
            return data

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
    mode = _store_mode()

    if mode == "redis_first":
        if _redis_set_json(key, value):
            return True

    base_url = os.environ.get("EXTERNAL_CONFIG_BASE_URL")
    api_token = os.environ.get("CONFIG_API_TOKEN")
    if base_url and api_token and requests is not None:
        try:
            ok = _external_config_set(base_url, api_token, key, value)
            if ok:
                return True
        except Exception:
            pass

    if mode == "php_first":
        if _redis_set_json(key, value):
            return True

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
