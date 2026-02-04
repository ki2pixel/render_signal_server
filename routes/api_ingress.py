from __future__ import annotations

import hashlib
import sys
from datetime import datetime, timezone
from email.utils import parseaddr

from flask import Blueprint, current_app, jsonify, request

from email_processing import link_extraction
from email_processing import orchestrator as email_orchestrator
from email_processing import pattern_matching
from services import AuthService, ConfigService
from utils.text_helpers import mask_sensitive_data
from utils.time_helpers import is_within_time_window_local, parse_time_hhmm

try:
    from services import R2TransferService
except Exception:
    R2TransferService = None

bp = Blueprint("api_ingress", __name__, url_prefix="/api/ingress")

_config_service = ConfigService()
_auth_service = AuthService(_config_service)


def _maybe_enrich_delivery_links_with_r2(
    *, delivery_links: list, email_id: str, logger
) -> None:
    if not delivery_links:
        return

    try:
        if R2TransferService is None:
            return

        r2_service = R2TransferService.get_instance()
        if not r2_service.is_enabled():
            return
    except Exception:
        return

    for item in delivery_links:
        if not isinstance(item, dict):
            continue

        raw_url = item.get("raw_url")
        provider = item.get("provider")
        if not isinstance(raw_url, str) or not raw_url.strip():
            continue
        if not isinstance(provider, str) or not provider.strip():
            continue

        if not isinstance(item.get("direct_url"), str) or not item.get("direct_url"):
            item["direct_url"] = raw_url

        try:
            normalized_source_url = r2_service.normalize_source_url(raw_url, provider)
        except Exception:
            normalized_source_url = raw_url

        remote_fetch_timeout = 15
        try:
            if provider == "dropbox" and "/scl/fo/" in normalized_source_url.lower():
                remote_fetch_timeout = 120
        except Exception:
            remote_fetch_timeout = 15

        try:
            r2_url, original_filename = r2_service.request_remote_fetch(
                source_url=normalized_source_url,
                provider=provider,
                email_id=email_id,
                timeout=remote_fetch_timeout,
            )
        except Exception:
            continue

        if not isinstance(r2_url, str) or not r2_url.strip():
            continue

        item["r2_url"] = r2_url
        if isinstance(original_filename, str) and original_filename.strip():
            item["original_filename"] = original_filename.strip()

        try:
            logger.info(
                "R2_TRANSFER: Successfully transferred %s link to R2 for email %s",
                provider,
                email_id,
            )
        except Exception:
            pass

        try:
            r2_service.persist_link_pair(
                source_url=normalized_source_url,
                r2_url=r2_url,
                provider=provider,
                original_filename=(original_filename if isinstance(original_filename, str) else None),
            )
        except Exception as ex:
            try:
                logger.debug("R2_TRANSFER: persist_link_pair failed for email %s: %s", email_id, ex)
            except Exception:
                pass


def _compute_email_id(*, subject: str, sender: str, date: str) -> str:
    unique_str = f"{subject}|{sender}|{date}"
    return hashlib.md5(unique_str.encode("utf-8")).hexdigest()


def _extract_sender_email(sender_raw: str) -> str:
    try:
        _, addr = parseaddr(sender_raw or "")
        if isinstance(addr, str) and addr.strip():
            return addr.strip()
    except Exception:
        pass
    return (sender_raw or "").strip()


