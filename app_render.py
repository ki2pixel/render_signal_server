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

# Attempt to import redis, will be checked before use
try:
    import redis

    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

from msal import ConfidentialClientApplication

app = Flask(__name__)
auth = HTTPBasicAuth()

# --- Tokens and Config de référence ---
REF_TRIGGER_PAGE_USER = "admin"
REF_TRIGGER_PAGE_PASSWORD = "UDPVA#esKf40r@"
REF_REMOTE_UI_ACCESS_TOKEN = "0wbgXHiF3e!MqE"
REF_INTERNAL_WORKER_COMMS_TOKEN = "Fn*G14Vb'!Hkra7"
REF_PROCESS_API_TOKEN = "rnd_PW5cGYVf4g131imu9cYkFw27u8dY"
REF_REGISTER_LOCAL_URL_TOKEN = "WMmWti@^n6RaUA"
REF_ONEDRIVE_CLIENT_ID = "6bbc767d-53e8-4b82-bd49-480d4c157a9b"
REF_ONEDRIVE_CLIENT_SECRET = "3Ah8Q~M7wk954ttbQRkt-xHn80enAeHd5wHG1XoEu"
REF_ONEDRIVE_TENANT_ID = "60fb2b89-e5bf-4232-98f6-f1ecb90660c5"
REF_MAKE_SCENARIO_WEBHOOK_URL = (
    "https://hook.eu2.make.com/wjcp43km1bgginyr1xu1pwui95ekr7gi"
)
REF_SENDER_OF_INTEREST_FOR_POLLING = "achats@media-solution.fr,camille.moine.pro@gmail.com,a.peault@media-solution.fr,v.lorent@media-solution.fr,technique@media-solution.fr,t.deslus@media-solution.fr"
REF_POLLING_TIMEZONE = "Europe/Paris"
REF_POLLING_ACTIVE_START_HOUR = 9
REF_POLLING_ACTIVE_END_HOUR = 23
REF_POLLING_ACTIVE_DAYS = "0,1,2,3,4"
REF_EMAIL_POLLING_INTERVAL_SECONDS = 30
# ------------------------------------------------------------------------------------

# --- Configuration du Logging ---
log_level_str = os.environ.get("FLASK_LOG_LEVEL", "INFO").upper()
log_level = getattr(logging, log_level_str, logging.INFO)
logging.basicConfig(
    level=log_level,
    format="%(asctime)s - %(levelname)s - %(name)s - %(module)s - %(funcName)s - %(lineno)d - %(message)s",
)

# --- Configuration des Identifiants pour la page de trigger ---
TRIGGER_PAGE_USER_ENV = os.environ.get("TRIGGER_PAGE_USER", REF_TRIGGER_PAGE_USER)
TRIGGER_PAGE_PASSWORD_ENV = os.environ.get(
    "TRIGGER_PAGE_PASSWORD", REF_TRIGGER_PAGE_PASSWORD
)
users = {}
if TRIGGER_PAGE_USER_ENV and TRIGGER_PAGE_PASSWORD_ENV:
    users[TRIGGER_PAGE_USER_ENV] = TRIGGER_PAGE_PASSWORD_ENV
    app.logger.info(
        f"CFG AUTH: Trigger page user '{TRIGGER_PAGE_USER_ENV}' configured."
    )
else:
    app.logger.warning(
        "CFG AUTH: TRIGGER_PAGE_USER or TRIGGER_PAGE_PASSWORD not set. HTTP Basic Auth for trigger page will NOT be actively enforced."
    )


@auth.verify_password
def verify_password(username, password):
    if not users:
        app.logger.debug("AUTH: No users configured, access granted by default.")
        return "anonymous_or_no_auth_user"
    user_stored_password = users.get(username)
    if user_stored_password and user_stored_password == password:
        app.logger.info(f"AUTH: User '{username}' authenticated successfully.")
        return username
    app.logger.warning(f"AUTH: Authentication failed for user '{username}'.")
    return None


# --- Configuration du Polling des Emails ---
POLLING_TIMEZONE_STR = os.environ.get("POLLING_TIMEZONE", REF_POLLING_TIMEZONE)
POLLING_ACTIVE_START_HOUR = int(
    os.environ.get("POLLING_ACTIVE_START_HOUR", REF_POLLING_ACTIVE_START_HOUR)
)
POLLING_ACTIVE_END_HOUR = int(
    os.environ.get("POLLING_ACTIVE_END_HOUR", REF_POLLING_ACTIVE_END_HOUR)
)
POLLING_ACTIVE_DAYS_RAW = os.environ.get("POLLING_ACTIVE_DAYS", REF_POLLING_ACTIVE_DAYS)
POLLING_ACTIVE_DAYS = []
if POLLING_ACTIVE_DAYS_RAW:
    try:
        POLLING_ACTIVE_DAYS = [
            int(d.strip())
            for d in POLLING_ACTIVE_DAYS_RAW.split(",")
            if d.strip().isdigit() and 0 <= int(d.strip()) <= 6
        ]
    except ValueError:
        app.logger.warning(
            f"CFG POLL: Invalid POLLING_ACTIVE_DAYS. Using default Mon-Fri."
        )
        POLLING_ACTIVE_DAYS = [0, 1, 2, 3, 4]
if not POLLING_ACTIVE_DAYS:
    POLLING_ACTIVE_DAYS = [0, 1, 2, 3, 4]
TZ_FOR_POLLING = None
if POLLING_TIMEZONE_STR.upper() != "UTC":
    if ZoneInfo:
        try:
            TZ_FOR_POLLING = ZoneInfo(POLLING_TIMEZONE_STR)
        except Exception as e:
            app.logger.warning(
                f"CFG POLL: Error loading TZ '{POLLING_TIMEZONE_STR}': {e}. Using UTC."
            )
            POLLING_TIMEZONE_STR = "UTC"
    else:
        app.logger.warning(
            f"CFG POLL: 'zoneinfo' not available. Using UTC. '{POLLING_TIMEZONE_STR}' ignored."
        )
        POLLING_TIMEZONE_STR = "UTC"
if TZ_FOR_POLLING is None:
    TZ_FOR_POLLING = timezone.utc
app.logger.info(
    f"CFG POLL: Timezone for polling: {POLLING_TIMEZONE_STR}. Active: {POLLING_ACTIVE_START_HOUR:02d}-{POLLING_ACTIVE_END_HOUR:02d}, Days: {POLLING_ACTIVE_DAYS}"
)
EMAIL_POLLING_INTERVAL_SECONDS = int(
    os.environ.get("EMAIL_POLLING_INTERVAL_SECONDS", REF_EMAIL_POLLING_INTERVAL_SECONDS)
)
POLLING_INACTIVE_CHECK_INTERVAL_SECONDS = int(
    os.environ.get("POLLING_INACTIVE_CHECK_INTERVAL_SECONDS", 600)
)
app.logger.info(
    f"CFG POLL: Active interval: {EMAIL_POLLING_INTERVAL_SECONDS}s. Inactive check: {POLLING_INACTIVE_CHECK_INTERVAL_SECONDS}s."
)

