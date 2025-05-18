from flask import Flask, jsonify, request, send_from_directory, current_app
import os
import time
from pathlib import Path
import json
import logging
import re # Pour les regex
# imaplib and email are no longer needed for the primary email checking logic if using Graph API
# import imaplib
# import email
# from email.header import decode_header
import requests # Pour télécharger depuis Dropbox et appeler l'API Graph

# Pour l'API Microsoft Graph (OneDrive) avec MSAL
from msal import ConfidentialClientApplication

app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Config Fichiers Signal/Statut ---
SIGNAL_DIR = Path(os.environ.get("RENDER_DISC_PATH", "./signal_data"))
TRIGGER_SIGNAL_FILE = SIGNAL_DIR / "workflow_trigger_signal.txt"
LOCAL_STATUS_FILE = SIGNAL_DIR / "current_local_status.json"
PROCESSED_EMAIL_IDS_FILE = SIGNAL_DIR / "processed_email_ids.txt"
DOWNLOAD_TEMP_DIR_RENDER = SIGNAL_DIR / "temp_downloads"

SIGNAL_DIR.mkdir(parents=True, exist_ok=True)
DOWNLOAD_TEMP_DIR_RENDER.mkdir(parents=True, exist_ok=True)

# --- Config Email (SENDER_OF_INTEREST is still key) & Dropbox ---
SENDER_OF_INTEREST = os.environ.get('SENDER_OF_INTEREST')

# --- Config API Microsoft Graph (OneDrive & Mail) ---
ONEDRIVE_CLIENT_ID = os.environ.get('ONEDRIVE_CLIENT_ID')
ONEDRIVE_CLIENT_SECRET = os.environ.get('ONEDRIVE_CLIENT_SECRET')
ONEDRIVE_REFRESH_TOKEN = os.environ.get('ONEDRIVE_REFRESH_TOKEN')

ONEDRIVE_AUTHORITY = "https://login.microsoftonline.com/consumers"
# **** CORRECTION: "offline_access" retiré de cette liste ****
ONEDRIVE_SCOPES_DELEGATED = ["Files.ReadWrite", "User.Read", "Mail.Read"]
ONEDRIVE_TARGET_PARENT_FOLDER_ID = os.environ.get('ONEDRIVE_TARGET_PARENT_FOLDER_ID', 'root')
ONEDRIVE_TARGET_SUBFOLDER_NAME = os.environ.get('ONEDRIVE_TARGET_SUBFOLDER_NAME', "DropboxDownloadsWorkflow")

msal_app = None # Gardons le nom msal_app pour la simplicité
if ONEDRIVE_CLIENT_ID and ONEDRIVE_CLIENT_SECRET:
    app.logger.info(f"Configuration de MSAL ConfidentialClientApplication avec Client ID et Authority: {ONEDRIVE_AUTHORITY}")
    msal_app = ConfidentialClientApplication( # Nom de variable conservé : msal_app
        ONEDRIVE_CLIENT_ID,
        authority=ONEDRIVE_AUTHORITY,
        client_credential=ONEDRIVE_CLIENT_SECRET
    )
else:
    app.logger.warning("ONEDRIVE_CLIENT_ID ou ONEDRIVE_CLIENT_SECRET manquant. L'intégration Graph API sera désactivée.")

# --- Fonctions Utilitaires ---
def find_dropbox_links(text):
    pattern = r'https?://www\.dropbox\.com/scl/(?:fo|fi)/[a-zA-Z0-9_/\-]+?\?[^ \n\r<>"]+'
    links = re.findall(pattern, text)
    return list(set(links))

def get_processed_email_ids():
    if not PROCESSED_EMAIL_IDS_FILE.exists():
        return set()
    with open(PROCESSED_EMAIL_IDS_FILE, 'r') as f:
        return set(line.strip() for line in f)

def add_processed_email_id(email_id_str):
    with open(PROCESSED_EMAIL_IDS_FILE, 'a') as f:
        f.write(email_id_str + "\n")

