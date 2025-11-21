from __future__ import annotations

import os
import json
from pathlib import Path

from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user

from utils.time_helpers import parse_time_hhmm
from config import app_config_store as _store

# Phase 5: Migration vers WebhookConfigService
from services import WebhookConfigService

bp = Blueprint("api_webhooks", __name__, url_prefix="/api/webhooks")

# Storage path kept compatible with legacy location used in app_render.py
WEBHOOK_CONFIG_FILE = (
    Path(__file__).resolve().parents[1] / "debug" / "webhook_config.json"
)

# Phase 5: Récupérer l'instance WebhookConfigService (Singleton)
try:
    _webhook_service = WebhookConfigService.get_instance()
except ValueError:
    # Fallback: initialiser si pas encore fait (cas tests)
    _webhook_service = WebhookConfigService.get_instance(
        file_path=WEBHOOK_CONFIG_FILE,
        external_store=_store
    )


def _load_webhook_config() -> dict:
    """Load persisted config from DB if available, else file fallback.
    
    Phase 5: Utilise WebhookConfigService (cache + validation).
    """
    return _webhook_service.get_all_config()


def _save_webhook_config(config: dict) -> bool:
    """Persist config to DB with file fallback.
    
    Phase 5: Utilise WebhookConfigService (validation automatique + cache invalidation).
    """
    success, _ = _webhook_service.update_config(config)
    return success


def _mask_url(url: str | None) -> str | None:
    if not url:
        return None
    if url.startswith("http"):
        parts = url.split("/")
        if len(parts) > 3:
            return f"{parts[0]}//{parts[2]}/***"
        return url[:30] + "***"
    return None


@bp.route("/config", methods=["GET"])  # GET /api/webhooks/config
@login_required
def get_webhook_config():
    persisted = _load_webhook_config()

    # Defaults from environment to mirror legacy behavior in app_render
    webhook_url = persisted.get("webhook_url") or os.environ.get("WEBHOOK_URL")
    webhook_ssl_verify = persisted.get(
        "webhook_ssl_verify",
        os.environ.get("WEBHOOK_SSL_VERIFY", "true").strip().lower()
        in ("1", "true", "yes", "on"),
    )
    # New: global enable/disable for sending webhooks (default: true)
    webhook_sending_enabled = persisted.get(
        "webhook_sending_enabled",
        os.environ.get("WEBHOOK_SENDING_ENABLED", "true").strip().lower()
        in ("1", "true", "yes", "on"),
    )
    # Time window for global webhook toggle (may be empty strings)
    webhook_time_start = (persisted.get("webhook_time_start") or "").strip()
    webhook_time_end = (persisted.get("webhook_time_end") or "").strip()
    
    # Absence pause configuration
    absence_pause_enabled = persisted.get("absence_pause_enabled", False)
    absence_pause_days = persisted.get("absence_pause_days", [])
    if not isinstance(absence_pause_days, list):
        absence_pause_days = []

    config = {
        "webhook_url": webhook_url or _mask_url(webhook_url),
        "webhook_ssl_verify": webhook_ssl_verify,
        "webhook_sending_enabled": bool(webhook_sending_enabled),
        # Expose as None when empty to be explicit in API response
        "webhook_time_start": webhook_time_start or None,
        "webhook_time_end": webhook_time_end or None,
        "absence_pause_enabled": bool(absence_pause_enabled),
        "absence_pause_days": absence_pause_days,
    }
    return jsonify({"success": True, "config": config}), 200