# --- Chemins et Fichiers ---
SIGNAL_DIR = Path(os.environ.get("RENDER_DISC_PATH", "./signal_data_app_render"))
TRIGGER_SIGNAL_FILE = SIGNAL_DIR / "local_workflow_trigger_signal.json"
PROCESSED_URLS_ONEDRIVE_FILENAME = "processed_dropbox_urls_workflow.txt"
PROCESSED_WEBHOOK_TRIGGERS_ONEDRIVE_FILENAME = "processed_webhook_triggers.txt"
LOCALTUNNEL_URL_FILE = SIGNAL_DIR / "current_localtunnel_url.txt"  # Fallback file
SIGNAL_DIR.mkdir(parents=True, exist_ok=True)
app.logger.info(
    f"CFG PATH: Signal directory for ephemeral files (if Redis fails/unavailable): {SIGNAL_DIR.resolve()}"
)


# --- Configuration Redis ---
REDIS_URL = os.environ.get("REDIS_URL")
redis_client = None
LOCALTUNNEL_URL_REDIS_KEY = (
    "current_localtunnel_url_v1"  # Added _v1 for potential future changes
)

if REDIS_AVAILABLE and REDIS_URL:
    try:
        redis_client = redis.from_url(
            REDIS_URL, socket_connect_timeout=5, socket_timeout=5
        )  # Added timeouts
        redis_client.ping()
        app.logger.info(
            f"CFG REDIS: Successfully connected to Redis at {REDIS_URL.split('@')[-1] if '@' in REDIS_URL else REDIS_URL}."
        )
    except redis.exceptions.ConnectionError as e_redis:
        app.logger.error(
            f"CFG REDIS: Could not connect to Redis at {REDIS_URL.split('@')[-1] if '@' in REDIS_URL else REDIS_URL}. Error: {e_redis}. Will use file fallback for Localtunnel URL."
        )
        redis_client = None
    except Exception as e_redis_other:  # Catch other potential redis client errors
        app.logger.error(
            f"CFG REDIS: An unexpected error occurred during Redis initialization: {e_redis_other}. Will use file fallback."
        )
        redis_client = None
elif REDIS_AVAILABLE and not REDIS_URL:
    app.logger.warning(
        "CFG REDIS: REDIS_URL not set. Redis client library is available, but Redis will not be used. Using file fallback for Localtunnel URL."
    )
    redis_client = None  # Explicitly set to None
else:  # REDIS_AVAILABLE is False
    app.logger.warning(
        "CFG REDIS: 'redis' Python library not installed. Redis will not be used. Using file fallback for Localtunnel URL."
    )
    redis_client = None  # Explicitly set to None


# --- Configuration OneDrive / MSAL ---
ONEDRIVE_CLIENT_ID = os.environ.get("ONEDRIVE_CLIENT_ID", REF_ONEDRIVE_CLIENT_ID)
ONEDRIVE_CLIENT_SECRET = os.environ.get(
    "ONEDRIVE_CLIENT_SECRET", REF_ONEDRIVE_CLIENT_SECRET
)
ONEDRIVE_REFRESH_TOKEN = os.environ.get("ONEDRIVE_REFRESH_TOKEN")
ONEDRIVE_TENANT_ID = os.environ.get("ONEDRIVE_TENANT_ID", REF_ONEDRIVE_TENANT_ID)
ONEDRIVE_AUTHORITY = (
    f"https://login.microsoftonline.com/{ONEDRIVE_TENANT_ID}"
    if ONEDRIVE_TENANT_ID != "consumers"
    else "https://login.microsoftonline.com/consumers"
)
ONEDRIVE_SCOPES_DELEGATED = ["Files.ReadWrite", "User.Read", "Mail.ReadWrite"]
ONEDRIVE_TARGET_PARENT_FOLDER_ID = os.environ.get(
    "ONEDRIVE_TARGET_PARENT_FOLDER_ID", "root"
)
ONEDRIVE_TARGET_SUBFOLDER_NAME = os.environ.get(
    "ONEDRIVE_TARGET_SUBFOLDER_NAME", "DropboxDownloadsWorkflow"
)
msal_app = None
if ONEDRIVE_CLIENT_ID and ONEDRIVE_CLIENT_SECRET:
    app.logger.info(
        f"CFG MSAL: Initializing MSAL. ClientID: '{ONEDRIVE_CLIENT_ID[:5]}...', Authority: {ONEDRIVE_AUTHORITY}"
    )
    msal_app = ConfidentialClientApplication(
        ONEDRIVE_CLIENT_ID,
        authority=ONEDRIVE_AUTHORITY,
        client_credential=ONEDRIVE_CLIENT_SECRET,
    )
else:
    app.logger.warning(
        "CFG MSAL: OneDrive Client ID/Secret missing. OneDrive & Email Polling disabled."
    )

# --- Configuration des Webhooks et Tokens ---
MAKE_SCENARIO_WEBHOOK_URL = os.environ.get(
    "MAKE_SCENARIO_WEBHOOK_URL", REF_MAKE_SCENARIO_WEBHOOK_URL
)
SENDER_OF_INTEREST_FOR_POLLING_RAW = os.environ.get(
    "SENDER_OF_INTEREST_FOR_POLLING", REF_SENDER_OF_INTEREST_FOR_POLLING
)
SENDER_LIST_FOR_POLLING = (
    [
        e.strip().lower()
        for e in SENDER_OF_INTEREST_FOR_POLLING_RAW.split(",")
        if e.strip()
    ]
    if SENDER_OF_INTEREST_FOR_POLLING_RAW
    else []
)
if SENDER_LIST_FOR_POLLING:
    app.logger.info(f"CFG POLL: Monitoring emails from: {SENDER_LIST_FOR_POLLING}")
else:
    app.logger.warning(
        "CFG POLL: SENDER_OF_INTEREST_FOR_POLLING not set. Email polling likely ineffective."
    )
EXPECTED_API_TOKEN = os.environ.get("PROCESS_API_TOKEN", REF_PROCESS_API_TOKEN)
if not EXPECTED_API_TOKEN:
    app.logger.warning(
        "CFG TOKEN: PROCESS_API_TOKEN not set. Make.com API endpoints insecure."
    )
else:
    app.logger.info(
        f"CFG TOKEN: PROCESS_API_TOKEN configured: '{EXPECTED_API_TOKEN[:5]}...'"
    )
REGISTER_LOCAL_URL_TOKEN = os.environ.get(
    "REGISTER_LOCAL_URL_TOKEN", REF_REGISTER_LOCAL_URL_TOKEN
)
if not REGISTER_LOCAL_URL_TOKEN:
    app.logger.warning(
        "CFG TOKEN: REGISTER_LOCAL_URL_TOKEN not set. Local worker registration insecure."
    )
