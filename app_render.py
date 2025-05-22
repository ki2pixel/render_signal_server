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
# from zoneinfo import ZoneInfo # Pour Python 3.9+ si gestion fuseaux horaires plus fine

from msal import ConfidentialClientApplication

app = Flask(__name__)

# Configuration du logging
log_level_str = os.environ.get('FLASK_LOG_LEVEL', 'INFO').upper()
log_level = getattr(logging, log_level_str, logging.INFO)
logging.basicConfig(level=log_level,
                    format='%(asctime)s - %(levelname)s - %(name)s - %(module)s - %(funcName)s - %(lineno)d - %(message)s')

# --- Configuration des Plages Horaires ---
POLLING_TIMEZONE_STR = os.environ.get("POLLING_TIMEZONE", "UTC")
POLLING_ACTIVE_START_HOUR = int(os.environ.get("POLLING_ACTIVE_START_HOUR", 0))
POLLING_ACTIVE_END_HOUR = int(os.environ.get("POLLING_ACTIVE_END_HOUR", 24))
POLLING_ACTIVE_DAYS_RAW = os.environ.get("POLLING_ACTIVE_DAYS", "0,1,2,3,4,5,6")
POLLING_ACTIVE_DAYS = []
if POLLING_ACTIVE_DAYS_RAW:
    try:
        POLLING_ACTIVE_DAYS = [int(day.strip()) for day in POLLING_ACTIVE_DAYS_RAW.split(',') if day.strip().isdigit() and 0 <= int(day.strip()) <= 6]
    except ValueError:
        app.logger.warning(f"CONFIGURATION POLLING: POLLING_ACTIVE_DAYS ('{POLLING_ACTIVE_DAYS_RAW}') mal formaté. Utilisation de tous les jours.")
        POLLING_ACTIVE_DAYS = list(range(7))
if not POLLING_ACTIVE_DAYS: POLLING_ACTIVE_DAYS = list(range(7))

TZ_FOR_POLLING = None
if POLLING_TIMEZONE_STR.upper() != "UTC":
    try:
        from zoneinfo import ZoneInfo
        TZ_FOR_POLLING = ZoneInfo(POLLING_TIMEZONE_STR)
        app.logger.info(f"CONFIGURATION POLLING: Utilisation du fuseau horaire '{POLLING_TIMEZONE_STR}' pour les plages actives.")
    except ImportError:
        app.logger.warning(f"CONFIGURATION POLLING: 'zoneinfo' non disponible. Utilisation d'UTC. '{POLLING_TIMEZONE_STR}' ignoré.")
        POLLING_TIMEZONE_STR = "UTC"
    except Exception as e_tz:
        app.logger.warning(f"CONFIGURATION POLLING: Erreur chargement fuseau horaire '{POLLING_TIMEZONE_STR}': {e_tz}. Utilisation d'UTC.")
        POLLING_TIMEZONE_STR = "UTC"
if POLLING_TIMEZONE_STR.upper() == "UTC" and TZ_FOR_POLLING is None:
    TZ_FOR_POLLING = timezone.utc
    app.logger.info(f"CONFIGURATION POLLING: Utilisation du fuseau horaire 'UTC' pour les plages actives.")

EMAIL_POLLING_INTERVAL_SECONDS = int(os.environ.get("EMAIL_POLLING_INTERVAL_SECONDS", 60))
POLLING_INACTIVE_CHECK_INTERVAL_SECONDS = int(os.environ.get("POLLING_INACTIVE_CHECK_INTERVAL_SECONDS", 300))

app.logger.info(f"CONFIGURATION POLLING: Intervalle emails plage active: {EMAIL_POLLING_INTERVAL_SECONDS}s.")
app.logger.info(f"CONFIGURATION POLLING: Plage active (fuseau '{POLLING_TIMEZONE_STR}'): {POLLING_ACTIVE_START_HOUR:02d}:00-{POLLING_ACTIVE_END_HOUR:02d}:00.")
app.logger.info(f"CONFIGURATION POLLING: Jours actifs (0=Lundi): {POLLING_ACTIVE_DAYS}")
app.logger.info(f"CONFIGURATION POLLING: Intervalle vérification hors plage: {POLLING_INACTIVE_CHECK_INTERVAL_SECONDS}s.")

# --- Constantes et Variables d'Environnement (autres) ---
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
SENDER_LIST_FOR_POLLING = []
if SENDER_OF_INTEREST_FOR_POLLING_RAW:
    SENDER_LIST_FOR_POLLING = [email.strip().lower() for email in SENDER_OF_INTEREST_FOR_POLLING_RAW.split(',') if email.strip()]
    app.logger.info(f"CONFIGURATION: Expéditeurs surveillés ({len(SENDER_LIST_FOR_POLLING)}): {SENDER_LIST_FOR_POLLING}")
else:
    app.logger.warning("CONFIGURATION: SENDER_OF_INTEREST_FOR_POLLING non défini.")

msal_app = None
if ONEDRIVE_CLIENT_ID and ONEDRIVE_CLIENT_SECRET:
    app.logger.info(f"CONFIGURATION: Initialisation MSAL avec Client ID '{ONEDRIVE_CLIENT_ID[:5]}...' et Authority: {ONEDRIVE_AUTHORITY}")
    msal_app = ConfidentialClientApplication(ONEDRIVE_CLIENT_ID, authority=ONEDRIVE_AUTHORITY, client_credential=ONEDRIVE_CLIENT_SECRET)
else:
    app.logger.warning("CONFIGURATION: ONEDRIVE_CLIENT_ID ou ONEDRIVE_CLIENT_SECRET manquant.")

EXPECTED_API_TOKEN = os.environ.get("PROCESS_API_TOKEN")
if not EXPECTED_API_TOKEN:
    app.logger.warning("CONFIGURATION: PROCESS_API_TOKEN non défini.")
app.logger.info(f"CONFIGURATION: Token attendu pour API: '{EXPECTED_API_TOKEN[:5]}...'")

# --- Verrou pour déduplication en mémoire des URLs en cours de traitement ---
PROCESSING_URLS_LOCK = threading.Lock()
PROCESSING_URLS = set()

# --- Fonctions Utilitaires ---
def sanitize_filename(filename_str, max_length=230):
    if filename_str is None:
        app.logger.warning("SANITIZE_FILENAME: filename_str None, utilisant nom par défaut.")
        filename_str = "fichier_nom_absent"
    sanitized_filename = str(filename_str)
    sanitized_filename = re.sub(r'[<>:"/\\|?*]', '_', sanitized_filename)
    sanitized_filename = re.sub(r'\.+', '.', sanitized_filename).strip('.')
    if not sanitized_filename:
        sanitized_filename = "fichier_sans_nom_valide"
    return sanitized_filename[:max_length]

