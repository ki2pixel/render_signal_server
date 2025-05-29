from flask import Flask, jsonify, request, send_from_directory
from flask_httpauth import HTTPBasicAuth
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

app = Flask(__name__)
auth = HTTPBasicAuth()

# --- Tokens and Config de référence (basés sur l'image/description fournie) ---
# (These remain the same as your previous version)
REF_TRIGGER_PAGE_USER = "admin"
REF_TRIGGER_PAGE_PASSWORD = "UDPVA#esKf40r@"
REF_REMOTE_UI_ACCESS_TOKEN = "0wbgXHiF3e!MqE"
REF_INTERNAL_WORKER_COMMS_TOKEN = "Fn*G14Vb'!Hkra7"
REF_PROCESS_API_TOKEN = "rnd_PW5cGYVf4g131imu9cYkFw27u8dY"
REF_REGISTER_LOCAL_URL_TOKEN = "WMmWti@^n6RaUA"
REF_ONEDRIVE_CLIENT_ID = "6bbc767d-53e8-4b82-bd49-480d4c157a9b"
REF_ONEDRIVE_CLIENT_SECRET = "3Ah8Q~M7wk954ttbQRkt-xHn80enAeHd5wHG1XoEu" # Placeholder
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
    # app.logger might not be fully configured yet if this runs too early.
    logging.warning("CFG REDIS (module level): 'redis' Python library not installed. Redis-based features will be disabled or use fallbacks.")


# --- Configuration des Identifiants pour la page de trigger ---
# (Identical to previous version)
TRIGGER_PAGE_USER_ENV = os.environ.get("TRIGGER_PAGE_USER", REF_TRIGGER_PAGE_USER)
TRIGGER_PAGE_PASSWORD_ENV = os.environ.get("TRIGGER_PAGE_PASSWORD", REF_TRIGGER_PAGE_PASSWORD)
users = {}
if TRIGGER_PAGE_USER_ENV and TRIGGER_PAGE_PASSWORD_ENV:
    users[TRIGGER_PAGE_USER_ENV] = TRIGGER_PAGE_PASSWORD_ENV
    app.logger.info(f"CFG AUTH: Trigger page user '{TRIGGER_PAGE_USER_ENV}' configured for HTTP Basic Auth.")
else:
    app.logger.warning("CFG AUTH: TRIGGER_PAGE_USER or TRIGGER_PAGE_PASSWORD not set. HTTP Basic Auth for trigger page will NOT be enforced actively.")

@auth.verify_password
def verify_password(username, password):
    if not users: 
        app.logger.debug("AUTH: No users configured for HTTP Basic Auth, access granted by default.")
        return "anonymous_or_no_auth_user" 
    user_stored_password = users.get(username)
    if user_stored_password and user_stored_password == password:
        app.logger.info(f"AUTH: User '{username}' authenticated successfully via HTTP Basic Auth.")
        return username
    app.logger.warning(f"AUTH: HTTP Basic Authentication failed for user '{username}'.")
    return None

# --- Configuration du Polling des Emails ---
# (Identical to previous version)
POLLING_TIMEZONE_STR = os.environ.get("POLLING_TIMEZONE", REF_POLLING_TIMEZONE)
POLLING_ACTIVE_START_HOUR = int(os.environ.get("POLLING_ACTIVE_START_HOUR", REF_POLLING_ACTIVE_START_HOUR))
POLLING_ACTIVE_END_HOUR = int(os.environ.get("POLLING_ACTIVE_END_HOUR", REF_POLLING_ACTIVE_END_HOUR)) 
POLLING_ACTIVE_DAYS_RAW = os.environ.get("POLLING_ACTIVE_DAYS", REF_POLLING_ACTIVE_DAYS) 
POLLING_ACTIVE_DAYS = []
if POLLING_ACTIVE_DAYS_RAW:
    try:
        POLLING_ACTIVE_DAYS = [int(d.strip()) for d in POLLING_ACTIVE_DAYS_RAW.split(',') if d.strip().isdigit() and 0 <= int(d.strip()) <= 6]
    except ValueError:
        app.logger.warning(f"CFG POLL: Invalid POLLING_ACTIVE_DAYS ('{POLLING_ACTIVE_DAYS_RAW}'). Using default Mon-Fri.")
        POLLING_ACTIVE_DAYS = [0,1,2,3,4]
if not POLLING_ACTIVE_DAYS: POLLING_ACTIVE_DAYS = [0,1,2,3,4]
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
EMAIL_POLLING_INTERVAL_SECONDS = int(os.environ.get("EMAIL_POLLING_INTERVAL_SECONDS", REF_EMAIL_POLLING_INTERVAL_SECONDS))
POLLING_INACTIVE_CHECK_INTERVAL_SECONDS = int(os.environ.get("POLLING_INACTIVE_CHECK_INTERVAL_SECONDS", 600))
app.logger.info(f"CFG POLL: Active polling interval: {EMAIL_POLLING_INTERVAL_SECONDS}s. Inactive period check interval: {POLLING_INACTIVE_CHECK_INTERVAL_SECONDS}s.")
app.logger.info(f"CFG POLL: Active schedule ({POLLING_TIMEZONE_STR}): {POLLING_ACTIVE_START_HOUR:02d}:00-{POLLING_ACTIVE_END_HOUR:02d}:00. Days (0=Mon): {POLLING_ACTIVE_DAYS}")

# --- Chemins et Fichiers (Mainly for trigger signal, Localtunnel URL fallback) ---
SIGNAL_DIR = Path(os.environ.get("RENDER_DISC_PATH", "./signal_data_app_render"))
TRIGGER_SIGNAL_FILE = SIGNAL_DIR / "local_workflow_trigger_signal.json"
LOCALTUNNEL_URL_FILE = SIGNAL_DIR / "current_localtunnel_url.txt" # Fallback file for LT URL
SIGNAL_DIR.mkdir(parents=True, exist_ok=True)
app.logger.info(f"CFG PATH: Signal directory for ephemeral files: {SIGNAL_DIR.resolve()}")

# --- Configuration Redis ---
REDIS_URL = os.environ.get('REDIS_URL')
redis_client = None
LOCALTUNNEL_URL_REDIS_KEY = "current_localtunnel_url_v1"
PROCESSED_EMAIL_IDS_REDIS_KEY = "processed_email_ids_set_v1"
PROCESSED_DROPBOX_URLS_REDIS_KEY = "processed_dropbox_urls_set_v1"
ONEDRIVE_REFRESH_TOKEN_REDIS_KEY = "onedrive_current_refresh_token_v1" # NEW KEY

