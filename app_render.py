from flask import Flask, jsonify, request, send_from_directory, current_app
import os
import time
from pathlib import Path
import json
import logging
import re
# import html as html_parser # No longer needed if stream_dropbox_to_onedrive is removed
import requests
import threading
from datetime import datetime, timedelta, timezone

try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None

from msal import ConfidentialClientApplication

app = Flask(__name__)

log_level_str = os.environ.get('FLASK_LOG_LEVEL', 'INFO').upper()
log_level = getattr(logging, log_level_str, logging.INFO)
logging.basicConfig(level=log_level,
                    format='%(asctime)s - %(levelname)s - %(name)s - %(module)s - %(funcName)s - %(lineno)d - %(message)s')

POLLING_TIMEZONE_STR = os.environ.get("POLLING_TIMEZONE", "UTC")
POLLING_ACTIVE_START_HOUR = int(os.environ.get("POLLING_ACTIVE_START_HOUR", 0))
POLLING_ACTIVE_END_HOUR = int(os.environ.get("POLLING_ACTIVE_END_HOUR", 24))
POLLING_ACTIVE_DAYS_RAW = os.environ.get("POLLING_ACTIVE_DAYS", "0,1,2,3,4,5,6")
POLLING_ACTIVE_DAYS = []
if POLLING_ACTIVE_DAYS_RAW:
    try: POLLING_ACTIVE_DAYS = [int(d.strip()) for d in POLLING_ACTIVE_DAYS_RAW.split(',') if d.strip().isdigit() and 0<=int(d.strip())<=6]
    except ValueError: app.logger.warning(f"CFG POLL: Invalid POLLING_ACTIVE_DAYS ('{POLLING_ACTIVE_DAYS_RAW}'). Using all days."); POLLING_ACTIVE_DAYS = list(range(7))
if not POLLING_ACTIVE_DAYS: POLLING_ACTIVE_DAYS = list(range(7))

TZ_FOR_POLLING = None
if POLLING_TIMEZONE_STR.upper() != "UTC":
    if ZoneInfo:
        try: TZ_FOR_POLLING = ZoneInfo(POLLING_TIMEZONE_STR); app.logger.info(f"CFG POLL: Using timezone '{POLLING_TIMEZONE_STR}'.")
        except Exception as e: app.logger.warning(f"CFG POLL: Error loading TZ '{POLLING_TIMEZONE_STR}': {e}. Using UTC."); POLLING_TIMEZONE_STR="UTC"
    else: app.logger.warning(f"CFG POLL: 'zoneinfo' not available. Using UTC. '{POLLING_TIMEZONE_STR}' ignored."); POLLING_TIMEZONE_STR="UTC"
if TZ_FOR_POLLING is None: TZ_FOR_POLLING = timezone.utc; app.logger.info(f"CFG POLL: Using timezone 'UTC'.")

EMAIL_POLLING_INTERVAL_SECONDS = int(os.environ.get("EMAIL_POLLING_INTERVAL_SECONDS", 60))
POLLING_INACTIVE_CHECK_INTERVAL_SECONDS = int(os.environ.get("POLLING_INACTIVE_CHECK_INTERVAL_SECONDS", 600))
app.logger.info(f"CFG POLL: Active interval: {EMAIL_POLLING_INTERVAL_SECONDS}s. Inactive check: {POLLING_INACTIVE_CHECK_INTERVAL_SECONDS}s.")
app.logger.info(f"CFG POLL: Active schedule ({POLLING_TIMEZONE_STR}): {POLLING_ACTIVE_START_HOUR:02d}:00-{POLLING_ACTIVE_END_HOUR:02d}:00. Days (0=Mon): {POLLING_ACTIVE_DAYS}")

SIGNAL_DIR = Path(os.environ.get("RENDER_DISC_PATH", "./signal_data_app_render"))
TRIGGER_SIGNAL_FILE = SIGNAL_DIR / "local_workflow_trigger_signal.json"
PROCESSED_URLS_ONEDRIVE_FILENAME = "processed_dropbox_urls_workflow.txt"
PROCESSED_WEBHOOK_TRIGGERS_ONEDRIVE_FILENAME = "processed_webhook_triggers.txt"
SIGNAL_DIR.mkdir(parents=True, exist_ok=True)