else:
    app.logger.info(
        f"CFG TOKEN: REGISTER_LOCAL_URL_TOKEN configured: '{REGISTER_LOCAL_URL_TOKEN[:5]}...'"
    )
REMOTE_UI_ACCESS_TOKEN_ENV = os.environ.get(
    "REMOTE_UI_ACCESS_TOKEN", REF_REMOTE_UI_ACCESS_TOKEN
)
INTERNAL_WORKER_COMMS_TOKEN_ENV = os.environ.get(
    "INTERNAL_WORKER_COMMS_TOKEN", REF_INTERNAL_WORKER_COMMS_TOKEN
)

# --- Fonctions Utilitaires OneDrive & MSAL ---
def sanitize_filename(filename_str, max_length=230):
    if filename_str is None:
        filename_str = "fichier_nom_absent"
    s = str(filename_str)
    s = re.sub(r'[<>:"/\\|?*]', "_", s)
    s = re.sub(r"\s+", "_", s)
    s = re.sub(r"\.+", ".", s).strip(".")
    return s[:max_length] if s else "fichier_sans_nom_valide"


def get_onedrive_access_token():
    if not msal_app:
        app.logger.error("MSAL: MSAL app not configured.")
        return None
    if not ONEDRIVE_REFRESH_TOKEN:
        app.logger.error(
            "MSAL: OneDrive refresh token missing (ONEDRIVE_REFRESH_TOKEN env var)."
        )
        return None
    token_result = msal_app.acquire_token_by_refresh_token(
        ONEDRIVE_REFRESH_TOKEN, scopes=ONEDRIVE_SCOPES_DELEGATED
    )
    if "access_token" in token_result:
        app.logger.info("MSAL: Access token obtained.")
        if (
            token_result.get("refresh_token")
            and token_result.get("refresh_token") != ONEDRIVE_REFRESH_TOKEN
        ):
            app.logger.warning(
                "MSAL: New refresh token issued. IMPORTANT: Update ONEDRIVE_REFRESH_TOKEN env var: "
                f"'{token_result.get('refresh_token')}'"
            )
        return token_result["access_token"]
    else:
        app.logger.error(
            f"MSAL: Failed to obtain access token. Error: {token_result.get('error')}, "
            f"Desc: {token_result.get('error_description')}. Details: {token_result}"
        )
        return None


def ensure_onedrive_folder(access_token, subfolder_name=None, parent_folder_id=None):
    target_folder_name = subfolder_name or ONEDRIVE_TARGET_SUBFOLDER_NAME
    effective_parent_id = parent_folder_id or ONEDRIVE_TARGET_PARENT_FOLDER_ID
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    parent_path_segment = (
        f"items/{effective_parent_id}"
        if effective_parent_id and effective_parent_id.lower() != "root"
        else "root"
    )
    clean_target_folder_name = sanitize_filename(target_folder_name, 100)
    check_url = f"https://graph.microsoft.com/v1.0/me/drive/{parent_path_segment}/children?$filter=name eq '{clean_target_folder_name}'"
    try:
        response = requests.get(check_url, headers=headers, timeout=15)
        response.raise_for_status()
        children = response.json().get("value", [])
        if children:
            folder_id = children[0]["id"]
            app.logger.info(
                f"OD_UTIL: Folder '{clean_target_folder_name}' found (ID: {folder_id})."
            )
            return folder_id
        app.logger.info(
            f"OD_UTIL: Folder '{clean_target_folder_name}' not found. Creating."
        )
        create_url = (
            f"https://graph.microsoft.com/v1.0/me/drive/{parent_path_segment}/children"
        )
        payload = {
            "name": clean_target_folder_name,
            "folder": {},
            "@microsoft.graph.conflictBehavior": "rename",
        }
        response_create = requests.post(
            create_url, headers=headers, json=payload, timeout=15
        )
        response_create.raise_for_status()
        created_folder_id = response_create.json()["id"]
        app.logger.info(
            f"OD_UTIL: Folder '{clean_target_folder_name}' created (ID: {created_folder_id})."
        )
        return created_folder_id
    except requests.exceptions.RequestException as e:
        app.logger.error(
            f"OD_UTIL: Error ensuring folder '{clean_target_folder_name}': {e}"
        )
        if hasattr(e, "response") and e.response is not None:
            app.logger.error(
                f"OD_UTIL: API Status: {e.response.status_code}, Body: {e.response.text[:500]}"
            )
        return None


def get_processed_items_from_onedrive_file(job_id_prefix, token, folder_id, filename):
    if not token or not folder_id:
        app.logger.error(
            f"DEDUP_ITEMS [{job_id_prefix}]: Token or FolderID missing for file '{filename}'."
        )
        return set()
    download_url = f"https://graph.microsoft.com/v1.0/me/drive/items/{folder_id}:/{sanitize_filename(filename)}:/content"
    headers = {"Authorization": f"Bearer {token}"}
    items = set()
    job_id = f"{job_id_prefix}_{time.time_ns() % 100000}"
    app.logger.debug(f"DEDUP_ITEMS [{job_id}]: Attempting to read '{filename}'.")

    max_retries = 3
    base_retry_delay_seconds = 5

    for attempt in range(max_retries):
        current_delay = base_retry_delay_seconds * (2**attempt)  # Exponential backoff
        try:
            response = requests.get(download_url, headers=headers, timeout=30)
            if response.status_code == 200:
                items.update(
                    line.strip() for line in response.text.splitlines() if line.strip()
                )
                app.logger.info(
                    f"DEDUP_ITEMS [{job_id}]: Read {len(items)} items from '{filename}' on attempt {attempt + 1}."
                )
                return items  # Success
            elif response.status_code == 404:
                app.logger.info(
                    f"DEDUP_ITEMS [{job_id}]: File '{filename}' not found in OneDrive on attempt {attempt + 1}. Will be created if items are added."
                )
                return (
                    items  # File not found is not an error for this function's purpose
                )
            elif response.status_code == 503:
                app.logger.warning(
                    f"DEDUP_ITEMS [{job_id}]: Received 503 (Service Unavailable) on attempt {attempt + 1}/{max_retries} for '{filename}'."
                )
                if attempt < max_retries - 1:
                    app.logger.info(
                        f"DEDUP_ITEMS [{job_id}]: Retrying in {current_delay}s..."
                    )
                    time.sleep(current_delay)
                    continue  # Go to next attempt
                else:  # Last attempt failed with 503
                    app.logger.error(
                        f"DEDUP_ITEMS [{job_id}]: Final attempt failed with 503 for '{filename}'."
                    )
                    response.raise_for_status()  # Raise exception for the last 503
            else:  # Other HTTP errors
                app.logger.error(
                    f"DEDUP_ITEMS [{job_id}]: Unexpected HTTP {response.status_code} for '{filename}' on attempt {attempt + 1}."
                )
                response.raise_for_status()  # Raise for other client/server errors
        except requests.exceptions.RequestException as e:
            app.logger.error(
                f"DEDUP_ITEMS [{job_id}]: RequestException downloading '{filename}' on attempt {attempt + 1}: {e}"
            )
            if hasattr(e, "response") and e.response is not None:
                app.logger.error(
                    f"DEDUP_ITEMS [{job_id}]: API Response Status: {e.response.status_code}, Body: {e.response.text[:200]}"
                )
            if attempt < max_retries - 1:
                app.logger.info(
                    f"DEDUP_ITEMS [{job_id}]: Retrying in {current_delay}s..."
                )
                time.sleep(current_delay)
            else:  # Last attempt failed with RequestException
                app.logger.error(
                    f"DEDUP_ITEMS [{job_id}]: Final attempt failed with RequestException for '{filename}'."
                )
                # Decide what to return: empty set or raise. For this function, empty set might be safer.
                return set()  # Return empty set on final failure

    app.logger.error(
        f"DEDUP_ITEMS [{job_id}]: All {max_retries} retries failed for '{filename}'. Returning empty set."
    )
    return items  # Should ideally not be reached if logic is correct, but as a fallback