current_onedrive_refresh_token_in_memory = None # Global var for the current refresh token

if REDIS_AVAILABLE and REDIS_URL:
    try:
        redis_client = redis.from_url(REDIS_URL, socket_connect_timeout=5, socket_timeout=5, health_check_interval=30)
        redis_client.ping()
        app.logger.info(f"CFG REDIS: Successfully connected to Redis at {REDIS_URL.split('@')[-1] if '@' in REDIS_URL else REDIS_URL}.")
    except redis.exceptions.ConnectionError as e_redis:
        app.logger.error(f"CFG REDIS: Could not connect to Redis. Error: {e_redis}. Redis-dependent features will be impaired or use fallbacks.")
        redis_client = None
    except Exception as e_redis_other:
        app.logger.error(f"CFG REDIS: An unexpected error occurred during Redis initialization: {e_redis_other}. Redis-dependent features will be impaired or use fallbacks.")
        redis_client = None
elif REDIS_AVAILABLE and not REDIS_URL:
    app.logger.warning("CFG REDIS: REDIS_URL not set, but 'redis' library is available. Redis will not be used for primary storage; fallbacks may apply.")
    redis_client = None
else: # REDIS_AVAILABLE is False
    app.logger.warning("CFG REDIS: 'redis' Python library not installed. Redis will not be used; fallbacks may apply.")
    redis_client = None

# --- Configuration OneDrive / MSAL ---
ONEDRIVE_CLIENT_ID = os.environ.get('ONEDRIVE_CLIENT_ID', REF_ONEDRIVE_CLIENT_ID)
ONEDRIVE_CLIENT_SECRET = os.environ.get('ONEDRIVE_CLIENT_SECRET', REF_ONEDRIVE_CLIENT_SECRET)
# ONEDRIVE_REFRESH_TOKEN from ENV is now primarily a seed/backup, managed by `initialize_refresh_token`
ONEDRIVE_TENANT_ID = os.environ.get('ONEDRIVE_TENANT_ID', REF_ONEDRIVE_TENANT_ID)
ONEDRIVE_AUTHORITY = f"https://login.microsoftonline.com/{ONEDRIVE_TENANT_ID}" if ONEDRIVE_TENANT_ID != "consumers" else "https://login.microsoftonline.com/consumers"
ONEDRIVE_SCOPES_DELEGATED = ["Mail.ReadWrite", "User.Read"] 

msal_app = None
if ONEDRIVE_CLIENT_ID and ONEDRIVE_CLIENT_SECRET:
    app.logger.info(f"CFG MSAL: Initializing MSAL ConfidentialClientApplication. ClientID: '{ONEDRIVE_CLIENT_ID[:5]}...', Authority: {ONEDRIVE_AUTHORITY}")
    msal_app = ConfidentialClientApplication(ONEDRIVE_CLIENT_ID, authority=ONEDRIVE_AUTHORITY, client_credential=ONEDRIVE_CLIENT_SECRET)
else:
    app.logger.warning("CFG MSAL: OneDrive Client ID or Client Secret missing. Email Polling features will be disabled.")

# --- Configuration des Webhooks et Tokens ---
# (Identical to previous version)
MAKE_SCENARIO_WEBHOOK_URL = os.environ.get("MAKE_SCENARIO_WEBHOOK_URL", REF_MAKE_SCENARIO_WEBHOOK_URL)
SENDER_OF_INTEREST_FOR_POLLING_RAW = os.environ.get("SENDER_OF_INTEREST_FOR_POLLING", REF_SENDER_OF_INTEREST_FOR_POLLING)
SENDER_LIST_FOR_POLLING = [e.strip().lower() for e in SENDER_OF_INTEREST_FOR_POLLING_RAW.split(',') if e.strip()] if SENDER_OF_INTEREST_FOR_POLLING_RAW else []
if SENDER_LIST_FOR_POLLING: app.logger.info(f"CFG POLL: Monitoring emails from {len(SENDER_LIST_FOR_POLLING)} senders: {SENDER_LIST_FOR_POLLING}")
else: app.logger.warning("CFG POLL: SENDER_OF_INTEREST_FOR_POLLING not set. Email polling likely ineffective.")
EXPECTED_API_TOKEN = os.environ.get("PROCESS_API_TOKEN", REF_PROCESS_API_TOKEN) 
if not EXPECTED_API_TOKEN: app.logger.warning("CFG TOKEN: PROCESS_API_TOKEN not set. API endpoints called by Make.com will be insecure.")
else: app.logger.info(f"CFG TOKEN: PROCESS_API_TOKEN (for Make.com calls) configured: '{EXPECTED_API_TOKEN[:5]}...'")
REGISTER_LOCAL_URL_TOKEN = os.environ.get("REGISTER_LOCAL_URL_TOKEN", REF_REGISTER_LOCAL_URL_TOKEN)
if not REGISTER_LOCAL_URL_TOKEN: app.logger.warning("CFG TOKEN: REGISTER_LOCAL_URL_TOKEN not set. Local worker registration insecure.")
else: app.logger.info(f"CFG TOKEN: REGISTER_LOCAL_URL_TOKEN (for local worker registration) configured: '{REGISTER_LOCAL_URL_TOKEN[:5]}...'")
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
                app.logger.info(f"MSAL_INIT: OneDrive refresh token loaded from Redis: '...{current_onedrive_refresh_token_in_memory[-20:] if current_onedrive_refresh_token_in_memory else 'EMPTY!'}'.")
        except redis.exceptions.RedisError as e_redis_get:
            app.logger.error(f"MSAL_INIT: Error reading refresh token from Redis key '{ONEDRIVE_REFRESH_TOKEN_REDIS_KEY}': {e_redis_get}. Will try ENV.")
    
    if not current_onedrive_refresh_token_in_memory:
        env_refresh_token = os.environ.get('ONEDRIVE_REFRESH_TOKEN') # This is the ENV var
        if env_refresh_token:
            current_onedrive_refresh_token_in_memory = env_refresh_token
            loaded_from_source = "environment variable"
            app.logger.info(f"MSAL_INIT: OneDrive refresh token loaded from ENV var 'ONEDRIVE_REFRESH_TOKEN': '...{current_onedrive_refresh_token_in_memory[-20:]}'.")
            # If loaded from ENV and Redis is available, store it in Redis
            if redis_client:
                try:
                    redis_client.set(ONEDRIVE_REFRESH_TOKEN_REDIS_KEY, current_onedrive_refresh_token_in_memory)
                    app.logger.info(f"MSAL_INIT: Wrote refresh token from ENV to Redis key '{ONEDRIVE_REFRESH_TOKEN_REDIS_KEY}'.")
                except redis.exceptions.RedisError as e_redis_set:
                     app.logger.error(f"MSAL_INIT: Error writing refresh token from ENV to Redis key '{ONEDRIVE_REFRESH_TOKEN_REDIS_KEY}': {e_redis_set}")
        else:
            app.logger.error("MSAL_INIT: CRITICAL - ONEDRIVE_REFRESH_TOKEN not found in Redis or environment variable. OneDrive/MSAL features requiring authentication will likely fail.")
            # current_onedrive_refresh_token_in_memory remains None
    
    app.logger.info(f"MSAL_INIT: OneDrive refresh token ready for use (loaded from: {loaded_from_source}).")