@bp.route("/config", methods=["POST"])  # POST /api/webhooks/config
@login_required
def update_webhook_config():
    payload = request.get_json(silent=True) or {}

    config = _load_webhook_config()

    if "webhook_url" in payload:
        val = payload["webhook_url"].strip() if payload["webhook_url"] else None
        # Exiger HTTPS strict
        if val and not val.startswith("https://"):
            return (
                jsonify({"success": False, "message": "webhook_url doit être une URL HTTPS valide."}),
                400,
            )
        config["webhook_url"] = val

    if "webhook_ssl_verify" in payload:
        config["webhook_ssl_verify"] = bool(payload["webhook_ssl_verify"])

    # New flag: webhook_sending_enabled
    if "webhook_sending_enabled" in payload:
        config["webhook_sending_enabled"] = bool(payload["webhook_sending_enabled"])
    
    # Absence pause configuration
    if "absence_pause_enabled" in payload:
        config["absence_pause_enabled"] = bool(payload["absence_pause_enabled"])
    
    if "absence_pause_days" in payload:
        days = payload["absence_pause_days"]
        if not isinstance(days, list):
            return jsonify({"success": False, "message": "absence_pause_days doit être une liste."}), 400
        
        # Valider les jours
        valid_days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        normalized_days = [str(d).lower() for d in days if isinstance(d, str)]
        invalid_days = [d for d in normalized_days if d not in valid_days]
        
        if invalid_days:
            return jsonify({"success": False, "message": f"Jours invalides: {', '.join(invalid_days)}"}), 400
        
        config["absence_pause_days"] = normalized_days
    
    # Validation: si absence_pause_enabled est True, vérifier qu'au moins un jour est sélectionné
    if config.get("absence_pause_enabled") and not config.get("absence_pause_days"):
        return jsonify({"success": False, "message": "Au moins un jour doit être sélectionné pour activer la pause absence."}), 400

    # Optional: accept time window fields here too, for convenience
    # Validate format using parse_time_hhmm when provided and non-empty
    if "webhook_time_start" in payload or "webhook_time_end" in payload:
        start = (str(payload.get("webhook_time_start", "")) or "").strip()
        end = (str(payload.get("webhook_time_end", "")) or "").strip()
        # If both empty -> clear
        if start == "" and end == "":
            config["webhook_time_start"] = ""
            config["webhook_time_end"] = ""
        else:
            # Require both if one is provided
            if not start or not end:
                return jsonify({"success": False, "message": "Both webhook_time_start and webhook_time_end are required (or both empty to clear)."}), 400
            if parse_time_hhmm(start) is None or parse_time_hhmm(end) is None:
                return jsonify({"success": False, "message": "Invalid time format. Use HHhMM or HH:MM (e.g., 11h30, 17:45)."}), 400
            config["webhook_time_start"] = start
            config["webhook_time_end"] = end

    # Nettoyer les champs obsolètes s'ils existent (ne pas supprimer presence_* gérés ci-dessus)
    obsolete_fields = [
        "recadrage_webhook_url",
        "autorepondeur_webhook_url",
        "polling_enabled",
    ]
    for field in obsolete_fields:
        if field in config:
            try:
                del config[field]
            except Exception:
                pass

    if not _save_webhook_config(config):
        return (
            jsonify({"success": False, "message": "Erreur lors de la sauvegarde de la configuration."}),
            500,
        )

    return jsonify({"success": True, "message": "Configuration mise à jour avec succès."}), 200


# ---- Dedicated time window for global webhook toggle ----

@bp.route("/time-window", methods=["GET"])  # GET /api/webhooks/time-window
@login_required
def get_webhook_global_time_window():
    cfg = _load_webhook_config()
    start = (cfg.get("webhook_time_start") or "").strip()
    end = (cfg.get("webhook_time_end") or "").strip()
    return jsonify({
        "success": True,
        "webhooks_time_start": start or None,
        "webhooks_time_end": end or None,
    }), 200


@bp.route("/time-window", methods=["POST"])  # POST /api/webhooks/time-window
@login_required
def set_webhook_global_time_window():
    payload = request.get_json(silent=True) or {}
    start = (payload.get("start") or "").strip()
    end = (payload.get("end") or "").strip()

    # Clear both -> disable constraint
    if start == "" and end == "":
        cfg = _load_webhook_config()
        cfg["webhook_time_start"] = ""
        cfg["webhook_time_end"] = ""
        if not _save_webhook_config(cfg):
            return jsonify({"success": False, "message": "Erreur lors de la sauvegarde."}), 500
        return jsonify({
            "success": True,
            "message": "Time window cleared (no constraints).",
            "webhooks_time_start": None,
            "webhooks_time_end": None,
        }), 200

    # Require both values when not clearing
    if not start or not end:
        return jsonify({"success": False, "message": "Both start and end are required (or both empty to clear)."}), 400

    # Validate format using parse_time_hhmm
    if parse_time_hhmm(start) is None or parse_time_hhmm(end) is None:
        return jsonify({"success": False, "message": "Invalid time format. Use HHhMM or HH:MM (e.g., 11h30, 17:45)."}), 400

    cfg = _load_webhook_config()
    cfg["webhook_time_start"] = start
    cfg["webhook_time_end"] = end
    if not _save_webhook_config(cfg):
        return jsonify({"success": False, "message": "Erreur lors de la sauvegarde."}), 500
    return jsonify({
        "success": True,
        "message": "Time window updated.",
        "webhooks_time_start": start,
        "webhooks_time_end": end,
    }), 200
