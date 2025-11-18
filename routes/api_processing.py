from __future__ import annotations

from pathlib import Path

from flask import Blueprint, jsonify, request
from flask_login import login_required
from config import app_config_store as _store
from preferences import processing_prefs as _prefs_module

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
    """
    Valide les préférences en normalisant les alias puis en déléguant à preferences.processing_prefs.
    Les alias 'exclude_keywords_recadrage' et 'exclude_keywords_autorepondeur' sont conservés dans le résultat
    mais la validation core est déléguée au module centralisé.
    """
    base_prefs = _load_processing_prefs()
    
    # Normalisation des alias: conserver les clés alias dans payload_normalized
    payload_normalized = dict(payload)
    
    # Validation des alias spécifiques (extend keys used by UI and tests)
    try:
        if "exclude_keywords_recadrage" in payload:
            val = payload["exclude_keywords_recadrage"]
            if not isinstance(val, list) or not all(isinstance(x, str) for x in val):
                return False, "exclude_keywords_recadrage doit être une liste de chaînes", base_prefs
            payload_normalized["exclude_keywords_recadrage"] = [x.strip() for x in val if x and isinstance(x, str)]
        
        if "exclude_keywords_autorepondeur" in payload:
            val = payload["exclude_keywords_autorepondeur"]
            if not isinstance(val, list) or not all(isinstance(x, str) for x in val):
                return False, "exclude_keywords_autorepondeur doit être une liste de chaînes", base_prefs
            payload_normalized["exclude_keywords_autorepondeur"] = [x.strip() for x in val if x and isinstance(x, str)]
    except Exception as e:
        return False, f"Alias validation error: {e}", base_prefs
    
    # Déléguer la validation des champs core au module centralisé
    ok, msg, validated_prefs = _prefs_module.validate_processing_prefs(payload_normalized, base_prefs)
    
    if not ok:
        return ok, msg, validated_prefs
    
    # Ajouter les alias validés au résultat final si présents
    if "exclude_keywords_recadrage" in payload_normalized:
        validated_prefs["exclude_keywords_recadrage"] = payload_normalized["exclude_keywords_recadrage"]
    if "exclude_keywords_autorepondeur" in payload_normalized:
        validated_prefs["exclude_keywords_autorepondeur"] = payload_normalized["exclude_keywords_autorepondeur"]
    
    return True, "ok", validated_prefs


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
