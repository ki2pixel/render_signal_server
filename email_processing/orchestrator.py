"""
email_processing.orchestrator
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Centralizes orchestration calls for the email polling workflow.
Provides a stable interface for email processing with detector-specific routing.
"""
from __future__ import annotations

from typing import Optional, Any, Dict
import re
from typing_extensions import TypedDict
from datetime import datetime, timezone
import os
import json
from pathlib import Path
from utils.time_helpers import parse_time_hhmm, is_within_time_window_local
from utils.text_helpers import mask_sensitive_data, strip_leading_reply_prefixes
from config import settings


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


def _fetch_and_parse_email(mail, num: bytes, logger, decode_fn, extract_sender_fn) -> Optional[ParsedEmail]:
    """Fetch et parse un email depuis IMAP.
    
    Args:
        mail: Connection IMAP active
        num: Numéro de message (bytes)
        logger: Logger Flask
        decode_fn: Fonction de décodage des headers (ar.decode_email_header)
        extract_sender_fn: Fonction d'extraction du sender (ar.extract_sender_email)
    
    Returns:
        ParsedEmail si succès, None si échec
    """
    from email import message_from_bytes
    
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
        
        msg = message_from_bytes(raw_bytes)
        subj_raw = msg.get('Subject', '')
        from_raw = msg.get('From', '')
        date_raw = msg.get('Date', '')
        
        subject = decode_fn(subj_raw) if decode_fn else subj_raw
        sender = extract_sender_fn(from_raw).lower() if extract_sender_fn else from_raw.lower()
        
        body_plain = ""
        body_html = ""
        try:
            if msg.is_multipart():
                for part in msg.walk():
                    ctype = part.get_content_type()
                    if ctype == 'text/plain':
                        body_plain = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                    elif ctype == 'text/html':
                        html_payload = part.get_payload(decode=True) or b''
                        if isinstance(html_payload, (bytes, bytearray)) and len(html_payload) > MAX_HTML_BYTES:
                            logger.warning("HTML content truncated (exceeded 1MB limit)")
                            html_payload = html_payload[:MAX_HTML_BYTES]
                        body_html = html_payload.decode('utf-8', errors='ignore')
            else:
                body_plain = msg.get_payload(decode=True).decode('utf-8', errors='ignore')
        except Exception as e:
            logger.debug("Email body extraction error for %s: %s", num, e)
        
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
        logger.error("Error fetching/parsing email %s: %s", num, e)
        return None


# =============================================================================
# MAIN ORCHESTRATION FUNCTION
# =============================================================================

