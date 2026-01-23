from __future__ import annotations

from datetime import datetime, timezone
import json
import sys

from flask import Blueprint, jsonify, request
from flask_login import login_required

from config.settings import TRIGGER_SIGNAL_FILE

bp = Blueprint("api_utility", __name__, url_prefix="/api")


@bp.route("/ping", methods=["GET", "HEAD"])
def ping():
    return (
        jsonify({"status": "pong", "timestamp_utc": datetime.now(timezone.utc).isoformat()}),
        200,
    )


@bp.route("/diag/runtime", methods=["GET"])
def diag_runtime():
    """Expose basic runtime state without requiring auth.

    Reads values from the main module (app_render) if available. All fields are best-effort.
    """
    now = datetime.now(timezone.utc)
    process_start_iso = None
    uptime_sec = None
    last_poll_cycle_ts = None
    last_webhook_sent_ts = None
    bg_poller_alive = None
    make_watcher_alive = None
    enable_bg = None

    mod = sys.modules.get("app_render")
    if mod is not None:
        try:
            ps = getattr(mod, "PROCESS_START_TIME", None)
            if ps:
                process_start_iso = getattr(ps, "isoformat", lambda: str(ps))()
                try:
                    uptime_sec = int((now - ps).total_seconds())
                except Exception:
                    uptime_sec = None
        except Exception:
            pass
        try:
            last_poll_cycle_ts = getattr(mod, "LAST_POLL_CYCLE_TS", None)
        except Exception:
            pass
        try:
            last_webhook_sent_ts = getattr(mod, "LAST_WEBHOOK_SENT_TS", None)
        except Exception:
            pass
        try:
            t = getattr(mod, "_bg_email_poller_thread", None)
            bg_poller_alive = bool(t and t.is_alive())
        except Exception:
            bg_poller_alive = None
        try:
            t2 = getattr(mod, "_make_watcher_thread", None)
            make_watcher_alive = bool(t2 and t2.is_alive())
        except Exception:
            make_watcher_alive = None
        try:
            enable_bg = bool(getattr(getattr(mod, "settings", object()), "ENABLE_BACKGROUND_TASKS", False))
        except Exception:
            enable_bg = None

    payload = {
        "process_start_time": process_start_iso,
        "uptime_sec": uptime_sec,
        "last_poll_cycle_ts": last_poll_cycle_ts,
        "last_webhook_sent_ts": last_webhook_sent_ts,
        "bg_poller_thread_alive": bg_poller_alive,
        "make_watcher_thread_alive": make_watcher_alive,
        "enable_background_tasks": enable_bg,
        "server_time_utc": now.isoformat(),
    }
    return jsonify(payload), 200


@bp.route("/check_trigger", methods=["GET"])
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


@bp.route("/get_local_status", methods=["GET"])
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