def get_onedrive_access_token():
    if not msal_app: # Utilise msal_app
        app.logger.error("MSAL ConfidentialClientApplication (msal_app) n'est pas configurée pour Graph API.")
        return None
    if not ONEDRIVE_REFRESH_TOKEN:
        app.logger.error("ONEDRIVE_REFRESH_TOKEN manquant. Impossible d'obtenir un token d'accès Graph API.")
        return None

    app.logger.info(f"Tentative d'acquisition d'un token d'accès Graph API en utilisant le refresh token pour les scopes: {ONEDRIVE_SCOPES_DELEGATED}")
    
    # Utilise msal_app et la liste de scopes corrigée
    result = msal_app.acquire_token_by_refresh_token(
        ONEDRIVE_REFRESH_TOKEN,
        scopes=ONEDRIVE_SCOPES_DELEGATED # La liste corrigée sans "offline_access"
    )

    if "access_token" in result:
        app.logger.info("Nouveau token d'accès Graph API obtenu avec succès via refresh token.")
        new_rt = result.get("refresh_token")
        if new_rt and new_rt != ONEDRIVE_REFRESH_TOKEN:
            app.logger.warning("Un nouveau refresh token Graph API a été émis. "
                               "Il est conseillé de le mettre à jour manuellement.")
        return result['access_token']
    else:
        error_description = result.get('error_description', "Aucune description d'erreur fournie.")
        error_code = result.get('error', "Aucun code d'erreur fourni.")
        app.logger.error(f"Erreur lors de l'acquisition du token Graph API: {error_code} - {error_description}")
        app.logger.error(f"Détails complets de l'erreur MSAL: {result}")
        return None

def ensure_onedrive_folder(access_token):
    headers = {'Authorization': 'Bearer ' + access_token, 'Content-Type': 'application/json'}
    folder_check_url = f"https://graph.microsoft.com/v1.0/me/drive/items/{ONEDRIVE_TARGET_PARENT_FOLDER_ID}/children?$filter=name eq '{ONEDRIVE_TARGET_SUBFOLDER_NAME}'"
    try:
        response = requests.get(folder_check_url, headers=headers)
        response.raise_for_status()
        children = response.json().get('value', [])
        if children:
            folder_id = children[0]['id']
            app.logger.info(f"Dossier OneDrive '{ONEDRIVE_TARGET_SUBFOLDER_NAME}' trouvé avec ID: {folder_id}")
            return folder_id
        else:
            app.logger.info(f"Dossier OneDrive '{ONEDRIVE_TARGET_SUBFOLDER_NAME}' non trouvé. Tentative de création.")
            folder_create_url = f"https://graph.microsoft.com/v1.0/me/drive/items/{ONEDRIVE_TARGET_PARENT_FOLDER_ID}/children"
            payload = {
                "name": ONEDRIVE_TARGET_SUBFOLDER_NAME,
                "folder": {},
                "@microsoft.graph.conflictBehavior": "rename"
            }
            response_create = requests.post(folder_create_url, headers=headers, json=payload)
            response_create.raise_for_status()
            folder_id = response_create.json()['id']
            app.logger.info(f"Dossier OneDrive '{ONEDRIVE_TARGET_SUBFOLDER_NAME}' créé avec ID: {folder_id}")
            return folder_id
    except requests.exceptions.RequestException as e:
        app.logger.error(f"Erreur API Graph lors de la vérification/création du dossier OneDrive: {e}")
        if hasattr(e, 'response') and e.response is not None:
            app.logger.error(f"Réponse de l'API Graph: {e.response.status_code} - {e.response.text}")
        return None