def add_item_to_onedrive_file(job_id_prefix, token, folder_id, filename, item_to_add):
    if not all([token, folder_id, filename, item_to_add]):
        app.logger.error(
            f"DEDUP_ITEMS [{job_id_prefix}]: Missing parameters to add item to '{filename}'."
        )
        return False

    job_id = f"{job_id_prefix}_{time.time_ns() % 100000}"
    # Get current items (this will also use retry logic)
    current_items = get_processed_items_from_onedrive_file(
        f"GET_{job_id_prefix}", token, folder_id, filename
    )

    if item_to_add in current_items:
        app.logger.info(
            f"DEDUP_ITEMS [{job_id}]: Item '{item_to_add}' already in '{filename}'. No update needed."
        )
        return True

    current_items.add(item_to_add)
    content_to_upload = "\n".join(sorted(list(current_items)))
    upload_url = f"https://graph.microsoft.com/v1.0/me/drive/items/{folder_id}:/{sanitize_filename(filename)}:/content?@microsoft.graph.conflictBehavior=replace"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "text/plain; charset=utf-8",
    }
    app.logger.debug(
        f"DEDUP_ITEMS [{job_id}]: Updating '{filename}' with item '{item_to_add}'. Total items: {len(current_items)}."
    )

    max_retries = 3
    base_retry_delay_seconds = 5

    for attempt in range(max_retries):
        current_delay = base_retry_delay_seconds * (2**attempt)
        try:
            response = requests.put(
                upload_url,
                headers=headers,
                data=content_to_upload.encode("utf-8"),
                timeout=60,
            )
            if response.status_code in [
                200,
                201,
            ]:  # 200 OK for update, 201 Created for new file
                app.logger.info(
                    f"DEDUP_ITEMS [{job_id}]: File '{filename}' updated successfully on OneDrive with '{item_to_add}' on attempt {attempt + 1}. Total items: {len(current_items)}."
                )
                return True
            elif response.status_code == 503:
                app.logger.warning(
                    f"DEDUP_ITEMS [{job_id}]: Received 503 (Service Unavailable) on attempt {attempt + 1}/{max_retries} for uploading to '{filename}'."
                )
                if attempt < max_retries - 1:
                    app.logger.info(
                        f"DEDUP_ITEMS [{job_id}]: Retrying in {current_delay}s..."
                    )
                    time.sleep(current_delay)
                    continue
                else:
                    app.logger.error(
                        f"DEDUP_ITEMS [{job_id}]: Final attempt failed with 503 for uploading to '{filename}'."
                    )
                    response.raise_for_status()
            else:
                app.logger.error(
                    f"DEDUP_ITEMS [{job_id}]: Unexpected HTTP {response.status_code} for uploading to '{filename}' on attempt {attempt + 1}."
                )
                response.raise_for_status()
        except requests.exceptions.RequestException as e:
            app.logger.error(
                f"DEDUP_ITEMS [{job_id}]: RequestException uploading updates to '{filename}' on attempt {attempt + 1}: {e}"
            )
            if hasattr(e, "response") and e.response is not None:
                app.logger.error(
                    f"DEDUP_ITEMS [{job_id}]: API Response Status: {e.response.status_code}, Body: {e.response.text[:200]}"
                )
            if attempt < max_retries - 1:
                app.logger.info(
                    f"DEDUP_ITEMS [{job_id}]: Retrying in {current_delay}s..."
                )
                time.sleep(current_delay)
            else:
                app.logger.error(
                    f"DEDUP_ITEMS [{job_id}]: Final attempt failed with RequestException for uploading to '{filename}'."
                )
                return False  # Indicate failure

    app.logger.error(
        f"DEDUP_ITEMS [{job_id}]: All {max_retries} retries failed for uploading to '{filename}'."
    )
    return False


