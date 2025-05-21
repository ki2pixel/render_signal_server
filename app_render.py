from flask import Flask, jsonify, request, send_from_directory, current_app
import os
import time
from pathlib import Path
import json
import logging
import re
import requests
import threading
import html as html_parser
import datetime # Ajouté pour /api/ping, bien qu'il semble que vous l'aviez déjà dans la version précédente.

from msal import ConfidentialClientApplication

app = Flask(__name__)

# Configuration du logging
log_level_str = os.environ.get('FLASK_LOG_LEVEL', 'INFO').upper()
log_level = getattr(logging, log_level_str, logging.INFO)
logging.basicConfig(level=log_level,
                    format='%(asctime)s - %(levelname)s - %(name)s - %(module)s - %(funcName)s - %(lineno)d - %(message)s')


# --- Configuration des Constantes et Variables d'Environnement ---
SIGNAL_DIR = Path(os.environ.get("RENDER_DISC_PATH", "./signal_data_app_render"))
TRIGGER_SIGNAL_FILE = SIGNAL_DIR / "local_workflow_trigger_signal.json"

DOWNLOAD_TEMP_DIR_RENDER = SIGNAL_DIR / "temp_dropbox_downloads"
# Nom de fichier unifié pour les URLs traitées sur OneDrive
PROCESSED_URLS_ONEDRIVE_FILENAME = "processed_dropbox_urls_workflow.txt"

SIGNAL_DIR.mkdir(parents=True, exist_ok=True)
DOWNLOAD_TEMP_DIR_RENDER.mkdir(parents=True, exist_ok=True)

# --- Configuration API Microsoft Graph (OneDrive) ---
ONEDRIVE_CLIENT_ID = os.environ.get('ONEDRIVE_CLIENT_ID')
ONEDRIVE_CLIENT_SECRET = os.environ.get('ONEDRIVE_CLIENT_SECRET')
ONEDRIVE_REFRESH_TOKEN = os.environ.get('ONEDRIVE_REFRESH_TOKEN')
ONEDRIVE_AUTHORITY = "https://login.microsoftonline.com/consumers"
ONEDRIVE_SCOPES_DELEGATED = ["Files.ReadWrite", "User.Read", "offline_access"]
ONEDRIVE_TARGET_PARENT_FOLDER_ID = os.environ.get('ONEDRIVE_TARGET_PARENT_FOLDER_ID', 'root')
ONEDRIVE_TARGET_SUBFOLDER_NAME = os.environ.get('ONEDRIVE_TARGET_SUBFOLDER_NAME', "DropboxDownloadsWorkflow")

msal_app = None
if ONEDRIVE_CLIENT_ID and ONEDRIVE_CLIENT_SECRET:
    app.logger.info(f"CONFIGURATION: Initialisation MSAL avec Client ID et Authority: {ONEDRIVE_AUTHORITY}")
    msal_app = ConfidentialClientApplication(
        ONEDRIVE_CLIENT_ID,
        authority=ONEDRIVE_AUTHORITY,
        client_credential=ONEDRIVE_CLIENT_SECRET
    )
else:
    app.logger.warning("CONFIGURATION: ONEDRIVE_CLIENT_ID ou ONEDRIVE_CLIENT_SECRET manquant. Intégration OneDrive désactivée.")

# --- Token d'API pour sécuriser les endpoints appelés par Make.com ---
EXPECTED_API_TOKEN = os.environ.get("PROCESS_API_TOKEN")
if not EXPECTED_API_TOKEN:
    app.logger.warning("CONFIGURATION: PROCESS_API_TOKEN non défini. L'endpoint pour Make.com sera non sécurisé.")
app.logger.info(f"CONFIGURATION: Token attendu pour /api/process_individual_dropbox_link (PROCESS_API_TOKEN): '{EXPECTED_API_TOKEN}'")