ONEDRIVE_CLIENT_ID = os.environ.get('ONEDRIVE_CLIENT_ID')
ONEDRIVE_CLIENT_SECRET = os.environ.get('ONEDRIVE_CLIENT_SECRET')
ONEDRIVE_REFRESH_TOKEN = os.environ.get('ONEDRIVE_REFRESH_TOKEN')
ONEDRIVE_AUTHORITY = "https://login.microsoftonline.com/consumers"
ONEDRIVE_SCOPES_DELEGATED = ["Files.ReadWrite", "User.Read", "Mail.ReadWrite"] # Mail.ReadWrite is for polling
ONEDRIVE_TARGET_PARENT_FOLDER_ID = os.environ.get('ONEDRIVE_TARGET_PARENT_FOLDER_ID', 'root')
ONEDRIVE_TARGET_SUBFOLDER_NAME = os.environ.get('ONEDRIVE_TARGET_SUBFOLDER_NAME', "DropboxDownloadsWorkflow")
MAKE_SCENARIO_WEBHOOK_URL = os.environ.get("MAKE_SCENARIO_WEBHOOK_URL")
SENDER_OF_INTEREST_FOR_POLLING_RAW = os.environ.get("SENDER_OF_INTEREST_FOR_POLLING")
SENDER_LIST_FOR_POLLING = [e.strip().lower() for e in SENDER_OF_INTEREST_FOR_POLLING_RAW.split(',') if e.strip()] if SENDER_OF_INTEREST_FOR_POLLING_RAW else []
if SENDER_LIST_FOR_POLLING: app.logger.info(f"CFG: Polling senders ({len(SENDER_LIST_FOR_POLLING)}): {SENDER_LIST_FOR_POLLING}")
else: app.logger.warning("CFG: SENDER_OF_INTEREST_FOR_POLLING not set (email polling will be ineffective).")

msal_app = None
if ONEDRIVE_CLIENT_ID and ONEDRIVE_CLIENT_SECRET:
    app.logger.info(f"CFG: MSAL init ClientID '{ONEDRIVE_CLIENT_ID[:5]}...', Authority: {ONEDRIVE_AUTHORITY}")
    msal_app = ConfidentialClientApplication(ONEDRIVE_CLIENT_ID, authority=ONEDRIVE_AUTHORITY, client_credential=ONEDRIVE_CLIENT_SECRET)
else: app.logger.warning("CFG: OneDrive Client ID/Secret missing. Graph features (including email polling and URL logging) disabled.")

EXPECTED_API_TOKEN = os.environ.get("PROCESS_API_TOKEN")
if not EXPECTED_API_TOKEN: app.logger.warning("CFG: PROCESS_API_TOKEN not set. API endpoints insecure.")
else: app.logger.info(f"CFG: API Token expected: '{EXPECTED_API_TOKEN[:5]}...'")

# No longer needed for streaming:
# PROCESSING_URLS_LOCK = threading.Lock()
# PROCESSING_URLS = set()
# STREAMING_WORKER_SEMAPHORE = threading.Semaphore(1)

def sanitize_filename(filename_str, max_length=230): # Still used by ensure_onedrive_folder
    if filename_str is None: filename_str = "fichier_nom_absent"
    s = str(filename_str); s = re.sub(r'[<>:"/\\|?*]', '_', s); s = re.sub(r'\s+', '_', s)
    s = re.sub(r'\.+', '.', s).strip('.'); return s[:max_length] if s else "fichier_sans_nom_valide"

def get_onedrive_access_token():
    if not msal_app: app.logger.error("MSAL: Not configured."); return None
    if not ONEDRIVE_REFRESH_TOKEN: app.logger.error("MSAL: Refresh token missing."); return None
    res = msal_app.acquire_token_by_refresh_token(ONEDRIVE_REFRESH_TOKEN, scopes=ONEDRIVE_SCOPES_DELEGATED)
    if "access_token" in res:
        app.logger.info("MSAL: Access token obtained.");
        if res.get("refresh_token") and res.get("refresh_token") != ONEDRIVE_REFRESH_TOKEN:
             app.logger.warning("MSAL: New refresh token issued. Update ONEDRIVE_REFRESH_TOKEN env var.")
        return res['access_token']
    app.logger.error(f"MSAL: Token error: {res.get('error')} - {res.get('error_description')}. Details: {res}"); return None