def upload_to_onedrive(filepath, filename_onedrive, access_token, target_folder_id):
    if not access_token or not target_folder_id:
        app.logger.error("Token d'accès OneDrive ou ID dossier cible manquant pour l'upload.")
        return False

    upload_url_simple_put = f"https://graph.microsoft.com/v1.0/me/drive/items/{target_folder_id}:/{filename_onedrive}:/content"
    headers_put = {'Authorization': 'Bearer ' + access_token, 'Content-Type': 'application/octet-stream'}
    file_size = os.path.getsize(filepath)
    app.logger.info(f"Tentative d'upload de '{filepath.name}' ({file_size} bytes) vers OneDrive folder ID {target_folder_id} sous le nom '{filename_onedrive}'")
    final_response = None

    try:
        if file_size < 4 * 1024 * 1024: # Petits fichiers (< 4MB)
            with open(filepath, 'rb') as f_data:
                response = requests.put(upload_url_simple_put, headers=headers_put, data=f_data)
                response.raise_for_status()
                final_response = response
        else: # Gros fichiers, session d'upload
            create_session_url = f"https://graph.microsoft.com/v1.0/me/drive/items/{target_folder_id}:/{filename_onedrive}:/createUploadSession"
            session_payload = {"item": {"@microsoft.graph.conflictBehavior": "rename"}}
            session_headers = {'Authorization': 'Bearer ' + access_token, 'Content-Type': 'application/json'}
            session_response = requests.post(create_session_url, headers=session_headers, json=session_payload)
            session_response.raise_for_status()
            upload_session_url = session_response.json()['uploadUrl']
            app.logger.info(f"Session d'upload OneDrive créée: {upload_session_url}")
            chunk_size = 5 * 1024 * 1024 # 5MB
            chunks_uploaded_count = 0
            with open(filepath, 'rb') as f_data:
                while True:
                    chunk = f_data.read(chunk_size)
                    if not chunk: break
                    start_byte = chunks_uploaded_count * chunk_size
                    end_byte = start_byte + len(chunk) - 1
                    chunk_headers = {'Content-Length': str(len(chunk)), 'Content-Range': f'bytes {start_byte}-{end_byte}/{file_size}'}
                    app.logger.info(f"Upload du chunk: bytes {start_byte}-{end_byte}/{file_size}")
                    response_chunk = requests.put(upload_session_url, headers=chunk_headers, data=chunk)
                    response_chunk.raise_for_status()
                    final_response = response_chunk
                    chunks_uploaded_count += 1
            app.logger.info(f"Tous les chunks de '{filepath.name}' uploadés.")

        if final_response and final_response.status_code < 300:
            app.logger.info(f"Fichier '{filename_onedrive}' uploadé avec succès sur OneDrive. Réponse: {final_response.status_code}")
            return True
        else:
            app.logger.error(f"Erreur inattendue après l'upload OneDrive ({filename_onedrive}). Status: {final_response.status_code if final_response else 'N/A'}")
            return False
    except requests.exceptions.RequestException as e:
        app.logger.error(f"Erreur API Graph lors de l'upload vers OneDrive ({filename_onedrive}): {e}")
        if hasattr(e, 'response') and e.response is not None:
            app.logger.error(f"Réponse de l'API Graph: {e.response.status_code} - {e.response.text}")
            if e.response.status_code == 401:
                 app.logger.error("L'erreur 401 Unauthorized suggère un problème avec le token d'accès.")
            if 'upload_session_url' in locals() and file_size >= 4 * 1024 * 1024:
                app.logger.info(f"Tentative d'annulation de la session d'upload: {upload_session_url}")
                requests.delete(upload_session_url, headers={'Authorization': 'Bearer ' + access_token})
        return False
    except Exception as ex:
        app.logger.error(f"Erreur générale inattendue pendant l'upload OneDrive ({filename_onedrive}): {ex}", exc_info=True)
        return False

