from flask import Flask, jsonify, request, send_from_directory # Removed session, redirect, url_for as not used in this iteration
from flask_httpauth import HTTPBasicAuth # Importation
# from werkzeug.security import generate_password_hash, check_password_hash # For optional password hashing
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

from msal import ConfidentialClientApplication

app = Flask(__name__)
auth = HTTPBasicAuth() # Initialisation

# --- Tokens and Config de référence (basés sur l'image/description fournie) ---
# Ces valeurs seraient normalement UNIQUEMENT dans les variables d'environnement.
# Pour la démo, si la var d'env n'est pas trouvée, on utilise celles-ci comme fallback.
# ATTENTION: NE PAS FAIRE CELA EN PRODUCTION POUR DES SECRETS.
REF_TRIGGER_PAGE_USER = "admin"
REF_TRIGGER_PAGE_PASSWORD = "UDPVA#esKf40r@"
REF_REMOTE_UI_ACCESS_TOKEN = "0wbgXHiF3e!MqE"
REF_INTERNAL_WORKER_COMMS_TOKEN = "Fn*G14Vb'!Hkra7"
REF_PROCESS_API_TOKEN = "rnd_PW5cGYVf4g131imu9cYkFw27u8dY" # Pour Make.com / EXPECTED_API_TOKEN
REF_REGISTER_LOCAL_URL_TOKEN = "WMmWti@^n6RaUA"

REF_ONEDRIVE_CLIENT_ID = "6bbc767d-53e8-4b82-bd49-480d4c157a9b"
REF_ONEDRIVE_CLIENT_SECRET = "3Ah8Q~M7wk954ttbQRkt-xHn80enAeHd5wHG1XoEu" # Placeholder - VRAI SECRET DANS ENV
REF_ONEDRIVE_TENANT_ID = "60fb2b89-e5bf-4232-98f6-f1ecb90660c5"
# ONEDRIVE_REFRESH_TOKEN est trop sensible pour un fallback codé, doit venir de l'ENV.

REF_MAKE_SCENARIO_WEBHOOK_URL = "https://hook.eu2.make.com/wjcp43km1bgginyr1xu1pwui95ekr7gi"
REF_SENDER_OF_INTEREST_FOR_POLLING = "achats@media-solution.fr,camille.moine.pro@gmail.com,a.peault@media-solution.fr,v.lorent@media-solution.fr,technique@media-solution.fr,t.deslus@media-solution.fr"

REF_POLLING_TIMEZONE = "Europe/Paris"
REF_POLLING_ACTIVE_START_HOUR = 9
REF_POLLING_ACTIVE_END_HOUR = 23
REF_POLLING_ACTIVE_DAYS = "0,1,2,3,4" # Lundi à Vendredi
REF_EMAIL_POLLING_INTERVAL_SECONDS = 30 # Ou 60 si vous préférez
# ------------------------------------------------------------------------------------

# --- Configuration des Identifiants pour la page de trigger ---
TRIGGER_PAGE_USER_ENV = os.environ.get("TRIGGER_PAGE_USER", REF_TRIGGER_PAGE_USER)
TRIGGER_PAGE_PASSWORD_ENV = os.environ.get("TRIGGER_PAGE_PASSWORD", REF_TRIGGER_PAGE_PASSWORD)

users = {}
if TRIGGER_PAGE_USER_ENV and TRIGGER_PAGE_PASSWORD_ENV:
    users[TRIGGER_PAGE_USER_ENV] = TRIGGER_PAGE_PASSWORD_ENV
    app.logger.info(f"CFG AUTH: Trigger page user '{TRIGGER_PAGE_USER_ENV}' configured for HTTP Basic Auth.")
else:
    app.logger.warning("CFG AUTH: TRIGGER_PAGE_USER or TRIGGER_PAGE_PASSWORD not set. HTTP Basic Auth for trigger page will NOT be enforced actively (all attempts will pass verify_password if users dict is empty).")


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


# --- Configuration du Logging ---
log_level_str = os.environ.get('FLASK_LOG_LEVEL', 'INFO').upper()
log_level = getattr(logging, log_level_str, logging.INFO)
logging.basicConfig(level=log_level,
                    format='%(asctime)s - %(levelname)s - %(name)s - %(module)s - %(funcName)s - %(lineno)d - %(message)s')

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