def get_mcal_graph_api_token():
    global current_onedrive_refresh_token_in_memory
    if not msal_app:
        app.logger.error("MSAL: MSAL app (ConfidentialClientApplication) not configured. Cannot get Graph API token.")
        return None
    
    if not current_onedrive_refresh_token_in_memory:
        app.logger.error("MSAL_TOKEN_ACQ: Current OneDrive refresh token is not available in memory. Attempting re-initialization...")
        initialize_refresh_token() # Attempt to load it again, e.g. if ENV var was updated after start
        if not current_onedrive_refresh_token_in_memory:
            app.logger.error("MSAL_TOKEN_ACQ: Re-initialization failed. No refresh token available. Cannot acquire access token.")
            return None
            
    app.logger.debug(f"MSAL_TOKEN_ACQ: Attempting to acquire token using refresh token from memory: '...{current_onedrive_refresh_token_in_memory[-20:]}'")
    token_result = msal_app.acquire_token_by_refresh_token(
        current_onedrive_refresh_token_in_memory,
        scopes=ONEDRIVE_SCOPES_DELEGATED
    )
    
    if "access_token" in token_result:
        app.logger.info("MSAL_TOKEN_ACQ: Graph API access token obtained successfully.")
        
        newly_issued_refresh_token = token_result.get("refresh_token")
        if newly_issued_refresh_token and newly_issued_refresh_token != current_onedrive_refresh_token_in_memory:
            app.logger.warning("MSAL_TOKEN_ACQ: A new refresh token was issued by Microsoft Graph. UPDATING in memory and Redis.")
            app.logger.warning(f"MSAL_TOKEN_ACQ: New token: '{newly_issued_refresh_token}' (For manual ENV update if needed as a backup)")
            
            current_onedrive_refresh_token_in_memory = newly_issued_refresh_token # Update in-memory cache
            
            if redis_client:
                try:
                    redis_client.set(ONEDRIVE_REFRESH_TOKEN_REDIS_KEY, current_onedrive_refresh_token_in_memory)
                    app.logger.info(f"MSAL_TOKEN_ACQ: Successfully stored new refresh token in Redis key '{ONEDRIVE_REFRESH_TOKEN_REDIS_KEY}': '...{current_onedrive_refresh_token_in_memory[-20:]}'")
                except redis.exceptions.RedisError as e_redis_set_new:
                    app.logger.error(f"MSAL_TOKEN_ACQ: CRITICAL - Failed to store new refresh token in Redis: {e_redis_set_new}. Subsequent calls might fail after service restart if ENV var 'ONEDRIVE_REFRESH_TOKEN' is not updated manually.")
            else:
                app.logger.warning("MSAL_TOKEN_ACQ: Redis client not available. Cannot store new refresh token persistently. Manual update of ENV var 'ONEDRIVE_REFRESH_TOKEN' is CRUCIAL.")
                
        return token_result['access_token']
    else:
        error_code = token_result.get("error")
        error_description = token_result.get("error_description")
        app.logger.error(f"MSAL_TOKEN_ACQ: Failed to obtain access token. Error: {error_code}, Description: {error_description}. Full response: {token_result}")
        
        # Handle invalid_grant specifically: the refresh token is likely dead.
        if error_code in ["invalid_grant", "interaction_required", "unauthorized_client"] or \
           (error_description and ("AADSTS70008" in error_description or "token is expired" in error_description.lower())): # AADSTS70008: The provided authorization code or refresh token is expired or malformed.
            app.logger.error("MSAL_TOKEN_ACQ: The current refresh token is invalid (e.g., expired, revoked). Clearing from memory and Redis (if used). Manual re-authentication and update of ONEDRIVE_REFRESH_TOKEN ENV variable is required.")
            current_onedrive_refresh_token_in_memory = None # Clear from memory
            if redis_client:
                try:
                    redis_client.delete(ONEDRIVE_REFRESH_TOKEN_REDIS_KEY)
                    app.logger.info(f"MSAL_TOKEN_ACQ: Invalid refresh token deleted from Redis key '{ONEDRIVE_REFRESH_TOKEN_REDIS_KEY}'.")
                except redis.exceptions.RedisError as e_redis_del:
                    app.logger.error(f"MSAL_TOKEN_ACQ: Error deleting invalid refresh token from Redis key '{ONEDRIVE_REFRESH_TOKEN_REDIS_KEY}': {e_redis_del}")
        return None

# --- Fonctions de Déduplication avec Redis ---
# (Identical to previous corrected version)
def is_email_id_processed_redis(email_id):
    if not redis_client:
        app.logger.warning("REDIS_DEDUP: Redis client not available for is_email_id_processed_redis. Assuming NOT processed.")
        return False 
    try:
        is_member = redis_client.sismember(PROCESSED_EMAIL_IDS_REDIS_KEY, email_id)
        app.logger.debug(f"REDIS_DEDUP: Checked for email ID '{email_id}'. Is processed: {is_member}.")
        return is_member
    except redis.exceptions.RedisError as e_redis:
        app.logger.error(f"REDIS_DEDUP: Error checking if email ID '{email_id}' is in set '{PROCESSED_EMAIL_IDS_REDIS_KEY}': {e_redis}. Assuming NOT processed to be safe.")
        return False 

