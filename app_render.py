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
    # No app logger available here yet, use standard logging if needed at module level
    # logging.warning("CFG REDIS: 'redis' Python library not installed. Redis-based features will be disabled or use fallbacks.")


from msal import ConfidentialClientApplication

app = Flask(__name__)
auth = HTTPBasicAuth()

# --- Tokens and Config de référence ---
REF_TRIGGER_PAGE_USER = "admin"
REF_TRIGGER_PAGE_PASSWORD = "UDPVA#esKf40r@" # Example, use env var
REF_REMOTE_UI_ACCESS_TOKEN = "0wbgXHiF3e!MqE" # Example, use env var
REF_INTERNAL_WORKER_COMMS_TOKEN = "Fn*G14Vb'!Hkra7" # Example, use env var
REF_PROCESS_API_TOKEN = "rnd_PW5cGYVf4g131imu9cYkFw27u8dY" # Example, use env var
REF_REGISTER_LOCAL_URL_TOKEN = "WMmWti@^n6RaUA" # Example, use env var

REF_ONEDRIVE_CLIENT_ID = "6bbc767d-53e8-4b82-bd49-480d4c157a9b" # Example, use env var
REF_ONEDRIVE_CLIENT_SECRET = "3Ah8Q~M7wk954ttbQRkt-xHn80enAeHd5wHG1XoEu" # Placeholder - VRAI SECRET DANS ENV
REF_ONEDRIVE_TENANT_ID = "60fb2b89-e5bf-4232-98f6-f1ecb90660c5" # Example, use env var
# ONEDRIVE_REFRESH_TOKEN est trop sensible pour un fallback codé, doit venir de l'ENV.

REF_MAKE_SCENARIO_WEBHOOK_URL = "https://hook.eu2.make.com/wjcp43km1bgginyr1xu1pwui95ekr7gi" # Example, use env var
REF_SENDER_OF_INTEREST_FOR_POLLING = "achats@media-solution.fr,camille.moine.pro@gmail.com,a.peault@media-solution.fr,v.lorent@media-solution.fr,technique@media-solution.fr,t.deslus@media-solution.fr" # Example, use env var

REF_POLLING_TIMEZONE = "Europe/Paris"
REF_POLLING_ACTIVE_START_HOUR = 9
REF_POLLING_ACTIVE_END_HOUR = 23
REF_POLLING_ACTIVE_DAYS = "0,1,2,3,4" # Lundi à Vendredi
REF_EMAIL_POLLING_INTERVAL_SECONDS = 30 
# ------------------------------------------------------------------------------------

# --- Configuration du Logging ---
log_level_str = os.environ.get('FLASK_LOG_LEVEL', 'INFO').upper()
log_level = getattr(logging, log_level_str, logging.INFO)
logging.basicConfig(level=log_level,
                    format='%(asctime)s - %(levelname)s - %(name)s - %(module)s - %(funcName)s - %(lineno)d - %(message)s')
if not REDIS_AVAILABLE:
    app.logger.warning("CFG REDIS: 'redis' Python library not installed at app init. Redis-based features will be disabled or use fallbacks.")


# --- Configuration des Identifiants pour la page de trigger ---
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
        POLLING_ACTIVE_DAYS = [0,1,2,3,4] # Fallback
if not POLLING_ACTIVE_DAYS: POLLING_ACTIVE_DAYS = [0,1,2,3,4] # Fallback
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
POLLING_INACTIVE_CHECK_INTERVAL_SECONDS = int(os.environ.get("POLLING_INACTIVE_CHECK_INTERVAL_SECONDS", 600)) # Default 10 min
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

if REDIS_AVAILABLE and REDIS_URL:
    try:
        # Added health_check_interval for potentially better resilience with some Redis clients/servers
        redis_client = redis.from_url(REDIS_URL, socket_connect_timeout=5, socket_timeout=5, health_check_interval=30)
        redis_client.ping()
        app.logger.info(f"CFG REDIS: Successfully connected to Redis at {REDIS_URL.split('@')[-1] if '@' in REDIS_URL else REDIS_URL}.")
    except redis.exceptions.ConnectionError as e_redis:
        app.logger.error(f"CFG REDIS: Could not connect to Redis. Error: {e_redis}. Redis-dependent features will be impaired or use fallbacks.")
        redis_client = None
    except Exception as e_redis_other: # Catch other potential redis client errors
        app.logger.error(f"CFG REDIS: An unexpected error occurred during Redis initialization: {e_redis_other}. Redis-dependent features will be impaired or use fallbacks.")
        redis_client = None