# --- Chemins et Fichiers ---
SIGNAL_DIR = Path(os.environ.get("RENDER_DISC_PATH", "./signal_data_app_render"))
TRIGGER_SIGNAL_FILE = SIGNAL_DIR / "local_workflow_trigger_signal.json"
PROCESSED_URLS_ONEDRIVE_FILENAME = "processed_dropbox_urls_workflow.txt"
PROCESSED_WEBHOOK_TRIGGERS_ONEDRIVE_FILENAME = "processed_webhook_triggers.txt"
LOCALTUNNEL_URL_FILE = SIGNAL_DIR / "current_localtunnel_url.txt"
SIGNAL_DIR.mkdir(parents=True, exist_ok=True)

# --- Configuration OneDrive / MSAL ---
ONEDRIVE_CLIENT_ID = os.environ.get('ONEDRIVE_CLIENT_ID', REF_ONEDRIVE_CLIENT_ID)
ONEDRIVE_CLIENT_SECRET = os.environ.get('ONEDRIVE_CLIENT_SECRET', REF_ONEDRIVE_CLIENT_SECRET)
ONEDRIVE_REFRESH_TOKEN = os.environ.get('ONEDRIVE_REFRESH_TOKEN') # Must be set in ENV
ONEDRIVE_TENANT_ID = os.environ.get('ONEDRIVE_TENANT_ID', REF_ONEDRIVE_TENANT_ID)
ONEDRIVE_AUTHORITY = f"https://login.microsoftonline.com/{ONEDRIVE_TENANT_ID}" if ONEDRIVE_TENANT_ID != "consumers" else "https://login.microsoftonline.com/consumers"

ONEDRIVE_SCOPES_DELEGATED = ["Files.ReadWrite", "User.Read", "Mail.ReadWrite"]
ONEDRIVE_TARGET_PARENT_FOLDER_ID = os.environ.get('ONEDRIVE_TARGET_PARENT_FOLDER_ID', 'root')
ONEDRIVE_TARGET_SUBFOLDER_NAME = os.environ.get('ONEDRIVE_TARGET_SUBFOLDER_NAME', "DropboxDownloadsWorkflow")

msal_app = None
if ONEDRIVE_CLIENT_ID and ONEDRIVE_CLIENT_SECRET:
    app.logger.info(f"CFG MSAL: Initializing MSAL ConfidentialClientApplication. ClientID: '{ONEDRIVE_CLIENT_ID[:5]}...', Authority: {ONEDRIVE_AUTHORITY}")
    msal_app = ConfidentialClientApplication(ONEDRIVE_CLIENT_ID, authority=ONEDRIVE_AUTHORITY, client_credential=ONEDRIVE_CLIENT_SECRET)
else:
    app.logger.warning("CFG MSAL: OneDrive Client ID or Client Secret missing. OneDrive & Email Polling features will be disabled.")

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


# --- Fonctions Utilitaires OneDrive & MSAL (Identiques à la version précédente) ---
def sanitize_filename(filename_str, max_length=230):
    if filename_str is None: filename_str = "fichier_nom_absent"
    s = str(filename_str)
    s = re.sub(r'[<>:"/\\|?*]', '_', s)
    s = re.sub(r'\s+', '_', s)        
    s = re.sub(r'\.+', '.', s).strip('.')
    return s[:max_length] if s else "fichier_sans_nom_valide"

def get_onedrive_access_token():
    if not msal_app:
        app.logger.error("MSAL: MSAL app not configured. Cannot get token.")
        return None
    if not ONEDRIVE_REFRESH_TOKEN: # This MUST come from environment
        app.logger.error("MSAL: OneDrive refresh token missing (ONEDRIVE_REFRESH_TOKEN env var). Cannot get token.")
        return None
    
    token_result = msal_app.acquire_token_by_refresh_token(ONEDRIVE_REFRESH_TOKEN, scopes=ONEDRIVE_SCOPES_DELEGATED)
    
    if "access_token" in token_result:
        app.logger.info("MSAL: Access token obtained successfully.")
        if token_result.get("refresh_token") and token_result.get("refresh_token") != ONEDRIVE_REFRESH_TOKEN:
            app.logger.warning("MSAL: A new refresh token was issued by OneDrive. "
                               "IMPORTANT: Update the ONEDRIVE_REFRESH_TOKEN environment variable with this new token: "
                               f"'{token_result.get('refresh_token')}'")
        return token_result['access_token']
    else:
        app.logger.error(f"MSAL: Failed to obtain access token. Error: {token_result.get('error')}, "
                         f"Description: {token_result.get('error_description')}. Details: {token_result}")
        return None