def mark_email_id_as_processed_redis(email_id):
    if not redis_client:
        app.logger.warning(f"REDIS_DEDUP: Redis client not available for mark_email_id_as_processed_redis. Cannot mark email ID '{email_id}'.")
        return False
    try:
        result = redis_client.sadd(PROCESSED_EMAIL_IDS_REDIS_KEY, email_id) 
        result_text = "newly added" if result == 1 else "already existed"
        app.logger.info(f"REDIS_DEDUP: Email ID '{email_id}' processed in Redis set '{PROCESSED_EMAIL_IDS_REDIS_KEY}'. Status: {result_text} (sadd command returned: {result}).")
        return True
    except redis.exceptions.RedisError as e_redis:
        app.logger.error(f"REDIS_DEDUP: Error adding email ID '{email_id}' to set '{PROCESSED_EMAIL_IDS_REDIS_KEY}': {e_redis}")
        return False

# --- Fonctions de Polling des Emails ---
# (Identical to previous version, uses get_mcal_graph_api_token)
def mark_email_as_read_outlook(token_msal, msg_id):
    if not token_msal or not msg_id:
        app.logger.error("MARK_READ_OUTLOOK: MSAL Token or Email ID missing for marking as read.")
        return False
    url = f"https://graph.microsoft.com/v1.0/me/messages/{msg_id}"
    headers = {'Authorization': f'Bearer {token_msal}', 'Content-Type': 'application/json'}
    payload = {"isRead": True}
    try:
        response = requests.patch(url, headers=headers, json=payload, timeout=15)
        response.raise_for_status()
        app.logger.info(f"MARK_READ_OUTLOOK: Email {msg_id} marked as read in Outlook.")
        return True
    except requests.exceptions.RequestException as e:
        app.logger.error(f"MARK_READ_OUTLOOK: API error marking email {msg_id} as read in Outlook: {e}")
        if hasattr(e, 'response') and e.response is not None:
            app.logger.error(f"MARK_READ_OUTLOOK: API Response: {e.response.status_code} - {e.response.text[:200]}")
        return False

def check_new_emails_and_trigger_make_webhook():
    app.logger.info("POLLER: Email polling cycle started (using Redis for deduplication).")
    if not SENDER_LIST_FOR_POLLING:
        app.logger.warning("POLLER: SENDER_LIST_FOR_POLLING is empty. Email polling will be ineffective.")
        return 0
    if not MAKE_SCENARIO_WEBHOOK_URL:
        app.logger.error("POLLER: MAKE_SCENARIO_WEBHOOK_URL not configured. Cannot trigger Make.com.")
        return 0
    
    token_msal = None # Will hold the MSAL Graph API token
    if msal_app: # Check if MSAL client was initialized
        if not current_onedrive_refresh_token_in_memory: # Check if we have a refresh token to use
            app.logger.error("POLLER: No OneDrive refresh token available in memory. Attempting re-initialization for polling cycle.")
            initialize_refresh_token() # Try to load/reload it
            if not current_onedrive_refresh_token_in_memory:
                 app.logger.error("POLLER: Still no OneDrive refresh token after re-init. Email polling cycle aborted.")
                 return 0
        
        token_msal = get_mcal_graph_api_token() # This now uses the managed refresh token
        if not token_msal:
            app.logger.error("POLLER: Failed to get MSAL Graph access token. Email polling cycle aborted as email reading will fail.")
            return 0 
    else:
        app.logger.warning("POLLER: MSAL app (ConfidentialClientApplication) not configured. Cannot read emails via Graph API. Email polling cycle aborted.")
        return 0

    triggered_webhook_count = 0
    try:
        since_date_str = (datetime.now(timezone.utc) - timedelta(days=2)).strftime('%Y-%m-%dT%H:%M:%SZ')
        sender_filter_parts = [f"from/emailAddress/address eq '{sender}'" for sender in SENDER_LIST_FOR_POLLING]
        sender_filter_string = " or ".join(sender_filter_parts)
        filter_query = f"isRead eq false and receivedDateTime ge {since_date_str} and ({sender_filter_string})"
        
        graph_url = (f"https://graph.microsoft.com/v1.0/me/mailFolders/inbox/messages?"
                     f"$filter={filter_query}&$select=id,subject,from,receivedDateTime,bodyPreview&"
                     f"$top=25&$orderby=receivedDateTime asc")

        app.logger.info(f"POLLER: Querying Graph API for emails. Filter: '{filter_query}'")
        headers_mail = {'Authorization': f'Bearer {token_msal}', 'Prefer': 'outlook.body-content-type="text"'}
        
        response = requests.get(graph_url, headers=headers_mail, timeout=45)
        response.raise_for_status()
        emails = response.json().get('value', [])
        
        app.logger.info(f"POLLER: Found {len(emails)} unread email(s) matching criteria (before Redis deduplication).")
        
        for mail in emails:
            mail_id = mail['id']
            mail_subject = mail.get('subject', 'N/A_Subject')
            
            if is_email_id_processed_redis(mail_id):
                app.logger.debug(f"POLLER: Email ID {mail_id} (Subj: '{mail_subject[:30]}...') already processed (found in Redis). Skipping webhook. Optionally marking as read.")
                if token_msal:
                    mark_email_as_read_outlook(token_msal, mail_id) 
                continue
            
            app.logger.info(f"POLLER: New relevant email found: ID={mail_id}, Subj='{mail_subject[:50]}...'. Triggering Make.com webhook.")
            
            payload_for_make = {
                "microsoft_graph_email_id": mail_id,
                "subject": mail_subject,
                "receivedDateTime": mail.get("receivedDateTime"),
                "sender_address": mail.get('from', {}).get('emailAddress', {}).get('address', 'N/A_Sender').lower(),
                "bodyPreview": mail.get('bodyPreview', '')
            }
            
            try:
                webhook_response = requests.post(MAKE_SCENARIO_WEBHOOK_URL, json=payload_for_make, timeout=30)
                if webhook_response.status_code == 200 and "accepted" in webhook_response.text.lower():
                    app.logger.info(f"POLLER: Make.com webhook call successful for email {mail_id}. Response: {webhook_response.status_code} - {webhook_response.text}")
                    if mark_email_id_as_processed_redis(mail_id):
                        triggered_webhook_count += 1
                        if token_msal and not mark_email_as_read_outlook(token_msal, mail_id):
                             app.logger.warning(f"POLLER: Failed to mark email {mail_id} as read in Outlook, but webhook sent and ID logged in Redis.")
                    else:
                        app.logger.error(f"POLLER: CRITICAL - Failed to log email ID {mail_id} to Redis. "
                                         "Email will NOT be marked as read in Outlook (if Outlook marking is enabled) to allow potential reprocessing if Redis issue is resolved.")
                else:
                    app.logger.error(f"POLLER: Make.com webhook call FAILED for email {mail_id}. Status: {webhook_response.status_code}, Response: {webhook_response.text[:200]}")
            except requests.exceptions.RequestException as e_webhook:
                app.logger.error(f"POLLER: Exception during Make.com webhook call for email {mail_id}: {e_webhook}")
        
        return triggered_webhook_count
        
    except requests.exceptions.RequestException as e_graph:
        app.logger.error(f"POLLER: Graph API error during email check: {e_graph}")
        if hasattr(e_graph, 'response') and e_graph.response is not None:
            app.logger.error(f"POLLER: API Response: {e_graph.response.status_code} - {e_graph.response.text[:500]}")
        return 0
    except Exception as e_general:
        app.logger.error(f"POLLER: Unexpected error during email polling cycle: {e_general}", exc_info=True)
        return 0