elif REDIS_AVAILABLE and not REDIS_URL:
    app.logger.warning("CFG REDIS: REDIS_URL not set, but 'redis' library is available. Redis will not be used for primary storage; fallbacks may apply.")
    redis_client = None
else: # REDIS_AVAILABLE is False
    app.logger.warning("CFG REDIS: 'redis' Python library not installed. Redis will not be used; fallbacks may apply.")
    redis_client = None


# --- Configuration OneDrive / MSAL (Still needed for reading emails and optionally marking as read) ---
ONEDRIVE_CLIENT_ID = os.environ.get('ONEDRIVE_CLIENT_ID', REF_ONEDRIVE_CLIENT_ID)
ONEDRIVE_CLIENT_SECRET = os.environ.get('ONEDRIVE_CLIENT_SECRET', REF_ONEDRIVE_CLIENT_SECRET)
ONEDRIVE_REFRESH_TOKEN = os.environ.get('ONEDRIVE_REFRESH_TOKEN')
ONEDRIVE_TENANT_ID = os.environ.get('ONEDRIVE_TENANT_ID', REF_ONEDRIVE_TENANT_ID)
ONEDRIVE_AUTHORITY = f"https://login.microsoftonline.com/{ONEDRIVE_TENANT_ID}" if ONEDRIVE_TENANT_ID != "consumers" else "https://login.microsoftonline.com/consumers"
ONEDRIVE_SCOPES_DELEGATED = ["Mail.ReadWrite", "User.Read"] # Mail.ReadWrite is key here. Files.ReadWrite might not be needed if not using OneDrive for deduplication files.

msal_app = None
if ONEDRIVE_CLIENT_ID and ONEDRIVE_CLIENT_SECRET:
    app.logger.info(f"CFG MSAL: Initializing MSAL ConfidentialClientApplication. ClientID: '{ONEDRIVE_CLIENT_ID[:5]}...', Authority: {ONEDRIVE_AUTHORITY}")
    msal_app = ConfidentialClientApplication(ONEDRIVE_CLIENT_ID, authority=ONEDRIVE_AUTHORITY, client_credential=ONEDRIVE_CLIENT_SECRET)
else:
    app.logger.warning("CFG MSAL: OneDrive Client ID or Client Secret missing. Email Polling features (reading emails, marking as read in Outlook) will be disabled.")

# --- Configuration des Webhooks et Tokens ---
MAKE_SCENARIO_WEBHOOK_URL = os.environ.get("MAKE_SCENARIO_WEBHOOK_URL", REF_MAKE_SCENARIO_WEBHOOK_URL)
SENDER_OF_INTEREST_FOR_POLLING_RAW = os.environ.get("SENDER_OF_INTEREST_FOR_POLLING", REF_SENDER_OF_INTEREST_FOR_POLLING)
SENDER_LIST_FOR_POLLING = []
if SENDER_OF_INTEREST_FOR_POLLING_RAW:
    SENDER_LIST_FOR_POLLING = [e.strip().lower() for e in SENDER_OF_INTEREST_FOR_POLLING_RAW.split(',') if e.strip()]
if SENDER_LIST_FOR_POLLING:
    app.logger.info(f"CFG POLL: Monitoring emails from {len(SENDER_LIST_FOR_POLLING)} senders: {SENDER_LIST_FOR_POLLING}")
else:
    app.logger.warning("CFG POLL: SENDER_OF_INTEREST_FOR_POLLING not set. Email polling will likely be ineffective.")

EXPECTED_API_TOKEN = os.environ.get("PROCESS_API_TOKEN", REF_PROCESS_API_TOKEN) 
if not EXPECTED_API_TOKEN:
    app.logger.warning("CFG TOKEN: PROCESS_API_TOKEN not set. API endpoints called by Make.com will be insecure.")
else:
    app.logger.info(f"CFG TOKEN: PROCESS_API_TOKEN (for Make.com calls) configured: '{EXPECTED_API_TOKEN[:5]}...'")

REGISTER_LOCAL_URL_TOKEN = os.environ.get("REGISTER_LOCAL_URL_TOKEN", REF_REGISTER_LOCAL_URL_TOKEN)
if not REGISTER_LOCAL_URL_TOKEN:
    app.logger.warning("CFG TOKEN: REGISTER_LOCAL_URL_TOKEN not set. Endpoint for registering local worker URL will be insecure if not matching on app_new.py.")
