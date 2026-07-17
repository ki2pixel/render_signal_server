"""
email_processing.orchestrator
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Centralizes orchestration calls for the email polling workflow.
Provides a stable interface for email processing with detector-specific routing.
"""
from __future__ import annotations

from typing import Optional, Any, Dict
import logging
import re as _stdlib_re  # kept for fallback when re2 is unavailable
from typing_extensions import TypedDict
from datetime import datetime, timezone
import os
import json
from pathlib import Path

try:
    import re2 as re
    _USING_RE2 = True
except ImportError:
    re = _stdlib_re
    _USING_RE2 = False
    logging.getLogger(__name__).warning(
        "ORCH: google-re2 not installed; falling back to stdlib re (no ReDoS protection)."
    )
from utils.time_helpers import parse_time_hhmm, is_within_time_window_local, get_polling_timezone
from utils.text_helpers import mask_sensitive_data, strip_leading_reply_prefixes
from config import settings
from services.deduplication_service import DeduplicationService
from services.rate_limit_service import RateLimitService
from services.webhook_logger_service import WebhookLoggerService
from email_processing import imap_client


from email import message_from_bytes

# =============================================================================
# CONSTANTS
# =============================================================================

IMAP_MAILBOX_INBOX = "INBOX"
IMAP_STATUS_OK = "OK"
IMAP_SEARCH_CRITERIA_UNSEEN = "(UNSEEN)"
IMAP_FETCH_RFC822 = "(RFC822)"

DETECTOR_RECADRAGE = "recadrage"
DETECTOR_DESABO = "desabonnement_journee_tarifs"

ROUTE_DESABO = "DESABO"
ROUTE_MEDIA_SOLUTION = "MEDIA_SOLUTION"

WEEKDAY_NAMES = [
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
]

MAX_HTML_BYTES = 1024 * 1024
WEBHOOK_DELIVERY_MODE_JSON = "json"
WEBHOOK_DELIVERY_MODE_FORM = "form"
WEBHOOK_DELIVERY_MODES = {
    WEBHOOK_DELIVERY_MODE_JSON,
    WEBHOOK_DELIVERY_MODE_FORM,
}


# =============================================================================
# TYPE DEFINITIONS
# =============================================================================

class ParsedEmail(TypedDict, total=False):
    """Structure d'un email parsé depuis IMAP."""
    num: str
    subject: str
    sender: str
    date_raw: str
    msg: Any  # email.message.Message
    body_plain: str
    body_html: str



# =============================================================================
# MODULE-LEVEL HELPERS
# =============================================================================

def _get_webhook_config_dict() -> dict:
    try:
        from services import WebhookConfigService

        service = None
        try:
            service = WebhookConfigService.get_instance()
        except ValueError:
            try:
                from config import app_config_store as _store
                from pathlib import Path as _Path

                cfg_path = _Path(__file__).resolve().parents[1] / "debug" / "webhook_config.json"
                service = WebhookConfigService.get_instance(
                    file_path=cfg_path,
                    external_store=_store,
                )
            except Exception:
                service = None

        if service is not None:
            try:
                service.reload()
            except Exception:
                pass
            data = service.get_all_config()
            if isinstance(data, dict):
                return data
    except Exception:
        pass

    try:
        from config import app_config_store as _store
        from pathlib import Path as _Path

        cfg_path = _Path(__file__).resolve().parents[1] / "debug" / "webhook_config.json"
        data = _store.get_config_json("webhook_config", file_fallback=cfg_path) or {}
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _get_routing_rules_payload() -> dict:
    """Charge les règles de routage dynamiques depuis le store Redis-first."""
    try:
        from services import RoutingRulesService

        service = None
        try:
            service = RoutingRulesService.get_instance()
        except ValueError:
            try:
                from config import app_config_store as _store
                from pathlib import Path as _Path

                cfg_path = _Path(__file__).resolve().parents[1] / "debug" / "routing_rules.json"
                service = RoutingRulesService.get_instance(
                    file_path=cfg_path,
                    external_store=_store,
                )
            except Exception:
                service = None

        if service is not None:
            try:
                service.reload()
            except Exception:
                pass
            payload = service.get_payload()
            if isinstance(payload, dict):
                return payload
    except Exception:
        pass

    try:
        from config import app_config_store as _store
        from pathlib import Path as _Path

        cfg_path = _Path(__file__).resolve().parents[1] / "debug" / "routing_rules.json"
        data = _store.get_config_json("routing_rules", file_fallback=cfg_path) or {}
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _normalize_match_value(value: str, *, case_sensitive: bool) -> str:
    if case_sensitive:
        return value
    return value.lower()


def _match_routing_condition(condition: dict, *, sender: str, subject: str, body: str) -> bool:
    try:
        field = str(condition.get("field") or "").strip().lower()
        operator = str(condition.get("operator") or "").strip().lower()
        value = str(condition.get("value") or "").strip()
        case_sensitive = bool(condition.get("case_sensitive", False))
        if not field or not operator or not value:
            return False

        target_map = {
            "sender": sender or "",
            "subject": subject or "",
            "body": body or "",
        }
        target = target_map.get(field, "")
        target_norm = _normalize_match_value(str(target), case_sensitive=case_sensitive)
        value_norm = _normalize_match_value(value, case_sensitive=case_sensitive)

        if operator == "contains":
            return value_norm in target_norm
        if operator == "equals":
            return value_norm == target_norm
        if operator == "regex":
            flags = 0 if case_sensitive else re.IGNORECASE
            try:
                return re.search(value, str(target), flags=flags) is not None
            except re.error:
                return False
        return False
    except Exception:
        return False


def _find_matching_routing_rule(
    rules: list,
    *,
    sender: str,
    subject: str,
    body: str,
    email_id: str,
    logger,
):
    if not isinstance(rules, list) or not rules:
        return None

    for rule in rules:
        if not isinstance(rule, dict):
            continue
        conditions = rule.get("conditions")
        if not isinstance(conditions, list) or not conditions:
            continue
        try:
            if all(
                _match_routing_condition(
                    cond,
                    sender=sender,
                    subject=subject,
                    body=body,
                )
                for cond in conditions
            ):
                try:
                    logger.info(
                        "ROUTING_RULES: Matched rule %s (%s) for email %s (sender=%s, subject=%s)",
                        rule.get("id", "unknown"),
                        rule.get("name", "rule"),
                        email_id,
                        mask_sensitive_data(sender or "", "email"),
                        mask_sensitive_data(subject or "", "subject"),
                    )
                except Exception:
                    pass
                return rule
        except Exception as exc:
            try:
                logger.debug(
                    "ROUTING_RULES: Evaluation error for rule %s: %s",
                    rule.get("id", "unknown"),
                    exc,
                )
            except Exception:
                pass
    return None