def background_email_poller():
    # (Identical to previous version, relies on the updated check_new_emails_and_trigger_make_webhook)
    app.logger.info(f"BG_POLLER: Email polling thread started. TZ for schedule: {POLLING_TIMEZONE_STR}.")
    consecutive_error_count = 0
    MAX_CONSECUTIVE_ERRORS = 5 

    while True:
        try:
            now_in_configured_tz = datetime.now(TZ_FOR_POLLING)
            current_hour = now_in_configured_tz.hour
            current_weekday = now_in_configured_tz.weekday()
            is_active_day = current_weekday in POLLING_ACTIVE_DAYS
            is_active_time = (POLLING_ACTIVE_START_HOUR <= current_hour < POLLING_ACTIVE_END_HOUR)
            log_schedule_details = (f"Day:{current_weekday}[Allowed:{POLLING_ACTIVE_DAYS}], "
                                    f"Hour:{current_hour:02d}h [{POLLING_ACTIVE_START_HOUR:02d}h-{POLLING_ACTIVE_END_HOUR:02d}h {POLLING_TIMEZONE_STR}]")

            if is_active_day and is_active_time:
                app.logger.info(f"BG_POLLER: In active period ({log_schedule_details}). Starting email poll cycle.")
                # Check essential configs for polling (MSAL app, refresh token in memory, Senders, Make URL)
                if not all([msal_app, current_onedrive_refresh_token_in_memory, 
                            SENDER_LIST_FOR_POLLING, MAKE_SCENARIO_WEBHOOK_URL]):
                    missing_cfg_details = []
                    if not msal_app: missing_cfg_details.append("MSAL app not init")
                    if not current_onedrive_refresh_token_in_memory: missing_cfg_details.append("No refresh token in memory")
                    if not SENDER_LIST_FOR_POLLING: missing_cfg_details.append("No senders list")
                    if not MAKE_SCENARIO_WEBHOOK_URL: missing_cfg_details.append("No Make webhook URL")
                    app.logger.warning(f"BG_POLLER: Essential configuration for MSAL/email polling is incomplete ({', '.join(missing_cfg_details)}). Waiting 60s and will re-check.")
                    time.sleep(60)
                    continue 
                
                webhooks_triggered = check_new_emails_and_trigger_make_webhook()
                app.logger.info(f"BG_POLLER: Active email poll cycle finished. {webhooks_triggered} Make.com webhook(s) triggered.")
                consecutive_error_count = 0 
                sleep_duration = EMAIL_POLLING_INTERVAL_SECONDS
            else:
                app.logger.info(f"BG_POLLER: Outside active period ({log_schedule_details}). Sleeping until next check for active window.")
                sleep_duration = POLLING_INACTIVE_CHECK_INTERVAL_SECONDS
            
            app.logger.debug(f"BG_POLLER: Sleeping for {sleep_duration} seconds.")
            time.sleep(sleep_duration)

        except Exception as e:
            consecutive_error_count += 1
            app.logger.error(f"BG_POLLER: Unhandled critical error in polling loop (Error #{consecutive_error_count}): {e}", exc_info=True)
            if consecutive_error_count >= MAX_CONSECUTIVE_ERRORS:
                app.logger.critical(f"BG_POLLER: Reached maximum consecutive errors ({MAX_CONSECUTIVE_ERRORS}). Stopping email polling thread.")
                break 
            sleep_on_error_duration = max(60, EMAIL_POLLING_INTERVAL_SECONDS) * (2 ** consecutive_error_count)
            app.logger.info(f"BG_POLLER: Sleeping for {sleep_on_error_duration}s due to error before retrying the loop.")
            time.sleep(sleep_on_error_duration)

# --- Endpoints API ---
# (Routes /api/register_local_downloader_url, /api/get_local_downloader_url, 
#  /api/log_processed_url, /api/check_trigger, /api/ping,
#  /, /api/get_local_status, /api/trigger_local_workflow, 
#  /api/check_emails_and_download are identical to the previous complete version that included Redis logic for these)
# For brevity, I will assume they are as in the last complete version you had where these were working with Redis.
# The key change was in the MSAL token handling and email polling parts above.

# Ensure /api/log_processed_url (if kept) uses PROCESSED_DROPBOX_URLS_REDIS_KEY
@app.route('/api/log_processed_url', methods=['POST'])
def api_log_processed_url():
    api_token = request.headers.get('X-API-Token')
    if not EXPECTED_API_TOKEN: 
        app.logger.critical("API_LOG_URL: PROCESS_API_TOKEN not set. Endpoint insecure.")
    elif api_token != EXPECTED_API_TOKEN: 
        return jsonify({"status": "error", "message": "Unauthorized."}), 401
    
    try: data = request.get_json()
    except Exception: return jsonify({"status":"error","message":"JSON format error"}),400 # Use status for consistency
    if not data or 'dropbox_url' not in data: return jsonify({"status": "error", "message": "'dropbox_url' is required."}), 400
    
    dropbox_url = data.get('dropbox_url')
    if not isinstance(dropbox_url, str) or not dropbox_url.lower().startswith("https://www.dropbox.com/"):
        return jsonify({"status": "error", "message": "Invalid Dropbox URL format."}), 400

    if not redis_client:
        app.logger.error("API_LOG_URL: Redis client not available. Cannot log processed Dropbox URL.")
        return jsonify({"status":"error", "message":"Redis service not configured/available on server for logging processed URL."}), 503

    try:
        if redis_client.sismember(PROCESSED_DROPBOX_URLS_REDIS_KEY, dropbox_url):
            app.logger.info(f"API_LOG_URL: Dropbox URL '{dropbox_url}' already logged in Redis set '{PROCESSED_DROPBOX_URLS_REDIS_KEY}'.")
            return jsonify({"status": "success", "message": "URL already logged."}), 200
        
        redis_client.sadd(PROCESSED_DROPBOX_URLS_REDIS_KEY, dropbox_url)
        app.logger.info(f"API_LOG_URL: Successfully logged Dropbox URL '{dropbox_url}' to Redis set '{PROCESSED_DROPBOX_URLS_REDIS_KEY}'.")
        return jsonify({"status": "success", "message": f"URL '{dropbox_url}' logged as processed in Redis."}), 200
    except redis.exceptions.RedisError as e_redis:
        app.logger.error(f"API_LOG_URL: Redis error logging Dropbox URL '{dropbox_url}' to set '{PROCESSED_DROPBOX_URLS_REDIS_KEY}': {e_redis}")
        return jsonify({"status": "error", "message": f"Failed to update Redis log for URL '{dropbox_url}' due to Redis error."}), 500
    except Exception as e:
        app.logger.error(f"API_LOG_URL: Generic error logging Dropbox URL '{dropbox_url}': {e}", exc_info=True)
        return jsonify({"status": "error", "message": f"Server error logging URL '{dropbox_url}'."}), 500