# --- Fonctions Utilitaires ---
def sanitize_filename(filename_str, max_length=230):
    sanitized = re.sub(r'[<>:"/\\|?*]', '_', filename_str)
    sanitized = re.sub(r'\.+', '.', sanitized).strip('.')
    if not sanitized: sanitized = "fichier_sans_nom"
    return sanitized[:max_length]

def get_onedrive_access_token():
    if not msal_app: app.logger.error("MSAL non configuré."); return None
    if not ONEDRIVE_REFRESH_TOKEN: app.logger.error("ONEDRIVE_REFRESH_TOKEN manquant."); return None
    app.logger.debug(f"Acquisition token Graph API pour scopes: {ONEDRIVE_SCOPES_DELEGATED}")
    result = msal_app.acquire_token_by_refresh_token(ONEDRIVE_REFRESH_TOKEN, scopes=ONEDRIVE_SCOPES_DELEGATED)
    if "access_token" in result:
        app.logger.info("Token d'accès Graph API obtenu.")
        if result.get("refresh_token") and result.get("refresh_token") != ONEDRIVE_REFRESH_TOKEN:
             app.logger.warning("Nouveau refresh token Graph API émis. Conseil: Mettez à jour la variable d'env ONEDRIVE_REFRESH_TOKEN.")
        return result['access_token']
    else:
        app.logger.error(f"Erreur acquisition token: {result.get('error')} - {result.get('error_description')}")
        app.logger.error(f"Détails MSAL: {result}"); return None

def ensure_onedrive_folder(access_token):
    headers = {'Authorization': 'Bearer ' + access_token, 'Content-Type': 'application/json'}
    parent_id = ONEDRIVE_TARGET_PARENT_FOLDER_ID if ONEDRIVE_TARGET_PARENT_FOLDER_ID and ONEDRIVE_TARGET_PARENT_FOLDER_ID.lower() != 'root' else 'root'
    subfolder_name_clean = sanitize_filename(ONEDRIVE_TARGET_SUBFOLDER_NAME, 100)
    if parent_id == 'root':
        folder_check_url = f"https://graph.microsoft.com/v1.0/me/drive/root/children?$filter=name eq '{subfolder_name_clean}'"
        folder_create_url = f"https://graph.microsoft.com/v1.0/me/drive/root/children"
    else:
        folder_check_url = f"https://graph.microsoft.com/v1.0/me/drive/items/{parent_id}/children?$filter=name eq '{subfolder_name_clean}'"
        folder_create_url = f"https://graph.microsoft.com/v1.0/me/drive/items/{parent_id}/children"
    try:
        response = requests.get(folder_check_url, headers=headers, timeout=15)
        response.raise_for_status(); children = response.json().get('value', [])
        if children: folder_id = children[0]['id']; app.logger.info(f"Dossier OneDrive '{subfolder_name_clean}' trouvé ID: {folder_id}"); return folder_id
        else:
            app.logger.info(f"Dossier OneDrive '{subfolder_name_clean}' non trouvé. Création.")
            payload = {"name": subfolder_name_clean, "folder": {}, "@microsoft.graph.conflictBehavior": "rename"}
            response_create = requests.post(folder_create_url, headers=headers, json=payload, timeout=15)
            response_create.raise_for_status(); folder_id = response_create.json()['id']
            app.logger.info(f"Dossier OneDrive '{subfolder_name_clean}' créé ID: {folder_id}"); return folder_id
    except requests.exceptions.RequestException as e:
        app.logger.error(f"Erreur API Graph dossier '{subfolder_name_clean}': {e}")
        if hasattr(e, 'response') and e.response is not None: app.logger.error(f"Réponse API: {e.response.status_code} - {e.response.text}")
        return None

def _try_cancel_upload_session(upload_session_url, filename_onedrive_clean, reason="erreur"):
    if not upload_session_url: return
    app.logger.info(f"Tentative d'annulation session upload ({reason}) pour {filename_onedrive_clean}: {upload_session_url}")
    token_for_delete = get_onedrive_access_token()
    if token_for_delete:
        try:
            requests.delete(upload_session_url, headers={'Authorization': 'Bearer ' + token_for_delete}, timeout=10)
            app.logger.info(f"Session upload pour {filename_onedrive_clean} annulée ou déjà expirée.")
        except requests.exceptions.RequestException as e_del:
            app.logger.warning(f"Échec annulation session upload pour {filename_onedrive_clean}: {e_del}")
    else:
        app.logger.warning(f"Impossible d'obtenir un token pour annuler la session d'upload de {filename_onedrive_clean}.")