else:
    app.logger.info(f"CFG TOKEN: REGISTER_LOCAL_URL_TOKEN (for local worker registration) configured: '{REGISTER_LOCAL_URL_TOKEN[:5]}...'")

REMOTE_UI_ACCESS_TOKEN_ENV = os.environ.get("REMOTE_UI_ACCESS_TOKEN", REF_REMOTE_UI_ACCESS_TOKEN)
INTERNAL_WORKER_COMMS_TOKEN_ENV = os.environ.get("INTERNAL_WORKER_COMMS_TOKEN", REF_INTERNAL_WORKER_COMMS_TOKEN)


# --- Fonctions Utilitaires MSAL ---
def get_mcal_graph_api_token(): # Renamed for clarity
    if not msal_app:
        app.logger.error("MSAL: MSAL app not configured. Cannot get Graph API token.")
        return None
    if not ONEDRIVE_REFRESH_TOKEN: # This MUST come from environment
        app.logger.error("MSAL: OneDrive refresh token missing (ONEDRIVE_REFRESH_TOKEN env var). Cannot get Graph API token.")
        return None
    
    token_result = msal_app.acquire_token_by_refresh_token(ONEDRIVE_REFRESH_TOKEN, scopes=ONEDRIVE_SCOPES_DELEGATED)
    
    if "access_token" in token_result:
        app.logger.info("MSAL: Graph API access token obtained successfully.")
        if token_result.get("refresh_token") and token_result.get("refresh_token") != ONEDRIVE_REFRESH_TOKEN:
            app.logger.warning("MSAL: A new refresh token was issued by Microsoft Graph. "
                               "IMPORTANT: Update the ONEDRIVE_REFRESH_TOKEN environment variable with this new token: "
                               f"'{token_result.get('refresh_token')}'")
        return token_result['access_token']
    else:
        app.logger.error(f"MSAL: Failed to obtain Graph API access token. Error: {token_result.get('error')}, "
                         f"Description: {token_result.get('error_description')}. Details: {token_result}")
        return None

# --- Fonctions de Déduplication avec Redis ---
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
        app.logger.info(f"REDIS_DEDUP: Email ID '{email_id}' processed in Redis set '{PROCESSED_EMAIL_IDS_REDIS_KEY}'. Result: {result (1 new, 0 exists)}.")
        return True
    except redis.exceptions.RedisError as e_redis:
        app.logger.error(f"REDIS_DEDUP: Error adding email ID '{email_id}' to set '{PROCESSED_EMAIL_IDS_REDIS_KEY}': {e_redis}")
        return False

# --- Fonctions de Polling des Emails (modifiée pour Redis deduplication) ---
def mark_email_as_read_outlook(token_msal, msg_id): # Kept if marking as read in Outlook is desired
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
    
    token_msal = None
    if msal_app:
        token_msal = get_mcal_graph_api_token()
        if not token_msal:
            app.logger.error("POLLER: Failed to get MSAL Graph token. Email polling cycle aborted as email reading will fail.")
            return 0 
    else:
        app.logger.warning("POLLER: MSAL app not configured. Cannot read emails via Graph API. Email polling cycle aborted.")
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
    app.logger.info(f"BG_POLLER: Email polling thread started. TZ for schedule: {POLLING_TIMEZONE_STR}.")
    consecutive_error_count = 0
    MAX_CONSECUTIVE_ERRORS = 5 # Stop after 5 consecutive critical errors in the loop

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
                
                # Check essential configs for polling emails (MSAL app for reading, Senders, Make URL)
                if not all([msal_app, ONEDRIVE_REFRESH_TOKEN, # MSAL needs refresh token too
                            SENDER_LIST_FOR_POLLING, MAKE_SCENARIO_WEBHOOK_URL]):
                    app.logger.warning("BG_POLLER: Essential configuration for MSAL/email polling is incomplete. Waiting 60s and will re-check.")
                    time.sleep(60)
                    continue 
                
                webhooks_triggered = check_new_emails_and_trigger_make_webhook()
                app.logger.info(f"BG_POLLER: Active email poll cycle finished. {webhooks_triggered} Make.com webhook(s) triggered.")
                consecutive_error_count = 0 # Reset on success
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
                app.logger.critical(f"BG_POLLER: Reached maximum consecutive errors ({MAX_CONSECUTIVE_ERRORS}). Stopping email polling thread to prevent further issues.")
                break # Exit the loop, thread stops
            
            # Exponential backoff for retrying the loop on error
            sleep_on_error_duration = max(60, EMAIL_POLLING_INTERVAL_SECONDS) * (2 ** consecutive_error_count) # Min 60s, then 120s, 240s...
            app.logger.info(f"BG_POLLER: Sleeping for {sleep_on_error_duration}s due to error before retrying the loop.")
            time.sleep(sleep_on_error_duration)

