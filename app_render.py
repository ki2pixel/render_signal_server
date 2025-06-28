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

from msal import ConfidentialClientApplication

app = Flask(__name__, template_folder='.', static_folder='static')
# NOUVEAU: Une clé secrète est OBLIGATOIRE pour les sessions.
# Pour la production, utilisez une valeur complexe stockée dans les variables d'environnement.
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "une-cle-secrete-tres-complexe-pour-le-developpement-a-changer")

# --- Tokens et Config de référence (basés sur l'image/description fournie) ---
REF_TRIGGER_PAGE_USER = "admin"
REF_TRIGGER_PAGE_PASSWORD = "UDPVA#esKf40r@"
REF_REMOTE_UI_ACCESS_TOKEN = "0wbgXHiF3e!MqE"
REF_INTERNAL_WORKER_COMMS_TOKEN = "Fn*G14VbHkra7"
REF_PROCESS_API_TOKEN = "rnd_PW5cGYVf4gl3limu9cYkFw27u8dY"
REF_REGISTER_LOCAL_URL_TOKEN = "WMmWtian6RaUA"
REF_ONEDRIVE_CLIENT_ID = "6bbc767d-53e8-4b82-bd49-480d4c157a9b"
REF_ONEDRIVE_CLIENT_SECRET = "SECRET_PLACEHOLDER_DO_NOT_COMMIT"  # Placeholder
REF_ONEDRIVE_TENANT_ID = "60fb2b89-e5bf-4232-98f6-f1ecb90660c5"
REF_MAKE_SCENARIO_WEBHOOK_URL = "https://hook.eu2.make.com/wjcp43km1bgginyr1xu1pwui95ekr7gi"
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
LOCALTUNNEL_URL_FILE = SIGNAL_DIR / "current_localtunnel_url.txt"
SIGNAL_DIR.mkdir(parents=True, exist_ok=True)
app.logger.info(f"CFG PATH: Signal directory for ephemeral files: {SIGNAL_DIR.resolve()}")

# --- Configuration Redis ---
REDIS_URL = os.environ.get('REDIS_URL')
redis_client = None
LOCALTUNNEL_URL_REDIS_KEY = "current_localtunnel_url_v1"
PROCESSED_EMAIL_IDS_REDIS_KEY = "processed_email_ids_set_v1"
PROCESSED_DROPBOX_URLS_REDIS_KEY = "processed_dropbox_urls_set_v1"
ONEDRIVE_REFRESH_TOKEN_REDIS_KEY = "onedrive_current_refresh_token_v1"

current_onedrive_refresh_token_in_memory = None

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

# --- Configuration OneDrive / MSAL ---
ONEDRIVE_CLIENT_ID = os.environ.get('ONEDRIVE_CLIENT_ID', REF_ONEDRIVE_CLIENT_ID)
ONEDRIVE_CLIENT_SECRET = os.environ.get('ONEDRIVE_CLIENT_SECRET', REF_ONEDRIVE_CLIENT_SECRET)
ONEDRIVE_TENANT_ID = os.environ.get('ONEDRIVE_TENANT_ID', REF_ONEDRIVE_TENANT_ID)
ONEDRIVE_AUTHORITY = f"https://login.microsoftonline.com/{ONEDRIVE_TENANT_ID}" if ONEDRIVE_TENANT_ID != "consumers" else "https://login.microsoftonline.com/consumers"
ONEDRIVE_SCOPES_DELEGATED = ["Mail.ReadWrite", "User.Read"]

msal_app = None
if ONEDRIVE_CLIENT_ID and ONEDRIVE_CLIENT_SECRET:
    app.logger.info(
        f"CFG MSAL: Initializing MSAL ConfidentialClientApplication. ClientID: '{ONEDRIVE_CLIENT_ID[:5]}...', Authority: {ONEDRIVE_AUTHORITY}")
    msal_app = ConfidentialClientApplication(ONEDRIVE_CLIENT_ID, authority=ONEDRIVE_AUTHORITY,
                                             client_credential=ONEDRIVE_CLIENT_SECRET)
