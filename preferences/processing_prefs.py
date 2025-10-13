"""
preferences/processing_prefs.py

Processing Preferences management (load/save/validate) with Redis and file fallbacks.
- Pure helpers: callers inject redis client, file path, defaults, and logger.
- Strict validation of types and bounds.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Tuple


def load_processing_prefs(
    *,
    redis_client,
    file_path: Path,
    defaults: dict,
    logger,
    redis_key: str | None = None,
) -> dict:
    # Try Redis first
    try:
        if redis_client is not None and redis_key:
            raw = redis_client.get(redis_key)
            if raw:
                try:
                    data = json.loads(raw if isinstance(raw, str) else raw.decode("utf-8"))
                    if isinstance(data, dict):
                        return {**defaults, **data}
                except Exception:
                    pass
    except Exception as e:
        if logger:
            logger.error(f"PROCESSING_PREFS: redis load error: {e}")

    # Fallback to file
    try:
        if file_path.exists():
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return {**defaults, **data}
    except Exception as e:
        if logger:
            logger.error(f"PROCESSING_PREFS: file load error: {e}")
    return dict(defaults)


def save_processing_prefs(
    prefs: dict,
    *,
    redis_client,
    file_path: Path,
    logger,
    redis_key: str | None = None,
) -> bool:
    # Try Redis first
    try:
        if redis_client is not None and redis_key:
            redis_client.set(redis_key, json.dumps(prefs, ensure_ascii=False))
            return True
    except Exception as e:
        if logger:
            logger.error(f"PROCESSING_PREFS: redis save error: {e}")

    # Fallback to file
    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(prefs, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        if logger:
            logger.error(f"PROCESSING_PREFS: file save error: {e}")
        return False


def validate_processing_prefs(payload: dict, defaults: dict) -> Tuple[bool, str, dict]:
    out = dict(defaults)
    try:
        if "exclude_keywords" in payload:
            val = payload["exclude_keywords"]
            if not isinstance(val, list) or not all(isinstance(x, str) for x in val):
                return False, "exclude_keywords doit être une liste de chaînes", out
            out["exclude_keywords"] = [x.strip() for x in val if x and isinstance(x, str)]

        if "require_attachments" in payload:
            out["require_attachments"] = bool(payload["require_attachments"])

        if "max_email_size_mb" in payload:
            v = payload["max_email_size_mb"]
            if v is None:
                out["max_email_size_mb"] = None
            else:
                vi = int(v)
                if vi <= 0:
                    return False, "max_email_size_mb doit être > 0 ou null", out
                out["max_email_size_mb"] = vi

        if "sender_priority" in payload:
            sp = payload["sender_priority"]
            if not isinstance(sp, dict):
                return False, "sender_priority doit être un objet {email: niveau}", out
            allowed = {"high", "medium", "low"}
            norm = {}
            for k, v in sp.items():
                if not isinstance(k, str) or not isinstance(v, str):
                    return False, "sender_priority: clés et valeurs doivent être des chaînes", out
                lv = v.lower().strip()
                if lv not in allowed:
                    return False, "sender_priority: niveau invalide (high|medium|low)", out
                norm[k.strip().lower()] = lv
            out["sender_priority"] = norm

        if "retry_count" in payload:
            rc = int(payload["retry_count"])
            if rc < 0 or rc > 10:
                return False, "retry_count hors limites (0..10)", out
            out["retry_count"] = rc

        if "retry_delay_sec" in payload:
            rd = int(payload["retry_delay_sec"])
            if rd < 0 or rd > 600:
                return False, "retry_delay_sec hors limites (0..600)", out
            out["retry_delay_sec"] = rd

        if "webhook_timeout_sec" in payload:
            to = int(payload["webhook_timeout_sec"])
            if to < 1 or to > 300:
                return False, "webhook_timeout_sec hors limites (1..300)", out
            out["webhook_timeout_sec"] = to

        if "rate_limit_per_hour" in payload:
            rl = int(payload["rate_limit_per_hour"])
            if rl < 0 or rl > 100000:
                return False, "rate_limit_per_hour hors limites (0..100000)", out
            out["rate_limit_per_hour"] = rl

        if "notify_on_failure" in payload:
            out["notify_on_failure"] = bool(payload["notify_on_failure"])

        return True, "ok", out
    except Exception as e:
        return False, f"Validation error: {e}", out