def ensure_onedrive_folder(access_token, subfolder_name=None, parent_folder_id=None):
    target_folder_name = subfolder_name or ONEDRIVE_TARGET_SUBFOLDER_NAME
    effective_parent_id = parent_folder_id or ONEDRIVE_TARGET_PARENT_FOLDER_ID
    headers = {'Authorization': f'Bearer {access_token}', 'Content-Type': 'application/json'}
    parent_path_segment = f"items/{effective_parent_id}" if effective_parent_id and effective_parent_id.lower() != 'root' else "root"
    clean_target_folder_name = sanitize_filename(target_folder_name, 100)
    check_url = f"https://graph.microsoft.com/v1.0/me/drive/{parent_path_segment}/children?$filter=name eq '{clean_target_folder_name}'"
    try:
        response = requests.get(check_url, headers=headers, timeout=15)
        response.raise_for_status()
        children = response.json().get('value', [])
        if children:
            folder_id = children[0]['id']
            app.logger.info(f"OD_UTIL: Folder '{clean_target_folder_name}' found with ID: {folder_id} under parent '{effective_parent_id}'.")
            return folder_id
        
        app.logger.info(f"OD_UTIL: Folder '{clean_target_folder_name}' not found under parent '{effective_parent_id}'. Attempting to create.")
        create_url = f"https://graph.microsoft.com/v1.0/me/drive/{parent_path_segment}/children"
        payload = {
            "name": clean_target_folder_name,
            "folder": {},
            "@microsoft.graph.conflictBehavior": "rename"
        }
        response_create = requests.post(create_url, headers=headers, json=payload, timeout=15)
        response_create.raise_for_status()
        created_folder_id = response_create.json()['id']
        app.logger.info(f"OD_UTIL: Folder '{clean_target_folder_name}' created successfully with ID: {created_folder_id} under parent '{effective_parent_id}'.")
        return created_folder_id
    except requests.exceptions.RequestException as e:
        app.logger.error(f"OD_UTIL: Graph API error during folder ensure operation for '{clean_target_folder_name}': {e}")
        if hasattr(e, 'response') and e.response is not None:
            app.logger.error(f"OD_UTIL: API Response Status: {e.response.status_code}, Body: {e.response.text[:500]}")
        return None

def get_processed_items_from_onedrive_file(job_id_prefix, token, folder_id, filename):
    if not token or not folder_id:
        app.logger.error(f"DEDUP_ITEMS [{job_id_prefix}]: Token or FolderID missing for file '{filename}'.")
        return set()
    download_url = f"https://graph.microsoft.com/v1.0/me/drive/items/{folder_id}:/{sanitize_filename(filename)}:/content"
    headers = {'Authorization': f'Bearer {token}'}
    items = set()
    job_id = f"{job_id_prefix}_{time.time_ns() % 100000}"
    app.logger.debug(f"DEDUP_ITEMS [{job_id}]: Attempting to read '{filename}'.")
    try:
        response = requests.get(download_url, headers=headers, timeout=30)
        if response.status_code == 200:
            items.update(line.strip() for line in response.text.splitlines() if line.strip())
            app.logger.info(f"DEDUP_ITEMS [{job_id}]: Read {len(items)} items from '{filename}'.")
        elif response.status_code == 404:
            app.logger.info(f"DEDUP_ITEMS [{job_id}]: File '{filename}' not found in OneDrive. Will be created if items are added.")
        else:
            response.raise_for_status()
    except requests.exceptions.RequestException as e:
        app.logger.error(f"DEDUP_ITEMS [{job_id}]: Error downloading '{filename}': {e}")
        if hasattr(e, 'response') and e.response is not None:
            app.logger.error(f"DEDUP_ITEMS [{job_id}]: API Response: {e.response.status_code} - {e.response.text[:200]}")
    return items

