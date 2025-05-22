from flask import Flask, jsonify, request, send_from_directory, current_app
import os
import time
from pathlib import Path
import json
import logging
import re
import html as html_parser
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
ONEDRIVE_SCOPES_DELEGATED = ["Files.ReadWrite", "User.Read", "Mail.ReadWrite"]
ONEDRIVE_TARGET_PARENT_FOLDER_ID = os.environ.get('ONEDRIVE_TARGET_PARENT_FOLDER_ID', 'root')
ONEDRIVE_TARGET_SUBFOLDER_NAME = os.environ.get('ONEDRIVE_TARGET_SUBFOLDER_NAME', "DropboxDownloadsWorkflow")
MAKE_SCENARIO_WEBHOOK_URL = os.environ.get("MAKE_SCENARIO_WEBHOOK_URL")
SENDER_OF_INTEREST_FOR_POLLING_RAW = os.environ.get("SENDER_OF_INTEREST_FOR_POLLING")
SENDER_LIST_FOR_POLLING = [e.strip().lower() for e in SENDER_OF_INTEREST_FOR_POLLING_RAW.split(',') if e.strip()] if SENDER_OF_INTEREST_FOR_POLLING_RAW else []
if SENDER_LIST_FOR_POLLING: app.logger.info(f"CFG: Polling senders ({len(SENDER_LIST_FOR_POLLING)}): {SENDER_LIST_FOR_POLLING}")
else: app.logger.warning("CFG: SENDER_OF_INTEREST_FOR_POLLING not set.")

msal_app = None
if ONEDRIVE_CLIENT_ID and ONEDRIVE_CLIENT_SECRET:
    app.logger.info(f"CFG: MSAL init ClientID '{ONEDRIVE_CLIENT_ID[:5]}...', Authority: {ONEDRIVE_AUTHORITY}")
    msal_app = ConfidentialClientApplication(ONEDRIVE_CLIENT_ID, authority=ONEDRIVE_AUTHORITY, client_credential=ONEDRIVE_CLIENT_SECRET)
else: app.logger.warning("CFG: OneDrive Client ID/Secret missing. Graph features disabled.")

EXPECTED_API_TOKEN = os.environ.get("PROCESS_API_TOKEN")
if not EXPECTED_API_TOKEN: app.logger.warning("CFG: PROCESS_API_TOKEN not set. API insecure.")
else: app.logger.info(f"CFG: API Token expected: '{EXPECTED_API_TOKEN[:5]}...'")

PROCESSING_URLS_LOCK = threading.Lock()
PROCESSING_URLS = set()
STREAMING_WORKER_SEMAPHORE = threading.Semaphore(1)

def sanitize_filename(filename_str, max_length=230):
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
        if r.status_code == 200: urls.update(l.strip() for l in r.text.splitlines() if l.strip()); app.logger.info(f"DEDUP_URLS [{job_id}]: Read {len(urls)} URLs.")
        elif r.status_code == 404: app.logger.info(f"DEDUP_URLS [{job_id}]: {PROCESSED_URLS_ONEDRIVE_FILENAME} not found.")
        else: r.raise_for_status()
    except requests.exceptions.RequestException as e: app.logger.error(f"DEDUP_URLS [{job_id}]: Error DLing {PROCESSED_URLS_ONEDRIVE_FILENAME}: {e}")
    return urls

def add_processed_url_to_onedrive(job_id, token, folder_id, url_proc):
    if not all([token,folder_id,url_proc]): app.logger.error(f"DEDUP_URLS [{job_id}]: Missing params."); return False
    urls = get_processed_urls_from_onedrive(job_id,token,folder_id)
    if url_proc in urls: app.logger.info(f"DEDUP_URLS [{job_id}]: URL '{url_proc}' already listed."); return True
    urls.add(url_proc); content = "\n".join(sorted(list(urls)))
    ul_url = f"https://graph.microsoft.com/v1.0/me/drive/items/{folder_id}:/{PROCESSED_URLS_ONEDRIVE_FILENAME}:/content?@microsoft.graph.conflictBehavior=replace"
    h = {'Authorization':f'Bearer {token}','Content-Type':'text/plain; charset=utf-8'}
    app.logger.debug(f"DEDUP_URLS [{job_id}]: Updating {PROCESSED_URLS_ONEDRIVE_FILENAME} ({len(urls)} URLs).")
    try:
        r = requests.put(ul_url,headers=h,data=content.encode('utf-8'),timeout=60); r.raise_for_status()
        app.logger.info(f"DEDUP_URLS [{job_id}]: {PROCESSED_URLS_ONEDRIVE_FILENAME} updated ({len(urls)} URLs)."); return True
    except requests.exceptions.RequestException as e:
        app.logger.error(f"DEDUP_URLS [{job_id}]: Error ULing {PROCESSED_URLS_ONEDRIVE_FILENAME}: {e}")
        if hasattr(e,'response') and e.response: app.logger.error(f"DEDUP_URLS [{job_id}]: API Resp: {e.response.status_code} - {e.response.text}")
        return False

