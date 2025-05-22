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
# from zoneinfo import ZoneInfo

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
        app.logger.warning(f"CFG POLL: POLLING_ACTIVE_DAYS ('{POLLING_ACTIVE_DAYS_RAW}') invalide. Tous jours.")
        POLLING_ACTIVE_DAYS = list(range(7))
if not POLLING_ACTIVE_DAYS: POLLING_ACTIVE_DAYS = list(range(7))

TZ_FOR_POLLING = None
if POLLING_TIMEZONE_STR.upper() != "UTC":
    try:
        from zoneinfo import ZoneInfo
        TZ_FOR_POLLING = ZoneInfo(POLLING_TIMEZONE_STR)
        app.logger.info(f"CFG POLL: Fuseau horaire '{POLLING_TIMEZONE_STR}' pour plages actives.")
    except ImportError:
        app.logger.warning(f"CFG POLL: 'zoneinfo' non dispo. UTC utilisé. '{POLLING_TIMEZONE_STR}' ignoré.")
        POLLING_TIMEZONE_STR = "UTC"
    except Exception as e_tz:
        app.logger.warning(f"CFG POLL: Erreur fuseau '{POLLING_TIMEZONE_STR}': {e_tz}. UTC utilisé.")
        POLLING_TIMEZONE_STR = "UTC"
if POLLING_TIMEZONE_STR.upper() == "UTC" and TZ_FOR_POLLING is None:
    TZ_FOR_POLLING = timezone.utc
    app.logger.info(f"CFG POLL: Fuseau horaire 'UTC' pour plages actives.")

EMAIL_POLLING_INTERVAL_SECONDS = int(os.environ.get("EMAIL_POLLING_INTERVAL_SECONDS", 120)) # Réduire pour tests, augmenter en prod (ex: 300)
POLLING_INACTIVE_CHECK_INTERVAL_SECONDS = int(os.environ.get("POLLING_INACTIVE_CHECK_INTERVAL_SECONDS", 300))

app.logger.info(f"CFG POLL: Intervalle emails actif: {EMAIL_POLLING_INTERVAL_SECONDS}s.")
app.logger.info(f"CFG POLL: Plage active ({POLLING_TIMEZONE_STR}): {POLLING_ACTIVE_START_HOUR:02d}:00-{POLLING_ACTIVE_END_HOUR:02d}:00. Jours: {POLLING_ACTIVE_DAYS}")
app.logger.info(f"CFG POLL: Intervalle vérification inactif: {POLLING_INACTIVE_CHECK_INTERVAL_SECONDS}s.")

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
    app.logger.info(f"CFG: Expéditeurs polling ({len(SENDER_LIST_FOR_POLLING)}): {SENDER_LIST_FOR_POLLING}")
else:
    app.logger.warning("CFG: SENDER_OF_INTEREST_FOR_POLLING non défini.")

msal_app = None
if ONEDRIVE_CLIENT_ID and ONEDRIVE_CLIENT_SECRET:
    app.logger.info(f"CFG: MSAL init ClientID '{ONEDRIVE_CLIENT_ID[:5]}...', Authority: {ONEDRIVE_AUTHORITY}")
    msal_app = ConfidentialClientApplication(ONEDRIVE_CLIENT_ID, authority=ONEDRIVE_AUTHORITY, client_credential=ONEDRIVE_CLIENT_SECRET)
else:
    app.logger.warning("CFG: ONEDRIVE_CLIENT_ID ou SECRET manquant. Graph désactivé.")

EXPECTED_API_TOKEN = os.environ.get("PROCESS_API_TOKEN")
if not EXPECTED_API_TOKEN:
    app.logger.warning("CFG: PROCESS_API_TOKEN non défini. API non sécurisée.")
app.logger.info(f"CFG: Token API attendu: '{EXPECTED_API_TOKEN[:5]}...'")

# --- Verrous et Sémaphores pour la gestion des workers ---
PROCESSING_URLS_LOCK = threading.Lock() # Pour protéger l'accès à PROCESSING_URLS
PROCESSING_URLS = set() # URLs actuellement en cours de traitement ou en attente par un worker de CETTE instance
STREAMING_WORKER_SEMAPHORE = threading.Semaphore(1) # Limite à 1 worker de streaming ACTIF à la fois

# --- Fonctions Utilitaires ---
def sanitize_filename(filename_str, max_length=230):
    if filename_str is None: filename_str = "fichier_nom_absent"
    s = str(filename_str); s = re.sub(r'[<>:"/\\|?*]', '_', s); s = re.sub(r'\.+', '.', s).strip('.')
    return s[:max_length] if s else "fichier_sans_nom_valide"

def get_onedrive_access_token():
    if not msal_app: app.logger.error("MSAL: Non configuré."); return None
    if not ONEDRIVE_REFRESH_TOKEN: app.logger.error("MSAL: REFRESH_TOKEN manquant."); return None
    res = msal_app.acquire_token_by_refresh_token(ONEDRIVE_REFRESH_TOKEN, scopes=ONEDRIVE_SCOPES_DELEGATED)
    if "access_token" in res:
        app.logger.info("MSAL: Token d'accès Graph API obtenu.")
        if res.get("refresh_token") and res.get("refresh_token") != ONEDRIVE_REFRESH_TOKEN:
             app.logger.warning("MSAL: Nouveau refresh token émis. MàJ var ONEDRIVE_REFRESH_TOKEN.")
        return res['access_token']
    app.logger.error(f"MSAL: Erreur token: {res.get('error')} - {res.get('error_description')}. Détails: {res}"); return None