def add_item_to_onedrive_file(job_id_prefix, token, folder_id, filename, item_to_add):
    if not all([token, folder_id, filename, item_to_add]):
        app.logger.error(f"DEDUP_ITEMS [{job_id_prefix}]: Missing parameters to add item to '{filename}'.")
        return False
    job_id = f"{job_id_prefix}_{time.time_ns() % 100000}"
    current_items = get_processed_items_from_onedrive_file(f"GET_{job_id_prefix}", token, folder_id, filename)
    if item_to_add in current_items:
        app.logger.info(f"DEDUP_ITEMS [{job_id}]: Item '{item_to_add}' already in '{filename}'. No update needed.")
        return True
    current_items.add(item_to_add)
    content_to_upload = "\n".join(sorted(list(current_items)))
    upload_url = f"https://graph.microsoft.com/v1.0/me/drive/items/{folder_id}:/{sanitize_filename(filename)}:/content?@microsoft.graph.conflictBehavior=replace"
    headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'text/plain; charset=utf-8'}
    app.logger.debug(f"DEDUP_ITEMS [{job_id}]: Updating '{filename}' with item '{item_to_add}'. Total items: {len(current_items)}.")
    try:
        response = requests.put(upload_url, headers=headers, data=content_to_upload.encode('utf-8'), timeout=60)
        response.raise_for_status()
        app.logger.info(f"DEDUP_ITEMS [{job_id}]: File '{filename}' updated successfully on OneDrive with '{item_to_add}'. Total items: {len(current_items)}.")
        return True
    except requests.exceptions.RequestException as e:
        app.logger.error(f"DEDUP_ITEMS [{job_id}]: Error uploading updates to '{filename}': {e}")
        if hasattr(e, 'response') and e.response is not None:
            app.logger.error(f"DEDUP_ITEMS [{job_id}]: API Response: {e.response.status_code} - {e.response.text[:200]}")
        return False

# --- Fonctions de Polling des Emails (Identiques à la version précédente) ---
def mark_email_as_read(token, msg_id):
    if not token or not msg_id:
        app.logger.error("MARK_READ: Token or Email ID missing.")
        return False
    url = f"https://graph.microsoft.com/v1.0/me/messages/{msg_id}"
    headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
    payload = {"isRead": True}
    try:
        response = requests.patch(url, headers=headers, json=payload, timeout=15)
        response.raise_for_status()
        app.logger.info(f"MARK_READ: Email {msg_id} marked as read.")
        return True
    except requests.exceptions.RequestException as e:
        app.logger.error(f"MARK_READ: API error marking email {msg_id} as read: {e}")
        return False