def get_onedrive_access_token():
    if not msal_app: app.logger.error("MSAL_AUTH: MSAL non configuré."); return None
    if not ONEDRIVE_REFRESH_TOKEN: app.logger.error("MSAL_AUTH: REFRESH_TOKEN manquant."); return None
    app.logger.debug(f"MSAL_AUTH: Acquisition token Graph API pour scopes: {ONEDRIVE_SCOPES_DELEGATED}")
    result = msal_app.acquire_token_by_refresh_token(ONEDRIVE_REFRESH_TOKEN, scopes=ONEDRIVE_SCOPES_DELEGATED)
    if "access_token" in result:
        app.logger.info("MSAL_AUTH: Token d'accès Graph API obtenu.")
        if result.get("refresh_token") and result.get("refresh_token") != ONEDRIVE_REFRESH_TOKEN:
             app.logger.warning("MSAL_AUTH: Nouveau refresh token Graph API émis. Mettez à jour ONEDRIVE_REFRESH_TOKEN.")
        return result['access_token']
    else:
        app.logger.error(f"MSAL_AUTH: Erreur token: {result.get('error')} - {result.get('error_description')}")
        app.logger.error(f"MSAL_AUTH: Détails MSAL: {result}"); return None

def ensure_onedrive_folder(access_token, subfolder_name=None, parent_folder_id=None):
    target_subfolder_name = subfolder_name or ONEDRIVE_TARGET_SUBFOLDER_NAME
    target_parent_id = parent_folder_id or ONEDRIVE_TARGET_PARENT_FOLDER_ID
    headers = {'Authorization': 'Bearer ' + access_token, 'Content-Type': 'application/json'}
    effective_parent_id = target_parent_id if target_parent_id and target_parent_id.lower() != 'root' else 'root'
    subfolder_name_clean = sanitize_filename(target_subfolder_name, 100)
    base_url = "https://graph.microsoft.com/v1.0/me/drive"
    folder_check_url = f"{base_url}/{'items/'+effective_parent_id if effective_parent_id != 'root' else 'root'}/children?$filter=name eq '{subfolder_name_clean}'"
    folder_create_url = f"{base_url}/{'items/'+effective_parent_id if effective_parent_id != 'root' else 'root'}/children"
    try:
        response = requests.get(folder_check_url, headers=headers, timeout=15)
        response.raise_for_status(); children = response.json().get('value', [])
        if children: folder_id = children[0]['id']; app.logger.info(f"ONEDRIVE_UTIL: Dossier '{subfolder_name_clean}' trouvé ID: {folder_id}"); return folder_id
        else:
            app.logger.info(f"ONEDRIVE_UTIL: Dossier '{subfolder_name_clean}' non trouvé. Création.")
            payload = {"name": subfolder_name_clean, "folder": {}, "@microsoft.graph.conflictBehavior": "rename"}
            response_create = requests.post(folder_create_url, headers=headers, json=payload, timeout=15)
            response_create.raise_for_status(); folder_id = response_create.json()['id']
            app.logger.info(f"ONEDRIVE_UTIL: Dossier '{subfolder_name_clean}' créé ID: {folder_id}"); return folder_id
    except requests.exceptions.RequestException as e:
        app.logger.error(f"ONEDRIVE_UTIL: Erreur API Graph dossier '{subfolder_name_clean}': {e}")
        if hasattr(e, 'response') and e.response is not None: app.logger.error(f"ONEDRIVE_UTIL: Réponse API: {e.response.status_code} - {e.response.text}")
        return None

def get_processed_urls_from_onedrive(job_id, access_token, target_folder_id): # job_id ajouté
    if not access_token or not target_folder_id:
        app.logger.error(f"DROPBOX_WORKER_DEDUP [{job_id}]: Token ou ID dossier manquant pour get_processed_urls.")
        return set()
    download_url = f"https://graph.microsoft.com/v1.0/me/drive/items/{target_folder_id}:/{PROCESSED_URLS_ONEDRIVE_FILENAME}:/content"
    headers = {'Authorization': 'Bearer ' + access_token}
    processed_urls = set()
    app.logger.debug(f"DROPBOX_WORKER_DEDUP [{job_id}]: Lecture {PROCESSED_URLS_ONEDRIVE_FILENAME}.")
    try:
        response = requests.get(download_url, headers=headers, timeout=30)
        if response.status_code == 200:
            lines = response.text.splitlines()
            for line in lines:
                if line.strip(): processed_urls.add(line.strip())
            app.logger.info(f"DROPBOX_WORKER_DEDUP [{job_id}]: Lu {len(processed_urls)} URLs depuis {PROCESSED_URLS_ONEDRIVE_FILENAME}.")
        elif response.status_code == 404:
            app.logger.info(f"DROPBOX_WORKER_DEDUP [{job_id}]: {PROCESSED_URLS_ONEDRIVE_FILENAME} non trouvé.")
        else: response.raise_for_status()
    except requests.exceptions.RequestException as e:
        app.logger.error(f"DROPBOX_WORKER_DEDUP [{job_id}]: Erreur DL {PROCESSED_URLS_ONEDRIVE_FILENAME}: {e}")
    return processed_urls

def add_processed_url_to_onedrive(job_id, access_token, target_folder_id, dropbox_url_processed): # job_id ajouté
    if not access_token or not target_folder_id or not dropbox_url_processed:
        app.logger.error(f"DROPBOX_WORKER_DEDUP [{job_id}]: Paramètres manquants pour add_processed_url.")
        return False
    current_urls = get_processed_urls_from_onedrive(job_id, access_token, target_folder_id) # Appel avec job_id
    if dropbox_url_processed in current_urls:
        app.logger.info(f"DROPBOX_WORKER_DEDUP [{job_id}]: URL '{dropbox_url_processed}' déjà listée.")
        return True
    current_urls.add(dropbox_url_processed)
    content_to_upload = "\n".join(sorted(list(current_urls)))
    upload_url = f"https://graph.microsoft.com/v1.0/me/drive/items/{target_folder_id}:/{PROCESSED_URLS_ONEDRIVE_FILENAME}:/content?@microsoft.graph.conflictBehavior=replace"
    headers = {'Authorization': 'Bearer ' + access_token, 'Content-Type': 'text/plain; charset=utf-8'}
    app.logger.debug(f"DROPBOX_WORKER_DEDUP [{job_id}]: MàJ {PROCESSED_URLS_ONEDRIVE_FILENAME} ({len(current_urls)} URLs).")
    try:
        response = requests.put(upload_url, headers=headers, data=content_to_upload.encode('utf-8'), timeout=60)
        response.raise_for_status()
        app.logger.info(f"DROPBOX_WORKER_DEDUP [{job_id}]: {PROCESSED_URLS_ONEDRIVE_FILENAME} màj succès ({len(current_urls)} URLs).")
        return True
    except requests.exceptions.RequestException as e:
        app.logger.error(f"DROPBOX_WORKER_DEDUP [{job_id}]: Erreur UL {PROCESSED_URLS_ONEDRIVE_FILENAME}: {e}")
        if hasattr(e, 'response') and e.response is not None: app.logger.error(f"DROPBOX_WORKER_DEDUP [{job_id}]: Réponse API: {e.response.status_code} - {e.response.text}")
        return False