def _is_webhook_sending_enabled() -> bool:
    """Check if webhook sending is globally enabled.
    
    Checks in order: DB config → JSON file → ENV var (default: true)
    Also checks absence pause configuration to block all emails on specific days.
    
    Returns:
        bool: True if webhooks should be sent
    """
    try:
        data = _get_webhook_config_dict() or {}

        absence_pause_enabled = data.get("absence_pause_enabled", False)
        if absence_pause_enabled:
            absence_pause_days = data.get("absence_pause_days", [])
            if isinstance(absence_pause_days, list) and absence_pause_days:
                local_now = datetime.now(timezone.utc).astimezone()
                weekday_idx: int | None = None
                try:
                    weekday_candidate = local_now.weekday()
                    if isinstance(weekday_candidate, int):
                        weekday_idx = weekday_candidate
                except Exception:
                    weekday_idx = None

                if weekday_idx is not None and 0 <= weekday_idx <= 6:
                    current_day = WEEKDAY_NAMES[weekday_idx]
                else:
                    current_day = local_now.strftime("%A").lower()
                normalized_days = [
                    str(d).strip().lower()
                    for d in absence_pause_days
                    if isinstance(d, str)
                ]
                if current_day in normalized_days:
                    return False

        if isinstance(data, dict) and "webhook_sending_enabled" in data:
            return bool(data.get("webhook_sending_enabled"))
    except Exception:
        pass
    try:
        env_val = os.environ.get("WEBHOOK_SENDING_ENABLED", "true").strip().lower()
        return env_val in ("1", "true", "yes", "on")
    except Exception:
        return True


def _load_webhook_global_time_window() -> tuple[str, str]:
    """Load webhook time window configuration.
    
    Checks in order: DB config → JSON file → ENV vars
    
    Returns:
        tuple[str, str]: (start_time_str, end_time_str) e.g. ('10h30', '19h00')
    """
    try:
        data = _get_webhook_config_dict() or {}
        s = (data.get("webhook_time_start") or "").strip()
        e = (data.get("webhook_time_end") or "").strip()
        # Use file values but allow ENV to fill missing sides
        env_s = (
            os.environ.get("WEBHOOKS_TIME_START")
            or os.environ.get("WEBHOOK_TIME_START")
            or ""
        ).strip()
        env_e = (
            os.environ.get("WEBHOOKS_TIME_END")
            or os.environ.get("WEBHOOK_TIME_END")
            or ""
        ).strip()
        if s or e:
            s_eff = s or env_s
            e_eff = e or env_e
            return s_eff, e_eff
    except Exception:
        pass
    # ENV fallbacks
    try:
        s = (
            os.environ.get("WEBHOOKS_TIME_START")
            or os.environ.get("WEBHOOK_TIME_START")
            or ""
        ).strip()
        e = (
            os.environ.get("WEBHOOKS_TIME_END")
            or os.environ.get("WEBHOOK_TIME_END")
            or ""
        ).strip()
        return s, e
    except Exception:
        return "", ""


def _normalize_webhook_delivery_mode(value: Any) -> str:
    candidate = str(value or "").strip().lower()
    if candidate in WEBHOOK_DELIVERY_MODES:
        return candidate
    return WEBHOOK_DELIVERY_MODE_JSON


def _resolve_webhook_delivery_settings(
    *,
    webhook_delivery_mode: str | None,
    webhook_fallback_on_415: bool | None,
) -> tuple[str, bool]:
    cfg = _get_webhook_config_dict() or {}

    resolved_mode = _normalize_webhook_delivery_mode(
        webhook_delivery_mode
        if webhook_delivery_mode is not None
        else cfg.get("webhook_delivery_mode")
        or os.environ.get("WEBHOOK_DELIVERY_MODE")
    )

    if webhook_fallback_on_415 is None:
        fallback_raw = cfg.get("webhook_fallback_on_415")
        if fallback_raw is None:
            fallback_raw = os.environ.get("WEBHOOK_FALLBACK_ON_415", "true")
        resolved_fallback = bool(fallback_raw) if isinstance(fallback_raw, bool) else str(
            fallback_raw
        ).strip().lower() in ("1", "true", "yes", "on")
    else:
        resolved_fallback = bool(webhook_fallback_on_415)

    return resolved_mode, resolved_fallback


def _build_webhook_mode_sequence(
    primary_mode: str,
    *,
    fallback_on_415: bool,
) -> list[str]:
    sequence = [primary_mode]
    if not fallback_on_415:
        return sequence

    alternate = (
        WEBHOOK_DELIVERY_MODE_FORM
        if primary_mode == WEBHOOK_DELIVERY_MODE_JSON
        else WEBHOOK_DELIVERY_MODE_JSON
    )
    if alternate not in sequence:
        sequence.append(alternate)
    return sequence


def _build_webhook_request_kwargs(
    *,
    serialized_payload: str,
    delivery_mode: str,
) -> dict[str, Any]:
    content_type = (
        "application/json"
        if delivery_mode == WEBHOOK_DELIVERY_MODE_JSON
        else "application/x-www-form-urlencoded"
    )
    return {
        "data": serialized_payload,
        "headers": {
            "Content-Type": content_type,
            "Accept": "application/json, text/plain, */*",
        },
    }


def _truncate_webhook_response_snippet(value: Any, *, limit: int = 200) -> str:
    if value is None:
        return ""
    text = str(value).strip().replace("\r", " ").replace("\n", " ")
    text = re.sub(r"\s+", " ", text)
    return text[:limit]


def _normalize_webhook_failure_reason(*, status_code: int | None, response_text: str = "") -> str:
    response_text_norm = str(response_text or "").strip().lower()
    if "imunify360" in response_text_norm or "bot-protection" in response_text_norm:
        return "bot_protection_denied"
    if status_code == 415:
        return "unsupported_media_type"
    if status_code == 429:
        return "rate_limited"
    if status_code is not None and status_code >= 500:
                return "upstream_server_error"
    if status_code is not None and status_code >= 400:
        return "upstream_client_error"
    if response_text_norm:
        return "remote_application_error"
    return "request_failed"


