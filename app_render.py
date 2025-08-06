from flask import Flask, jsonify, request, send_from_directory, render_template, redirect, url_for
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
import os
import time
from pathlib import Path
import json
import logging
import re
import requests
import threading
from datetime import datetime, timedelta, timezone
import imaplib
import email
from email.header import decode_header
import ssl
import hashlib
import urllib3
import re

try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None

try:
    import redis

    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    # Logging at module level might not use app's logger config yet.
    # Standard logging can be used if needed here, or rely on app.logger later.

app = Flask(__name__, template_folder='.', static_folder='static')
# NOUVEAU: Une clé secrète est OBLIGATOIRE pour les sessions.
# Pour la production, utilisez une valeur complexe stockée dans les variables d'environnement.
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "une-cle-secrete-tres-complexe-pour-le-developpement-a-changer")

# --- Tokens et Config de référence (basés sur l'image/description fournie) ---
REF_TRIGGER_PAGE_USER = "admin"
REF_TRIGGER_PAGE_PASSWORD = "UDPVA#esKf40r@"
REF_PROCESS_API_TOKEN = "rnd_PW5cGYVf4gl3limu9cYkFw27u8dY"
REF_EMAIL_ADDRESS = "kidpixel@inbox.lt"
REF_EMAIL_PASSWORD = "YvP3Zw66Xx"  # Special IMAP/SMTP password for inbox.lt
REF_IMAP_SERVER = "mail.inbox.lt"
REF_IMAP_PORT = 993
REF_IMAP_USE_SSL = True
REF_WEBHOOK_URL = "https://webhook.kidpixel.fr/index.php"
REF_MAKECOM_WEBHOOK_URL = "https://hook.eu2.make.com/s98s0s735h23qakb9pp0id8c8hbhfqph"
REF_MAKECOM_API_KEY = "12e8b61d-a78e-47f5-9f87-359af19f46cb"
REF_SENDER_OF_INTEREST_FOR_POLLING = "achats@media-solution.fr,camille.moine.pro@gmail.com,a.peault@media-solution.fr,v.lorent@media-solution.fr,technique@media-solution.fr,t.deslus@media-solution.fr"
REF_POLLING_TIMEZONE = "Europe/Paris"
REF_POLLING_ACTIVE_START_HOUR = 9
REF_POLLING_ACTIVE_END_HOUR = 23
REF_POLLING_ACTIVE_DAYS = "0,1,2,3,4"
REF_EMAIL_POLLING_INTERVAL_SECONDS = 30
# ------------------------------------------------------------------------------------

# --- Configuration du Logging ---
log_level_str = os.environ.get('FLASK_LOG_LEVEL', 'INFO').upper()
log_level = getattr(logging, log_level_str, logging.INFO)
logging.basicConfig(level=log_level,
                    format='%(asctime)s - %(levelname)s - %(name)s - %(module)s - %(funcName)s - %(lineno)d - %(message)s')
if not REDIS_AVAILABLE:
    logging.warning(
        "CFG REDIS (module level): 'redis' Python library not installed. Redis-based features will be disabled or use fallbacks.")

# --- Configuration des Identifiants pour la page de connexion ---
TRIGGER_PAGE_USER_ENV = os.environ.get("TRIGGER_PAGE_USER", REF_TRIGGER_PAGE_USER)
TRIGGER_PAGE_PASSWORD_ENV = os.environ.get("TRIGGER_PAGE_PASSWORD", REF_TRIGGER_PAGE_PASSWORD)
users = {}
if TRIGGER_PAGE_USER_ENV and TRIGGER_PAGE_PASSWORD_ENV:
    users[TRIGGER_PAGE_USER_ENV] = TRIGGER_PAGE_PASSWORD_ENV
    app.logger.info(f"CFG AUTH: Utilisateur '{TRIGGER_PAGE_USER_ENV}' configuré pour la connexion.")
else:
    app.logger.warning(
        "CFG AUTH: TRIGGER_PAGE_USER ou TRIGGER_PAGE_PASSWORD non défini. La connexion à l'interface sera impossible.")

# --- NOUVELLE CONFIGURATION : FLASK-LOGIN ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'  # Redirige les utilisateurs non connectés vers la route /login
login_manager.login_message = "Veuillez vous connecter pour accéder à cette page."
login_manager.login_message_category = "info"


# NOUVEAU: Classe utilisateur requise par Flask-Login
class User(UserMixin):
    def __init__(self, id):
        self.id = id

    @staticmethod
    def get(user_id):
        if user_id in users:
            return User(user_id)
        return None