def check_new_emails_and_trigger_make_webhook():
    app.logger.info("POLLER: Email polling cycle started.")
    if not SENDER_LIST_FOR_POLLING:
        app.logger.warning("POLLER: SENDER_LIST_FOR_POLLING is empty. Email polling will be ineffective.")
        return 0
    if not MAKE_SCENARIO_WEBHOOK_URL:
        app.logger.error("POLLER: MAKE_SCENARIO_WEBHOOK_URL not configured. Cannot trigger Make.com.")
        return 0
    if not msal_app:
        app.logger.error("POLLER: MSAL app not configured. Cannot perform email polling.")
        return 0

    token = get_onedrive_access_token()
    if not token:
        app.logger.error("POLLER: Failed to get OneDrive token for email polling.")
        return 0
    
    onedrive_app_folder_id = ensure_onedrive_folder(token)
    if not onedrive_app_folder_id:
        app.logger.error("POLLER: Failed to ensure OneDrive folder for deduplication files. Cannot proceed.")
        return 0
        
    processed_email_ids = get_processed_items_from_onedrive_file(
        "WH_TRIG", token, onedrive_app_folder_id, PROCESSED_WEBHOOK_TRIGGERS_ONEDRIVE_FILENAME
    )
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
        headers_mail = {'Authorization': f'Bearer {token}', 'Prefer': 'outlook.body-content-type="text"'}
        response = requests.get(graph_url, headers=headers_mail, timeout=45)
        response.raise_for_status()
        emails = response.json().get('value', [])
        
        app.logger.info(f"POLLER: Found {len(emails)} unread email(s) matching criteria (before webhook deduplication).")
        
        for mail in emails:
            mail_id = mail['id']
            mail_subject = mail.get('subject', 'N/A_Subject')
            sender_address = mail.get('from', {}).get('emailAddress', {}).get('address', 'N/A_Sender').lower()

            if mail_id in processed_email_ids:
                app.logger.debug(f"POLLER: Email ID {mail_id} (Subject: '{mail_subject[:30]}...') already triggered a webhook. Skipping.")
                continue
            
            app.logger.info(f"POLLER: New relevant email found: ID={mail_id}, Subject='{mail_subject[:50]}...'. Triggering Make.com webhook.")
            
            payload_for_make = {
                "microsoft_graph_email_id": mail_id,
                "subject": mail_subject,
                "receivedDateTime": mail.get("receivedDateTime"),
                "sender_address": sender_address,
                "bodyPreview": mail.get('bodyPreview', '')
            }
            
            try:
                webhook_response = requests.post(MAKE_SCENARIO_WEBHOOK_URL, json=payload_for_make, timeout=30)
                if webhook_response.status_code == 200 and "accepted" in webhook_response.text.lower():
                    app.logger.info(f"POLLER: Make.com webhook call successful for email {mail_id}. Response: {webhook_response.status_code} - {webhook_response.text}")
                    if add_item_to_onedrive_file("WH_TRIG_ADD", token, onedrive_app_folder_id, PROCESSED_WEBHOOK_TRIGGERS_ONEDRIVE_FILENAME, mail_id):
                        triggered_webhook_count += 1
                        if not mark_email_as_read(token, mail_id):
                             app.logger.warning(f"POLLER: Failed to mark email {mail_id} as read, but webhook was sent and ID logged.")
                    else:
                        app.logger.error(f"POLLER: CRITICAL - Failed to log email ID {mail_id} to {PROCESSED_WEBHOOK_TRIGGERS_ONEDRIVE_FILENAME}. "
                                         "Email will NOT be marked as read to allow reprocessing.")
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
                
                if not all([ONEDRIVE_CLIENT_ID, ONEDRIVE_CLIENT_SECRET, ONEDRIVE_REFRESH_TOKEN, 
                            SENDER_LIST_FOR_POLLING, MAKE_SCENARIO_WEBHOOK_URL, msal_app]):
                    app.logger.warning("BG_POLLER: Essential configuration for polling is incomplete. Waiting 60s and will re-check.")
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
                app.logger.critical(f"BG_POLLER: Reached maximum consecutive errors ({MAX_CONSECUTIVE_ERRORS}). Stopping email polling thread to prevent further issues.")
                break
            
            sleep_on_error_duration = max(60, EMAIL_POLLING_INTERVAL_SECONDS) * (2 ** consecutive_error_count)
            app.logger.info(f"BG_POLLER: Sleeping for {sleep_on_error_duration}s due to error before retrying.")
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
    except Exception: return jsonify({"status": "error", "message": "Malformed JSON payload"}), 400 # Catch if get_json fails
    new_lt_url = data.get('localtunnel_url')
    if new_lt_url and not isinstance(new_lt_url, str): return jsonify({"status": "error", "message": "'localtunnel_url' must be a string or null."}), 400
    if new_lt_url and not (new_lt_url.startswith("http://") or new_lt_url.startswith("https://")): return jsonify({"status": "error", "message": "Invalid localtunnel URL format."}), 400
    try:
        if new_lt_url:
            with open(LOCALTUNNEL_URL_FILE, "w") as f: f.write(new_lt_url)
            app.logger.info(f"API_REG_LT_URL: Localtunnel URL registered: '{new_lt_url}'")
            return jsonify({"status": "success", "message": "Localtunnel URL registered."}), 200
        else:
            if LOCALTUNNEL_URL_FILE.exists(): LOCALTUNNEL_URL_FILE.unlink()
            app.logger.info(f"API_REG_LT_URL: Localtunnel URL unregistered/cleared.")
            return jsonify({"status": "success", "message": "Localtunnel URL unregistered/cleared."}), 200
    except Exception as e:
        app.logger.error(f"API_REG_LT_URL: Server error for localtunnel URL: {e}", exc_info=True)
        return jsonify({"status": "error", "message": "Server error processing localtunnel URL registration."}), 500

@app.route('/api/get_local_downloader_url', methods=['GET'])
def get_local_downloader_url_for_make():
    received_token = request.headers.get('X-API-Token')
    if not EXPECTED_API_TOKEN: app.logger.critical("API_GET_LT_URL: EXPECTED_API_TOKEN not set. Endpoint insecure.")
    elif received_token != EXPECTED_API_TOKEN:
        app.logger.warning(f"API_GET_LT_URL: Unauthorized access. Token: '{str(received_token)[:20]}...'")
        return jsonify({"status": "error", "message": "Unauthorized"}), 401
    if LOCALTUNNEL_URL_FILE.exists():
        try:
            with open(LOCALTUNNEL_URL_FILE, "r") as f: lt_url = f.read().strip()
            if lt_url: return jsonify({"status": "success", "localtunnel_url": lt_url}), 200
            else: return jsonify({"status": "error", "message": "Local worker URL not available (empty file)."}), 404
        except Exception as e: return jsonify({"status": "error", "message": "Server error reading local worker URL."}), 500
    else: return jsonify({"status": "error", "message": "Local worker URL not registered or unavailable."}), 404