else:
    app.logger.warning(
        "CFG MSAL: OneDrive Client ID or Client Secret missing. Email Polling features will be disabled.")

# --- Configuration des Webhooks et Tokens ---
MAKE_SCENARIO_WEBHOOK_URL = os.environ.get("MAKE_SCENARIO_WEBHOOK_URL", REF_MAKE_SCENARIO_WEBHOOK_URL)
app.logger.info(f"CFG WEBHOOK: Make.com webhook URL configured to: {MAKE_SCENARIO_WEBHOOK_URL}")
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
    app.logger.info(f"CFG TOKEN: PROCESS_API_TOKEN (for Make.com calls) configured: '{EXPECTED_API_TOKEN[:5]}...'")
REGISTER_LOCAL_URL_TOKEN = os.environ.get("REGISTER_LOCAL_URL_TOKEN", REF_REGISTER_LOCAL_URL_TOKEN)
if not REGISTER_LOCAL_URL_TOKEN:
    app.logger.warning("CFG TOKEN: REGISTER_LOCAL_URL_TOKEN not set. Local worker registration insecure.")
else:
    app.logger.info(
        f"CFG TOKEN: REGISTER_LOCAL_URL_TOKEN (for local worker registration) configured: '{REGISTER_LOCAL_URL_TOKEN[:5]}...'")
REMOTE_UI_ACCESS_TOKEN_ENV = os.environ.get("REMOTE_UI_ACCESS_TOKEN", REF_REMOTE_UI_ACCESS_TOKEN)
INTERNAL_WORKER_COMMS_TOKEN_ENV = os.environ.get("INTERNAL_WORKER_COMMS_TOKEN", REF_INTERNAL_WORKER_COMMS_TOKEN)


# --- Fonctions Utilitaires MSAL & Refresh Token Management ---
def initialize_refresh_token():
    """Loads the OneDrive refresh token from Redis or ENV at startup."""
    global current_onedrive_refresh_token_in_memory
    loaded_from_source = "nothing (will rely on fresh auth or failure)"

    if redis_client:
        try:
            token_bytes = redis_client.get(ONEDRIVE_REFRESH_TOKEN_REDIS_KEY)
            if token_bytes:
                current_onedrive_refresh_token_in_memory = token_bytes.decode('utf-8')
                loaded_from_source = "Redis"
                app.logger.info(
                    f"MSAL_INIT: OneDrive refresh token loaded from Redis: '...{current_onedrive_refresh_token_in_memory[-20:] if current_onedrive_refresh_token_in_memory else 'EMPTY!'}'.")
        except redis.exceptions.RedisError as e_redis_get:
            app.logger.error(
                f"MSAL_INIT: Error reading refresh token from Redis key '{ONEDRIVE_REFRESH_TOKEN_REDIS_KEY}': {e_redis_get}. Will try ENV.")

    if not current_onedrive_refresh_token_in_memory:
        env_refresh_token = os.environ.get('ONEDRIVE_REFRESH_TOKEN')  # This is the ENV var
        if env_refresh_token:
            current_onedrive_refresh_token_in_memory = env_refresh_token
            loaded_from_source = "environment variable"
            app.logger.info(
                f"MSAL_INIT: OneDrive refresh token loaded from ENV var 'ONEDRIVE_REFRESH_TOKEN': '...{current_onedrive_refresh_token_in_memory[-20:]}'.")
            if redis_client:
                try:
                    redis_client.set(ONEDRIVE_REFRESH_TOKEN_REDIS_KEY, current_onedrive_refresh_token_in_memory)
                    app.logger.info(
                        f"MSAL_INIT: Wrote refresh token from ENV to Redis key '{ONEDRIVE_REFRESH_TOKEN_REDIS_KEY}'.")
                except redis.exceptions.RedisError as e_redis_set:
                    app.logger.error(
                        f"MSAL_INIT: Error writing refresh token from ENV to Redis key '{ONEDRIVE_REFRESH_TOKEN_REDIS_KEY}': {e_redis_set}")
        else:
            app.logger.error(
                "MSAL_INIT: CRITICAL - ONEDRIVE_REFRESH_TOKEN not found in Redis or environment variable. OneDrive/MSAL features requiring authentication will likely fail.")

    app.logger.info(f"MSAL_INIT: OneDrive refresh token ready for use (loaded from: {loaded_from_source}).")