# NOUVEAU: Fonction pour charger un utilisateur depuis la session
@login_manager.user_loader
def load_user(user_id):
    return User.get(user_id)


# --- Configuration du Polling des Emails ---
POLLING_TIMEZONE_STR = os.environ.get("POLLING_TIMEZONE", REF_POLLING_TIMEZONE)
POLLING_ACTIVE_START_HOUR = int(os.environ.get("POLLING_ACTIVE_START_HOUR", REF_POLLING_ACTIVE_START_HOUR))
POLLING_ACTIVE_END_HOUR = int(os.environ.get("POLLING_ACTIVE_END_HOUR", REF_POLLING_ACTIVE_END_HOUR))
POLLING_ACTIVE_DAYS_RAW = os.environ.get("POLLING_ACTIVE_DAYS", REF_POLLING_ACTIVE_DAYS)
POLLING_ACTIVE_DAYS = []
if POLLING_ACTIVE_DAYS_RAW:
    try:
        POLLING_ACTIVE_DAYS = [int(d.strip()) for d in POLLING_ACTIVE_DAYS_RAW.split(',') if
                               d.strip().isdigit() and 0 <= int(d.strip()) <= 6]
    except ValueError:
        app.logger.warning(
            f"CFG POLL: Invalid POLLING_ACTIVE_DAYS ('{POLLING_ACTIVE_DAYS_RAW}'). Using default Mon-Fri.")
        POLLING_ACTIVE_DAYS = [0, 1, 2, 3, 4]
if not POLLING_ACTIVE_DAYS: POLLING_ACTIVE_DAYS = [0, 1, 2, 3, 4]
TZ_FOR_POLLING = None
if POLLING_TIMEZONE_STR.upper() != "UTC":
    if ZoneInfo:
        try:
            TZ_FOR_POLLING = ZoneInfo(POLLING_TIMEZONE_STR)
            app.logger.info(f"CFG POLL: Using timezone '{POLLING_TIMEZONE_STR}' for polling schedule.")
        except Exception as e:
            app.logger.warning(f"CFG POLL: Error loading TZ '{POLLING_TIMEZONE_STR}': {e}. Using UTC.")
            POLLING_TIMEZONE_STR = "UTC"
    else:
        app.logger.warning(f"CFG POLL: 'zoneinfo' module not available. Using UTC. '{POLLING_TIMEZONE_STR}' ignored.")
        POLLING_TIMEZONE_STR = "UTC"
if TZ_FOR_POLLING is None:
    TZ_FOR_POLLING = timezone.utc
    app.logger.info(f"CFG POLL: Using timezone 'UTC' for polling schedule (default or fallback).")
EMAIL_POLLING_INTERVAL_SECONDS = int(
    os.environ.get("EMAIL_POLLING_INTERVAL_SECONDS", REF_EMAIL_POLLING_INTERVAL_SECONDS))
POLLING_INACTIVE_CHECK_INTERVAL_SECONDS = int(os.environ.get("POLLING_INACTIVE_CHECK_INTERVAL_SECONDS", 600))
app.logger.info(
    f"CFG POLL: Active polling interval: {EMAIL_POLLING_INTERVAL_SECONDS}s. Inactive period check interval: {POLLING_INACTIVE_CHECK_INTERVAL_SECONDS}s.")
app.logger.info(
    f"CFG POLL: Active schedule ({POLLING_TIMEZONE_STR}): {POLLING_ACTIVE_START_HOUR:02d}:00-{POLLING_ACTIVE_END_HOUR:02d}:00. Days (0=Mon): {POLLING_ACTIVE_DAYS}")

# --- Chemins et Fichiers ---
SIGNAL_DIR = Path(os.environ.get("RENDER_DISC_PATH", "./signal_data_app_render"))
TRIGGER_SIGNAL_FILE = SIGNAL_DIR / "local_workflow_trigger_signal.json"
SIGNAL_DIR.mkdir(parents=True, exist_ok=True)
app.logger.info(f"CFG PATH: Signal directory for ephemeral files: {SIGNAL_DIR.resolve()}")

# --- Configuration Redis ---
REDIS_URL = os.environ.get('REDIS_URL')
redis_client = None
PROCESSED_EMAIL_IDS_REDIS_KEY = "processed_email_ids_set_v1"