# --- Fonctions de Polling des Emails ---
def mark_email_as_read(token, msg_id):
    if not token or not msg_id:
        app.logger.error("MARK_READ: Token/Email ID missing.")
        return False
    url = f"https://graph.microsoft.com/v1.0/me/messages/{msg_id}"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
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
        app.logger.warning("POLLER: SENDER_LIST_FOR_POLLING empty.")
        return 0
    if not MAKE_SCENARIO_WEBHOOK_URL:
        app.logger.error("POLLER: MAKE_SCENARIO_WEBHOOK_URL not set.")
        return 0
    if not msal_app:
        app.logger.error("POLLER: MSAL app not configured.")
        return 0
    token = get_onedrive_access_token()
    if not token:
        app.logger.error("POLLER: Failed to get OneDrive token.")
        return 0
    onedrive_app_folder_id = ensure_onedrive_folder(token)
    if not onedrive_app_folder_id:
        app.logger.error("POLLER: Failed to ensure OneDrive folder.")
        return 0
    processed_email_ids = get_processed_items_from_onedrive_file(
        "WH_TRIG",
        token,
        onedrive_app_folder_id,
        PROCESSED_WEBHOOK_TRIGGERS_ONEDRIVE_FILENAME,
    )
    triggered_webhook_count = 0
    try:
        since_date_str = (datetime.now(timezone.utc) - timedelta(days=2)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        sender_filter_parts = [
            f"from/emailAddress/address eq '{sender}'"
            for sender in SENDER_LIST_FOR_POLLING
        ]
        sender_filter_string = " or ".join(sender_filter_parts)
        filter_query = f"isRead eq false and receivedDateTime ge {since_date_str} and ({sender_filter_string})"
        graph_url = (
            f"https://graph.microsoft.com/v1.0/me/mailFolders/inbox/messages?"
            f"$filter={filter_query}&$select=id,subject,from,receivedDateTime,bodyPreview&"
            f"$top=25&$orderby=receivedDateTime asc"
        )
        app.logger.info(f"POLLER: Querying Graph API. Filter: '{filter_query}'")
        headers_mail = {
            "Authorization": f"Bearer {token}",
            "Prefer": 'outlook.body-content-type="text"',
        }
        response = requests.get(graph_url, headers=headers_mail, timeout=45)
        response.raise_for_status()
        emails = response.json().get("value", [])
        app.logger.info(
            f"POLLER: Found {len(emails)} unread email(s) matching criteria (before dedup)."
        )
        for mail in emails:
            mail_id = mail["id"]
            mail_subject = mail.get("subject", "N/A_Subject")
            sender_address = (
                mail.get("from", {})
                .get("emailAddress", {})
                .get("address", "N/A_Sender")
                .lower()
            )
            if mail_id in processed_email_ids:
                app.logger.debug(
                    f"POLLER: Email ID {mail_id} (Subj: '{mail_subject[:30]}...') already processed. Skipping."
                )
                continue
            app.logger.info(
                f"POLLER: New email: ID={mail_id}, Subj='{mail_subject[:50]}...'. Triggering Make."
            )
            payload_for_make = {
                "microsoft_graph_email_id": mail_id,
                "subject": mail_subject,
                "receivedDateTime": mail.get("receivedDateTime"),
                "sender_address": sender_address,
                "bodyPreview": mail.get("bodyPreview", ""),
            }
            try:
                webhook_response = requests.post(
                    MAKE_SCENARIO_WEBHOOK_URL, json=payload_for_make, timeout=30
                )
                if (
                    webhook_response.status_code == 200
                    and "accepted" in webhook_response.text.lower()
                ):
                    app.logger.info(
                        f"POLLER: Make webhook OK for email {mail_id}. Resp: {webhook_response.status_code} - {webhook_response.text}"
                    )
                    if add_item_to_onedrive_file(
                        "WH_TRIG_ADD",
                        token,
                        onedrive_app_folder_id,
                        PROCESSED_WEBHOOK_TRIGGERS_ONEDRIVE_FILENAME,
                        mail_id,
                    ):
                        triggered_webhook_count += 1
                        if not mark_email_as_read(token, mail_id):
                            app.logger.warning(
                                f"POLLER: Failed to mark email {mail_id} as read."
                            )
                    else:
                        app.logger.error(
                            f"POLLER: CRITICAL - Failed to log email ID {mail_id}. Email NOT marked read."
                        )
                else:
                    app.logger.error(
                        f"POLLER: Make webhook FAILED for email {mail_id}. Status: {webhook_response.status_code}, Resp: {webhook_response.text[:200]}"
                    )
            except requests.exceptions.RequestException as e_webhook:
                app.logger.error(
                    f"POLLER: Exception during Make webhook for email {mail_id}: {e_webhook}"
                )
        return triggered_webhook_count
    except requests.exceptions.RequestException as e_graph:
        app.logger.error(f"POLLER: Graph API error: {e_graph}")
        if hasattr(e_graph, "response") and e_graph.response is not None:
            app.logger.error(
                f"POLLER: API Resp: {e_graph.response.status_code} - {e_graph.response.text[:500]}"
            )
        return 0
    except Exception as e_general:
        app.logger.error(f"POLLER: Unexpected error: {e_general}", exc_info=True)
        return 0


def background_email_poller():
    app.logger.info(
        f"BG_POLLER: Email polling thread started. TZ: {POLLING_TIMEZONE_STR}."
    )
    consecutive_error_count = 0
    MAX_CONSECUTIVE_ERRORS = 5
    while True:
        try:
            now_in_configured_tz = datetime.now(TZ_FOR_POLLING)
            current_hour, current_weekday = (
                now_in_configured_tz.hour,
                now_in_configured_tz.weekday(),
            )
            is_active_day = current_weekday in POLLING_ACTIVE_DAYS
            is_active_time = (
                POLLING_ACTIVE_START_HOUR <= current_hour < POLLING_ACTIVE_END_HOUR
            )
            log_sched = (
                f"Day:{current_weekday}[{POLLING_ACTIVE_DAYS}], "
                f"Hour:{current_hour:02d}h [{POLLING_ACTIVE_START_HOUR:02d}h-{POLLING_ACTIVE_END_HOUR:02d}h {POLLING_TIMEZONE_STR}]"
            )
            if is_active_day and is_active_time:
                app.logger.info(f"BG_POLLER: Active period ({log_sched}). Polling.")
                if not all(
                    [
                        ONEDRIVE_CLIENT_ID,
                        ONEDRIVE_CLIENT_SECRET,
                        ONEDRIVE_REFRESH_TOKEN,
                        SENDER_LIST_FOR_POLLING,
                        MAKE_SCENARIO_WEBHOOK_URL,
                        msal_app,
                    ]
                ):
                    app.logger.warning(
                        "BG_POLLER: Essential polling config incomplete. Waiting 60s."
                    )
                    time.sleep(60)
                    continue
                webhooks_triggered = check_new_emails_and_trigger_make_webhook()
                app.logger.info(
                    f"BG_POLLER: Active poll cycle finished. {webhooks_triggered} webhook(s) triggered."
                )
                consecutive_error_count = 0
                sleep_duration = EMAIL_POLLING_INTERVAL_SECONDS
            else:
                app.logger.info(
                    f"BG_POLLER: Outside active period ({log_sched}). Sleeping."
                )
                sleep_duration = POLLING_INACTIVE_CHECK_INTERVAL_SECONDS
            app.logger.debug(f"BG_POLLER: Sleeping for {sleep_duration} seconds.")
            time.sleep(sleep_duration)
        except Exception as e:
            consecutive_error_count += 1
            app.logger.error(
                f"BG_POLLER: Unhandled error in loop (Err #{consecutive_error_count}): {e}",
                exc_info=True,
            )
            if consecutive_error_count >= MAX_CONSECUTIVE_ERRORS:
                app.logger.critical(
                    f"BG_POLLER: Max errors ({MAX_CONSECUTIVE_ERRORS}). Stopping thread."
                )
                break
            sleep_on_error_duration = max(60, EMAIL_POLLING_INTERVAL_SECONDS) * (
                2**consecutive_error_count
            )
            app.logger.info(
                f"BG_POLLER: Sleeping for {sleep_on_error_duration}s due to error."
            )
            time.sleep(sleep_on_error_duration)


# --- Endpoints API ---


@app.route("/api/register_local_downloader_url", methods=["POST"])
def register_local_downloader_url():
    received_token = request.headers.get("X-Register-Token")
    if REGISTER_LOCAL_URL_TOKEN and received_token != REGISTER_LOCAL_URL_TOKEN:
        app.logger.warning(
            f"API_REG_LT_URL: Unauthorized. Token: '{str(received_token)[:20]}...'"
        )
        return jsonify({"status": "error", "message": "Unauthorized"}), 401
    try:
        data = request.get_json()
        if not data:
            return jsonify({"status": "error", "message": "Invalid JSON"}), 400
    except Exception:
        return jsonify({"status": "error", "message": "Malformed JSON"}), 400

    new_lt_url = data.get("localtunnel_url")
    if new_lt_url and not isinstance(new_lt_url, str):
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "'localtunnel_url' must be a string or null.",
                }
            ),
            400,
        )
    if new_lt_url and not (
        new_lt_url.startswith("http://") or new_lt_url.startswith("https://")
    ):
        return (
            jsonify({"status": "error", "message": "Invalid localtunnel URL format."}),
            400,
        )

    try:
        if redis_client:  # Try Redis first
            if new_lt_url:
                redis_client.set(LOCALTUNNEL_URL_REDIS_KEY, new_lt_url)
                app.logger.info(
                    f"API_REG_LT_URL: Localtunnel URL registered in Redis: '{new_lt_url}'"
                )
            else:  # new_lt_url is None or empty, meaning unregister
                redis_client.delete(LOCALTUNNEL_URL_REDIS_KEY)
                app.logger.info(f"API_REG_LT_URL: Localtunnel URL deleted from Redis.")
        else:  # Fallback to ephemeral file storage
            app.logger.warning(
                f"API_REG_LT_URL: Redis unavailable, using fallback file storage for Localtunnel URL."
            )
            # SIGNAL_DIR.mkdir(parents=True, exist_ok=True) # Already done at startup
            if new_lt_url:
                with open(LOCALTUNNEL_URL_FILE, "w") as f:
                    f.write(new_lt_url)
                app.logger.info(
                    f"API_REG_LT_URL: Localtunnel URL (fallback file) registered: '{new_lt_url}'"
                )
            else:  # Unregister
                if LOCALTUNNEL_URL_FILE.exists():
                    LOCALTUNNEL_URL_FILE.unlink()
                app.logger.info(
                    f"API_REG_LT_URL: Localtunnel URL (fallback file) unregistered/cleared."
                )
        return (
            jsonify({"status": "success", "message": "Localtunnel URL processed."}),
            200,
        )
    except redis.exceptions.RedisError as e_redis_op:  # Catch specific Redis operational errors
        app.logger.error(
            f"API_REG_LT_URL: Redis operation error: {e_redis_op}. Check Redis server/connection.",
            exc_info=True,
        )
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Server error (Redis operation failed) processing Localtunnel URL.",
                }
            ),
            500,
        )
    except Exception as e:
        app.logger.error(
            f"API_REG_LT_URL: Server error processing Localtunnel URL: {e}",
            exc_info=True,
        )
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Server error processing Localtunnel URL registration.",
                }
            ),
            500,
        )