def ensure_onedrive_folder(access_token, subfolder_name=None, parent_folder_id=None):
    name = subfolder_name or ONEDRIVE_TARGET_SUBFOLDER_NAME; p_id = parent_folder_id or ONEDRIVE_TARGET_PARENT_FOLDER_ID
    headers = {'Authorization': 'Bearer ' + access_token, 'Content-Type': 'application/json'}
    eff_p_id = p_id if p_id and p_id.lower() != 'root' else 'root'; name_clean = sanitize_filename(name, 100)
    base = "https://graph.microsoft.com/v1.0/me/drive"; c_url = f"{base}/{'items/'+eff_p_id if eff_p_id!='root' else 'root'}/children"
    chk_url = f"{c_url}?$filter=name eq '{name_clean}'"
    try:
        r = requests.get(chk_url, headers=headers, timeout=15); r.raise_for_status()
        children = r.json().get('value', [])
        if children: app.logger.info(f"OD_UTIL: Dossier '{name_clean}' trouvé ID: {children[0]['id']}"); return children[0]['id']
        app.logger.info(f"OD_UTIL: Dossier '{name_clean}' non trouvé. Création.")
        pl = {"name": name_clean, "folder": {}, "@microsoft.graph.conflictBehavior": "rename"}
        rc = requests.post(c_url, headers=headers, json=pl, timeout=15); rc.raise_for_status()
        app.logger.info(f"OD_UTIL: Dossier '{name_clean}' créé ID: {rc.json()['id']}"); return rc.json()['id']
    except requests.exceptions.RequestException as e:
        app.logger.error(f"OD_UTIL: Erreur API Graph dossier '{name_clean}': {e}")
        if hasattr(e, 'response') and e.response: app.logger.error(f"OD_UTIL: API Réponse: {e.response.status_code} - {e.response.text}")
        return None

def get_processed_urls_from_onedrive(job_id, access_token, target_folder_id):
    if not access_token or not target_folder_id: app.logger.error(f"DEDUP [{job_id}]: Token/ID dossier manquant."); return set()
    dl_url = f"https://graph.microsoft.com/v1.0/me/drive/items/{target_folder_id}:/{PROCESSED_URLS_ONEDRIVE_FILENAME}:/content"
    headers = {'Authorization': 'Bearer ' + access_token}; urls = set()
    app.logger.debug(f"DEDUP [{job_id}]: Lecture {PROCESSED_URLS_ONEDRIVE_FILENAME}.")
    try:
        r = requests.get(dl_url, headers=headers, timeout=30)
        if r.status_code == 200: urls.update(l.strip() for l in r.text.splitlines() if l.strip()); app.logger.info(f"DEDUP [{job_id}]: Lu {len(urls)} URLs.")
        elif r.status_code == 404: app.logger.info(f"DEDUP [{job_id}]: {PROCESSED_URLS_ONEDRIVE_FILENAME} non trouvé.")
        else: r.raise_for_status()
    except requests.exceptions.RequestException as e: app.logger.error(f"DEDUP [{job_id}]: Erreur DL {PROCESSED_URLS_ONEDRIVE_FILENAME}: {e}")
    return urls

def add_processed_url_to_onedrive(job_id, access_token, target_folder_id, url_processed):
    if not all([access_token, target_folder_id, url_processed]): app.logger.error(f"DEDUP [{job_id}]: Paramètres manquants."); return False
    urls = get_processed_urls_from_onedrive(job_id, access_token, target_folder_id)
    if url_processed in urls: app.logger.info(f"DEDUP [{job_id}]: URL '{url_processed}' déjà listée."); return True
    urls.add(url_processed); content = "\n".join(sorted(list(urls)))
    ul_url = f"https://graph.microsoft.com/v1.0/me/drive/items/{target_folder_id}:/{PROCESSED_URLS_ONEDRIVE_FILENAME}:/content?@microsoft.graph.conflictBehavior=replace"
    headers = {'Authorization': 'Bearer ' + access_token, 'Content-Type': 'text/plain; charset=utf-8'}
    app.logger.debug(f"DEDUP [{job_id}]: MàJ {PROCESSED_URLS_ONEDRIVE_FILENAME} ({len(urls)} URLs).")
    try:
        r = requests.put(ul_url, headers=headers, data=content.encode('utf-8'), timeout=60); r.raise_for_status()
        app.logger.info(f"DEDUP [{job_id}]: {PROCESSED_URLS_ONEDRIVE_FILENAME} màj succès ({len(urls)} URLs)."); return True
    except requests.exceptions.RequestException as e:
        app.logger.error(f"DEDUP [{job_id}]: Erreur UL {PROCESSED_URLS_ONEDRIVE_FILENAME}: {e}")
        if hasattr(e, 'response') and e.response: app.logger.error(f"DEDUP [{job_id}]: API Réponse: {e.response.status_code} - {e.response.text}")
        return False

# --- Fonctions Streaming Dropbox -> OneDrive ---
def _try_cancel_upload_session_streaming(job_id, upload_session_url, filename_clean, reason="erreur"):
    if not upload_session_url: return
    app.logger.info(f"STREAM [{job_id}]: Annulation session ({reason}) {filename_clean}: {upload_session_url[:70]}...")
    token = get_onedrive_access_token()
    if token:
        try: requests.delete(upload_session_url, headers={'Authorization': 'Bearer ' + token}, timeout=10); app.logger.info(f"STREAM [{job_id}]: Session {filename_clean} annulée/expirée.")
        except requests.exceptions.RequestException as e: app.logger.warning(f"STREAM [{job_id}]: Échec annulation session {filename_clean}: {e}")
    else: app.logger.warning(f"STREAM [{job_id}]: Pas de token pour annuler session {filename_clean}.")