def _parse_email(mail, num: bytes, logger) -> Optional[ParsedEmail]:
    """Fetch and parse email from IMAP."""
    try:
        status, msg_data = mail.fetch(num, '(RFC822)')
        if status != 'OK' or not msg_data:
            logger.warning("IMAP: Failed to fetch message %s (status=%s)", num, status)
            return None

        raw_bytes = None
        for part in msg_data:
            if isinstance(part, tuple) and isinstance(part[1], (bytes, bytearray)):
                raw_bytes = part[1]
                break
        if not raw_bytes:
            logger.warning("IMAP: No RFC822 bytes for message %s", num)
            return None

        from email import message_from_bytes
        msg = message_from_bytes(raw_bytes)
        subj_raw = msg.get('Subject', '')
        from_raw = msg.get('From', '')
        date_raw = msg.get('Date', '')

        subject = imap_client.decode_email_header_value(subj_raw)
        sender = imap_client.extract_sender_email(from_raw).lower()

        body_plain, body_html = _extract_email_bodies(msg, logger)

        return {
            'num': num.decode() if isinstance(num, bytes) else str(num),
            'subject': subject,
            'sender': sender,
            'date_raw': date_raw,
            'msg': msg,
            'body_plain': body_plain,
            'body_html': body_html,
        }
    except Exception as e:
        logger.error("IMAP error fetching/parsing email %s: %s", num, e)
        return None


def _extract_email_bodies(msg, logger) -> tuple[str, str]:
    """Extract plain and HTML bodies from message with size limit enforcement."""
    body_plain = ""
    body_html = ""
    try:
        if msg.is_multipart():
            html_bytes_total = 0
            html_truncated_logged = False
            for part in msg.walk():
                ctype = part.get_content_type()
                disp = (part.get('Content-Disposition') or '').lower()
                if 'attachment' in disp:
                    continue
                payload = part.get_payload(decode=True) or b''
                if ctype == 'text/plain':
                    body_plain += payload.decode(part.get_content_charset() or 'utf-8', errors='ignore')
                elif ctype == 'text/html':
                    if isinstance(payload, (bytes, bytearray)):
                        remaining = MAX_HTML_BYTES - html_bytes_total
                        if len(payload) > remaining:
                            payload = payload[:remaining]
                            if not html_truncated_logged:
                                logger.warning("HTML content truncated (exceeded 1MB limit)")
                                html_truncated_logged = True
                        html_bytes_total += len(payload)
                    body_html += payload.decode(part.get_content_charset() or 'utf-8', errors='ignore')
        else:
            payload = msg.get_payload(decode=True) or b''
            ctype = msg.get_content_type() or 'text/plain'
            if ctype == 'text/html':
                if len(payload) > MAX_HTML_BYTES:
                    logger.warning("HTML content truncated (exceeded 1MB limit)")
                    payload = payload[:MAX_HTML_BYTES]
                body_html = payload.decode(msg.get_content_charset() or 'utf-8', errors='ignore')
            else:
                body_plain = payload.decode(msg.get_content_charset() or 'utf-8', errors='ignore')
    except Exception as e:
        logger.debug("Email body extraction error: %s", e)
    return body_plain, body_html


def _apply_routing_rules(
    subject: str,
    sender_addr: str,
    body: str,
    email_id: str,
    logger,
) -> tuple[str | None, bool, str | None]:
    """Applies dynamic routing rules and returns (webhook_url, stop_processing, priority)."""
    try:
        routing_payload = _get_routing_rules_payload()
        routing_rules = routing_payload.get("rules") if isinstance(routing_payload, dict) else []
        matched_rule = _find_matching_routing_rule(
            routing_rules,
            sender=sender_addr,
            subject=subject,
            body=body,
            email_id=email_id,
            logger=logger,
        )
        if isinstance(matched_rule, dict):
            actions = matched_rule.get("actions")
            if isinstance(actions, dict):
                candidate_url = actions.get("webhook_url")
                if isinstance(candidate_url, str) and candidate_url.strip():
                    routing_webhook_url = candidate_url.strip()
                    routing_stop_processing = bool(actions.get("stop_processing", False))
                    priority_value = actions.get("priority")
                    routing_priority = priority_value.strip().lower() if isinstance(priority_value, str) else None
                    return routing_webhook_url, routing_stop_processing, routing_priority
                else:
                    logger.warning(
                        "ROUTING_RULES: Rule %s missing webhook_url; skipping",
                        matched_rule.get("id", "unknown"),
                    )
    except Exception as routing_exc:
        logger.debug("ROUTING_RULES: Evaluation error: %s", routing_exc)
    return None, False, None


def _enforce_time_window(
    detector_val: str | None,
    desabo_is_urgent: bool,
    now_local: datetime,
    s_str: str,
    e_str: str,
    within: bool,
    email_id: str,
    mail,
    num,
    logger,
) -> bool:
    """Checks the time window constraints and logs outcomes."""
    if within:
        return True
    tw_start_str = s_str or 'unset'
    tw_end_str = e_str or 'unset'
    now_str = now_local.strftime('%H:%M')
    if detector_val == 'desabonnement_journee_tarifs':
        if desabo_is_urgent:
            logger.info("WEBHOOK_GLOBAL_TIME_WINDOW: Outside window for urgent DESABO (now=%s, window=%s-%s)", now_str, tw_start_str, tw_end_str)
            return False
        logger.info("WEBHOOK_GLOBAL_TIME_WINDOW: Outside window for DESABO (non-urgent) -> bypassing (now=%s, window=%s-%s)", now_str, tw_start_str, tw_end_str)
        return True
    if detector_val == 'recadrage':
        logger.info("WEBHOOK_GLOBAL_TIME_WINDOW: Outside window for RECADRAGE -> skipping (now=%s, window=%s-%s)", now_str, tw_start_str, tw_end_str)
        try:
            DeduplicationService.get_instance().mark_email_processed(email_id)
            imap_client.mark_email_as_read_imap(logger, mail, num)
        except Exception:
            pass
        return False
    logger.info("WEBHOOK_GLOBAL_TIME_WINDOW: Outside dedicated window for email %s. Skipping.", email_id)
    return False