@app.route("/api/get_local_downloader_url", methods=["GET"])
def get_local_downloader_url_for_make():
    received_token = request.headers.get("X-API-Token")
    if not EXPECTED_API_TOKEN:
        app.logger.critical(
            "API_GET_LT_URL: EXPECTED_API_TOKEN not set. Endpoint insecure."
        )
    elif received_token != EXPECTED_API_TOKEN:
        app.logger.warning(
            f"API_GET_LT_URL: Unauthorized. Token: '{str(received_token)[:20]}...'"
        )
        return jsonify({"status": "error", "message": "Unauthorized"}), 401

    lt_url = None
    try:
        if redis_client:  # Try Redis first
            url_bytes = redis_client.get(LOCALTUNNEL_URL_REDIS_KEY)
            if url_bytes:
                lt_url = url_bytes.decode("utf-8")
                app.logger.info(
                    f"API_GET_LT_URL: Fetched Localtunnel URL from Redis: '{lt_url}'"
                )
            else:
                app.logger.info(
                    f"API_GET_LT_URL: Localtunnel URL not found in Redis (key: {LOCALTUNNEL_URL_REDIS_KEY})."
                )
        else:  # Fallback to ephemeral file storage if Redis was never available
            app.logger.warning(
                f"API_GET_LT_URL: Redis unavailable, trying fallback file for Localtunnel URL."
            )
            if LOCALTUNNEL_URL_FILE.exists():
                with open(LOCALTUNNEL_URL_FILE, "r") as f:
                    lt_url_file_content = f.read().strip()
                if lt_url_file_content:  # Ensure file is not empty
                    lt_url = lt_url_file_content
                    app.logger.info(
                        f"API_GET_LT_URL: Fetched Localtunnel URL from fallback file: '{lt_url}'"
                    )
                else:
                    app.logger.warning(
                        f"API_GET_LT_URL: Fallback file '{LOCALTUNNEL_URL_FILE}' exists but is empty."
                    )
            else:
                app.logger.info(
                    f"API_GET_LT_URL: Fallback file '{LOCALTUNNEL_URL_FILE}' does not exist."
                )

        if lt_url:
            return jsonify({"status": "success", "localtunnel_url": lt_url}), 200
        else:
            app.logger.warning(
                "API_GET_LT_URL: Localtunnel URL ultimately not found in Redis or fallback file."
            )
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": "Local worker URL not registered or currently unavailable.",
                    }
                ),
                404,
            )
    except redis.exceptions.RedisError as e_redis_op:  # Catch specific Redis operational errors
        app.logger.error(
            f"API_GET_LT_URL: Redis operation error: {e_redis_op}. Check Redis server/connection.",
            exc_info=True,
        )
        # Fallback to file if Redis op fails mid-request (after initial successful connection)
        app.logger.warning(
            f"API_GET_LT_URL: Redis operation failed. Attempting fallback to file for this request."
        )
        if LOCALTUNNEL_URL_FILE.exists():
            try:
                with open(LOCALTUNNEL_URL_FILE, "r") as f:
                    lt_url = f.read().strip()
                if lt_url:
                    app.logger.info(
                        f"API_GET_LT_URL: Fetched (after Redis error) from fallback file: '{lt_url}'"
                    )
                    return (
                        jsonify({"status": "success", "localtunnel_url": lt_url}),
                        200,
                    )
            except Exception as e_file_fallback:
                app.logger.error(
                    f"API_GET_LT_URL: Error reading fallback file after Redis error: {e_file_fallback}",
                    exc_info=True,
                )
        app.logger.error(
            f"API_GET_LT_URL: URL not found even after Redis error and fallback attempt."
        )
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Server error (Redis op failed) and fallback unavailable.",
                }
            ),
            503,
        )  # Service Unavailable
    except Exception as e:
        app.logger.error(
            f"API_GET_LT_URL: Error retrieving localtunnel URL: {e}", exc_info=True
        )
        return (
            jsonify(
                {"status": "error", "message": "Server error reading local worker URL."}
            ),
            500,
        )