@bp.route("/gmail", methods=["POST"])
def ingest_gmail():
    if not _auth_service.verify_api_key_from_request(request):
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"success": False, "message": "Invalid JSON payload"}), 400

    subject = payload.get("subject")
    sender_raw = payload.get("sender")
    body = payload.get("body")
    email_date = payload.get("date")

    if not isinstance(subject, str):
        subject = ""
    if not isinstance(sender_raw, str):
        sender_raw = ""
    if not isinstance(body, str):
        body = ""
    if not isinstance(email_date, str):
        email_date = ""

    if not sender_raw:
        return jsonify({"success": False, "message": "Missing field: sender"}), 400
    if not body:
        return jsonify({"success": False, "message": "Missing field: body"}), 400

    ar = sys.modules.get("app_render")
    if ar is None:
        return jsonify({"success": False, "message": "Server not ready"}), 503

    try:
        rfs = getattr(ar, "_runtime_flags_service", None)
        if rfs is not None and hasattr(rfs, "get_flag"):
            if not bool(rfs.get_flag("gmail_ingress_enabled", True)):
                return (
                    jsonify({"success": False, "message": "Gmail ingress disabled"}),
                    409,
                )
    except Exception:
        pass

    try:
        sender_email = _extract_sender_email(sender_raw)
    except Exception:
        sender_email = sender_raw

    sender_email = (sender_email or sender_raw).strip().lower()

    email_id = _compute_email_id(subject=subject, sender=sender_email, date=email_date)

    try:
        current_app.logger.info(
            "INGRESS: gmail payload received (email_id=%s sender=%s subject=%s)",
            email_id,
            mask_sensitive_data(sender_email, "email"),
            mask_sensitive_data(subject, "subject"),
        )
    except Exception:
        pass

    try:
        is_processed_fn = getattr(ar, "is_email_id_processed_redis", None)
        if callable(is_processed_fn) and is_processed_fn(email_id):
            return (
                jsonify({"success": True, "status": "already_processed", "email_id": email_id}),
                200,
            )
    except Exception:
        pass

    try:
        gmail_sender_list = getattr(ar, "GMAIL_SENDER_ALLOWLIST", [])
        allowed = [
            str(s).strip().lower()
            for s in (gmail_sender_list if isinstance(gmail_sender_list, list) else [])
            if isinstance(s, str) and s.strip()
        ]
        if allowed and sender_email not in allowed:
            try:
                mark_processed_fn = getattr(ar, "mark_email_id_as_processed_redis", None)
                if callable(mark_processed_fn):
                    mark_processed_fn(email_id)
            except Exception:
                pass
            return (
                jsonify({"success": True, "status": "skipped_sender_not_allowed", "email_id": email_id}),
                200,
            )
    except Exception:
        pass

    try:
        if not email_orchestrator._is_webhook_sending_enabled():
            return (
                jsonify({"success": False, "message": "Webhook sending disabled"}),
                409,
            )
    except Exception:
        pass

    tz_for_polling = getattr(ar, "TZ_FOR_POLLING", None)
    try:
        now_local = datetime.now(tz_for_polling) if tz_for_polling else datetime.now()
    except Exception:
        now_local = datetime.now()

    detector_val = None
    delivery_time_val = None
    desabo_is_urgent = False
    try:
        ms_res = pattern_matching.check_media_solution_pattern(
            subject or "", body, tz_for_polling, current_app.logger
        )
        if isinstance(ms_res, dict) and bool(ms_res.get("matches")):
            detector_val = "recadrage"
            delivery_time_val = ms_res.get("delivery_time")
        else:
            des_res = pattern_matching.check_desabo_conditions(
                subject or "", body, current_app.logger
            )
            if isinstance(des_res, dict) and bool(des_res.get("matches")):
                detector_val = "desabonnement_journee_tarifs"
                desabo_is_urgent = bool(des_res.get("is_urgent"))
    except Exception:
        detector_val = None

    s_str, e_str = "", ""
    try:
        s_str, e_str = email_orchestrator._load_webhook_global_time_window()
    except Exception:
        s_str, e_str = "", ""

    start_t = parse_time_hhmm(s_str) if s_str else None
    end_t = parse_time_hhmm(e_str) if e_str else None
    within = True
    if start_t and end_t:
        within = is_within_time_window_local(now_local, start_t, end_t)

    if not within:
        if detector_val == "desabonnement_journee_tarifs":
            if desabo_is_urgent:
                return (
                    jsonify({"success": False, "message": "Outside time window (DESABO urgent)"}),
                    409,
                )
        elif detector_val == "recadrage":
            try:
                mark_processed_fn = getattr(ar, "mark_email_id_as_processed_redis", None)
                if callable(mark_processed_fn):
                    mark_processed_fn(email_id)
            except Exception:
                pass
            return (
                jsonify({"success": True, "status": "skipped_outside_time_window", "email_id": email_id}),
                200,
            )
        else:
            return (
                jsonify({"success": False, "message": "Outside time window"}),
                409,
            )

    start_payload_val = None
    try:
        if start_t and end_t:
            if within:
                start_payload_val = "maintenant"
            else:
                if (
                    detector_val == "desabonnement_journee_tarifs"
                    and not desabo_is_urgent
                    and now_local.time() < start_t
                ):
                    start_payload_val = s_str
    except Exception:
        start_payload_val = None

    delivery_links = link_extraction.extract_provider_links_from_text(body)

    try:
        _maybe_enrich_delivery_links_with_r2(
            delivery_links=delivery_links or [],
            email_id=email_id,
            logger=current_app.logger,
        )
    except Exception:
        pass

    payload_for_webhook = {
        "microsoft_graph_email_id": email_id,
        "subject": subject or "",
        "receivedDateTime": email_date or "",
        "sender_address": sender_raw,
        "bodyPreview": (body or "")[:200],
        "email_content": body or "",
        "source": "gmail_push",
    }

    try:
        if detector_val:
            payload_for_webhook["detector"] = detector_val
        if detector_val == "recadrage" and delivery_time_val:
            payload_for_webhook["delivery_time"] = delivery_time_val
        payload_for_webhook["sender_email"] = sender_email
    except Exception:
        pass

    try:
        if start_payload_val is not None:
            payload_for_webhook["webhooks_time_start"] = start_payload_val
        if e_str:
            payload_for_webhook["webhooks_time_end"] = e_str
    except Exception:
        pass

    webhook_cfg = {}
    try:
        webhook_cfg = email_orchestrator._get_webhook_config_dict() or {}
    except Exception:
        webhook_cfg = {}

    webhook_url = ""
    try:
        webhook_url = str(webhook_cfg.get("webhook_url") or "").strip()
    except Exception:
        webhook_url = ""
    if not webhook_url:
        webhook_url = str(getattr(ar, "WEBHOOK_URL", "") or "").strip()
    if not webhook_url:
        return jsonify({"success": False, "message": "WEBHOOK_URL not configured"}), 500

    webhook_ssl_verify = True
    try:
        webhook_ssl_verify = bool(webhook_cfg.get("webhook_ssl_verify", True))
    except Exception:
        webhook_ssl_verify = True

    allow_without_links = bool(getattr(ar, "ALLOW_CUSTOM_WEBHOOK_WITHOUT_LINKS", False))
    try:
        rfs = getattr(ar, "_runtime_flags_service", None)
        if rfs is not None and hasattr(rfs, "get_flag"):
            allow_without_links = bool(
                rfs.get_flag("allow_custom_webhook_without_links", allow_without_links)
            )
    except Exception:
        pass

    processing_prefs = getattr(ar, "PROCESSING_PREFS", {})

    rate_limit_allow_send = getattr(ar, "_rate_limit_allow_send", None)
    record_send_event = getattr(ar, "_record_send_event", None)
    append_webhook_log = getattr(ar, "_append_webhook_log", None)
    mark_processed_fn = getattr(ar, "mark_email_id_as_processed_redis", None)

    if not callable(rate_limit_allow_send) or not callable(record_send_event):
        return jsonify({"success": False, "message": "Server misconfigured"}), 500
    if not callable(append_webhook_log) or not callable(mark_processed_fn):
        return jsonify({"success": False, "message": "Server misconfigured"}), 500

    import requests
    import time

    try:
        flow_result = email_orchestrator.send_custom_webhook_flow(
            email_id=email_id,
            subject=subject,
            payload_for_webhook=payload_for_webhook,
            delivery_links=delivery_links or [],
            webhook_url=webhook_url,
            webhook_ssl_verify=webhook_ssl_verify,
            allow_without_links=allow_without_links,
            processing_prefs=processing_prefs,
            rate_limit_allow_send=rate_limit_allow_send,
            record_send_event=record_send_event,
            append_webhook_log=append_webhook_log,
            mark_email_id_as_processed_redis=mark_processed_fn,
            mark_email_as_read_imap=lambda *_a, **_kw: True,
            mail=None,
            email_num=None,
            urlparse=None,
            requests=requests,
            time=time,
            logger=current_app.logger,
        )

        return (
            jsonify(
                {
                    "success": True,
                    "status": "processed",
                    "email_id": email_id,
                    "flow_result": flow_result,
                    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                }
            ),
            200,
        )
    except Exception as e:
        try:
            current_app.logger.error("INGRESS: processing error for %s: %s", email_id, e)
        except Exception:
            pass
        return jsonify({"success": False, "message": "Internal error"}), 500