def get_mcal_graph_api_token():
    global current_onedrive_refresh_token_in_memory
    if not msal_app:
        app.logger.error("MSAL: MSAL app (ConfidentialClientApplication) not configured. Cannot get Graph API token.")
        return None

    if not current_onedrive_refresh_token_in_memory:
        app.logger.error(
            "MSAL_TOKEN_ACQ: Current OneDrive refresh token is not available in memory. Attempting re-initialization...")
        initialize_refresh_token()
        if not current_onedrive_refresh_token_in_memory:
            app.logger.error(
                "MSAL_TOKEN_ACQ: Re-initialization failed. No refresh token available. Cannot acquire access token.")
            return None

    app.logger.debug(
        f"MSAL_TOKEN_ACQ: Attempting to acquire token using refresh token from memory: '...{current_onedrive_refresh_token_in_memory[-20:]}'")
    token_result = msal_app.acquire_token_by_refresh_token(
        current_onedrive_refresh_token_in_memory,
        scopes=ONEDRIVE_SCOPES_DELEGATED
    )

    if "access_token" in token_result:
        app.logger.info("MSAL_TOKEN_ACQ: Graph API access token obtained successfully.")

        newly_issued_refresh_token = token_result.get("refresh_token")
        if newly_issued_refresh_token and newly_issued_refresh_token != current_onedrive_refresh_token_in_memory:
            app.logger.warning(
                "MSAL_TOKEN_ACQ: A new refresh token was issued by Microsoft Graph. UPDATING in memory and Redis.")
            app.logger.warning(
                f"MSAL_TOKEN_ACQ: New token: '{newly_issued_refresh_token}' (For manual ENV update if needed as a backup)")
            current_onedrive_refresh_token_in_memory = newly_issued_refresh_token
            if redis_client:
                try:
                    redis_client.set(ONEDRIVE_REFRESH_TOKEN_REDIS_KEY, current_onedrive_refresh_token_in_memory)
                    app.logger.info(
                        f"MSAL_TOKEN_ACQ: Successfully stored new refresh token in Redis key '{ONEDRIVE_REFRESH_TOKEN_REDIS_KEY}': '...{current_onedrive_refresh_token_in_memory[-20:]}'")
                except redis.exceptions.RedisError as e_redis_set_new:
                    app.logger.error(
                        f"MSAL_TOKEN_ACQ: CRITICAL - Failed to store new refresh token in Redis: {e_redis_set_new}.")
            else:
                app.logger.warning(
                    "MSAL_TOKEN_ACQ: Redis client not available. Cannot store new refresh token persistently.")

        return token_result['access_token']
    else:
        error_code = token_result.get("error")
        error_description = token_result.get("error_description")
        app.logger.error(
            f"MSAL_TOKEN_ACQ: Failed to obtain access token. Error: {error_code}, Description: {error_description}. Full response: {token_result}")

        if error_code in ["invalid_grant", "interaction_required", "unauthorized_client"] or \
                (error_description and (
                        "AADSTS70008" in error_description or "token is expired" in error_description.lower())):
            app.logger.error(
                "MSAL_TOKEN_ACQ: The current refresh token is invalid. Manual re-authentication is required.")
            current_onedrive_refresh_token_in_memory = None
            if redis_client:
                try:
                    redis_client.delete(ONEDRIVE_REFRESH_TOKEN_REDIS_KEY)
                    app.logger.info(
                        f"MSAL_TOKEN_ACQ: Invalid refresh token deleted from Redis key '{ONEDRIVE_REFRESH_TOKEN_REDIS_KEY}'.")
                except redis.exceptions.RedisError as e_redis_del:
                    app.logger.error(f"MSAL_TOKEN_ACQ: Error deleting invalid refresh token from Redis: {e_redis_del}")
        return None


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