def stream_dropbox_to_onedrive(job_id, dropbox_url, access_token_initial, target_folder_id, subject_default="FichierDropbox"):
    app.logger.info(f"STREAM [{job_id}]: Démarrage URL: {dropbox_url}")
    fname = sanitize_filename(subject_default or "FichierDropboxStream")
    fsize_db = None; upload_url_od = None
    url_unesc = html_parser.unescape(dropbox_url); url_mod = url_unesc.replace("dl=0", "dl=1")
    url_mod = re.sub(r'dl=[^&?#]+', 'dl=1', url_mod)
    if '?dl=1' not in url_mod and '&dl=1' not in url_mod: url_mod += ("&" if "?" in url_mod else "?") + "dl=1"
    app.logger.info(f"STREAM [{job_id}]: URL Dropbox stream: {url_mod}")
    try: # Get Dropbox metadata
        h_db_meta = {'User-Agent': 'Mozilla/5.0'}; r_meta_db = requests.get(url_mod, stream=True, allow_redirects=True, timeout=60, headers=h_db_meta)
        r_meta_db.raise_for_status()
        cd = r_meta_db.headers.get('content-disposition')
        if cd:
            m_utf8 = re.search(r"filename\*=UTF-8''([^;\n\r]+)", cd, re.I); ext_name = None
            if m_utf8: ext_name = requests.utils.unquote(m_utf8.group(1))
            else:
                m_simple = re.search(r'filename="([^"]+)"', cd, re.I)
                if m_simple: ext_name = m_simple.group(1);
                if '%' in ext_name:
                    try: ext_name = requests.utils.unquote(ext_name)
                    except: app.logger.warning(f"STREAM [{job_id}]: Échec unquote: {ext_name}")
            if ext_name: fname = sanitize_filename(ext_name); app.logger.info(f"STREAM [{job_id}]: Nom fichier DB: '{fname}'")
        if "dropbox.com/scl/fo/" in url_unesc and not any(fname.lower().endswith(e) for e in ['.zip','.rar','.7z']):
            fname = os.path.splitext(fname)[0] + ".zip"; app.logger.info(f"STREAM [{job_id}]: Lien dossier DB, nom ajusté: '{fname}'")
        len_str = r_meta_db.headers.get('content-length')
        if len_str and len_str.isdigit(): fsize_db = int(len_str); app.logger.info(f"STREAM [{job_id}]: Fichier: '{fname}', Taille: {fsize_db}b.")
        else: app.logger.warning(f"STREAM [{job_id}]: Taille fichier DB inconnue pour '{fname}'.")
        r_meta_db.close()
    except requests.exceptions.RequestException as e: app.logger.error(f"STREAM [{job_id}]: Erreur méta DB {url_mod}: {e}"); return False

    if not access_token_initial or not target_folder_id: app.logger.error(f"STREAM [{job_id}]: Token/ID dossier OD manquant."); return False
    # ONEDRIVE_CHUNK_SIZE à définir globalement ou passer en argument. Pour l'instant, hardcodé comme avant.
    ONEDRIVE_CHUNK_SIZE = int(os.environ.get("ONEDRIVE_CHUNK_SIZE_MB", 240)) * 1024 * 1024 # Default 60MB
    if ONEDRIVE_CHUNK_SIZE % (320 * 1024) != 0: # Ensure multiple of 320 KiB
        ONEDRIVE_CHUNK_SIZE = ((ONEDRIVE_CHUNK_SIZE // (320*1024)) +1) * (320*1024)
        app.logger.warning(f"STREAM [{job_id}]: ONEDRIVE_CHUNK_SIZE ajusté à {ONEDRIVE_CHUNK_SIZE // (1024*1024)}MB pour être multiple de 320KiB.")
    else:
        app.logger.info(f"STREAM [{job_id}]: ONEDRIVE_CHUNK_SIZE utilisé: {ONEDRIVE_CHUNK_SIZE // (1024*1024)}MB.")


    create_s_url = f"https://graph.microsoft.com/v1.0/me/drive/items/{target_folder_id}:/{fname}:/createUploadSession"
    s_pl = {"item": {"@microsoft.graph.conflictBehavior": "rename", "name": fname}}
    s_h = {'Authorization': 'Bearer ' + access_token_initial, 'Content-Type': 'application/json'}
    try: # Create OneDrive upload session
        s_r = requests.post(create_s_url, headers=s_h, json=s_pl, timeout=60); s_r.raise_for_status()
        upload_url_od = s_r.json()['uploadUrl']; app.logger.info(f"STREAM [{job_id}]: Session OD créée '{fname}': {upload_url_od[:70]}...")
    except requests.exceptions.RequestException as e:
        app.logger.error(f"STREAM [{job_id}]: Erreur création session OD '{fname}': {e}")
        if hasattr(e, 'response') and e.response: app.logger.error(f"STREAM [{job_id}]: API Réponse: {e.response.status_code} - {e.response.text}")
        return False

    bytes_ul = 0; MAX_RETRIES = 3; RETRY_DELAY = 10; DROPBOX_READ_CHUNK = 1 * 1024 * 1024
    r_db_dl = None
    try: # Stream data
        h_db_dl = {'User-Agent': 'Mozilla/5.0'}; r_db_dl = requests.get(url_mod, stream=True, allow_redirects=True, timeout=1800, headers=h_db_dl)
        r_db_dl.raise_for_status(); c_buf = b""; last_od_r = None
        for db_c_data in r_db_dl.iter_content(chunk_size=DROPBOX_READ_CHUNK):
            if not db_c_data: app.logger.info(f"STREAM [{job_id}]: Fin stream DB '{fname}'."); break
            c_buf += db_c_data
            while len(c_buf) >= ONEDRIVE_CHUNK_SIZE:
                c_ul_od = c_buf[:ONEDRIVE_CHUNK_SIZE]; c_buf = c_buf[ONEDRIVE_CHUNK_SIZE:]
                s_byte = bytes_ul; e_byte = bytes_ul + len(c_ul_od) - 1; retries = 0; ul_ok = False
                while retries < MAX_RETRIES:
                    try:
                        perc = f" ({( (e_byte + 1) / fsize_db) * 100:.2f}%)" if fsize_db else ""
                        app.logger.info(f"STREAM [{job_id}]: Upload chunk OD (Try {retries+1}) {fname} {s_byte}-{e_byte}/{fsize_db or '*'}{perc}")
                        c_h_od = {'Content-Length': str(len(c_ul_od)), 'Content-Range': f'bytes {s_byte}-{e_byte}/{fsize_db or "*"}'}
                        last_od_r = requests.put(upload_url_od, headers=c_h_od, data=c_ul_od, timeout=600); last_od_r.raise_for_status() # Increased timeout
                        app.logger.info(f"STREAM [{job_id}]: Chunk OD {fname} {s_byte}-{e_byte} OK. Status: {last_od_r.status_code}")
                        bytes_ul += len(c_ul_od); ul_ok = True
                        if last_od_r.status_code == 201: app.logger.info(f"STREAM [{job_id}]: Fichier '{fname}' streamé (201)."); return True
                        break
                    except requests.exceptions.RequestException as e:
                        retries += 1; app.logger.warning(f"STREAM [{job_id}]: Erreur UL chunk OD {fname} (Try {retries}/{MAX_RETRIES}): {e}")
                        if hasattr(e, 'response') and e.response:
                            app.logger.warning(f"STREAM [{job_id}]: API Réponse chunk: {e.response.status_code} - {e.response.text[:200]}")
                            if e.response.status_code in [400,401,403,404,409,410,416]: _try_cancel_upload_session_streaming(job_id, upload_url_od, fname, "err critique chunk"); return False
                        if retries >= MAX_RETRIES: _try_cancel_upload_session_streaming(job_id, upload_url_od, fname, "échec chunk"); return False
                        time.sleep(RETRY_DELAY * (2**(retries-1)))
                if not ul_ok: _try_cancel_upload_session_streaming(job_id, upload_url_od, fname, "échec tous retries chunk"); return False
        if len(c_buf) > 0: # Last fragment
            app.logger.info(f"STREAM [{job_id}]: Upload dernier fragment {len(c_buf)}b {fname}")
            s_byte = bytes_ul; e_byte = bytes_ul + len(c_buf) - 1; retries = 0; ul_ok = False
            while retries < MAX_RETRIES:
                try:
                    perc = f" ({( (e_byte + 1) / fsize_db) * 100:.2f}%)" if fsize_db else ""
                    app.logger.info(f"STREAM [{job_id}]: Upload DERNIER chunk (Try {retries+1}) {fname} {s_byte}-{e_byte}/{fsize_db or '*'}{perc}")
                    c_h_od = {'Content-Length': str(len(c_buf)), 'Content-Range': f'bytes {s_byte}-{e_byte}/{fsize_db or "*"}'}
                    last_od_r = requests.put(upload_url_od, headers=c_h_od, data=c_buf, timeout=600); last_od_r.raise_for_status() # Increased timeout
                    app.logger.info(f"STREAM [{job_id}]: DERNIER Chunk {fname} OK. Status: {last_od_r.status_code}")
                    bytes_ul += len(c_buf); ul_ok = True
                    if last_od_r.status_code == 201: app.logger.info(f"STREAM [{job_id}]: Fichier '{fname}' streamé (201 dernier chunk)."); return True
                    else:
                        app.logger.warning(f"STREAM [{job_id}]: Statut inattendu {last_od_r.status_code} dernier chunk {fname}. UL:{bytes_ul}, Att:{fsize_db}")
                        if fsize_db and bytes_ul == fsize_db: app.logger.info(f"STREAM [{job_id}]: Taille OK, succès {fname}."); return True
                        elif not fsize_db and last_od_r.status_code in [200,202]: app.logger.info(f"STREAM [{job_id}]: UL {fname} (taille inconnue) fini {last_od_r.status_code}. Succès."); return True
                        _try_cancel_upload_session_streaming(job_id, upload_url_od, fname, "statut dernier chunk incertain"); return False
                    break
                except requests.exceptions.RequestException as e:
                    retries += 1; app.logger.warning(f"STREAM [{job_id}]: Erreur UL DERNIER chunk {fname} (Try {retries}): {e}")
                    if hasattr(e, 'response') and e.response:
                        app.logger.warning(f"STREAM [{job_id}]: API Réponse DERNIER chunk: {e.response.status_code} - {e.response.text[:200]}")
                        if e.response.status_code in [400,401,403,404,409,410,416]: _try_cancel_upload_session_streaming(job_id, upload_url_od, fname, "err critique dernier chunk"); return False
                    if retries >= MAX_RETRIES: _try_cancel_upload_session_streaming(job_id, upload_url_od, fname, "échec dernier chunk"); return False
                    time.sleep(RETRY_DELAY * (2**(retries-1)))
            if not ul_ok: _try_cancel_upload_session_streaming(job_id, upload_url_od, fname, "échec tous retries dernier chunk"); return False
        if fsize_db:
            if bytes_ul == fsize_db: app.logger.info(f"STREAM [{job_id}]: Vérif finale: {bytes_ul}/{fsize_db}b '{fname}'. Succès."); return True
            else: _try_cancel_upload_session_streaming(job_id, upload_url_od, fname, "incohérence taille"); return False
        elif last_od_r and last_od_r.status_code == 201: app.logger.info(f"STREAM [{job_id}]: UL {fname} (taille inconnue) fini 201. Succès."); return True
        else: _try_cancel_upload_session_streaming(job_id, upload_url_od, fname, "fin stream incertaine"); return False
    except requests.exceptions.RequestException as e: app.logger.error(f"STREAM [{job_id}]: Erreur stream DB {url_mod}: {e}"); _try_cancel_upload_session_streaming(job_id, upload_url_od, fname, "erreur stream DB"); return False
    except Exception as e: app.logger.error(f"STREAM [{job_id}]: Erreur globale stream {fname}: {e}", exc_info=True); _try_cancel_upload_session_streaming(job_id, upload_url_od, fname, "erreur globale stream"); return False
    finally:
        if r_db_dl:
            try: r_db_dl.close(); app.logger.info(f"STREAM [{job_id}]: Connexion DB fermée.")
            except Exception as e: app.logger.warning(f"STREAM [{job_id}]: Erreur fermeture connexion DB: {e}")

def process_dropbox_link_worker(dropbox_url, subject_for_default_filename, email_id_for_logging):
    global PROCESSING_URLS, PROCESSING_URLS_LOCK, STREAMING_WORKER_SEMAPHORE

    job_id_base = (re.sub(r'[^a-zA-Z0-9]', '', email_id_for_logging)[-12:] if email_id_for_logging and email_id_for_logging not in ['N/A', 'N/A_EMAIL_ID'] else "") or \
                  (re.sub(r'[^a-zA-Z0-9]', '', dropbox_url)[-20:] if len(re.sub(r'[^a-zA-Z0-9]', '', dropbox_url)) > 5 else f"URL_TS_{time.time_ns()}"[-12:])
    if not job_id_base: job_id_base = f"TS_{time.time_ns()}"[-12:] # Fallback si tout est vide
    job_id = f"S-{job_id_base}"
    
    # Note: L'ajout à PROCESSING_URLS est maintenant dans l'API caller.
    # Ici, on se concentre sur l'acquisition du sémaphore et le travail.
    
    acquired_semaphore = False
    try:
        app.logger.info(f"WORKER [{job_id}]: Tentative démarrage pour URL: '{dropbox_url}' (attente sémaphore).")
        # Timeout pour l'acquisition du sémaphore (ex: 5 minutes)
        if not STREAMING_WORKER_SEMAPHORE.acquire(blocking=True, timeout=300):
            app.logger.warning(f"WORKER [{job_id}]: Timeout attente sémaphore. Autre transfert trop long. Abandon pour '{dropbox_url}'.")
            return # L'URL sera retirée de PROCESSING_URLS par le finally de ce thread
        acquired_semaphore = True
        app.logger.info(f"WORKER [{job_id}]: Sémaphore acquis. DÉMARRAGE EFFECTIF (streaming) URL: '{dropbox_url}', Sujet: '{subject_for_default_filename}'")

        if not dropbox_url or not isinstance(dropbox_url, str) or not dropbox_url.lower().startswith("https://www.dropbox.com/"):
            app.logger.error(f"WORKER [{job_id}]: URL Dropbox invalide: '{dropbox_url}'. Arrêt.")
            return

        access_token_graph = get_onedrive_access_token()
        if not access_token_graph: app.logger.error(f"WORKER [{job_id}]: Échec token Graph. Arrêt."); return
        
        onedrive_target_folder_id = ensure_onedrive_folder(access_token_graph)
        if not onedrive_target_folder_id: app.logger.error(f"WORKER [{job_id}]: Échec dossier OD. Arrêt."); return
        
        # Déduplication persistante (fichier)
        processed_urls_persistent = get_processed_urls_from_onedrive(job_id, access_token_graph, onedrive_target_folder_id)
        unescaped_url = html_parser.unescape(dropbox_url)
        if dropbox_url in processed_urls_persistent or unescaped_url in processed_urls_persistent:
            app.logger.info(f"WORKER [{job_id}]: URL '{dropbox_url}' (ou unescaped) déjà traitée (fichier persistant). Ignorée.")
            return
            
        app.logger.info(f"WORKER [{job_id}]: URL '{dropbox_url}' nouvelle (non trouvée dans fichier persistant). Lancement streaming.")
        success_transfer = stream_dropbox_to_onedrive(
            job_id, dropbox_url, access_token_graph, onedrive_target_folder_id, subject_for_default_filename
        )
        
        if success_transfer:
            app.logger.info(f"WORKER [{job_id}]: Streaming '{dropbox_url}' réussi. MàJ liste URLs persistante.")
            if not add_processed_url_to_onedrive(job_id, access_token_graph, onedrive_target_folder_id, dropbox_url):
                app.logger.error(f"WORKER [{job_id}]: CRITIQUE - Fichier '{dropbox_url}' streamé mais échec màj {PROCESSED_URLS_ONEDRIVE_FILENAME}.")
        else: app.logger.error(f"WORKER [{job_id}]: Échec streaming '{dropbox_url}'.")
    
    finally:
        if acquired_semaphore:
            STREAMING_WORKER_SEMAPHORE.release()
            app.logger.info(f"WORKER [{job_id}]: Sémaphore relâché pour '{dropbox_url}'.")
        
        # Retirer l'URL de la liste des URLs en cours de traitement (déduplication en mémoire)
        with PROCESSING_URLS_LOCK:
            # Utiliser l'URL originale telle qu'elle a été ajoutée dans l'API
            original_url_key = dropbox_url 
            if original_url_key in PROCESSING_URLS:
                PROCESSING_URLS.remove(original_url_key)
                app.logger.info(f"WORKER [{job_id}]: URL '{original_url_key}' retirée de PROCESSING_URLS (taille: {len(PROCESSING_URLS)}).")
            # else: # Peut arriver si le worker a été lancé mais a échoué très tôt avant même d'ajouter, ou si l'API a rejeté
            #     app.logger.debug(f"WORKER [{job_id}]: Tentative de retrait URL '{original_url_key}' de PROCESSING_URLS, mais non trouvée.")
        app.logger.info(f"WORKER [{job_id}]: Fin tâche pour '{dropbox_url}'.")


# --- Fonctions Polling Email & Déclenchement Webhook ---
def mark_email_as_read(access_token, message_id):
    if not access_token or not message_id: app.logger.error("MARK_READ: Token/ID manquant."); return False
    url = f"https://graph.microsoft.com/v1.0/me/messages/{message_id}"; h = {'Authorization':f'Bearer {access_token}','Content-Type':'application/json'}; p = {"isRead":True}
    try: r = requests.patch(url, headers=h, json=p, timeout=15); r.raise_for_status(); app.logger.info(f"MARK_READ: Email {message_id} marqué lu."); return True
    except requests.exceptions.RequestException as e:
        app.logger.error(f"MARK_READ: Erreur API {message_id}: {e}")
        if hasattr(e,'response') and e.response: app.logger.error(f"MARK_READ: API Réponse: {e.response.status_code} - {e.response.text}")
        return False
    except Exception as e: app.logger.error(f"MARK_READ: Erreur {message_id}: {e}",exc_info=True); return False

def get_processed_webhook_trigger_ids(access_token, target_folder_id):
    if not access_token or not target_folder_id: return set()
    dl_url = f"https://graph.microsoft.com/v1.0/me/drive/items/{target_folder_id}:/{PROCESSED_WEBHOOK_TRIGGERS_ONEDRIVE_FILENAME}:/content"
    h = {'Authorization':f'Bearer {access_token}'}; ids=set()
    app.logger.debug(f"DEDUP_WH: Lecture {PROCESSED_WEBHOOK_TRIGGERS_ONEDRIVE_FILENAME}")
    try:
        r = requests.get(dl_url, headers=h, timeout=30)
        if r.status_code == 200: ids.update(l.strip() for l in r.text.splitlines() if l.strip()); app.logger.info(f"DEDUP_WH: Lu {len(ids)} IDs.")
        elif r.status_code == 404: app.logger.info(f"DEDUP_WH: {PROCESSED_WEBHOOK_TRIGGERS_ONEDRIVE_FILENAME} non trouvé.")
        else: r.raise_for_status()
    except requests.exceptions.RequestException as e: app.logger.error(f"DEDUP_WH: Erreur DL: {e}")
    return ids

def add_processed_webhook_trigger_id(access_token, target_folder_id, email_id):
    if not all([access_token, target_folder_id, email_id]): return False
    ids = get_processed_webhook_trigger_ids(access_token, target_folder_id); ids.add(email_id)
    content = "\n".join(sorted(list(ids)))
    ul_url = f"https://graph.microsoft.com/v1.0/me/drive/items/{target_folder_id}:/{PROCESSED_WEBHOOK_TRIGGERS_ONEDRIVE_FILENAME}:/content?@microsoft.graph.conflictBehavior=replace"
    h = {'Authorization':f'Bearer {access_token}','Content-Type':'text/plain; charset=utf-8'}
    try: r = requests.put(ul_url, headers=h, data=content.encode('utf-8'), timeout=60); r.raise_for_status(); app.logger.info(f"DEDUP_WH: {PROCESSED_WEBHOOK_TRIGGERS_ONEDRIVE_FILENAME} màj ({len(ids)} IDs)."); return True
    except requests.exceptions.RequestException as e: app.logger.error(f"DEDUP_WH: Erreur UL: {e}"); return False

def check_new_emails_and_trigger_make_webhook():
    app.logger.info("POLLER: Vérification emails...")
    if not SENDER_LIST_FOR_POLLING: app.logger.warning("POLLER: SENDER_LIST vide."); return 0
    if not MAKE_SCENARIO_WEBHOOK_URL: app.logger.error("POLLER: MAKE_SCENARIO_WEBHOOK_URL non cfg."); return 0
    token = get_onedrive_access_token()
    if not token: app.logger.error("POLLER: Échec token Graph."); return 0
    folder_id = ensure_onedrive_folder(token)
    if not folder_id: app.logger.error("POLLER: Erreur dossier OD dédup."); return 0
    processed_ids = get_processed_webhook_trigger_ids(token, folder_id); triggered = 0
    try:
        since = (datetime.now(timezone.utc) - timedelta(days=1)).strftime('%Y-%m-%dT%H:%M:%SZ')
        f_q = f"isRead eq false and receivedDateTime ge {since}"
        url = f"https://graph.microsoft.com/v1.0/me/mailFolders/inbox/messages?$filter={f_q}&$select=id,subject,from,receivedDateTime,bodyPreview&$top=100&$orderby=receivedDateTime desc"
        app.logger.info(f"POLLER: Appel Graph Mail (filtre: '{f_q}').")
        h_mail = {'Authorization':f'Bearer {token}','Prefer':'outlook.body-content-type="text"'}
        r = requests.get(url, headers=h_mail, timeout=30); r.raise_for_status(); emails = r.json().get('value',[])
        app.logger.info(f"POLLER: {len(emails)} email(s) non lus récents (avant filtre).")
        rel_emails = [e for e in emails if e.get('from',{}).get('emailAddress',{}).get('address','').lower() in SENDER_LIST_FOR_POLLING]
        app.logger.info(f"POLLER: {len(rel_emails)} email(s) pertinents.")
        for mail_data in reversed(rel_emails):
            mail_id = mail_data['id']; subj = mail_data.get('subject','N/A')
            if mail_id in processed_ids: app.logger.debug(f"POLLER: Webhook déjà pour {mail_id}. Ignoré."); continue
            app.logger.info(f"POLLER: Email pertinent {mail_id}, Sujet: '{str(subj)[:50]}...'. Déclenchement webhook.")
            pl = {"microsoft_graph_email_id":mail_id, "subject":subj, "receivedDateTime":mail_data.get("receivedDateTime"),
                  "sender_address":mail_data.get('from',{}).get('emailAddress',{}).get('address','').lower(), "bodyPreview":mail_data.get('bodyPreview','')}
            try:
                wh_r = requests.post(MAKE_SCENARIO_WEBHOOK_URL, json=pl, timeout=20)
                if wh_r.status_code == 200 and "accepted" in wh_r.text.lower():
                    app.logger.info(f"POLLER: Webhook Make OK {mail_id}. R: {wh_r.status_code} - {wh_r.text}")
                    if add_processed_webhook_trigger_id(token, folder_id, mail_id):
                        triggered += 1
                        if not mark_email_as_read(token, mail_id): app.logger.warning(f"POLLER: Échec marquage lu {mail_id}, mais WH ok.")
                    else: app.logger.error(f"POLLER: Échec ajout {mail_id} à triggers traités. Non marqué lu.")
                else: app.logger.error(f"POLLER: Erreur WH Make {mail_id}. S: {wh_r.status_code}, R: {wh_r.text[:200]}")
            except requests.exceptions.RequestException as e: app.logger.error(f"POLLER: Excep WH Make {mail_id}: {e}")
        return triggered
    except requests.exceptions.RequestException as e:
        app.logger.error(f"POLLER: Erreur API Graph Mail: {e}")
        if hasattr(e,'response') and e.response: app.logger.error(f"POLLER: API Réponse: {e.response.status_code} - {e.response.text}")
        return 0
    except Exception as e: app.logger.error(f"POLLER: Erreur: {e}", exc_info=True); return 0

# --- Thread Background Polling Email ---
def background_email_poller():
    app.logger.info(f"BG_POLLER: Démarrage (Fuseau: {POLLING_TIMEZONE_STR}).")
    err_count = 0; MAX_ERR = 5
    while True:
        try:
            now = datetime.now(TZ_FOR_POLLING)
            active_day = now.weekday() in POLLING_ACTIVE_DAYS
            active_time = POLLING_ACTIVE_START_HOUR <= now.hour < POLLING_ACTIVE_END_HOUR
            log_dets = f"Jour:{now.weekday()}[{POLLING_ACTIVE_DAYS}],Heure:{now.hour:02d}h[{POLLING_ACTIVE_START_HOUR:02d}h-{POLLING_ACTIVE_END_HOUR:02d}h {POLLING_TIMEZONE_STR}]"
            if active_day and active_time:
                app.logger.info(f"BG_POLLER: Plage active ({log_dets}). Cycle.")
                if not all([ONEDRIVE_CLIENT_ID,ONEDRIVE_SECRET,ONEDRIVE_REFRESH_TOKEN,SENDER_LIST_FOR_POLLING,MAKE_SCENARIO_WEBHOOK_URL]):
                    app.logger.warning("BG_POLLER: Cfg incomplète. Attente 60s."); time.sleep(60); continue
                triggered_n = check_new_emails_and_trigger_make_webhook()
                app.logger.info(f"BG_POLLER: Cycle actif fini. {triggered_n} WH(s) déclenché(s).")
                err_count = 0; sleep_t = EMAIL_POLLING_INTERVAL_SECONDS
            else: app.logger.info(f"BG_POLLER: Hors plage active ({log_dets}). Veille."); sleep_t = POLLING_INACTIVE_CHECK_INTERVAL_SECONDS
            time.sleep(sleep_t)
        except Exception as e:
            err_count+=1; app.logger.error(f"BG_POLLER: Erreur #{err_count}: {e}",exc_info=True)
            if err_count >= MAX_ERR: app.logger.critical(f"BG_POLLER: Trop d'erreurs ({MAX_ERR}). Arrêt."); break
            time.sleep(EMAIL_POLLING_INTERVAL_SECONDS * (2**err_count))

# --- Endpoints Flask ---
@app.route('/api/process_individual_dropbox_link', methods=['POST'])
def api_process_individual_dropbox_link():
    global PROCESSING_URLS, PROCESSING_URLS_LOCK # Référence aux variables globales
    
    token_api = request.headers.get('X-API-Token')
    if not EXPECTED_API_TOKEN: app.logger.error("API_PROC: PROCESS_API_TOKEN non cfg."); return jsonify({"s":"err","m":"Err cfg serveur"}),500
    if token_api != EXPECTED_API_TOKEN: app.logger.warning(f"API_PROC: Accès non autorisé. T:{token_api}."); return jsonify({"s":"err","m":"Non autorisé"}),401
    app.logger.info("API_PROC: Token API validé.")
    
    try: data = request.get_json(silent=True) or (json.loads(request.data.decode('utf-8')) if request.data else None)
    except Exception as e: app.logger.error(f"API_PROC: Erreur JSON: {e}",exc_info=True); return jsonify({"s":"err","m":f"Err JSON: {e}"}),400
    app.logger.info(f"API_PROC: Données JSON: {str(data)[:200]}{'...' if len(str(data)) > 200 else ''}")
    if not data or 'dropbox_url' not in data: app.logger.error(f"API_PROC: Payload invalide: {data}"); return jsonify({"s":"err","m":"dropbox_url manquante"}),400
    
    db_url = data.get('dropbox_url')
    subj = data.get('email_subject', 'Fichier_Dropbox_Sujet_Absent')
    mail_id_log = data.get('microsoft_graph_email_id', 'N/A_EMAIL_ID')
    
    with PROCESSING_URLS_LOCK:
        if db_url in PROCESSING_URLS:
            app.logger.info(f"API_PROC: URL '{db_url}' déjà en traitement/attente. Ignorée.")
            return jsonify({"status": "ignored_in_process", "message": "URL déjà en cours de traitement ou en attente."}), 200 # HTTP 200 OK mais traitement ignoré
        PROCESSING_URLS.add(db_url)
        app.logger.info(f"API_PROC: URL '{db_url}' ajoutée à PROCESSING_URLS (taille: {len(PROCESSING_URLS)}).")

    app.logger.info(f"API_PROC: Demande reçue URL: {db_url} (Sujet: {subj}, EmailID: {mail_id_log})")
    
    # Génération du suffixe du nom du thread
    name_suffix_base = (re.sub(r'[^a-zA-Z0-9]', '', mail_id_log)[-15:] if mail_id_log and mail_id_log not in ['N/A', 'N/A_EMAIL_ID'] else "")
    if not name_suffix_base: name_suffix_base = (re.sub(r'[^a-zA-Z0-9]', '', db_url)[-20:] if len(re.sub(r'[^a-zA-Z0-9]', '', db_url)) > 5 else "")
    if not name_suffix_base: name_suffix_base = str(time.time_ns())[-10:]
    
    thread = threading.Thread(target=process_dropbox_link_worker, args=(db_url, subj, mail_id_log), name=f"StreamW-{name_suffix_base}")
    thread.daemon = True; thread.start()
    app.logger.info(f"API_PROC: Tâche streaming pour {db_url} mise en file (thread: {thread.name}).")
    return jsonify({"status": "accepted", "message": "Demande de traitement (streaming) reçue et mise en file."}), 202

@app.route('/api/trigger_local_workflow', methods=['POST'])
def trigger_local_workflow():
    pl = request.json or {"cmd":"start_local","ts":time.time()}
    try:
        with open(TRIGGER_SIGNAL_FILE,"w") as f: json.dump(pl,f)
        app.logger.info(f"LOCAL_API: Signal posé {TRIGGER_SIGNAL_FILE}. P: {pl}"); return jsonify({"s":"ok","m":"Signal posé"}),200
    except Exception as e: app.logger.error(f"LOCAL_API: Erreur pose signal: {e}",exc_info=True); return jsonify({"s":"err","m":"Err interne pose signal"}),500

@app.route('/api/check_trigger', methods=['GET'])
def check_local_workflow_trigger():
    res_data = {'cmd_pending':False,'payload':None}
    if TRIGGER_SIGNAL_FILE.exists():
        try:
            with open(TRIGGER_SIGNAL_FILE,'r') as f: pl = json.load(f)
            res_data['cmd_pending']=True; res_data['payload']=pl
            TRIGGER_SIGNAL_FILE.unlink(); app.logger.info(f"LOCAL_API: Signal lu et supprimé. P: {pl}")
        except Exception as e: app.logger.error(f"LOCAL_API: Erreur traitement signal {TRIGGER_SIGNAL_FILE}: {e}",exc_info=True)
    return jsonify(res_data)

@app.route('/api/ping', methods=['GET', 'HEAD'])
def api_ping():
    ip = request.headers.get('X-Forwarded-For',request.remote_addr); ua = request.headers.get('User-Agent','N/A')
    app.logger.info(f"PING_API: Keep-Alive /api/ping IP:{ip}, UA:{ua} at {datetime.now(timezone.utc).isoformat()}")
    r = jsonify({"s":"pong","ts":time.time()}); r.headers["Cache-Control"]="no-cache,no-store,must-revalidate"; r.headers["Pragma"]="no-cache"; r.headers["Expires"]="0"
    return r, 200

@app.route('/')
def serve_trigger_page_main():
    app.logger.info("ROOT: '/' appelée. Servir 'trigger_page.html'.")
    try: return send_from_directory(app.root_path, 'trigger_page.html')
    except FileNotFoundError: app.logger.error(f"ROOT: ERREUR: trigger_page.html non trouvé dans {app.root_path}."); return "Err: Page non trouvée.",404
    except Exception as e: app.logger.error(f"ROOT: Erreur send_from_directory: {e}",exc_info=True); return "Err interne serveur (UI).",500

if __name__ == '__main__':
    debug = os.environ.get('FLASK_DEBUG','False').lower()=='true'
    start_bg = not debug or os.environ.get("WERKZEUG_RUN_MAIN")=="true"
    if start_bg:
        if all([ONEDRIVE_CLIENT_ID,ONEDRIVE_SECRET,ONEDRIVE_REFRESH_TOKEN,SENDER_LIST_FOR_POLLING,MAKE_SCENARIO_WEBHOOK_URL]):
            poll_th = threading.Thread(target=background_email_poller,name="EmailPollerThread"); poll_th.daemon=True; poll_th.start()
            app.logger.info(f"MAIN: Thread polling emails démarré (exp: {len(SENDER_LIST_FOR_POLLING)}, fuseau: {POLLING_TIMEZONE_STR}).")
        else: app.logger.warning("MAIN: Thread polling emails NON démarré (cfg incomplète).")
    port = int(os.environ.get('PORT',10000))
    if not EXPECTED_API_TOKEN: app.logger.critical("MAIN: ALERTE SÉCURITÉ: PROCESS_API_TOKEN NON DÉFINI.")
    app.logger.info(f"MAIN: Démarrage serveur Flask port {port} debug={debug}")
    app.run(host='0.0.0.0',port=port,debug=debug,use_reloader=(debug and os.environ.get("WERKZEUG_RUN_MAIN")!="true"))