def check_new_emails_and_trigger_webhook() -> int:
    """Execute one IMAP polling cycle and trigger webhooks when appropriate.
    
    This is the main orchestration function for email-based webhook triggering.
    It connects to IMAP, fetches unseen emails, applies pattern detection,
    and triggers appropriate webhooks based on routing rules.
    
    Workflow:
    1. Connect to IMAP server
    2. Fetch unseen emails from INBOX
    3. For each email:
       a. Parse headers and body
       b. Check sender allowlist and deduplication
       c. Infer detector type (RECADRAGE, DESABO, or none)
       d. Route to appropriate handler (Presence, DESABO, Media Solution, Custom)
       e. Apply time window rules
       f. Send webhook if conditions are met
       g. Mark email as processed
    
    Routes:
    - PRESENCE: Thursday/Friday presence notifications via autorepondeur webhook
    - DESABO: Désabonnement requests via Make.com webhook (bypasses time window)
    - MEDIA_SOLUTION: Legacy Media Solution route (disabled, uses Custom instead)
    - CUSTOM: Unified webhook flow via WEBHOOK_URL (with time window enforcement)
    
    Detector types:
    - RECADRAGE: Média Solution pattern (subject + delivery time extraction)
    - DESABO: Désabonnement + journée + tarifs pattern
    - None: Falls back to Custom webhook flow
    
    Returns:
        int: Number of triggered actions (best-effort count)
    
    Implementation notes:
    - Imports are lazy (inside function) to avoid circular dependencies
    - Defensive logging: never raises exceptions to the background loop
    - Uses deduplication (Redis) to avoid processing same email multiple times
    - Subject-group deduplication prevents spam from repetitive emails
    """
    # Legacy delegation removed: tests validate detector-specific behavior here
    try:
        import imaplib
        from email import message_from_bytes
    except Exception:
        # If stdlib imports fail, nothing we can do
        return 0

    try:
        import app_render as ar
        _app = ar.app
        from email_processing import imap_client
        from email_processing import payloads
        from email_processing import link_extraction
        from config import webhook_time_window as _w_tw
    except Exception as _imp_ex:
        try:
            # If wiring isn't ready, log and bail out
            from app_render import app as _app
            _app.logger.error(
                "ORCHESTRATOR: Wiring error; skipping cycle: %s", _imp_ex
            )
        except Exception:
            pass
        return 0

    try:
        allow_legacy = os.environ.get("ORCHESTRATOR_ALLOW_LEGACY_DELEGATION", "").strip().lower() in (
            "1",
            "true",
            "yes",
            "on",
        )
        if allow_legacy:
            legacy_fn = getattr(ar, "_legacy_check_new_emails_and_trigger_webhook", None)
            if callable(legacy_fn):
                try:
                    _app.logger.info(
                        "ORCHESTRATOR: legacy delegation enabled; calling app_render._legacy_check_new_emails_and_trigger_webhook"
                    )
                except Exception:
                    pass
                res = legacy_fn()
                try:
                    return int(res) if res is not None else 0
                except Exception:
                    return 0
    except Exception:
        pass

    logger = getattr(_app, 'logger', None)
    if not logger:
        return 0

    try:
        if not _is_webhook_sending_enabled():
            try:
                _day = datetime.now(timezone.utc).astimezone().strftime('%A')
            except Exception:
                _day = "unknown"
            logger.info(
                "ABSENCE_PAUSE: Global absence active for today (%s) — skipping all webhook sends this cycle.",
                _day,
            )
            return 0
    except Exception:
        pass

    mail = ar.create_imap_connection()
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

        def _is_within_time_window_local(now_local):
            try:
                return _w_tw.is_within_global_time_window(now_local)
            except Exception:
                return True

        for num in email_nums:
            try:
                status, msg_data = mail.fetch(num, '(RFC822)')
                if status != 'OK' or not msg_data:
                    logger.warning("IMAP: Failed to fetch message %s (status=%s)", num, status)
                    try:
                        logger.info(
                            "IGNORED: Skipping email %s due to fetch failure (status=%s)",
                            num.decode() if isinstance(num, bytes) else str(num),
                            status,
                        )
                    except Exception:
                        pass
                    if os.environ.get('ORCH_TEST_RERAISE') == '1':
                        try:
                            print("DEBUG_TEST group dedup -> continue")
                        except Exception:
                            pass
                    if os.environ.get('ORCH_TEST_RERAISE') == '1':
                        try:
                            print("DEBUG_TEST email-id dedup -> continue")
                        except Exception:
                            pass
                    continue
                raw_bytes = None
                for part in msg_data:
                    if isinstance(part, tuple) and isinstance(part[1], (bytes, bytearray)):
                        raw_bytes = part[1]
                        break
                if not raw_bytes:
                    logger.warning("IMAP: No RFC822 bytes for message %s", num)
                    try:
                        logger.info(
                            "IGNORED: Skipping email %s due to empty RFC822 payload",
                            num.decode() if isinstance(num, bytes) else str(num),
                        )
                    except Exception:
                        pass
                    continue

                msg = message_from_bytes(raw_bytes)
                subj_raw = msg.get('Subject', '')
                from_raw = msg.get('From', '')
                date_raw = msg.get('Date', '')
                subject = ar.decode_email_header(subj_raw)
                sender_addr = ar.extract_sender_email(from_raw).lower()
                if os.environ.get('ORCH_TEST_RERAISE') == '1':
                    try:
                        print(
                            "DEBUG_TEST parsed subject='%s' sender='%s'"
                            % (
                                mask_sensitive_data(subject or "", "subject"),
                                mask_sensitive_data(sender_addr or "", "email"),
                            )
                        )
                    except Exception:
                        pass
                try:
                    logger.info(
                        "POLLER: Email read from IMAP: num=%s, subject='%s', sender='%s'",
                        num.decode() if isinstance(num, bytes) else str(num),
                        mask_sensitive_data(subject or "", "subject") or 'N/A',
                        mask_sensitive_data(sender_addr or "", "email") or 'N/A',
                    )
                except Exception:
                    pass

                try:
                    sender_list = getattr(ar, 'SENDER_LIST_FOR_POLLING', None)
                except Exception:
                    sender_list = None
                if not sender_list:
                    try:
                        sender_list = getattr(settings, 'SENDER_LIST_FOR_POLLING', [])
                    except Exception:
                        sender_list = []
                allowed = [str(s).lower() for s in (sender_list or [])]
                if os.environ.get('ORCH_TEST_RERAISE') == '1':
                    try:
                        allowed_masked = [mask_sensitive_data(s or "", "email") for s in allowed][:3]
                        print(
                            "DEBUG_TEST allowlist allowed_count=%s allowed_sample=%s sender=%s"
                            % (
                                len(allowed),
                                allowed_masked,
                                mask_sensitive_data(sender_addr or "", "email"),
                            )
                        )
                    except Exception:
                        pass
                if allowed and sender_addr not in allowed:
                    logger.info(
                        "POLLER: Skipping email %s (sender %s not in allowlist)",
                        num.decode() if isinstance(num, bytes) else str(num),
                        mask_sensitive_data(sender_addr or "", "email"),
                    )
                    try:
                        logger.info(
                            "IGNORED: Sender not in allowlist for email %s (sender=%s)",
                            num.decode() if isinstance(num, bytes) else str(num),
                            mask_sensitive_data(sender_addr or "", "email"),
                        )
                    except Exception:
                        pass
                    continue

                headers_map = {
                    'Message-ID': msg.get('Message-ID', ''),
                    'Subject': subject or '',
                    'Date': date_raw or '',
                }
                email_id = imap_client.generate_email_id(headers_map)
                if os.environ.get('ORCH_TEST_RERAISE') == '1':
                    try:
                        print(f"DEBUG_TEST email_id={email_id}")
                    except Exception:
                        pass
                if ar.is_email_id_processed_redis(email_id):
                    logger.info("DEDUP_EMAIL: Skipping already processed email_id=%s", email_id)
                    try:
                        logger.info("IGNORED: Email %s ignored due to email-id dedup", email_id)
                    except Exception:
                        pass
                    continue

                try:
                    original_subject = subject or ''
                    core_subject = strip_leading_reply_prefixes(original_subject)
                    if core_subject != original_subject:
                        logger.info(
                            "IGNORED: Skipping webhook because subject is a reply/forward (email_id=%s, subject='%s')",
                            email_id,
                            mask_sensitive_data(original_subject or "", "subject"),
                        )
                        ar.mark_email_id_as_processed_redis(email_id)
                        ar.mark_email_as_read_imap(mail, num)
                        if os.environ.get('ORCH_TEST_RERAISE') == '1':
                            try:
                                print("DEBUG_TEST reply/forward skip -> continue")
                            except Exception:
                                pass
                        continue
                except Exception:
                    pass

                combined_text_for_detection = ""
                full_text = ""
                html_text = ""
                html_bytes_total = 0
                html_truncated_logged = False
                try:
                    if msg.is_multipart():
                        for part in msg.walk():
                            ctype = part.get_content_type()
                            disp = (part.get('Content-Disposition') or '').lower()
                            if 'attachment' in disp:
                                continue
                            payload = part.get_payload(decode=True) or b''
                            if ctype == 'text/plain':
                                decoded = payload.decode(part.get_content_charset() or 'utf-8', errors='ignore')
                                full_text += decoded
                            elif ctype == 'text/html':
                                if isinstance(payload, (bytes, bytearray)):
                                    remaining = MAX_HTML_BYTES - html_bytes_total
                                    if remaining <= 0:
                                        if not html_truncated_logged:
                                            logger.warning("HTML content truncated (exceeded 1MB limit)")
                                            html_truncated_logged = True
                                        continue
                                    if len(payload) > remaining:
                                        payload = payload[:remaining]
                                        if not html_truncated_logged:
                                            logger.warning("HTML content truncated (exceeded 1MB limit)")
                                            html_truncated_logged = True
                                    html_bytes_total += len(payload)
                                decoded = payload.decode(part.get_content_charset() or 'utf-8', errors='ignore')
                                html_text += decoded
                    else:
                        payload = msg.get_payload(decode=True) or b''
                        if isinstance(payload, (bytes, bytearray)) and (msg.get_content_type() or 'text/plain') == 'text/html':
                            if len(payload) > MAX_HTML_BYTES:
                                logger.warning("HTML content truncated (exceeded 1MB limit)")
                                payload = payload[:MAX_HTML_BYTES]
                        decoded = payload.decode(msg.get_content_charset() or 'utf-8', errors='ignore')
                        ctype_single = msg.get_content_type() or 'text/plain'
                        if ctype_single == 'text/html':
                            html_text = decoded
                        else:
                            full_text = decoded
                except Exception:
                    full_text = full_text or ''
                    html_text = html_text or ''

                # Combine plain + HTML for detectors that scan raw text (regex catches URLs in HTML too)
                try:
                    combined_text_for_detection = (full_text or '') + "\n" + (html_text or '')
                    if os.environ.get('ORCH_TEST_RERAISE') == '1':
                        try:
                            print("DEBUG_TEST combined text ready")
                        except Exception:
                            pass
                except Exception:
                    combined_text_for_detection = full_text or ''

                # Presence route removed (feature deprecated)

                # 2) DESABO route — disabled (legacy Make.com path). Unified flow via WEBHOOK_URL only.
                try:
                    logger.info("ROUTES: DESABO route disabled — using unified custom webhook flow (WEBHOOK_URL)")
                except Exception:
                    pass

                # 3) Media Solution route — disabled (legacy Make.com path). Unified flow via WEBHOOK_URL only.
                try:
                    logger.info("ROUTES: Media Solution route disabled — using unified custom webhook flow (WEBHOOK_URL)")
                except Exception:
                    pass

                # 4) Custom webhook flow (outside-window handling occurs after detector inference)

                # Enforce dedicated webhook-global time window only when sending is enabled
                try:
                    now_local = datetime.now(ar.TZ_FOR_POLLING)
                except Exception:
                    now_local = datetime.now(timezone.utc)

                s_str, e_str = _load_webhook_global_time_window()
                s_t = parse_time_hhmm(s_str) if s_str else None
                e_t = parse_time_hhmm(e_str) if e_str else None
                # Prefer module-level patched helper if available (tests set orch_local.is_within_time_window_local)
                _patched = globals().get('is_within_time_window_local')
                if callable(_patched):
                    within = _patched(now_local, s_t, e_t)
                else:
                    try:
                        from utils import time_helpers as _th
                        within = _th.is_within_time_window_local(now_local, s_t, e_t)
                    except Exception:
                        # Fallback to the locally imported helper
                        within = is_within_time_window_local(now_local, s_t, e_t)
                if os.environ.get('ORCH_TEST_RERAISE') == '1':
                    try:
                        print(f"DEBUG_TEST window s='{s_str}' e='{e_str}' within={within}")
                    except Exception:
                        pass

                delivery_links = link_extraction.extract_provider_links_from_text(combined_text_for_detection or '')
                
                # R2 Transfer: enrich delivery_links with R2 URLs if enabled
                try:
                    from services import R2TransferService
                    r2_service = R2TransferService.get_instance()
                    
                    if r2_service.is_enabled() and delivery_links:
                        for link_item in delivery_links:
                            if not isinstance(link_item, dict):
                                continue
                            
                            source_url = link_item.get('raw_url')
                            provider = link_item.get('provider')
                            if source_url:
                                fallback_raw_url = source_url
                                fallback_direct_url = link_item.get('direct_url') or source_url
                                link_item['raw_url'] = source_url
                                if not link_item.get('direct_url'):
                                    link_item['direct_url'] = fallback_direct_url
                            
                            if source_url and provider:
                                try:
                                    normalized_source_url = r2_service.normalize_source_url(
                                        source_url, provider
                                    )
                                    remote_fetch_timeout = 15
                                    if (
                                        provider == "dropbox"
                                        and "/scl/fo/" in normalized_source_url.lower()
                                    ):
                                        remote_fetch_timeout = 120

                                    r2_result = None
                                    try:
                                        r2_result = r2_service.request_remote_fetch(
                                            source_url=normalized_source_url,
                                            provider=provider,
                                            email_id=email_id,
                                            timeout=remote_fetch_timeout
                                        )
                                    except Exception:
                                        r2_result = None

                                    r2_url = None
                                    original_filename = None
                                    if isinstance(r2_result, tuple) and len(r2_result) == 2:
                                        r2_url, original_filename = r2_result
                                    elif r2_result is None:
                                        r2_url = None

                                    if r2_url:
                                        link_item['r2_url'] = r2_url
                                        if isinstance(original_filename, str) and original_filename.strip():
                                            link_item['original_filename'] = original_filename.strip()
                                        # Persister la paire source/R2
                                        r2_service.persist_link_pair(
                                            source_url=normalized_source_url,
                                            r2_url=r2_url,
                                            provider=provider,
                                            original_filename=original_filename,
                                        )
                                        logger.info(
                                            "R2_TRANSFER: Successfully transferred %s link to R2 for email %s",
                                            provider,
                                            email_id
                                        )
                                    else:
                                        logger.warning(
                                            "R2 transfer failed, falling back to source url"
                                        )
                                        if source_url:
                                            link_item['raw_url'] = fallback_raw_url
                                            link_item['direct_url'] = fallback_direct_url
                                except Exception:
                                    logger.warning(
                                        "R2 transfer failed, falling back to source url"
                                    )
                                    if source_url:
                                        link_item['raw_url'] = fallback_raw_url
                                        link_item['direct_url'] = fallback_direct_url
                                    # Continue avec le lien source original
                except Exception as r2_service_ex:
                    logger.debug("R2_TRANSFER: Service unavailable or disabled: %s", str(r2_service_ex))
                
                # Group dedup check for custom webhook
                group_id = ar.generate_subject_group_id(subject or '')
                if ar.is_subject_group_processed(group_id):
                    logger.info("DEDUP_GROUP: Skipping email %s (group %s processed)", email_id, group_id)
                    ar.mark_email_id_as_processed_redis(email_id)
                    ar.mark_email_as_read_imap(mail, num)
                    try:
                        logger.info(
                            "IGNORED: Email %s ignored due to subject-group dedup (group=%s)",
                            email_id,
                            group_id,
                        )
                    except Exception:
                        pass
                    continue

                # Infer a detector for PHP receiver (Gmail sending path)
                if os.environ.get('ORCH_TEST_RERAISE') == '1':
                    try:
                        print("DEBUG_TEST entering detector inference")
                    except Exception:
                        pass
                detector_val = None
                delivery_time_val = None  # for recadrage
                desabo_is_urgent = False  # for DESABO
                try:
                    # Obtain pattern_matching each time, preferring a monkeypatched object on this module
                    pm_mod = globals().get('pattern_matching')
                    if pm_mod is None or not hasattr(pm_mod, 'check_media_solution_pattern'):
                        from email_processing import pattern_matching as _pm
                        pm_mod = _pm
                    if os.environ.get('ORCH_TEST_RERAISE') == '1':
                        try:
                            print(f"DEBUG_TEST pm_mod={type(pm_mod)} has_ms={hasattr(pm_mod,'check_media_solution_pattern')} has_des={hasattr(pm_mod,'check_desabo_conditions')}")
                        except Exception:
                            pass
                    # Prefer Media Solution if matched
                    ms_res = pm_mod.check_media_solution_pattern(
                        subject or '', combined_text_for_detection or '', ar.TZ_FOR_POLLING, logger
                    )
                    if isinstance(ms_res, dict) and bool(ms_res.get('matches')):
                        detector_val = 'recadrage'
                        try:
                            delivery_time_val = ms_res.get('delivery_time')
                        except Exception:
                            delivery_time_val = None
                    else:
                        # Fallback: DESABO detector if base conditions are met
                        des_res = pm_mod.check_desabo_conditions(
                            subject or '', combined_text_for_detection or '', logger
                        )
                        if os.environ.get('ORCH_TEST_RERAISE') == '1':
                            try:
                                print(f"DEBUG_TEST ms_res={ms_res} des_res={des_res}")
                            except Exception:
                                pass
                        if isinstance(des_res, dict) and bool(des_res.get('matches')):
                            # Optionally require a Dropbox request hint if provided by helper
                            if des_res.get('has_dropbox_request') is True:
                                detector_val = 'desabonnement_journee_tarifs'
                            else:
                                detector_val = 'desabonnement_journee_tarifs'
                            try:
                                desabo_is_urgent = bool(des_res.get('is_urgent'))
                            except Exception:
                                desabo_is_urgent = False
                except Exception as _det_ex:
                    try:
                        logger.debug("DETECTOR_DEBUG: inference error for email %s: %s", email_id, _det_ex)
                    except Exception:
                        pass

                try:
                    logger.info(
                        "CUSTOM_WEBHOOK: detector inferred for email %s: %s", email_id, detector_val or 'none'
                    )
                    if detector_val == 'recadrage':
                        logger.info(
                            "CUSTOM_WEBHOOK: recadrage delivery_time for email %s: %s", email_id, delivery_time_val or 'none'
                        )
                except Exception:
                    pass

                # Test-only: surface decision inputs
                if os.environ.get('ORCH_TEST_RERAISE') == '1':
                    try:
                        print(
                            "DEBUG_TEST within=%s detector=%s start='%s' end='%s' subj='%s'"
                            % (
                                within,
                                detector_val,
                                s_str,
                                e_str,
                                mask_sensitive_data(subject or "", "subject"),
                            )
                        )
                    except Exception:
                        pass

                # DESABO: bypass window, RECADRAGE: skip sending
                if not within:
                    tw_start_str = (s_str or 'unset')
                    tw_end_str = (e_str or 'unset')
                    if detector_val == 'desabonnement_journee_tarifs':
                        if desabo_is_urgent:
                            logger.info(
                                "WEBHOOK_GLOBAL_TIME_WINDOW: Outside window for email %s and detector=DESABO but URGENT -> skipping webhook (now=%s, window=%s-%s)",
                                email_id,
                                now_local.strftime('%H:%M'),
                                tw_start_str,
                                tw_end_str,
                            )
                            try:
                                logger.info("IGNORED: DESABO urgent skipped outside window (email %s)", email_id)
                            except Exception:
                                pass
                            continue
                        else:
                            logger.info(
                                "WEBHOOK_GLOBAL_TIME_WINDOW: Outside window for email %s but detector=DESABO (non-urgent) -> bypassing window and proceeding to send (now=%s, window=%s-%s)",
                                email_id,
                                now_local.strftime('%H:%M'),
                                tw_start_str,
                                tw_end_str,
                            )
                            # Fall through to payload/send below
                    elif detector_val == 'recadrage':
                        logger.info(
                            "WEBHOOK_GLOBAL_TIME_WINDOW: Outside window for email %s and detector=RECADRAGE -> skipping webhook AND marking read/processed (now=%s, window=%s-%s)",
                            email_id,
                            now_local.strftime('%H:%M'),
                            tw_start_str,
                            tw_end_str,
                        )
                        try:
                            ar.mark_email_id_as_processed_redis(email_id)
                            ar.mark_email_as_read_imap(mail, num)
                            logger.info("IGNORED: RECADRAGE skipped outside window and marked processed (email %s)", email_id)
                        except Exception:
                            pass
                        continue
                    else:
                        logger.info(
                            "WEBHOOK_GLOBAL_TIME_WINDOW: Outside dedicated window for email %s (now=%s, window=%s-%s). Skipping.",
                            email_id,
                            now_local.strftime('%H:%M'),
                            tw_start_str,
                            tw_end_str,
                        )
                        try:
                            logger.info("IGNORED: Webhook skipped due to dedicated time window (email %s)", email_id)
                        except Exception:
                            pass
                        continue

                # Required by validator: sender_address, subject, receivedDateTime
                # Provide email_content to avoid server-side IMAP search and allow URL extraction.
                preview = (combined_text_for_detection or "")[:200]
                # Load current global time window strings and compute start payload logic
                # IMPORTANT: Prefer the same source used for the bypass decision (s_str/e_str)
                # to avoid desynchronization with config overrides. Fall back to
                # config.webhook_time_window.get_time_window_info() only if needed.
                try:
                    # s_str/e_str were loaded earlier via _load_webhook_global_time_window()
                    _pref_start = (s_str or '').strip()
                    _pref_end = (e_str or '').strip()
                    if not _pref_start or not _pref_end:
                        tw_info = _w_tw.get_time_window_info()
                        _pref_start = _pref_start or (tw_info.get('start') or '').strip()
                        _pref_end = _pref_end or (tw_info.get('end') or '').strip()
                    tw_start_str = _pref_start or None
                    tw_end_str = _pref_end or None
                except Exception:
                    tw_start_str = None
                    tw_end_str = None

                # Determine start payload:
                # - If within window: "maintenant"
                # - If before window start AND detector is DESABO non-urgent (bypass case): use configured start string
                # - Else (after window end or window inactive): leave unset (PHP defaults to 'maintenant')
                start_payload_val = None
                try:
                    if tw_start_str and tw_end_str:
                        from utils.time_helpers import parse_time_hhmm as _parse_hhmm
                        start_t = _parse_hhmm(tw_start_str)
                        end_t = _parse_hhmm(tw_end_str)
                        if start_t and end_t:
                            # Reuse the already computed local time and within decision
                            now_t = now_local.timetz().replace(tzinfo=None)
                            if within:
                                start_payload_val = "maintenant"
                            else:
                                # Before window start: for DESABO non-urgent bypass, fix start to configured start
                                if (
                                    detector_val == 'desabonnement_journee_tarifs'
                                    and not desabo_is_urgent
                                    and now_t < start_t
                                ):
                                    start_payload_val = tw_start_str
                except Exception:
                    start_payload_val = None
                payload_for_webhook = {
                    "microsoft_graph_email_id": email_id,  # reuse our ID for compatibility
                    "subject": subject or "",
                    "receivedDateTime": date_raw or "",  # raw Date header (RFC 2822)
                    "sender_address": from_raw or sender_addr,
                    "bodyPreview": preview,
                    "email_content": combined_text_for_detection or "",
                }
                # Attach window strings if configured
                try:
                    if start_payload_val is not None:
                        payload_for_webhook["webhooks_time_start"] = start_payload_val
                    if tw_end_str is not None:
                        payload_for_webhook["webhooks_time_end"] = tw_end_str
                except Exception:
                    pass
                # Add fields used by PHP handler for detector-based Gmail sending
                try:
                    if detector_val:
                        payload_for_webhook["detector"] = detector_val
                    # Provide delivery_time for recadrage flow if available
                    if detector_val == 'recadrage' and delivery_time_val:
                        payload_for_webhook["delivery_time"] = delivery_time_val
                    # Provide a clean sender email explicitly
                    payload_for_webhook["sender_email"] = sender_addr or ar.extract_sender_email(from_raw)
                except Exception:
                    pass

                routing_webhook_url = None
                routing_stop_processing = False
                routing_priority = None
                try:
                    routing_payload = _get_routing_rules_payload()
                    routing_rules = routing_payload.get("rules") if isinstance(routing_payload, dict) else []
                    matched_rule = _find_matching_routing_rule(
                        routing_rules,
                        sender=sender_addr,
                        subject=subject or "",
                        body=combined_text_for_detection or "",
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
                                if isinstance(priority_value, str) and priority_value.strip():
                                    routing_priority = priority_value.strip().lower()
                            else:
                                try:
                                    logger.warning(
                                        "ROUTING_RULES: Rule %s missing webhook_url; skipping",
                                        matched_rule.get("id", "unknown"),
                                    )
                                except Exception:
                                    pass
                        if routing_webhook_url:
                            payload_for_webhook["routing_rule"] = {
                                "id": matched_rule.get("id"),
                                "name": matched_rule.get("name"),
                                "priority": routing_priority or "normal",
                            }
                except Exception as routing_exc:
                    try:
                        logger.debug("ROUTING_RULES: Evaluation error: %s", routing_exc)
                    except Exception:
                        pass

                # Execute custom webhook flow (handles retries, logging, read marking on success)
                if routing_webhook_url:
                    cont = send_custom_webhook_flow(
                        email_id=email_id,
                        subject=subject or '',
                        payload_for_webhook=payload_for_webhook,
                        delivery_links=delivery_links or [],
                        webhook_url=routing_webhook_url,
                        webhook_ssl_verify=True,
                        allow_without_links=bool(getattr(ar, 'ALLOW_CUSTOM_WEBHOOK_WITHOUT_LINKS', False)),
                        processing_prefs=getattr(ar, 'PROCESSING_PREFS', {}),
                        # Use runtime helpers from app_render so tests can monkeypatch them
                        rate_limit_allow_send=getattr(ar, '_rate_limit_allow_send'),
                        record_send_event=getattr(ar, '_record_send_event'),
                        append_webhook_log=getattr(ar, '_append_webhook_log'),
                        mark_email_id_as_processed_redis=ar.mark_email_id_as_processed_redis,
                        mark_email_as_read_imap=ar.mark_email_as_read_imap,
                        mail=mail,
                        email_num=num,
                        urlparse=None,
                        requests=__import__('requests'),
                        time=__import__('time'),
                        logger=logger,
                    )
                    # Best-effort: if the flow returned False, an attempt was made (success or handled error)
                    if cont is False:
                        triggered_count += 1
                    if routing_stop_processing:
                        continue

                should_send_default = True
                if routing_webhook_url and routing_webhook_url == ar.WEBHOOK_URL:
                    should_send_default = False
                if should_send_default:
                    cont = send_custom_webhook_flow(
                        email_id=email_id,
                        subject=subject or '',
                        payload_for_webhook=payload_for_webhook,
                        delivery_links=delivery_links or [],
                        webhook_url=ar.WEBHOOK_URL,
                        webhook_ssl_verify=True,
                        allow_without_links=bool(getattr(ar, 'ALLOW_CUSTOM_WEBHOOK_WITHOUT_LINKS', False)),
                        processing_prefs=getattr(ar, 'PROCESSING_PREFS', {}),
                        # Use runtime helpers from app_render so tests can monkeypatch them
                        rate_limit_allow_send=getattr(ar, '_rate_limit_allow_send'),
                        record_send_event=getattr(ar, '_record_send_event'),
                        append_webhook_log=getattr(ar, '_append_webhook_log'),
                        mark_email_id_as_processed_redis=ar.mark_email_id_as_processed_redis,
                        mark_email_as_read_imap=ar.mark_email_as_read_imap,
                        mail=mail,
                        email_num=num,
                        urlparse=None,
                        requests=__import__('requests'),
                        time=__import__('time'),
                        logger=logger,
                    )
                    # Best-effort: if the flow returned False, an attempt was made (success or handled error)
                    if cont is False:
                        triggered_count += 1

            except Exception as e_one:
                # In tests, allow re-raising to surface the exact failure location
                if os.environ.get('ORCH_TEST_RERAISE') == '1':
                    raise
                logger.error("POLLER: Exception while processing message %s: %s", num, e_one)
                # Keep going for other emails
                continue

        return triggered_count
    finally:
        # Ensure IMAP is closed
        try:
            ar.close_imap_connection(mail)
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


def handle_presence_route(
    *,
    subject: str,
    full_email_content: str,
    email_id: str,
    sender_raw: str,
    tz_for_polling,
    webhooks_time_start_str,
    webhooks_time_end_str,
    presence_flag,
    presence_true_url,
    presence_false_url,
    is_within_time_window_local,
    extract_sender_email,
    send_makecom_webhook,
    logger,
) -> bool:
    return False


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
) -> bool:
    """Execute the custom webhook send flow. Returns True if caller should continue to next email.

    This function performs:
    - Skip if no links and policy forbids sending without links (logs + mark processed)
    - Rate limiting check
    - Retries with timeout
    - Dashboard logging for success/error
    - Mark processed + mark as read upon success
    """
    try:
        if (not delivery_links) and (not allow_without_links):
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
            return True
    except Exception:
        pass

    # Rate limit
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

    retries = int(processing_prefs.get('retry_count') or 0)
    delay = int(processing_prefs.get('retry_delay_sec') or 0)
    timeout_sec = int(processing_prefs.get('webhook_timeout_sec') or 30)

    last_exc = None
    webhook_response = None
    try:
        logger.debug(
            "CUSTOM_WEBHOOK_DEBUG: Preparing to send custom webhook for email %s to %s (timeout=%ss, retries=%d, delay=%ds)",
            email_id, webhook_url, timeout_sec, retries, delay,
        )
    except Exception:
        pass

    for attempt in range(retries + 1):
        try:
            payload_to_send = dict(payload_for_webhook) if isinstance(payload_for_webhook, dict) else {
                "microsoft_graph_email_id": email_id,
                "subject": subject or "",
            }
            if delivery_links:
                try:
                    payload_to_send["delivery_links"] = delivery_links
                except Exception:
                    # Defensive: do not fail send due to payload mutation
                    pass
            webhook_response = requests.post(
                webhook_url,
                json=payload_to_send,
                headers={'Content-Type': 'application/json'},
                timeout=timeout_sec,
                verify=webhook_ssl_verify,
            )
            break
        except Exception as e_req:
            last_exc = e_req
            if attempt < retries and delay > 0:
                time.sleep(delay)
    # record attempt for rate-limit window
    record_send_event()
    if webhook_response is None:
        raise last_exc or Exception("Webhook request failed")

    # Response handling
    if webhook_response.status_code == 200:
        try:
            response_data = webhook_response.json() if webhook_response.content else {}
        except Exception:
            response_data = {}
        if response_data.get('success', False):
            logger.info("POLLER: Webhook triggered successfully for email %s.", email_id)
            append_webhook_log({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "type": "custom",
                "email_id": email_id,
                "status": "success",
                "status_code": webhook_response.status_code,
                "webhook_url": (webhook_url[:50] + "...") if len(webhook_url) > 50 else webhook_url,
                "subject": (subject[:100] if subject else None),
            })
            if mark_email_id_as_processed_redis(email_id):
                # caller expects to increment its counters; here we only mark read
                mark_email_as_read_imap(mail, email_num)
            return False
        else:
            logger.error(
                "POLLER: Webhook processing failed for email %s. Response: %s",
                email_id,
                (response_data.get('message', 'Unknown error')),
            )
            append_webhook_log({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "type": "custom",
                "email_id": email_id,
                "status": "error",
                "status_code": webhook_response.status_code,
                "error_message": (response_data.get('message', 'Unknown error'))[:200],
                "webhook_url": (webhook_url[:50] + "...") if len(webhook_url) > 50 else webhook_url,
                "subject": (subject[:100] if subject else None),
            })
            return False
    else:
        logger.error(
            "POLLER: Webhook call FAILED for email %s. Status: %s, Response: %s",
            email_id,
            webhook_response.status_code,
            webhook_response.text[:200],
        )
        append_webhook_log({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": "custom",
            "email_id": email_id,
            "status": "error",
            "status_code": webhook_response.status_code,
            "error_message": webhook_response.text[:200] if webhook_response.text else "Unknown error",
            "webhook_url": (webhook_url[:50] + "...") if len(webhook_url) > 50 else webhook_url,
            "subject": (subject[:100] if subject else None),
        })
        return False