# --- Fonctions Streaming Dropbox -> OneDrive ---
def _try_cancel_upload_session_streaming(job_id, upload_session_url, filename_onedrive_clean, reason="erreur"):
    if not upload_session_url: return
    app.logger.info(f"STREAM_WORKER [{job_id}]: Annulation session upload ({reason}) pour {filename_onedrive_clean}: {upload_session_url[:70]}...")
    token_for_delete = get_onedrive_access_token()
    if token_for_delete:
        try:
            requests.delete(upload_session_url, headers={'Authorization': 'Bearer ' + token_for_delete}, timeout=10)
            app.logger.info(f"STREAM_WORKER [{job_id}]: Session upload {filename_onedrive_clean} annulée/expirée.")
        except requests.exceptions.RequestException as e_del:
            app.logger.warning(f"STREAM_WORKER [{job_id}]: Échec annulation session {filename_onedrive_clean}: {e_del}")
    else:
        app.logger.warning(f"STREAM_WORKER [{job_id}]: Pas de token pour annuler session {filename_onedrive_clean}.")

def stream_dropbox_to_onedrive(job_id, dropbox_url, access_token_graph_initial, target_folder_id_onedrive, subject_for_default_filename="FichierDropbox"):
    app.logger.info(f"STREAM_WORKER [{job_id}]: Démarrage streaming URL: {dropbox_url}")
    filename_for_onedrive = sanitize_filename(subject_for_default_filename if subject_for_default_filename else "FichierDropboxStream")
    file_size_dropbox = None
    upload_session_url_onedrive = None
    unescaped_url = html_parser.unescape(dropbox_url)
    modified_url = unescaped_url.replace("dl=0", "dl=1")
    modified_url = re.sub(r'dl=[^&?#]+', 'dl=1', modified_url)
    if '?dl=1' not in modified_url and '&dl=1' not in modified_url:
        modified_url += ("&" if "?" in modified_url else "?") + "dl=1"
    app.logger.info(f"STREAM_WORKER [{job_id}]: URL Dropbox pour stream: {modified_url}")
    try:
        headers_db_meta = {'User-Agent': 'Mozilla/5.0'}
        response_meta_db = requests.get(modified_url, stream=True, allow_redirects=True, timeout=60, headers=headers_db_meta)
        response_meta_db.raise_for_status()
        content_disp = response_meta_db.headers.get('content-disposition')
        if content_disp:
            app.logger.debug(f"STREAM_WORKER [{job_id}]: Content-Disposition Dropbox: '{content_disp}'")
            m_utf8 = re.search(r"filename\*=UTF-8''([^;\n\r]+)", content_disp, flags=re.IGNORECASE)
            extracted_name = None
            if m_utf8: extracted_name = requests.utils.unquote(m_utf8.group(1))
            else:
                m_simple = re.search(r'filename="([^"]+)"', content_disp, flags=re.IGNORECASE)
                if m_simple:
                    extracted_name = m_simple.group(1)
                    if '%' in extracted_name:
                        try: extracted_name = requests.utils.unquote(extracted_name)
                        except Exception: app.logger.warning(f"STREAM_WORKER [{job_id}]: Échec unquote: {extracted_name}")
            if extracted_name:
                filename_for_onedrive = sanitize_filename(extracted_name)
                app.logger.info(f"STREAM_WORKER [{job_id}]: Nom fichier Dropbox: '{filename_for_onedrive}'")
        if "dropbox.com/scl/fo/" in unescaped_url and not any(filename_for_onedrive.lower().endswith(ext) for ext in ['.zip', '.rar', '.7z']):
            filename_for_onedrive = os.path.splitext(filename_for_onedrive)[0] + ".zip"
            app.logger.info(f"STREAM_WORKER [{job_id}]: Lien dossier Dropbox, nom ajusté: '{filename_for_onedrive}'")
        total_length_dropbox_str = response_meta_db.headers.get('content-length')
        if total_length_dropbox_str and total_length_dropbox_str.isdigit():
            file_size_dropbox = int(total_length_dropbox_str)
            app.logger.info(f"STREAM_WORKER [{job_id}]: Fichier: '{filename_for_onedrive}', Taille: {file_size_dropbox} bytes.")
        else: app.logger.warning(f"STREAM_WORKER [{job_id}]: Taille fichier Dropbox inconnue pour '{filename_for_onedrive}'.")
        response_meta_db.close()
    except requests.exceptions.RequestException as e_meta:
        app.logger.error(f"STREAM_WORKER [{job_id}]: Erreur métadonnées Dropbox {modified_url}: {e_meta}")
        return False

    if not access_token_graph_initial or not target_folder_id_onedrive:
        app.logger.error(f"STREAM_WORKER [{job_id}]: Token initial ou ID dossier OneDrive manquant.")
        return False
    create_session_url = f"https://graph.microsoft.com/v1.0/me/drive/items/{target_folder_id_onedrive}:/{filename_for_onedrive}:/createUploadSession"
    session_payload = {"item": {"@microsoft.graph.conflictBehavior": "rename", "name": filename_for_onedrive}}
    session_headers = {'Authorization': 'Bearer ' + access_token_graph_initial, 'Content-Type': 'application/json'}
    try:
        session_response = requests.post(create_session_url, headers=session_headers, json=session_payload, timeout=60)
        session_response.raise_for_status()
        upload_session_data = session_response.json()
        upload_session_url_onedrive = upload_session_data['uploadUrl']
        app.logger.info(f"STREAM_WORKER [{job_id}]: Session upload OneDrive créée pour '{filename_for_onedrive}': {upload_session_url_onedrive[:70]}...")
    except requests.exceptions.RequestException as e_session:
        app.logger.error(f"STREAM_WORKER [{job_id}]: Erreur création session upload OneDrive '{filename_for_onedrive}': {e_session}")
        if hasattr(e_session, 'response') and e_session.response is not None: app.logger.error(f"STREAM_WORKER [{job_id}]: Réponse API: {e_session.response.status_code} - {e_session.response.text}")
        return False

    bytes_uploaded_total = 0
    MAX_CHUNK_RETRIES_ONEDRIVE = 3
    RETRY_DELAY_SECONDS_ONEDRIVE = 10
    ONEDRIVE_CHUNK_SIZE = 60 * 1024 * 1024
    DROPBOX_READ_CHUNK_SIZE = 1 * 1024 * 1024
    response_db_download = None
    try:
        headers_db_download = {'User-Agent': 'Mozilla/5.0'}
        response_db_download = requests.get(modified_url, stream=True, allow_redirects=True, timeout=1800, headers=headers_db_download)
        response_db_download.raise_for_status()
        chunk_buffer = b""
        last_onedrive_response = None
        for dropbox_chunk_data in response_db_download.iter_content(chunk_size=DROPBOX_READ_CHUNK_SIZE):
            if not dropbox_chunk_data: app.logger.info(f"STREAM_WORKER [{job_id}]: Fin stream Dropbox '{filename_for_onedrive}'."); break
            chunk_buffer += dropbox_chunk_data
            while len(chunk_buffer) >= ONEDRIVE_CHUNK_SIZE:
                chunk_to_upload_onedrive = chunk_buffer[:ONEDRIVE_CHUNK_SIZE]
                chunk_buffer = chunk_buffer[ONEDRIVE_CHUNK_SIZE:]
                start_byte = bytes_uploaded_total
                end_byte = bytes_uploaded_total + len(chunk_to_upload_onedrive) - 1
                current_retries = 0
                upload_successful_this_chunk = False
                while current_retries < MAX_CHUNK_RETRIES_ONEDRIVE:
                    try:
                        percentage_str = f" ({( (end_byte + 1) / file_size_dropbox) * 100:.2f}%)" if file_size_dropbox else ""
                        app.logger.info(f"STREAM_WORKER [{job_id}]: Upload chunk OneDrive (Try {current_retries+1}) {filename_for_onedrive} bytes {start_byte}-{end_byte}/{file_size_dropbox if file_size_dropbox else '*'}{percentage_str}")
                        chunk_headers_od = {
                            'Content-Length': str(len(chunk_to_upload_onedrive)),
                            'Content-Range': f'bytes {start_byte}-{end_byte}/{file_size_dropbox if file_size_dropbox else "*"}'
                        }
                        last_onedrive_response = requests.put(upload_session_url_onedrive, headers=chunk_headers_od, data=chunk_to_upload_onedrive, timeout=300)
                        last_onedrive_response.raise_for_status()
                        app.logger.info(f"STREAM_WORKER [{job_id}]: Chunk OneDrive {filename_for_onedrive} bytes {start_byte}-{end_byte} OK. Status: {last_onedrive_response.status_code}")
                        bytes_uploaded_total += len(chunk_to_upload_onedrive)
                        upload_successful_this_chunk = True
                        if last_onedrive_response.status_code == 201: app.logger.info(f"STREAM_WORKER [{job_id}]: Fichier '{filename_for_onedrive}' streamé (Statut 201)."); return True
                        break
                    except requests.exceptions.RequestException as e_chunk_od:
                        current_retries += 1
                        app.logger.warning(f"STREAM_WORKER [{job_id}]: Erreur upload chunk OneDrive {filename_for_onedrive} (Try {current_retries}/{MAX_CHUNK_RETRIES_ONEDRIVE}): {e_chunk_od}")
                        if hasattr(e_chunk_od, 'response') and e_chunk_od.response is not None:
                            app.logger.warning(f"STREAM_WORKER [{job_id}]: Réponse API chunk: {e_chunk_od.response.status_code} - {e_chunk_od.response.text[:200]}")
                            if e_chunk_od.response.status_code in [400,401,403,404,409,410,416]: _try_cancel_upload_session_streaming(job_id, upload_session_url_onedrive, filename_for_onedrive, "erreur critique chunk"); return False
                        if current_retries >= MAX_CHUNK_RETRIES_ONEDRIVE: _try_cancel_upload_session_streaming(job_id, upload_session_url_onedrive, filename_for_onedrive, "échec chunk"); return False
                        time.sleep(RETRY_DELAY_SECONDS_ONEDRIVE * (2**(current_retries-1)))
                if not upload_successful_this_chunk: _try_cancel_upload_session_streaming(job_id, upload_session_url_onedrive, filename_for_onedrive, "échec tous retries chunk"); return False
        if len(chunk_buffer) > 0:
            app.logger.info(f"STREAM_WORKER [{job_id}]: Upload dernier fragment {len(chunk_buffer)} bytes pour {filename_for_onedrive}")
            start_byte = bytes_uploaded_total
            end_byte = bytes_uploaded_total + len(chunk_buffer) - 1
            current_retries = 0
            upload_successful_this_chunk = False
            while current_retries < MAX_CHUNK_RETRIES_ONEDRIVE:
                try:
                    percentage_str = f" ({( (end_byte + 1) / file_size_dropbox) * 100:.2f}%)" if file_size_dropbox else ""
                    app.logger.info(f"STREAM_WORKER [{job_id}]: Upload DERNIER chunk (Try {current_retries+1}) {filename_for_onedrive} bytes {start_byte}-{end_byte}/{file_size_dropbox if file_size_dropbox else '*'}{percentage_str}")
                    chunk_headers_od = {
                        'Content-Length': str(len(chunk_buffer)),
                        'Content-Range': f'bytes {start_byte}-{end_byte}/{file_size_dropbox if file_size_dropbox else "*"}'
                    }
                    last_onedrive_response = requests.put(upload_session_url_onedrive, headers=chunk_headers_od, data=chunk_buffer, timeout=300)
                    last_onedrive_response.raise_for_status()
                    app.logger.info(f"STREAM_WORKER [{job_id}]: DERNIER Chunk {filename_for_onedrive} OK. Status: {last_onedrive_response.status_code}")
                    bytes_uploaded_total += len(chunk_buffer)
                    upload_successful_this_chunk = True
                    if last_onedrive_response.status_code == 201: app.logger.info(f"STREAM_WORKER [{job_id}]: Fichier '{filename_for_onedrive}' streamé (Statut 201 dernier chunk)."); return True
                    else:
                        app.logger.warning(f"STREAM_WORKER [{job_id}]: Statut inattendu {last_onedrive_response.status_code} dernier chunk {filename_for_onedrive}. Uploadé: {bytes_uploaded_total}, Attendu: {file_size_dropbox}")
                        if file_size_dropbox is not None and bytes_uploaded_total == file_size_dropbox: app.logger.info(f"STREAM_WORKER [{job_id}]: Taille OK, considérant succès {filename_for_onedrive}."); return True
                        elif file_size_dropbox is None and last_onedrive_response.status_code in [200, 202]: app.logger.info(f"STREAM_WORKER [{job_id}]: Upload {filename_for_onedrive} (taille inconnue) fini statut {last_onedrive_response.status_code}. Succès."); return True
                        _try_cancel_upload_session_streaming(job_id, upload_session_url_onedrive, filename_for_onedrive, "statut dernier chunk incertain"); return False
                    break
                except requests.exceptions.RequestException as e_chunk_od_last:
                    current_retries += 1
                    app.logger.warning(f"STREAM_WORKER [{job_id}]: Erreur upload DERNIER chunk {filename_for_onedrive} (Try {current_retries}): {e_chunk_od_last}")
                    if hasattr(e_chunk_od_last, 'response') and e_chunk_od_last.response is not None:
                        app.logger.warning(f"STREAM_WORKER [{job_id}]: Réponse API DERNIER chunk: {e_chunk_od_last.response.status_code} - {e_chunk_od_last.response.text[:200]}")
                        if e_chunk_od_last.response.status_code in [400,401,403,404,409,410,416]: _try_cancel_upload_session_streaming(job_id, upload_session_url_onedrive, filename_for_onedrive, "erreur critique dernier chunk"); return False
                    if current_retries >= MAX_CHUNK_RETRIES_ONEDRIVE: _try_cancel_upload_session_streaming(job_id, upload_session_url_onedrive, filename_for_onedrive, "échec dernier chunk"); return False
                    time.sleep(RETRY_DELAY_SECONDS_ONEDRIVE * (2**(current_retries-1)))
            if not upload_successful_this_chunk: _try_cancel_upload_session_streaming(job_id, upload_session_url_onedrive, filename_for_onedrive, "échec tous retries dernier chunk"); return False
        if file_size_dropbox is not None:
            if bytes_uploaded_total == file_size_dropbox: app.logger.info(f"STREAM_WORKER [{job_id}]: Vérif finale: {bytes_uploaded_total}/{file_size_dropbox} bytes pour '{filename_for_onedrive}'. Succès."); return True
            else: _try_cancel_upload_session_streaming(job_id, upload_session_url_onedrive, filename_for_onedrive, "incohérence taille finale"); return False
        elif last_onedrive_response and last_onedrive_response.status_code == 201: app.logger.info(f"STREAM_WORKER [{job_id}]: Upload {filename_for_onedrive} (taille inconnue) fini statut 201. Succès."); return True
        else: _try_cancel_upload_session_streaming(job_id, upload_session_url_onedrive, filename_for_onedrive, "fin stream incertaine"); return False
    except requests.exceptions.RequestException as e_download:
        app.logger.error(f"STREAM_WORKER [{job_id}]: Erreur stream Dropbox {modified_url}: {e_download}")
        if upload_session_url_onedrive: _try_cancel_upload_session_streaming(job_id, upload_session_url_onedrive, filename_for_onedrive, "erreur stream Dropbox")
        return False
    except Exception as e_global_stream:
        app.logger.error(f"STREAM_WORKER [{job_id}]: Erreur globale stream {filename_for_onedrive}: {e_global_stream}", exc_info=True)
        if upload_session_url_onedrive: _try_cancel_upload_session_streaming(job_id, upload_session_url_onedrive, filename_for_onedrive, "erreur globale stream")
        return False
    finally:
        if response_db_download:
            try: response_db_download.close(); app.logger.info(f"STREAM_WORKER [{job_id}]: Connexion Dropbox fermée.")
            except Exception as e_close: app.logger.warning(f"STREAM_WORKER [{job_id}]: Erreur fermeture connexion Dropbox: {e_close}")