def _send_webhook(
    email_id: str,
    subject: str,
    payload_for_webhook: dict,
    delivery_links: list,
    webhook_url: str,
    processing_prefs: dict,
    mail,
    num,
    logger,
) -> bool:
    """Dispatches sending to custom webhook flow. Returns success/attempt status."""
    return send_custom_webhook_flow(
        email_id=email_id,
        subject=subject,
        payload_for_webhook=payload_for_webhook,
        delivery_links=delivery_links,
        webhook_url=webhook_url,
        webhook_ssl_verify=True,
        allow_without_links=bool(getattr(settings, 'ALLOW_CUSTOM_WEBHOOK_WITHOUT_LINKS', False)),
        processing_prefs=processing_prefs,
        rate_limit_allow_send=RateLimitService.get_instance().allow_send,
        record_send_event=RateLimitService.get_instance().record_event,
        append_webhook_log=WebhookLoggerService.get_instance().append_log,
        mark_email_id_as_processed_redis=DeduplicationService.get_instance().mark_email_processed,
        mark_email_as_read_imap=lambda *a, **k: imap_client.mark_email_as_read_imap(logger, *a, **k),
        mail=mail,
        email_num=num,
        urlparse=None,
        requests=__import__('requests'),
        time=__import__('time'),
        logger=logger,
    )


def _handle_r2_enrichment(delivery_links: list, email_id: str, logger) -> None:
    """Enrich delivery links with Cloudflare R2 offload URLs when enabled."""
    try:
        from services import R2TransferService
        r2_service = R2TransferService.get_instance()
        if not r2_service.is_enabled() or not delivery_links:
            return
        for link_item in delivery_links:
            if not isinstance(link_item, dict):
                continue
            source_url = link_item.get('raw_url')
            provider = link_item.get('provider')
            if source_url and provider:
                fallback_raw_url = source_url
                fallback_direct_url = link_item.get('direct_url') or source_url
                link_item['raw_url'] = source_url
                if not link_item.get('direct_url'):
                    link_item['direct_url'] = fallback_direct_url
                try:
                    normalized = r2_service.normalize_source_url(source_url, provider)
                    timeout = 120 if provider == "dropbox" and "/scl/fo/" in normalized.lower() else 15
                    r2_result = r2_service.request_remote_fetch(
                        source_url=normalized, provider=provider, email_id=email_id, timeout=timeout
                    )
                    r2_url, filename = r2_result if isinstance(r2_result, tuple) and len(r2_result) == 2 else (None, None)
                    if r2_url:
                        link_item['r2_url'] = r2_url
                        if isinstance(filename, str) and filename.strip():
                            link_item['original_filename'] = filename.strip()
                        r2_service.persist_link_pair(normalized, r2_url, provider, filename)
                        logger.info("R2_TRANSFER: Successfully transferred link to R2 for %s", email_id)
                    else:
                        raise ValueError("R2 fetch returned empty url")
                except Exception:
                    logger.warning("R2 transfer failed, falling back to source url")
                    link_item['raw_url'] = fallback_raw_url
                    link_item['direct_url'] = fallback_direct_url
    except Exception as ex:
        logger.debug("R2_TRANSFER: Service unavailable: %s", ex)


def _infer_detectors(subject: str, text: str, logger) -> tuple[str | None, str | None, bool]:
    """Infers pattern matchers (DESABO / RECADRAGE). Returns (detector, delivery_time, is_urgent)."""
    detector_val = None
    delivery_time_val = None
    desabo_is_urgent = False
    try:
        pm_mod = globals().get('pattern_matching')
        if pm_mod is None or not hasattr(pm_mod, 'check_media_solution_pattern'):
            from email_processing import pattern_matching as _pm
            pm_mod = _pm
        ms_res = pm_mod.check_media_solution_pattern(
            subject or '', text or '', get_polling_timezone(), logger
        )
        if isinstance(ms_res, dict) and bool(ms_res.get('matches')):
            detector_val = 'recadrage'
            delivery_time_val = ms_res.get('delivery_time')
        else:
            des_res = pm_mod.check_desabo_conditions(
                subject or '', text or '', logger
            )
            if isinstance(des_res, dict) and bool(des_res.get('matches')):
                detector_val = 'desabonnement_journee_tarifs'
                desabo_is_urgent = bool(des_res.get('is_urgent'))
    except Exception as _det_ex:
        logger.debug("DETECTOR_DEBUG: inference error: %s", _det_ex)
    return detector_val, delivery_time_val, desabo_is_urgent


def _build_webhook_payload(
    email_id: str,
    subject: str,
    date_raw: str,
    from_raw: str,
    sender_addr: str,
    combined_text: str,
    s_str: str,
    e_str: str,
    within: bool,
    detector_val: str | None,
    delivery_time_val: str | None,
    desabo_is_urgent: bool,
    now_local: datetime,
    start_t,
    _w_tw,
) -> dict:
    """Builds the final payload dictionary for the webhook call."""
    preview = (combined_text or "")[:200]
    s_eff = s_str or _w_tw.get_time_window_info().get('start') or ''
    e_eff = e_str or _w_tw.get_time_window_info().get('end') or ''
    start_payload_val = None
    try:
        if s_eff and e_eff and start_t:
            now_t = now_local.timetz().replace(tzinfo=None)
            if within:
                start_payload_val = "maintenant"
            elif detector_val == 'desabonnement_journee_tarifs' and not desabo_is_urgent and now_t < start_t:
                start_payload_val = s_eff
    except Exception:
        pass
    payload = {
        "microsoft_graph_email_id": email_id,
        "subject": subject or "",
        "receivedDateTime": date_raw or "",
        "sender_address": from_raw or sender_addr,
        "bodyPreview": preview,
        "email_content": combined_text or "",
        "sender_email": sender_addr,
    }
    if start_payload_val is not None:
        payload["webhooks_time_start"] = start_payload_val
    if e_eff:
        payload["webhooks_time_end"] = e_eff
    if detector_val:
        payload["detector"] = detector_val
    if detector_val == 'recadrage' and delivery_time_val:
        payload["delivery_time"] = delivery_time_val
    return payload