# All other routes like /api/register_local_downloader_url, /api/get_local_downloader_url, 
# /api/check_trigger, /api/ping, /, /api/get_local_status, /api/trigger_local_workflow,
# /api/check_emails_and_download
# remain as they were in the fully working version that used Redis for LT URL.
# For example:
@app.route('/api/register_local_downloader_url', methods=['POST'])
def register_local_downloader_url():
    received_token = request.headers.get('X-Register-Token')
    if REGISTER_LOCAL_URL_TOKEN and received_token != REGISTER_LOCAL_URL_TOKEN:
        app.logger.warning(f"API_REG_LT_URL: Unauthorized. Token: '{str(received_token)[:20]}...'")
        return jsonify({"status": "error", "message": "Unauthorized"}), 401
    try:
        data = request.get_json()
        if not data: return jsonify({"status": "error", "message": "Invalid JSON"}), 400
    except Exception: return jsonify({"status": "error", "message": "Malformed JSON"}), 400
    new_lt_url = data.get('localtunnel_url')
    if new_lt_url and not isinstance(new_lt_url, str): 
        return jsonify({"status": "error", "message": "'localtunnel_url' must be a string or null."}), 400
    if new_lt_url and not (new_lt_url.startswith("http://") or new_lt_url.startswith("https://")): 
        return jsonify({"status": "error", "message": "Invalid localtunnel URL format."}), 400
    try:
        storage_method = "Redis" if redis_client else "fallback file"
        if redis_client:
            if new_lt_url: redis_client.set(LOCALTUNNEL_URL_REDIS_KEY, new_lt_url)
            else: redis_client.delete(LOCALTUNNEL_URL_REDIS_KEY)
        else: 
            app.logger.warning(f"API_REG_LT_URL: Redis unavailable, using fallback file for LT URL.")
            LOCALTUNNEL_URL_FILE.parent.mkdir(parents=True, exist_ok=True)
            if new_lt_url:
                with open(LOCALTUNNEL_URL_FILE, "w") as f: f.write(new_lt_url)
            else: 
                if LOCALTUNNEL_URL_FILE.exists(): LOCALTUNNEL_URL_FILE.unlink()
        msg_action = "registered" if new_lt_url else "unregistered/cleared"
        app.logger.info(f"API_REG_LT_URL: Localtunnel URL {msg_action} via {storage_method}" + (f": '{new_lt_url}'" if new_lt_url else "."))
        return jsonify({"status": "success", "message": f"Localtunnel URL {msg_action} via {storage_method}."}), 200
    except redis.exceptions.RedisError as e_redis_op:
        app.logger.error(f"API_REG_LT_URL: Redis op error: {e_redis_op}.", exc_info=True)
        return jsonify({"status": "error", "message": "Server error (Redis op failed) for LT URL."}), 500
    except Exception as e:
        app.logger.error(f"API_REG_LT_URL: Server error for LT URL: {e}", exc_info=True)
        return jsonify({"status": "error", "message": "Server error for LT URL registration."}), 500

@app.route('/api/get_local_downloader_url', methods=['GET'])
def get_local_downloader_url_for_make():
    received_token = request.headers.get('X-API-Token')
    if not EXPECTED_API_TOKEN: app.logger.critical("API_GET_LT_URL: EXPECTED_API_TOKEN not set. Endpoint insecure.")
    elif received_token != EXPECTED_API_TOKEN:
        app.logger.warning(f"API_GET_LT_URL: Unauthorized. Token: '{str(received_token)[:20]}...'")
        return jsonify({"status": "error", "message": "Unauthorized"}), 401
    lt_url, source_of_url = None, "not found"
    try:
        if redis_client:
            url_bytes = redis_client.get(LOCALTUNNEL_URL_REDIS_KEY)
            if url_bytes: lt_url, source_of_url = url_bytes.decode('utf-8'), "Redis"
            else: app.logger.info(f"API_GET_LT_URL: LT URL not in Redis. Trying fallback.")
        if not lt_url:
            if not redis_client: app.logger.warning(f"API_GET_LT_URL: Redis unavailable, trying fallback file.")
            if LOCALTUNNEL_URL_FILE.exists():
                with open(LOCALTUNNEL_URL_FILE, "r") as f: lt_url_file_content = f.read().strip()
                if lt_url_file_content: lt_url, source_of_url = lt_url_file_content, "fallback file"
                else: app.logger.warning(f"API_GET_LT_URL: Fallback file empty.")
            else: app.logger.info(f"API_GET_LT_URL: Fallback file not found.")
        if lt_url:
            app.logger.info(f"API_GET_LT_URL: Fetched LT URL from {source_of_url}: '{lt_url}'")
            return jsonify({"status": "success", "localtunnel_url": lt_url}), 200
        else:
            app.logger.warning("API_GET_LT_URL: LT URL not found in Redis or fallback.")
            return jsonify({"status": "error", "message": "Local worker URL not registered."}), 404
    except redis.exceptions.RedisError as e_redis_op:
        app.logger.error(f"API_GET_LT_URL: Redis op error: {e_redis_op}. Trying fallback.", exc_info=True)
        if LOCALTUNNEL_URL_FILE.exists():
            try:
                with open(LOCALTUNNEL_URL_FILE, "r") as f: temp_lt_url = f.read().strip()
                if temp_lt_url:
                    app.logger.info(f"API_GET_LT_URL: Fetched (after Redis error) from fallback: '{temp_lt_url}'")
                    return jsonify({"status": "success", "localtunnel_url": temp_lt_url}), 200
            except Exception as e_file_fb: app.logger.error(f"API_GET_LT_URL: Error reading fallback after Redis error: {e_file_fb}", exc_info=True)
        app.logger.error(f"API_GET_LT_URL: URL not found after Redis error and fallback attempt.")
        return jsonify({"status": "error", "message": "Server error (Redis op failed) & fallback unavailable."}), 503
    except Exception as e:
        app.logger.error(f"API_GET_LT_URL: Error retrieving LT URL: {e}", exc_info=True)
        return jsonify({"status": "error", "message": "Server error reading local worker URL."}), 500

