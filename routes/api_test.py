from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from flask import Blueprint, jsonify, request

from auth.helpers import testapi_authorized as _testapi_authorized
from config.webhook_time_window import (
    get_time_window_info,
    update_time_window,
)
from config.webhook_config import load_webhook_config, save_webhook_config
from config.settings import (
    WEBHOOK_CONFIG_FILE,
    WEBHOOK_LOGS_FILE,
    WEBHOOK_URL,
    WEBHOOK_SSL_VERIFY,
    POLLING_TIMEZONE_STR,
    POLLING_ACTIVE_DAYS,
    POLLING_ACTIVE_START_HOUR,
    POLLING_ACTIVE_END_HOUR,
    EMAIL_POLLING_INTERVAL_SECONDS,
    POLLING_INACTIVE_CHECK_INTERVAL_SECONDS,
    ENABLE_SUBJECT_GROUP_DEDUP,
)
from utils.validators import normalize_make_webhook_url as _normalize_make_webhook_url

bp = Blueprint("api_test", __name__, url_prefix="/api/test")


"""Webhook config I/O helpers are centralized in config/webhook_config."""


def _mask_url(url: str | None) -> str | None:
    if not url:
        return None
    if url.startswith("http"):
        parts = url.split("/")
        if len(parts) > 3:
            return f"{parts[0]}//{parts[2]}/***"
        return url[:30] + "***"
    return None


# --- Endpoints ---

@bp.route("/get_webhook_time_window", methods=["GET"])
def get_webhook_time_window():
    if not _testapi_authorized(request):
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    try:
        info = get_time_window_info()
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
        return (
            jsonify({"success": False, "message": "Erreur lors de la récupération de la fenêtre horaire."}),
            500,
        )


@bp.route("/set_webhook_time_window", methods=["POST"])
def set_webhook_time_window():
    if not _testapi_authorized(request):
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    try:
        payload = request.get_json(silent=True) or {}
        start = payload.get("start", "")
        end = payload.get("end", "")
        ok, msg = update_time_window(start, end)
        status = 200 if ok else 400
        info = get_time_window_info()
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
        return (
            jsonify({"success": False, "message": "Erreur interne lors de la mise à jour."}),
            500,
        )


@bp.route("/get_webhook_config", methods=["GET"])
def get_webhook_config():
    if not _testapi_authorized(request):
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    try:
        persisted = load_webhook_config(WEBHOOK_CONFIG_FILE)
        cfg = {
            "webhook_url": persisted.get("webhook_url") or _mask_url(WEBHOOK_URL),
            "webhook_ssl_verify": persisted.get("webhook_ssl_verify", WEBHOOK_SSL_VERIFY),
            "polling_enabled": persisted.get("polling_enabled", False),
        }
        return jsonify({"success": True, "config": cfg}), 200
    except Exception:
        return (
            jsonify({"success": False, "message": "Erreur lors de la récupération de la configuration."}),
            500,
        )


@bp.route("/update_webhook_config", methods=["POST"])
def update_webhook_config():
    if not _testapi_authorized(request):
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    try:
        payload = request.get_json(silent=True) or {}
        config = load_webhook_config(WEBHOOK_CONFIG_FILE)

        if "webhook_url" in payload:
            val = payload["webhook_url"].strip() if payload["webhook_url"] else None
            if val and not val.startswith("http"):
                return (
                    jsonify({"success": False, "message": "webhook_url doit être une URL HTTPS valide."}),
                    400,
                )
            config["webhook_url"] = val

        if "recadrage_webhook_url" in payload:
            val = payload["recadrage_webhook_url"].strip() if payload["recadrage_webhook_url"] else None
            if val and not val.startswith("http"):
                return (
                    jsonify({"success": False, "message": "recadrage_webhook_url doit être une URL HTTPS valide."}),
                    400,
                )
            config["recadrage_webhook_url"] = val

        # presence fields removed

        if "autorepondeur_webhook_url" in payload:
            val = payload["autorepondeur_webhook_url"].strip() if payload["autorepondeur_webhook_url"] else None
            if val:
                val = _normalize_make_webhook_url(val)
            config["autorepondeur_webhook_url"] = val

        if "webhook_ssl_verify" in payload:
            config["webhook_ssl_verify"] = bool(payload["webhook_ssl_verify"])

        if not save_webhook_config(WEBHOOK_CONFIG_FILE, config):
            return (
                jsonify({"success": False, "message": "Erreur lors de la sauvegarde de la configuration."}),
                500,
            )
        return jsonify({"success": True, "message": "Configuration mise à jour avec succès."}), 200
    except Exception:
        return (
            jsonify({"success": False, "message": "Erreur interne lors de la mise à jour."}),
            500,
        )


@bp.route("/get_polling_config", methods=["GET"])
def get_polling_config():
    if not _testapi_authorized(request):
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    try:
        return (
            jsonify(
                {
                    "success": True,
                    "timezone": POLLING_TIMEZONE_STR,
                    "active_days": POLLING_ACTIVE_DAYS,
                    "active_start_hour": POLLING_ACTIVE_START_HOUR,
                    "active_end_hour": POLLING_ACTIVE_END_HOUR,
                    "interval_seconds": EMAIL_POLLING_INTERVAL_SECONDS,
                    "inactive_check_interval_seconds": POLLING_INACTIVE_CHECK_INTERVAL_SECONDS,
                    "enable_subject_group_dedup": ENABLE_SUBJECT_GROUP_DEDUP,
                }
            ),
            200,
        )
    except Exception:
        return (
            jsonify({"success": False, "message": "Erreur lors de la récupération de la configuration de polling."}),
            500,
        )


@bp.route("/webhook_logs", methods=["GET"])
def webhook_logs():
    if not _testapi_authorized(request):
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    try:
        days = int(request.args.get("days", 7))
        if days < 1:
            days = 7
        if days > 30:
            days = 30

        if not WEBHOOK_LOGS_FILE.exists():
            return jsonify({"success": True, "logs": [], "count": 0, "days_filter": days}), 200
        with open(WEBHOOK_LOGS_FILE, "r", encoding="utf-8") as f:
            all_logs = json.load(f) or []

        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        filtered = []
        for log in all_logs:
            try:
                log_time = datetime.fromisoformat(log.get("timestamp", ""))
                if log_time >= cutoff:
                    filtered.append(log)
            except Exception:
                filtered.append(log)

        filtered = filtered[-50:]
        filtered.reverse()
        return (
            jsonify({"success": True, "logs": filtered, "count": len(filtered), "days_filter": days}),
            200,
        )
    except Exception:
        return (
            jsonify({"success": False, "message": "Erreur lors de la récupération des logs."}),
            500,
        )


@bp.route("/clear_email_dedup", methods=["POST"])
def clear_email_dedup():
    if not _testapi_authorized(request):
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    try:
        payload = request.get_json(silent=True) or {}
        email_id = str(payload.get("email_id") or "").strip()
        if not email_id:
            return jsonify({"success": False, "message": "email_id manquant"}), 400
        # Legacy endpoint: no in-memory store to clear. Redis not used here; report not removed.
        return jsonify({"success": True, "removed": False, "email_id": email_id}), 200
    except Exception:
        return jsonify({"success": False, "message": "Erreur interne"}), 500
