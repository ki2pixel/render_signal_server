"""
email_processing.orchestrator
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Minimally centralizes orchestration calls for the email polling workflow.
Step 4E-a: wrapper that delegates to the legacy implementation in app_render.py
without moving the function body yet. This enables future extractions to
happen behind this stable facade.
"""
from __future__ import annotations

from typing import Optional
from datetime import datetime, timezone

# NOTE: We import lazily inside functions to avoid circular imports at module load


def check_new_emails_and_trigger_webhook():
    """Delegate to legacy implementation if available, otherwise no-op safely.

    Returns:
        int: number of webhooks triggered (0 on fallback)
    """
    try:
        # Local import to avoid circular dependency at import time
        from app_render import _legacy_check_new_emails_and_trigger_webhook as _legacy_check
        return _legacy_check()
    except Exception as _e_legacy:
        # Fallback: avoid crashing the polling thread if legacy impl is absent
        try:
            from app_render import app as _app
            _app.logger.error(
                "ORCHESTRATOR: Legacy implementation not found; skipping cycle (returns 0). Error: %s",
                _e_legacy,
            )
        except Exception:
            pass
        return 0


def compute_desabo_time_window(
    *,
    now_local,
    webhooks_time_start,
    webhooks_time_start_str: Optional[str],
    webhooks_time_end_str: Optional[str],
    within_window: bool,
):
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
    webhooks_time_start_str: Optional[str],
    webhooks_time_end_str: Optional[str],
    presence_flag: bool,
    presence_true_url: Optional[str],
    presence_false_url: Optional[str],
    is_within_time_window_local,
    extract_sender_email,
    send_makecom_webhook,
    logger,
) -> bool:
    """Detect 'samedi' presence emails and optionally send Make.com webhook.

    Returns:
        bool: presence_routed (engage exclusivity at caller side if True)
    """
    try:
        def _normalize_no_accents_lower(s: str) -> str:
            try:
                import unicodedata
                if not s:
                    return ""
                nfkd = unicodedata.normalize('NFD', s)
                no_accents = ''.join(ch for ch in nfkd if not unicodedata.combining(ch))
                return no_accents.lower()
            except Exception:
                return (s or "").lower()

        norm_subject = _normalize_no_accents_lower(subject)
        norm_body = _normalize_no_accents_lower(full_email_content)
        contains_samedi = ("samedi" in norm_subject) and ("samedi" in norm_body)

        if not contains_samedi:
            return False

        try:
            now_check = datetime.now(tz_for_polling)
            logger.debug(
                "PRESENCE_DEBUG: Email %s - contains_samedi=True, weekday=%d",
                email_id,
                now_check.weekday(),
            )
        except Exception:
            pass

        now_local = datetime.now(tz_for_polling)
        is_friday = now_local.weekday() == 4
        is_thursday = now_local.weekday() == 3
        if not (is_friday or is_thursday):
            logger.info(
                "PRESENCE: 'samedi' detected for email %s but today is not Thursday or Friday (weekday=%d). Presence webhooks are restricted to Thursdays and Fridays. Skipping.",
                email_id,
                now_local.weekday(),
            )
            return False

        if not is_within_time_window_local(now_local):
            logger.info(
                "PRESENCE: Time window not satisfied for email %s (now=%s, window=%s-%s). Skipping.",
                email_id,
                now_local.strftime('%H:%M'),
                webhooks_time_start_str or 'unset',
                webhooks_time_end_str or 'unset',
            )
            return False

        presence_url = presence_true_url if presence_flag else presence_false_url
        # Engage exclusivity even if URL not configured (caller will act on True)
        if presence_url:
            logger.info(
                "PRESENCE: 'samedi' detected with valid day/time window for email %s. PRESENCE=%s. Sending to dedicated Make webhook.",
                email_id,
                presence_flag,
            )
            presence_sender_email = extract_sender_email(sender_raw)
            send_ok = send_makecom_webhook(
                subject=subject,
                delivery_time=None,
                sender_email=presence_sender_email,
                email_id=email_id,
                override_webhook_url=presence_url,
                extra_payload={
                    "presence": presence_flag,
                    "detector": "samedi_presence",
                    "webhooks_time_start": webhooks_time_start_str or None,
                    "webhooks_time_end": webhooks_time_end_str or None,
                },
            )
            if send_ok:
                logger.info("PRESENCE: Make.com webhook (presence) sent successfully for email %s", email_id)
            else:
                logger.error("PRESENCE: Make.com webhook (presence) failed for email %s", email_id)
        else:
            logger.warning(
                "PRESENCE: 'samedi' detected with valid day/time window but PRESENCE_*_MAKE_WEBHOOK_URL not configured. Exclusivity applied; skipping presence webhook call and custom webhook."
            )
        return True
    except Exception as e_presence:
        logger.error("PRESENCE: Exception during samedi presence handling for email %s: %s", email_id, e_presence)
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


