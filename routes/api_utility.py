from __future__ import annotations

from datetime import datetime, timezone
import json

from flask import Blueprint, jsonify, request
from flask_login import login_required

from config.settings import TRIGGER_SIGNAL_FILE

bp = Blueprint("api_utility", __name__, url_prefix="/api")


@bp.route("/ping", methods=["GET", "HEAD"])  # GET /api/ping
def ping():
    return (
        jsonify({"status": "pong", "timestamp_utc": datetime.now(timezone.utc).isoformat()}),
        200,
    )


@bp.route("/check_trigger", methods=["GET"])  # GET /api/check_trigger
def check_local_workflow_trigger():
    if TRIGGER_SIGNAL_FILE.exists():
        try:
            with open(TRIGGER_SIGNAL_FILE, "r", encoding="utf-8") as f:
                payload = json.load(f)
        except Exception:
            payload = None
        try:
            TRIGGER_SIGNAL_FILE.unlink()
        except Exception:
            pass
        return jsonify({"command_pending": True, "payload": payload})
    return jsonify({"command_pending": False, "payload": None})


@bp.route("/get_local_status", methods=["GET"])  # GET /api/get_local_status
@login_required
def api_get_local_status():
    """Retourne un snapshot minimal de statut pour l'UI distante."""
    payload = {
        "overall_status_text": "En attente...",
        "status_text": "Système prêt.",
        "overall_status_code_from_worker": "idle",
        "progress_current": 0,
        "progress_total": 0,
        "current_step_name": "",
        "recent_downloads": [],
    }
    return jsonify(payload), 200
