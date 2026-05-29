"""
services.ingress_service
~~~~~~~~~~~~~~~~~~~~~~~~

Service pour traiter l'ingestion d'emails via push (Gmail Push).

Features:
- Pattern Singleton
- Validation des payloads
- Utilisation de DeduplicationService
- Routage vers email_orchestrator
"""
from __future__ import annotations

import hashlib
import logging
import sys
import threading
from datetime import datetime, timezone
from email.utils import parseaddr
from typing import Optional, Tuple, Dict, Any, TYPE_CHECKING
from pathlib import Path

if TYPE_CHECKING:
    from services.config_service import ConfigService
    from config.app_config_store import AppConfigStore

from email_processing import link_extraction
from email_processing import orchestrator as email_orchestrator
from email_processing import pattern_matching
from utils.text_helpers import mask_sensitive_data
from utils.time_helpers import is_within_time_window_local, parse_time_hhmm, get_polling_timezone
from config import settings
from config.app_config_store import get_config_json as _config_get
from routes.api_processing import DEFAULT_PROCESSING_PREFS
from services.deduplication_service import DeduplicationService
from services.runtime_flags_service import RuntimeFlagsService

try:
    from services import R2TransferService
except Exception:
    R2TransferService = None



class IngressService:
    """Service d'ingestion des webhooks Gmail Push."""

    _instance: Optional[IngressService] = None
    _lock = threading.RLock()

    def __init__(
        self,
        config_service: Optional[ConfigService] = None,
        app_config_store: Optional[AppConfigStore] = None,
        logger: Optional[logging.Logger] = None,
    ):
        self._config = config_service
        self._store = app_config_store
        self._logger = logger or logging.getLogger(__name__)

    @classmethod
    def get_instance(
        cls,
        config_service: Optional[ConfigService] = None,
        app_config_store: Optional[AppConfigStore] = None,
    ) -> IngressService:
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls(config_service, app_config_store)
            return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        with cls._lock:
            cls._instance = None

    def _compute_email_id(self, subject: str, sender: str, date: str) -> str:
        unique_str = f"{subject}|{sender}|{date}"
        return hashlib.md5(unique_str.encode("utf-8")).hexdigest()

    def _extract_sender_email(self, sender_raw: str) -> str:
        try:
            _, addr = parseaddr(sender_raw or "")
            if isinstance(addr, str) and addr.strip():
                return addr.strip()
        except Exception:
            pass
        return (sender_raw or "").strip()

    def _maybe_enrich_delivery_links_with_r2(
            self, delivery_links: list, email_id: str
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
                self._logger.info(
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
                    self._logger.debug("R2_TRANSFER: persist_link_pair failed for email %s: %s", email_id, ex)
                except Exception:
                    pass

    def process_gmail_push(self, payload: Dict[str, Any]) -> Tuple[Dict[str, Any], int]:
        subject = payload.get("subject", "")
        sender_raw = payload.get("sender", "")
        body = payload.get("body", "")
        email_date = payload.get("date", "")

        if not isinstance(subject, str):
            subject = ""
        if not isinstance(sender_raw, str):
            sender_raw = ""
        if not isinstance(body, str):
            body = ""
        if not isinstance(email_date, str):
            email_date = ""

        if not sender_raw:
            return {"success": False, "message": "Missing field: sender"}, 400
        if not body:
            return {"success": False, "message": "Missing field: body"}, 400

        try:
            rfs = RuntimeFlagsService.get_instance()
            if rfs is not None:
                gmail_ingress_enabled = bool(rfs.get_flag("gmail_ingress_enabled", True))
                if not gmail_ingress_enabled:
                    self._logger.warning("INGRESS: Gmail ingress disabled - gmail_ingress_enabled=False")
                    return {"success": False, "message": "Gmail ingress disabled"}, 409
        except Exception:
            pass

        try:
            sender_email = self._extract_sender_email(sender_raw)
        except Exception:
            sender_email = sender_raw

        sender_email = (sender_email or sender_raw).strip().lower()
        email_id = self._compute_email_id(subject=subject, sender=sender_email, date=email_date)

        try:
            self._logger.info(
                "INGRESS: gmail payload received (email_id=%s sender=%s subject=%s)",
                email_id,
                mask_sensitive_data(sender_email, "email"),
                mask_sensitive_data(subject, "subject"),
            )
        except Exception:
            pass

        dedup_service = DeduplicationService.get_instance()

        if dedup_service.is_email_processed(email_id):
            return {"success": True, "status": "already_processed", "email_id": email_id}, 200

        inflight_acquired = False
        try:
            lock_ttl = getattr(settings, "EMAIL_ID_INFLIGHT_LOCK_TTL_SECONDS", 10)
            inflight_acquired = bool(dedup_service.acquire_email_inflight_lock(email_id, lock_ttl))
            if not inflight_acquired:
                return {"success": True, "status": "already_processing", "email_id": email_id}, 200
        except Exception:
            inflight_acquired = False

        try:
            try:
                gmail_sender_list = getattr(settings, "GMAIL_SENDER_ALLOWLIST", [])
                allowed = [
                    str(s).strip().lower()
                    for s in (gmail_sender_list if isinstance(gmail_sender_list, list) else [])
                    if isinstance(s, str) and s.strip()
                ]
                if allowed and sender_email not in allowed:
                    dedup_service.mark_email_processed(email_id)
                    return {"success": True, "status": "skipped_sender_not_allowed", "email_id": email_id}, 200
            except Exception:
                pass

            try:
                if not email_orchestrator._is_webhook_sending_enabled():
                    return {"success": False, "message": "Webhook sending disabled"}, 409
            except Exception:
                pass

            tz_for_polling = get_polling_timezone()
            try:
                now_local = datetime.now(tz_for_polling) if tz_for_polling else datetime.now()
            except Exception:
                now_local = datetime.now()

            detector_val, delivery_time_val, desabo_is_urgent = None, None, False
            try:
                ms_res = pattern_matching.check_media_solution_pattern(
                    subject or "", body, tz_for_polling, self._logger
                )
                if isinstance(ms_res, dict) and bool(ms_res.get("matches")):
                    detector_val = "recadrage"
                    delivery_time_val = ms_res.get("delivery_time")
                else:
                    des_res = pattern_matching.check_desabo_conditions(
                        subject or "", body, self._logger
                    )
                    if isinstance(des_res, dict) and bool(des_res.get("matches")):
                        detector_val = "desabonnement_journee_tarifs"
                        desabo_is_urgent = bool(des_res.get("is_urgent"))
            except Exception:
                pass

            s_str, e_str = "", ""
            try:
                s_str, e_str = email_orchestrator._load_webhook_global_time_window()
            except Exception:
                pass

            start_t = parse_time_hhmm(s_str) if s_str else None
            end_t = parse_time_hhmm(e_str) if e_str else None
            within = True
            if start_t and end_t:
                within = is_within_time_window_local(now_local, start_t, end_t)

            if not within:
                if detector_val == "desabonnement_journee_tarifs":
                    if desabo_is_urgent:
                        return {"success": False, "message": "Outside time window (DESABO urgent)"}, 409
                    # Non-urgent DESABO: bypass time window, continue to send webhook
                elif detector_val == "recadrage":
                    dedup_service.mark_email_processed(email_id)
                    return {"success": True, "status": "skipped_outside_time_window", "email_id": email_id}, 200
                else:
                    return {"success": False, "message": "Outside time window"}, 409

            start_payload_val = None
            if start_t and end_t:
                if within:
                    start_payload_val = "maintenant"
                elif detector_val == "desabonnement_journee_tarifs" and not desabo_is_urgent and now_local.time() < start_t:
                    start_payload_val = s_str

            delivery_links = link_extraction.extract_provider_links_from_text(body)
            self._maybe_enrich_delivery_links_with_r2(delivery_links or [], email_id)

            payload_for_webhook = {
                "microsoft_graph_email_id": email_id,
                "subject": subject or "",
                "receivedDateTime": email_date or "",
                "sender_address": sender_raw,
                "bodyPreview": (body or "")[:200],
                "email_content": body or "",
                "source": "gmail_push",
            }
            if detector_val:
                payload_for_webhook["detector"] = detector_val
            if detector_val == "recadrage" and delivery_time_val:
                payload_for_webhook["delivery_time"] = delivery_time_val
            payload_for_webhook["sender_email"] = sender_email

            if start_payload_val is not None:
                payload_for_webhook["webhooks_time_start"] = start_payload_val
            if e_str:
                payload_for_webhook["webhooks_time_end"] = e_str

            webhook_cfg = email_orchestrator._get_webhook_config_dict() or {}
            webhook_url = str(webhook_cfg.get("webhook_url") or "").strip()
            if not webhook_url:
                webhook_url = str(getattr(settings, "WEBHOOK_URL", "")).strip()
            if not webhook_url:
                return {"success": False, "message": "WEBHOOK_URL not configured"}, 500

            webhook_ssl_verify = bool(webhook_cfg.get("webhook_ssl_verify", True))
            webhook_delivery_mode = str(webhook_cfg.get("webhook_delivery_mode") or "json").strip().lower() or "json"
            webhook_fallback_on_415 = bool(webhook_cfg.get("webhook_fallback_on_415", True))

            allow_without_links = bool(getattr(settings, "ALLOW_CUSTOM_WEBHOOK_WITHOUT_LINKS", False))
            try:
                rfs = RuntimeFlagsService.get_instance()
                if rfs is not None:
                    allow_without_links = bool(rfs.get_flag("allow_custom_webhook_without_links", allow_without_links))
            except Exception:
                pass

            processing_prefs = {}
            try:
                from routes.api_processing import DEFAULT_PROCESSING_PREFS
                from config.app_config_store import get_config_json as _config_get
                from pathlib import Path
                processing_prefs_file = Path(__file__).resolve().parents[1] / "debug" / "processing_prefs.json"
                data = _config_get("processing_prefs", file_fallback=processing_prefs_file) or {}
                if isinstance(data, dict):
                    processing_prefs = {**DEFAULT_PROCESSING_PREFS, **data}
                else:
                    processing_prefs = DEFAULT_PROCESSING_PREFS.copy()
            except Exception:
                pass

            from services.rate_limit_service import RateLimitService
            from services.webhook_logger_service import WebhookLoggerService
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
                    rate_limit_allow_send=RateLimitService.get_instance().allow_send,
                    record_send_event=RateLimitService.get_instance().record_event,
                    append_webhook_log=WebhookLoggerService.get_instance().append_log,
                    mark_email_id_as_processed_redis=dedup_service.mark_email_processed,
                    mark_email_as_read_imap=lambda *_a, **_kw: True,
                    mail=None,
                    email_num=None,
                    urlparse=None,
                    requests=requests,
                    time=time,
                    logger=self._logger,
                    webhook_delivery_mode=webhook_delivery_mode,
                    webhook_fallback_on_415=webhook_fallback_on_415,
                )

                return {
                    "success": True,
                    "status": "processed",
                    "email_id": email_id,
                    "flow_result": flow_result,
                    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                }, 200
            except Exception as e:
                self._logger.error("INGRESS: processing error for %s: %s", email_id, e)
                return {"success": False, "message": "Internal error"}, 500

        finally:
            if inflight_acquired:
                try:
                    dedup_service.release_email_inflight_lock(email_id)
                except Exception:
                    pass