def handle_media_solution_route(
    *,
    subject: str,
    full_email_content: str,
    email_id: str,
    processing_prefs: dict,
    tz_for_polling,
    check_media_solution_pattern,
    extract_sender_email,
    sender_raw: str,
    send_makecom_webhook,
    mark_subject_group_processed,
    subject_group_id: str | None,
    logger,
) -> bool:
    """Handle Media Solution detection and Make.com send. Returns True if sent successfully."""
    try:
        pattern_result = check_media_solution_pattern(subject, full_email_content, tz_for_polling, logger)
        if not pattern_result.get('matches'):
            return False
        logger.info("POLLER: Email %s matches Média Solution pattern", email_id)

        sender_email = extract_sender_email(sender_raw)
        # Per-webhook exclude list for RECADRAGE
        try:
            ex_rec = processing_prefs.get('exclude_keywords_recadrage') or []
            if ex_rec:
                from utils.text_helpers import normalize_no_accents_lower_trim as _norm
                norm_subj2 = _norm(subject or "")
                nb = _norm(full_email_content or "")
                if any((kw or '').strip().lower() in norm_subj2 or (kw or '').strip().lower() in nb for kw in ex_rec):
                    logger.info("EXCLUDE_KEYWORD: RECADRAGE skipped for %s (matched per-webhook exclude)", email_id)
                    return False
        except Exception as _ex2:
            logger.debug("EXCLUDE_KEYWORD: error evaluating recadrage excludes: %s", _ex2)

        makecom_success = send_makecom_webhook(
            subject=subject,
            delivery_time=pattern_result.get('delivery_time'),
            sender_email=sender_email,
            email_id=email_id,
            override_webhook_url=None,
            extra_payload=None,
        )
        if makecom_success:
            try:
                if subject_group_id:
                    mark_subject_group_processed(subject_group_id)
            except Exception:
                pass
        return makecom_success
    except Exception as e:
        logger.error("MEDIA_SOLUTION: Exception during handling for email %s: %s", email_id, e)
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
    # Skip if no links and policy forbids
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
                "error": "No delivery links detected; skipping per config",
                "target_url": (webhook_url[:50] + "...") if len(webhook_url) > 50 else webhook_url,
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
                "error": "Rate limit exceeded",
                "target_url": (webhook_url[:50] + "...") if len(webhook_url) > 50 else webhook_url,
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
            webhook_response = requests.post(
                webhook_url,
                json=payload_for_webhook,
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
            # Malformed or non-JSON body; treat as unsuccessful processing
            response_data = {}
        if response_data.get('success', False):
            logger.info("POLLER: Webhook triggered successfully for email %s.", email_id)
            append_webhook_log({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "type": "custom",
                "email_id": email_id,
                "status": "success",
                "status_code": webhook_response.status_code,
                "target_url": (webhook_url[:50] + "...") if len(webhook_url) > 50 else webhook_url,
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
                "error": (response_data.get('message', 'Unknown error'))[:200],
                "target_url": (webhook_url[:50] + "...") if len(webhook_url) > 50 else webhook_url,
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
            "error": webhook_response.text[:200] if webhook_response.text else "Unknown error",
            "target_url": (webhook_url[:50] + "...") if len(webhook_url) > 50 else webhook_url,
            "subject": (subject[:100] if subject else None),
        })
        return False
