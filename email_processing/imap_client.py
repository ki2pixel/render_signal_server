"""
email_processing.imap_client
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Gestion de la connexion IMAP pour la lecture des emails et helpers associés.
"""
from __future__ import annotations

import hashlib
import imaplib
import re
from email.header import decode_header
from logging import Logger
from typing import Optional, Union

from config.settings import (
    EMAIL_ADDRESS,
    EMAIL_PASSWORD,
    IMAP_PORT,
    IMAP_SERVER,
    IMAP_USE_SSL,
)


def create_imap_connection(logger: Optional[Logger]) -> Optional[Union[imaplib.IMAP4_SSL, imaplib.IMAP4]]:
    """Crée une connexion IMAP sécurisée au serveur email.

    Args:
        logger: Instance de logger Flask (app.logger) ou None

    Returns:
        Connection IMAP (IMAP4_SSL ou IMAP4) si succès, None si échec
    """
    if not logger:
        # Fallback minimal si pas de logger disponible
        return None

    # Validation minimale des paramètres de connexion (ne jamais logger les credentials)
    if not IMAP_SERVER or not EMAIL_ADDRESS or not EMAIL_PASSWORD:
        logger.error("IMAP: Configuration incomplète (serveur, email ou mot de passe manquant)")
        return None

    # Logs de debug uniquement (pas INFO pour éviter le spam)
    logger.debug("IMAP: Tentative de connexion au serveur %s:%s (SSL=%s)", IMAP_SERVER, IMAP_PORT, IMAP_USE_SSL)

    try:
        if IMAP_USE_SSL:
            mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
        else:
            # Connexion non-sécurisée (déconseillé)
            logger.warning("IMAP: Connexion non-SSL utilisée (vulnérable)")
            mail = imaplib.IMAP4(IMAP_SERVER, IMAP_PORT)

        # Authentification (ne jamais logger le mot de passe)
        mail.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        logger.info("IMAP: Connexion établie avec succès (%s)", IMAP_SERVER)
        return mail

    except imaplib.IMAP4.error as e:
        logger.error("IMAP: Échec d'authentification pour %s sur %s:%s - %s", EMAIL_ADDRESS, IMAP_SERVER, IMAP_PORT, e)
        return None
    except Exception as e:
        logger.error("IMAP: Erreur de connexion à %s:%s - %s", IMAP_SERVER, IMAP_PORT, e)
        return None


def close_imap_connection(logger: Optional[Logger], mail: Optional[Union[imaplib.IMAP4_SSL, imaplib.IMAP4]]) -> None:
    """Ferme proprement une connexion IMAP.
    
    Args:
        logger: Instance de logger Flask (app.logger) ou None
        mail: Connection IMAP à fermer ou None
    """
    try:
        if mail:
            mail.close()
            mail.logout()
            if logger:
                logger.debug("IMAP: Connection closed successfully")
    except Exception as e:
        if logger:
            logger.warning("IMAP: Error closing connection: %s", e)


def generate_email_id(msg_data: dict) -> str:
    """Génère un ID unique pour un email basé sur son contenu (Message-ID|Subject|Date)."""
    msg_id = msg_data.get('Message-ID', '')
    subject = msg_data.get('Subject', '')
    date = msg_data.get('Date', '')
    unique_string = f"{msg_id}|{subject}|{date}"
    return hashlib.md5(unique_string.encode('utf-8')).hexdigest()


def extract_sender_email(from_header: str) -> str:
    """Extrait une adresse email depuis un header From."""
    if not from_header:
        return ""
    email_pattern = r'<([^>]+)>|([^\s<>]+@[^\s<>]+)'
    match = re.search(email_pattern, from_header)
    if match:
        return match.group(1) if match.group(1) else match.group(2)
    return ""


def decode_email_header_value(header_value: str) -> str:
    """Décode un header potentiellement encodé (RFC2047)."""
    if not header_value:
        return ""
    decoded_parts = decode_header(header_value)
    decoded_string = ""
    for part, encoding in decoded_parts:
        if isinstance(part, bytes):
            if encoding:
                try:
                    decoded_string += part.decode(encoding)
                except (UnicodeDecodeError, LookupError):
                    decoded_string += part.decode('utf-8', errors='ignore')
            else:
                decoded_string += part.decode('utf-8', errors='ignore')
        else:
            decoded_string += str(part)
    return decoded_string


def mark_email_as_read_imap(logger: Optional[Logger], mail: Optional[Union[imaplib.IMAP4_SSL, imaplib.IMAP4]], email_num: str) -> bool:
    """Marque un email comme lu via IMAP.
    
    Args:
        logger: Instance de logger Flask (app.logger) ou None
        mail: Connection IMAP active
        email_num: Numéro de l'email à marquer comme lu
        
    Returns:
        True si succès, False sinon
    """
    try:
        if not mail:
            return False
        mail.store(email_num, '+FLAGS', '\\Seen')
        if logger:
            logger.debug("IMAP: Email %s marked as read", email_num)
        return True
    except Exception as e:
        if logger:
            logger.error("IMAP: Error marking email %s as read: %s", email_num, e)
        return False