# --- Endpoints API ---

@app.route('/api/register_local_downloader_url', methods=['POST'])
def register_local_downloader_url():
    received_token = request.headers.get('X-Register-Token')
    if REGISTER_LOCAL_URL_TOKEN and received_token != REGISTER_LOCAL_URL_TOKEN:
        app.logger.warning(f"API_REG_LT_URL: Unauthorized access attempt. Token: '{str(received_token)[:20]}...'")
        return jsonify({"status": "error", "message": "Unauthorized"}), 401
    try:
        data = request.get_json()
        if not data: return jsonify({"status": "error", "message": "Invalid JSON payload"}), 400
    except Exception: return jsonify({"status": "error", "message": "Malformed JSON payload"}), 400
    
    new_lt_url = data.get('localtunnel_url')
    if new_lt_url and not isinstance(new_lt_url, str): 
        return jsonify({"status": "error", "message": "'localtunnel_url' must be a string or null."}), 400
    if new_lt_url and not (new_lt_url.startswith("http://") or new_lt_url.startswith("https://")): 
        return jsonify({"status": "error", "message": "Invalid localtunnel URL format."}), 400

    try:
        storage_method = "Redis" if redis_client else "fallback file"
        if redis_client:
            if new_lt_url:
                redis_client.set(LOCALTUNNEL_URL_REDIS_KEY, new_lt_url)
            else: # new_lt_url is None or empty, meaning unregister
                redis_client.delete(LOCALTUNNEL_URL_REDIS_KEY)
        else: # Fallback to ephemeral file storage
            app.logger.warning(f"API_REG_LT_URL: Redis unavailable, using fallback file storage for Localtunnel URL.")
            if new_lt_url:
                # Ensure parent dir exists, though SIGNAL_DIR.mkdir is at startup
                LOCALTUNNEL_URL_FILE.parent.mkdir(parents=True, exist_ok=True) 
                with open(LOCALTUNNEL_URL_FILE, "w") as f: f.write(new_lt_url)
            else: # Unregister
                if LOCALTUNNEL_URL_FILE.exists(): LOCALTUNNEL_URL_FILE.unlink()
        
        if new_lt_url:
            app.logger.info(f"API_REG_LT_URL: Localtunnel URL registered via {storage_method}: '{new_lt_url}'")
            return jsonify({"status": "success", "message": f"Localtunnel URL registered via {storage_method}."}), 200
        else:
            app.logger.info(f"API_REG_LT_URL: Localtunnel URL unregistered/cleared via {storage_method}.")
            return jsonify({"status": "success", "message": f"Localtunnel URL unregistered/cleared via {storage_method}."}), 200

    except redis.exceptions.RedisError as e_redis_op:
        app.logger.error(f"API_REG_LT_URL: Redis operation error: {e_redis_op}. Check Redis server/connection.", exc_info=True)
        return jsonify({"status": "error", "message": "Server error (Redis operation failed) processing Localtunnel URL."}), 500
    except Exception as e:
        app.logger.error(f"API_REG_LT_URL: Server error processing localtunnel URL: {e}", exc_info=True)
        return jsonify({"status": "error", "message": "Server error processing localtunnel URL registration."}), 500

