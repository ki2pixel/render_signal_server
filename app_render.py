from flask import Flask, jsonify, request, send_from_directory, current_app
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

# --- Configuration du Logging ---
log_level_str = os.environ.get('FLASK_LOG_LEVEL', 'INFO').upper()
log_level = getattr(logging, log_level_str, logging.INFO)
logging.basicConfig(level=log_level,
                    format='%(asctime)s - %(levelname)s - %(name)s - %(module)s - %(funcName)s - %(lineno)d - %(message)s')

# --- Configuration du Polling des Emails ---
POLLING_TIMEZONE_STR = os.environ.get("POLLING_TIMEZONE", "UTC")
POLLING_ACTIVE_START_HOUR = int(os.environ.get("POLLING_ACTIVE_START_HOUR", 0))
POLLING_ACTIVE_END_HOUR = int(os.environ.get("POLLING_ACTIVE_END_HOUR", 24)) 
POLLING_ACTIVE_DAYS_RAW = os.environ.get("POLLING_ACTIVE_DAYS", "0,1,2,3,4,5,6") 
POLLING_ACTIVE_DAYS = []
if POLLING_ACTIVE_DAYS_RAW:
    try:
        POLLING_ACTIVE_DAYS = [int(d.strip()) for d in POLLING_ACTIVE_DAYS_RAW.split(',') if d.strip().isdigit() and 0 <= int(d.strip()) <= 6]
    except ValueError:
        app.logger.warning(f"CFG POLL: Invalid POLLING_ACTIVE_DAYS ('{POLLING_ACTIVE_DAYS_RAW}'). Using all days.")
        POLLING_ACTIVE_DAYS = list(range(7))
if not POLLING_ACTIVE_DAYS: POLLING_ACTIVE_DAYS = list(range(7))

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
        app.logger.warning(f"CFG POLL: 'zoneinfo' module not available for Python version. Using UTC. '{POLLING_TIMEZONE_STR}' ignored.")
        POLLING_TIMEZONE_STR = "UTC"
if TZ_FOR_POLLING is None: 
    TZ_FOR_POLLING = timezone.utc
    app.logger.info(f"CFG POLL: Using timezone 'UTC' for polling schedule.")

EMAIL_POLLING_INTERVAL_SECONDS = int(os.environ.get("EMAIL_POLLING_INTERVAL_SECONDS", 60))
POLLING_INACTIVE_CHECK_INTERVAL_SECONDS = int(os.environ.get("POLLING_INACTIVE_CHECK_INTERVAL_SECONDS", 600))
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
ONEDRIVE_CLIENT_ID = os.environ.get('ONEDRIVE_CLIENT_ID')
ONEDRIVE_CLIENT_SECRET = os.environ.get('ONEDRIVE_CLIENT_SECRET')
ONEDRIVE_REFRESH_TOKEN = os.environ.get('ONEDRIVE_REFRESH_TOKEN')
ONEDRIVE_AUTHORITY = "https://login.microsoftonline.com/consumers"
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
MAKE_SCENARIO_WEBHOOK_URL = os.environ.get("MAKE_SCENARIO_WEBHOOK_URL")
SENDER_OF_INTEREST_FOR_POLLING_RAW = os.environ.get("SENDER_OF_INTEREST_FOR_POLLING")
SENDER_LIST_FOR_POLLING = []
if SENDER_OF_INTEREST_FOR_POLLING_RAW:
    SENDER_LIST_FOR_POLLING = [e.strip().lower() for e in SENDER_OF_INTEREST_FOR_POLLING_RAW.split(',') if e.strip()]
if SENDER_LIST_FOR_POLLING:
    app.logger.info(f"CFG POLL: Monitoring emails from {len(SENDER_LIST_FOR_POLLING)} senders: {SENDER_LIST_FOR_POLLING}")
else:
    app.logger.warning("CFG POLL: SENDER_OF_INTEREST_FOR_POLLING not set. Email polling will likely be ineffective.")

EXPECTED_API_TOKEN = os.environ.get("PROCESS_API_TOKEN") 
if not EXPECTED_API_TOKEN:
    app.logger.warning("CFG TOKEN: PROCESS_API_TOKEN not set. API endpoints called by Make.com will be insecure.")