@app.route('/api/log_processed_url', methods=['POST'])
def api_log_processed_url():
    api_token = request.headers.get('X-API-Token')
    if not EXPECTED_API_TOKEN: return jsonify({"status": "error", "message": "Server config error: API token not set."}), 500
    if api_token != EXPECTED_API_TOKEN: return jsonify({"status": "error", "message": "Unauthorized."}), 401
    try: data = request.get_json()
    except Exception: return jsonify({"s":"err","m":"JSON format error"}),400
    if not data or 'dropbox_url' not in data: return jsonify({"status": "error", "message": "'dropbox_url' is required."}), 400
    dropbox_url = data.get('dropbox_url')
    if not isinstance(dropbox_url, str) or not dropbox_url.lower().startswith("https://www.dropbox.com/"):
        return jsonify({"status": "error", "message": "Invalid Dropbox URL format."}), 400
    if not msal_app: return jsonify({"status":"error", "message":"OneDrive service not configured"}), 503
    token = get_onedrive_access_token()
    if not token: return jsonify({"status": "error", "message": "Failed to obtain OneDrive token."}), 500
    onedrive_app_folder_id = ensure_onedrive_folder(token)
    if not onedrive_app_folder_id: return jsonify({"status": "error", "message": "Failed to access OneDrive target folder."}), 500
    if add_item_to_onedrive_file("LOG_URL", token, onedrive_app_folder_id, PROCESSED_URLS_ONEDRIVE_FILENAME, dropbox_url):
        return jsonify({"status": "success", "message": f"URL logged."}), 200
    else: return jsonify({"status": "error", "message": f"Failed to update log."}), 500

@app.route('/api/check_trigger', methods=['GET'])
def check_local_workflow_trigger():
    response_data = {'command_pending': False, 'payload': None}
    if TRIGGER_SIGNAL_FILE.exists():
        try:
            with open(TRIGGER_SIGNAL_FILE, 'r') as f: payload_from_file = json.load(f)
            response_data['command_pending'] = True
            response_data['payload'] = payload_from_file
            TRIGGER_SIGNAL_FILE.unlink()
            app.logger.info(f"LOCAL_CHECK_API: Signal read and file deleted. Payload: {payload_from_file}")
        except Exception as e:
            app.logger.error(f"LOCAL_CHECK_API: Error processing signal file: {e}", exc_info=True)
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
        if not os.path.exists(os.path.join(app.root_path, 'trigger_page.html')):
            app.logger.error(f"ROOT_UI: CRITICAL - 'trigger_page.html' does NOT exist in ({app.root_path}).")
            return "Error: Main page content not found (file missing).", 404
        return send_from_directory(app.root_path, 'trigger_page.html')
    except FileNotFoundError:
        app.logger.error(f"ROOT_UI: CRITICAL - 'trigger_page.html' not found ({app.root_path}).")
        return "Error: Main page content not found.", 404
    except Exception as e:
        app.logger.error(f"ROOT_UI: Unexpected error serving 'trigger_page.html': {e}", exc_info=True)
        return "Internal server error serving UI.", 500