@app.route('/api/get_local_downloader_url', methods=['GET'])
def get_local_downloader_url_for_make():
    received_token = request.headers.get('X-API-Token')
    if not EXPECTED_API_TOKEN: app.logger.critical("API_GET_LT_URL: EXPECTED_API_TOKEN not set on server. Endpoint is insecure but proceeding.")
    elif received_token != EXPECTED_API_TOKEN:
        app.logger.warning(f"API_GET_LT_URL: Unauthorized access attempt to get local URL. Token: '{str(received_token)[:20]}...'")
        return jsonify({"status": "error", "message": "Unauthorized"}), 401

    lt_url = None
    source_of_url = "not found"
    try:
        if redis_client:
            url_bytes = redis_client.get(LOCALTUNNEL_URL_REDIS_KEY)
            if url_bytes:
                lt_url = url_bytes.decode('utf-8')
                source_of_url = "Redis"
            else:
                app.logger.info(f"API_GET_LT_URL: Localtunnel URL not found in Redis (key: {LOCALTUNNEL_URL_REDIS_KEY}). Trying fallback file.")
        
        if not lt_url: # If Redis client is None or URL not found in Redis
            if not redis_client: app.logger.warning(f"API_GET_LT_URL: Redis unavailable, trying fallback file for Localtunnel URL.")
            if LOCALTUNNEL_URL_FILE.exists():
                with open(LOCALTUNNEL_URL_FILE, "r") as f: 
                    lt_url_file_content = f.read().strip()
                if lt_url_file_content:
                    lt_url = lt_url_file_content
                    source_of_url = "fallback file"
                else:
                     app.logger.warning(f"API_GET_LT_URL: Fallback file '{LOCALTUNNEL_URL_FILE}' exists but is empty.")
            else:
                app.logger.info(f"API_GET_LT_URL: Fallback file '{LOCALTUNNEL_URL_FILE}' does not exist.")
        
        if lt_url:
            app.logger.info(f"API_GET_LT_URL: Fetched Localtunnel URL from {source_of_url}: '{lt_url}'")
            return jsonify({"status": "success", "localtunnel_url": lt_url}), 200
        else:
            app.logger.warning("API_GET_LT_URL: Localtunnel URL ultimately not found in Redis or fallback file.")
            return jsonify({"status": "error", "message": "Local worker URL not registered or currently unavailable."}), 404

    except redis.exceptions.RedisError as e_redis_op:
        app.logger.error(f"API_GET_LT_URL: Redis operation error: {e_redis_op}. Check Redis server/connection.", exc_info=True)
        # Fallback to file if Redis op fails mid-request
        app.logger.warning(f"API_GET_LT_URL: Redis operation failed. Attempting fallback to file for this request.")
        if LOCALTUNNEL_URL_FILE.exists():
            try:
                with open(LOCALTUNNEL_URL_FILE, "r") as f: temp_lt_url = f.read().strip()
                if temp_lt_url:
                    app.logger.info(f"API_GET_LT_URL: Fetched (after Redis error) from fallback file: '{temp_lt_url}'")
                    return jsonify({"status": "success", "localtunnel_url": temp_lt_url}), 200
            except Exception as e_file_fallback:
                app.logger.error(f"API_GET_LT_URL: Error reading fallback file after Redis error: {e_file_fallback}", exc_info=True)
        app.logger.error(f"API_GET_LT_URL: URL not found even after Redis error and fallback attempt.")
        return jsonify({"status": "error", "message": "Server error (Redis op failed) and fallback for LT URL unavailable."}), 503
    except Exception as e:
        app.logger.error(f"API_GET_LT_URL: Error retrieving localtunnel URL: {e}", exc_info=True)
        return jsonify({"status": "error", "message": "Server error reading local worker URL."}), 500

@app.route('/api/log_processed_url', methods=['POST'])
def api_log_processed_url():
    api_token = request.headers.get('X-API-Token')
    if not EXPECTED_API_TOKEN: 
        app.logger.critical("API_LOG_URL: PROCESS_API_TOKEN not set. Endpoint insecure.")
        # Depending on policy, you might still allow if token is not set, or return 500
        # For now, let's assume if it's not set, it's a server config issue that shouldn't block if called.
        # return jsonify({"status": "error", "message": "Server config error: API token not set."}), 500
    elif api_token != EXPECTED_API_TOKEN: 
        return jsonify({"status": "error", "message": "Unauthorized."}), 401
    
    try: data = request.get_json()
    except Exception: return jsonify({"s":"err","m":"JSON format error"}),400
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


@app.route('/api/check_trigger', methods=['GET'])
def check_local_workflow_trigger():
    response_data = {'command_pending': False, 'payload': None}
    if TRIGGER_SIGNAL_FILE.exists(): # Still using file for this UI-triggered signal
        try:
            with open(TRIGGER_SIGNAL_FILE, 'r') as f: payload_from_file = json.load(f)
            response_data['command_pending'] = True
            response_data['payload'] = payload_from_file
            TRIGGER_SIGNAL_FILE.unlink() # Consume the signal
            app.logger.info(f"LOCAL_CHECK_API: Signal read from file '{TRIGGER_SIGNAL_FILE}' and file deleted. Payload: {payload_from_file}")
        except Exception as e:
            app.logger.error(f"LOCAL_CHECK_API: Error processing signal file '{TRIGGER_SIGNAL_FILE}': {e}", exc_info=True)
            # If error, don't send command_pending=True to avoid processing a bad signal.
    return jsonify(response_data)