def download_and_relay_to_onedrive(dropbox_url):
    modified_url = dropbox_url.replace("dl=0", "dl=1")
    modified_url = re.sub(r'dl=[^&]+', 'dl=1', modified_url)
    app.logger.info(f"Dropbox: Téléchargement depuis {modified_url}")
    temp_filepath = None 

    try:
        response = requests.get(modified_url, stream=True, allow_redirects=True, timeout=300)
        response.raise_for_status()

        filename_dropbox = "downloaded_file_from_dropbox"
        content_disposition = response.headers.get('content-disposition')
        if content_disposition:
            fn_match = re.search(r'filename\*?=(?:UTF-8\'\')?([^;\n\r"]+)', content_disposition, flags=re.IGNORECASE)
            if fn_match:
                filename_dropbox = requests.utils.unquote(fn_match.group(1)).strip('"')
            else:
                fn_match_simple = re.findall('filename="?(.+?)"?(?:;|$)', content_disposition)
                if fn_match_simple: filename_dropbox = fn_match_simple[0]

        filename_onedrive = re.sub(r'[<>:"/\\|?*]', '_', filename_dropbox)
        filename_onedrive = filename_onedrive[:200]
        temp_filepath = DOWNLOAD_TEMP_DIR_RENDER / filename_onedrive

        with open(temp_filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192 * 4):
                f.write(chunk)
        app.logger.info(f"Dropbox: Téléchargé '{filename_dropbox}' vers '{temp_filepath}'")

        access_token_graph = get_onedrive_access_token()
        if access_token_graph:
            target_folder_id = ensure_onedrive_folder(access_token_graph)
            if target_folder_id:
                if upload_to_onedrive(temp_filepath, filename_onedrive, access_token_graph, target_folder_id):
                    app.logger.info(f"OneDrive: Succès upload de '{filename_onedrive}'")
                    if temp_filepath and temp_filepath.exists(): temp_filepath.unlink()
                    return True
                else:
                    app.logger.error(f"OneDrive: Échec upload de '{filename_onedrive}'")
            else:
                app.logger.error("OneDrive: Impossible d'obtenir/créer le dossier cible.")
        else:
            app.logger.error("OneDrive: Impossible d'obtenir le token d'accès Graph API.")
        
        return False

    except requests.exceptions.Timeout:
        app.logger.error(f"Dropbox: Timeout lors du téléchargement pour {modified_url}")
        return False
    except requests.exceptions.RequestException as e:
        app.logger.error(f"Dropbox: Erreur de téléchargement pour {modified_url}: {e}")
        if hasattr(e, 'response') and e.response is not None:
            app.logger.error(f"Réponse de Dropbox: {e.response.status_code} - {e.response.text}")
        return False
    except Exception as e_main:
        app.logger.error(f"Erreur générale dans download_and_relay_to_onedrive pour {dropbox_url}: {e_main}", exc_info=True)
        if temp_filepath and temp_filepath.exists():
             app.logger.info(f"Le fichier temporaire {temp_filepath} est conservé suite à l'erreur.")
        return False