def _load_processing_prefs() -> dict:
    """Loads current processing preferences with default fallback."""
    try:
        from routes.api_processing import DEFAULT_PROCESSING_PREFS
        from config.app_config_store import get_config_json as _config_get
        from pathlib import Path
        processing_prefs_file = Path(__file__).resolve().parents[1] / "debug" / "processing_prefs.json"
        data = _config_get("processing_prefs", file_fallback=processing_prefs_file) or {}
        if isinstance(data, dict):
            return {**DEFAULT_PROCESSING_PREFS, **data}
    except Exception:
        pass
    try:
        from routes.api_processing import DEFAULT_PROCESSING_PREFS
        return DEFAULT_PROCESSING_PREFS.copy()
    except Exception:
        return {}


# =============================================================================
# MAIN ORCHESTRATION FUNCTION
# =============================================================================

def check_new_emails_and_trigger_webhook() -> int:
    """Execute one IMAP polling cycle and trigger webhooks when appropriate."""
    logger = None
    try:
        from app_render import app as _app
        logger = getattr(_app, 'logger', None)
    except Exception:
        pass
    if not logger:
        import logging
        logger = logging.getLogger("email_processing.orchestrator")
    try:
        from email_processing import payloads, link_extraction
        from config import webhook_time_window as _w_tw
    except Exception as _imp_ex:
        logger.error("ORCHESTRATOR: Wiring error; skipping cycle: %s", _imp_ex)
        return 0

    if not _is_webhook_sending_enabled():
        logger.info("ABSENCE_PAUSE: Global absence active — skipping webhook sends.")
        return 0

    mail = imap_client.create_imap_connection(logger)
    if not mail:
        logger.error("POLLER: Email polling cycle aborted: IMAP connection failed.")
        return 0

    triggered_count = 0
    try:
        try:
            status, _ = mail.select(IMAP_MAILBOX_INBOX)
            if status != IMAP_STATUS_OK:
                logger.error("IMAP: Unable to select INBOX (status=%s)", status)
                return 0
        except Exception as e_sel:
            logger.error("IMAP: Exception selecting INBOX: %s", e_sel)
            return 0

        try:
            status, data = mail.search(None, 'UNSEEN')
            if status != IMAP_STATUS_OK:
                logger.error("IMAP: search UNSEEN failed (status=%s)", status)
                return 0
            email_nums = data[0].split() if data and data[0] else []
        except Exception as e_search:
            logger.error("IMAP: Exception during search UNSEEN: %s", e_search)
            return 0

        for num in email_nums:
            try:
                email_data = _parse_email(mail, num, logger)
                if not email_data:
                    continue

                subject, sender_addr, msg = email_data['subject'], email_data['sender'], email_data['msg']
                try:
                    sender_list = getattr(settings, 'SENDER_LIST_FOR_POLLING', [])
                except Exception:
                    sender_list = []
                allowed = [str(s).lower() for s in (sender_list or [])]
                if allowed and sender_addr not in allowed:
                    logger.info("POLLER: Skipping email %s (sender not in allowlist)", email_data['num'])
                    continue

                headers_map = {'Message-ID': msg.get('Message-ID', ''), 'Subject': subject or '', 'Date': email_data['date_raw']}
                email_id = imap_client.generate_email_id(headers_map)
                if DeduplicationService.get_instance().is_email_processed(email_id):
                    logger.info("DEDUP_EMAIL: Skipping already processed email_id=%s", email_id)
                    continue

                core_subject = strip_leading_reply_prefixes(subject or '')
                if core_subject != subject:
                    logger.info("IGNORED: Skipping reply/forward (email_id=%s)", email_id)
                    DeduplicationService.get_instance().mark_email_processed(email_id)
                    imap_client.mark_email_as_read_imap(logger, mail, num)
                    continue

                combined_text = (email_data['body_plain'] or '') + "\n" + (email_data['body_html'] or '')
                delivery_links = link_extraction.extract_provider_links_from_text(combined_text)
                _handle_r2_enrichment(delivery_links, email_id, logger)

                group_id = DeduplicationService.get_instance().generate_subject_group_id(subject or '')
                if DeduplicationService.get_instance().is_subject_group_processed(group_id):
                    logger.info("DEDUP_GROUP: Skipping email %s (group processed)", email_id)
                    DeduplicationService.get_instance().mark_email_processed(email_id)
                    imap_client.mark_email_as_read_imap(logger, mail, num)
                    continue

                detector_val, delivery_time_val, desabo_is_urgent = _infer_detectors(subject, combined_text, logger)
                logger.info("CUSTOM_WEBHOOK: detector inferred for email %s: %s", email_id, detector_val or 'none')

                now_local = datetime.now(get_polling_timezone())
                s_str, e_str = _load_webhook_global_time_window()
                s_t, e_t = parse_time_hhmm(s_str) if s_str else None, parse_time_hhmm(e_str) if e_str else None

                _patched = globals().get('is_within_time_window_local')
                within = _patched(now_local, s_t, e_t) if callable(_patched) else is_within_time_window_local(now_local, s_t, e_t)

                if not _enforce_time_window(detector_val, desabo_is_urgent, now_local, s_str, e_str, within, email_id, mail, num, logger):
                    continue

                payload = _build_webhook_payload(
                    email_id, subject, email_data['date_raw'], msg.get('From', ''), sender_addr, combined_text,
                    s_str, e_str, within, detector_val, delivery_time_val, desabo_is_urgent, now_local, s_t, _w_tw
                )
                processing_prefs = _load_processing_prefs()

                routing_webhook_url, routing_stop_processing, routing_priority = _apply_routing_rules(
                    subject, sender_addr, combined_text, email_id, logger
                )
                if routing_webhook_url:
                    if routing_priority:
                        payload["routing_rule"] = {"id": payload.get("routing_rule", {}).get("id"), "name": payload.get("routing_rule", {}).get("name"), "priority": routing_priority}
                    cont = _send_webhook(email_id, subject, payload, delivery_links, routing_webhook_url, processing_prefs, mail, num, logger)
                    if cont is False:
                        triggered_count += 1
                    if routing_stop_processing:
                        continue

                should_send_default = True
                default_webhook_url = getattr(settings, 'WEBHOOK_URL', '')
                if routing_webhook_url and routing_webhook_url == default_webhook_url:
                    should_send_default = False
                if should_send_default:
                    cont = _send_webhook(email_id, subject, payload, delivery_links, default_webhook_url, processing_prefs, mail, num, logger)
                    if cont is False:
                        triggered_count += 1

            except Exception as e_one:
                if os.environ.get('ORCH_TEST_RERAISE') == '1':
                    raise
                logger.error("POLLER: Exception while processing message %s: %s", num, e_one)
                continue

        return triggered_count
    finally:
        try:
            imap_client.close_imap_connection(logger, mail)
        except Exception:
            pass