def ensure_onedrive_folder(access_token, subfolder_name=None, parent_folder_id=None):
    name = subfolder_name or ONEDRIVE_TARGET_SUBFOLDER_NAME; p_id = parent_folder_id or ONEDRIVE_TARGET_PARENT_FOLDER_ID
    h = {'Authorization':f'Bearer {access_token}','Content-Type':'application/json'}
    eff_p_id = p_id if p_id and p_id.lower()!='root' else 'root'; name_clean = sanitize_filename(name,100)
    base = "https://graph.microsoft.com/v1.0/me/drive"; p_path = f"items/{eff_p_id}" if eff_p_id!='root' else "root"
    chk_url = f"{base}/{p_path}/children?$filter=name eq '{name_clean}'"; cre_url = f"{base}/{p_path}/children"
    try:
        r = requests.get(chk_url,headers=h,timeout=15); r.raise_for_status(); children = r.json().get('value',[])
        if children: app.logger.info(f"OD_UTIL: Folder '{name_clean}' found ID: {children[0]['id']}"); return children[0]['id']
        app.logger.info(f"OD_UTIL: Folder '{name_clean}' not found. Creating."); pl = {"name":name_clean,"folder":{},"@microsoft.graph.conflictBehavior":"rename"}
        rc = requests.post(cre_url,headers=h,json=pl,timeout=15); rc.raise_for_status()
        app.logger.info(f"OD_UTIL: Folder '{name_clean}' created ID: {rc.json()['id']}"); return rc.json()['id']
    except requests.exceptions.RequestException as e:
        app.logger.error(f"OD_UTIL: Graph API error for folder '{name_clean}': {e}")
        if hasattr(e,'response') and e.response: app.logger.error(f"OD_UTIL: API Response: {e.response.status_code} - {e.response.text}")
        return None

def get_processed_urls_from_onedrive(job_id, token, folder_id):
    if not token or not folder_id: app.logger.error(f"DEDUP_URLS [{job_id}]: Token/FolderID missing."); return set()
    dl_url = f"https://graph.microsoft.com/v1.0/me/drive/items/{folder_id}:/{PROCESSED_URLS_ONEDRIVE_FILENAME}:/content"
    h = {'Authorization':f'Bearer {token}'}; urls=set()
    app.logger.debug(f"DEDUP_URLS [{job_id}]: Reading {PROCESSED_URLS_ONEDRIVE_FILENAME}.")
    try:
        r = requests.get(dl_url,headers=h,timeout=30)
        if r.status_code == 200: urls.update(l.strip() for l in r.text.splitlines() if l.strip()); app.logger.info(f"DEDUP_URLS [{job_id}]: Read {len(urls)} URLs from {PROCESSED_URLS_ONEDRIVE_FILENAME}.")
        elif r.status_code == 404: app.logger.info(f"DEDUP_URLS [{job_id}]: {PROCESSED_URLS_ONEDRIVE_FILENAME} not found.")
        else: r.raise_for_status()
    except requests.exceptions.RequestException as e: app.logger.error(f"DEDUP_URLS [{job_id}]: Error DLing {PROCESSED_URLS_ONEDRIVE_FILENAME}: {e}")
    return urls

def add_processed_url_to_onedrive(job_id, token, folder_id, url_proc):
    if not all([token,folder_id,url_proc]): app.logger.error(f"DEDUP_URLS [{job_id}]: Missing params to add URL."); return False
    # html_parser.unescape might be useful if URLs can come in escaped form
    # For now, assume url_proc is the canonical form app_new.py used
    # unesc_url = html_parser.unescape(url_proc) # Consider if needed
    
    urls = get_processed_urls_from_onedrive(job_id,token,folder_id)
    if url_proc in urls: # or unesc_url in urls:
        app.logger.info(f"DEDUP_URLS [{job_id}]: URL '{url_proc}' already listed in {PROCESSED_URLS_ONEDRIVE_FILENAME}."); return True
        
    urls.add(url_proc); content = "\n".join(sorted(list(urls)))
    ul_url = f"https://graph.microsoft.com/v1.0/me/drive/items/{folder_id}:/{PROCESSED_URLS_ONEDRIVE_FILENAME}:/content?@microsoft.graph.conflictBehavior=replace"
    h = {'Authorization':f'Bearer {token}','Content-Type':'text/plain; charset=utf-8'}
    app.logger.debug(f"DEDUP_URLS [{job_id}]: Updating {PROCESSED_URLS_ONEDRIVE_FILENAME} with '{url_proc}' ({len(urls)} total URLs).")
    try:
        r = requests.put(ul_url,headers=h,data=content.encode('utf-8'),timeout=60); r.raise_for_status()
        app.logger.info(f"DEDUP_URLS [{job_id}]: {PROCESSED_URLS_ONEDRIVE_FILENAME} updated with '{url_proc}' ({len(urls)} URLs)."); return True
    except requests.exceptions.RequestException as e:
        app.logger.error(f"DEDUP_URLS [{job_id}]: Error ULing {PROCESSED_URLS_ONEDRIVE_FILENAME}: {e}")
        if hasattr(e,'response') and e.response: app.logger.error(f"DEDUP_URLS [{job_id}]: API Resp: {e.response.status_code} - {e.response.text}")
        return False