if REDIS_AVAILABLE and REDIS_URL:
    try:
        redis_client = redis.from_url(REDIS_URL, socket_connect_timeout=5, socket_timeout=5, health_check_interval=30)
        redis_client.ping()
        app.logger.info(
            f"CFG REDIS: Successfully connected to Redis at {REDIS_URL.split('@')[-1] if '@' in REDIS_URL else REDIS_URL}.")
    except redis.exceptions.ConnectionError as e_redis:
        app.logger.error(
            f"CFG REDIS: Could not connect to Redis. Error: {e_redis}. Redis-dependent features will be impaired or use fallbacks.")
        redis_client = None
    except Exception as e_redis_other:
        app.logger.error(
            f"CFG REDIS: An unexpected error occurred during Redis initialization: {e_redis_other}. Redis-dependent features will be impaired or use fallbacks.")
        redis_client = None
elif REDIS_AVAILABLE and not REDIS_URL:
    app.logger.warning(
        "CFG REDIS: REDIS_URL not set, but 'redis' library is available. Redis will not be used for primary storage; fallbacks may apply.")
    redis_client = None
else:
    app.logger.warning("CFG REDIS: 'redis' Python library not installed. Redis will not be used; fallbacks may apply.")
    redis_client = None

# --- Configuration IMAP Email ---
EMAIL_ADDRESS = os.environ.get('EMAIL_ADDRESS', REF_EMAIL_ADDRESS)
EMAIL_PASSWORD = os.environ.get('EMAIL_PASSWORD', REF_EMAIL_PASSWORD)
IMAP_SERVER = os.environ.get('IMAP_SERVER', REF_IMAP_SERVER)
IMAP_PORT = int(os.environ.get('IMAP_PORT', REF_IMAP_PORT))
IMAP_USE_SSL = os.environ.get('IMAP_USE_SSL', str(REF_IMAP_USE_SSL)).lower() in ('true', '1', 'yes')

# Log configuration sources for debugging
app.logger.info("CFG EMAIL_DEBUG: Configuration sources:")
app.logger.info(f"CFG EMAIL_DEBUG: - EMAIL_ADDRESS: {'ENV' if 'EMAIL_ADDRESS' in os.environ else 'DEFAULT'} = {EMAIL_ADDRESS}")
app.logger.info(f"CFG EMAIL_DEBUG: - EMAIL_PASSWORD: {'ENV' if 'EMAIL_PASSWORD' in os.environ else 'DEFAULT'} = {'*' * len(EMAIL_PASSWORD) if EMAIL_PASSWORD else 'NOT_SET'}")
app.logger.info(f"CFG EMAIL_DEBUG: - IMAP_SERVER: {'ENV' if 'IMAP_SERVER' in os.environ else 'DEFAULT'} = {IMAP_SERVER}")
app.logger.info(f"CFG EMAIL_DEBUG: - IMAP_PORT: {'ENV' if 'IMAP_PORT' in os.environ else 'DEFAULT'} = {IMAP_PORT}")
app.logger.info(f"CFG EMAIL_DEBUG: - IMAP_USE_SSL: {'ENV' if 'IMAP_USE_SSL' in os.environ else 'DEFAULT'} = {IMAP_USE_SSL}")

# Log reference values for comparison
app.logger.info("CFG EMAIL_DEBUG: Reference values:")
app.logger.info(f"CFG EMAIL_DEBUG: - REF_EMAIL_ADDRESS = {REF_EMAIL_ADDRESS}")
app.logger.info(f"CFG EMAIL_DEBUG: - REF_IMAP_SERVER = {REF_IMAP_SERVER}")
app.logger.info(f"CFG EMAIL_DEBUG: - REF_IMAP_PORT = {REF_IMAP_PORT}")

# Validation de la configuration email
email_config_valid = True
if not EMAIL_ADDRESS or not EMAIL_PASSWORD:
    app.logger.warning("CFG EMAIL: Email address or password missing. Email polling features will be disabled.")
    email_config_valid = False
elif not IMAP_SERVER:
    app.logger.warning("CFG EMAIL: IMAP server not configured. Email polling features will be disabled.")
    email_config_valid = False
else:
    app.logger.info(f"CFG EMAIL: Email polling configured for {EMAIL_ADDRESS} via {IMAP_SERVER}:{IMAP_PORT} (SSL: {IMAP_USE_SSL})")

# --- Configuration des Webhooks et Tokens ---
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", REF_WEBHOOK_URL)
MAKECOM_WEBHOOK_URL = os.environ.get("MAKECOM_WEBHOOK_URL", REF_MAKECOM_WEBHOOK_URL)
MAKECOM_API_KEY = os.environ.get("MAKECOM_API_KEY", REF_MAKECOM_API_KEY)

app.logger.info(f"CFG WEBHOOK: Custom webhook URL configured to: {WEBHOOK_URL}")
app.logger.info(f"CFG MAKECOM: Make.com webhook URL configured to: {MAKECOM_WEBHOOK_URL}")