else:
    app.logger.info(f"CFG TOKEN: PROCESS_API_TOKEN (for Make.com calls) configured: '{EXPECTED_API_TOKEN[:5]}...'")

REGISTER_LOCAL_URL_TOKEN = os.environ.get("REGISTER_LOCAL_URL_TOKEN")
if not REGISTER_LOCAL_URL_TOKEN:
    app.logger.warning("CFG TOKEN: REGISTER_LOCAL_URL_TOKEN not set. Endpoint for registering local worker URL will be insecure if not matching on app_new.py.")
else:
    app.logger.info(f"CFG TOKEN: REGISTER_LOCAL_URL_TOKEN (for local worker registration) configured: '{REGISTER_LOCAL_URL_TOKEN[:5]}...'")

REMOTE_UI_ACCESS_TOKEN_ENV = os.environ.get("REMOTE_UI_ACCESS_TOKEN")
INTERNAL_WORKER_COMMS_TOKEN_ENV = os.environ.get("INTERNAL_WORKER_COMMS_TOKEN")

if not REMOTE_UI_ACCESS_TOKEN_ENV:
    app.logger.warning("CFG TOKEN: REMOTE_UI_ACCESS_TOKEN_ENV not set. Endpoint /api/get_local_status will be INSECURE if accessed directly without a token check in a reverse proxy, for example.")
else:
    app.logger.info(f"CFG TOKEN: REMOTE_UI_ACCESS_TOKEN_ENV for UI access to /api/get_local_status configured: '{REMOTE_UI_ACCESS_TOKEN_ENV[:5]}...'")

if not INTERNAL_WORKER_COMMS_TOKEN_ENV:
    app.logger.warning("CFG TOKEN: INTERNAL_WORKER_COMMS_TOKEN_ENV not set. Communication with local worker app_new.py (for /api/get_remote_status_summary) will be INSECURE.")
else:
    app.logger.info(f"CFG TOKEN: INTERNAL_WORKER_COMMS_TOKEN_ENV for worker communication configured.")


# --- Fonctions Utilitaires OneDrive & MSAL ---
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
    if not ONEDRIVE_REFRESH_TOKEN:
        app.logger.error("MSAL: OneDrive refresh token missing. Cannot get token.")
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

# --- Fonctions de Polling des Emails ---
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
    global REGISTER_LOCAL_URL_TOKEN

    received_token = request.headers.get('X-Register-Token')
    if REGISTER_LOCAL_URL_TOKEN and received_token != REGISTER_LOCAL_URL_TOKEN:
        app.logger.warning(f"API_REG_LT_URL: Unauthorized access attempt to register local URL. Token: '{str(received_token)[:20]}...'")
        return jsonify({"status": "error", "message": "Unauthorized"}), 401
    
    try:
        data = request.get_json()
        if not data:
            app.logger.error("API_REG_LT_URL: No JSON payload received.")
            return jsonify({"status": "error", "message": "Invalid JSON payload"}), 400
    except Exception as e_json:
        app.logger.error(f"API_REG_LT_URL: Error parsing JSON payload: {e_json}")
        return jsonify({"status": "error", "message": "Malformed JSON payload"}), 400

    new_lt_url = data.get('localtunnel_url')

    if new_lt_url and not isinstance(new_lt_url, str):
        app.logger.error(f"API_REG_LT_URL: 'localtunnel_url' field is not a string: {type(new_lt_url)}")
        return jsonify({"status": "error", "message": "'localtunnel_url' must be a string or null."}), 400
        
    if new_lt_url and not (new_lt_url.startswith("http://") or new_lt_url.startswith("https://")):
        app.logger.error(f"API_REG_LT_URL: Invalid localtunnel URL format received: '{new_lt_url}'")
        return jsonify({"status": "error", "message": "Invalid localtunnel URL format."}), 400

    try:
        if new_lt_url:
            with open(LOCALTUNNEL_URL_FILE, "w") as f:
                f.write(new_lt_url)
            app.logger.info(f"API_REG_LT_URL: Localtunnel URL for local worker registered: '{new_lt_url}'")
            return jsonify({"status": "success", "message": "Localtunnel URL registered."}), 200
        else:
            if LOCALTUNNEL_URL_FILE.exists():
                LOCALTUNNEL_URL_FILE.unlink()
                app.logger.info(f"API_REG_LT_URL: Localtunnel URL file removed (local worker likely stopped or unregistered).")
            else:
                app.logger.info(f"API_REG_LT_URL: Received request to unregister localtunnel URL, but no file existed. No action taken.")
            return jsonify({"status": "success", "message": "Localtunnel URL unregistered/cleared."}), 200
            
    except Exception as e:
        app.logger.error(f"API_REG_LT_URL: Server error during file operation for localtunnel URL: {e}", exc_info=True)
        return jsonify({"status": "error", "message": "Server error processing localtunnel URL registration."}), 500