def process_dropbox_link_worker(dropbox_url, subject_for_default_filename, email_id_for_logging):
    job_id_base = ""
    if email_id_for_logging and email_id_for_logging not in ['N/A', 'N/A_EMAIL_ID']:
        job_id_base = re.sub(r'[^a-zA-Z0-9]', '', email_id_for_logging)[-12:]
        if not job_id_base: job_id_base = f"TS_{time.time_ns()}"[-12:]
    else:
        sanitized_url_part = re.sub(r'[^a-zA-Z0-9]', '', dropbox_url)[-20:]
        job_id_base = sanitized_url_part if len(sanitized_url_part) > 5 else f"URL_TS_{time.time_ns()}"[-12:]
    job_id = f"S-{job_id_base}"
    app.logger.info(f"DROPBOX_WORKER_THREAD [{job_id}]: DÉMARRAGE (streaming) URL: '{dropbox_url}', Sujet: '{subject_for_default_filename}'")
    
    try: # Englobe tout le worker pour s'assurer que PROCESSING_URLS est nettoyé
        if not dropbox_url or not isinstance(dropbox_url, str) or not dropbox_url.lower().startswith("https://www.dropbox.com/"):
            app.logger.error(f"DROPBOX_WORKER_THREAD [{job_id}]: URL Dropbox invalide: '{dropbox_url}'. Arrêt.")
            return

        access_token_graph = get_onedrive_access_token()
        if not access_token_graph: app.logger.error(f"DROPBOX_WORKER_THREAD [{job_id}]: Échec token Graph. Arrêt."); return
        
        onedrive_target_folder_id = ensure_onedrive_folder(access_token_graph)
        if not onedrive_target_folder_id: app.logger.error(f"DROPBOX_WORKER_THREAD [{job_id}]: Échec dossier OneDrive. Arrêt."); return
        
        processed_urls = get_processed_urls_from_onedrive(job_id, access_token_graph, onedrive_target_folder_id) # Appel avec job_id
        unescaped_received_url = html_parser.unescape(dropbox_url)
        if dropbox_url in processed_urls or unescaped_received_url in processed_urls:
            app.logger.info(f"DROPBOX_WORKER_THREAD [{job_id}]: URL '{dropbox_url}' (ou unescaped) déjà traitée (fichier). Ignorée.")
            return
            
        app.logger.info(f"DROPBOX_WORKER_THREAD [{job_id}]: URL '{dropbox_url}' nouvelle. Lancement streaming.")
        success_transfer = stream_dropbox_to_onedrive(
            job_id, dropbox_url, access_token_graph, onedrive_target_folder_id, subject_for_default_filename
        )
        
        if success_transfer:
            app.logger.info(f"DROPBOX_WORKER_THREAD [{job_id}]: Streaming '{dropbox_url}' réussi. MàJ liste URLs.")
            if not add_processed_url_to_onedrive(job_id, access_token_graph, onedrive_target_folder_id, dropbox_url): # Appel avec job_id
                app.logger.error(f"DROPBOX_WORKER_THREAD [{job_id}]: CRITIQUE - Fichier '{dropbox_url}' streamé mais échec màj {PROCESSED_URLS_ONEDRIVE_FILENAME}.")
        else: app.logger.error(f"DROPBOX_WORKER_THREAD [{job_id}]: Échec streaming '{dropbox_url}'.")
    
    finally: # S'assure que l'URL est retirée de la liste des URLs en cours de traitement
        with PROCESSING_URLS_LOCK:
            # Utiliser l'URL originale non modifiée telle qu'elle a été ajoutée à PROCESSING_URLS
            # C'est dropbox_url qui a été passée en argument au worker et utilisée pour la déduplication en mémoire.
            original_url_key = dropbox_url 
            if original_url_key in PROCESSING_URLS:
                PROCESSING_URLS.remove(original_url_key)
                app.logger.info(f"DROPBOX_WORKER_THREAD [{job_id}]: URL '{original_url_key}' retirée de PROCESSING_URLS.")
            else:
                app.logger.warning(f"DROPBOX_WORKER_THREAD [{job_id}]: Tentative de retrait de URL '{original_url_key}' de PROCESSING_URLS, mais non trouvée.")
        app.logger.info(f"DROPBOX_WORKER_THREAD [{job_id}]: Fin tâche (streaming) pour '{dropbox_url}'")


