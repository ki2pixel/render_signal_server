"""
email_processing.payloads
~~~~~~~~~~~~~~~~~~~~~~~~~~

Builders for webhook payloads to keep formatting logic centralized and testable.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from typing_extensions import TypedDict


class CustomWebhookPayload(TypedDict, total=False):
    """Structure du payload pour le webhook custom (PHP endpoint)."""
    microsoft_graph_email_id: str
    subject: Optional[str]
    receivedDateTime: Optional[str]
    sender_address: Optional[str]
    bodyPreview: Optional[str]
    email_content: Optional[str]
    delivery_links: List[Dict[str, str]]
    first_direct_download_url: Optional[str]
    dropbox_urls: List[str]
    dropbox_first_url: Optional[str]


class DesaboMakePayload(TypedDict, total=False):
    """Structure du payload pour le webhook Make.com DESABO."""
    detector: str
    email_content: Optional[str]
    Text: Optional[str]
    Subject: Optional[str]
    Sender: Optional[Dict[str, str]]
    webhooks_time_start: Optional[str]
    webhooks_time_end: Optional[str]


def _extract_dropbox_urls_legacy(delivery_links: Optional[List[Dict[str, str]]]) -> List[str]:
    """Extrait les URLs Dropbox depuis delivery_links pour compatibilité legacy.
    
    Args:
        delivery_links: Liste de dicts avec 'provider' et 'raw_url'
    
    Returns:
        Liste des raw_url où provider == 'dropbox'
    """
    if not delivery_links:
        return []
    
    try:
        return [
            item.get("raw_url")
            for item in delivery_links
            if item and item.get("provider") == "dropbox" and item.get("raw_url")
        ]
    except Exception:
        return []


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
    
    Note: delivery_links items may contain an optional 'r2_url' field if R2TransferService
    successfully transferred the file to Cloudflare R2. The structure is:
        {
            'provider': 'dropbox',
            'raw_url': 'https://...',
            'direct_url': 'https://...' or None,
            'r2_url': 'https://media.example.com/...' (optional)
        }
    """
    dropbox_urls_legacy = _extract_dropbox_urls_legacy(delivery_links)
    
    payload = {
        "microsoft_graph_email_id": email_id,
        "subject": subject,
        "receivedDateTime": date_received,
        "sender_address": sender,
        "bodyPreview": body_preview,
        "email_content": full_email_content,
        "delivery_links": delivery_links,
        "first_direct_download_url": first_direct_url,
        "dropbox_urls": dropbox_urls_legacy,
        "dropbox_first_url": dropbox_urls_legacy[0] if dropbox_urls_legacy else None,
    }

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