# --- stream_dropbox_to_onedrive function and its helper _try_cancel_upload_session_streaming REMOVED ---
# --- process_dropbox_link_worker function REMOVED ---


def mark_email_as_read(token, msg_id):
    if not token or not msg_id: app.logger.error("MARK_READ: Token/ID missing."); return False
    url = f"https://graph.microsoft.com/v1.0/me/messages/{msg_id}"; h={'Authorization':f'Bearer {token}','Content-Type':'application/json'}; p={"isRead":True}
    try: r=requests.patch(url,headers=h,json=p,timeout=15); r.raise_for_status(); app.logger.info(f"MARK_READ: Email {msg_id} marked read."); return True
    except requests.exceptions.RequestException as e: app.logger.error(f"MARK_READ: API error for {msg_id}: {e}"); return False

def get_processed_webhook_trigger_ids(token, folder_id):
    # This job_id is just for logging within this function scope
    job_id = f"WH_DEDUP_GET_{time.time_ns()}"[-15:]
    if not token or not folder_id: app.logger.error(f"DEDUP_WH [{job_id}]: Token/FolderID missing."); return set()
    url=f"https://graph.microsoft.com/v1.0/me/drive/items/{folder_id}:/{PROCESSED_WEBHOOK_TRIGGERS_ONEDRIVE_FILENAME}:/content"
    h={'Authorization':f'Bearer {token}'}; ids=set()
    app.logger.debug(f"DEDUP_WH [{job_id}]: Reading {PROCESSED_WEBHOOK_TRIGGERS_ONEDRIVE_FILENAME}")
    try:
        r=requests.get(url,headers=h,timeout=30)
        if r.status_code==200: ids.update(l.strip() for l in r.text.splitlines() if l.strip()); app.logger.info(f"DEDUP_WH [{job_id}]: Read {len(ids)} IDs from {PROCESSED_WEBHOOK_TRIGGERS_ONEDRIVE_FILENAME}.")
        elif r.status_code==404: app.logger.info(f"DEDUP_WH [{job_id}]: {PROCESSED_WEBHOOK_TRIGGERS_ONEDRIVE_FILENAME} not found.")
        else: r.raise_for_status()
    except requests.exceptions.RequestException as e: app.logger.error(f"DEDUP_WH [{job_id}]: DL error for {PROCESSED_WEBHOOK_TRIGGERS_ONEDRIVE_FILENAME}: {e}")
    return ids

def add_processed_webhook_trigger_id(token, folder_id, email_id):
    job_id = f"WH_DEDUP_ADD_{time.time_ns()}"[-15:]
    if not all([token,folder_id,email_id]): app.logger.error(f"DEDUP_WH [{job_id}]: Missing params to add email_id."); return False
    ids=get_processed_webhook_trigger_ids(token,folder_id) # Pass token & folder_id
    if email_id in ids:
        app.logger.info(f"DEDUP_WH [{job_id}]: Email ID '{email_id}' already in {PROCESSED_WEBHOOK_TRIGGERS_ONEDRIVE_FILENAME}."); return True

    ids.add(email_id); content="\n".join(sorted(list(ids)))
    url=f"https://graph.microsoft.com/v1.0/me/drive/items/{folder_id}:/{PROCESSED_WEBHOOK_TRIGGERS_ONEDRIVE_FILENAME}:/content?@microsoft.graph.conflictBehavior=replace"
    h={'Authorization':f'Bearer {token}','Content-Type':'text/plain; charset=utf-8'}
    app.logger.debug(f"DEDUP_WH [{job_id}]: Updating {PROCESSED_WEBHOOK_TRIGGERS_ONEDRIVE_FILENAME} with '{email_id}' ({len(ids)} total IDs).")
    try: r=requests.put(url,headers=h,data=content.encode('utf-8'),timeout=60); r.raise_for_status(); app.logger.info(f"DEDUP_WH [{job_id}]: {PROCESSED_WEBHOOK_TRIGGERS_ONEDRIVE_FILENAME} updated ({len(ids)} IDs)."); return True
    except requests.exceptions.RequestException as e: app.logger.error(f"DEDUP_WH [{job_id}]: UL error for {PROCESSED_WEBHOOK_TRIGGERS_ONEDRIVE_FILENAME}: {e}"); return False