def _try_cancel_upload_session_streaming(job_id, ul_sess_url, fname_clean, reason="error"):
    if not ul_sess_url: return
    app.logger.info(f"STREAM [{job_id}]: Cancelling session ({reason}) for {fname_clean}: {ul_sess_url[:70]}...")
    token = get_onedrive_access_token()
    if token:
        try: requests.delete(ul_sess_url,headers={'Authorization':f'Bearer {token}'},timeout=10); app.logger.info(f"STREAM [{job_id}]: Session {fname_clean} cancelled/expired.")
        except requests.exceptions.RequestException as e: app.logger.warning(f"STREAM [{job_id}]: Failed to cancel session {fname_clean}: {e}")
    else: app.logger.warning(f"STREAM [{job_id}]: No token to cancel session {fname_clean}.")

def stream_dropbox_to_onedrive(job_id, db_url, token_initial, target_folder_id, subj_default="FichierDropbox"):
    # OneDrive Chunk Size Configuration
    ONEDRIVE_CHUNK_SIZE_MB_ENV = os.environ.get("ONEDRIVE_CHUNK_SIZE_MB", "40") # Default to 40MB
    try:
        ONEDRIVE_CHUNK_SIZE_MB = int(ONEDRIVE_CHUNK_SIZE_MB_ENV)
        if not (0 < ONEDRIVE_CHUNK_SIZE_MB <= 240) :
            app.logger.warning(f"STREAM [{job_id}]: ONEDRIVE_CHUNK_SIZE_MB ('{ONEDRIVE_CHUNK_SIZE_MB_ENV}') out of safe range (1-240MB). Using 40MB.")
            ONEDRIVE_CHUNK_SIZE_MB = 40
    except ValueError:
        app.logger.warning(f"STREAM [{job_id}]: Invalid ONEDRIVE_CHUNK_SIZE_MB ('{ONEDRIVE_CHUNK_SIZE_MB_ENV}'). Using 40MB.")
        ONEDRIVE_CHUNK_SIZE_MB = 40
    
    ONEDRIVE_CHUNK_SIZE = ONEDRIVE_CHUNK_SIZE_MB * 1024 * 1024
    CHUNK_ALIGNMENT = 320 * 1024
    if ONEDRIVE_CHUNK_SIZE % CHUNK_ALIGNMENT != 0:
        ONEDRIVE_CHUNK_SIZE = ((ONEDRIVE_CHUNK_SIZE // CHUNK_ALIGNMENT) +1) * CHUNK_ALIGNMENT
        app.logger.info(f"STREAM [{job_id}]: ONEDRIVE_CHUNK_SIZE aligned to {ONEDRIVE_CHUNK_SIZE//(1024*1024)}MB ({ONEDRIVE_CHUNK_SIZE} bytes).")
    else:
        app.logger.info(f"STREAM [{job_id}]: Using ONEDRIVE_CHUNK_SIZE: {ONEDRIVE_CHUNK_SIZE_MB}MB (from env or default) -> {ONEDRIVE_CHUNK_SIZE//(1024*1024)}MB ({ONEDRIVE_CHUNK_SIZE} bytes) after alignment.")

    app.logger.info(f"STREAM [{job_id}]: Starting stream for URL: {db_url}")
    fname_od = sanitize_filename(subj_default or "FichierDropboxStream")
    fsize_db = None; ul_sess_url_od = None
    url_unesc = html_parser.unescape(db_url); url_mod = url_unesc.replace("dl=0","dl=1")
    url_mod = re.sub(r'dl=[^&?#]+','dl=1',url_mod)
    if '?dl=1' not in url_mod and '&dl=1' not in url_mod: url_mod += ("&" if "?" in url_mod else "?") + "dl=1"
    app.logger.info(f"STREAM [{job_id}]: Dropbox stream URL: {url_mod}")

    try:
        h_db_meta = {'User-Agent':'Mozilla/5.0'}; r_meta = requests.get(url_mod,stream=True,allow_redirects=True,timeout=60,headers=h_db_meta)
        r_meta.raise_for_status(); cd = r_meta.headers.get('content-disposition')
        if cd:
            m_utf8 = re.search(r"filename\*=UTF-8''([^;\n\r]+)",cd,re.I); ext_name=None
            if m_utf8: ext_name = requests.utils.unquote(m_utf8.group(1))
            else:
                m_simple = re.search(r'filename="([^"]+)"',cd,re.I)
                if m_simple: ext_name = m_simple.group(1)
                if ext_name and '%' in ext_name:
                    try: ext_name = requests.utils.unquote(ext_name)
                    except: app.logger.warning(f"STREAM [{job_id}]: Failed unquote: {ext_name}")
            if ext_name: fname_od = sanitize_filename(ext_name); app.logger.info(f"STREAM [{job_id}]: Filename from DB: '{fname_od}'")
        if "dropbox.com/scl/fo/" in url_unesc and not any(fname_od.lower().endswith(e) for e in ['.zip','.rar','.7z']):
            fname_od = os.path.splitext(fname_od)[0]+".zip"; app.logger.info(f"STREAM [{job_id}]: Dropbox folder link, filename adjusted: '{fname_od}'")
        len_str = r_meta.headers.get('content-length')
        if len_str and len_str.isdigit(): fsize_db = int(len_str); app.logger.info(f"STREAM [{job_id}]: File: '{fname_od}', Size: {fsize_db}b.")
        else: app.logger.warning(f"STREAM [{job_id}]: Unknown DB file size for '{fname_od}'.")
        r_meta.close()
    except requests.exceptions.RequestException as e: app.logger.error(f"STREAM [{job_id}]: DB metadata error {url_mod}: {e}"); return False

    if not token_initial or not target_folder_id: app.logger.error(f"STREAM [{job_id}]: Missing initial token or OD folder ID."); return False
    cre_s_url = f"https://graph.microsoft.com/v1.0/me/drive/items/{target_folder_id}:/{fname_od}:/createUploadSession"
    s_pl = {"item":{"@microsoft.graph.conflictBehavior":"rename","name":fname_od}}
    s_h = {'Authorization':f'Bearer {token_initial}','Content-Type':'application/json'}
    try:
        s_r = requests.post(cre_s_url,headers=s_h,json=s_pl,timeout=60); s_r.raise_for_status()
        ul_sess_url_od = s_r.json()['uploadUrl']; app.logger.info(f"STREAM [{job_id}]: OD session for '{fname_od}': {ul_sess_url_od[:70]}...")
    except requests.exceptions.RequestException as e:
        app.logger.error(f"STREAM [{job_id}]: OD session creation error for '{fname_od}': {e}")
        if hasattr(e,'response') and e.response: app.logger.error(f"STREAM [{job_id}]: API Resp: {e.response.status_code} - {e.response.text}")
        return False

    bytes_ul=0; MAX_RETRIES=3; RETRY_DELAY=10; DROPBOX_READ_CHUNK=1*1024*1024; CHUNK_UL_TIMEOUT=600
    r_db_dl=None
    try:
        h_db_dl = {'User-Agent':'Mozilla/5.0'}; r_db_dl = requests.get(url_mod,stream=True,allow_redirects=True,timeout=1800,headers=h_db_dl)
        r_db_dl.raise_for_status(); c_buf=b""; last_od_r=None
        for db_c_data in r_db_dl.iter_content(chunk_size=DROPBOX_READ_CHUNK):
            if not db_c_data: app.logger.info(f"STREAM [{job_id}]: End of DB stream for '{fname_od}'. Buffer size before final: {len(c_buf)}b."); break
            c_buf += db_c_data
            if len(c_buf) % (5 * 1024 * 1024) < DROPBOX_READ_CHUNK : # Log approx every 5MB accumulated
                 app.logger.debug(f"STREAM [{job_id}]: Accumulated to chunk_buffer. Current size: {len(c_buf)}b / {ONEDRIVE_CHUNK_SIZE}b target.")
            while len(c_buf) >= ONEDRIVE_CHUNK_SIZE:
                c_ul = c_buf[:ONEDRIVE_CHUNK_SIZE]
                app.logger.info(f"STREAM [{job_id}]: Preparing OD chunk. Buffer size: {len(c_buf)}b, Chunk to send: {len(c_ul)}b.")
                c_buf = c_buf[ONEDRIVE_CHUNK_SIZE:]
                s_b=bytes_ul; e_b=bytes_ul+len(c_ul)-1; retries=0; ul_ok=False
                while retries < MAX_RETRIES:
                    try:
                        perc=f" ({( (e_b+1)/fsize_db)*100:.2f}%)" if fsize_db else ""
                        app.logger.info(f"STREAM [{job_id}]: Uploading OD chunk (Try {retries+1}) {fname_od} bytes {s_b}-{e_b}/{fsize_db or '*'}{perc}")
                        c_h = {'Content-Length':str(len(c_ul)),'Content-Range':f'bytes {s_b}-{e_b}/{fsize_db or "*"}'}
                        last_od_r = requests.put(ul_sess_url_od,headers=c_h,data=c_ul,timeout=CHUNK_UL_TIMEOUT); last_od_r.raise_for_status()
                        app.logger.info(f"STREAM [{job_id}]: OD chunk {fname_od} {s_b}-{e_b} OK. Status: {last_od_r.status_code}")
                        bytes_ul+=len(c_ul); ul_ok=True
                        if last_od_r.status_code==201: app.logger.info(f"STREAM [{job_id}]: File '{fname_od}' streamed (201)."); return True
                        break
                    except requests.exceptions.RequestException as e:
                        retries+=1; app.logger.warning(f"STREAM [{job_id}]: OD chunk upload error {fname_od} (Try {retries}/{MAX_RETRIES}): {e}")
                        if hasattr(e,'response') and e.response:
                            app.logger.warning(f"STREAM [{job_id}]: API chunk resp: {e.response.status_code} - {e.response.text[:200]}")
                            if e.response.status_code in [400,401,403,404,409,410,416]: _try_cancel_upload_session_streaming(job_id,ul_sess_url_od,fname_od,"critical chunk err"); return False
                        if retries>=MAX_RETRIES: _try_cancel_upload_session_streaming(job_id,ul_sess_url_od,fname_od,"chunk failure"); return False
                        time.sleep(RETRY_DELAY * (2**(retries-1)))
                if not ul_ok: _try_cancel_upload_session_streaming(job_id,ul_sess_url_od,fname_od,"all chunk retries failed"); return False
        if len(c_buf) > 0:
            app.logger.info(f"STREAM [{job_id}]: Preparing LAST OD fragment. Remaining buffer size: {len(c_buf)}b.")
            s_b=bytes_ul; e_b=bytes_ul+len(c_buf)-1; retries=0; ul_ok=False
            while retries < MAX_RETRIES:
                try:
                    perc=f" ({( (e_b+1)/fsize_db)*100:.2f}%)" if fsize_db else ""
                    app.logger.info(f"STREAM [{job_id}]: Uploading LAST OD chunk (Try {retries+1}) {fname_od} {s_b}-{e_b}/{fsize_db or '*'}{perc}")
                    c_h = {'Content-Length':str(len(c_buf)),'Content-Range':f'bytes {s_b}-{e_b}/{fsize_db or "*"}'}
                    last_od_r = requests.put(ul_sess_url_od,headers=c_h,data=c_buf,timeout=CHUNK_UL_TIMEOUT); last_od_r.raise_for_status()
                    app.logger.info(f"STREAM [{job_id}]: LAST OD chunk {fname_od} OK. Status: {last_od_r.status_code}")
                    bytes_ul+=len(c_buf); ul_ok=True
                    if last_od_r.status_code==201: app.logger.info(f"STREAM [{job_id}]: File '{fname_od}' streamed (201 last chunk)."); return True
                    else:
                        app.logger.warning(f"STREAM [{job_id}]: Unexpected status {last_od_r.status_code} for last chunk {fname_od}. Uploaded:{bytes_ul}, Expected:{fsize_db}")
                        if fsize_db and bytes_ul==fsize_db: app.logger.info(f"STREAM [{job_id}]: Size matches, success for {fname_od}."); return True
                        elif not fsize_db and last_od_r.status_code in [200,202]: app.logger.info(f"STREAM [{job_id}]: Upload {fname_od} (unknown size) finished {last_od_r.status_code}. Success."); return True
                        _try_cancel_upload_session_streaming(job_id,ul_sess_url_od,fname_od,"uncertain last chunk status"); return False
                    break
                except requests.exceptions.RequestException as e:
                    retries+=1; app.logger.warning(f"STREAM [{job_id}]: LAST OD chunk upload error {fname_od} (Try {retries}): {e}")
                    if hasattr(e,'response') and e.response:
                        app.logger.warning(f"STREAM [{job_id}]: API LAST chunk resp: {e.response.status_code} - {e.response.text[:200]}")
                        if e.response.status_code in [400,401,403,404,409,410,416]: _try_cancel_upload_session_streaming(job_id,ul_sess_url_od,fname_od,"critical last chunk err"); return False
                    if retries>=MAX_RETRIES: _try_cancel_upload_session_streaming(job_id,ul_sess_url_od,fname_od,"last chunk failure"); return False
                    time.sleep(RETRY_DELAY * (2**(retries-1)))
            if not ul_ok: _try_cancel_upload_session_streaming(job_id,ul_sess_url_od,fname_od,"all last chunk retries failed"); return False
        if fsize_db:
            if bytes_ul==fsize_db: app.logger.info(f"STREAM [{job_id}]: Final check: {bytes_ul}/{fsize_db}b for '{fname_od}'. Success."); return True
            else: _try_cancel_upload_session_streaming(job_id,ul_sess_url_od,fname_od,"final size mismatch"); return False
        elif last_od_r and last_od_r.status_code==201: app.logger.info(f"STREAM [{job_id}]: Upload {fname_od} (unknown size) finished with 201. Success."); return True
        else: _try_cancel_upload_session_streaming(job_id,ul_sess_url_od,fname_od,"uncertain stream end"); return False
    except requests.exceptions.RequestException as e: app.logger.error(f"STREAM [{job_id}]: DB stream error {url_mod}: {e}"); _try_cancel_upload_session_streaming(job_id,ul_sess_url_od,fname_od,"DB stream error"); return False
    except Exception as e: app.logger.error(f"STREAM [{job_id}]: Global stream error {fname_od}: {e}",exc_info=True); _try_cancel_upload_session_streaming(job_id,ul_sess_url_od,fname_od,"global stream error"); return False
    finally:
        if r_db_dl:
            try: r_db_dl.close(); app.logger.info(f"STREAM [{job_id}]: DB download connection closed.")
            except Exception as e: app.logger.warning(f"STREAM [{job_id}]: Error closing DB connection: {e}")

def process_dropbox_link_worker(dropbox_url, subject_default, email_id_log):
    global PROCESSING_URLS, PROCESSING_URLS_LOCK, STREAMING_WORKER_SEMAPHORE # Required for global vars

    job_id_base = (re.sub(r'[^a-zA-Z0-9]','',email_id_log)[-12:] if email_id_log and email_id_log not in ['N/A','N/A_EMAIL_ID'] else "") or \
                  (re.sub(r'[^a-zA-Z0-9]','',dropbox_url)[-20:] if len(re.sub(r'[^a-zA-Z0-9]','',dropbox_url)) > 5 else "") or \
                  f"TS_{time.time_ns()}"[-12:]
    job_id = f"S-{job_id_base}"
    
    # Flag to track if this thread added the URL to PROCESSING_URLS (handled by API now)
    # Flag to track if semaphore was acquired by this thread
    semaphore_acquired_by_this_thread = False
    # The URL is added to PROCESSING_URLS by the API endpoint before this thread starts.
    # This worker is responsible for removing it from PROCESSING_URLS in the finally block.

    try:
        app.logger.info(f"WORKER [{job_id}]: Preparing for URL: '{dropbox_url}' (awaiting semaphore).")
        SEMAPHORE_TIMEOUT = 600 
        if not STREAMING_WORKER_SEMAPHORE.acquire(blocking=True, timeout=SEMAPHORE_TIMEOUT):
            app.logger.warning(f"WORKER [{job_id}]: Timeout ({SEMAPHORE_TIMEOUT}s) acquiring semaphore. Another transfer likely too long. Aborting for '{dropbox_url}'.")
            return # PROCESSING_URLS will be cleaned up in finally
        semaphore_acquired_by_this_thread = True
        app.logger.info(f"WORKER [{job_id}]: Semaphore acquired. STARTING processing for URL: '{dropbox_url}', Subject: '{subject_default}'")

        if not dropbox_url or not isinstance(dropbox_url, str) or not dropbox_url.lower().startswith("https://www.dropbox.com/"):
            app.logger.error(f"WORKER [{job_id}]: Invalid Dropbox URL: '{dropbox_url}'. Stopping."); return

        token = get_onedrive_access_token()
        if not token: app.logger.error(f"WORKER [{job_id}]: Failed to get Graph token. Stopping."); return
        
        folder_id = ensure_onedrive_folder(token)
        if not folder_id: app.logger.error(f"WORKER [{job_id}]: Failed to ensure OneDrive folder. Stopping."); return
        
        processed_persistent = get_processed_urls_from_onedrive(job_id, token, folder_id)
        unesc_url = html_parser.unescape(dropbox_url)
        if dropbox_url in processed_persistent or unesc_url in processed_persistent:
            app.logger.info(f"WORKER [{job_id}]: URL '{dropbox_url}' (or unescaped) already in persistent processed list. Ignoring."); return
            
        app.logger.info(f"WORKER [{job_id}]: URL '{dropbox_url}' is new (not in persistent list). Starting stream to OneDrive.")
        success = stream_dropbox_to_onedrive(job_id, dropbox_url, token, folder_id, subject_default)
        
        if success:
            app.logger.info(f"WORKER [{job_id}]: Stream of '{dropbox_url}' successful. Updating persistent processed list.")
            if not add_processed_url_to_onedrive(job_id, token, folder_id, dropbox_url):
                app.logger.error(f"WORKER [{job_id}]: CRITICAL - File '{dropbox_url}' streamed BUT FAILED to update {PROCESSED_URLS_ONEDRIVE_FILENAME}.")
        else: app.logger.error(f"WORKER [{job_id}]: Stream failed for '{dropbox_url}'.")
    
    finally:
        if semaphore_acquired_by_this_thread:
            STREAMING_WORKER_SEMAPHORE.release()
            app.logger.info(f"WORKER [{job_id}]: Semaphore released for URL '{dropbox_url}'.")
        
        # This worker is responsible for removing the URL from PROCESSING_URLS
        with PROCESSING_URLS_LOCK:
            if dropbox_url in PROCESSING_URLS: # Check again, as it might have been removed if API call was very quick
                PROCESSING_URLS.remove(dropbox_url)
                app.logger.info(f"WORKER [{job_id}]: URL '{dropbox_url}' removed from in-memory PROCESSING_URLS (current size: {len(PROCESSING_URLS)}).")
        app.logger.info(f"WORKER [{job_id}]: Task finished for URL '{dropbox_url}'.")

# --- (Rest of the Email Polling and Flask Endpoints as in the previous complete script) ---
# ... (mark_email_as_read, get_processed_webhook_trigger_ids, add_processed_webhook_trigger_id) ...
# ... (check_new_emails_and_trigger_make_webhook, background_email_poller) ...
# ... (api_process_individual_dropbox_link - this was already updated in previous complete script to handle PROCESSING_URLS addition) ...
# ... (trigger_local_workflow, check_local_workflow_trigger, api_ping, serve_trigger_page_main, __main__) ...

def mark_email_as_read(token, msg_id):
    if not token or not msg_id: app.logger.error("MARK_READ: Token/ID missing."); return False
    url = f"https://graph.microsoft.com/v1.0/me/messages/{msg_id}"; h={'Authorization':f'Bearer {token}','Content-Type':'application/json'}; p={"isRead":True}
    try: r=requests.patch(url,headers=h,json=p,timeout=15); r.raise_for_status(); app.logger.info(f"MARK_READ: Email {msg_id} marked read."); return True
    except requests.exceptions.RequestException as e: app.logger.error(f"MARK_READ: API error for {msg_id}: {e}"); return False

def get_processed_webhook_trigger_ids(token, folder_id):
    if not token or not folder_id: return set()
    url=f"https://graph.microsoft.com/v1.0/me/drive/items/{folder_id}:/{PROCESSED_WEBHOOK_TRIGGERS_ONEDRIVE_FILENAME}:/content"
    h={'Authorization':f'Bearer {token}'}; ids=set()
    app.logger.debug(f"DEDUP_WH: Reading {PROCESSED_WEBHOOK_TRIGGERS_ONEDRIVE_FILENAME}")
    try:
        r=requests.get(url,headers=h,timeout=30)
        if r.status_code==200: ids.update(l.strip() for l in r.text.splitlines() if l.strip()); app.logger.info(f"DEDUP_WH: Read {len(ids)} IDs.")
        elif r.status_code==404: app.logger.info(f"DEDUP_WH: {PROCESSED_WEBHOOK_TRIGGERS_ONEDRIVE_FILENAME} not found.")
        else: r.raise_for_status()
    except requests.exceptions.RequestException as e: app.logger.error(f"DEDUP_WH: DL error: {e}")
    return ids

def add_processed_webhook_trigger_id(token, folder_id, email_id):
    if not all([token,folder_id,email_id]): return False
    ids=get_processed_webhook_trigger_ids(token,folder_id); ids.add(email_id); content="\n".join(sorted(list(ids)))
    url=f"https://graph.microsoft.com/v1.0/me/drive/items/{folder_id}:/{PROCESSED_WEBHOOK_TRIGGERS_ONEDRIVE_FILENAME}:/content?@microsoft.graph.conflictBehavior=replace"
    h={'Authorization':f'Bearer {token}','Content-Type':'text/plain; charset=utf-8'}
    try: r=requests.put(url,headers=h,data=content.encode('utf-8'),timeout=60); r.raise_for_status(); app.logger.info(f"DEDUP_WH: {PROCESSED_WEBHOOK_TRIGGERS_ONEDRIVE_FILENAME} updated ({len(ids)} IDs)."); return True
    except requests.exceptions.RequestException as e: app.logger.error(f"DEDUP_WH: UL error: {e}"); return False

def check_new_emails_and_trigger_make_webhook():
    app.logger.info("POLLER: Checking new emails...")
    if not SENDER_LIST_FOR_POLLING: app.logger.warning("POLLER: SENDER_LIST_FOR_POLLING is empty."); return 0
    if not MAKE_SCENARIO_WEBHOOK_URL: app.logger.error("POLLER: MAKE_SCENARIO_WEBHOOK_URL not configured."); return 0
    token=get_onedrive_access_token()
    if not token: app.logger.error("POLLER: Failed to get Graph token."); return 0
    folder_id=ensure_onedrive_folder(token)
    if not folder_id: app.logger.error("POLLER: Failed to ensure OneDrive folder for dedup."); return 0
    processed_ids=get_processed_webhook_trigger_ids(token,folder_id); triggered=0
    try:
        since=(datetime.now(timezone.utc)-timedelta(days=1)).strftime('%Y-%m-%dT%H:%M:%SZ')
        filt=f"isRead eq false and receivedDateTime ge {since}"
        url=f"https://graph.microsoft.com/v1.0/me/mailFolders/inbox/messages?$filter={filt}&$select=id,subject,from,receivedDateTime,bodyPreview&$top=100&$orderby=receivedDateTime desc"
        app.logger.info(f"POLLER: Calling Graph Mail API (filter: '{filt}').")
        h_mail={'Authorization':f'Bearer {token}','Prefer':'outlook.body-content-type="text"'}
        r=requests.get(url,headers=h_mail,timeout=30); r.raise_for_status(); emails=r.json().get('value',[])
        app.logger.info(f"POLLER: {len(emails)} recent unread email(s) fetched (before sender filter).")
        rel_emails=[e for e in emails if e.get('from',{}).get('emailAddress',{}).get('address','').lower() in SENDER_LIST_FOR_POLLING]
        app.logger.info(f"POLLER: {len(rel_emails)} relevant email(s) after sender filter.")
        for mail in reversed(rel_emails):
            mail_id=mail['id']; subj=mail.get('subject','N/A')
            if mail_id in processed_ids: app.logger.debug(f"POLLER: Webhook already sent for email {mail_id}. Skipping."); continue
            app.logger.info(f"POLLER: Relevant email found (ID:{mail_id}, Subject:'{str(subj)[:50]}...'). Triggering Make webhook.")
            pl={"microsoft_graph_email_id":mail_id,"subject":subj,"receivedDateTime":mail.get("receivedDateTime"),
                "sender_address":mail.get('from',{}).get('emailAddress',{}).get('address','').lower(),"bodyPreview":mail.get('bodyPreview','')}
            try:
                wh_r=requests.post(MAKE_SCENARIO_WEBHOOK_URL,json=pl,timeout=20)
                if wh_r.status_code==200 and "accepted" in wh_r.text.lower():
                    app.logger.info(f"POLLER: Make webhook call successful for {mail_id}. Resp: {wh_r.status_code} - {wh_r.text}")
                    if add_processed_webhook_trigger_id(token,folder_id,mail_id):
                        triggered+=1
                        if not mark_email_as_read(token,mail_id): app.logger.warning(f"POLLER: Failed to mark {mail_id} as read, but webhook OK.")
                    else: app.logger.error(f"POLLER: Failed to add {mail_id} to processed triggers. Email NOT marked read.")
                else: app.logger.error(f"POLLER: Make webhook call error for {mail_id}. Status: {wh_r.status_code}, Resp: {wh_r.text[:200]}")
            except requests.exceptions.RequestException as e: app.logger.error(f"POLLER: Make webhook call exception for {mail_id}: {e}")
        return triggered
    except requests.exceptions.RequestException as e: app.logger.error(f"POLLER: Graph Mail API error: {e}"); return 0
    except Exception as e: app.logger.error(f"POLLER: Unexpected error: {e}",exc_info=True); return 0

def background_email_poller():
    app.logger.info(f"BG_POLLER: Starting email polling thread (TZ: {POLLING_TIMEZONE_STR}).")
    err_count=0; MAX_ERR=5
    while True:
        try:
            now=datetime.now(TZ_FOR_POLLING); hour=now.hour; wday=now.weekday()
            active_day = wday in POLLING_ACTIVE_DAYS; active_time = POLLING_ACTIVE_START_HOUR <= hour < POLLING_ACTIVE_END_HOUR
            log_dets = f"Day:{wday}[Act:{POLLING_ACTIVE_DAYS}],Hour:{hour:02d}h[{POLLING_ACTIVE_START_HOUR:02d}h-{POLLING_ACTIVE_END_HOUR:02d}h {POLLING_TIMEZONE_STR}]"
            if active_day and active_time:
                app.logger.info(f"BG_POLLER: In active period ({log_dets}). Starting poll cycle.")
                if not all([ONEDRIVE_CLIENT_ID,ONEDRIVE_CLIENT_SECRET,ONEDRIVE_REFRESH_TOKEN,SENDER_LIST_FOR_POLLING,MAKE_SCENARIO_WEBHOOK_URL]):
                    app.logger.warning("BG_POLLER: Incomplete config for polling. Waiting 60s."); time.sleep(60); continue
                triggered_n=check_new_emails_and_trigger_make_webhook()
                app.logger.info(f"BG_POLLER: Active poll cycle finished. {triggered_n} webhook(s) triggered.")
                err_count=0; sleep_t=EMAIL_POLLING_INTERVAL_SECONDS
            else: app.logger.info(f"BG_POLLER: Outside active period ({log_dets}). Sleeping."); sleep_t=POLLING_INACTIVE_CHECK_INTERVAL_SECONDS
            time.sleep(sleep_t)
        except Exception as e:
            err_count+=1; app.logger.error(f"BG_POLLER: Major unhandled error (count #{err_count}): {e}",exc_info=True)
            if err_count>=MAX_ERR: app.logger.critical(f"BG_POLLER: Too many consecutive errors ({MAX_ERR}). Stopping thread."); break
            time.sleep(max(60,EMAIL_POLLING_INTERVAL_SECONDS)*(2**err_count))

@app.route('/api/process_individual_dropbox_link', methods=['POST'])
def api_process_individual_dropbox_link():
    global PROCESSING_URLS, PROCESSING_URLS_LOCK
    
    api_token=request.headers.get('X-API-Token')
    if not EXPECTED_API_TOKEN: app.logger.error("API_PROC: PROCESS_API_TOKEN not configured."); return jsonify({"s":"err","m":"Server config error"}),500
    if api_token!=EXPECTED_API_TOKEN: app.logger.warning(f"API_PROC: Unauthorized access. Token: '{api_token}'."); return jsonify({"s":"err","m":"Unauthorized"}),401
    app.logger.info("API_PROC: API token validated.")
    
    try: data = request.get_json(silent=True) or (json.loads(request.data.decode('utf-8')) if request.data else None)
    except Exception as e: app.logger.error(f"API_PROC: JSON parsing error: {e}",exc_info=True); return jsonify({"s":"err","m":f"JSON format error: {e}"}),400
    app.logger.info(f"API_PROC: Received JSON data: {str(data)[:200]}{'...' if len(str(data))>200 else ''}")
    if not data or 'dropbox_url' not in data: app.logger.error(f"API_PROC: Invalid payload or missing 'dropbox_url'. Data: {data}"); return jsonify({"s":"err","m":"dropbox_url missing or invalid payload"}),400
    
    db_url=data.get('dropbox_url')
    if not isinstance(db_url,str) or not db_url.lower().startswith("https://www.dropbox.com/"):
        app.logger.error(f"API_PROC: Invalid Dropbox URL provided: '{db_url}'"); return jsonify({"s":"err","m":"Invalid Dropbox URL."}),400

    subj_fallback=data.get('email_subject','Fichier_Dropbox_Sujet_Absent'); mail_id_log=data.get('microsoft_graph_email_id','N/A_EMAIL_ID')
    
    with PROCESSING_URLS_LOCK:
        if db_url in PROCESSING_URLS:
            app.logger.info(f"API_PROC: URL '{db_url}' already in process/queue by this instance. Request ignored.")
            return jsonify({"s":"ignored_processing","m":"URL already in process/queue."}),200
        PROCESSING_URLS.add(db_url)
        app.logger.info(f"API_PROC: URL '{db_url}' added to PROCESSING_URLS (in-memory set, current size: {len(PROCESSING_URLS)}).")

    app.logger.info(f"API_PROC: Request for URL: {db_url} (Subject Fallback: {subj_fallback}, EmailID: {mail_id_log})")
    
    name_suf_base = (re.sub(r'[^a-zA-Z0-9]','',mail_id_log)[-15:] if mail_id_log and mail_id_log not in ['N/A','N/A_EMAIL_ID'] else "") or \
                    (re.sub(r'[^a-zA-Z0-9]','',db_url)[-20:] if len(re.sub(r'[^a-zA-Z0-9]','',db_url)) > 5 else "") or \
                    str(time.time_ns())[-10:]
    
    thread = threading.Thread(target=process_dropbox_link_worker,args=(db_url,subj_fallback,mail_id_log),name=f"StreamW-{name_suf_base}")
    thread.daemon=True; thread.start()
    app.logger.info(f"API_PROC: Stream task for {db_url} queued (Thread: {thread.name}).")
    return jsonify({"s":"accepted","m":"Stream request received and queued."}),202

@app.route('/api/trigger_local_workflow', methods=['POST'])
def trigger_local_workflow():
    pl=request.json or {"cmd":"start_local","ts":time.time()}
    try:
        with open(TRIGGER_SIGNAL_FILE,"w") as f: json.dump(pl,f)
        app.logger.info(f"LOCAL_API: Local signal set {TRIGGER_SIGNAL_FILE}. Payload: {pl}"); return jsonify({"s":"ok","m":"Signal set"}),200
    except Exception as e: app.logger.error(f"LOCAL_API: Error setting signal: {e}",exc_info=True); return jsonify({"s":"err","m":"Internal error setting signal"}),500

@app.route('/api/check_trigger', methods=['GET'])
def check_local_workflow_trigger():
    res={'cmd_pending':False,'payload':None}
    if TRIGGER_SIGNAL_FILE.exists():
        try:
            with open(TRIGGER_SIGNAL_FILE,'r') as f: pl=json.load(f)
            res['cmd_pending']=True; res['payload']=pl
            TRIGGER_SIGNAL_FILE.unlink(); app.logger.info(f"LOCAL_API: Signal read and deleted. Payload: {pl}")
        except Exception as e: app.logger.error(f"LOCAL_API: Error processing signal file {TRIGGER_SIGNAL_FILE}: {e}",exc_info=True)
    return jsonify(res)

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
    debug=os.environ.get('FLASK_DEBUG','False').lower()=='true'
    start_bg_threads = not debug or os.environ.get("WERKZEUG_RUN_MAIN")=="true"
    if start_bg_threads:
        if all([ONEDRIVE_CLIENT_ID,ONEDRIVE_CLIENT_SECRET,ONEDRIVE_REFRESH_TOKEN,SENDER_LIST_FOR_POLLING,MAKE_SCENARIO_WEBHOOK_URL]):
            email_th=threading.Thread(target=background_email_poller,name="EmailPollerThread"); email_th.daemon=True; email_th.start()
            app.logger.info(f"MAIN: Email polling thread started (Senders:{len(SENDER_LIST_FOR_POLLING)}, TZ:{POLLING_TIMEZONE_STR}).")
        else: app.logger.warning("MAIN: Email polling thread NOT started due to incomplete configuration.")
    port=int(os.environ.get('PORT',10000))
    if not EXPECTED_API_TOKEN: app.logger.critical("MAIN: SECURITY ALERT: PROCESS_API_TOKEN IS NOT SET.")
    app.logger.info(f"MAIN: Starting Flask server on port {port} with debug={debug}")
    app.run(host='0.0.0.0',port=port,debug=debug,use_reloader=(debug and os.environ.get("WERKZEUG_RUN_MAIN")!="true"))
