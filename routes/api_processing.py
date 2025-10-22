from __future__ import annotations

import json
from pathlib import Path

from flask import Blueprint, jsonify, request
from flask_login import login_required
from config import app_config_store as _store

bp = Blueprint("api_processing", __name__, url_prefix="/api/processing_prefs")
legacy_bp = Blueprint("api_processing_legacy", __name__)

# Storage compatible with legacy locations
PROCESSING_PREFS_FILE = (
    Path(__file__).resolve().parents[1] / "debug" / "processing_prefs.json"
)
DEFAULT_PROCESSING_PREFS = {
    "exclude_keywords": [],
    "require_attachments": False,
    "max_email_size_mb": None,
    "sender_priority": {},
    "retry_count": 0,
    "retry_delay_sec": 2,
    "webhook_timeout_sec": 30,
    "rate_limit_per_hour": 5,
    "notify_on_failure": False,
    "mirror_media_to_custom": True,  # Activer le miroir vers le webhook personnalisé par défaut
}


def _load_processing_prefs() -> dict:
    """Load prefs from DB if available, else file; merge with defaults."""
    data = _store.get_config_json(
        "processing_prefs", file_fallback=PROCESSING_PREFS_FILE
    ) or {}
    if isinstance(data, dict):
        return {**DEFAULT_PROCESSING_PREFS, **data}
    return DEFAULT_PROCESSING_PREFS.copy()


def _save_processing_prefs(prefs: dict) -> bool:
    """Persist prefs to DB with file fallback."""
    return _store.set_config_json(
        "processing_prefs", prefs, file_fallback=PROCESSING_PREFS_FILE
    )


def _validate_processing_prefs(payload: dict) -> tuple[bool, str, dict]:
    out = _load_processing_prefs()
    try:
        # Alias/extended keys used by UI and tests
        if "exclude_keywords_recadrage" in payload:
            val = payload["exclude_keywords_recadrage"]
            if not isinstance(val, list) or not all(isinstance(x, str) for x in val):
                return False, "exclude_keywords_recadrage doit être une liste de chaînes", out
            out["exclude_keywords_recadrage"] = [x.strip() for x in val if x and isinstance(x, str)]
        if "exclude_keywords_autorepondeur" in payload:
            val = payload["exclude_keywords_autorepondeur"]
            if not isinstance(val, list) or not all(isinstance(x, str) for x in val):
                return False, "exclude_keywords_autorepondeur doit être une liste de chaînes", out
            out["exclude_keywords_autorepondeur"] = [x.strip() for x in val if x and isinstance(x, str)]

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


@bp.route("", methods=["GET"])  # GET /api/processing_prefs
@login_required
def get_processing_prefs():
    try:
        return jsonify({"success": True, "prefs": _load_processing_prefs()})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@bp.route("", methods=["POST"])  # POST /api/processing_prefs
@login_required
def update_processing_prefs():
    try:
        payload = request.get_json(force=True, silent=True) or {}
        ok, msg, new_prefs = _validate_processing_prefs(payload)
        if not ok:
            return jsonify({"success": False, "message": msg}), 400
        if _save_processing_prefs(new_prefs):
            return jsonify({"success": True, "message": "Préférences mises à jour.", "prefs": new_prefs})
        return jsonify({"success": False, "message": "Erreur lors de la sauvegarde."}), 500
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


# --- Legacy alias routes to maintain backward-compat URLs used by tests/UI ---
@legacy_bp.route("/api/get_processing_prefs", methods=["GET"])  # legacy URL
@login_required
def legacy_get_processing_prefs():
    return get_processing_prefs()


@legacy_bp.route("/api/update_processing_prefs", methods=["POST"])  # legacy URL
@login_required
def legacy_update_processing_prefs():
    return update_processing_prefs()