def check_new_emails_and_trigger_make_webhook():
    app.logger.info("POLLER: Checking new emails...")
    if not SENDER_LIST_FOR_POLLING: app.logger.warning("POLLER: SENDER_LIST_FOR_POLLING is empty. Email polling ineffective."); return 0
    if not MAKE_SCENARIO_WEBHOOK_URL: app.logger.error("POLLER: MAKE_SCENARIO_WEBHOOK_URL not configured. Cannot trigger Make."); return 0
    
    token=get_onedrive_access_token()
    if not token: app.logger.error("POLLER: Failed to get Graph token for email polling."); return 0
    
    folder_id=ensure_onedrive_folder(token) # For webhook trigger deduplication file
    if not folder_id: app.logger.error("POLLER: Failed to ensure OneDrive folder for webhook deduplication. Cannot proceed with polling."); return 0
    
    processed_email_ids=get_processed_webhook_trigger_ids(token,folder_id)
    triggered_count=0
    
    try:
        # Check emails from the last 2 days to be safe with timezones and processing delays
        since_datetime=(datetime.now(timezone.utc)-timedelta(days=2)).strftime('%Y-%m-%dT%H:%M:%SZ')
        # Filter for unread emails from specific senders received since the 'since_datetime'
        sender_filters = " or ".join([f"from/emailAddress/address eq '{sender}'" for sender in SENDER_LIST_FOR_POLLING])
        filter_query=f"isRead eq false and receivedDateTime ge {since_datetime} and ({sender_filters})"
        
        # Max 25 emails per poll to avoid long processing, order by receivedDateTime ascending to process older first
        url=f"https://graph.microsoft.com/v1.0/me/mailFolders/inbox/messages?$filter={filter_query}&$select=id,subject,from,receivedDateTime,bodyPreview&$top=25&$orderby=receivedDateTime asc"
        
        app.logger.info(f"POLLER: Calling Graph Mail API (filter: '{filter_query}').")
        h_mail={'Authorization':f'Bearer {token}','Prefer':'outlook.body-content-type="text"'} # Get body as text
        r=requests.get(url,headers=h_mail,timeout=45); r.raise_for_status()
        emails=r.json().get('value',[])
        
        app.logger.info(f"POLLER: {len(emails)} unread email(s) fetched matching criteria.")
        
        for mail in emails: # Already ordered by receivedDateTime asc, so no need to reverse
            mail_id=mail['id']; mail_subject=mail.get('subject','N/A_SUBJECT')
            sender_info = mail.get('from',{}).get('emailAddress',{}).get('address','N/A_SENDER').lower()

            if mail_id in processed_email_ids:
                app.logger.debug(f"POLLER: Email ID {mail_id} already processed for webhook trigger. Skipping."); continue
            
            app.logger.info(f"POLLER: New relevant email found (ID:{mail_id}, Subject:'{str(mail_subject)[:50]}...'). Triggering Make webhook.")
            
            # Payload for Make.com webhook
            payload_to_make={
                "microsoft_graph_email_id": mail_id,
                "subject": mail_subject,
                "receivedDateTime": mail.get("receivedDateTime"),
                "sender_address": sender_info,
                "bodyPreview": mail.get('bodyPreview','') # Make.com will extract Dropbox URL
            }
            
            try:
                wh_r=requests.post(MAKE_SCENARIO_WEBHOOK_URL,json=payload_to_make,timeout=30)
                # Expecting 200 OK with "Accepted" from Make.com
                if wh_r.status_code==200 and "accepted" in wh_r.text.lower():
                    app.logger.info(f"POLLER: Make webhook call successful for email {mail_id}. Resp: {wh_r.status_code} - {wh_r.text}")
                    # Add to processed webhook triggers and mark as read
                    if add_processed_webhook_trigger_id(token,folder_id,mail_id):
                        triggered_count+=1
                        if not mark_email_as_read(token,mail_id):
                             app.logger.warning(f"POLLER: Failed to mark email {mail_id} as read, but webhook was OK.")
                    else:
                        app.logger.error(f"POLLER: CRITICAL - Failed to add email {mail_id} to {PROCESSED_WEBHOOK_TRIGGERS_ONEDRIVE_FILENAME}. Email NOT marked read to allow reprocessing.")
                else:
                    app.logger.error(f"POLLER: Make webhook call failed for email {mail_id}. Status: {wh_r.status_code}, Resp: {wh_r.text[:200]}")
            except requests.exceptions.RequestException as e:
                app.logger.error(f"POLLER: Make webhook call exception for email {mail_id}: {e}")
        
        return triggered_count
        
    except requests.exceptions.RequestException as e:
        app.logger.error(f"POLLER: Graph Mail API error during email check: {e}")
        if hasattr(e,'response') and e.response: app.logger.error(f"POLLER: API Response: {e.response.status_code} - {e.response.text}")
        return 0
    except Exception as e:
        app.logger.error(f"POLLER: Unexpected error during email check: {e}",exc_info=True)
        return 0

