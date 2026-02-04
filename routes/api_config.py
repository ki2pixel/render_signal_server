from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask_login import login_required

from config import webhook_time_window
from config import app_config_store as _store
from config.settings import (
    RUNTIME_FLAGS_FILE,
    DISABLE_EMAIL_ID_DEDUP as DEFAULT_DISABLE_EMAIL_ID_DEDUP,
    ALLOW_CUSTOM_WEBHOOK_WITHOUT_LINKS as DEFAULT_ALLOW_CUSTOM_WEBHOOK_WITHOUT_LINKS,
    POLLING_TIMEZONE_STR,
)
from services import RuntimeFlagsService

bp = Blueprint("api_config", __name__, url_prefix="/api")

# Récupérer l'instance RuntimeFlagsService (Singleton)
# L'instance est déjà initialisée dans app_render.py
try:
    _runtime_flags_service = RuntimeFlagsService.get_instance()
except ValueError:
    # Fallback: initialiser si pas encore fait (cas tests)
    _runtime_flags_service = RuntimeFlagsService.get_instance(
        file_path=RUNTIME_FLAGS_FILE,
        defaults={
            "disable_email_id_dedup": bool(DEFAULT_DISABLE_EMAIL_ID_DEDUP),
            "allow_custom_webhook_without_links": bool(DEFAULT_ALLOW_CUSTOM_WEBHOOK_WITHOUT_LINKS),
            "gmail_ingress_enabled": True,
        },
        external_store=_store,
    )


# Wrappers legacy supprimés - Appels directs aux services


# ---- Time window (session-protected) ----

@bp.route("/get_webhook_time_window", methods=["GET"])
@login_required
def get_webhook_time_window():
    try:
        # Best-effort: pull latest values from external store to reflect remote edits
        try:
            cfg = _store.get_config_json("webhook_config") or {}
            gs = (cfg.get("global_time_start") or "").strip()
            ge = (cfg.get("global_time_end") or "").strip()
            # Only sync when BOTH values are provided (non-empty). Do NOT clear on double-empty here.
            if (gs != "" and ge != ""):
                webhook_time_window.update_time_window(gs, ge)
        except Exception:
            pass
        info = webhook_time_window.get_time_window_info()
        return (
            jsonify(
                {
                    "success": True,
                    "webhooks_time_start": info.get("start") or None,
                    "webhooks_time_end": info.get("end") or None,
                    "timezone": POLLING_TIMEZONE_STR,
                }
            ),
            200,
        )
    except Exception:
        return jsonify({"success": False, "message": "Erreur lors de la récupération de la fenêtre horaire."}), 500


@bp.route("/set_webhook_time_window", methods=["POST"])
@login_required
def set_webhook_time_window():
    try:
        payload = request.get_json(silent=True) or {}
        start = payload.get("start", "")
        end = payload.get("end", "")
        ok, msg = webhook_time_window.update_time_window(start, end)
        status = 200 if ok else 400
        info = webhook_time_window.get_time_window_info()
        # Best-effort: mirror the global time window to external config store under
        # webhook_config as global_time_start/global_time_end so that
        # https://webhook.kidpixel.fr/data/app_config/webhook_config.json reflects it too.
        try:
            cfg = _store.get_config_json("webhook_config") or {}
            cfg["global_time_start"] = (info.get("start") or "") or None
            cfg["global_time_end"] = (info.get("end") or "") or None
            # Do not fail the request if external store is unavailable
            _store.set_config_json("webhook_config", cfg)
        except Exception:
            pass
        return (
            jsonify(
                {
                    "success": ok,
                    "message": msg,
                    "webhooks_time_start": info.get("start") or None,
                    "webhooks_time_end": info.get("end") or None,
                }
            ),
            status,
        )
    except Exception:
        return jsonify({"success": False, "message": "Erreur interne lors de la mise à jour."}), 500


# ---- Runtime flags (session-protected) ----

@bp.route("/get_runtime_flags", methods=["GET"])
@login_required
def get_runtime_flags():
    """Récupère les flags runtime.
    
    Appel direct à RuntimeFlagsService (cache intelligent 60s).
    """
    try:
        # Appel direct au service (cache si valide, sinon reload)
        data = _runtime_flags_service.get_all_flags()
        return jsonify({"success": True, "flags": data}), 200
    except Exception:
        return jsonify({"success": False, "message": "Erreur interne"}), 500


@bp.route("/update_runtime_flags", methods=["POST"])
@login_required
def update_runtime_flags():
    """Met à jour les flags runtime.
    
    Appel direct à RuntimeFlagsService.update_flags() - Atomic update + invalidation cache.
    """
    try:
        payload = request.get_json(silent=True) or {}
        
        # Préparer les mises à jour (validation)
        updates = {}
        if "disable_email_id_dedup" in payload:
            updates["disable_email_id_dedup"] = bool(payload.get("disable_email_id_dedup"))
        if "allow_custom_webhook_without_links" in payload:
            updates["allow_custom_webhook_without_links"] = bool(payload.get("allow_custom_webhook_without_links"))
        if "gmail_ingress_enabled" in payload:
            updates["gmail_ingress_enabled"] = bool(payload.get("gmail_ingress_enabled"))
        
        # Appel direct au service (mise à jour atomique + persiste + invalide cache)
        if not _runtime_flags_service.update_flags(updates):
            return jsonify({"success": False, "message": "Erreur lors de la sauvegarde."}), 500
        
        # Récupérer les flags à jour
        data = _runtime_flags_service.get_all_flags()
        return jsonify({
            "success": True,
            "flags": data,
            "message": "Modifications enregistrées. Un redémarrage peut être nécessaire."
        }), 200
    except Exception:
        return jsonify({"success": False, "message": "Erreur interne"}), 500