# --- Fonctions de Polling des Emails ---
def mark_email_as_read_outlook(token_msal, msg_id):
    if not token_msal or not msg_id: return False
    url = f"https://graph.microsoft.com/v1.0/me/messages/{msg_id}"
    headers = {'Authorization': f'Bearer {token_msal}', 'Content-Type': 'application/json'}
    payload = {"isRead": True}
    try:
        response = requests.patch(url, headers=headers, json=payload, timeout=15)
        response.raise_for_status()
        app.logger.info(f"MARK_READ_OUTLOOK: Email {msg_id} marked as read.")
        return True
    except requests.exceptions.RequestException as e:
        app.logger.error(f"MARK_READ_OUTLOOK: API error marking email {msg_id} as read: {e}")
        return False


def check_new_emails_and_trigger_make_webhook():
    """
    Vérifie les nouveaux emails, s'assure que le worker local est joignable,
    puis déclenche le webhook Make.com pour chaque email valide.
    VERSION OPTIMISÉE.
    """
    app.logger.info("POLLER: Email polling cycle started.")
    if not all([SENDER_LIST_FOR_POLLING, MAKE_SCENARIO_WEBHOOK_URL, msal_app]):
        app.logger.error("POLLER: Incomplete config for polling. Aborting cycle.")
        return 0

    token_msal = get_mcal_graph_api_token()
    if not token_msal:
        app.logger.error("POLLER: Failed to get MSAL Graph access token. Aborting cycle.")
        return 0

    triggered_webhook_count = 0
    try:
        # Étape 1 : Construire la requête et récupérer les emails non lus
        since_date_str = (datetime.now(timezone.utc) - timedelta(days=2)).strftime('%Y-%m-%dT%H:%M:%SZ')
        sender_filter_parts = [f"from/emailAddress/address eq '{sender}'" for sender in SENDER_LIST_FOR_POLLING]
        sender_filter_string = " or ".join(sender_filter_parts)
        filter_query = f"isRead eq false and receivedDateTime ge {since_date_str} and ({sender_filter_string})"
        graph_url = (f"https://graph.microsoft.com/v1.0/me/mailFolders/inbox/messages?"
                     f"$filter={filter_query}&$select=id,subject,from,receivedDateTime,bodyPreview&"
                     f"$top=25&$orderby=receivedDateTime asc")

        app.logger.info(f"POLLER: Querying Graph API with filter: '{filter_query}'")
        headers_mail = {'Authorization': f'Bearer {token_msal}', 'Prefer': 'outlook.body-content-type="text"'}

        response = requests.get(graph_url, headers=headers_mail, timeout=45)
        response.raise_for_status()
        emails = response.json().get('value', [])

        app.logger.info(f"POLLER: Found {len(emails)} unread email(s) matching criteria.")

        # S'il n'y a rien à faire, on sort tôt.
        if not emails:
            return 0

        # --- NOUVELLE LOGIQUE OPTIMISÉE ---
        # Étape 2 : Vérifier la santé du worker UNE SEULE FOIS si des emails sont trouvés.
        if not is_local_worker_alive():
            app.logger.warning(
                f"POLLER: Worker local injoignable. Le traitement du lot de {len(emails)} email(s) est reporté. Ils resteront non lus."
            )
            # On arrête tout de suite, sans boucler, pour réessayer l'ensemble du lot plus tard.
            return 0

        app.logger.info("POLLER: Worker local is alive. Proceeding with email batch processing.")
        # --- FIN DE LA NOUVELLE LOGIQUE ---

        # Étape 3 : Traiter chaque email du lot
        for mail in emails:
            mail_id = mail['id']
            mail_subject = mail.get('subject', 'N/A_Subject')

            if is_email_id_processed_redis(mail_id):
                app.logger.debug(
                    f"POLLER: Email ID {mail_id} (Subj: '{mail_subject[:30]}...') is already processed. Marking as read to clean up inbox.")
                mark_email_as_read_outlook(token_msal, mail_id)
                continue

            # La vérification de la santé du worker a déjà été faite, on peut donc traiter l'email.
            payload_for_make = {
                "microsoft_graph_email_id": mail_id,
                "subject": mail_subject,
                "receivedDateTime": mail.get("receivedDateTime"),
                "sender_address": mail.get('from', {}).get('emailAddress', {}).get('address', 'N/A'),
                "bodyPreview": mail.get('bodyPreview', '')
            }

            try:
                webhook_response = requests.post(MAKE_SCENARIO_WEBHOOK_URL, json=payload_for_make, timeout=30)
                if webhook_response.status_code == 200 and "accepted" in webhook_response.text.lower():
                    app.logger.info(f"POLLER: Make.com webhook triggered successfully for email {mail_id}.")

                    if mark_email_id_as_processed_redis(mail_id):
                        triggered_webhook_count += 1
                        mark_email_as_read_outlook(token_msal, mail_id)
                    else:
                        app.logger.error(
                            f"POLLER: CRITICAL - Failed to mark email {mail_id} as processed in Redis. It will be re-processed in the next cycle, causing potential duplicates.")
                        # On ne le marque pas comme lu pour attirer l'attention sur ce problème.
                else:
                    app.logger.error(
                        f"POLLER: Make.com webhook call FAILED for email {mail_id}. Status: {webhook_response.status_code}, Response: {webhook_response.text[:200]}")
                    # On ne marque pas comme traité/lu, pour que l'échec soit ré-essayé plus tard.

            except requests.exceptions.RequestException as e_webhook:
                app.logger.error(f"POLLER: Exception during Make.com webhook call for email {mail_id}: {e_webhook}")
                # En cas d'erreur de communication avec Make, on ne fait rien de plus. L'email restera non lu
                # et sera ré-essayé au prochain cycle. On passe simplement à l'email suivant du lot.
                continue

        return triggered_webhook_count

    except requests.exceptions.RequestException as e_graph:
        app.logger.error(f"POLLER: Graph API request failed: {e_graph}")
    except Exception as e_general:
        app.logger.error(f"POLLER: Unexpected error in polling cycle: {e_general}", exc_info=True)

    return triggered_webhook_count


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
                if not all(
                        [current_onedrive_refresh_token_in_memory, SENDER_LIST_FOR_POLLING, MAKE_SCENARIO_WEBHOOK_URL]):
                    app.logger.warning(f"BG_POLLER: Essential config for polling is incomplete. Waiting 60s.")
                    time.sleep(60)
                    continue

                webhooks_triggered = check_new_emails_and_trigger_make_webhook()
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