def upload_to_onedrive(filepath, filename_onedrive, access_token, target_folder_id):
    if not access_token or not target_folder_id: app.logger.error("Upload: Token/ID dossier manquant."); return False
    filename_onedrive_clean = sanitize_filename(filename_onedrive)
    upload_url_simple_put = f"https://graph.microsoft.com/v1.0/me/drive/items/{target_folder_id}:/{filename_onedrive_clean}:/content?@microsoft.graph.conflictBehavior=rename"
    headers_put = {'Authorization': 'Bearer ' + access_token, 'Content-Type': 'application/octet-stream'}
    file_size = Path(filepath).stat().st_size
    app.logger.info(f"Upload de '{Path(filepath).name}' ({file_size}b) vers OneDrive '{filename_onedrive_clean}'")
    
    MAX_CHUNK_RETRIES = 3; RETRY_DELAY_SECONDS = 5; final_response = None
    upload_session_url = None # Définir avant le try pour être accessible dans le finally implicite du except

    try:
        if file_size < 4 * 1024 * 1024:
            with open(filepath, 'rb') as f_data:
                response = requests.put(upload_url_simple_put, headers=headers_put, data=f_data, timeout=300) # Timeout 5 min pour petits fichiers
                response.raise_for_status(); final_response = response
        else:
            create_session_url = f"https://graph.microsoft.com/v1.0/me/drive/items/{target_folder_id}:/{filename_onedrive_clean}:/createUploadSession"
            session_payload = {"item": {"@microsoft.graph.conflictBehavior": "rename"}}
            session_headers = {'Authorization': 'Bearer ' + access_token, 'Content-Type': 'application/json'}
            session_response = requests.post(create_session_url, headers=session_headers, json=session_payload, timeout=60)
            session_response.raise_for_status(); upload_session_url = session_response.json()['uploadUrl']
            app.logger.info(f"Session upload OneDrive créée pour {filename_onedrive_clean}.")
            chunk_size = 10 * 1024 * 1024; chunks_uploaded_count = 0
            with open(filepath, 'rb') as f_data:
                while True:
                    chunk = f_data.read(chunk_size)
                    if not chunk: break
                    start_byte = chunks_uploaded_count * chunk_size; end_byte = start_byte + len(chunk) - 1
                    percentage_complete = ((end_byte + 1) / file_size) * 100 if file_size > 0 else 0
                    chunk_headers = {'Content-Length': str(len(chunk)), 'Content-Range': f'bytes {start_byte}-{end_byte}/{file_size}'}
                    current_chunk_retries = 0
                    while current_chunk_retries < MAX_CHUNK_RETRIES:
                        try:
                            app.logger.info(f"Upload chunk (Try {current_chunk_retries + 1}/{MAX_CHUNK_RETRIES}): {filename_onedrive_clean} bytes {start_byte}-{end_byte}/{file_size} ({percentage_complete:.2f}%)")
                            response_chunk = requests.put(upload_session_url, headers=chunk_headers, data=chunk, timeout=180) # Timeout 3 min par chunk
                            response_chunk.raise_for_status(); final_response = response_chunk
                            app.logger.info(f"Chunk {filename_onedrive_clean} bytes {start_byte}-{end_byte} ({percentage_complete:.2f}%) OK. Status: {response_chunk.status_code}")
                            break
                        except requests.exceptions.RequestException as e_chunk:
                            current_chunk_retries += 1; app.logger.warning(f"Erreur upload chunk {filename_onedrive_clean} (Try {current_chunk_retries}/{MAX_CHUNK_RETRIES}): {e_chunk}")
                            status_code_chunk = None
                            if hasattr(e_chunk, 'response') and e_chunk.response is not None:
                                status_code_chunk = e_chunk.response.status_code
                                app.logger.warning(f"Réponse API chunk: {status_code_chunk} - {e_chunk.response.text[:200]}")
                            
                            is_retryable_status = status_code_chunk in [429, 500, 502, 503, 504]
                            is_network_error = status_code_chunk is None # Indique souvent un problème réseau avant réponse HTTP

                            if (is_retryable_status or is_network_error) and current_chunk_retries < MAX_CHUNK_RETRIES:
                                delay = RETRY_DELAY_SECONDS * (2 ** (current_chunk_retries -1)); app.logger.info(f"Attente {delay}s avant retry chunk..."); time.sleep(delay)
                            else:
                                app.logger.error(f"Échec final chunk {filename_onedrive_clean} après {current_chunk_retries} tentatives (erreur non récupérable ou réseau)."); raise e_chunk # Relance l'exception du chunk
                    else: # Exécuté si la boucle while des retries se termine sans break (donc tous les retries ont échoué)
                        app.logger.error(f"Max retries ({MAX_CHUNK_RETRIES}) atteint pour chunk {filename_onedrive_clean}. Abandon upload."); return False
                    chunks_uploaded_count += 1
            app.logger.info(f"Tous les chunks de '{filename_onedrive_clean}' traités pour upload.")
        
        if final_response and final_response.status_code < 300:
            app.logger.info(f"Fichier '{filename_onedrive_clean}' uploadé avec succès. Statut final: {final_response.status_code}")
            return True
        else:
            status_to_log = final_response.status_code if final_response else 'N/A'
            app.logger.error(f"Erreur après tentatives d'upload ({filename_onedrive_clean}). Statut final: {status_to_log}")
            # Pas besoin de _try_cancel_upload_session ici si l'échec vient d'un chunk, car l'exception aurait déjà été levée
            return False
            
    except requests.exceptions.RequestException as e:
        app.logger.error(f"Erreur API Graph upload ({filename_onedrive_clean}): {e}")
        if hasattr(e, 'response') and e.response is not None: app.logger.error(f"Réponse API: {e.response.status_code} - {e.response.text}")
        if file_size >= 4 * 1024 * 1024: _try_cancel_upload_session(upload_session_url, filename_onedrive_clean, "erreur RequestException")
        return False
    except Exception as ex: # Pour les erreurs non interceptées spécifiquement (ex: erreur de logique dans le code des chunks)
        app.logger.error(f"Erreur générale non gérée pendant l'upload ({filename_onedrive_clean}): {ex}", exc_info=True)
        if file_size >= 4 * 1024 * 1024: _try_cancel_upload_session(upload_session_url, filename_onedrive_clean, "erreur générale Exception")
        return False