# --- Fonctions Polling Email & Déclenchement Webhook ---
def mark_email_as_read(access_token, message_id):
    if not access_token or not message_id: app.logger.error("MARK_AS_READ: Token/ID manquant."); return False
    mark_as_read_url = f"https://graph.microsoft.com/v1.0/me/messages/{message_id}"
    headers = {'Authorization': 'Bearer ' + access_token, 'Content-Type': 'application/json'}
    payload = {"isRead": True}
    try:
        response = requests.patch(mark_as_read_url, headers=headers, json=payload, timeout=15)
        response.raise_for_status(); app.logger.info(f"MARK_AS_READ: Email ID {message_id} marqué lu."); return True
    except requests.exceptions.RequestException as e:
        app.logger.error(f"MARK_AS_READ: Erreur API Graph email ID {message_id}: {e}")
        if hasattr(e, 'response') and e.response is not None:
            app.logger.error(f"MARK_AS_READ: Réponse API Graph: {e.response.status_code} - {e.response.text}")
            if e.response.status_code == 403: app.logger.error("MARK_AS_READ: Erreur 403. Vérifiez permission Mail.ReadWrite.")
        return False
    except Exception as ex_general: app.logger.error(f"MARK_AS_READ: Erreur inattendue {message_id}: {ex_general}", exc_info=True); return False