@app.route('/api/get_local_status', methods=['GET'])
@auth.login_required
def get_local_status_proxied():
    app.logger.info(f"PROXY_STATUS: API /api/get_local_status called by user '{auth.current_user()}'.")

    received_ui_token = request.args.get('ui_token')
    if REMOTE_UI_ACCESS_TOKEN_ENV:
        if not received_ui_token or received_ui_token != REMOTE_UI_ACCESS_TOKEN_ENV:
            app.logger.warning(f"PROXY_STATUS: Invalid ui_token for /api/get_local_status by user '{auth.current_user()}'.")
            return jsonify({"error": "Invalid UI token"}), 403
    
    localtunnel_url = None
    if LOCALTUNNEL_URL_FILE.exists():
        try:
            with open(LOCALTUNNEL_URL_FILE, "r") as f: localtunnel_url = f.read().strip()
        except Exception as e:
            app.logger.error(f"PROXY_STATUS: Error reading LT URL file: {e}")
            return jsonify({"overall_status_text": "Erreur Serveur Distant", "status_text": "Err lecture URL worker."}), 500

    if not localtunnel_url:
        app.logger.warning("PROXY_STATUS: LT URL not available.")
        return jsonify({"overall_status_text": "Worker Local Indisponible", "status_text": "Worker non connecté."}), 503

    try:
        target_url = f"{localtunnel_url.rstrip('/')}/api/get_remote_status_summary"
        headers_to_worker = {}
        if INTERNAL_WORKER_COMMS_TOKEN_ENV:
            headers_to_worker['X-Worker-Token'] = INTERNAL_WORKER_COMMS_TOKEN_ENV
        else:
            app.logger.warning(f"PROXY_STATUS: No INTERNAL_WORKER_COMMS_TOKEN_ENV. Calling {target_url} unauthenticated.")
            
        response_local = requests.get(target_url, headers=headers_to_worker, timeout=10)
        response_local.raise_for_status()
        local_data = response_local.json()

        # Mapping logic (simplified for brevity, use your existing logic)
        overall_status_display_text = local_data.get("overall_status_code", "idle") # Needs proper mapping
        status_text_detail_val = local_data.get("last_updated_utc", "")
        # ... (Your existing logic for overall_status_display_text, status_text_detail_val, progress, etc.)

        return jsonify({
            "overall_status_text": overall_status_display_text, 
            "status_text": status_text_detail_val, # Make sure this is the correct structure
            "progress_current": local_data.get("progress_current", 0), 
            "progress_total": local_data.get("progress_total", 0),
            "current_step_name": local_data.get("current_step_name"), 
            "recent_downloads": local_data.get("recent_downloads", [])
        }), 200

    except requests.exceptions.Timeout:
        return jsonify({"overall_status_text": "Worker Local (Timeout)", "status_text": "Timeout connexion worker."}), 504 
    except requests.exceptions.ConnectionError:
        return jsonify({"overall_status_text": "Worker Local (Connexion Refusée)", "status_text": "Connexion worker refusée."}), 502
    except requests.exceptions.HTTPError as e_http:
        if e_http.response.status_code == 401:
            app.logger.error(f"PROXY_STATUS: 401 Unauthorized from worker {target_url}. Check INTERNAL_WORKER_COMMS_TOKEN_ENV.")
            return jsonify({"overall_status_text": "Erreur Authentification Interne", "status_text": "Auth vers worker local échouée."}), 401
        return jsonify({"overall_status_text": f"Worker Local (Erreur HTTP {e_http.response.status_code})", "status_text": "Erreur HTTP du worker."}), e_http.response.status_code
    except requests.exceptions.RequestException as e_req:
        return jsonify({"overall_status_text": "Worker Local (Erreur Réseau)", "status_text": "Erreur réseau vers worker."}), 503
    except Exception as e_gen:
        app.logger.error(f"PROXY_STATUS: Generic error for {target_url}: {e_gen}", exc_info=True)
        return jsonify({"overall_status_text": "Erreur Serveur Distant (Proxy)", "status_text": "Erreur interne proxy."}), 500

@app.route('/api/trigger_local_workflow', methods=['POST'])
@auth.login_required
def trigger_local_workflow_authed():
    app.logger.info(f"LOCAL_TRIGGER_API: Called by user '{auth.current_user()}'.")
    payload = request.json
    if not payload: payload = {"command": "start_manual_generic", "timestamp_utc": datetime.now(timezone.utc).isoformat()}
    elif not isinstance(payload, dict): 
        payload = {"command": "start_manual_generic", "original_payload": payload, "timestamp_utc": datetime.now(timezone.utc).isoformat()}
    else: payload.setdefault("timestamp_utc", datetime.now(timezone.utc).isoformat())
    try:
        with open(TRIGGER_SIGNAL_FILE, "w") as f: json.dump(payload, f)
        app.logger.info(f"LOCAL_TRIGGER_API: Signal file '{TRIGGER_SIGNAL_FILE}' set. Payload: {payload}")
        return jsonify({"status": "ok", "message": "Local workflow signal set."}), 200
    except Exception as e:
        app.logger.error(f"LOCAL_TRIGGER_API: Error writing signal file: {e}", exc_info=True)
        return jsonify({"status": "error", "message": "Internal server error setting signal."}), 500