# --- Nouvelle fonction pour vérifier les emails via Microsoft Graph API ---
def check_emails_via_graph_and_download():
    app.logger.info("Déclenchement vérification emails via Graph API et téléchargement Dropbox.")
    
    access_token = get_onedrive_access_token()
    if not access_token:
        app.logger.error("Impossible d'obtenir un token d'accès Graph API pour lire les emails.")
        return -1 

    if not SENDER_OF_INTEREST:
        app.logger.error("SENDER_OF_INTEREST n'est pas configuré. Impossible de filtrer les emails.")
        return -1

    headers = {'Authorization': 'Bearer ' + access_token, 'Content-Type': 'application/json'}
    filter_query = f"$filter=from/emailAddress/address eq '{SENDER_OF_INTEREST}' and isRead eq false"
    messages_url = f"https://graph.microsoft.com/v1.0/me/mailFolders/inbox/messages?{filter_query}&$orderBy=receivedDateTime desc&$top=20"
    
    num_downloaded_total = 0
    processed_graph_email_ids = get_processed_email_ids()

    try:
        response = requests.get(messages_url, headers=headers)
        response.raise_for_status()
        emails_data = response.json().get('value', [])
        app.logger.info(f"Trouvé {len(emails_data)} email(s) potentiels de '{SENDER_OF_INTEREST}' via Graph API (non lus, top 20).")

        for email_item in emails_data:
            email_id_graph = email_item['id']
            if email_id_graph in processed_graph_email_ids:
                continue
            
            subject = email_item.get('subject', "N/A")
            app.logger.info(f"Traitement Email Graph ID: {email_id_graph}, Sujet: {subject}")
            
            body_content = email_item.get('body', {}).get('content', '')
            if not body_content:
                body_content = email_item.get('bodyPreview', '')
            
            if body_content:
                links_found = find_dropbox_links(body_content)
                if links_found:
                    app.logger.info(f"Email Graph ID {email_id_graph}: Liens Dropbox trouvés: {links_found}")
                    for link in links_found:
                        if not download_and_relay_to_onedrive(link):
                            app.logger.error(f"Échec du traitement du lien {link} pour l'email Graph ID {email_id_graph}")
                        else:
                            num_downloaded_total += 1
                    
                    add_processed_email_id(email_id_graph)
                    mark_as_read_url = f"https://graph.microsoft.com/v1.0/me/messages/{email_id_graph}"
                    patch_payload = {"isRead": True}
                    try:
                        mark_response = requests.patch(mark_as_read_url, headers=headers, json=patch_payload)
                        mark_response.raise_for_status()
                        app.logger.info(f"Email Graph ID {email_id_graph} marqué comme lu.")
                    except requests.exceptions.RequestException as e_mark:
                        app.logger.warning(f"Échec du marquage comme lu pour l'email Graph ID {email_id_graph}: {e_mark}")
                else:
                    app.logger.info(f"Email Graph ID {email_id_graph}: Aucun lien Dropbox trouvé.")
                    add_processed_email_id(email_id_graph)
            else:
                app.logger.warning(f"Email Graph ID {email_id_graph}: Corps de l'email vide.")
                add_processed_email_id(email_id_graph)

    except requests.exceptions.RequestException as e_graph:
        app.logger.error(f"Erreur API Graph lors de la lecture des emails: {e_graph}")
        if hasattr(e_graph, 'response') and e_graph.response is not None:
            app.logger.error(f"Réponse API Graph: {e_graph.response.status_code} - {e_graph.response.text}")
        return -1
    except Exception as ex_general:
        app.logger.error(f"Erreur inattendue pendant la lecture des emails via Graph API: {ex_general}", exc_info=True)
        return -1

    return num_downloaded_total

# --- Endpoint pour Déclencher la Vérification des Emails (maintenant via Graph API) ---
@app.route('/api/check_emails_and_download', methods=['POST'])
def api_check_emails_and_download():
    app.logger.info("API: Déclenchement de la vérification des emails (via Graph API) et téléchargement.")
    
    lock_file = SIGNAL_DIR / "email_check.lock"
    if lock_file.exists():
        try:
            if time.time() - lock_file.stat().st_mtime < 300:
                 app.logger.warning("Vérification des emails déjà en cours (lock file récent).")
                 return jsonify({"status": "busy", "message": "Vérification des emails déjà en cours."}), 429
            else:
                app.logger.warning("Ancien lock file trouvé, suppression et poursuite.")
                lock_file.unlink(missing_ok=True)
        except OSError as e:
            app.logger.error(f"Erreur avec le lock file {lock_file}: {e}")

    try:
        lock_file.touch()
    except OSError as e:
        app.logger.error(f"Impossible de créer le lock file {lock_file}: {e}")
        return jsonify({"status": "error", "message": "Erreur interne (lock file)"}), 500

    num_downloaded = 0
    try:
        if not all([ONEDRIVE_CLIENT_ID, ONEDRIVE_CLIENT_SECRET, ONEDRIVE_REFRESH_TOKEN, SENDER_OF_INTEREST]):
            msg = "Configuration Graph API ou SENDER_OF_INTEREST incomplète."
            app.logger.error(msg)
            if lock_file.exists(): lock_file.unlink(missing_ok=True)
            return jsonify({"status": "error", "message": msg}), 500

        num_downloaded = check_emails_via_graph_and_download()

        if num_downloaded == -1:
            msg = "Une erreur est survenue pendant la vérification des emails via Graph API."
            status_code = 500
        else:
            msg = f"Vérification emails (Graph API) terminée. {num_downloaded} nouveau(x) fichier(s) transféré(s) vers OneDrive."
            status_code = 200
        
        app.logger.info(msg)
        if lock_file.exists(): lock_file.unlink(missing_ok=True)
        return jsonify({"status": "success" if status_code==200 else "error", "message": msg, "files_downloaded": num_downloaded if num_downloaded !=-1 else 0}), status_code

    except Exception as e:
        app.logger.error(f"Erreur inattendue dans l'endpoint /api/check_emails_and_download: {e}", exc_info=True)
        if lock_file.exists(): lock_file.unlink(missing_ok=True)
        return jsonify({"status": "error", "message": f"Erreur inattendue: {str(e)}"}), 500