def is_local_worker_alive():
    """
    Vérifie si le worker local est joignable en appelant son endpoint de ping.
    Renvoie True si le worker est joignable, False sinon.
    """
    app.logger.info("WORKER_CHECK: Vérification du statut du worker local.")
    localtunnel_url = None

    # Étape 1 : Récupérer l'URL du worker (depuis Redis ou fichier)
    try:
        if redis_client:
            url_bytes = redis_client.get(LOCALTUNNEL_URL_REDIS_KEY)
            if url_bytes:
                localtunnel_url = url_bytes.decode('utf-8')
        if not localtunnel_url and LOCALTUNNEL_URL_FILE.exists():
            with open(LOCALTUNNEL_URL_FILE, "r") as f:
                localtunnel_url = f.read().strip()
    except Exception as e_url:
        app.logger.error(f"WORKER_CHECK: Erreur lors de la récupération de l'URL du worker: {e_url}")
        return False

    if not localtunnel_url:
        app.logger.warning("WORKER_CHECK: Worker local non enregistré (aucune URL trouvée).")
        return False

    # Étape 2 : Tenter de "pinger" le worker
    # On utilise un endpoint léger qui doit exister sur le worker.
    # Assurez-vous que vos workers (app_new.py/app_ubuntu.py) ont une route /api/ping.
    try:
        # On assume que les workers ont un endpoint /api/ping
        target_url = f"{localtunnel_url.rstrip('/')}/api/ping"
        headers = {'X-Worker-Token': INTERNAL_WORKER_COMMS_TOKEN_ENV} if INTERNAL_WORKER_COMMS_TOKEN_ENV else {}

        # Timeout très court (5s) car un ping doit être rapide
        response = requests.get(target_url, headers=headers, timeout=5)

        if response.status_code == 200:
            app.logger.info(f"WORKER_CHECK: Le worker à l'URL '{localtunnel_url}' est joignable.")
            return True
        else:
            app.logger.warning(
                f"WORKER_CHECK: Le worker a répondu mais avec un statut d'erreur {response.status_code}.")
            return False

    except requests.exceptions.RequestException as e:
        app.logger.error(f"WORKER_CHECK: Impossible de contacter le worker à l'URL '{localtunnel_url}'. Erreur: {e}")
        return False

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
@app.route('/api/register_local_downloader_url', methods=['POST'])
def register_local_downloader_url():
    received_token = request.headers.get('X-Register-Token')
    if REGISTER_LOCAL_URL_TOKEN and received_token != REGISTER_LOCAL_URL_TOKEN:
        return jsonify({"status": "error", "message": "Unauthorized"}), 401
    data = request.get_json(silent=True)
    if not data: return jsonify({"status": "error", "message": "Invalid JSON"}), 400
    new_lt_url = data.get('localtunnel_url')

    try:
        storage_method = "Redis" if redis_client else "fallback file"
        if redis_client:
            if new_lt_url:
                redis_client.set(LOCALTUNNEL_URL_REDIS_KEY, new_lt_url)
            else:
                redis_client.delete(LOCALTUNNEL_URL_REDIS_KEY)
        else:
            if new_lt_url:
                with open(LOCALTUNNEL_URL_FILE, "w") as f:
                    f.write(new_lt_url)
            elif LOCALTUNNEL_URL_FILE.exists():
                LOCALTUNNEL_URL_FILE.unlink()
        msg_action = "registered" if new_lt_url else "cleared"
        app.logger.info(f"API_REG_LT_URL: Localtunnel URL {msg_action} via {storage_method}.")
        return jsonify({"status": "success", "message": f"URL {msg_action}."}), 200
    except Exception as e:
        app.logger.error(f"API_REG_LT_URL: Server error: {e}", exc_info=True)
        return jsonify({"status": "error", "message": "Server error."}), 500