def download_file_from_dropbox_and_upload_to_onedrive(dropbox_url, access_token_graph, target_folder_id_onedrive, subject_for_default_filename="FichierDropbox"):
    app.logger.info(f"WORKER_DL_UL: Traitement URL Dropbox: {dropbox_url}")
    unescaped_url = html_parser.unescape(dropbox_url)
    modified_url = unescaped_url.replace("dl=0", "dl=1")
    modified_url = re.sub(r'dl=[^&?#]+', 'dl=1', modified_url)
    if '?dl=1' not in modified_url and '&dl=1' not in modified_url:
        modified_url += ("&" if "?" in modified_url else "?") + "dl=1"
    app.logger.info(f"WORKER_DL_UL: URL Dropbox finale pour téléchargement: {modified_url}")

    temp_filepath = None; ts = time.strftime('%Y%m%d-%H%M%S')
    default_filename_base = sanitize_filename(subject_for_default_filename, 180)
    default_filename_with_ts = f"{default_filename_base}_{ts}.telechargement"

    try:
        headers_db = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response_db = requests.get(modified_url, stream=True, allow_redirects=True, timeout=900, headers=headers_db) # Timeout 15 min
        response_db.raise_for_status()

        total_length_dropbox_str = response_db.headers.get('content-length')
        total_length_dropbox = int(total_length_dropbox_str) if total_length_dropbox_str and total_length_dropbox_str.isdigit() else None
        if total_length_dropbox: app.logger.info(f"WORKER_DL_UL: Taille fichier Dropbox: {total_length_dropbox} bytes.")
        else: app.logger.warning("WORKER_DL_UL: Content-Length Dropbox non trouvé/invalide. Progression DL non affichable.")

        filename_for_onedrive = default_filename_with_ts
        content_disp = response_db.headers.get('content-disposition')
        if content_disp:
            app.logger.debug(f"WORKER_DL_UL: Content-Disposition Dropbox: '{content_disp}'")
            m_utf8 = re.search(r"filename\*=UTF-8''([^;\n\r]+)", content_disp, flags=re.IGNORECASE)
            if m_utf8:
                filename_from_cd = requests.utils.unquote(m_utf8.group(1))
                app.logger.info(f"WORKER_DL_UL: Nom de fichier (filename* UTF-8) extrait: '{filename_from_cd}'")
            else:
                m_simple = re.search(r'filename="([^"]+)"', content_disp, flags=re.IGNORECASE)
                if m_simple:
                    filename_from_cd = m_simple.group(1)
                    if '%' in filename_from_cd:
                        try: filename_from_cd = requests.utils.unquote(filename_from_cd)
                        except Exception: pass
                    app.logger.info(f"WORKER_DL_UL: Nom de fichier (filename=\"\") extrait: '{filename_from_cd}'")
                else:
                    app.logger.warning(f"WORKER_DL_UL: Impossible de parser 'filename' ou 'filename*' dans Content-Disposition. Utilisation nom par défaut.")
                    filename_from_cd = None
            if filename_from_cd:
                filename_for_onedrive = sanitize_filename(filename_from_cd)
                is_dropbox_folder_link = "dropbox.com/scl/fo/" in unescaped_url
                has_archive_extension = any(filename_for_onedrive.lower().endswith(ext) for ext in ['.zip', '.rar', '.7z'])
                if is_dropbox_folder_link and not has_archive_extension:
                    name_part, _ = os.path.splitext(filename_for_onedrive) # _ pour current_ext
                    filename_for_onedrive = name_part + ".zip"
                    app.logger.info(f"WORKER_DL_UL: Lien dossier Dropbox & pas d'ext d'archive, ajout/remplacement par .zip. Nom final: '{filename_for_onedrive}'")
        else:
            app.logger.warning(f"WORKER_DL_UL: Content-Disposition Dropbox non trouvé. Utilisation du nom par défaut: '{filename_for_onedrive}'")
        if not filename_for_onedrive: filename_for_onedrive = f"fichier_dropbox_{ts}.bin"

        temp_filepath = DOWNLOAD_TEMP_DIR_RENDER / filename_for_onedrive
        app.logger.info(f"WORKER_DL_UL: Téléchargement Dropbox vers: '{temp_filepath}'")
        downloaded_length = 0; last_logged_percentage_dl = -10
        with open(temp_filepath, 'wb') as f:
            for chunk_db in response_db.iter_content(chunk_size=1024*1024*2): # 2MB chunks
                if chunk_db:
                    f.write(chunk_db); downloaded_length += len(chunk_db)
                    if total_length_dropbox and total_length_dropbox > 0:
                        percentage_dl = int((downloaded_length / total_length_dropbox) * 100)
                        if percentage_dl >= last_logged_percentage_dl + 5 or last_logged_percentage_dl < 0 :
                            app.logger.info(f"WORKER_DL_UL: DL Dropbox {filename_for_onedrive} en cours... {downloaded_length}/{total_length_dropbox}b ({percentage_dl}%)")
                            last_logged_percentage_dl = percentage_dl
        if total_length_dropbox and downloaded_length < total_length_dropbox:
            app.logger.warning(f"WORKER_DL_UL: Taille DL ({downloaded_length}) < attendue ({total_length_dropbox}) pour {filename_for_onedrive}.")
        app.logger.info(f"WORKER_DL_UL: Fichier Dropbox '{filename_for_onedrive}' téléchargé ({downloaded_length}b).")

        if upload_to_onedrive(temp_filepath, filename_for_onedrive, access_token_graph, target_folder_id_onedrive):
            app.logger.info(f"WORKER_DL_UL: Upload OneDrive de '{filename_for_onedrive}' réussi.")
            return True
        else:
            app.logger.error(f"WORKER_DL_UL: Échec upload OneDrive de '{filename_for_onedrive}'.")
            return False
    except requests.exceptions.Timeout: app.logger.error(f"WORKER_DL_UL: Timeout Dropbox pour {modified_url}"); return False
    except requests.exceptions.RequestException as e:
        app.logger.error(f"WORKER_DL_UL: Erreur requête Dropbox {modified_url}: {e}")
        if hasattr(e, 'response') and e.response is not None: app.logger.error(f"WORKER_DL_UL: Réponse Dropbox: {e.response.status_code} - {e.response.text[:500]}...")
        return False
    except Exception as e_main: app.logger.error(f"WORKER_DL_UL: Erreur générale DL/UL {dropbox_url}: {e_main}", exc_info=True); return False
    finally:
        if temp_filepath and temp_filepath.exists():
            try: temp_filepath.unlink(); app.logger.info(f"WORKER_DL_UL: Fichier temp '{temp_filepath.name}' supprimé.")
            except OSError as e_unlink: app.logger.error(f"WORKER_DL_UL: Erreur suppression temp '{temp_filepath.name}': {e_unlink}")

