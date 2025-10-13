#!/usr/bin/env python3
"""
Simulate webhook payloads for three scenarios without performing real HTTP requests.
- Case 1: Email with a Dropbox folder link (custom webhook expects dropbox_urls legacy field)
- Case 2: Email with only FromSmash/SwissTransfer links (no dropbox_urls)
- Case 3: Presence and Desabo flows to Make.com (uses send_makecom_webhook payloads)

This script mocks requests.post so no network calls are made.
Run with:
  DISABLE_BACKGROUND_TASKS=true \
  python debug/simulate_webhooks.py

Note:
- We import functions from app_render.py and re-use their logic to build payloads.
- We do not run background poller.
- The goal is to inspect payload content printed to stdout.
"""
from __future__ import annotations

import os
import json
from types import SimpleNamespace
import sys
from pathlib import Path

# Ensure background tasks aren't started on import
os.environ.setdefault("DISABLE_BACKGROUND_TASKS", "true")

# Make project root importable so `import app_render` works when running this file directly
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import app_render as app  # noqa: E402

# --- Mock requests.post to avoid any real network I/O ---
class _MockResponse:
    def __init__(self, status_code=200, text="{\"success\":true}"):
        self.status_code = status_code
        self.text = text
        self.content = text.encode("utf-8")

    def json(self):
        try:
            return json.loads(self.text)
        except Exception:
            return {}


def _mock_post(url, json=None, headers=None, timeout=None, verify=None):  # noqa: A002 (shadow builtins by param name 'json')
    print("\n[MOCK requests.post]\n- URL:", url)
    print("- Headers:", headers)
    print("- Verify:", verify)
    print("- Timeout:", timeout)
    print("- JSON payload:")
    print(json_dumps(json))
    return _MockResponse(status_code=200, text='{"success": true, "message": "mock"}')


# Patch requests.post in the imported module scope
app.requests.post = _mock_post  # type: ignore


def json_dumps(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True)


def build_custom_webhook_payload(subject: str, body: str, email_id: str = "test_email_id") -> dict:
    """Replicate the payload building for the custom webhook, including legacy dropbox_urls."""
    # Minimal fields used downstream
    body_preview = (body or "")[:200]
    date_received = "2025-10-03T08:00:00Z"
    sender = "\"Test Sender\" <test@example.com>"

    provider_links = app.extract_provider_links_from_text(body)
    delivery_links: list[dict] = []
    first_direct_url = None
    for link in provider_links:
        provider = link["provider"]
        raw_url = link["raw_url"]
        # We don't want to trigger any heavy headless logic. The resolver will only parse HTML; safe.
        direct_url = app.resolve_direct_download_url(provider, raw_url)
        delivery_links.append({
            "provider": provider,
            "raw_url": raw_url,
            "direct_url": direct_url,
        })
        if not first_direct_url and direct_url:
            first_direct_url = direct_url

    payload_for_webhook: dict = {
        "microsoft_graph_email_id": email_id,
        "subject": subject,
        "receivedDateTime": date_received,
        "sender_address": sender,
        "bodyPreview": body_preview,
        "email_content": body,
        "delivery_links": delivery_links,
        "first_direct_download_url": first_direct_url,
    }

    # Legacy mapping for receivers expecting `dropbox_urls`
    dropbox_urls_legacy = [
        item.get("raw_url")
        for item in delivery_links
        if item and item.get("provider") == "dropbox" and item.get("raw_url")
    ]
    if dropbox_urls_legacy:
        payload_for_webhook["dropbox_urls"] = dropbox_urls_legacy

    return payload_for_webhook