@app.route('/api/check_trigger', methods=['GET'])
def check_local_workflow_trigger(): # Stays file-based for simplicity
    response_data = {'command_pending': False, 'payload': None}
    if TRIGGER_SIGNAL_FILE.exists():
        try:
            with open(TRIGGER_SIGNAL_FILE, 'r') as f: payload_from_file = json.load(f)
            response_data['command_pending'] = True; response_data['payload'] = payload_from_file
            TRIGGER_SIGNAL_FILE.unlink()
            app.logger.info(f"LOCAL_CHECK_API: Signal read from '{TRIGGER_SIGNAL_FILE}', deleted. Payload: {payload_from_file}")
        except Exception as e: app.logger.error(f"LOCAL_CHECK_API: Error processing '{TRIGGER_SIGNAL_FILE}': {e}", exc_info=True)
    return jsonify(response_data)

@app.route('/api/ping', methods=['GET','HEAD'])
def api_ping():
    app.logger.info(f"PING_API: Received /api/ping from IP:{request.headers.get('X-Forwarded-For', request.remote_addr)}")
    response = jsonify({"status":"pong", "timestamp_utc": datetime.now(timezone.utc).isoformat()})
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return response, 200

@app.route('/')
@auth.login_required
def serve_trigger_page_main(): # Assumes trigger_page.html is at app.root_path
    if not users and (TRIGGER_PAGE_USER_ENV or TRIGGER_PAGE_PASSWORD_ENV):
        app.logger.error("AUTH ERROR: User/pass env vars set, but 'users' dict empty.")
        return "Server auth config error.", 500
    app.logger.info(f"ROOT_UI: Request for '/' by user '{auth.current_user()}'. Serving 'trigger_page.html'.")
    try:
        if not os.path.exists(os.path.join(app.root_path, 'trigger_page.html')):
             app.logger.error(f"ROOT_UI: CRITICAL - 'trigger_page.html' NOT found in {os.path.join(app.root_path, 'trigger_page.html')}.")
             return "Error: Main page content not found (file missing).", 404
        return send_from_directory(app.root_path, 'trigger_page.html')
    except Exception as e:
        app.logger.error(f"ROOT_UI: Unexpected error serving 'trigger_page.html': {e}", exc_info=True)
        return "Internal server error serving UI.", 500

@app.route('/api/get_local_status', methods=['GET'])
@auth.login_required
def get_local_status_proxied(): # Relies on the updated LT URL fetching logic internally
    app.logger.info(f"PROXY_STATUS: /api/get_local_status by user '{auth.current_user()}'.")
    received_ui_token = request.args.get('ui_token')
    if REMOTE_UI_ACCESS_TOKEN_ENV and (not received_ui_token or received_ui_token != REMOTE_UI_ACCESS_TOKEN_ENV):
        app.logger.warning(f"PROXY_STATUS: Invalid ui_token by '{auth.current_user()}'.")
        return jsonify({"error": "Invalid UI token"}), 403
    localtunnel_url = None
    try:
        if redis_client:
            url_bytes = redis_client.get(LOCALTUNNEL_URL_REDIS_KEY)
            if url_bytes: localtunnel_url = url_bytes.decode('utf-8')
        if not localtunnel_url and not redis_client:
             if LOCALTUNNEL_URL_FILE.exists():
                with open(LOCALTUNNEL_URL_FILE, "r") as f: file_content = f.read().strip()
                if file_content: localtunnel_url = file_content
    except Exception as e_url_f: app.logger.error(f"PROXY_STATUS: Error fetching LT URL: {e_url_f}")
    if not localtunnel_url:
        app.logger.warning("PROXY_STATUS: LT URL not available for proxy.")
        return jsonify({"overall_status_code_from_worker": "worker_unavailable", "overall_status_text": "Worker Indisponible", "status_text": "Worker non connecté."}), 503
    try:
        target_url = f"{localtunnel_url.rstrip('/')}/api/get_remote_status_summary"
        headers_to_worker = {'X-Worker-Token': INTERNAL_WORKER_COMMS_TOKEN_ENV} if INTERNAL_WORKER_COMMS_TOKEN_ENV else {}
        if not INTERNAL_WORKER_COMMS_TOKEN_ENV: app.logger.warning(f"PROXY_STATUS: No INT_WORK_TOKEN. Calling {target_url} unauth'd.")
        response_local = requests.get(target_url, headers=headers_to_worker, timeout=10)
        response_local.raise_for_status(); local_data = response_local.json()
        return jsonify({ # Pass through fields expected by UI
            "overall_status_code_from_worker": local_data.get("overall_status_code"), "overall_status_text": local_data.get("overall_status_text_display"), 
            "current_step_name": local_data.get("current_step_name"), "status_text": local_data.get("status_text_detail"), 
            "progress_current": local_data.get("progress_current", 0), "progress_total": local_data.get("progress_total", 0),
            "recent_downloads": local_data.get("recent_downloads", []), "last_sequence_summary": local_data.get("last_sequence_summary")
        }), 200
    except requests.exceptions.Timeout: return jsonify({"overall_status_code_from_worker": "worker_timeout", "overall_status_text": "Worker (Timeout)", "status_text": "Timeout worker."}), 504 
    except requests.exceptions.ConnectionError: return jsonify({"overall_status_code_from_worker": "worker_conn_refused", "overall_status_text": "Worker (Connexion Refusée)", "status_text": "Connexion worker refusée."}), 502
    except requests.exceptions.HTTPError as e_http:
        sc, err_msg, det_msg = e_http.response.status_code, f"Worker (HTTP {e_http.response.status_code})", "Erreur HTTP worker."
        if sc == 401: err_msg, det_msg = "Erreur Auth Interne (Worker)", "Auth vers worker local échouée."
        app.logger.error(f"PROXY_STATUS: HTTP {sc} from worker {target_url}. Resp: {e_http.response.text[:200]}")
        return jsonify({"overall_status_code_from_worker": f"worker_http_error_{sc}", "overall_status_text": err_msg, "status_text": det_msg}), sc
    except Exception as e_gen:
        app.logger.error(f"PROXY_STATUS: Generic error for {target_url}: {e_gen}", exc_info=True)
        return jsonify({"overall_status_code_from_worker": "proxy_internal_error", "overall_status_text": "Erreur Serveur (Proxy)", "status_text": "Erreur interne proxy."}), 500