def background_email_poller():
    app.logger.info(f"BG_POLLER: Starting email polling thread (TZ: {POLLING_TIMEZONE_STR}).")
    err_count=0; MAX_ERR=5
    while True:
        try:
            now_local_tz=datetime.now(TZ_FOR_POLLING)
            current_hour=now_local_tz.hour
            current_weekday=now_local_tz.weekday() # Monday is 0 and Sunday is 6
            
            is_active_day = current_weekday in POLLING_ACTIVE_DAYS
            is_active_time = POLLING_ACTIVE_START_HOUR <= current_hour < POLLING_ACTIVE_END_HOUR
            
            log_details = f"Day:{current_weekday}[Allowed:{POLLING_ACTIVE_DAYS}], Hour:{current_hour:02d}h [{POLLING_ACTIVE_START_HOUR:02d}h-{POLLING_ACTIVE_END_HOUR:02d}h {POLLING_TIMEZONE_STR}]"

            if is_active_day and is_active_time:
                app.logger.info(f"BG_POLLER: In active period ({log_details}). Starting poll cycle.")
                # Check for essential configurations for polling
                if not all([ONEDRIVE_CLIENT_ID, ONEDRIVE_CLIENT_SECRET, ONEDRIVE_REFRESH_TOKEN, SENDER_LIST_FOR_POLLING, MAKE_SCENARIO_WEBHOOK_URL]):
                    app.logger.warning("BG_POLLER: Incomplete configuration for email polling. Waiting 60s and will re-check config.")
                    time.sleep(60)
                    continue 
                
                webhooks_triggered_count = check_new_emails_and_trigger_make_webhook()
                app.logger.info(f"BG_POLLER: Active poll cycle finished. {webhooks_triggered_count} Make webhook(s) triggered.")
                err_count=0 # Reset error count on successful cycle
                current_sleep_interval = EMAIL_POLLING_INTERVAL_SECONDS
            else:
                app.logger.info(f"BG_POLLER: Outside active period ({log_details}). Sleeping until next check for active window.")
                current_sleep_interval = POLLING_INACTIVE_CHECK_INTERVAL_SECONDS
            
            app.logger.debug(f"BG_POLLER: Sleeping for {current_sleep_interval} seconds.")
            time.sleep(current_sleep_interval)

        except Exception as e:
            err_count+=1
            app.logger.error(f"BG_POLLER: Major unhandled error in polling loop (Attempt #{err_count}): {e}",exc_info=True)
            if err_count>=MAX_ERR:
                app.logger.critical(f"BG_POLLER: Too many consecutive errors ({MAX_ERR}). Stopping email polling thread.")
                break 
            # Exponential backoff for retries after errors
            sleep_on_error = max(60, EMAIL_POLLING_INTERVAL_SECONDS) * (2**err_count)
            app.logger.info(f"BG_POLLER: Sleeping for {sleep_on_error}s due to error.")
            time.sleep(sleep_on_error)