@app.route('/api/get_local_downloader_url', methods=['GET'])
def get_local_downloader_url_for_make():
    received_token = request.headers.get('X-API-Token')
    if EXPECTED_API_TOKEN and received_token != EXPECTED_API_TOKEN:
        return jsonify({"status": "error", "message": "Unauthorized"}), 401
    lt_url = None
    try:
        if redis_client:
            url_bytes = redis_client.get(LOCALTUNNEL_URL_REDIS_KEY)
            if url_bytes: lt_url = url_bytes.decode('utf-8')
        if not lt_url and LOCALTUNNEL_URL_FILE.exists():
            with open(LOCALTUNNEL_URL_FILE, "r") as f: lt_url = f.read().strip()

        if lt_url:
            return jsonify({"status": "success", "localtunnel_url": lt_url}), 200
        else:
            return jsonify({"status": "error", "message": "Local worker URL not registered."}), 404
    except Exception as e:
        app.logger.error(f"API_GET_LT_URL: Error: {e}", exc_info=True)
        return jsonify({"status": "error", "message": "Server error."}), 500


@app.route('/api/log_processed_url', methods=['POST'])
def api_log_processed_url():
    if request.headers.get('X-API-Token') != EXPECTED_API_TOKEN:
        return jsonify({"status": "error", "message": "Unauthorized."}), 401
    data = request.get_json(silent=True)
    if not data or 'dropbox_url' not in data: return jsonify(
        {"status": "error", "message": "'dropbox_url' required."}), 400
    if not redis_client:
        return jsonify({"status": "error", "message": "Redis service unavailable."}), 503
    redis_client.sadd(PROCESSED_DROPBOX_URLS_REDIS_KEY, data['dropbox_url'])
    return jsonify({"status": "success"}), 200


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
    return send_from_directory(app.root_path, 'trigger_page.html')