@app.route('/api/trigger_local_workflow', methods=['POST'])
@auth.login_required
def trigger_local_workflow_authed(): # Stays file-based for simplicity
    app.logger.info(f"LOCAL_TRIGGER_API: Called by user '{auth.current_user()}'.")
    payload = request.json or {"command": "start_manual_generic_from_ui"}
    if not isinstance(payload, dict): payload = {"command": "start_manual_generic_from_ui", "original_payload": payload}
    payload.setdefault("timestamp_utc", datetime.now(timezone.utc).isoformat())
    payload.setdefault("triggered_by_user", auth.current_user())
    try:
        with open(TRIGGER_SIGNAL_FILE, "w") as f: json.dump(payload, f)
        app.logger.info(f"LOCAL_TRIGGER_API: Signal file '{TRIGGER_SIGNAL_FILE}' set. Payload: {payload}")
        return jsonify({"status": "ok", "message": "Local workflow signal set."}), 200
    except Exception as e:
        app.logger.error(f"LOCAL_TRIGGER_API: Error writing '{TRIGGER_SIGNAL_FILE}': {e}", exc_info=True)
        return jsonify({"status": "error", "message": "Internal server error setting signal."}), 500

@app.route('/api/check_emails_and_download', methods=['POST'])
@auth.login_required
def api_check_emails_and_download_authed(): # Relies on updated email polling
    app.logger.info(f"API_EMAIL_CHECK: Manual trigger by '{auth.current_user()}'.")
    def run_task():
        with app.app_context(): 
            try:
                app.logger.info("API_EMAIL_CHECK_THREAD: Starting task...")
                webhooks_triggered = check_new_emails_and_trigger_make_webhook()
                app.logger.info(f"API_EMAIL_CHECK_THREAD: Finished. {webhooks_triggered} webhook(s) triggered.")
            except Exception as e_t: app.logger.error(f"API_EMAIL_CHECK_THREAD: Error: {e_t}", exc_info=True)
    if not all([msal_app, current_onedrive_refresh_token_in_memory, SENDER_LIST_FOR_POLLING, MAKE_SCENARIO_WEBHOOK_URL]):
        app.logger.error("API_EMAIL_CHECK: Cannot start: incomplete server config (MSAL/Polling/Webhook).")
        return jsonify({"status": "error", "message": "Config serveur email incomplète."}), 503
    threading.Thread(target=run_task, name="ManualEmailCheckThread").start()
    return jsonify({"status": "success", "message": "Vérification emails (arrière-plan) lancée."}), 202

# --- Démarrage de l'Application et des Threads ---
if __name__ == '__main__':
    if not REDIS_AVAILABLE:
        app.logger.critical("MAIN_APP: Redis library not found. Critical Redis-dependent features will fail. Please install 'redis' library.")
    if not REDIS_URL:
        app.logger.warning("MAIN_APP: REDIS_URL is not set. Refresh token persistence and other Redis features will be disabled or use fallbacks.")
    
    initialize_refresh_token() # Initialize the refresh token at startup

    is_debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    should_start_background_threads = not is_debug_mode or os.environ.get("WERKZEUG_RUN_MAIN") == "true"

    if should_start_background_threads:
        app.logger.info("MAIN_APP: Preparing background threads.")
        # Check conditions for Email Polling Thread again, now that current_onedrive_refresh_token_in_memory is initialized
        if all([msal_app, current_onedrive_refresh_token_in_memory, SENDER_LIST_FOR_POLLING, MAKE_SCENARIO_WEBHOOK_URL]):
            email_poller_thread = threading.Thread(target=background_email_poller, name="EmailPollerThread", daemon=True)
            email_poller_thread.start()
            app.logger.info(f"MAIN_APP: Background email polling thread started successfully.")
        else:
            missing_configs = []
            if not msal_app: missing_configs.append("MSAL app not initialized")
            if not current_onedrive_refresh_token_in_memory: missing_configs.append("OneDrive Refresh Token (from ENV or Redis)")
            if not SENDER_LIST_FOR_POLLING: missing_configs.append("Sender List for Polling")
            if not MAKE_SCENARIO_WEBHOOK_URL: missing_configs.append("Make.com Webhook URL")
            app.logger.warning(f"MAIN_APP: Background email polling thread NOT started due to incomplete configuration: {', '.join(missing_configs)}.")
    else:
        app.logger.info("MAIN_APP: Background threads not started by this Werkzeug child process (expected in debug mode with reloader).")

    # Final startup warnings for critical tokens (identical to previous version)
    if not users: app.logger.warning("MAIN_APP: HTTP Basic Auth for UI is not configured.")
    if not EXPECTED_API_TOKEN: app.logger.critical("MAIN_APP: PROCESS_API_TOKEN not set. Make.com endpoints INSECURE.")
    if not REGISTER_LOCAL_URL_TOKEN: app.logger.warning("MAIN_APP: REGISTER_LOCAL_URL_TOKEN not set. Local worker registration potentially INSECURE.")
    if not REMOTE_UI_ACCESS_TOKEN_ENV and users: app.logger.info("MAIN_APP: REMOTE_UI_ACCESS_TOKEN not set; ui_token check skipped if Basic Auth'd.")
    if not INTERNAL_WORKER_COMMS_TOKEN_ENV: app.logger.warning("MAIN_APP: INTERNAL_WORKER_COMMS_TOKEN not set. Worker communication unauthenticated.")

    server_port = int(os.environ.get('PORT', 10000))
    app.logger.info(f"MAIN_APP: Flask server starting on 0.0.0.0:{server_port}. Debug: {is_debug_mode}")
    use_reloader_val = is_debug_mode and os.environ.get("WERKZEUG_RUN_MAIN") != "true"
    app.run(host='0.0.0.0', port=server_port, debug=is_debug_mode, use_reloader=use_reloader_val)