@app.route('/api/ping', methods=['GET','HEAD'])
def api_ping():
    client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    app.logger.info(f"PING_API: Received /api/ping from IP:{client_ip}")
    response = jsonify({"status":"pong", "timestamp_utc": datetime.now(timezone.utc).isoformat()})
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return response, 200


# Endpoints PROTECTED by HTTP Basic Auth (for trigger_page.html)
@app.route('/')
@auth.login_required
def serve_trigger_page_main():
    if not users and (TRIGGER_PAGE_USER_ENV or TRIGGER_PAGE_PASSWORD_ENV):
        app.logger.error("AUTH ERROR: User/password env vars set, but 'users' dict is empty. Check config.")
        return "Server authentication configuration error.", 500
    
    app.logger.info(f"ROOT_UI: Request for '/' by user '{auth.current_user()}'. Serving 'trigger_page.html'.")
    try:
        # Ensure trigger_page.html is at the root of your application deployment on Render
        # or in a 'static' folder if you configure Flask to serve static files from there.
        # send_from_directory expects the directory relative to app.root_path or an absolute path.
        # If trigger_page.html is next to app_render.py, app.root_path is correct.
        if not os.path.exists(os.path.join(app.root_path, 'trigger_page.html')):
             app.logger.error(f"ROOT_UI: CRITICAL - 'trigger_page.html' does NOT exist in expected location ({os.path.join(app.root_path, 'trigger_page.html')}).")
             return "Error: Main page content not found (file missing).", 404
        return send_from_directory(app.root_path, 'trigger_page.html')
    except FileNotFoundError: # Should be caught by the os.path.exists check, but as a safeguard
        app.logger.error(f"ROOT_UI: CRITICAL - 'trigger_page.html' not found in directory '{app.root_path}'.")
        return "Error: Main page content not found.", 404
    except Exception as e:
        app.logger.error(f"ROOT_UI: Unexpected error serving 'trigger_page.html': {e}", exc_info=True)
        return "Internal server error serving UI.", 500