# Suppress SSL warnings for webhook calls (due to certificate hostname mismatch)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
app.logger.warning("CFG WEBHOOK: SSL verification disabled for webhook calls due to certificate hostname mismatch")
SENDER_OF_INTEREST_FOR_POLLING_RAW = os.environ.get("SENDER_OF_INTEREST_FOR_POLLING",
                                                    REF_SENDER_OF_INTEREST_FOR_POLLING)
SENDER_LIST_FOR_POLLING = [e.strip().lower() for e in SENDER_OF_INTEREST_FOR_POLLING_RAW.split(',') if
                           e.strip()] if SENDER_OF_INTEREST_FOR_POLLING_RAW else []
if SENDER_LIST_FOR_POLLING:
    app.logger.info(
        f"CFG POLL: Monitoring emails from {len(SENDER_LIST_FOR_POLLING)} senders: {SENDER_LIST_FOR_POLLING}")
else:
    app.logger.warning("CFG POLL: SENDER_OF_INTEREST_FOR_POLLING not set. Email polling likely ineffective.")
EXPECTED_API_TOKEN = os.environ.get("PROCESS_API_TOKEN", REF_PROCESS_API_TOKEN)
if not EXPECTED_API_TOKEN:
    app.logger.warning("CFG TOKEN: PROCESS_API_TOKEN not set. API endpoints called by Make.com will be insecure.")
else:
    app.logger.info(f"CFG TOKEN: PROCESS_API_TOKEN (for Make.com calls) configured: '{EXPECTED_API_TOKEN[:5]}...')")


# --- Fonctions Utilitaires IMAP ---
def create_imap_connection():
    """Crée une connexion IMAP sécurisée au serveur email."""
    # Log detailed configuration for debugging
    app.logger.info(f"IMAP_DEBUG: Attempting connection with:")
    app.logger.info(f"IMAP_DEBUG: - Server: {IMAP_SERVER}")
    app.logger.info(f"IMAP_DEBUG: - Port: {IMAP_PORT}")
    app.logger.info(f"IMAP_DEBUG: - SSL: {IMAP_USE_SSL}")
    app.logger.info(f"IMAP_DEBUG: - Email: {EMAIL_ADDRESS}")
    app.logger.info(f"IMAP_DEBUG: - Password: {'*' * len(EMAIL_PASSWORD) if EMAIL_PASSWORD else 'NOT_SET'}")

    try:
        if IMAP_USE_SSL:
            # Connexion SSL/TLS
            app.logger.info(f"IMAP_DEBUG: Creating SSL connection to {IMAP_SERVER}:{IMAP_PORT}")
            mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
        else:
            # Connexion non-sécurisée (non recommandée)
            app.logger.info(f"IMAP_DEBUG: Creating non-SSL connection to {IMAP_SERVER}:{IMAP_PORT}")
            mail = imaplib.IMAP4(IMAP_SERVER, IMAP_PORT)

        app.logger.info(f"IMAP_DEBUG: Connection established, attempting authentication...")
        # Authentification
        mail.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        app.logger.info(f"IMAP: Successfully connected to {IMAP_SERVER}:{IMAP_PORT}")
        return mail
    except imaplib.IMAP4.error as e:
        app.logger.error(f"IMAP: Authentication failed for {EMAIL_ADDRESS} on {IMAP_SERVER}:{IMAP_PORT} - {e}")
        return None
    except Exception as e:
        app.logger.error(f"IMAP: Connection error to {IMAP_SERVER}:{IMAP_PORT} - {e}")
        return None


def close_imap_connection(mail):
    """Ferme proprement une connexion IMAP."""
    try:
        if mail:
            mail.close()
            mail.logout()
            app.logger.debug("IMAP: Connection closed successfully")
    except Exception as e:
        app.logger.warning(f"IMAP: Error closing connection: {e}")


def generate_email_id(msg_data):
    """Génère un ID unique pour un email basé sur son contenu."""
    # Utilise un hash du Message-ID, sujet et date pour créer un ID unique
    msg_id = msg_data.get('Message-ID', '')
    subject = msg_data.get('Subject', '')
    date = msg_data.get('Date', '')

    # Combine les éléments et crée un hash
    unique_string = f"{msg_id}|{subject}|{date}"
    return hashlib.md5(unique_string.encode('utf-8')).hexdigest()