@app.route("/api/log_processed_url", methods=["POST"])
def api_log_processed_url():
    api_token = request.headers.get("X-API-Token")
    if not EXPECTED_API_TOKEN:
        return jsonify({"s": "err", "m": "Server API token not set."}), 500
    if api_token != EXPECTED_API_TOKEN:
        return jsonify({"s": "err", "m": "Unauthorized."}), 401
    try:
        data = request.get_json()
    except Exception:
        return jsonify({"s": "err", "m": "JSON format error"}), 400
    if not data or "dropbox_url" not in data:
        return jsonify({"s": "err", "m": "'dropbox_url' required."}), 400
    dropbox_url = data.get("dropbox_url")
    if not isinstance(dropbox_url, str) or not dropbox_url.lower().startswith(
        "https://www.dropbox.com/"
    ):
        return jsonify({"s": "err", "m": "Invalid Dropbox URL."}), 400
    if not msal_app:
        return jsonify({"s": "err", "m": "OneDrive not configured"}), 503
    token = get_onedrive_access_token()
    if not token:
        return jsonify({"s": "err", "m": "OneDrive token failed."}), 500
    onedrive_app_folder_id = ensure_onedrive_folder(token)
    if not onedrive_app_folder_id:
        return jsonify({"s": "err", "m": "OneDrive folder access failed."}), 500
    if add_item_to_onedrive_file(
        "LOG_URL",
        token,
        onedrive_app_folder_id,
        PROCESSED_URLS_ONEDRIVE_FILENAME,
        dropbox_url,
    ):
        return jsonify({"s": "ok", "m": f"URL logged."}), 200
    else:
        return jsonify({"s": "err", "m": f"Failed to update log."}), 500


@app.route("/api/check_trigger", methods=["GET"])
def check_local_workflow_trigger():
    response_data = {"command_pending": False, "payload": None}
    if TRIGGER_SIGNAL_FILE.exists():  # Still using file for this signal
        try:
            with open(TRIGGER_SIGNAL_FILE, "r") as f:
                payload_from_file = json.load(f)
            response_data["command_pending"] = True
            response_data["payload"] = payload_from_file
            TRIGGER_SIGNAL_FILE.unlink()
            app.logger.info(
                f"LOCAL_CHECK_API: Signal read from file, deleted. Payload: {payload_from_file}"
            )
        except Exception as e:
            app.logger.error(
                f"LOCAL_CHECK_API: Error processing signal file: {e}", exc_info=True
            )
    return jsonify(response_data)


@app.route("/api/ping", methods=["GET", "HEAD"])
def api_ping():
    client_ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    app.logger.info(f"PING_API: Received /api/ping from IP:{client_ip}")
    response = jsonify(
        {"status": "pong", "timestamp_utc": datetime.now(timezone.utc).isoformat()}
    )
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return response, 200


# Endpoints PROTECTED by HTTP Basic Auth
@app.route("/")
@auth.login_required
def serve_trigger_page_main():
    if not users and (TRIGGER_PAGE_USER_ENV or TRIGGER_PAGE_PASSWORD_ENV):
        app.logger.error("AUTH ERROR: User/pass env vars set, but 'users' dict empty.")
        return "Server auth config error.", 500
    app.logger.info(
        f"ROOT_UI: Request for '/' by user '{auth.current_user()}'. Serving trigger_page.html."
    )
    try:
        # Simplified path, assuming trigger_page.html is in the same directory as app_render.py or in 'static'
        # For Render, files are typically at the root of your project structure.
        # So, app.root_path usually points to the directory containing app_render.py
        return send_from_directory(app.root_path, "trigger_page.html")
    except FileNotFoundError:
        app.logger.error(
            f"ROOT_UI: CRITICAL - 'trigger_page.html' not found in {app.root_path}."
        )
        return "Error: Main page content not found.", 404
    except Exception as e:
        app.logger.error(
            f"ROOT_UI: Error serving 'trigger_page.html': {e}", exc_info=True
        )
        return "Internal server error serving UI.", 500


@app.route("/api/get_local_status", methods=["GET"])
@auth.login_required
def get_local_status_proxied():
    app.logger.info(
        f"PROXY_STATUS: /api/get_local_status by user '{auth.current_user()}'."
    )
    received_ui_token = request.args.get("ui_token")
    if REMOTE_UI_ACCESS_TOKEN_ENV and (
        not received_ui_token or received_ui_token != REMOTE_UI_ACCESS_TOKEN_ENV
    ):
        app.logger.warning(
            f"PROXY_STATUS: Invalid ui_token by '{auth.current_user()}'."
        )
        return jsonify({"error": "Invalid UI token"}), 403

    localtunnel_url = None  # Will be populated from Redis or file
    try:  # Fetch URL using the same logic as /api/get_local_downloader_url but without token check here (already auth'd by Basic)
        if redis_client:
            url_bytes = redis_client.get(LOCALTUNNEL_URL_REDIS_KEY)
            if url_bytes:
                localtunnel_url = url_bytes.decode("utf-8")
        if (
            not localtunnel_url and not redis_client
        ):  # If redis_client is None or URL not found in Redis
            if LOCALTUNNEL_URL_FILE.exists():
                with open(LOCALTUNNEL_URL_FILE, "r") as f:
                    file_content = f.read().strip()
                    if file_content:
                        localtunnel_url = file_content  # Assign if not empty
    except Exception as e_url_fetch:  # Catch errors during URL fetching for this proxy endpoint
        app.logger.error(
            f"PROXY_STATUS: Error fetching LT URL for status proxy: {e_url_fetch}"
        )
        # Don't immediately fail; proceed to check if localtunnel_url was fetched before error

    if not localtunnel_url:
        app.logger.warning("PROXY_STATUS: LT URL not available for proxy.")
        return (
            jsonify(
                {
                    "overall_status_text": "Worker Local Indisponible",
                    "status_text": "Worker non connecté.",
                }
            ),
            503,
        )

    try:
        target_url = f"{localtunnel_url.rstrip('/')}/api/get_remote_status_summary"
        headers_to_worker = {}
        if INTERNAL_WORKER_COMMS_TOKEN_ENV:
            headers_to_worker["X-Worker-Token"] = INTERNAL_WORKER_COMMS_TOKEN_ENV
        else:
            app.logger.warning(
                f"PROXY_STATUS: No INTERNAL_WORKER_COMMS_TOKEN_ENV. Calling {target_url} unauth'd."
            )

        response_local = requests.get(target_url, headers=headers_to_worker, timeout=10)
        response_local.raise_for_status()
        local_data = response_local.json()
        # This mapping needs to be robust based on what app_new.py actually sends
        return (
            jsonify(
                {
                    "overall_status_code_from_worker": local_data.get(
                        "overall_status_code"
                    ),  # Pass the raw code
                    "overall_status_text": local_data.get(
                        "overall_status_text_display",
                        local_data.get("overall_status_code", "état inconnu"),
                    ),  # A display-friendly version if app_new provides it, else code
                    "status_text": local_data.get(
                        "status_text_detail", local_data.get("last_updated_utc", "")
                    ),
                    "current_step_name": local_data.get(
                        "current_step_name"
                    ),  # Pass through
                    "progress_current": local_data.get("progress_current", 0),
                    "progress_total": local_data.get("progress_total", 0),
                    "recent_downloads": local_data.get("recent_downloads", []),
                    "last_sequence_summary": local_data.get(
                        "last_sequence_summary"
                    ),  # Pass through
                }
            ),
            200,
        )
    except requests.exceptions.Timeout:
        return (
            jsonify(
                {
                    "overall_status_text": "Worker Local (Timeout)",
                    "status_text": "Timeout connexion worker.",
                }
            ),
            504,
        )
    except requests.exceptions.ConnectionError:
        return (
            jsonify(
                {
                    "overall_status_text": "Worker Local (Connexion Refusée)",
                    "status_text": "Connexion worker refusée.",
                }
            ),
            502,
        )
    except requests.exceptions.HTTPError as e_http:
        status_code = e_http.response.status_code
        err_msg = f"Worker Local (Erreur HTTP {status_code})"
        detail_msg = "Erreur HTTP du worker."
        if status_code == 401:
            app.logger.error(
                f"PROXY_STATUS: 401 Unauth from worker {target_url}. Check INTERNAL_WORKER_COMMS_TOKEN_ENV."
            )
            err_msg, detail_msg = (
                "Erreur Authentification Interne",
                "Auth vers worker local échouée.",
            )
        return (
            jsonify({"overall_status_text": err_msg, "status_text": detail_msg}),
            status_code,
        )
    except requests.exceptions.RequestException as e_req:
        return (
            jsonify(
                {
                    "overall_status_text": "Worker Local (Erreur Réseau)",
                    "status_text": "Erreur réseau vers worker.",
                }
            ),
            503,
        )
    except Exception as e_gen:
        app.logger.error(
            f"PROXY_STATUS: Generic error for {target_url}: {e_gen}", exc_info=True
        )
        return (
            jsonify(
                {
                    "overall_status_text": "Erreur Serveur Distant (Proxy)",
                    "status_text": "Erreur interne proxy.",
                }
            ),
            500,
        )