@app.route('/api/get_local_status', methods=['GET'])
@auth.login_required
def get_local_status_proxied():
    app.logger.info(f"PROXY_STATUS: API /api/get_local_status called by user '{auth.current_user()}'.")

    received_ui_token = request.args.get('ui_token')
    if REMOTE_UI_ACCESS_TOKEN_ENV: # Only check if the token is configured on the server
        if not received_ui_token or received_ui_token != REMOTE_UI_ACCESS_TOKEN_ENV:
            app.logger.warning(f"PROXY_STATUS: Invalid or missing ui_token for /api/get_local_status by user '{auth.current_user()}'. Received: '{received_ui_token}'")
            return jsonify({"error": "Invalid UI token"}), 403
    
    localtunnel_url = None
    # Fetch LT URL using Redis-first, file-fallback logic (similar to /api/get_local_downloader_url)
    try:
        if redis_client:
            url_bytes = redis_client.get(LOCALTUNNEL_URL_REDIS_KEY)
            if url_bytes: localtunnel_url = url_bytes.decode('utf-8')
        
        if not localtunnel_url and not redis_client : # If redis was None OR URL not in Redis
             if LOCALTUNNEL_URL_FILE.exists():
                with open(LOCALTUNNEL_URL_FILE, "r") as f: 
                    file_content = f.read().strip()
                    if file_content: localtunnel_url = file_content
    except Exception as e_url_fetch:
        app.logger.error(f"PROXY_STATUS: Error fetching LT URL for status proxy: {e_url_fetch}")
        # Proceed to check if localtunnel_url was fetched before error, or return error if critical

    if not localtunnel_url:
        app.logger.warning("PROXY_STATUS: Localtunnel URL not available for proxying status.")
        return jsonify({
            "overall_status_code_from_worker": "worker_unavailable",
            "overall_status_text": "Worker Local Indisponible", 
            "status_text": "Worker local non connecté ou URL non enregistrée.",
            "last_sequence_summary": None, # Ensure all fields are present even on error
            "recent_downloads": [] 
        }), 503

    try:
        target_url = f"{localtunnel_url.rstrip('/')}/api/get_remote_status_summary"
        headers_to_worker = {}
        if INTERNAL_WORKER_COMMS_TOKEN_ENV:
            headers_to_worker['X-Worker-Token'] = INTERNAL_WORKER_COMMS_TOKEN_ENV
        else:
            app.logger.warning(f"PROXY_STATUS: No INTERNAL_WORKER_COMMS_TOKEN_ENV set. Calling worker at {target_url} unauthenticated.")
            
        response_local = requests.get(target_url, headers=headers_to_worker, timeout=10)
        response_local.raise_for_status()
        local_data = response_local.json()

        # Pass through the structured data from app_new.py
        # The UI (trigger_page.html) will interpret these fields.
        return jsonify({
            "overall_status_code_from_worker": local_data.get("overall_status_code"),
            "overall_status_text": local_data.get("overall_status_text_display"), 
            "current_step_name": local_data.get("current_step_name"),
            "status_text": local_data.get("status_text_detail"), 
            "progress_current": local_data.get("progress_current", 0), 
            "progress_total": local_data.get("progress_total", 0),
            "recent_downloads": local_data.get("recent_downloads", []),
            "last_sequence_summary": local_data.get("last_sequence_summary")
        }), 200

    except requests.exceptions.Timeout:
        app.logger.warning(f"PROXY_STATUS: Timeout connecting to worker at {target_url}.")
        return jsonify({"overall_status_code_from_worker": "worker_timeout", "overall_status_text": "Worker Local (Timeout)", "status_text": "Timeout connexion worker."}), 504 
    except requests.exceptions.ConnectionError:
        app.logger.warning(f"PROXY_STATUS: Connection refused by worker at {target_url}.")
        return jsonify({"overall_status_code_from_worker": "worker_conn_refused", "overall_status_text": "Worker Local (Connexion Refusée)", "status_text": "Connexion worker refusée."}), 502
    except requests.exceptions.HTTPError as e_http:
        status_code = e_http.response.status_code
        err_msg = f"Worker Local (Erreur HTTP {status_code})"
        detail_msg = "Erreur HTTP du worker."
        if status_code == 401: # Specifically for token error from worker
            app.logger.error(f"PROXY_STATUS: 401 Unauthorized from worker at {target_url}. Check INTERNAL_WORKER_COMMS_TOKEN_ENV on both apps.")
            err_msg, detail_msg = "Erreur Authentification Interne (Worker)", "Auth vers worker local échouée."
        else:
            app.logger.error(f"PROXY_STATUS: HTTP error {status_code} from worker at {target_url}. Response: {e_http.response.text[:200]}")
        return jsonify({"overall_status_code_from_worker": f"worker_http_error_{status_code}", "overall_status_text": err_msg, "status_text": detail_msg}), status_code
    except requests.exceptions.RequestException as e_req:
        app.logger.error(f"PROXY_STATUS: Network error proxying to worker at {target_url}: {e_req}")
        return jsonify({"overall_status_code_from_worker": "worker_network_error", "overall_status_text": "Worker Local (Erreur Réseau)", "status_text": "Erreur réseau vers worker."}), 503
    except Exception as e_gen:
        app.logger.error(f"PROXY_STATUS: Generic error proxying to worker at {target_url}: {e_gen}", exc_info=True)
        return jsonify({"overall_status_code_from_worker": "proxy_internal_error", "overall_status_text": "Erreur Serveur Distant (Proxy Interne)", "status_text": "Erreur interne du proxy."}), 500

@app.route('/api/trigger_local_workflow', methods=['POST'])
@auth.login_required
def trigger_local_workflow_authed():
    app.logger.info(f"LOCAL_TRIGGER_API: Called by user '{auth.current_user()}'.")
    payload = request.json
    # Standardize payload, add timestamp
    if not payload: 
        payload = {"command": "start_manual_generic_from_ui"}
    elif not isinstance(payload, dict): 
        payload = {"command": "start_manual_generic_from_ui", "original_payload": payload}
    
    payload.setdefault("timestamp_utc", datetime.now(timezone.utc).isoformat())
    payload.setdefault("triggered_by_user", auth.current_user())

    try:
        # Using file for this UI-triggered signal remains simple and effective
        with open(TRIGGER_SIGNAL_FILE, "w") as f: json.dump(payload, f)
        app.logger.info(f"LOCAL_TRIGGER_API: Signal file '{TRIGGER_SIGNAL_FILE}' set for local worker. Payload: {payload}")
        return jsonify({"status": "ok", "message": "Local workflow signal set."}), 200
    except Exception as e:
        app.logger.error(f"LOCAL_TRIGGER_API: Error writing signal file '{TRIGGER_SIGNAL_FILE}': {e}", exc_info=True)
        return jsonify({"status": "error", "message": "Internal server error setting signal."}), 500