def extract_sender_email(from_header):
    """
    Extrait l'adresse email du header 'From'.

    Gère les formats:
    - "Name <email@domain.com>" → "email@domain.com"
    - "email@domain.com" → "email@domain.com"

    Args:
        from_header (str): Contenu du header 'From'

    Returns:
        str: Adresse email extraite ou chaîne vide si non trouvée
    """
    if not from_header:
        return ""

    # Pattern regex pour extraire l'email entre < > ou directement
    email_pattern = r'<([^>]+)>|([^\s<>]+@[^\s<>]+)'
    match = re.search(email_pattern, from_header)

    if match:
        # Si trouvé entre < >, utiliser le premier groupe, sinon le second
        return match.group(1) if match.group(1) else match.group(2)

    return ""


def decode_email_header(header_value):
    """Décode les en-têtes d'email qui peuvent être encodés."""
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


def mark_email_as_read_imap(mail, email_num):
    """Marque un email comme lu via IMAP."""
    try:
        mail.store(email_num, '+FLAGS', '\\Seen')
        app.logger.debug(f"IMAP: Email {email_num} marked as read")
        return True
    except Exception as e:
        app.logger.error(f"IMAP: Error marking email {email_num} as read: {e}")
        return False


def check_media_solution_pattern(subject, email_content):
    """
    Vérifie si l'email correspond au pattern Média Solution spécifique.

    Conditions requises:
    1. Contenu contient: "https://www.dropbox.com/scl/fo"
    2. Sujet contient: "Média Solution - Missions Recadrage - Lot"
    3. Contenu contient: "à faire pour"

    Returns: dict avec 'matches' (bool) et 'delivery_time' (str ou None)
    """
    result = {'matches': False, 'delivery_time': None}

    if not subject or not email_content:
        return result

    # Vérifier les 3 conditions
    condition1 = "https://www.dropbox.com/scl/fo" in email_content
    condition2 = "Média Solution - Missions Recadrage - Lot" in subject
    condition3 = "à faire pour" in email_content

    app.logger.debug(f"PATTERN_CHECK: Dropbox URL: {condition1}, Subject pattern: {condition2}, Delivery phrase: {condition3}")

    if condition1 and condition2 and condition3:
        # Extraire l'heure de livraison avec regex
        # Pattern: "à faire pour" suivi d'espaces et de l'heure (format comme "11h38")
        delivery_pattern = r'à faire pour\s+(\d{1,2}h\d{2})'
        match = re.search(delivery_pattern, email_content, re.IGNORECASE)

        if match:
            result['delivery_time'] = match.group(1)
            result['matches'] = True
            app.logger.info(f"PATTERN_MATCH: Email matches Média Solution pattern. Delivery time: {result['delivery_time']}")
        else:
            app.logger.warning("PATTERN_CHECK: All conditions met but couldn't extract delivery time")

    return result


def send_makecom_webhook(subject, delivery_time, sender_email, email_id):
    """
    Envoie les données à Make.com webhook pour les emails Média Solution.

    Args:
        subject (str): Sujet complet de l'email
        delivery_time (str): Heure de livraison extraite (ex: "11h38")
        sender_email (str): Adresse email de l'expéditeur
        email_id (str): ID unique de l'email pour les logs

    Returns:
        bool: True si succès, False sinon
    """
    payload = {
        "subject": subject,
        "delivery_time": delivery_time,
        "sender_email": sender_email
    }

    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {MAKECOM_API_KEY}'
    }

    try:
        app.logger.info(f"MAKECOM: Sending webhook for email {email_id} - Subject: '{subject}', Delivery: {delivery_time}, Sender: {sender_email}")

        response = requests.post(
            MAKECOM_WEBHOOK_URL,
            json=payload,
            headers=headers,
            timeout=30,
            verify=True  # Make.com should have valid SSL certificates
        )

        if response.status_code == 200:
            app.logger.info(f"MAKECOM: Webhook sent successfully for email {email_id}")
            return True
        else:
            app.logger.error(f"MAKECOM: Webhook failed for email {email_id}. Status: {response.status_code}, Response: {response.text[:200]}")
            return False

    except requests.exceptions.RequestException as e:
        app.logger.error(f"MAKECOM: Exception during webhook call for email {email_id}: {e}")
        return False


# --- Fonctions de Déduplication avec Redis ---
def is_email_id_processed_redis(email_id):
    if not redis_client: return False
    try:
        return redis_client.sismember(PROCESSED_EMAIL_IDS_REDIS_KEY, email_id)
    except redis.exceptions.RedisError as e_redis:
        app.logger.error(f"REDIS_DEDUP: Error checking email ID '{email_id}': {e_redis}. Assuming NOT processed.")
        return False