@app.route('/api/get_local_downloader_url', methods=['GET'])
def get_local_downloader_url_for_make():
    received_token = request.headers.get('X-API-Token')
    if not EXPECTED_API_TOKEN :
        app.logger.critical("API_GET_LT_URL: EXPECTED_API_TOKEN not set on server. Endpoint is insecure but proceeding.")
    elif received_token != EXPECTED_API_TOKEN:
        app.logger.warning(f"API_GET_LT_URL: Unauthorized access attempt to get local URL. Token: '{str(received_token)[:20]}...'")
        return jsonify({"status": "error", "message": "Unauthorized"}), 401
        
    if LOCALTUNNEL_URL_FILE.exists():
        try:
            with open(LOCALTUNNEL_URL_FILE, "r") as f:
                lt_url = f.read().strip()
            if lt_url:
                app.logger.info(f"API_GET_LT_URL: Providing localtunnel URL to Make.com: '{lt_url}'")
                return jsonify({"status": "success", "localtunnel_url": lt_url}), 200
            else:
                app.logger.warning("API_GET_LT_URL: Localtunnel URL file found but is empty. Local worker may not be ready.")
                return jsonify({"status": "error", "message": "Local worker URL is currently not available (empty file)."}), 404
        except Exception as e:
            app.logger.error(f"API_GET_LT_URL: Error reading localtunnel URL file: {e}", exc_info=True)
            return jsonify({"status": "error", "message": "Server error reading local worker URL."}), 500
    else:
        app.logger.warning("API_GET_LT_URL: Localtunnel URL file not found. Local worker may not have registered yet or is offline.")
        return jsonify({"status": "error", "message": "Local worker URL not registered or currently unavailable."}), 404

@app.route('/api/log_processed_url', methods=['POST'])
def api_log_processed_url():
    api_token = request.headers.get('X-API-Token')
    if not EXPECTED_API_TOKEN:
        app.logger.error("API_LOG_URL: PROCESS_API_TOKEN not configured. Cannot authenticate.")
        return jsonify({"status": "error", "message": "Server configuration error: API token not set."}), 500
    if api_token != EXPECTED_API_TOKEN:
        app.logger.warning(f"API_LOG_URL: Unauthorized access attempt. Token: '{str(api_token)[:20]}...'")
        return jsonify({"status": "error", "message": "Unauthorized."}), 401
    
    app.logger.info("API_LOG_URL: API token validated for logging processed URL.")
    
    try: data = request.get_json()
    except Exception as e_json: app.logger.error(f"API_LOG_URL: JSON parsing error: {e_json}"); return jsonify({"s":"err","m":f"JSON format error: {e_json}"}),400

    if not data or 'dropbox_url' not in data:
        app.logger.error(f"API_LOG_URL: 'dropbox_url' missing in payload. Data: {data}")
        return jsonify({"status": "error", "message": "'dropbox_url' is required."}), 400
        
    dropbox_url = data.get('dropbox_url')
    email_subject = data.get('email_subject', 'N/A_Subject_From_Local_Worker')
    email_id = data.get('microsoft_graph_email_id', 'N/A_EmailID_From_Local_Worker')
    job_id_log = f"LOGURL_{str(email_id)[-10:]}_{time.time_ns() % 100000}"

    if not isinstance(dropbox_url, str) or not dropbox_url.lower().startswith("https://www.dropbox.com/"):
        app.logger.error(f"API_LOG_URL [{job_id_log}]: Invalid Dropbox URL format: '{dropbox_url}'")
        return jsonify({"status": "error", "message": "Invalid Dropbox URL format."}), 400

    app.logger.info(f"API_LOG_URL [{job_id_log}]: Request to log URL: '{dropbox_url}', Subject: '{email_subject}', EmailID: '{email_id}'")

    if not msal_app: app.logger.error(f"API_LOG_URL [{job_id_log}]: MSAL not configured."); return jsonify({"status":"error", "message":"OneDrive service not configured on server"}), 503

    token = get_onedrive_access_token()
    if not token:
        app.logger.error(f"API_LOG_URL [{job_id_log}]: Failed to get OneDrive token.")
        return jsonify({"status": "error", "message": "Failed to obtain OneDrive token for logging."}), 500
    
    onedrive_app_folder_id = ensure_onedrive_folder(token)
    if not onedrive_app_folder_id:
        app.logger.error(f"API_LOG_URL [{job_id_log}]: Failed to ensure OneDrive folder.")
        return jsonify({"status": "error", "message": "Failed to access OneDrive target folder for logging."}), 500
        
    if add_item_to_onedrive_file(f"LOG_URL_{job_id_log}", token, onedrive_app_folder_id, PROCESSED_URLS_ONEDRIVE_FILENAME, dropbox_url):
        app.logger.info(f"API_LOG_URL [{job_id_log}]: Successfully logged URL '{dropbox_url}' to {PROCESSED_URLS_ONEDRIVE_FILENAME}.")
        return jsonify({"status": "success", "message": f"URL '{dropbox_url}' logged as processed."}), 200
    else:
        app.logger.error(f"API_LOG_URL [{job_id_log}]: Failed to log URL '{dropbox_url}' to {PROCESSED_URLS_ONEDRIVE_FILENAME}.")
        return jsonify({"status": "error", "message": f"Failed to update persistent log for URL '{dropbox_url}'."}), 500

