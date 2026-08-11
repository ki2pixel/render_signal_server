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
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from email.utils import parseaddr
from typing import Optional, Tuple, Dict, Any, TYPE_CHECKING
from pathlib import Path

if TYPE_CHECKING:
    from services.config_service import ConfigService

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

from typing import Any
try:
    from services import R2TransferService
except Exception:
    R2TransferService = None  # type: ignore


class IngressService:
    """Service d'ingestion des webhooks Gmail Push."""

    _instance: Optional[IngressService] = None
    _lock = threading.RLock()
    _executor: Optional[ThreadPoolExecutor] = None

    @classmethod
    def _get_executor(cls) -> ThreadPoolExecutor:
        if cls._executor is None:
            cls._executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="ingress-")
        return cls._executor

    @classmethod
    def shutdown_executor(cls) -> None:
        """Shutdown the background executor (for tests)."""
        if cls._executor is not None:
            cls._executor.shutdown(wait=True)
            cls._executor = None

    def __init__(
        self,
        config_service: Optional[ConfigService] = None,
        logger: Optional[logging.Logger] = None,
    ):
        self._config = config_service
        self._logger = logger or logging.getLogger(__name__)

    @classmethod
    def get_instance(
        cls,
        config_service: Optional[ConfigService] = None,
    ) -> IngressService:
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls(config_service)
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

    def _maybe_enrich_delivery_links_with_r2(self, delivery_links: list, email_id: str) -> None:
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
            self._process_single_delivery_link(item, r2_service, email_id)

    def _process_single_delivery_link(self, item: dict, r2_service: Any, email_id: str) -> None:
        if not isinstance(item, dict):
            return

        raw_url = item.get("raw_url")
        provider = item.get("provider")
        if not isinstance(raw_url, str) or not raw_url.strip():
            return
        if not isinstance(provider, str) or not provider.strip():
            return

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
            pass

        try:
            r2_url, original_filename = r2_service.request_remote_fetch(
                source_url=normalized_source_url,
                provider=provider,
                email_id=email_id,
                timeout=remote_fetch_timeout,
            )
        except Exception:
            return

        if not isinstance(r2_url, str) or not r2_url.strip():
            return

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

    def _validate_payload(self, payload: Dict[str, Any]) -> Tuple[bool, str, dict]:
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
            return False, "Missing field: sender", {}
        if not body:
            return False, "Missing field: body", {}
            
        return True, "", {
            "subject": subject,
            "sender_raw": sender_raw,
            "body": body,
            "email_date": email_date
        }

    def _check_ingress_enabled(self) -> Tuple[bool, str]:
        try:
            rfs = RuntimeFlagsService.get_instance()
            if rfs is not None:
                gmail_ingress_enabled = bool(rfs.get_flag("gmail_ingress_enabled", True))
                if not gmail_ingress_enabled:
                    self._logger.warning("INGRESS: Gmail ingress disabled - gmail_ingress_enabled=False")
                    return False, "Gmail ingress disabled"
        except Exception as e:
            self._logger.warning("INGRESS: Error checking ingress enabled flag, failing closed: %s", e)
            return False, "Internal error"
        return True, ""

    def _check_sender_allowlist(self, sender_email: str) -> bool:
        try:
            gmail_sender_list = getattr(settings, "GMAIL_SENDER_ALLOWLIST", [])
            allowed = [
                str(s).strip().lower()
                for s in (gmail_sender_list if isinstance(gmail_sender_list, list) else [])
                if isinstance(s, str) and s.strip()
            ]
            if allowed and sender_email not in allowed:
                return False
        except Exception as e:
            self._logger.warning("INGRESS: Error checking sender allowlist, failing closed: %s", e)
            return False
        return True

    def _get_detector_and_time(self, subject: str, body: str, tz_for_polling: Any) -> Tuple[Optional[str], Optional[str], bool]:
        detector_val, delivery_time_val, desabo_is_urgent = None, None, False
        try:
            ms_res = pattern_matching.check_media_solution_pattern(
                subject, body, tz_for_polling, self._logger
            )
            if isinstance(ms_res, dict) and bool(ms_res.get("matches")):
                detector_val = "recadrage"
                delivery_time_val = ms_res.get("delivery_time")
            else:
                des_res = pattern_matching.check_desabo_conditions(
                    subject, body, self._logger
                )
                if isinstance(des_res, dict) and bool(des_res.get("matches")):
                    detector_val = "desabonnement_journee_tarifs"
                    desabo_is_urgent = bool(des_res.get("is_urgent"))
        except Exception:
            pass
        return detector_val, delivery_time_val, desabo_is_urgent

    def _evaluate_time_window(self, now_local: datetime) -> Tuple[bool, Optional[str], str]:
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

        start_payload_val = None
        if start_t and end_t:
            if within:
                start_payload_val = "maintenant"
            # note: logic for desabo non urgent is handled outside
        return within, start_payload_val, e_str

    def _get_processing_prefs(self) -> dict:
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
        return processing_prefs

    def _extract_clean_sender(self, sender_raw: str) -> str:
        try:
            sender_email = self._extract_sender_email(sender_raw)
        except Exception:
            sender_email = sender_raw
        return (sender_email or sender_raw).strip().lower()

    def _log_ingress_receipt(self, email_id: str, sender_email: str, subject: str) -> None:
        try:
            self._logger.info(
                "INGRESS: gmail payload received (email_id=%s sender=%s subject=%s)",
                mask_sensitive_data(email_id, "id"),
                mask_sensitive_data(sender_email, "email"),
                mask_sensitive_data(subject, "subject"),
            )
        except Exception:
            pass

    def _evaluate_time_window_policy(
        self,
        within: bool,
        start_payload_val: Optional[str],
        e_str: str,
        detector_val: Optional[str],
        desabo_is_urgent: bool,
        dedup_service: Any,
        email_id: str,
        now_local: datetime,
    ) -> Tuple[Optional[Tuple[Dict[str, Any], int]], Optional[str]]:
        s_str = ""
        try:
            s_str, _ = email_orchestrator._load_webhook_global_time_window()
        except Exception:
            pass
        start_t = parse_time_hhmm(s_str) if s_str else None
        if not within:
            if detector_val == "desabonnement_journee_tarifs":
                if desabo_is_urgent:
                    return ({"success": False, "message": "Outside time window (DESABO urgent)"}, 409), start_payload_val
            elif detector_val == "recadrage":
                dedup_service.mark_email_processed(email_id)
                return ({"success": True, "status": "skipped_outside_time_window", "email_id": email_id}, 200), start_payload_val
            else:
                return ({"success": False, "message": "Outside time window"}, 409), start_payload_val
        if not within and start_t and detector_val == "desabonnement_journee_tarifs" and not desabo_is_urgent and now_local.time() < start_t:
            start_payload_val = s_str
        return None, start_payload_val

    def _send_ingress_webhook(
        self,
        *,
        email_id: str,
        subject: str,
        payload_for_webhook: Dict[str, Any],
        delivery_links: list,
        dedup_service: Any,
    ) -> Tuple[Dict[str, Any], int]:
        from services.rate_limit_service import RateLimitService
        from services.webhook_logger_service import WebhookLoggerService
        import requests
        import time as _time

        webhook_cfg = email_orchestrator._get_webhook_config_dict() or {}
        webhook_url = str(webhook_cfg.get("webhook_url") or "").strip()
        # Refuse les URLs placeholder (example.com, etc.) : elles ne doivent
        # jamais servir de cible réelle. On retombe alors sur l'env var,
        # puis sur le défaut documenté.
        from utils.validators import is_placeholder_webhook_url as _is_placeholder_webhook_url

        if not webhook_url or _is_placeholder_webhook_url(webhook_url):
            webhook_url = str(getattr(settings, "WEBHOOK_URL", "")).strip()
        if not webhook_url or _is_placeholder_webhook_url(webhook_url):
            webhook_url = "https://webhook.kidpixel.fr/index.php"
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
        processing_prefs = self._get_processing_prefs()
        try:
            flow_result = email_orchestrator.send_custom_webhook_flow(
                email_id=email_id, subject=subject, payload_for_webhook=payload_for_webhook,
                delivery_links=delivery_links, webhook_url=webhook_url, webhook_ssl_verify=webhook_ssl_verify,
                allow_without_links=allow_without_links, processing_prefs=processing_prefs,
                rate_limit_allow_send=RateLimitService.get_instance().allow_send,
                record_send_event=RateLimitService.get_instance().record_event,
                append_webhook_log=WebhookLoggerService.get_instance().append_log,
                mark_email_id_as_processed_redis=dedup_service.mark_email_processed,
                mark_email_as_read_imap=lambda *_a, **_kw: True, mail=None, email_num=None, urlparse=None,
                requests=requests, time=_time, logger=self._logger,
                webhook_delivery_mode=webhook_delivery_mode, webhook_fallback_on_415=webhook_fallback_on_415,
            )
            return {"success": True, "status": "processed", "email_id": email_id, "flow_result": flow_result, "timestamp_utc": datetime.now(timezone.utc).isoformat()}, 200
        except Exception as e:
            self._logger.error("INGRESS: processing error for %s: %s", email_id, e)
            return {"success": False, "message": "Internal error"}, 500

    def _handle_allowed_email(
        self,
        *,
        dedup_service: Any,
        email_id: str,
        sender_email: str,
        subject: str,
        body: str,
        email_date: str,
        sender_raw: str,
    ) -> Tuple[Dict[str, Any], int]:
        tz_for_polling = get_polling_timezone()
        try:
            now_local = datetime.now(tz_for_polling) if tz_for_polling else datetime.now()
        except Exception:
            now_local = datetime.now()
        detector_val, delivery_time_val, desabo_is_urgent = self._get_detector_and_time(subject, body, tz_for_polling)
        within, start_payload_val, e_str = self._evaluate_time_window(now_local)
        early_exit, start_payload_val = self._evaluate_time_window_policy(
            within, start_payload_val, e_str, detector_val, desabo_is_urgent, dedup_service, email_id, now_local,
        )
        if early_exit is not None:
            return early_exit
        delivery_links = link_extraction.extract_provider_links_from_text(body)
        self._maybe_enrich_delivery_links_with_r2(delivery_links or [], email_id)
        payload_for_webhook: Dict[str, Any] = {
            "microsoft_graph_email_id": email_id, "subject": subject, "receivedDateTime": email_date,
            "sender_address": sender_raw, "bodyPreview": body[:200], "email_content": body,
            "source": "gmail_push", "sender_email": sender_email,
        }
        if detector_val:
            payload_for_webhook["detector"] = detector_val
        if detector_val == "recadrage" and delivery_time_val:
            payload_for_webhook["delivery_time"] = delivery_time_val
        if start_payload_val is not None:
            payload_for_webhook["webhooks_time_start"] = start_payload_val
        if e_str:
            payload_for_webhook["webhooks_time_end"] = e_str
        return self._send_ingress_webhook(
            email_id=email_id, subject=subject, payload_for_webhook=payload_for_webhook,
            delivery_links=delivery_links or [], dedup_service=dedup_service,
        )

    def _process_fresh_email(
        self,
        *,
        dedup_service: Any,
        email_id: str,
        sender_email: str,
        subject: str,
        body: str,
        email_date: str,
        sender_raw: str,
    ) -> Tuple[Dict[str, Any], int]:
        if not self._check_sender_allowlist(sender_email):
            dedup_service.mark_email_processed(email_id)
            return {"success": True, "status": "skipped_sender_not_allowed", "email_id": email_id}, 200
        try:
            if not email_orchestrator._is_webhook_sending_enabled():
                return {"success": False, "message": "Webhook sending disabled"}, 409
        except Exception:
            pass
        return self._handle_allowed_email(
            dedup_service=dedup_service, email_id=email_id, sender_email=sender_email,
            subject=subject, body=body, email_date=email_date, sender_raw=sender_raw,
        )

    def _check_preconditions(
        self,
        sender_email: str,
        dedup_service: Any,
        email_id: str,
    ) -> Tuple[bool, Tuple[Dict[str, Any], int] | None]:
        """Fast synchronous checks before dispatching to background.

        Returns (can_proceed, early_response).
        early_response is set if the email should be rejected synchronously.
        """
        if not self._check_sender_allowlist(sender_email):
            dedup_service.mark_email_processed(email_id)
            return False, ({"success": True, "status": "skipped_sender_not_allowed", "email_id": email_id}, 200)
        try:
            if not email_orchestrator._is_webhook_sending_enabled():
                return False, ({"success": False, "message": "Webhook sending disabled"}, 409)
        except Exception:
            pass
        return True, None

    def _process_in_background(
        self,
        dedup_service: Any,
        email_id: str,
        lock_token: Optional[str],
        sender_email: str,
        subject: str,
        body: str,
        email_date: str,
        sender_raw: str,
    ) -> None:
        """Background processing: link extraction, R2 transfer, webhook dispatch."""
        try:
            self._handle_allowed_email(
                dedup_service=dedup_service, email_id=email_id, sender_email=sender_email,
                subject=subject, body=body, email_date=email_date, sender_raw=sender_raw,
            )
        except Exception:
            try:
                self._logger.error(
                    "INGRESS: Background processing failed for %s", email_id, exc_info=True
                )
            except Exception:
                pass
        finally:
            try:
                dedup_service.release_email_inflight_lock(email_id, lock_token)
            except Exception:
                pass

    def process_gmail_push(self, payload: Dict[str, Any]) -> Tuple[Dict[str, Any], int]:
        valid, msg, fields = self._validate_payload(payload)
        if not valid:
            return {"success": False, "message": msg}, 400

        subject, sender_raw, body, email_date = fields["subject"], fields["sender_raw"], fields["body"], fields["email_date"]

        enabled, msg = self._check_ingress_enabled()
        if not enabled:
            return {"success": False, "message": msg}, 409

        sender_email = self._extract_clean_sender(sender_raw)
        email_id = self._compute_email_id(subject=subject, sender=sender_email, date=email_date)
        self._log_ingress_receipt(email_id, sender_email, subject)

        dedup_service = DeduplicationService.get_instance()
        if dedup_service.is_email_processed(email_id):
            return {"success": True, "status": "already_processed", "email_id": email_id}, 200

        # Fast synchronous preconditions (allowlist, webhook enabled)
        can_proceed, early = self._check_preconditions(sender_email, dedup_service, email_id)
        if not can_proceed:
            return early  # type: ignore[return-value]

        lock_token = None
        inflight_acquired = False
        try:
            lock_ttl = getattr(settings, "EMAIL_ID_INFLIGHT_LOCK_TTL_SECONDS", 10)
            inflight_acquired, lock_token = dedup_service.acquire_email_inflight_lock(email_id, lock_ttl)
            if not inflight_acquired:
                return {"success": True, "status": "already_processing", "email_id": email_id}, 200
        except Exception:
            inflight_acquired = False

        if inflight_acquired:
            self._get_executor().submit(
                self._process_in_background,
                dedup_service=dedup_service,
                email_id=email_id,
                lock_token=lock_token,
                sender_email=sender_email,
                subject=subject,
                body=body,
                email_date=email_date,
                sender_raw=sender_raw,
            )
            return {"success": True, "status": "queued", "email_id": email_id}, 200

        return self._process_fresh_email(
            dedup_service=dedup_service, email_id=email_id, sender_email=sender_email,
            subject=subject, body=body, email_date=email_date, sender_raw=sender_raw,
        )
