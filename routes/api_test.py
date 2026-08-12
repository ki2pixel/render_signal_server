from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from flask import Blueprint, jsonify, request, Response

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
)
from utils.validators import normalize_make_webhook_url as _normalize_make_webhook_url
from utils.validators import is_placeholder_webhook_url as _is_placeholder_webhook_url
from config import settings as _settings

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
def get_webhook_time_window() -> Response | tuple[Response, int]:
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
def set_webhook_time_window() -> Response | tuple[Response, int]:
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
def get_webhook_config() -> Response | tuple[Response, int]:
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
def update_webhook_config() -> Response | tuple[Response, int]:
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
            if val and _is_placeholder_webhook_url(val):
                return (
                    jsonify({"success": False, "message": "webhook_url ne peut pas être une URL placeholder (ex: example.com)."}),
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


@bp.route("/webhook_logs", methods=["GET"])
def webhook_logs() -> Response | tuple[Response, int]:
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
def clear_email_dedup() -> Response | tuple[Response, int]:
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


def _resolve_webhook_target(webhook_url: str | None) -> tuple[str, str | None]:
    """Resolve the effective webhook target URL (override -> config -> env -> default).

    Mirrors the real ingress flow (ingress_service._send_ingress_webhook):
    persisted config first, then WEBHOOK_URL env var, then the documented
    default endpoint. An explicit webhook_url in the request body wins.
    """
    url = (webhook_url or "").strip()
    if not url:
        # Imported locally to avoid a circular import at module load time.
        from email_processing.orchestrator import _get_webhook_config_dict as _orch_get_webhook_config_dict

        try:
            webhook_cfg = _orch_get_webhook_config_dict() or {}
            url = str(webhook_cfg.get("webhook_url") or "").strip()
        except Exception:
            url = ""
    if not url or _is_placeholder_webhook_url(url):
        url = str(getattr(_settings, "WEBHOOK_URL", "") or "").strip()
    if not url or _is_placeholder_webhook_url(url):
        return "https://webhook.kidpixel.fr/index.php", "no URL configured, using default fallback"
    return url, None


def _load_processing_prefs() -> dict:
    """Load processing prefs from config store with file fallback (same as ingress)."""
    from routes.api_processing import DEFAULT_PROCESSING_PREFS
    from config.app_config_store import get_config_json as _config_get
    from pathlib import Path

    prefs_file = Path(__file__).resolve().parents[1] / "debug" / "processing_prefs.json"
    data = _config_get("processing_prefs", file_fallback=prefs_file) or {}
    if isinstance(data, dict):
        return {**DEFAULT_PROCESSING_PREFS, **data}
    return DEFAULT_PROCESSING_PREFS.copy()


@bp.route("/send_test_webhook", methods=["POST"])
def send_test_webhook() -> Response | tuple[Response, int]:
    """Send a test webhook (real or dry-run).

    Body (JSON):
        - dry_run: bool, default true. When true, nothing is sent; the
          full payload preview is returned instead.
        - webhook_url: optional target override. When omitted, the
          effective config/env/default URL is used (masked in response).
        - email_id: optional id included in the payload.
        - subject: optional subject.
        - delivery_links: optional list of links to include.
        - payload: optional extra payload merged before delivery_links.
    """
    if not _testapi_authorized(request):
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    try:
        body = request.get_json(silent=True) or {}
        dry_run = bool(body.get("dry_run", True))
        webhook_url = str(body.get("webhook_url") or "").strip() or None
        target_url, fallback_note = _resolve_webhook_target(webhook_url)

        email_id = str(body.get("email_id") or "").strip() or "test-webhook"
        subject = body.get("subject")
        delivery_links = body.get("delivery_links") or []
        if not isinstance(delivery_links, list):
            return (
                jsonify({"success": False, "message": "delivery_links doit être une liste."}),
                400,
            )
        extra_payload = body.get("payload") or {}
        if not isinstance(extra_payload, dict):
            return (
                jsonify({"success": False, "message": "payload doit être un objet JSON."}),
                400,
            )

        # Merge any provided fields into the payload (subject always overrides).
        payload_for_webhook = dict(extra_payload)
        payload_for_webhook["microsoft_graph_email_id"] = email_id
        payload_for_webhook["subject"] = subject or payload_for_webhook.get("subject") or ""

        # Imported locally to avoid a circular import (routes -> orchestrator -> services -> routes).
        from email_processing.orchestrator import (
            _get_webhook_config_dict as _orch_get_webhook_config_dict,
            build_dry_run_preview as _orch_build_dry_run_preview,
        )

        webhook_cfg = _orch_get_webhook_config_dict() or {}
        webhook_ssl_verify = bool(webhook_cfg.get("webhook_ssl_verify", True))
        webhook_delivery_mode = str(webhook_cfg.get("webhook_delivery_mode") or "json").strip().lower() or "json"
        webhook_fallback_on_415 = bool(webhook_cfg.get("webhook_fallback_on_415", True))

        preview = _orch_build_dry_run_preview(
            email_id=email_id,
            subject=subject,
            payload_for_webhook=payload_for_webhook,
            delivery_links=delivery_links,
            webhook_url=target_url,
            webhook_delivery_mode=webhook_delivery_mode,
            webhook_fallback_on_415=webhook_fallback_on_415,
        )

        if dry_run:
            return (
                jsonify(
                    {
                        "success": True,
                        "dry_run": True,
                        "message": "Dry-run: aucun envoi effectué.",
                        "target_url": target_url,
                        "target_masked": _mask_url(target_url) or target_url,
                        "fallback_note": fallback_note,
                        "webhook_ssl_verify": webhook_ssl_verify,
                        "delivery_mode_sequence": preview["delivery_mode_sequence"],
                        "resolved_delivery_mode": preview["resolved_delivery_mode"],
                        "fallback_on_415": preview["fallback_on_415"],
                        "payload_size_bytes": preview["payload_size_bytes"],
                        "payload": preview["payload"],
                        "serialized_payload": preview["serialized_payload"],
                    }
                ),
                200,
            )

        # Real send: reuse the same flow as ingress (custom webhook path).
        from services.rate_limit_service import RateLimitService
        from services.webhook_logger_service import WebhookLoggerService
        from services.deduplication_service import DeduplicationService
        import requests
        import time as _time
        from email_processing.orchestrator import send_custom_webhook_flow as _orch_send_custom_webhook_flow

        processing_prefs = _load_processing_prefs()
        flow_result = _orch_send_custom_webhook_flow(
            email_id=email_id,
            subject=subject,
            payload_for_webhook=payload_for_webhook,
            delivery_links=delivery_links,
            webhook_url=target_url,
            webhook_ssl_verify=webhook_ssl_verify,
            allow_without_links=bool(getattr(_settings, "ALLOW_CUSTOM_WEBHOOK_WITHOUT_LINKS", False)),
            processing_prefs=processing_prefs,
            rate_limit_allow_send=RateLimitService.get_instance().allow_send,
            record_send_event=RateLimitService.get_instance().record_event,
            append_webhook_log=WebhookLoggerService.get_instance().append_log,
            mark_email_id_as_processed_redis=DeduplicationService.get_instance().mark_email_processed,
            mark_email_as_read_imap=lambda *_a, **_kw: True,
            mail=None,
            email_num=None,
            urlparse=None,
            requests=requests,
            time=_time,
            logger=__import__("logging").getLogger(__name__),
            webhook_delivery_mode=webhook_delivery_mode,
            webhook_fallback_on_415=webhook_fallback_on_415,
        )
        return (
            jsonify(
                {
                    "success": True,
                    "dry_run": False,
                    "message": "Webhook envoyé.",
                    "target_url": _mask_url(target_url) or target_url,
                    "flow_result": flow_result,
                    "payload_size_bytes": preview["payload_size_bytes"],
                }
            ),
            200,
        )
    except Exception as e:
        return (
            jsonify({"success": False, "message": f"Erreur interne: {str(e)}"}),
            500,
        )