def get_processed_urls_from_onedrive(access_token, target_folder_id):
    if not access_token or not target_folder_id: return set()
    download_url = f"https://graph.microsoft.com/v1.0/me/drive/items/{target_folder_id}:/{PROCESSED_URLS_ONEDRIVE_FILENAME}:/content"
    headers = {'Authorization': 'Bearer ' + access_token}; processed_urls = set()
    app.logger.debug(f"Tentative de lecture de {PROCESSED_URLS_ONEDRIVE_FILENAME} depuis OneDrive.")
    try:
        response = requests.get(download_url, headers=headers, timeout=30)
        if response.status_code == 200:
            lines = response.text.splitlines()
            for line in lines:
                if line.strip(): processed_urls.add(line.strip())
            app.logger.info(f"Lu {len(processed_urls)} URLs depuis {PROCESSED_URLS_ONEDRIVE_FILENAME}.")
        elif response.status_code == 404: app.logger.info(f"{PROCESSED_URLS_ONEDRIVE_FILENAME} non trouvé sur OneDrive. Initialisation nouvelle liste.")
        else: response.raise_for_status()
    except requests.exceptions.RequestException as e: app.logger.error(f"Erreur téléchargement {PROCESSED_URLS_ONEDRIVE_FILENAME}: {e}")
    return processed_urls