@app.route('/api/log_processed_url', methods=['POST'])
def api_log_processed_url():
    # This endpoint is called by app_new.py (local worker) after it successfully downloads a file
    # to log the Dropbox URL as processed in the OneDrive file.
    
    api_token = request.headers.get('X-API-Token')
    if not EXPECTED_API_TOKEN:
        app.logger.error("API_LOG_URL: PROCESS_API_TOKEN not configured on Render. Cannot authenticate request.")
        return jsonify({"status": "error", "message": "Server configuration error: API token not set."}), 500
    if api_token != EXPECTED_API_TOKEN:
        app.logger.warning(f"API_LOG_URL: Unauthorized access attempt. Token: '{str(api_token)[:20]}...'")
        return jsonify({"status": "error", "message": "Unauthorized."}), 401
    
    app.logger.info("API_LOG_URL: API token validated.")
    
    try:
        data = request.get_json(silent=True) or (json.loads(request.data.decode('utf-8')) if request.data else None)
    except Exception as e:
        app.logger.error(f"API_LOG_URL: JSON parsing error: {e}", exc_info=True)
        return jsonify({"status": "error", "message": f"Invalid JSON payload: {e}"}), 400

    if not data or 'dropbox_url' not in data:
        app.logger.error(f"API_LOG_URL: 'dropbox_url' missing in payload. Data: {data}")
        return jsonify({"status": "error", "message": "'dropbox_url' is required."}), 400
        
    dropbox_url_to_log = data.get('dropbox_url')
    email_subject_for_log = data.get('email_subject', 'N/A_Subject_From_Local') # Optional
    email_id_for_log = data.get('microsoft_graph_email_id', 'N/A_EmailID_From_Local') # Optional
    job_id = f"LOGURL_{email_id_for_log[-10:]}_{time.time_ns() % 100000}"


    if not isinstance(dropbox_url_to_log, str) or not dropbox_url_to_log.lower().startswith("https://www.dropbox.com/"):
        app.logger.error(f"API_LOG_URL [{job_id}]: Invalid Dropbox URL provided: '{dropbox_url_to_log}'")
        return jsonify({"status": "error", "message": "Invalid Dropbox URL format."}), 400

    app.logger.info(f"API_LOG_URL [{job_id}]: Request to log URL: '{dropbox_url_to_log}', Subject: '{email_subject_for_log}', EmailID: '{email_id_for_log}'")

    token = get_onedrive_access_token()
    if not token:
        app.logger.error(f"API_LOG_URL [{job_id}]: Failed to get OneDrive token. Cannot log URL.")
        return jsonify({"status": "error", "message": "Failed to obtain OneDrive token."}), 500
    
    folder_id = ensure_onedrive_folder(token)
    if not folder_id:
        app.logger.error(f"API_LOG_URL [{job_id}]: Failed to ensure OneDrive folder. Cannot log URL.")
        return jsonify({"status": "error", "message": "Failed to access OneDrive target folder."}), 500
        
    if add_processed_url_to_onedrive(job_id, token, folder_id, dropbox_url_to_log):
        app.logger.info(f"API_LOG_URL [{job_id}]: Successfully logged URL '{dropbox_url_to_log}' to {PROCESSED_URLS_ONEDRIVE_FILENAME}.")
        return jsonify({"status": "success", "message": f"URL '{dropbox_url_to_log}' logged as processed."}), 200
    else:
        app.logger.error(f"API_LOG_URL [{job_id}]: Failed to log URL '{dropbox_url_to_log}' to {PROCESSED_URLS_ONEDRIVE_FILENAME}.")
        return jsonify({"status": "error", "message": f"Failed to update persistent log for URL '{dropbox_url_to_log}'."}), 500

@app.route('/api/trigger_local_workflow', methods=['POST'])
def trigger_local_workflow():
    # This endpoint is called by trigger_page.html (served by '/')
    # It writes a signal file that app_new.py (local worker) can poll via /api/check_trigger
    payload = request.json
    if not payload:
        payload = {"command": "start_manual_generic", "timestamp": time.time()}
    else:
        payload.setdefault("timestamp", time.time())

    try:
        with open(TRIGGER_SIGNAL_FILE, "w") as f:
            json.dump(payload, f)
        app.logger.info(f"LOCAL_TRIGGER_API: Signal file '{TRIGGER_SIGNAL_FILE}' created/updated. Payload: {payload}")
        return jsonify({"status": "ok", "message": "Local workflow signal set."}), 200
    except Exception as e:
        app.logger.error(f"LOCAL_TRIGGER_API: Error writing signal file '{TRIGGER_SIGNAL_FILE}': {e}", exc_info=True)
        return jsonify({"status": "error", "message": "Internal server error setting signal."}), 500

