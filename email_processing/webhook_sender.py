"""
email_processing.webhook_sender
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Fonctions d'envoi de webhooks (Make.com, autorépondeur, etc.).
Extraction depuis app_render.py pour améliorer la modularité et la testabilité.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Callable, Optional

import requests

from config import settings


def send_makecom_webhook(
    subject: str,
    delivery_time: Optional[str],
    sender_email: Optional[str],
    email_id: str,
    override_webhook_url: Optional[str] = None,
    extra_payload: Optional[dict] = None,
    *,
    attempts: int = 2,
    logger: Optional[logging.Logger] = None,
    log_hook: Optional[Callable[[dict], None]] = None,
) -> bool:
    """Envoie un webhook vers Make.com.

    Cette fonction est une extraction de `app_render.py`. Elle supporte l'injection
    d'un logger et d'un hook de log pour éviter les dépendances directes sur Flask
    (`app.logger`) et sur les fonctions internes de logging du dashboard.

    Args:
        subject: Sujet de l'email
        delivery_time: Heure/fenêtre de livraison extraite (ex: "11h38" ou None)
        sender_email: Adresse e-mail de l'expéditeur
        email_id: Identifiant unique de l'email (pour les logs)
        override_webhook_url: URL Make.com alternative (prioritaire si fournie)
        extra_payload: Données supplémentaires à fusionner dans le payload JSON
        attempts: Nombre de tentatives d'envoi (défaut: 2, minimum: 1)
        logger: Logger optionnel (par défaut logging.getLogger(__name__))
        log_hook: Callback facultatif prenant un dict pour journaliser côté dashboard

    Returns:
        bool: True en cas de succès HTTP 200, False sinon
    """
    log = logger or logging.getLogger(__name__)

    payload = {
        "subject": subject,
        "delivery_time": delivery_time,
        "sender_email": sender_email,
    }
    if extra_payload:
        for k, v in extra_payload.items():
            if k not in payload:
                payload[k] = v

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {settings.MAKECOM_API_KEY}",
    }

    target_url = override_webhook_url or settings.RECADRAGE_MAKE_WEBHOOK_URL
    if not target_url:
        # In test contexts, we still want to exercise retry logic. Use a placeholder URL.
        log.error("MAKECOM: No webhook URL configured (target_url is empty). Proceeding with placeholder for retry behavior.")
        target_url = "http://localhost/placeholder-webhook"

    # Valider le nombre de tentatives (au moins 1)
    attempts = max(1, attempts)
    last_ok = False
    for attempt in range(1, attempts + 1):
        try:
            log.info(
                "MAKECOM: Sending webhook (attempt %s/%s) for email %s - Subject: '%s', Delivery: %s, Sender: %s",
                attempt,
                attempts,
                email_id,
                subject,
                delivery_time,
                sender_email,
            )

            response = requests.post(
                target_url,
                json=payload,
                headers=headers,
                timeout=30,
                verify=True,
            )

            ok = response.status_code == 200
            last_ok = ok
            log_text = None if ok else (response.text[:200] if getattr(response, "text", None) else "Unknown error")

            # Hook vers le dashboard log si disponible (par tentative)
            if log_hook:
                try:
                    log_entry = {
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "type": "makecom",
                        "email_id": email_id,
                        "status": "success" if ok else "error",
                        "status_code": response.status_code,
                        "target_url": target_url[:50] + "..." if len(target_url) > 50 else target_url,
                        "subject": subject[:100] if subject else None,
                    }
                    if not ok:
                        log_entry["error"] = log_text
                    log_hook(log_entry)
                except Exception:
                    pass

            if ok:
                log.info("MAKECOM: Webhook sent successfully for email %s on attempt %s", email_id, attempt)
                return True
            else:
                log.error(
                    "MAKECOM: Webhook failed for email %s on attempt %s. Status: %s, Response: %s",
                    email_id,
                    attempt,
                    response.status_code,
                    log_text,
                )
        except requests.exceptions.RequestException as e:
            last_ok = False
            log.error("MAKECOM: Exception during webhook call for email %s on attempt %s: %s", email_id, attempt, e)
            if log_hook:
                try:
                    log_hook(
                        {
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "type": "makecom",
                            "email_id": email_id,
                            "status": "error",
                            "error": str(e)[:200],
                            "target_url": target_url[:50] + "..." if len(target_url) > 50 else target_url,
                            "subject": subject[:100] if subject else None,
                        }
                    )
                except Exception:
                    pass

    return last_ok
