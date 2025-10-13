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
    recadrage_url = persisted.get("recadrage_webhook_url") or os.environ.get(
        "RECADRAGE_MAKE_WEBHOOK_URL"
    )
    autorepondeur_url = persisted.get("autorepondeur_webhook_url") or os.environ.get(
        "AUTOREPONDEUR_MAKE_WEBHOOK_URL"
    )
    presence_flag = persisted.get(
        "presence_flag",
        os.environ.get("PRESENCE", "false").strip().lower() in ("1", "true", "yes", "on"),
    )
    presence_true_url = persisted.get("presence_true_url") or os.environ.get(
        "PRESENCE_TRUE_MAKE_WEBHOOK_URL"
    )
    presence_false_url = persisted.get("presence_false_url") or os.environ.get(
        "PRESENCE_FALSE_MAKE_WEBHOOK_URL"
    )
    webhook_ssl_verify = persisted.get(
        "webhook_ssl_verify",
        os.environ.get("WEBHOOK_SSL_VERIFY", "true").strip().lower()
        in ("1", "true", "yes", "on"),
    )
    polling_enabled = persisted.get(
        "polling_enabled",
        os.environ.get("ENABLE_BACKGROUND_TASKS", "0").strip().lower()
        in ("1", "true", "yes", "on"),
    )

    config = {
        "webhook_url": webhook_url or _mask_url(webhook_url),
        "recadrage_webhook_url": recadrage_url or _mask_url(recadrage_url),
        "presence_flag": presence_flag,
        "presence_true_url": presence_true_url or _mask_url(presence_true_url),
        "presence_false_url": presence_false_url or _mask_url(presence_false_url),
        "autorepondeur_webhook_url": autorepondeur_url or _mask_url(autorepondeur_url),
        "webhook_ssl_verify": webhook_ssl_verify,
        "polling_enabled": polling_enabled,
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

    if "recadrage_webhook_url" in payload:
        val = payload["recadrage_webhook_url"].strip() if payload["recadrage_webhook_url"] else None
        # Exiger HTTPS strict
        if val and not val.startswith("https://"):
            return (
                jsonify({"success": False, "message": "recadrage_webhook_url doit être une URL HTTPS valide."}),
                400,
            )
        config["recadrage_webhook_url"] = val

    if "presence_flag" in payload:
        config["presence_flag"] = bool(payload["presence_flag"])

    if "presence_true_url" in payload:
        val = payload["presence_true_url"].strip() if payload["presence_true_url"] else None
        if val:
            val = _normalize_make_webhook_url(val)
        config["presence_true_url"] = val

    if "presence_false_url" in payload:
        val = payload["presence_false_url"].strip() if payload["presence_false_url"] else None
        if val:
            val = _normalize_make_webhook_url(val)
        config["presence_false_url"] = val

    if "autorepondeur_webhook_url" in payload:
        val = payload["autorepondeur_webhook_url"].strip() if payload["autorepondeur_webhook_url"] else None
        if val:
            val = _normalize_make_webhook_url(val)
        config["autorepondeur_webhook_url"] = val

    if "webhook_ssl_verify" in payload:
        config["webhook_ssl_verify"] = bool(payload["webhook_ssl_verify"])

    if not _save_webhook_config(config):
        return (
            jsonify({"success": False, "message": "Erreur lors de la sauvegarde de la configuration."}),
            500,
        )

    return jsonify({"success": True, "message": "Configuration mise à jour avec succès."}), 200
