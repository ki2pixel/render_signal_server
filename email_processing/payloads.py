"""
email_processing.payloads
~~~~~~~~~~~~~~~~~~~~~~~~~~

Builders for webhook payloads to keep formatting logic centralized and testable.
"""
from __future__ import annotations

from typing import List, Dict, Any, Optional


def build_custom_webhook_payload(
    *,
    email_id: str,
    subject: Optional[str],
    date_received: Optional[str],
    sender: Optional[str],
    body_preview: Optional[str],
    full_email_content: Optional[str],
    delivery_links: List[Dict[str, str]],
    first_direct_url: Optional[str],
) -> Dict[str, Any]:
    """Builds the payload dict for the custom webhook.

    Mirrors legacy fields for backward compatibility.
    Adds legacy Dropbox-specific aliases (`dropbox_urls`, `dropbox_first_url`).
    """
    payload = {
        "microsoft_graph_email_id": email_id,
        "subject": subject,
        "receivedDateTime": date_received,
        "sender_address": sender,
        "bodyPreview": body_preview,
        "email_content": full_email_content,
        "delivery_links": delivery_links,
        "first_direct_download_url": first_direct_url,
    }

    try:
        dropbox_urls_legacy = [
            item.get("raw_url")
            for item in (delivery_links or [])
            if item and item.get("provider") == "dropbox" and item.get("raw_url")
        ]
    except Exception:
        dropbox_urls_legacy = []

    payload["dropbox_urls"] = dropbox_urls_legacy
    payload["dropbox_first_url"] = dropbox_urls_legacy[0] if dropbox_urls_legacy else None

    return payload


def build_desabo_make_payload(
    *,
    subject: Optional[str],
    full_email_content: Optional[str],
    sender_email: Optional[str],
    time_start_payload: Optional[str],
    time_end_payload: Optional[str],
) -> Dict[str, Any]:
    """Builds the `extra_payload` for DESABO Make.com webhook.

    Matches legacy keys expected by Make scenario (detector, Text, Subject, Sender, webhooks_time_*).
    """
    return {
        "detector": "desabonnement_journee_tarifs",
        "email_content": full_email_content,
        # Mailhook-style aliases for Make mapping
        "Text": full_email_content,
        "Subject": subject,
        "Sender": {"email": sender_email} if sender_email else None,
        "webhooks_time_start": time_start_payload,
        "webhooks_time_end": time_end_payload,
    }