@app.route('/api/trigger_local_workflow', methods=['POST'])
def trigger_local_workflow():
    payload = request.json
    if not payload: payload = {"command": "start_manual_generic", "timestamp_utc": datetime.now(timezone.utc).isoformat()}
    elif not isinstance(payload, dict): 
        app.logger.warning(f"LOCAL_TRIGGER_API: Payload received is not a dictionary: {payload}. Wrapping it.")
        payload = {"command": "start_manual_generic", "original_payload": payload, "timestamp_utc": datetime.now(timezone.utc).isoformat()}
    else: 
        payload.setdefault("timestamp_utc", datetime.now(timezone.utc).isoformat())

    try:
        with open(TRIGGER_SIGNAL_FILE, "w") as f: json.dump(payload, f)
        app.logger.info(f"LOCAL_TRIGGER_API: Signal file '{TRIGGER_SIGNAL_FILE}' created/updated. Payload: {payload}")
        return jsonify({"status": "ok", "message": "Local workflow signal set."}), 200
    except Exception as e:
        app.logger.error(f"LOCAL_TRIGGER_API: Error writing signal file '{TRIGGER_SIGNAL_FILE}': {e}", exc_info=True)
        return jsonify({"status": "error", "message": "Internal server error setting signal."}), 500

@app.route('/api/check_trigger', methods=['GET'])
def check_local_workflow_trigger():
    response_data = {'command_pending': False, 'payload': None}
    if TRIGGER_SIGNAL_FILE.exists():
        try:
            with open(TRIGGER_SIGNAL_FILE, 'r') as f: payload_from_file = json.load(f)
            response_data['command_pending'] = True
            response_data['payload'] = payload_from_file
            TRIGGER_SIGNAL_FILE.unlink()
            app.logger.info(f"LOCAL_CHECK_API: Signal read from '{TRIGGER_SIGNAL_FILE}' and file deleted. Payload: {payload_from_file}")
        except Exception as e:
            app.logger.error(f"LOCAL_CHECK_API: Error processing/deleting signal file '{TRIGGER_SIGNAL_FILE}': {e}", exc_info=True)
    return jsonify(response_data)

@app.route('/api/ping', methods=['GET','HEAD'])
def api_ping():
    client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    user_agent = request.headers.get('User-Agent', 'N/A_User_Agent')
    app.logger.info(f"PING_API: Received /api/ping from IP:{client_ip}, UA:{user_agent} at {datetime.now(timezone.utc).isoformat()}")
    response = jsonify({"status":"pong", "timestamp_utc": datetime.now(timezone.utc).isoformat()})
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response, 200