@app.route('/api/check_emails_and_download', methods=['POST'])
@auth.login_required
def api_check_emails_and_download_authed():
    app.logger.info(f"API_EMAIL_CHECK: Manual trigger from user '{auth.current_user()}'.")
    def run_email_check_task_in_thread():
        with app.app_context(): 
            try:
                app.logger.info("API_EMAIL_CHECK_THREAD: Starting email check...")
                webhooks_triggered = check_new_emails_and_trigger_make_webhook()
                app.logger.info(f"API_EMAIL_CHECK_THREAD: Finished. {webhooks_triggered} webhook(s) triggered.")
            except Exception as e_thread:
                app.logger.error(f"API_EMAIL_CHECK_THREAD: Error: {e_thread}", exc_info=True)

    if not all([ONEDRIVE_CLIENT_ID, ONEDRIVE_CLIENT_SECRET, ONEDRIVE_REFRESH_TOKEN, SENDER_LIST_FOR_POLLING, MAKE_SCENARIO_WEBHOOK_URL, msal_app]):
        return jsonify({"status": "error", "message": "Config serveur email incomplète."}), 503

    email_thread = threading.Thread(target=run_email_check_task_in_thread, name="ManualEmailCheckThread")
    email_thread.start()
    return jsonify({"status": "success", "message": "Vérification emails (arrière-plan) lancée."}), 202


# --- Démarrage de l'Application et des Threads ---
if __name__ == '__main__':
    is_debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    should_start_background_threads = not is_debug_mode or os.environ.get("WERKZEUG_RUN_MAIN") == "true"

    if should_start_background_threads:
        app.logger.info("MAIN_APP: Preparing to start background threads.")
        if all([ONEDRIVE_CLIENT_ID, ONEDRIVE_CLIENT_SECRET, ONEDRIVE_REFRESH_TOKEN, msal_app, SENDER_LIST_FOR_POLLING, MAKE_SCENARIO_WEBHOOK_URL]):
            email_poller_thread = threading.Thread(target=background_email_poller, name="EmailPollerThread", daemon=True)
            email_poller_thread.start()
            app.logger.info(f"MAIN_APP: Email polling thread started.")
        else:
            app.logger.warning("MAIN_APP: Email polling thread NOT started due to incomplete OneDrive/MSAL/Webhook config.")
    else:
        app.logger.info("MAIN_APP: Background threads not started by this Werkzeug child process.")

    server_port = int(os.environ.get('PORT', 10000))
    
    if not users: app.logger.warning("MAIN_APP: HTTP Basic Auth for UI is not configured (TRIGGER_PAGE_USER/PASSWORD env vars not set or using fallback values and they are empty). UI is unprotected if fallbacks are empty.")
    if not EXPECTED_API_TOKEN or EXPECTED_API_TOKEN == REF_PROCESS_API_TOKEN and not REF_PROCESS_API_TOKEN : app.logger.critical("MAIN_APP: PROCESS_API_TOKEN not set or using empty fallback. Make.com endpoints INSECURE.")
    if not REGISTER_LOCAL_URL_TOKEN or REGISTER_LOCAL_URL_TOKEN == REF_REGISTER_LOCAL_URL_TOKEN and not REF_REGISTER_LOCAL_URL_TOKEN: app.logger.warning("MAIN_APP: REGISTER_LOCAL_URL_TOKEN not set or using empty fallback. Local worker registration endpoint potentially INSECURE.")
    if not REMOTE_UI_ACCESS_TOKEN_ENV and users: app.logger.info("MAIN_APP: REMOTE_UI_ACCESS_TOKEN for /api/get_local_status is not set (or using empty fallback), but HTTP Basic Auth is active. ui_token check will be skipped if user is auth'd by Basic Auth.")
    if not INTERNAL_WORKER_COMMS_TOKEN_ENV or INTERNAL_WORKER_COMMS_TOKEN_ENV == REF_INTERNAL_WORKER_COMMS_TOKEN and not REF_INTERNAL_WORKER_COMMS_TOKEN : app.logger.warning("MAIN_APP: INTERNAL_WORKER_COMMS_TOKEN not set or using empty fallback. app_render <-> app_new communication unauthenticated.")


    app.logger.info(f"MAIN_APP: Flask server starting on 0.0.0.0:{server_port}. Debug: {is_debug_mode}")
    app.run(host='0.0.0.0', port=server_port, debug=is_debug_mode, use_reloader=(is_debug_mode and os.environ.get("WERKZEUG_RUN_MAIN") != "true"))
