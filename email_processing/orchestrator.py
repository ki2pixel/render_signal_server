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


def check_new_emails_and_trigger_webhook() -> int:
    """Execute one IMAP polling cycle and trigger webhooks when appropriate.

    Returns the number of triggered actions (best-effort count).

    Implementation notes:
    - Imports are inside the function to avoid circular dependencies at import time.
    - Uses helpers exposed by app_render and modules under email_processing/.
    - Defensive logging; never raises to the background loop.
    """
    # Compatibility layer: if a legacy implementation exists in app_render,
    # delegate to it (tests may monkeypatch this symbol to validate delegation).
    try:
        from app_render import _legacy_check_new_emails_and_trigger_webhook as _legacy_impl  # type: ignore[attr-defined]
        if _legacy_impl:
            return int(_legacy_impl())
    except Exception:
        # If legacy symbol not present or unusable, proceed with native flow
        pass
    # Lazy imports to avoid cycles
    try:
        import imaplib
        from email import message_from_bytes
    except Exception:
        # If stdlib imports fail, nothing we can do
        return 0

    try:
        # Pull runtime components from app_render (configured at app startup)
        from app_render import (
            app as _app,
            create_imap_connection,
            close_imap_connection,
            extract_sender_email,
            decode_email_header,
            mark_email_as_read_imap,
            send_makecom_webhook,
            generate_subject_group_id,
            is_subject_group_processed,
            mark_subject_group_processed,
            is_email_id_processed_redis,
            mark_email_id_as_processed_redis,
            _rate_limit_allow_send,
            _record_send_event,
            _append_webhook_log,
            WEBHOOK_URL,
            ALLOW_CUSTOM_WEBHOOK_WITHOUT_LINKS,
            PROCESSING_PREFS,
            SENDER_LIST_FOR_POLLING,
            TZ_FOR_POLLING,
        )
        # Local modules
        from email_processing import imap_client
        from email_processing import pattern_matching
        from email_processing import payloads
        from email_processing import link_extraction
        from config import webhook_time_window as _w_tw
        from config.settings import AUTOREPONDEUR_MAKE_WEBHOOK_URL
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

    logger = getattr(_app, 'logger', None)
    if not logger:
        return 0

    # Establish IMAP connection
    mail = create_imap_connection()
    if not mail:
        logger.error("POLLER: Email polling cycle aborted: IMAP connection failed.")
        return 0

    triggered_count = 0
    try:
        # Select INBOX
        try:
            status, _ = mail.select('INBOX')
            if status != 'OK':
                logger.error("IMAP: Unable to select INBOX (status=%s)", status)
                return 0
        except Exception as e_sel:
            logger.error("IMAP: Exception selecting INBOX: %s", e_sel)
            return 0

        # Search unseen messages
        try:
            status, data = mail.search(None, 'UNSEEN')
            if status != 'OK':
                logger.error("IMAP: search UNSEEN failed (status=%s)", status)
                return 0
            email_nums = data[0].split() if data and data[0] else []
        except Exception as e_search:
            logger.error("IMAP: Exception during search UNSEEN: %s", e_search)
            return 0

        # Helper: is within Make webhook window (for presence route)
        def _is_within_time_window_local(now_local):
            try:
                return _w_tw.is_within_global_time_window(now_local)
            except Exception:
                return True

        # Process each unseen message
        for num in email_nums:
            try:
                # Fetch full message
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
                subject = decode_email_header(subj_raw)
                sender_addr = extract_sender_email(from_raw).lower()
                # Observability: log when an email has been read and parsed (no sensitive content)
                try:
                    logger.info(
                        "POLLER: Email read from IMAP: num=%s, subject='%s', sender='%s'",
                        num.decode() if isinstance(num, bytes) else str(num),
                        subject or 'N/A',
                        sender_addr or 'N/A',
                    )
                except Exception:
                    pass

                # Filter by allowed senders
                try:
                    allowed = [s.lower() for s in (SENDER_LIST_FOR_POLLING or [])]
                except Exception:
                    allowed = []
                if allowed and sender_addr not in allowed:
                    logger.info("POLLER: Skipping email %s (sender %s not in allowlist)", num.decode() if isinstance(num, bytes) else str(num), sender_addr)
                    try:
                        logger.info(
                            "IGNORED: Sender not in allowlist for email %s (sender=%s)",
                            num.decode() if isinstance(num, bytes) else str(num),
                            sender_addr,
                        )
                    except Exception:
                        pass
                    continue

                # Build a simple headers dict to compute email_id
                headers_map = {
                    'Message-ID': msg.get('Message-ID', ''),
                    'Subject': subject or '',
                    'Date': date_raw or '',
                }
                email_id = imap_client.generate_email_id(headers_map)
                if is_email_id_processed_redis(email_id):
                    logger.info("DEDUP_EMAIL: Skipping already processed email_id=%s", email_id)
                    try:
                        logger.info("IGNORED: Email %s ignored due to email-id dedup", email_id)
                    except Exception:
                        pass
                    continue

                # Extract text/plain and text/html content for pattern checks and link extraction
                full_text = ""
                html_text = ""
                try:
                    if msg.is_multipart():
                        for part in msg.walk():
                            ctype = part.get_content_type()
                            disp = (part.get('Content-Disposition') or '').lower()
                            if 'attachment' in disp:
                                continue
                            payload = part.get_payload(decode=True) or b''
                            decoded = payload.decode(part.get_content_charset() or 'utf-8', errors='ignore')
                            if ctype == 'text/plain':
                                full_text += decoded
                            elif ctype == 'text/html':
                                html_text += decoded
                    else:
                        payload = msg.get_payload(decode=True) or b''
                        decoded = payload.decode(msg.get_content_charset() or 'utf-8', errors='ignore')
                        # Fallback: if single-part, treat as plain, but keep HTML if content-type hints it
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
                except Exception:
                    combined_text_for_detection = full_text or ''

                # 1) Presence "samedi" route (exclusive if matched)
                routed_presence = handle_presence_route(
                    subject=subject or '',
                    full_email_content=combined_text_for_detection or '',
                    email_id=email_id,
                    sender_raw=from_raw,
                    tz_for_polling=TZ_FOR_POLLING,
                    webhooks_time_start_str=None,
                    webhooks_time_end_str=None,
                    presence_flag=False if _app.config.get('PRESENCE_FLAG') is None else _app.config.get('PRESENCE_FLAG'),
                    presence_true_url=_app.config.get('PRESENCE_TRUE_MAKE_WEBHOOK_URL'),
                    presence_false_url=_app.config.get('PRESENCE_FALSE_MAKE_WEBHOOK_URL'),
                    is_within_time_window_local=_is_within_time_window_local,
                    extract_sender_email=extract_sender_email,
                    send_makecom_webhook=send_makecom_webhook,
                    logger=logger,
                )
                if routed_presence:
                    # Presence is exclusive; mark processed and continue
                    mark_email_id_as_processed_redis(email_id)
                    mark_email_as_read_imap(mail, num)
                    triggered_count += 1
                    continue

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

                # 4) Custom webhook flow (if WEBHOOK_URL configured)
                if not WEBHOOK_URL:
                    logger.info("POLLER: WEBHOOK_URL not configured; skipping custom webhook for %s", email_id)
                    continue

                delivery_links = link_extraction.extract_provider_links_from_text(combined_text_for_detection or '')
                # Group dedup check for custom webhook
                group_id = generate_subject_group_id(subject or '')
                if is_subject_group_processed(group_id):
                    logger.info("DEDUP_GROUP: Skipping email %s (group %s processed)", email_id, group_id)
                    mark_email_id_as_processed_redis(email_id)
                    mark_email_as_read_imap(mail, num)
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
                detector_val = None
                try:
                    # Prefer Media Solution if matched
                    ms_res = pattern_matching.check_media_solution_pattern(
                        subject or '', combined_text_for_detection or '', TZ_FOR_POLLING, logger
                    )
                    if isinstance(ms_res, dict) and bool(ms_res.get('matches')):
                        detector_val = 'recadrage'
                    else:
                        # Fallback: DESABO detector if base conditions are met
                        des_res = pattern_matching.check_desabo_conditions(
                            subject or '', combined_text_for_detection or '', logger
                        )
                        if isinstance(des_res, dict) and bool(des_res.get('matches')):
                            # Optionally require a Dropbox request hint if provided by helper
                            if des_res.get('has_dropbox_request') is True:
                                detector_val = 'desabonnement_journee_tarifs'
                            else:
                                detector_val = 'desabonnement_journee_tarifs'
                except Exception as _det_ex:
                    try:
                        logger.debug("DETECTOR_DEBUG: inference error for email %s: %s", email_id, _det_ex)
                    except Exception:
                        pass

                try:
                    logger.info(
                        "CUSTOM_WEBHOOK: detector inferred for email %s: %s", email_id, detector_val or 'none'
                    )
                except Exception:
                    pass

                # Build payload expected by PHP endpoint (see deployment/public_html/index.php)
                # Required by validator: sender_address, subject, receivedDateTime
                # Provide email_content to avoid server-side IMAP search and allow URL extraction.
                preview = (combined_text_for_detection or "")[:200]
                # Load current global time window strings and compute start payload logic
                try:
                    tw_info = _w_tw.get_time_window_info()
                    tw_start_str = (tw_info.get('start') or '').strip() or None
                    tw_end_str = (tw_info.get('end') or '').strip() or None
                except Exception:
                    tw_start_str = None
                    tw_end_str = None
                # Determine start payload:
                # - If within window: "maintenant"
                # - If before window start: configured start string
                # - Else (after window end or window inactive): leave unset (PHP defaults to 'maintenant')
                start_payload_val = None
                try:
                    if tw_start_str and tw_end_str:
                        from utils.time_helpers import parse_time_hhmm as _parse_hhmm
                        start_t = _parse_hhmm(tw_start_str)
                        end_t = _parse_hhmm(tw_end_str)
                        if start_t and end_t:
                            now_local = datetime.now(TZ_FOR_POLLING)
                            now_t = now_local.timetz().replace(tzinfo=None)
                            # Compare naive times (same local TZ day context)
                            if start_t <= now_t <= end_t:
                                start_payload_val = "maintenant"
                            elif now_t < start_t:
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
                    # Provide a clean sender email explicitly
                    payload_for_webhook["sender_email"] = sender_addr or extract_sender_email(from_raw)
                except Exception:
                    pass

                # Execute custom webhook flow (handles retries, logging, read marking on success)
                cont = send_custom_webhook_flow(
                    email_id=email_id,
                    subject=subject or '',
                    payload_for_webhook=payload_for_webhook,
                    delivery_links=delivery_links or [],
                    webhook_url=WEBHOOK_URL,
                    webhook_ssl_verify=True,
                    allow_without_links=bool(ALLOW_CUSTOM_WEBHOOK_WITHOUT_LINKS),
                    processing_prefs=PROCESSING_PREFS,
                    rate_limit_allow_send=_rate_limit_allow_send,
                    record_send_event=_record_send_event,
                    append_webhook_log=_append_webhook_log,
                    mark_email_id_as_processed_redis=mark_email_id_as_processed_redis,
                    mark_email_as_read_imap=mark_email_as_read_imap,
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
                logger.error("POLLER: Exception while processing message %s: %s", num, e_one)
                # Keep going for other emails
                continue

        return triggered_count
    finally:
        # Ensure IMAP is closed
        try:
            close_imap_connection(mail)
        except Exception:
            pass


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
            try:
                logger.info("IGNORED: Presence webhook skipped due to time window (email %s)", email_id)
            except Exception:
                pass
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

        # Extract delivery links from email content to include in webhook payload.
        # Note: direct URL resolution was removed; we pass raw URLs and keep first_direct_download_url as None.
        try:
            from email_processing import link_extraction as _link_extraction
            delivery_links = _link_extraction.extract_provider_links_from_text(full_email_content or '')
            try:
                logger.debug(
                    "MEDIA_SOLUTION_DEBUG: Extracted %d delivery link(s) for email %s",
                    len(delivery_links or []),
                    email_id,
                )
            except Exception:
                pass
        except Exception:
            delivery_links = []

        extra_payload = {
            "delivery_links": delivery_links or [],
            # direct resolution removed (see docs); keep explicit null for compatibility
            "first_direct_download_url": None,
        }

        makecom_success = send_makecom_webhook(
            subject=subject,
            delivery_time=pattern_result.get('delivery_time'),
            sender_email=sender_email,
            email_id=email_id,
            override_webhook_url=None,
            extra_payload=extra_payload,
        )
        if makecom_success:
            # Optional mirror to custom PHP endpoint (deployment/) to persist links
            # Log mirror attempt or reason for skipping
            try:
                mirror_enabled = bool(processing_prefs.get('mirror_media_to_custom'))
            except Exception:
                mirror_enabled = False
                
            try:
                from app_render import WEBHOOK_URL as _CUSTOM_URL
            except Exception:
                _CUSTOM_URL = None
                
            try:
                logger.info(
                    "MEDIA_SOLUTION: Mirror diagnostics — enabled=%s, url_configured=%s, links=%d",
                    mirror_enabled,
                    bool(_CUSTOM_URL),
                    len(delivery_links or []),
                )
            except Exception:
                pass
                
            # Only attempt mirror if Make.com webhook was successful
            if makecom_success and mirror_enabled and _CUSTOM_URL:
                try:
                    import requests as _requests
                    mirror_payload = {
                        # Use simple shape accepted by deployment receiver
                        "subject": subject or "",
                        "sender_email": sender_email or None,
                        "delivery_links": delivery_links or [],
                    }
                    logger.info(
                        "MEDIA_SOLUTION: Starting mirror POST to custom endpoint (%s) with %d link(s)",
                        _CUSTOM_URL,
                        len(delivery_links or []),
                    )
                    _resp = _requests.post(
                        _CUSTOM_URL,
                        json=mirror_payload,
                        headers={"Content-Type": "application/json"},
                        timeout=int(processing_prefs.get('webhook_timeout_sec') or 30),
                        verify=True,
                    )
                    if getattr(_resp, "status_code", None) != 200:
                        logger.error(
                            "MEDIA_SOLUTION: Mirror call failed (status=%s): %s",
                            getattr(_resp, "status_code", "n/a"),
                            (getattr(_resp, "text", "") or "")[:200],
                        )
                    else:
                        logger.info("MEDIA_SOLUTION: Mirror call succeeded (status=200)")
                except Exception as _m_ex:
                    logger.error("MEDIA_SOLUTION: Exception during mirror call: %s", _m_ex)
            else:
                # Log why mirror was not attempted
                if not makecom_success:
                    logger.error("MEDIA_SOLUTION: Make webhook failed; mirror not attempted")
                elif not mirror_enabled:
                    logger.info("MEDIA_SOLUTION: Mirror skipped — mirror_media_to_custom disabled")
                elif not _CUSTOM_URL:
                    logger.info("MEDIA_SOLUTION: Mirror skipped — WEBHOOK_URL not configured")
            
            # Mark as processed if needed
            try:
                if subject_group_id and makecom_success:
                    mark_subject_group_processed(subject_group_id)
            except Exception as e:
                logger.error("MEDIA_SOLUTION: Error marking subject group as processed: %s", e)
            
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