def mark_email_id_as_processed_redis(email_id):
    if not redis_client: return False
    try:
        redis_client.sadd(PROCESSED_EMAIL_IDS_REDIS_KEY, email_id)
        return True
    except redis.exceptions.RedisError as e_redis:
        app.logger.error(f"REDIS_DEDUP: Error adding email ID '{email_id}': {e_redis}")
        return False


# --- Fonctions de Polling des Emails IMAP ---


def check_new_emails_and_trigger_webhook():
    """
    Vérifie les nouveaux emails via IMAP et déclenche le webhook personnalisé pour chaque email valide.
    VERSION IMAP - remplace l'ancienne version Microsoft Graph API.
    """
    app.logger.info("POLLER: Email polling cycle started (IMAP).")
    if not all([SENDER_LIST_FOR_POLLING, WEBHOOK_URL, email_config_valid]):
        app.logger.error("POLLER: Incomplete config for polling. Aborting cycle.")
        return 0

    # Créer une connexion IMAP
    mail = create_imap_connection()
    if not mail:
        app.logger.error("POLLER: Failed to create IMAP connection. Aborting cycle.")
        return 0

    triggered_webhook_count = 0
    try:
        # Sélectionner la boîte de réception
        mail.select('INBOX')

        # Rechercher les emails non lus des derniers 2 jours
        since_date = (datetime.now() - timedelta(days=2)).strftime('%d-%b-%Y')
        search_criteria = f'(UNSEEN SINCE {since_date})'

        app.logger.info(f"POLLER: Searching for emails with criteria: {search_criteria}")

        # Rechercher les emails
        status, email_ids = mail.search(None, search_criteria)
        if status != 'OK':
            app.logger.error(f"POLLER: IMAP search failed: {status}")
            return 0

        email_list = email_ids[0].split()
        app.logger.info(f"POLLER: Found {len(email_list)} unread email(s).")

        if not email_list:
            return 0

        app.logger.info("POLLER: Proceeding with email batch processing.")

        # Traiter chaque email
        for email_num in email_list:
            try:
                # Récupérer l'email
                status, email_data = mail.fetch(email_num, '(RFC822)')
                if status != 'OK':
                    app.logger.warning(f"POLLER: Failed to fetch email {email_num}")
                    continue

                # Parser l'email
                raw_email = email_data[0][1]
                email_message = email.message_from_bytes(raw_email)

                # Extraire les informations de l'email
                subject = decode_email_header(email_message.get('Subject', ''))
                sender = email_message.get('From', '')
                date_received = email_message.get('Date', '')
                message_id = email_message.get('Message-ID', '')

                # Générer un ID unique pour l'email
                email_id = generate_email_id({
                    'Message-ID': message_id,
                    'Subject': subject,
                    'Date': date_received
                })

                app.logger.debug(f"POLLER: Processing email {email_num} - Subject: '{subject[:50]}...', From: {sender}")

                # Vérifier si l'expéditeur est dans la liste des expéditeurs d'intérêt
                sender_email = sender.lower()
                is_from_monitored_sender = any(monitored_sender in sender_email for monitored_sender in SENDER_LIST_FOR_POLLING)

                if not is_from_monitored_sender:
                    app.logger.debug(f"POLLER: Email {email_num} from {sender} is not from a monitored sender. Skipping.")
                    continue

                # Vérifier si l'email a déjà été traité
                if is_email_id_processed_redis(email_id):
                    app.logger.debug(f"POLLER: Email ID {email_id} already processed. Marking as read.")
                    mark_email_as_read_imap(mail, email_num)
                    continue

                # Extraire le contenu complet de l'email
                body_preview = ""
                full_email_content = ""

                if email_message.is_multipart():
                    for part in email_message.walk():
                        if part.get_content_type() == "text/plain":
                            try:
                                content = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                                if not body_preview:
                                    body_preview = content[:500]
                                if not full_email_content:
                                    full_email_content = content
                                break
                            except:
                                pass
                else:
                    try:
                        content = email_message.get_payload(decode=True).decode('utf-8', errors='ignore')
                        body_preview = content[:500]
                        full_email_content = content
                    except:
                        pass

                # Préparer le payload pour le webhook personnalisé (format requis + contenu complet)
                payload_for_webhook = {
                    "microsoft_graph_email_id": email_id,  # Maintenir le nom pour compatibilité
                    "subject": subject,
                    "receivedDateTime": date_received,
                    "sender_address": sender,
                    "bodyPreview": body_preview,
                    "email_content": full_email_content  # Contenu complet pour éviter la recherche IMAP
                }

                # Déclencher le webhook personnalisé
                try:
                    webhook_response = requests.post(
                        WEBHOOK_URL,
                        json=payload_for_webhook,
                        headers={'Content-Type': 'application/json'},
                        timeout=30,
                        verify=False  # Disable SSL verification for hostname mismatch issues
                    )

                    # Vérifier la réponse du webhook
                    if webhook_response.status_code == 200:
                        response_data = webhook_response.json() if webhook_response.content else {}
                        if response_data.get('success', False):
                            app.logger.info(f"POLLER: Webhook triggered successfully for email {email_id}.")

                            # Marquer comme traité dans Redis
                            if mark_email_id_as_processed_redis(email_id):
                                triggered_webhook_count += 1
                                mark_email_as_read_imap(mail, email_num)
                            else:
                                app.logger.error(f"POLLER: CRITICAL - Failed to mark email {email_id} as processed in Redis.")
                        else:
                            app.logger.error(f"POLLER: Webhook processing failed for email {email_id}. Response: {response_data.get('message', 'Unknown error')}")
                    else:
                        app.logger.error(f"POLLER: Webhook call FAILED for email {email_id}. Status: {webhook_response.status_code}, Response: {webhook_response.text[:200]}")

                except requests.exceptions.RequestException as e_webhook:
                    app.logger.error(f"POLLER: Exception during webhook call for email {email_id}: {e_webhook}")
                    continue

                # Vérifier le pattern Média Solution et envoyer à Make.com si nécessaire
                try:
                    pattern_result = check_media_solution_pattern(subject, full_email_content)

                    if pattern_result['matches']:
                        app.logger.info(f"POLLER: Email {email_id} matches Média Solution pattern")

                        # Extraire l'adresse email de l'expéditeur
                        sender_email = extract_sender_email(sender)

                        # Envoyer à Make.com webhook
                        makecom_success = send_makecom_webhook(
                            subject=subject,
                            delivery_time=pattern_result['delivery_time'],
                            sender_email=sender_email,
                            email_id=email_id
                        )

                        if makecom_success:
                            app.logger.info(f"POLLER: Make.com webhook sent successfully for email {email_id}")
                        else:
                            app.logger.error(f"POLLER: Make.com webhook failed for email {email_id}")
                    else:
                        app.logger.debug(f"POLLER: Email {email_id} does not match Média Solution pattern")

                except Exception as e_makecom:
                    app.logger.error(f"POLLER: Exception during Média Solution pattern check for email {email_id}: {e_makecom}")
                    # Continue processing other emails even if this fails

            except Exception as e_email:
                app.logger.error(f"POLLER: Error processing email {email_num}: {e_email}")
                continue

        return triggered_webhook_count

    except Exception as e_general:
        app.logger.error(f"POLLER: Unexpected error in IMAP polling cycle: {e_general}", exc_info=True)
        return triggered_webhook_count
    finally:
        close_imap_connection(mail)