@app.route('/api/check_trigger', methods=['GET'])
def check_local_workflow_trigger():
    # This endpoint is polled by app_new.py (local worker) to see if trigger_page.html initiated a manual command
    response_data = {'command_pending': False, 'payload': None}
    if TRIGGER_SIGNAL_FILE.exists():
        try:
            with open(TRIGGER_SIGNAL_FILE, 'r') as f:
                payload = json.load(f)
            response_data['command_pending'] = True
            response_data['payload'] = payload
            TRIGGER_SIGNAL_FILE.unlink() # Consume the signal
            app.logger.info(f"LOCAL_CHECK_API: Signal read from '{TRIGGER_SIGNAL_FILE}' and file deleted. Payload: {payload}")
        except Exception as e:
            app.logger.error(f"LOCAL_CHECK_API: Error processing signal file '{TRIGGER_SIGNAL_FILE}': {e}", exc_info=True)
            # Potentially leave the file if unreadable, or delete if corrupt to prevent loop
            # For now, just log and return no command pending
    return jsonify(response_data)

@app.route('/api/ping', methods=['GET','HEAD'])
def api_ping():
    ip=request.headers.get('X-Forwarded-For',request.remote_addr); ua=request.headers.get('User-Agent','N/A')
    app.logger.info(f"PING_API: Keep-alive /api/ping from IP:{ip}, UA:{ua} at {datetime.now(timezone.utc).isoformat()}")
    r=jsonify({"s":"pong","ts":time.time()}); r.headers["Cache-Control"]="no-cache,no-store,must-revalidate"; r.headers["Pragma"]="no-cache"; r.headers["Expires"]="0"
    return r,200

@app.route('/')
def serve_trigger_page_main():
    app.logger.info("ROOT: '/' called. Attempting to serve 'trigger_page.html'.")
    try: return send_from_directory(app.root_path,'trigger_page.html')
    except FileNotFoundError: app.logger.error(f"ROOT: ERROR: trigger_page.html not found in {app.root_path}."); return "Error: Main page not found.",404
    except Exception as e: app.logger.error(f"ROOT: Error in send_from_directory: {e}",exc_info=True); return "Internal server error (UI).",500

if __name__ == '__main__':
    debug_mode = os.environ.get('FLASK_DEBUG','False').lower()=='true'
    # In Flask debug mode with reloader, this block runs twice.
    # WERKZEUG_RUN_MAIN ensures threads only start in the main Werkzeug process.
    start_background_threads = not debug_mode or os.environ.get("WERKZEUG_RUN_MAIN") == "true"

    if start_background_threads:
        app.logger.info("MAIN: Preparing to start background threads (if configured).")
        # Check if all necessary environment variables for email polling are set
        if all([ONEDRIVE_CLIENT_ID, ONEDRIVE_CLIENT_SECRET, ONEDRIVE_REFRESH_TOKEN, SENDER_LIST_FOR_POLLING, MAKE_SCENARIO_WEBHOOK_URL]):
            email_poller_thread = threading.Thread(target=background_email_poller, name="EmailPollerThread")
            email_poller_thread.daemon = True # Allows main program to exit even if thread is running
            email_poller_thread.start()
            app.logger.info(f"MAIN: Email polling thread started. Senders: {len(SENDER_LIST_FOR_POLLING)}, TZ: {POLLING_TIMEZONE_STR}, Webhook: {'Configured' if MAKE_SCENARIO_WEBHOOK_URL else 'NOT CONFIGURED'}.")
        else:
            app.logger.warning("MAIN: Email polling thread NOT started due to incomplete configuration (OneDrive credentials, Senders, or Make Webhook URL missing).")
    else:
        app.logger.info("MAIN: Background threads will not be started by this process (likely a Werkzeug child reloader process).")

    port = int(os.environ.get('PORT', 10000))
    if not EXPECTED_API_TOKEN:
        app.logger.critical("MAIN: SECURITY ALERT: PROCESS_API_TOKEN IS NOT SET. API ENDPOINTS ARE INSECURE.")
    
    app.logger.info(f"MAIN: Starting Flask server on host 0.0.0.0, port {port}, debug={debug_mode}")
    # use_reloader should be False if WERKZEUG_RUN_MAIN is true, to avoid double reload issue with threads.
    # However, typical Flask debug mode handles this. If using an external manager like gunicorn, it handles workers.
    app.run(host='0.0.0.0', port=port, debug=debug_mode, use_reloader=(debug_mode and os.environ.get("WERKZEUG_RUN_MAIN") != "true"))
