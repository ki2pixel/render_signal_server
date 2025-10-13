from __future__ import annotations

import json
import os
from pathlib import Path

from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user

bp = Blueprint("api_polling", __name__, url_prefix="/api/polling")

# Reuse legacy-compatible storage location
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


@bp.route("/toggle", methods=["POST"])  # POST /api/polling/toggle
@login_required
def toggle_polling():
    try:
        payload = request.get_json(silent=True) or {}
        enable = bool(payload.get("enable", False))

        config = _load_webhook_config()
        config["polling_enabled"] = enable

        if not _save_webhook_config(config):
            return (
                jsonify({"success": False, "message": "Erreur lors de la sauvegarde de l'état du polling."}),
                500,
            )

        # We don't log via app.logger here to avoid coupling; UI can read back state via api_webhooks/config
        return (
            jsonify(
                {
                    "success": True,
                    "message": f"Polling {'activé' if enable else 'désactivé'}. Redémarrez le serveur pour effet complet.",
                    "polling_enabled": enable,
                }
            ),
            200,
        )
    except Exception:
        return jsonify({"success": False, "message": "Erreur interne."}), 500
