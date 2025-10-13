"""
email_processing.imap_client
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Gestion de la connexion IMAP pour la lecture des emails et helpers associés.
"""

from config.settings import (
    IMAP_SERVER,
    IMAP_PORT,
    IMAP_USE_SSL,
    EMAIL_ADDRESS,
    EMAIL_PASSWORD,
)

import imaplib
import hashlib
import re
from email.header import decode_header


def create_imap_connection(logger):
    """
    Crée une connexion IMAP sécurisée au serveur email.
    
    Args:
        logger: Instance de logger Flask (app.logger)
    
    Returns:
        imaplib.IMAP4_SSL ou imaplib.IMAP4 si succès, None si échec
    """
    # Log detailed configuration for debugging
    logger.info(f"IMAP_DEBUG: Attempting connection with:")
    logger.info(f"IMAP_DEBUG: - Server: {IMAP_SERVER}")
    logger.info(f"IMAP_DEBUG: - Port: {IMAP_PORT}")
    logger.info(f"IMAP_DEBUG: - SSL: {IMAP_USE_SSL}")
    logger.info(f"IMAP_DEBUG: - Email: {EMAIL_ADDRESS}")
    logger.info(f"IMAP_DEBUG: - Password: {'*' * len(EMAIL_PASSWORD) if EMAIL_PASSWORD else 'NOT_SET'}")

    try:
        if IMAP_USE_SSL:
            # Connexion SSL/TLS
            logger.info(f"IMAP_DEBUG: Creating SSL connection to {IMAP_SERVER}:{IMAP_PORT}")
            mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
        else:
            # Connexion non-sécurisée (non recommandée)
            logger.info(f"IMAP_DEBUG: Creating non-SSL connection to {IMAP_SERVER}:{IMAP_PORT}")
            mail = imaplib.IMAP4(IMAP_SERVER, IMAP_PORT)

        logger.info(f"IMAP_DEBUG: Connection established, attempting authentication...")
        # Authentification
        mail.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        logger.info(f"IMAP: Successfully connected to {IMAP_SERVER}:{IMAP_PORT}")
        return mail
    except imaplib.IMAP4.error as e:
        logger.error(f"IMAP: Authentication failed for {EMAIL_ADDRESS} on {IMAP_SERVER}:{IMAP_PORT} - {e}")
        return None
    except Exception as e:
        logger.error(f"IMAP: Connection error to {IMAP_SERVER}:{IMAP_PORT} - {e}")
        return None


def close_imap_connection(logger, mail):
    """Ferme proprement une connexion IMAP."""
    try:
        if mail:
            mail.close()
            mail.logout()
            if logger:
                logger.debug("IMAP: Connection closed successfully")
    except Exception as e:
        if logger:
            logger.warning(f"IMAP: Error closing connection: {e}")


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


def mark_email_as_read_imap(logger, mail, email_num) -> bool:
    """Marque un email comme lu via IMAP."""
    try:
        mail.store(email_num, '+FLAGS', '\\Seen')
        if logger:
            logger.debug(f"IMAP: Email {email_num} marked as read")
        return True
    except Exception as e:
        if logger:
            logger.error(f"IMAP: Error marking email {email_num} as read: {e}")
        return False
