from __future__ import annotations

import os
import json
from pathlib import Path

from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user

from utils.validators import normalize_make_webhook_url as _normalize_make_webhook_url

bp = Blueprint("api_webhooks", __name__, url_prefix="/api/webhooks")

# Storage path kept compatible with legacy location used in app_render.py
WEBHOOK_CONFIG_FILE = (
    Path(__file__).resolve().parents[1] / "debug" / "webhook_config.json"
)


def _load_webhook_config() -> dict:
    if not WEBHOOK_CONFIG_FILE.exists():
        return {}
    try:
        with open(WEBHOOK_CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_webhook_config(config: dict) -> bool:
    try:
        WEBHOOK_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(WEBHOOK_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        return True
    except Exception:
        return False


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
    presence_flag = persisted.get(
        "presence_flag",
        os.environ.get("PRESENCE", "false").strip().lower() in ("1", "true", "yes", "on"),
    )
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
    config = {
        "webhook_url": webhook_url or _mask_url(webhook_url),
        "presence_flag": presence_flag,
        "webhook_ssl_verify": webhook_ssl_verify,
        "webhook_sending_enabled": bool(webhook_sending_enabled),
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

    if "presence_flag" in payload:
        config["presence_flag"] = bool(payload["presence_flag"])

    if "webhook_ssl_verify" in payload:
        config["webhook_ssl_verify"] = bool(payload["webhook_ssl_verify"])

    # New flag: webhook_sending_enabled
    if "webhook_sending_enabled" in payload:
        config["webhook_sending_enabled"] = bool(payload["webhook_sending_enabled"])

    # Nettoyer les champs obsolètes s'ils existent
    obsolete_fields = [
        "recadrage_webhook_url", "presence_true_url", "presence_false_url", 
        "autorepondeur_webhook_url", "polling_enabled"
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