@app.route('/api/check_emails_and_download', methods=['POST'])
@auth.login_required
def api_check_emails_and_download_authed():
    app.logger.info(f"API_EMAIL_CHECK: Manual trigger for email check from user '{auth.current_user()}'.")
    
    def run_email_check_task_in_thread():
        with app.app_context(): # Important for threads using app context (like logging)
            try:
                app.logger.info("API_EMAIL_CHECK_THREAD: Starting email check and Make.com trigger...")
                webhooks_triggered = check_new_emails_and_trigger_make_webhook()
                app.logger.info(f"API_EMAIL_CHECK_THREAD: Email check and Make.com trigger finished. {webhooks_triggered} webhook(s) potentially triggered.")
            except Exception as e_thread:
                app.logger.error(f"API_EMAIL_CHECK_THREAD: Error during manual email check task: {e_thread}", exc_info=True)

    # Check critical configurations before starting thread
    if not all([msal_app, ONEDRIVE_REFRESH_TOKEN, SENDER_LIST_FOR_POLLING, MAKE_SCENARIO_WEBHOOK_URL]):
        app.logger.error("API_EMAIL_CHECK: Cannot start manual email check due to incomplete server configuration (MSAL/Polling/Webhook).")
        return jsonify({"status": "error", "message": "Configuration serveur pour la vérification email est incomplète."}), 503

    email_thread = threading.Thread(target=run_email_check_task_in_thread, name="ManualEmailCheckThread")
    email_thread.start()
    return jsonify({"status": "success", "message": "Vérification des emails (et déclenchement Make.com si applicable) lancée en arrière-plan."}), 202


# --- Démarrage de l'Application et des Threads ---
if __name__ == '__main__':
    is_debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    # Werkzeug reloader runs the main module twice. Only start threads in the main Werkzeug process.
    should_start_background_threads = not is_debug_mode or os.environ.get("WERKZEUG_RUN_MAIN") == "true"

    if should_start_background_threads:
        app.logger.info("MAIN_APP: Preparing to start background threads.")
        # Check for Email Polling Thread
        if all([msal_app, ONEDRIVE_REFRESH_TOKEN, SENDER_LIST_FOR_POLLING, MAKE_SCENARIO_WEBHOOK_URL]):
            email_poller_thread = threading.Thread(target=background_email_poller, name="EmailPollerThread", daemon=True)
            email_poller_thread.start()
            app.logger.info(f"MAIN_APP: Background email polling thread started successfully.")
        else:
            app.logger.warning("MAIN_APP: Background email polling thread NOT started due to incomplete MSAL/Polling/Webhook configuration.")
    else:
        app.logger.info("MAIN_APP: Background threads not started by this Werkzeug child process (expected in debug mode with reloader).")

    server_port = int(os.environ.get('PORT', 10000))
    
    # Final startup warnings for critical tokens
    if not users: app.logger.warning("MAIN_APP: HTTP Basic Auth for UI is not configured (TRIGGER_PAGE_USER/PASSWORD env vars not set or using fallback values and they are empty). UI is unprotected if fallbacks are empty.")
    if not EXPECTED_API_TOKEN: app.logger.critical("MAIN_APP: PROCESS_API_TOKEN not set or using empty fallback. Make.com endpoints INSECURE.")
    if not REGISTER_LOCAL_URL_TOKEN: app.logger.warning("MAIN_APP: REGISTER_LOCAL_URL_TOKEN not set or using empty fallback. Local worker registration endpoint potentially INSECURE.")
    if not REMOTE_UI_ACCESS_TOKEN_ENV and users: app.logger.info("MAIN_APP: REMOTE_UI_ACCESS_TOKEN for /api/get_local_status is not set (or using empty fallback), but HTTP Basic Auth is active. ui_token check will be skipped if user is auth'd by Basic Auth.")
    if not INTERNAL_WORKER_COMMS_TOKEN_ENV: app.logger.warning("MAIN_APP: INTERNAL_WORKER_COMMS_TOKEN not set or using empty fallback. app_render <-> app_new communication via /api/get_remote_status_summary unauthenticated.")


    app.logger.info(f"MAIN_APP: Flask server starting on 0.0.0.0:{server_port}. Debug: {is_debug_mode}")
    # use_reloader should be True if debug is True, but only if not managed by Werkzeug's main process already
    use_reloader_val = is_debug_mode and os.environ.get("WERKZEUG_RUN_MAIN") != "true"
    app.run(host='0.0.0.0', port=server_port, debug=is_debug_mode, use_reloader=use_reloader_val)