@app.route('/api/get_local_status', methods=['GET'])
@login_required
def get_local_status_proxied():
    app.logger.info(f"PROXY_STATUS: /api/get_local_status par l'utilisateur '{current_user.id}'.")

    localtunnel_url = None
    try:
        if redis_client:
            url_bytes = redis_client.get(LOCALTUNNEL_URL_REDIS_KEY)
            if url_bytes:
                localtunnel_url = url_bytes.decode('utf-8')
        if not localtunnel_url and LOCALTUNNEL_URL_FILE.exists():
            with open(LOCALTUNNEL_URL_FILE, "r") as f:
                localtunnel_url = f.read().strip()
    except Exception as e_url:
        app.logger.error(f"PROXY_STATUS: Erreur lecture URL du worker: {e_url}")
        # On continue, l'absence d'URL sera gérée plus bas
        pass

    if not localtunnel_url:
        return jsonify({
            "overall_status_text": "Worker Indisponible",
            "status_text": "L'URL du worker local n'est pas enregistrée.",
            "overall_status_code_from_worker": "worker_unavailable"
        }), 503

    try:
        target_url = f"{localtunnel_url.rstrip('/')}/api/get_remote_status_summary"
        headers_to_worker = {
            'X-Worker-Token': INTERNAL_WORKER_COMMS_TOKEN_ENV} if INTERNAL_WORKER_COMMS_TOKEN_ENV else {}

        response_local = requests.get(target_url, headers=headers_to_worker, timeout=10)
        response_local.raise_for_status()

        local_data = response_local.json()

        # --- BLOC DE MAPPAGE CORRIGÉ ---
        # On traduit ici les clés du worker en clés attendues par le JavaScript.
        response_for_frontend = {
            "overall_status_text": local_data.get("overall_status_text_display", "Statut non défini"),
            "status_text": local_data.get("status_text_detail", "Détails non disponibles"),
            "overall_status_code_from_worker": local_data.get("overall_status_code"),
            "current_step_name": local_data.get("current_step_name"),
            "progress_current": local_data.get("progress_current", 0),
            "progress_total": local_data.get("progress_total", 0),
            "recent_downloads": local_data.get("recent_downloads", []),
            "last_sequence_summary": local_data.get("last_sequence_summary")
        }
        return jsonify(response_for_frontend), 200
        # --- FIN DU BLOC DE MAPPAGE ---

    except requests.exceptions.HTTPError as e:
        # Gérer les erreurs HTTP comme 401, 404, etc.
        error_code = e.response.status_code
        app.logger.error(f"PROXY_STATUS: Erreur HTTP {error_code} du worker: {e}")
        return jsonify({
            "overall_status_text": f"Erreur Worker ({error_code})",
            "status_text": f"Le worker a répondu avec une erreur: {e.response.reason}",
            "overall_status_code_from_worker": f"worker_http_error_{error_code}"
        }), 502

    except requests.exceptions.RequestException as e:
        # Gérer les erreurs de connexion, timeout, etc.
        app.logger.error(f"PROXY_STATUS: Erreur de communication avec le worker local: {e}")
        return jsonify({
            "overall_status_text": "Erreur Proxy",
            "status_text": "Impossible de contacter le worker local.",
            "overall_status_code_from_worker": "proxy_connection_error"
        }), 502