def get_processed_webhook_trigger_ids(access_token, target_folder_id):
    if not access_token or not target_folder_id: return set()
    download_url = f"https://graph.microsoft.com/v1.0/me/drive/items/{target_folder_id}:/{PROCESSED_WEBHOOK_TRIGGERS_ONEDRIVE_FILENAME}:/content"
    headers = {'Authorization': 'Bearer ' + access_token}; ids = set()
    app.logger.debug(f"EMAIL_POLLER_DEDUP: Lecture {PROCESSED_WEBHOOK_TRIGGERS_ONEDRIVE_FILENAME}")
    try:
        response = requests.get(download_url, headers=headers, timeout=30)
        if response.status_code == 200:
            lines = response.text.splitlines()
            for line in lines:
                if line.strip(): ids.add(line.strip())
            app.logger.info(f"EMAIL_POLLER_DEDUP: Lu {len(ids)} IDs depuis {PROCESSED_WEBHOOK_TRIGGERS_ONEDRIVE_FILENAME}.")
        elif response.status_code == 404: app.logger.info(f"EMAIL_POLLER_DEDUP: {PROCESSED_WEBHOOK_TRIGGERS_ONEDRIVE_FILENAME} non trouvé.")
        else: response.raise_for_status()
    except requests.exceptions.RequestException as e: app.logger.error(f"EMAIL_POLLER_DEDUP: Erreur DL {PROCESSED_WEBHOOK_TRIGGERS_ONEDRIVE_FILENAME}: {e}")
    return ids

def add_processed_webhook_trigger_id(access_token, target_folder_id, email_id_processed):
    if not access_token or not target_folder_id or not email_id_processed: return False
    current_ids = get_processed_webhook_trigger_ids(access_token, target_folder_id)
    current_ids.add(email_id_processed)
    content_to_upload = "\n".join(sorted(list(current_ids)))
    upload_url = f"https://graph.microsoft.com/v1.0/me/drive/items/{target_folder_id}:/{PROCESSED_WEBHOOK_TRIGGERS_ONEDRIVE_FILENAME}:/content?@microsoft.graph.conflictBehavior=replace"
    headers = {'Authorization': 'Bearer ' + access_token, 'Content-Type': 'text/plain; charset=utf-8'}
    try:
        response = requests.put(upload_url, headers=headers, data=content_to_upload.encode('utf-8'), timeout=60)
        response.raise_for_status(); app.logger.info(f"EMAIL_POLLER_DEDUP: {PROCESSED_WEBHOOK_TRIGGERS_ONEDRIVE_FILENAME} màj ({len(current_ids)} IDs)."); return True
    except requests.exceptions.RequestException as e: app.logger.error(f"EMAIL_POLLER_DEDUP: Erreur UL {PROCESSED_WEBHOOK_TRIGGERS_ONEDRIVE_FILENAME}: {e}"); return False