def background_email_poller():
    app.logger.info(f"BG_POLLER: Email polling thread started. TZ for schedule: {POLLING_TIMEZONE_STR}.")
    consecutive_error_count = 0
    MAX_CONSECUTIVE_ERRORS = 5

    while True:
        try:
            now_in_configured_tz = datetime.now(TZ_FOR_POLLING)
            is_active_day = now_in_configured_tz.weekday() in POLLING_ACTIVE_DAYS
            is_active_time = POLLING_ACTIVE_START_HOUR <= now_in_configured_tz.hour < POLLING_ACTIVE_END_HOUR

            if is_active_day and is_active_time:
                app.logger.info(f"BG_POLLER: In active period. Starting poll cycle.")
                if not all([email_config_valid, SENDER_LIST_FOR_POLLING, WEBHOOK_URL]):
                    app.logger.warning(f"BG_POLLER: Essential config for polling is incomplete. Waiting 60s.")
                    time.sleep(60)
                    continue

                webhooks_triggered = check_new_emails_and_trigger_webhook()
                app.logger.info(f"BG_POLLER: Active poll cycle finished. {webhooks_triggered} webhook(s) triggered.")
                consecutive_error_count = 0
                sleep_duration = EMAIL_POLLING_INTERVAL_SECONDS
            else:
                app.logger.info(f"BG_POLLER: Outside active period. Sleeping.")
                sleep_duration = POLLING_INACTIVE_CHECK_INTERVAL_SECONDS

            time.sleep(sleep_duration)

        except Exception as e:
            consecutive_error_count += 1
            app.logger.error(f"BG_POLLER: Unhandled error in polling loop (Error #{consecutive_error_count}): {e}",
                             exc_info=True)
            if consecutive_error_count >= MAX_CONSECUTIVE_ERRORS:
                app.logger.critical(f"BG_POLLER: Max consecutive errors reached. Stopping thread.")
                break
            sleep_on_error_duration = max(60, EMAIL_POLLING_INTERVAL_SECONDS) * (2 ** consecutive_error_count)
            app.logger.info(f"BG_POLLER: Sleeping for {sleep_on_error_duration}s due to error.")
            time.sleep(sleep_on_error_duration)