def simulate_case_1_dropbox():
    print("\n=== Case 1: Dropbox folder link present ===")
    subject = "Média Solution - Missions Recadrage - Lot 42"
    body = (
        "Bonjour,\n\nVoici les fichiers : https://www.dropbox.com/scl/fo/abc123/\n"
        "À faire pour 11h51.\n"
    )
    # Build custom webhook payload
    payload = build_custom_webhook_payload(subject, body, email_id="case1")
    print("Generated custom payload:")
    print(json_dumps(payload))

    # Simulate Make.com call if pattern matches
    pattern = app.check_media_solution_pattern(subject, body)
    print("Pattern result:")
    print(json_dumps(pattern))
    if pattern.get("matches"):
        sender_email = "expediteur@example.com"
        print("\nSimulated Make.com webhook (mocked):")
        app.send_makecom_webhook(
            subject=subject,
            delivery_time=pattern["delivery_time"],
            sender_email=sender_email,
            email_id="case1-make",
        )


def simulate_case_2_non_dropbox():
    print("\n=== Case 2: Only FromSmash/SwissTransfer links ===")
    subject = "Média Solution - Missions Recadrage - Lot 43"
    body = (
        "Bonjour,\n\nJ'ai déposé ici : https://fromsmash.com/OPhYnnPgFM-ct\n"
        "Et ici : https://www.swisstransfer.com/d/6bacf66b-9a4d-4df4-af3f-ccb96a444c12\n"
        "À faire pour 09h05.\n"
    )
    payload = build_custom_webhook_payload(subject, body, email_id="case2")
    print("Generated custom payload:")
    print(json_dumps(payload))
    print("dropbox_urls present:", "dropbox_urls" in payload)

    pattern = app.check_media_solution_pattern(subject, body)
    print("Pattern result:")
    print(json_dumps(pattern))
    if pattern.get("matches"):
        print("\nSimulated Make.com webhook (mocked):")
        app.send_makecom_webhook(
            subject=subject,
            delivery_time=pattern["delivery_time"],
            sender_email="expediteur@example.com",
            email_id="case2-make",
        )


def simulate_case_3_presence_and_desabo():
    print("\n=== Case 3: Presence (samedi) and Desabo flows ===")

    # Presence: subject/body both contain 'samedi'; Make webhook should be sent with presence flag
    subject_presence = "Planning samedi – Disponibilités"
    body_presence = "Sujet et corps mentionnent samedi. samedI présent dans le corps aussi."
    print("Simulated Make.com PRESENCE webhook (mocked):")
    app.send_makecom_webhook(
        subject=subject_presence,
        delivery_time=None,
        sender_email="presence@example.com",
        email_id="case3-presence",
        override_webhook_url=(app.PRESENCE_TRUE_MAKE_WEBHOOK_URL or app.PRESENCE_FALSE_MAKE_WEBHOOK_URL),
        extra_payload={
            "presence": app.PRESENCE_FLAG,
            "detector": "samedi_presence",
            "webhooks_time_start": getattr(app, "WEBHOOKS_TIME_START_STR", None),
            "webhooks_time_end": getattr(app, "WEBHOOKS_TIME_END_STR", None),
        },
    )

    # Desabo: terms + a Dropbox request link
    subject_desabo = "Information clients"
    body_desabo = (
        "Se désabonner — journée — tarifs habituels.\n"
        "Uploader via https://www.dropbox.com/request/xyz123\n"
    )
    print("\nSimulated Make.com DESABO webhook (mocked):")
    app.send_makecom_webhook(
        subject=subject_desabo,
        delivery_time=None,
        sender_email="desabo@example.com",
        email_id="case3-desabo",
        override_webhook_url=app.AUTOREPONDEUR_MAKE_WEBHOOK_URL,
        extra_payload={
            "detector": "desabonnement_journee_tarifs",
            "email_content": body_desabo,
            "Text": body_desabo,
            "Subject": subject_desabo,
            "Sender": {"email": "desabo@example.com"},
            "webhooks_time_start": getattr(app, "WEBHOOKS_TIME_START_STR", None),
            "webhooks_time_end": getattr(app, "WEBHOOKS_TIME_END_STR", None),
        },
    )


def main():
    print("Simulation starting. Background tasks disabled:", os.environ.get("DISABLE_BACKGROUND_TASKS"))
    simulate_case_1_dropbox()
    simulate_case_2_non_dropbox()
    simulate_case_3_presence_and_desabo()
    print("\nDone.")


if __name__ == "__main__":
    main()