def check_new_emails_and_trigger_make_webhook():
    app.logger.info("EMAIL_POLLER: Vérification nouveaux emails...")
    if not SENDER_LIST_FOR_POLLING: app.logger.warning("EMAIL_POLLER: SENDER_LIST_FOR_POLLING vide."); return 0
    if not MAKE_SCENARIO_WEBHOOK_URL: app.logger.error("EMAIL_POLLER: MAKE_SCENARIO_WEBHOOK_URL non configuré."); return 0
    access_token = get_onedrive_access_token()
    if not access_token: app.logger.error("EMAIL_POLLER: Échec token Graph pour polling."); return 0
    onedrive_processing_folder_id = ensure_onedrive_folder(access_token)
    if not onedrive_processing_folder_id: app.logger.error("EMAIL_POLLER: Erreur dossier OneDrive pour dédup."); return 0
    processed_trigger_ids = get_processed_webhook_trigger_ids(access_token, onedrive_processing_folder_id)
    triggered_count_this_run = 0
    try:
        since_datetime_for_graph = (datetime.now(timezone.utc) - timedelta(days=1))
        since_datetime_iso = since_datetime_for_graph.strftime('%Y-%m-%dT%H:%M:%SZ')
        filter_query = f"isRead eq false and receivedDateTime ge {since_datetime_iso}"
        messages_url = f"https://graph.microsoft.com/v1.0/me/mailFolders/inbox/messages?$filter={filter_query}&$select=id,subject,from,receivedDateTime,bodyPreview&$top=100&$orderby=receivedDateTime desc"
        app.logger.info(f"EMAIL_POLLER: Appel Graph API Mail (filtre: '{filter_query}').")
        headers_graph_mail = {'Authorization': 'Bearer ' + access_token, 'Prefer': 'outlook.body-content-type="text"'}
        response = requests.get(messages_url, headers=headers_graph_mail, timeout=30)
        response.raise_for_status(); emails_from_graph = response.json().get('value', [])
        app.logger.info(f"EMAIL_POLLER: {len(emails_from_graph)} email(s) non lus récents (avant filtre expéditeur).")
        relevant_emails = []
        if SENDER_LIST_FOR_POLLING:
            for email_data in emails_from_graph:
                email_sender_address = email_data.get('from', {}).get('emailAddress', {}).get('address', '').lower()
                if email_sender_address in SENDER_LIST_FOR_POLLING: relevant_emails.append(email_data)
                else: app.logger.debug(f"EMAIL_POLLER: Email ID {email_data['id']} de {email_sender_address} ignoré (pas dans SENDER_LIST).")
        else: app.logger.warning("EMAIL_POLLER: SENDER_LIST_FOR_POLLING vide, aucun email pertinent.")
        app.logger.info(f"EMAIL_POLLER: {len(relevant_emails)} email(s) pertinents après filtrage expéditeur.")
        for email_data in reversed(relevant_emails):
            email_id_graph = email_data['id']
            email_subject = email_data.get('subject', 'N/A')
            if email_id_graph in processed_trigger_ids: app.logger.debug(f"EMAIL_POLLER: Webhook déjà déclenché pour email ID {email_id_graph}. Ignoré."); continue
            app.logger.info(f"EMAIL_POLLER: Email pertinent ID: {email_id_graph}, Sujet: '{str(email_subject)[:50]}...'. Déclenchement webhook.")
            webhook_payload = {
                "microsoft_graph_email_id": email_id_graph, "subject": email_subject, 
                "receivedDateTime": email_data.get("receivedDateTime"),
                "sender_address": email_data.get('from', {}).get('emailAddress', {}).get('address', 'N/A').lower(),
                "bodyPreview": email_data.get('bodyPreview', '') 
            }
            try:
                webhook_response = requests.post(MAKE_SCENARIO_WEBHOOK_URL, json=webhook_payload, timeout=20)
                if webhook_response.status_code == 200 and "accepted" in webhook_response.text.lower():
                    app.logger.info(f"EMAIL_POLLER: Webhook Make OK pour {email_id_graph}. Réponse: {webhook_response.status_code} - {webhook_response.text}")
                    if add_processed_webhook_trigger_id(access_token, onedrive_processing_folder_id, email_id_graph):
                        triggered_count_this_run += 1
                        if mark_email_as_read(access_token, email_id_graph): app.logger.info(f"EMAIL_POLLER: Email ID {email_id_graph} marqué lu.")
                        else: app.logger.warning(f"EMAIL_POLLER: Échec marquage lu {email_id_graph}, mais webhook appelé et ID enregistré.")
                    else: app.logger.error(f"EMAIL_POLLER: Échec ajout {email_id_graph} à triggers traités. Email NON marqué lu.")
                else: app.logger.error(f"EMAIL_POLLER: Erreur webhook Make pour {email_id_graph}. Statut: {webhook_response.status_code}, Réponse: {webhook_response.text[:200]}")
            except requests.exceptions.RequestException as e_wh: app.logger.error(f"EMAIL_POLLER: Exception webhook Make pour {email_id_graph}: {e_wh}")
        return triggered_count_this_run
    except requests.exceptions.RequestException as e_graph:
        app.logger.error(f"EMAIL_POLLER: Erreur API Graph Mail: {e_graph}")
        if hasattr(e_graph, 'response') and e_graph.response is not None: app.logger.error(f"EMAIL_POLLER: Réponse API Graph Mail: {e_graph.response.status_code} - {e_graph.response.text}")
        return 0
    except Exception as e_main: app.logger.error(f"EMAIL_POLLER: Erreur inattendue: {e_main}", exc_info=True); return 0

# --- Thread Background Polling Email ---
def background_email_poller():
    app.logger.info(f"BACKGROUND_EMAIL_POLLER_THREAD: Démarrage (Fuseau: {POLLING_TIMEZONE_STR}).")
    consecutive_errors = 0
    MAX_CONSECUTIVE_ERRORS = 5
    while True:
        try:
            now_in_polling_tz = datetime.now(TZ_FOR_POLLING)
            is_active_day = now_in_polling_tz.weekday() in POLLING_ACTIVE_DAYS
            is_active_time = POLLING_ACTIVE_START_HOUR <= now_in_polling_tz.hour < POLLING_ACTIVE_END_HOUR
            log_details = f"Jour: {now_in_polling_tz.weekday()} [Actifs: {POLLING_ACTIVE_DAYS}], Heure: {now_in_polling_tz.hour:02d}h [Plage: {POLLING_ACTIVE_START_HOUR:02d}h-{POLLING_ACTIVE_END_HOUR:02d}h {POLLING_TIMEZONE_STR}]"
            if is_active_day and is_active_time:
                app.logger.info(f"BACKGROUND_EMAIL_POLLER_THREAD: Plage active ({log_details}). Cycle polling.")
                if not all([ONEDRIVE_CLIENT_ID, ONEDRIVE_CLIENT_SECRET, ONEDRIVE_REFRESH_TOKEN, SENDER_LIST_FOR_POLLING, MAKE_SCENARIO_WEBHOOK_URL]):
                    app.logger.warning("BACKGROUND_EMAIL_POLLER_THREAD: Config incomplète. Attente 60s."); time.sleep(60); continue
                num_triggered = check_new_emails_and_trigger_make_webhook()
                app.logger.info(f"BACKGROUND_EMAIL_POLLER_THREAD: Cycle polling actif fini. {num_triggered} webhook(s) déclenché(s).")
                consecutive_errors = 0; sleep_duration = EMAIL_POLLING_INTERVAL_SECONDS
            else:
                app.logger.info(f"BACKGROUND_EMAIL_POLLER_THREAD: Hors plage active ({log_details}). Veille."); sleep_duration = POLLING_INACTIVE_CHECK_INTERVAL_SECONDS
            time.sleep(sleep_duration)
        except Exception as e:
            consecutive_errors += 1
            app.logger.error(f"BACKGROUND_EMAIL_POLLER_THREAD: Erreur majeure (#{consecutive_errors}): {e}", exc_info=True)
            if consecutive_errors >= MAX_CONSECUTIVE_ERRORS: app.logger.critical(f"BACKGROUND_EMAIL_POLLER_THREAD: Trop d'erreurs ({MAX_CONSECUTIVE_ERRORS}). Arrêt."); break
            time.sleep(EMAIL_POLLING_INTERVAL_SECONDS * (2 ** consecutive_errors))