@app.route('/')
def serve_trigger_page_main():
    app.logger.info("ROOT_UI: Request for '/'. Attempting to serve 'trigger_page.html'.")
    try:
        if not os.path.exists(os.path.join(app.root_path, 'trigger_page.html')):
            app.logger.error(f"ROOT_UI: CRITICAL - 'trigger_page.html' does NOT exist in application root path ({app.root_path}). Check deployment.")
            return "Error: Main page content not found (file missing).", 404
        return send_from_directory(app.root_path, 'trigger_page.html')
    except FileNotFoundError:
        app.logger.error(f"ROOT_UI: CRITICAL - 'trigger_page.html' not found in application root path ({app.root_path}).")
        return "Error: Main page content not found.", 404
    except Exception as e:
        app.logger.error(f"ROOT_UI: Unexpected error serving 'trigger_page.html': {e}", exc_info=True)
        return "Internal server error serving UI.", 500

@app.route('/api/get_local_status', methods=['GET'])
def get_local_status_proxied():
    global REMOTE_UI_ACCESS_TOKEN_ENV, INTERNAL_WORKER_COMMS_TOKEN_ENV

    received_ui_token = request.args.get('ui_token')
    if REMOTE_UI_ACCESS_TOKEN_ENV:
        if not received_ui_token or received_ui_token != REMOTE_UI_ACCESS_TOKEN_ENV:
            app.logger.warning(f"PROXY_STATUS: Unauthorized access attempt to /api/get_local_status. Missing or invalid ui_token.")
            return jsonify({"error": "Unauthorized"}), 401
    
    localtunnel_url = None
    if LOCALTUNNEL_URL_FILE.exists():
        try:
            with open(LOCALTUNNEL_URL_FILE, "r") as f:
                localtunnel_url = f.read().strip()
        except Exception as e:
            app.logger.error(f"PROXY_STATUS: Error reading localtunnel URL file: {e}")
            return jsonify({
                "overall_status_text": "Erreur Serveur Distant",
                "status_text": "Impossible de lire l'URL du worker local.",
                "progress_current": 0, "progress_total": 0, "current_step_name": None,
                "recent_downloads": []
            }), 500

    if not localtunnel_url:
        app.logger.warning("PROXY_STATUS: Localtunnel URL not available for proxying status.")
        return jsonify({
            "overall_status_text": "Worker Local Indisponible",
            "status_text": "Le worker local n'est pas connecté ou n'a pas communiqué son adresse.",
            "progress_current": 0, "progress_total": 0, "current_step_name": None,
            "recent_downloads": []
        }), 503

    try:
        target_url = f"{localtunnel_url.rstrip('/')}/api/get_remote_status_summary"
        headers_to_worker = {}
        if INTERNAL_WORKER_COMMS_TOKEN_ENV:
            headers_to_worker['X-Worker-Token'] = INTERNAL_WORKER_COMMS_TOKEN_ENV
        else:
            app.logger.warning(f"PROXY_STATUS: Communicating with worker {target_url} without X-Worker-Token as INTERNAL_WORKER_COMMS_TOKEN_ENV is not set.")
            
        response_local = requests.get(target_url, headers=headers_to_worker, timeout=10)
        response_local.raise_for_status() # Will raise HTTPError for 4xx/5xx responses
        local_data = response_local.json()

        overall_status_text_val = "Inconnu"
        status_text_detail_val = local_data.get("last_updated_utc", "")

        status_code_map = {
            "idle": "Inactif / Prêt",
            "auto_mode_active": "Mode Auto Actif - Séquence en cours",
            "sequence_running": "Séquence Manuelle en Cours",
            "step_running": "Étape Individuelle en Cours",
            "completed_success_recent": "Terminée avec succès (récent)",
            "completed_error_recent": "Terminée avec erreurs (récent)",
        }
        overall_status_text_val = status_code_map.get(local_data.get("overall_status_code"), "Statut Indéterminé")

        current_step_name_val = local_data.get("current_step_name")
        if current_step_name_val:
            status_text_detail_val = f"Étape: {current_step_name_val}. (MàJ: {status_text_detail_val})"
        else:
            status_text_detail_val = f"(MàJ: {status_text_detail_val})"
        
        if local_data.get("last_updated_utc"):
            try:
                last_update_dt_str = local_data["last_updated_utc"]
                if last_update_dt_str.endswith('Z'): # Compatibility with ISO 8601 'Z' for UTC
                    last_update_dt_str = last_update_dt_str[:-1] + '+00:00'
                last_update_dt = datetime.fromisoformat(last_update_dt_str)
                if last_update_dt.tzinfo is None: # Ensure timezone aware for comparison
                    last_update_dt = last_update_dt.replace(tzinfo=timezone.utc)

                if datetime.now(timezone.utc) - last_update_dt > timedelta(minutes=2):
                    overall_status_text_val += " (Statut Ancien?)"
                    status_text_detail_val = "Dernier statut du worker local reçu il y a > 2 min. " + status_text_detail_val
            except ValueError as e_date_parse:
                app.logger.warning(f"PROXY_STATUS: Error parsing date '{local_data['last_updated_utc']}': {e_date_parse}")

        return jsonify({
            "overall_status_text": overall_status_text_val,
            "status_text": status_text_detail_val,
            "progress_current": local_data.get("progress_current", 0),
            "progress_total": local_data.get("progress_total", 0),
            "current_step_name": current_step_name_val,
            "recent_downloads": local_data.get("recent_downloads", [])
        }), 200

    except requests.exceptions.Timeout:
        app.logger.warning(f"PROXY_STATUS: Timeout connecting to local worker at {target_url}")
        return jsonify({
            "overall_status_text": "Worker Local (Timeout)", "status_text": "La connexion au worker local a expiré.",
            "progress_current": 0, "progress_total": 0, "current_step_name": None, "recent_downloads": []
        }), 504 
    except requests.exceptions.ConnectionError:
        app.logger.warning(f"PROXY_STATUS: Connection error to local worker at {target_url}")
        return jsonify({
            "overall_status_text": "Worker Local (Connexion Refusée)", "status_text": "Impossible de se connecter au worker local.",
            "progress_current": 0, "progress_total": 0, "current_step_name": None, "recent_downloads": []
        }), 502
    except requests.exceptions.HTTPError as e_http: # Catch HTTPError separately for 401 from worker
        app.logger.error(f"PROXY_STATUS: HTTPError from local worker {target_url}: {e_http}")
        if e_http.response.status_code == 401:
            app.logger.error(f"PROXY_STATUS: Received 401 Unauthorized from local worker {target_url}. Check INTERNAL_WORKER_COMMS_TOKEN_ENV consistency.")
            return jsonify({
                "overall_status_text": "Erreur d'Authentification Interne",
                "status_text": "Le serveur distant n'a pas pu s'authentifier auprès du worker local.",
                "progress_current": 0, "progress_total": 0, "current_step_name": None, "recent_downloads": []
            }), 401 # Propagate 401
        # For other HTTP errors from worker
        return jsonify({
            "overall_status_text": f"Worker Local (Erreur {e_http.response.status_code})", "status_text": f"Erreur communication avec worker local.",
            "progress_current": 0, "progress_total": 0, "current_step_name": None, "recent_downloads": []
        }), e_http.response.status_code
    except requests.exceptions.RequestException as e_req: # Other request errors
        app.logger.error(f"PROXY_STATUS: RequestException to local worker {target_url}: {e_req}")
        return jsonify({
            "overall_status_text": "Worker Local (Erreur Réseau)", "status_text": "Erreur de communication réseau avec le worker local.",
            "progress_current": 0, "progress_total": 0, "current_step_name": None, "recent_downloads": []
        }), 503 # Service Unavailable is a reasonable general code here
    except Exception as e_gen:
        app.logger.error(f"PROXY_STATUS: Generic error proxying status from {target_url}: {e_gen}", exc_info=True)
        return jsonify({
            "overall_status_text": "Erreur Serveur Distant (Proxy)", "status_text": "Erreur interne récupération statut local.",
            "progress_current": 0, "progress_total": 0, "current_step_name": None, "recent_downloads": []
        }), 500