# --- Nouvelle Route Principale pour servir trigger_page.html ---
@app.route('/')
def serve_trigger_page():
    app.logger.info("Route '/' appelée. Tentative de servir 'trigger_page.html'.")
    directory_to_serve_from = '.' 
    file_to_serve = 'trigger_page.html'
    expected_file_location = Path(current_app.root_path) / directory_to_serve_from / file_to_serve
    
    if not expected_file_location.is_file():
        app.logger.error(f"ERREUR: '{file_to_serve}' NON TROUVÉ à: {expected_file_location.resolve()}")
        try:
            content_list = os.listdir(Path(current_app.root_path) / directory_to_serve_from)
            app.logger.info(f"Contenu du dossier '{Path(current_app.root_path) / directory_to_serve_from}': {content_list}")
        except Exception as e_ls: app.logger.error(f"Impossible de lister le contenu du dossier: {e_ls}")
        return "Erreur: Fichier principal de l'interface non trouvé. Vérifiez les logs.", 404
    try:
        return send_from_directory(directory_to_serve_from, file_to_serve)
    except Exception as e_send:
        app.logger.error(f"Erreur send_from_directory pour '{file_to_serve}': {e_send}", exc_info=True)
        return "Erreur interne du serveur lors de la tentative de servir la page.", 500

# --- Endpoints API de base (pour la gestion des signaux et statuts) ---
@app.route('/api/trigger_workflow', methods=['POST'])
def trigger_workflow():
    timestamp = time.time()
    with open(TRIGGER_SIGNAL_FILE, "w") as f: f.write(str(timestamp))
    app.logger.info(f"Workflow triggered via API at {timestamp}. Signal file updated.")
    return jsonify({"status": "success", "message": "Workflow triggered", "timestamp": timestamp})

@app.route('/api/check_trigger', methods=['GET'])
def check_trigger():
    if TRIGGER_SIGNAL_FILE.exists():
        try:
            timestamp = TRIGGER_SIGNAL_FILE.read_text()
            TRIGGER_SIGNAL_FILE.unlink() 
            app.logger.info(f"Trigger signal consumed. Timestamp: {timestamp}")
            return jsonify({"triggered": True, "timestamp": float(timestamp)})
        except Exception as e:
            app.logger.error(f"Error processing trigger signal file: {e}")
            return jsonify({"triggered": False, "error": str(e)}), 500
    return jsonify({"triggered": False})

@app.route('/api/update_local_status', methods=['POST'])
def update_local_status():
    data = request.json
    with open(LOCAL_STATUS_FILE, "w") as f: json.dump(data, f)
    app.logger.info(f"Local status updated: {data}")
    return jsonify({"status": "success", "message": "Local status updated"})

@app.route('/api/get_local_status', methods=['GET'])
def get_local_status():
    if LOCAL_STATUS_FILE.exists():
        with open(LOCAL_STATUS_FILE, "r") as f: status_data = json.load(f)
        return jsonify(status_data)
    return jsonify({"status": "idle", "message": "No local status file found."})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=os.environ.get('FLASK_DEBUG', 'False').lower() == 'true')