@app.route('/api/trigger_local_workflow', methods=['POST'])
@login_required
def trigger_local_workflow_authed():
    app.logger.info(f"LOCAL_TRIGGER_API: Appelé par l'utilisateur '{current_user.id}'.")
    payload = request.json or {"command": "start_manual_generic_from_ui"}
    payload.setdefault("triggered_by_user", current_user.id)
    payload.setdefault("timestamp_utc", datetime.now(timezone.utc).isoformat())
    try:
        with open(TRIGGER_SIGNAL_FILE, "w") as f:
            json.dump(payload, f)
        return jsonify({"status": "ok", "message": "Signal envoyé."}), 200
    except Exception as e:
        app.logger.error(f"LOCAL_TRIGGER_API: Erreur écriture signal: {e}", exc_info=True)
        return jsonify({"status": "error", "message": "Erreur serveur."}), 500


@app.route('/api/check_emails_and_download', methods=['POST'])
@login_required
def api_check_emails_and_download_authed():
    app.logger.info(f"API_EMAIL_CHECK: Déclenchement manuel par '{current_user.id}'.")

    def run_task():
        with app.app_context():
            check_new_emails_and_trigger_make_webhook()

    if not all(
            [msal_app, current_onedrive_refresh_token_in_memory, SENDER_LIST_FOR_POLLING, MAKE_SCENARIO_WEBHOOK_URL]):
        return jsonify({"status": "error", "message": "Config serveur email incomplète."}), 503
    threading.Thread(target=run_task).start()
    return jsonify({"status": "success", "message": "Vérification en arrière-plan lancée."}), 202


# La fonction de démarrage des tâches reste ici, mais elle ne sera appelée que par Gunicorn ou par le __main__
def start_background_tasks():
    """
    Fonction qui initialise et démarre les threads d'arrière-plan.
    """
    app.logger.info("BACKGROUND_TASKS: Initialisation des tâches...")
    initialize_refresh_token()

    # On vérifie si toutes les conditions sont remplies pour lancer le thread.
    if all([msal_app, current_onedrive_refresh_token_in_memory, SENDER_LIST_FOR_POLLING, MAKE_SCENARIO_WEBHOOK_URL]):
        email_poller_thread = threading.Thread(target=background_email_poller, name="EmailPollerThread", daemon=True)
        email_poller_thread.start()
        app.logger.info("BACKGROUND_TASKS: Thread de polling des emails démarré.")
    else:
        # Log détaillé si le thread ne peut pas démarrer
        missing_configs = []
        if not msal_app: missing_configs.append("MSAL app non initialisée")
        if not current_onedrive_refresh_token_in_memory: missing_configs.append("Refresh Token manquant")
        if not SENDER_LIST_FOR_POLLING: missing_configs.append("Liste des expéditeurs vide")
        if not MAKE_SCENARIO_WEBHOOK_URL: missing_configs.append("URL du webhook manquante")
        app.logger.warning(
            f"BACKGROUND_TASKS: Thread de polling non démarré. Configuration incomplète : {', '.join(missing_configs)}")


# Le code ici est exécuté UNE SEULE FOIS par Gunicorn dans le processus maître
# avant la création des workers. C'est l'endroit parfait pour lancer notre tâche unique.
start_background_tasks()

# Ce bloc ne sera JAMAIS exécuté par Gunicorn, mais il est utile pour le débogage local
if __name__ == '__main__':
    app.logger.info(f"MAIN_APP: (Lancement direct pour débogage local)")
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 10000)))