@app.route('/api/check_emails_and_download', methods=['POST'])
def api_check_emails_and_download():
    app.logger.info("API_EMAIL_CHECK: Manual trigger for email check received.")
    
    def run_email_check_task_in_thread():
        with app.app_context(): 
            try:
                app.logger.info("API_EMAIL_CHECK_THREAD: Starting email check and Make trigger.")
                webhooks_triggered = check_new_emails_and_trigger_make_webhook()
                app.logger.info(f"API_EMAIL_CHECK_THREAD: Email check finished. {webhooks_triggered} webhook(s) triggered.")
            except Exception as e_thread:
                app.logger.error(f"API_EMAIL_CHECK_THREAD: Error in email check thread: {e_thread}", exc_info=True)

    if not all([ONEDRIVE_CLIENT_ID, ONEDRIVE_CLIENT_SECRET, ONEDRIVE_REFRESH_TOKEN, 
                SENDER_LIST_FOR_POLLING, MAKE_SCENARIO_WEBHOOK_URL, msal_app]):
        msg = "Configuration serveur incomplète pour le traitement des emails."
        app.logger.error(f"API_EMAIL_CHECK: {msg}")
        return jsonify({"status": "error", "message": msg}), 503

    email_thread = threading.Thread(target=run_email_check_task_in_thread, name="ManualEmailCheckThread")
    email_thread.start()
    
    return jsonify({"status": "success", "message": "Vérification des emails et transfert vers OneDrive lancés en arrière-plan."}), 202