def add_processed_url_to_onedrive(access_token, target_folder_id, dropbox_url_processed):
    if not access_token or not target_folder_id or not dropbox_url_processed: return False
    current_urls = get_processed_urls_from_onedrive(access_token, target_folder_id)
    current_urls.add(dropbox_url_processed)

    content_to_upload = "\n".join(sorted(list(current_urls))) if current_urls else ""
    upload_url = f"https://graph.microsoft.com/v1.0/me/drive/items/{target_folder_id}:/{PROCESSED_URLS_ONEDRIVE_FILENAME}:/content?@microsoft.graph.conflictBehavior=replace"
    headers = {'Authorization': 'Bearer ' + access_token, 'Content-Type': 'text/plain; charset=utf-8'}
    try:
        response = requests.put(upload_url, headers=headers, data=content_to_upload.encode('utf-8'), timeout=60)
        response.raise_for_status()
        app.logger.info(f"{PROCESSED_URLS_ONEDRIVE_FILENAME} mis à jour sur OneDrive ({len(current_urls)} URLs).")
        return True
    except requests.exceptions.RequestException as e: app.logger.error(f"Erreur upload {PROCESSED_URLS_ONEDRIVE_FILENAME}: {e}"); return False

def process_dropbox_link_worker(dropbox_url, subject_for_default_filename, email_id_for_logging):
    app.logger.info(f"WORKER_THREAD: Démarrage pour URL: {dropbox_url} (Sujet Fallback: {subject_for_default_filename}, EmailID: {email_id_for_logging})")
    access_token_graph = get_onedrive_access_token()
    if not access_token_graph: app.logger.error(f"WORKER_THREAD: Échec token Graph pour {dropbox_url}. Arrêt."); return
    target_folder_id_onedrive = ensure_onedrive_folder(access_token_graph)
    if not target_folder_id_onedrive: app.logger.error(f"WORKER_THREAD: Échec dossier OneDrive pour {dropbox_url}. Arrêt."); return

    processed_urls = get_processed_urls_from_onedrive(access_token_graph, target_folder_id_onedrive)
    if dropbox_url in processed_urls:
        app.logger.info(f"WORKER_THREAD: URL {dropbox_url} déjà traitée (vérifié dans worker). Ignorée.")
        return
    app.logger.info(f"WORKER_THREAD: URL {dropbox_url} nouvelle. Lancement transfert.")
    success_transfer = download_file_from_dropbox_and_upload_to_onedrive(
        dropbox_url, access_token_graph, target_folder_id_onedrive, subject_for_default_filename
    )
    if success_transfer:
        app.logger.info(f"WORKER_THREAD: Transfert {dropbox_url} réussi. MàJ liste URLs traitées.")
        if not add_processed_url_to_onedrive(access_token_graph, target_folder_id_onedrive, dropbox_url):
            app.logger.error(f"WORKER_THREAD: CRITIQUE - Fichier {dropbox_url} transféré mais échec màj {PROCESSED_URLS_ONEDRIVE_FILENAME}.")
    else: app.logger.error(f"WORKER_THREAD: Échec transfert {dropbox_url}.")
    app.logger.info(f"WORKER_THREAD: Fin tâche pour {dropbox_url}")