def compute_desabo_time_window(
    *,
    now_local,
    webhooks_time_start,
    webhooks_time_start_str: Optional[str],
    webhooks_time_end_str: Optional[str],
    within_window: bool,
) -> tuple[bool, Optional[str], bool]:
    """Compute DESABO time window flags and payload start value.

    Returns (early_ok: bool, time_start_payload: Optional[str], window_ok: bool)
    """
    early_ok = False
    try:
        if webhooks_time_start and now_local.time() < webhooks_time_start:
            early_ok = True
    except Exception:
        early_ok = False

    # If not early and not within window, it's not allowed
    if (not early_ok) and (not within_window):
        return early_ok, None, False

    # Payload rule: early -> configured start; within window -> "maintenant"
    time_start_payload = webhooks_time_start_str if early_ok else "maintenant"
    return early_ok, time_start_payload, True


def handle_desabo_route(
    *,
    subject: str,
    full_email_content: str,
    html_email_content: str | None,
    email_id: str,
    sender_raw: str,
    tz_for_polling,
    webhooks_time_start,
    webhooks_time_start_str: Optional[str],
    webhooks_time_end_str: Optional[str],
    processing_prefs: dict,
    extract_sender_email,
    check_desabo_conditions,
    build_desabo_make_payload,
    send_makecom_webhook,
    override_webhook_url,
    mark_subject_group_processed,
    subject_group_id: str | None,
    is_within_time_window_local,
    logger,
) -> bool:
    """Handle DESABO detection and Make webhook send. Returns True if routed (exclusive)."""
    try:
        combined_text = (full_email_content or "") + "\n" + (html_email_content or "")
        desabo_res = check_desabo_conditions(subject, combined_text, logger)
        has_dropbox_request = bool(desabo_res.get("has_dropbox_request"))
        has_required = bool(desabo_res.get("matches"))
        has_forbidden = False

        # Logging context (diagnostic)
        try:
            from utils.text_helpers import normalize_no_accents_lower_trim as _norm
            norm_body2 = _norm(full_email_content or "")
            required_terms = ["se desabonner", "journee", "tarifs habituels"]
            forbidden_terms = ["annulation", "facturation", "facture", "moment", "reference client", "total ht"]
            missing_required = [t for t in required_terms if t not in norm_body2]
            present_forbidden = [t for t in forbidden_terms if t in norm_body2]
            logger.debug(
                "DESABO_DEBUG: Email %s - required_terms_ok=%s, forbidden_present=%s, dropbox_request=%s, missing_required=%s, present_forbidden=%s",
                email_id, has_required, has_forbidden, has_dropbox_request, missing_required, present_forbidden,
            )
        except Exception:
            pass

        if not (has_required and not has_forbidden and has_dropbox_request):
            return False

        # Per-webhook exclude list for AUTOREPONDEUR
        desabo_excluded = False
        try:
            ex_auto = processing_prefs.get('exclude_keywords_autorepondeur') or []
            if ex_auto:
                from utils.text_helpers import normalize_no_accents_lower_trim as _norm
                norm_subj2 = _norm(subject or "")
                nb = _norm(full_email_content or "")
                if any((kw or '').strip().lower() in norm_subj2 or (kw or '').strip().lower() in nb for kw in ex_auto):
                    logger.info("EXCLUDE_KEYWORD: AUTOREPONDEUR skipped for %s (matched per-webhook exclude)", email_id)
                    desabo_excluded = True
        except Exception as _ex:
            logger.debug("EXCLUDE_KEYWORD: error evaluating autorepondeur excludes: %s", _ex)
        if desabo_excluded:
            return False

        # Time window
        now_local = datetime.now(tz_for_polling)
        within_window = is_within_time_window_local(now_local)
        early_ok, time_start_payload, window_ok = compute_desabo_time_window(
            now_local=now_local,
            webhooks_time_start=webhooks_time_start,
            webhooks_time_start_str=webhooks_time_start_str,
            webhooks_time_end_str=webhooks_time_end_str,
            within_window=within_window,
        )
        if not window_ok:
            logger.info(
                "DESABO: Time window not satisfied for email %s (now=%s, window=%s-%s). Skipping.",
                email_id, now_local.strftime('%H:%M'), webhooks_time_start_str or 'unset', webhooks_time_end_str or 'unset'
            )
            try:
                logger.info("IGNORED: DESABO skipped due to time window (email %s)", email_id)
            except Exception:
                pass
            return False

        sender_email_clean = extract_sender_email(sender_raw)
        extra_payload = build_desabo_make_payload(
            subject=subject,
            full_email_content=full_email_content,
            sender_email=sender_email_clean,
            time_start_payload=time_start_payload,
            time_end_payload=webhooks_time_end_str or None,
        )
        logger.info(
            "DESABO: Conditions matched for email %s. Sending Make webhook (early_ok=%s, start_payload=%s)",
            email_id, early_ok, time_start_payload,
        )
        send_ok = send_makecom_webhook(
            subject=subject,
            delivery_time=None,
            sender_email=sender_email_clean,
            email_id=email_id,
            override_webhook_url=override_webhook_url,
            extra_payload=extra_payload,
        )
        if send_ok:
            logger.info("DESABO: Make.com webhook sent successfully for email %s", email_id)
            try:
                if subject_group_id:
                    mark_subject_group_processed(subject_group_id)
            except Exception:
                pass
        else:
            logger.error("DESABO: Make.com webhook failed for email %s", email_id)
        return True
    except Exception as e_desabo:
        logger.error("DESABO: Exception during unsubscribe/journee/tarifs handling for email %s: %s", email_id, e_desabo)
        return False


def _check_no_links_policy(
    *,
    email_id: str,
    subject: str | None,
    delivery_links: list,
    allow_without_links: bool,
    webhook_url: str,
    mark_email_id_as_processed_redis,
    mark_email_as_read_imap,
    mail,
    email_num,
    append_webhook_log,
    logger,
) -> bool:
    if delivery_links or allow_without_links:
        return False
    try:
        logger.info(
            "CUSTOM_WEBHOOK: Skipping send for %s because no delivery links were detected and ALLOW_CUSTOM_WEBHOOK_WITHOUT_LINKS=false",
            email_id,
        )
        try:
            if mark_email_id_as_processed_redis(email_id):
                mark_email_as_read_imap(mail, email_num)
        except Exception:
            pass
        append_webhook_log({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": "custom",
            "email_id": email_id,
            "status": "skipped",
            "status_code": 204,
            "error_message": "No delivery links detected; skipping per config",
            "webhook_url": (webhook_url[:50] + "...") if len(webhook_url) > 50 else webhook_url,
            "subject": (subject[:100] if subject else None),
        })
    except Exception:
        pass
    return True