# --- Démarrage de l'Application et des Threads ---
if __name__ == '__main__':
    is_debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    should_start_background_threads = not is_debug_mode or os.environ.get("WERKZEUG_RUN_MAIN") == "true"

    if should_start_background_threads:
        app.logger.info("MAIN_APP: Preparing to start background threads (if configured).")
        
        if all([ONEDRIVE_CLIENT_ID, ONEDRIVE_CLIENT_SECRET, ONEDRIVE_REFRESH_TOKEN, msal_app]):
            if SENDER_LIST_FOR_POLLING and MAKE_SCENARIO_WEBHOOK_URL:
                email_poller_service_thread = threading.Thread(target=background_email_poller, name="EmailPollerThread")
                email_poller_service_thread.daemon = True
                email_poller_service_thread.start()
                app.logger.info(f"MAIN_APP: Email polling thread started successfully. Monitoring {len(SENDER_LIST_FOR_POLLING)} senders.")
            else:
                app.logger.warning("MAIN_APP: Email polling thread NOT started. SENDER_LIST_FOR_POLLING or MAKE_SCENARIO_WEBHOOK_URL is not configured.")
        else:
            app.logger.warning("MAIN_APP: Email polling thread NOT started due to missing OneDrive/MSAL configuration (Client ID, Secret, Refresh Token).")
    else:
        app.logger.info("MAIN_APP: Background threads will not be started by this Werkzeug child process (reloader active).")

    server_port = int(os.environ.get('PORT', 10000))
    
    if not EXPECTED_API_TOKEN:
        app.logger.critical("MAIN_APP: SECURITY ALERT - PROCESS_API_TOKEN (EXPECTED_API_TOKEN) IS NOT SET. Endpoints for Make.com are INSECURE.")
    if not REGISTER_LOCAL_URL_TOKEN:
        app.logger.warning("MAIN_APP: SECURITY NOTE - REGISTER_LOCAL_URL_TOKEN IS NOT SET. Endpoint for local worker URL registration is potentially INSECURE if not also disabled on app_new.py.")
    if not REMOTE_UI_ACCESS_TOKEN_ENV:
        app.logger.warning("MAIN_APP: SECURITY NOTE - REMOTE_UI_ACCESS_TOKEN_ENV IS NOT SET. /api/get_local_status is accessible without a token.")
    if not INTERNAL_WORKER_COMMS_TOKEN_ENV:
        app.logger.warning("MAIN_APP: SECURITY NOTE - INTERNAL_WORKER_COMMS_TOKEN_ENV IS NOT SET. Communication between app_render and app_new is unauthenticated.")


    app.logger.info(f"MAIN_APP: Starting Flask development server on host 0.0.0.0, port {server_port}. Debug mode: {is_debug_mode}")
    app.run(host='0.0.0.0', port=server_port, debug=is_debug_mode, use_reloader=(is_debug_mode and os.environ.get("WERKZEUG_RUN_MAIN") != "true"))