# --- Endpoints Flask ---
@app.route('/api/process_individual_dropbox_link', methods=['POST'])
def api_process_individual_dropbox_link():
    received_token = request.headers.get('X-API-Token')
    if not EXPECTED_API_TOKEN: app.logger.error("API_DROPBOX_PROCESS: PROCESS_API_TOKEN non configuré."); return jsonify({"status": "error", "message": "Erreur config serveur"}), 500
    if received_token != EXPECTED_API_TOKEN: app.logger.warning(f"API_DROPBOX_PROCESS: Accès non autorisé. Token: '{received_token}'."); return jsonify({"status": "error", "message": "Non autorisé"}), 401
    app.logger.info("API_DROPBOX_PROCESS: Token API validé.")
    data = None
    try:
        data = request.get_json(silent=True)
        if data is None and request.data:
            try: data = json.loads(request.data.decode('utf-8'))
            except Exception as e_parse: app.logger.error(f"API_DROPBOX_PROCESS: Échec parsing manuel: {e_parse}"); raise
        app.logger.info(f"API_DROPBOX_PROCESS: Données JSON: {str(data)[:500]}{'...' if len(str(data)) > 500 else ''}")
    except Exception as e: app.logger.error(f"API_DROPBOX_PROCESS: Erreur parsing JSON: {e}", exc_info=True); return jsonify({"status": "error", "message": f"Erreur JSON: {str(e)}"}), 400
    if not data or 'dropbox_url' not in data: app.logger.error(f"API_DROPBOX_PROCESS: Payload invalide. 'data': {data}"); return jsonify({"status": "error", "message": "dropbox_url manquante ou payload invalide"}), 400
    
    dropbox_url_to_process = data.get('dropbox_url')
    email_subject_from_make = data.get('email_subject')
    email_subject_for_filename = email_subject_from_make if email_subject_from_make is not None else 'Fichier_Dropbox_Sujet_Absent'
    email_id_for_logging = data.get('microsoft_graph_email_id', 'N/A_EMAIL_ID')
    
    # Déduplication en mémoire pour éviter de lancer plusieurs threads pour la même URL simultanément
    with PROCESSING_URLS_LOCK:
        # Utiliser l'URL telle que reçue pour la clé de déduplication en mémoire
        if dropbox_url_to_process in PROCESSING_URLS:
            app.logger.info(f"API_DROPBOX_PROCESS: URL '{dropbox_url_to_process}' déjà en cours de traitement par un autre thread. Ignorée.")
            return jsonify({"status": "ignored", "message": "URL déjà en cours de traitement."}), 200 # 200 pour ne pas que Make retente forcément
        PROCESSING_URLS.add(dropbox_url_to_process)
        app.logger.info(f"API_DROPBOX_PROCESS: URL '{dropbox_url_to_process}' ajoutée à PROCESSING_URLS.")

    app.logger.info(f"API_DROPBOX_PROCESS: Demande reçue URL: {dropbox_url_to_process} (Sujet: {email_subject_for_filename}, EmailID: {email_id_for_logging})")
    thread_name_suffix = (re.sub(r'[^a-zA-Z0-9]', '', email_id_for_logging)[-15:] if email_id_for_logging and email_id_for_logging not in ['N/A', 'N/A_EMAIL_ID'] else str(time.time_ns())[-10:]) or str(time.time_ns())[-10:]
    thread = threading.Thread(target=process_dropbox_link_worker, args=(dropbox_url_to_process, email_subject_for_filename, email_id_for_logging), name=f"StreamWorker-{thread_name_suffix}")
    thread.daemon = True; thread.start()
    app.logger.info(f"API_DROPBOX_PROCESS: Tâche streaming pour {dropbox_url_to_process} mise en file (thread: {thread.name}).")
    return jsonify({"status": "accepted", "message": "Demande de traitement (streaming) reçue."}), 202

@app.route('/api/trigger_local_workflow', methods=['POST'])
def trigger_local_workflow():
    command_payload = request.json or {"command": "start_local_process", "timestamp": time.time()}
    try:
        with open(TRIGGER_SIGNAL_FILE, "w") as f: json.dump(command_payload, f)
        app.logger.info(f"LOCAL_TRIGGER_API: Signal local posé {TRIGGER_SIGNAL_FILE}. Payload: {command_payload}"); return jsonify({"status": "success", "message": "Signal posé"}), 200
    except Exception as e: app.logger.error(f"LOCAL_TRIGGER_API: Erreur pose signal: {e}", exc_info=True); return jsonify({"status": "error", "message": "Erreur interne pose signal"}), 500

@app.route('/api/check_trigger', methods=['GET'])
def check_local_workflow_trigger():
    response_data = {'command_pending': False, 'payload': None}
    if TRIGGER_SIGNAL_FILE.exists():
        try:
            with open(TRIGGER_SIGNAL_FILE, 'r') as f: payload = json.load(f)
            response_data['command_pending'] = True; response_data['payload'] = payload
            TRIGGER_SIGNAL_FILE.unlink(); app.logger.info(f"LOCAL_TRIGGER_API: Signal lu et supprimé. P: {payload}")
        except Exception as e: app.logger.error(f"LOCAL_TRIGGER_API: Erreur traitement signal {TRIGGER_SIGNAL_FILE} : {e}", exc_info=True)
    return jsonify(response_data)

@app.route('/api/ping', methods=['GET', 'HEAD'])
def api_ping():
    ip_address = request.headers.get('X-Forwarded-For', request.remote_addr)
    user_agent = request.headers.get('User-Agent', 'N/A')
    app.logger.info(f"PING_API: Keep-Alive /api/ping IP: {ip_address}, UA: {user_agent} at {datetime.now(timezone.utc).isoformat()}")
    response = jsonify({"status": "pong", "timestamp": time.time()})
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"; response.headers["Pragma"] = "no-cache"; response.headers["Expires"] = "0"
    return response, 200

@app.route('/')
def serve_trigger_page_main():
    app.logger.info("ROOT_ROUTE: '/' appelée. Tentative servir 'trigger_page.html'.")
    try: return send_from_directory(app.root_path, 'trigger_page.html')
    except FileNotFoundError: app.logger.error(f"ROOT_ROUTE: ERREUR: trigger_page.html non trouvé dans {app.root_path}."); return "Erreur: Page non trouvée.", 404
    except Exception as e_send: app.logger.error(f"ROOT_ROUTE: Erreur send_from_directory: {e_send}", exc_info=True); return "Erreur interne serveur (UI).", 500

if __name__ == '__main__':
    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    start_background_threads = not debug_mode or os.environ.get("WERKZEUG_RUN_MAIN") == "true"
    if start_background_threads:
        if all([ONEDRIVE_CLIENT_ID, ONEDRIVE_CLIENT_SECRET, ONEDRIVE_REFRESH_TOKEN, SENDER_LIST_FOR_POLLING, MAKE_SCENARIO_WEBHOOK_URL]):
            email_poll_thread = threading.Thread(target=background_email_poller, name="EmailPollerThread"); email_poll_thread.daemon = True; email_poll_thread.start()
            app.logger.info(f"MAIN_APP: Thread polling emails démarré (expéditeurs: {len(SENDER_LIST_FOR_POLLING)}, fuseau: {POLLING_TIMEZONE_STR}).")
        else: app.logger.warning("MAIN_APP: Thread polling emails NON démarré (config incomplète).")
    port = int(os.environ.get('PORT', 10000))
    if not EXPECTED_API_TOKEN: app.logger.critical("MAIN_APP: ALERTE SÉCURITÉ: PROCESS_API_TOKEN NON DÉFINI.")
    app.logger.info(f"MAIN_APP: Démarrage serveur Flask port {port} debug={debug_mode}")
    app.run(host='0.0.0.0', port=port, debug=debug_mode, use_reloader=(debug_mode and os.environ.get("WERKZEUG_RUN_MAIN") != "true"))