# --- NOUVELLES ROUTES POUR L'AUTHENTIFICATION ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user and current_user.is_authenticated:
        return redirect(url_for('serve_trigger_page_main'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if username in users and users[username] == password:
            user_obj = User(username)
            login_user(user_obj)
            app.logger.info(f"AUTH: Connexion réussie pour l'utilisateur '{username}'.")
            next_page = request.args.get('next')
            return redirect(next_page or url_for('serve_trigger_page_main'))
        else:
            app.logger.warning(f"AUTH: Tentative de connexion échouée pour '{username}'.")
            return render_template('login.html', error="Identifiants invalides.")

    return render_template('login.html', url_for=url_for)


@app.route('/logout')
@login_required
def logout():
    user_id = current_user.id
    logout_user()
    app.logger.info(f"AUTH: Déconnexion de l'utilisateur '{user_id}'.")
    return redirect(url_for('login'))


# --- Endpoints API (Non-UI, protégés par token) ---


@app.route('/api/check_trigger', methods=['GET'])
def check_local_workflow_trigger():
    if TRIGGER_SIGNAL_FILE.exists():
        with open(TRIGGER_SIGNAL_FILE, 'r') as f: payload = json.load(f)
        TRIGGER_SIGNAL_FILE.unlink()
        return jsonify({'command_pending': True, 'payload': payload})
    return jsonify({'command_pending': False, 'payload': None})


@app.route('/api/ping', methods=['GET', 'HEAD'])
def api_ping():
    return jsonify({"status": "pong", "timestamp_utc": datetime.now(timezone.utc).isoformat()}), 200


# --- ROUTES UI PROTÉGÉES MISES À JOUR ---

@app.route('/')
@login_required
def serve_trigger_page_main():
    app.logger.info(f"ROOT_UI: Requête pour '/' par l'utilisateur '{current_user.id}'. Service de 'trigger_page.html'.")
    return render_template('trigger_page.html')





@app.route('/api/check_emails_and_download', methods=['POST'])
@login_required
def api_check_emails_and_download_authed():
    app.logger.info(f"API_EMAIL_CHECK: Déclenchement manuel par '{current_user.id}'.")

    def run_task():
        with app.app_context():
            check_new_emails_and_trigger_webhook()

    if not all([email_config_valid, SENDER_LIST_FOR_POLLING, WEBHOOK_URL]):
        return jsonify({"status": "error", "message": "Config serveur email incomplète."}), 503
    threading.Thread(target=run_task).start()
    return jsonify({"status": "success", "message": "Vérification en arrière-plan lancée."}), 202


# La fonction de démarrage des tâches reste ici, mais elle ne sera appelée que par Gunicorn ou par le __main__
def start_background_tasks():
    """
    Fonction qui initialise et démarre les threads d'arrière-plan.
    """
    app.logger.info("BACKGROUND_TASKS: Initialisation des tâches...")

    # On vérifie si toutes les conditions sont remplies pour lancer le thread.
    if all([email_config_valid, SENDER_LIST_FOR_POLLING, WEBHOOK_URL]):
        email_poller_thread = threading.Thread(target=background_email_poller, name="EmailPollerThread", daemon=True)
        email_poller_thread.start()
        app.logger.info("BACKGROUND_TASKS: Thread de polling des emails démarré.")
    else:
        # Log détaillé si le thread ne peut pas démarré
        missing_configs = []
        if not email_config_valid: missing_configs.append("Configuration email invalide")
        if not SENDER_LIST_FOR_POLLING: missing_configs.append("Liste des expéditeurs vide")
        if not WEBHOOK_URL: missing_configs.append("URL du webhook manquante")
        app.logger.warning(
            f"BACKGROUND_TASKS: Thread de polling non démarré. Configuration incomplète : {', '.join(missing_configs)}")


# Le code ici est exécuté UNE SEULE FOIS par Gunicorn dans le processus maître
# avant la création des workers. C'est l'endroit parfait pour lancer notre tâche unique.
start_background_tasks()

# Ce bloc ne sera JAMAIS exécuté par Gunicorn, mais il est utile pour le débogage local
if __name__ == '__main__':
    app.logger.info(f"MAIN_APP: (Lancement direct pour débogage local)")
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 10000)))