def _check_rate_limit(
    *,
    email_id: str,
    subject: str | None,
    webhook_url: str,
    rate_limit_allow_send,
    append_webhook_log,
    logger,
) -> bool:
    try:
        if not rate_limit_allow_send():
            logger.warning("RATE_LIMIT: Skipping webhook send due to rate limit.")
            append_webhook_log({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "type": "custom",
                "email_id": email_id,
                "status": "error",
                "status_code": 429,
                "error_message": "Rate limit exceeded",
                "webhook_url": (webhook_url[:50] + "...") if len(webhook_url) > 50 else webhook_url,
                "subject": (subject[:100] if subject else None),
            })
            return True
    except Exception:
        pass
    return False


def _prepare_payload(
    *,
    email_id: str,
    subject: str | None,
    payload_for_webhook: dict,
    delivery_links: list,
) -> tuple[dict, str, int]:
    payload_to_send = dict(payload_for_webhook) if isinstance(payload_for_webhook, dict) else {
        "microsoft_graph_email_id": email_id,
        "subject": subject or "",
    }
    if delivery_links:
        try:
            payload_to_send["delivery_links"] = delivery_links
        except Exception:
            pass
    serialized_payload = json.dumps(payload_to_send, ensure_ascii=False)
    payload_size_bytes = len(serialized_payload.encode("utf-8"))
    return payload_to_send, serialized_payload, payload_size_bytes


def _log_webhook_outcome(
    *,
    email_id: str,
    subject: str | None,
    webhook_url: str,
    status: str,
    status_code: int,
    append_webhook_log,
    delivery_mode: str | None = None,
    attempted_delivery_modes: list | None = None,
    payload_size_bytes: int = 0,
    error_message: str | None = None,
    response_snippet: str | None = None,
    failure_reason: str | None = None,
) -> None:
    modes = attempted_delivery_modes or []
    entry: dict = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "type": "custom",
        "email_id": email_id,
        "status": status,
        "status_code": status_code,
        "webhook_url": (webhook_url[:50] + "...") if len(webhook_url) > 50 else webhook_url,
        "subject": (subject[:100] if subject else None),
    }
    if delivery_mode is not None:
        entry["delivery_mode"] = delivery_mode
        entry["attempted_delivery_modes"] = modes
        entry["fallback_used"] = len(set(modes)) > 1
        entry["payload_size_bytes"] = payload_size_bytes
    if error_message is not None:
        entry["error_message"] = error_message
    if response_snippet is not None:
        entry["response_snippet"] = response_snippet
    if failure_reason is not None:
        entry["failure_reason"] = failure_reason
    append_webhook_log(entry)


def _send_single_attempt(
    *,
    email_id: str,
    serialized_payload: str,
    webhook_url: str,
    webhook_ssl_verify: bool,
    timeout_sec: int,
    resolved_delivery_mode: str,
    resolved_fallback_on_415: bool,
    retries: int,
    attempt: int,
    requests,
    logger,
) -> tuple[Any, bool, str, list[str]]:
    webhook_response = None
    should_retry = False
    last_mode = resolved_delivery_mode
    attempted: list[str] = []
    for mode_index, delivery_mode in enumerate(
        _build_webhook_mode_sequence(resolved_delivery_mode, fallback_on_415=resolved_fallback_on_415)
    ):
        last_mode = delivery_mode
        attempted.append(delivery_mode)
        request_kwargs = _build_webhook_request_kwargs(serialized_payload=serialized_payload, delivery_mode=delivery_mode)
        try:
            logger.debug("CUSTOM_WEBHOOK_DEBUG: attempt=%d/%d email=%s mode=%s", attempt + 1, retries + 1, email_id, delivery_mode)
        except Exception:
            pass
        webhook_response = requests.post(webhook_url, timeout=timeout_sec, verify=webhook_ssl_verify, **request_kwargs)
        if webhook_response.status_code != 415:
            break
        snippet = _truncate_webhook_response_snippet(getattr(webhook_response, "text", ""))
        try:
            logger.warning("CUSTOM_WEBHOOK: 415 for email %s mode=%s attempt=%d/%d resp=%s", email_id, delivery_mode, attempt + 1, retries + 1, snippet)
        except Exception:
            pass
        if mode_index == 0 and resolved_fallback_on_415:
            continue
        should_retry = attempt < retries
        break
    return webhook_response, should_retry, last_mode, attempted


def _execute_webhook_with_retries(
    *,
    email_id: str,
    serialized_payload: str,
    webhook_url: str,
    webhook_ssl_verify: bool,
    retries: int,
    delay: int,
    timeout_sec: int,
    resolved_delivery_mode: str,
    resolved_fallback_on_415: bool,
    requests,
    time,
    logger,
) -> tuple[Any, Exception | None, str, list[str]]:
    last_exc: Exception | None = None
    webhook_response = None
    last_delivery_mode = resolved_delivery_mode
    attempted_delivery_modes: list[str] = []
    for attempt in range(retries + 1):
        try:
            resp, should_retry, last_mode, modes = _send_single_attempt(
                email_id=email_id, serialized_payload=serialized_payload,
                webhook_url=webhook_url, webhook_ssl_verify=webhook_ssl_verify,
                timeout_sec=timeout_sec, resolved_delivery_mode=resolved_delivery_mode,
                resolved_fallback_on_415=resolved_fallback_on_415,
                retries=retries, attempt=attempt, requests=requests, logger=logger,
            )
            webhook_response = resp
            last_delivery_mode = last_mode
            attempted_delivery_modes.extend(modes)
            if webhook_response is not None and not should_retry:
                break
        except Exception as e_req:
            last_exc = e_req
            webhook_response = None
            if attempt < retries and delay > 0:
                time.sleep(delay)
            continue
        if should_retry:
            if delay > 0:
                time.sleep(delay)
    return webhook_response, last_exc, last_delivery_mode, attempted_delivery_modes