@app.route('/api/process_individual_dropbox_link', methods=['POST'])
def api_process_individual_dropbox_link():
    received_token = request.headers.get('X-API-Token')
    if not EXPECTED_API_TOKEN: app.logger.error("API: PROCESS_API_TOKEN non configuré."); return jsonify({"status": "error", "message": "Erreur de configuration serveur"}), 500
    if received_token != EXPECTED_API_TOKEN: app.logger.warning(f"API: Accès non autorisé. Token reçu: '{received_token}'."); return jsonify({"status": "error", "message": "Non autorisé"}), 401
    app.logger.info("API: Token API validé.")

    app.logger.debug(f"API: Headers: {dict(request.headers)}")
    app.logger.debug(f"API: Données brutes (premiers 200 chars): {request.data[:200]}")
    data = None
    try:
        data = request.get_json(silent=True)
        if data is None and request.data:
            app.logger.warning(f"API: get_json(silent=True) None. Tentative parsing manuel.")
            try: data = json.loads(request.data.decode('utf-8'))
            except Exception as e_parse: app.logger.error(f"API: Échec parsing manuel: {e_parse}"); raise
        app.logger.info(f"API: Données JSON parsées: {data if data else 'Aucune ou parsing échoué avant log'}")
    except Exception as e: app.logger.error(f"API: Erreur parsing JSON initial: {e}", exc_info=True); return jsonify({"status": "error", "message": f"Erreur décodage JSON: {str(e)}"}), 400
    if not data or 'dropbox_url' not in data: app.logger.error(f"API: Payload invalide. 'data': {data}"); return jsonify({"status": "error", "message": "dropbox_url manquante ou payload invalide"}), 400

    dropbox_url_to_process = data.get('dropbox_url')
    email_subject_for_filename = data.get('email_subject', 'Fichier_Dropbox')
    email_id_for_logging = data.get('email_id', 'N/A')
    app.logger.info(f"API: Demande reçue pour URL: {dropbox_url_to_process} (Sujet fallback: {email_subject_for_filename}, EmailID: {email_id_for_logging})")

    thread = threading.Thread(target=process_dropbox_link_worker, args=(dropbox_url_to_process, email_subject_for_filename, email_id_for_logging))
    thread.daemon = True; thread.start()
    app.logger.info(f"API: Tâche pour {dropbox_url_to_process} mise en file (thread démarré).")
    return jsonify({"status": "accepted", "message": "Demande de traitement reçue et mise en file d'attente."}), 202