@app.route("/api/trigger_local_workflow", methods=["POST"])
@auth.login_required
def trigger_local_workflow_authed():
    app.logger.info(f"LOCAL_TRIGGER_API: Called by user '{auth.current_user()}'.")
    payload = request.json
    if not payload:
        payload = {"command": "start_manual_generic"}
    elif not isinstance(payload, dict):
        payload = {"command": "start_manual_generic", "original_payload": payload}
    payload.setdefault("timestamp_utc", datetime.now(timezone.utc).isoformat())
    try:  # Still using file for this signal
        with open(TRIGGER_SIGNAL_FILE, "w") as f:
            json.dump(payload, f)
        app.logger.info(
            f"LOCAL_TRIGGER_API: Signal file '{TRIGGER_SIGNAL_FILE}' set. Payload: {payload}"
        )
        return jsonify({"status": "ok", "message": "Local workflow signal set."}), 200
    except Exception as e:
        app.logger.error(
            f"LOCAL_TRIGGER_API: Error writing signal file: {e}", exc_info=True
        )
        return (
            jsonify(
                {"status": "error", "message": "Internal server error setting signal."}
            ),
            500,
        )


@app.route("/api/check_emails_and_download", methods=["POST"])
@auth.login_required
def api_check_emails_and_download_authed():
    app.logger.info(
        f"API_EMAIL_CHECK: Manual trigger from user '{auth.current_user()}'."
    )

    def run_email_check_task_in_thread():
        with app.app_context():
            try:
                app.logger.info("API_EMAIL_CHECK_THREAD: Starting email check...")
                webhooks_triggered = check_new_emails_and_trigger_make_webhook()
                app.logger.info(
                    f"API_EMAIL_CHECK_THREAD: Finished. {webhooks_triggered} webhook(s) triggered."
                )
            except Exception as e_thread:
                app.logger.error(
                    f"API_EMAIL_CHECK_THREAD: Error: {e_thread}", exc_info=True
                )

    if not all(
        [
            ONEDRIVE_CLIENT_ID,
            ONEDRIVE_CLIENT_SECRET,
            ONEDRIVE_REFRESH_TOKEN,
            SENDER_LIST_FOR_POLLING,
            MAKE_SCENARIO_WEBHOOK_URL,
            msal_app,
        ]
    ):
        return (
            jsonify({"status": "error", "message": "Config serveur email incomplète."}),
            503,
        )
    email_thread = threading.Thread(
        target=run_email_check_task_in_thread, name="ManualEmailCheckThread"
    )
    email_thread.start()
    return (
        jsonify(
            {
                "status": "success",
                "message": "Vérification emails (arrière-plan) lancée.",
            }
        ),
        202,
    )


# --- Démarrage ---
if __name__ == "__main__":
    is_debug_mode = os.environ.get("FLASK_DEBUG", "False").lower() == "true"
    should_start_background_threads = (
        not is_debug_mode or os.environ.get("WERKZEUG_RUN_MAIN") == "true"
    )

    if should_start_background_threads:
        app.logger.info("MAIN_APP: Preparing background threads.")
        if all(
            [
                ONEDRIVE_CLIENT_ID,
                ONEDRIVE_CLIENT_SECRET,
                ONEDRIVE_REFRESH_TOKEN,
                msal_app,
                SENDER_LIST_FOR_POLLING,
                MAKE_SCENARIO_WEBHOOK_URL,
            ]
        ):
            email_poller_thread = threading.Thread(
                target=background_email_poller, name="EmailPollerThread", daemon=True
            )
            email_poller_thread.start()
            app.logger.info(f"MAIN_APP: Email polling thread started.")
        else:
            app.logger.warning(
                "MAIN_APP: Email polling thread NOT started due to incomplete OneDrive/MSAL/Webhook config."
            )
    else:
        app.logger.info(
            "MAIN_APP: Background threads not started by this Werkzeug child process."
        )

    server_port = int(os.environ.get("PORT", 10000))

    if not users:
        app.logger.warning(
            "MAIN_APP: HTTP Basic Auth for UI NOT configured (TRIGGER_PAGE_USER/PASSWORD env vars likely not set)."
        )
    if not EXPECTED_API_TOKEN:
        app.logger.critical(
            "MAIN_APP: PROCESS_API_TOKEN not set. Make.com endpoints INSECURE."
        )
    if not REGISTER_LOCAL_URL_TOKEN:
        app.logger.warning(
            "MAIN_APP: REGISTER_LOCAL_URL_TOKEN not set. Local worker registration endpoint INSECURE."
        )
    if not REMOTE_UI_ACCESS_TOKEN_ENV and users:
        app.logger.info(
            "MAIN_APP: REMOTE_UI_ACCESS_TOKEN for /api/get_local_status NOT set; ui_token check skipped if Basic Auth'd."
        )
    if not INTERNAL_WORKER_COMMS_TOKEN_ENV:
        app.logger.warning(
            "MAIN_APP: INTERNAL_WORKER_COMMS_TOKEN not set. app_render <-> app_new communication UNauthenticated."
        )

    app.logger.info(
        f"MAIN_APP: Flask server starting on 0.0.0.0:{server_port}. Debug: {is_debug_mode}"
    )
    app.run(
        host="0.0.0.0",
        port=server_port,
        debug=is_debug_mode,
        use_reloader=(is_debug_mode and os.environ.get("WERKZEUG_RUN_MAIN") != "true"),
    )