def _process_webhook_response(
    *,
    email_id: str,
    subject: str | None,
    webhook_url: str,
    webhook_response,
    last_exc: Exception | None,
    last_delivery_mode: str,
    attempted_delivery_modes: list[str],
    payload_size_bytes: int,
    mark_email_id_as_processed_redis,
    mark_email_as_read_imap,
    mail,
    email_num,
    record_send_event,
    append_webhook_log,
    logger,
) -> bool:
    record_send_event()
    if webhook_response is None:
        raise last_exc or Exception("Webhook request failed")
    if webhook_response.status_code == 200:
        try:
            response_data = webhook_response.json() if webhook_response.content else {}
        except Exception:
            response_data = {}
        if response_data.get("success", False):
            logger.info("POLLER: Webhook triggered successfully for email %s.", email_id)
            _log_webhook_outcome(
                email_id=email_id, subject=subject, webhook_url=webhook_url, status="success",
                status_code=200, append_webhook_log=append_webhook_log,
                delivery_mode=last_delivery_mode, attempted_delivery_modes=attempted_delivery_modes,
                payload_size_bytes=payload_size_bytes,
            )
            if mark_email_id_as_processed_redis(email_id):
                mark_email_as_read_imap(mail, email_num)
            return False
        msg = str(response_data.get("message", "Unknown error"))
        logger.error("POLLER: Webhook processing failed for email %s. Response: %s", email_id, msg)
        _log_webhook_outcome(
            email_id=email_id, subject=subject, webhook_url=webhook_url, status="error",
            status_code=200, append_webhook_log=append_webhook_log,
            delivery_mode=last_delivery_mode, attempted_delivery_modes=attempted_delivery_modes,
            payload_size_bytes=payload_size_bytes, error_message=msg[:200],
            response_snippet=_truncate_webhook_response_snippet(msg),
            failure_reason=_normalize_webhook_failure_reason(status_code=200, response_text=msg),
        )
        return False
    snippet = _truncate_webhook_response_snippet(webhook_response.text)
    logger.error("POLLER: Webhook call FAILED for email %s. Status: %s, mode=%s, Response: %s",
                 email_id, webhook_response.status_code, last_delivery_mode, snippet)
    _log_webhook_outcome(
        email_id=email_id, subject=subject, webhook_url=webhook_url, status="error",
        status_code=webhook_response.status_code, append_webhook_log=append_webhook_log,
        delivery_mode=last_delivery_mode, attempted_delivery_modes=attempted_delivery_modes,
        payload_size_bytes=payload_size_bytes, response_snippet=snippet or "Unknown error",
        error_message=snippet or "Unknown error",
        failure_reason=_normalize_webhook_failure_reason(
            status_code=webhook_response.status_code, response_text=webhook_response.text or ""
        ),
    )
    return False


def send_custom_webhook_flow(
    *,
    email_id: str,
    subject: str | None,
    payload_for_webhook: dict,
    delivery_links: list,
    webhook_url: str,
    webhook_ssl_verify: bool,
    allow_without_links: bool,
    processing_prefs: dict,
    rate_limit_allow_send,
    record_send_event,
    append_webhook_log,
    mark_email_id_as_processed_redis,
    mark_email_as_read_imap,
    mail,
    email_num,
    urlparse,
    requests,
    time,
    logger,
    webhook_delivery_mode: str | None = None,
    webhook_fallback_on_415: bool | None = None,
) -> bool:
    """Execute the custom webhook send flow. Returns True if caller should continue to next email."""
    if _check_no_links_policy(
        email_id=email_id, subject=subject, delivery_links=delivery_links,
        allow_without_links=allow_without_links, webhook_url=webhook_url,
        mark_email_id_as_processed_redis=mark_email_id_as_processed_redis,
        mark_email_as_read_imap=mark_email_as_read_imap, mail=mail, email_num=email_num,
        append_webhook_log=append_webhook_log, logger=logger,
    ):
        return True
    if _check_rate_limit(
        email_id=email_id, subject=subject, webhook_url=webhook_url,
        rate_limit_allow_send=rate_limit_allow_send, append_webhook_log=append_webhook_log, logger=logger,
    ):
        return True
    _payload_to_send, serialized_payload, payload_size_bytes = _prepare_payload(
        email_id=email_id, subject=subject, payload_for_webhook=payload_for_webhook, delivery_links=delivery_links,
    )
    retries = int(processing_prefs.get("retry_count") or 0)
    delay = int(processing_prefs.get("retry_delay_sec") or 0)
    timeout_sec = int(processing_prefs.get("webhook_timeout_sec") or 30)
    resolved_delivery_mode, resolved_fallback_on_415 = _resolve_webhook_delivery_settings(
        webhook_delivery_mode=webhook_delivery_mode, webhook_fallback_on_415=webhook_fallback_on_415,
    )
    try:
        logger.debug(
            "CUSTOM_WEBHOOK_DEBUG: Preparing to send for email %s to %s "
            "(timeout=%ss, retries=%d, delay=%ds, mode=%s, fallback=%s, bytes=%d)",
            email_id, webhook_url, timeout_sec, retries, delay,
            resolved_delivery_mode, resolved_fallback_on_415, payload_size_bytes,
        )
    except Exception:
        pass
    webhook_response, last_exc, last_delivery_mode, attempted_delivery_modes = _execute_webhook_with_retries(
        email_id=email_id, serialized_payload=serialized_payload, webhook_url=webhook_url,
        webhook_ssl_verify=webhook_ssl_verify, retries=retries, delay=delay,
        timeout_sec=timeout_sec, resolved_delivery_mode=resolved_delivery_mode,
        resolved_fallback_on_415=resolved_fallback_on_415, requests=requests, time=time, logger=logger,
    )
    return _process_webhook_response(
        email_id=email_id, subject=subject, webhook_url=webhook_url,
        webhook_response=webhook_response, last_exc=last_exc,
        last_delivery_mode=last_delivery_mode, attempted_delivery_modes=attempted_delivery_modes,
        payload_size_bytes=payload_size_bytes,
        mark_email_id_as_processed_redis=mark_email_id_as_processed_redis,
        mark_email_as_read_imap=mark_email_as_read_imap, mail=mail, email_num=email_num,
        record_send_event=record_send_event, append_webhook_log=append_webhook_log, logger=logger,
    )