@app.route('/api/trigger_local_workflow', methods=['POST'])
def trigger_local_workflow():
    command_payload = request.json or {"command": "start_local_process", "timestamp": time.time()}
    try:
        with open(TRIGGER_SIGNAL_FILE, "w") as f: json.dump(command_payload, f)
        app.logger.info(f"Signal local posé sur {TRIGGER_SIGNAL_FILE}. Payload: {command_payload}")
        return jsonify({"status": "success", "message": "Signal pour workflow local posé", "payload": command_payload}), 200
    except Exception as e: app.logger.error(f"Erreur pose signal local: {e}", exc_info=True); return jsonify({"status": "error", "message": "Erreur interne pose signal"}), 500

@app.route('/api/check_trigger', methods=['GET'])
def check_local_workflow_trigger():
    response_data = {'command_pending': False, 'payload': None}
    if TRIGGER_SIGNAL_FILE.exists():
        try:
            with open(TRIGGER_SIGNAL_FILE, 'r') as f: payload = json.load(f)
            response_data['command_pending'] = True; response_data['payload'] = payload
            TRIGGER_SIGNAL_FILE.unlink(); app.logger.info(f"Signal local lu et supprimé de {TRIGGER_SIGNAL_FILE}. P: {payload}")
        except Exception as e: app.logger.error(f"Erreur traitement signal {TRIGGER_SIGNAL_FILE} : {e}", exc_info=True)
    return jsonify(response_data)

@app.route('/api/ping', methods=['GET', 'HEAD'])
def api_ping():
    ip_address = request.headers.get('X-Forwarded-For', request.remote_addr)
    user_agent = request.headers.get('User-Agent', 'N/A')
    # Utilisation de datetime pour le timestamp dans le log du ping
    app.logger.info(f"PING_RECEIVED: Keep-Alive sur /api/ping depuis IP: {ip_address}, UA: {user_agent} at {datetime.datetime.utcnow().isoformat()}")
    response = jsonify({"status": "pong", "timestamp": time.time()})
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"; response.headers["Pragma"] = "no-cache"; response.headers["Expires"] = "0"
    return response, 200

@app.route('/')
def serve_trigger_page_main():
    app.logger.info("Route '/' appelée. Tentative de servir 'trigger_page.html'.")
    try:
        return send_from_directory(app.root_path, 'trigger_page.html')
    except FileNotFoundError:
        app.logger.error(f"ERREUR: trigger_page.html non trouvé dans {app.root_path}.")
        return "Erreur: Page principale non trouvée.", 404
    except Exception as e_send:
        app.logger.error(f"Erreur send_from_directory pour trigger_page.html: {e_send}", exc_info=True)
        return "Erreur interne du serveur (UI).", 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    if not EXPECTED_API_TOKEN:
        app.logger.critical("ALERTE SÉCURITÉ: PROCESS_API_TOKEN N'EST PAS DÉFINIE. L'API Make.com est NON SÉCURISÉE.")
    app.logger.info(f"Démarrage serveur Flask sur port {port} avec debug={debug_mode}")
    app.run(host='0.0.0.0', port=port, debug=debug_mode, use_reloader= (debug_mode and os.environ.get("WERKZEUG_RUN_MAIN") != "true") )
