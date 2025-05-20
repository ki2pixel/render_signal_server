from flask import Flask, jsonify, request, send_from_directory, current_app
import os
import time
from pathlib import Path
import json
import logging
import re 
import html as html_parser 
import requests 
import threading # Ajout pour le traitement en arrière-plan

from msal import ConfidentialClientApplication

app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Config Fichiers ---
SIGNAL_DIR = Path(os.environ.get("RENDER_DISC_PATH", "./signal_data"))
DOWNLOAD_TEMP_DIR_RENDER = SIGNAL_DIR / "temp_downloads"
PROCESSED_DROPBOX_URLS_ONEDRIVE_FILENAME = "processed_dropbox_urls_workflow.txt"
TRIGGER_SIGNAL_FILE = SIGNAL_DIR / "local_workflow_trigger_signal.json" 

SIGNAL_DIR.mkdir(parents=True, exist_ok=True)
DOWNLOAD_TEMP_DIR_RENDER.mkdir(parents=True, exist_ok=True)

# --- Config API Microsoft Graph (OneDrive) ---
ONEDRIVE_CLIENT_ID = os.environ.get('ONEDRIVE_CLIENT_ID')
ONEDRIVE_CLIENT_SECRET = os.environ.get('ONEDRIVE_CLIENT_SECRET')
ONEDRIVE_REFRESH_TOKEN = os.environ.get('ONEDRIVE_REFRESH_TOKEN')
ONEDRIVE_AUTHORITY = "https://login.microsoftonline.com/consumers"
ONEDRIVE_SCOPES_DELEGATED = ["Files.ReadWrite", "User.Read"]
ONEDRIVE_TARGET_PARENT_FOLDER_ID = os.environ.get('ONEDRIVE_TARGET_PARENT_FOLDER_ID', 'root')
ONEDRIVE_TARGET_SUBFOLDER_NAME = os.environ.get('ONEDRIVE_TARGET_SUBFOLDER_NAME', "DropboxDownloadsWorkflow")

# --- Config Sécurité API pour le Workflow B (Make.com) ---
EXPECTED_API_TOKEN = os.environ.get("PROCESS_API_TOKEN") 
if not EXPECTED_API_TOKEN:
    app.logger.warning("CRITICAL SECURITY WARNING: La variable d'environnement PROCESS_API_TOKEN n'est pas définie.")
app.logger.info(f"CONFIGURATION: Token attendu pour /api/process_individual_dropbox_link (PROCESS_API_TOKEN): '{EXPECTED_API_TOKEN}'")

msal_app = None
if ONEDRIVE_CLIENT_ID and ONEDRIVE_CLIENT_SECRET:
    app.logger.info(f"Configuration de MSAL avec Client ID et Authority: {ONEDRIVE_AUTHORITY}")
    msal_app = ConfidentialClientApplication(
        ONEDRIVE_CLIENT_ID,
        authority=ONEDRIVE_AUTHORITY,
        client_credential=ONEDRIVE_CLIENT_SECRET
    )
else:
    app.logger.warning("ONEDRIVE_CLIENT_ID ou ONEDRIVE_CLIENT_SECRET manquant. Intégration Graph désactivée.")

# --- Fonctions Utilitaires ---
def sanitize_filename(filename_str, max_length=230): # Limite OneDrive un peu plus basse pour la sécurité
    sanitized = re.sub(r'[<>:"/\\|?*]', '_', filename_str)
    sanitized = re.sub(r'\.+', '.', sanitized).strip('.')
    if not sanitized: # Si le nom devient vide
        sanitized = "fichier_sans_nom"
    return sanitized[:max_length]

def get_onedrive_access_token():
    # (Identique à la version précédente)
    if not msal_app: app.logger.error("MSAL non configuré."); return None
    if not ONEDRIVE_REFRESH_TOKEN: app.logger.error("ONEDRIVE_REFRESH_TOKEN manquant."); return None
    app.logger.info(f"Acquisition token Graph API pour scopes: {ONEDRIVE_SCOPES_DELEGATED}")
    result = msal_app.acquire_token_by_refresh_token(ONEDRIVE_REFRESH_TOKEN, scopes=ONEDRIVE_SCOPES_DELEGATED)
    if "access_token" in result:
        app.logger.info("Token d'accès Graph API obtenu.")
        if result.get("refresh_token") and result.get("refresh_token") != ONEDRIVE_REFRESH_TOKEN:
             app.logger.warning("Nouveau refresh token Graph API émis. Mettez à jour ONEDRIVE_REFRESH_TOKEN.")
        return result['access_token']
    else:
        app.logger.error(f"Erreur acquisition token: {result.get('error')} - {result.get('error_description')}")
        app.logger.error(f"Détails erreur MSAL: {result}")
        return None

def ensure_onedrive_folder(access_token):
    # (Identique à la version précédente)
    headers = {'Authorization': 'Bearer ' + access_token, 'Content-Type': 'application/json'}
    parent_id = ONEDRIVE_TARGET_PARENT_FOLDER_ID if ONEDRIVE_TARGET_PARENT_FOLDER_ID and ONEDRIVE_TARGET_PARENT_FOLDER_ID.lower() != 'root' else 'root'
    subfolder_name_clean = sanitize_filename(ONEDRIVE_TARGET_SUBFOLDER_NAME, 100) # Nettoyer aussi le nom du sous-dossier

    if parent_id == 'root':
        folder_check_url = f"https://graph.microsoft.com/v1.0/me/drive/root/children?$filter=name eq '{subfolder_name_clean}'"
        folder_create_url = f"https://graph.microsoft.com/v1.0/me/drive/root/children"
    else:
        folder_check_url = f"https://graph.microsoft.com/v1.0/me/drive/items/{parent_id}/children?$filter=name eq '{subfolder_name_clean}'"
        folder_create_url = f"https://graph.microsoft.com/v1.0/me/drive/items/{parent_id}/children"
    try:
        response = requests.get(folder_check_url, headers=headers)
        response.raise_for_status()
        children = response.json().get('value', [])
        if children:
            folder_id = children[0]['id']
            app.logger.info(f"Dossier OneDrive '{subfolder_name_clean}' trouvé ID: {folder_id}")
            return folder_id
        else:
            app.logger.info(f"Dossier OneDrive '{subfolder_name_clean}' non trouvé. Création.")
            payload = {"name": subfolder_name_clean, "folder": {}, "@microsoft.graph.conflictBehavior": "rename"}
            response_create = requests.post(folder_create_url, headers=headers, json=payload)
            response_create.raise_for_status()
            folder_id = response_create.json()['id']
            app.logger.info(f"Dossier OneDrive '{subfolder_name_clean}' créé ID: {folder_id}")
            return folder_id
    except requests.exceptions.RequestException as e:
        app.logger.error(f"Erreur API Graph dossier OneDrive '{subfolder_name_clean}': {e}")
        if hasattr(e, 'response') and e.response is not None: app.logger.error(f"Réponse API: {e.response.status_code} - {e.response.text}")
        return None

def upload_to_onedrive(filepath, filename_onedrive, access_token, target_folder_id):
    # (Globalement identique, juste s'assurer que filename_onedrive est déjà nettoyé)
    if not access_token or not target_folder_id: app.logger.error("Upload: Token ou ID dossier manquant."); return False
    
    # filename_onedrive devrait déjà être nettoyé par la fonction appelante
    # mais une dernière vérification ne fait pas de mal.
    filename_onedrive_clean = sanitize_filename(filename_onedrive)

    upload_url_simple_put = f"https://graph.microsoft.com/v1.0/me/drive/items/{target_folder_id}:/{filename_onedrive_clean}:/content?@microsoft.graph.conflictBehavior=rename"
    headers_put = {'Authorization': 'Bearer ' + access_token, 'Content-Type': 'application/octet-stream'}
    file_size = os.path.getsize(filepath)
    app.logger.info(f"Upload de '{filepath.name}' ({file_size}b) vers OneDrive '{filename_onedrive_clean}'")
    final_response = None
    try:
        if file_size < 4 * 1024 * 1024:
            with open(filepath, 'rb') as f_data:
                response = requests.put(upload_url_simple_put, headers=headers_put, data=f_data)
                response.raise_for_status()
                final_response = response
        else:
            create_session_url = f"https://graph.microsoft.com/v1.0/me/drive/items/{target_folder_id}:/{filename_onedrive_clean}:/createUploadSession"
            session_payload = {"item": {"@microsoft.graph.conflictBehavior": "rename"}}
            session_headers = {'Authorization': 'Bearer ' + access_token, 'Content-Type': 'application/json'}
            session_response = requests.post(create_session_url, headers=session_headers, json=session_payload)
            session_response.raise_for_status()
            upload_session_url = session_response.json()['uploadUrl']
            app.logger.info(f"Session d'upload OneDrive créée.")
            chunk_size = 10 * 1024 * 1024 # 10MB chunks
            chunks_uploaded_count = 0
            with open(filepath, 'rb') as f_data:
                while True:
                    chunk = f_data.read(chunk_size)
                    if not chunk: break
                    start_byte = chunks_uploaded_count * chunk_size
                    end_byte = start_byte + len(chunk) - 1
                    chunk_headers = {'Content-Length': str(len(chunk)), 'Content-Range': f'bytes {start_byte}-{end_byte}/{file_size}'}
                    app.logger.info(f"Upload chunk: bytes {start_byte}-{end_byte}/{file_size}")
                    response_chunk = requests.put(upload_session_url, headers=chunk_headers, data=chunk)
                    response_chunk.raise_for_status()
                    final_response = response_chunk # Pour le statut final
                    chunks_uploaded_count += 1
            app.logger.info(f"Tous les chunks de '{filepath.name}' uploadés.")
        if final_response and final_response.status_code < 300:
            app.logger.info(f"Fichier '{filename_onedrive_clean}' uploadé avec succès. Statut: {final_response.status_code}")
            return True
        else:
            app.logger.error(f"Erreur après upload ({filename_onedrive_clean}). Statut: {final_response.status_code if final_response else 'N/A'}")
            return False
    except requests.exceptions.RequestException as e:
        app.logger.error(f"Erreur API Graph upload ({filename_onedrive_clean}): {e}")
        if hasattr(e, 'response') and e.response is not None: app.logger.error(f"Réponse API: {e.response.status_code} - {e.response.text}")
        if 'upload_session_url' in locals() and file_size >= 4 * 1024 * 1024:
            requests.delete(upload_session_url, headers={'Authorization': 'Bearer ' + access_token}) 
        return False
    except Exception as ex:
        app.logger.error(f"Erreur générale upload ({filename_onedrive_clean}): {ex}", exc_info=True)
        return False

# MODIFIED: download_and_relay_to_onedrive
def download_file_from_dropbox_and_upload_to_onedrive(dropbox_url, access_token_graph, target_folder_id_onedrive, subject_for_default_filename="FichierDropbox"):
    app.logger.info(f"WORKER: Traitement URL Dropbox: {dropbox_url}")
    unescaped_url = html_parser.unescape(dropbox_url)
    modified_url = unescaped_url.replace("dl=0", "dl=1")
    modified_url = re.sub(r'dl=[^&?#]+', 'dl=1', modified_url)
    if '?dl=1' not in modified_url and '&dl=1' not in modified_url:
        modified_url += ("&" if "?" in modified_url else "?") + "dl=1"
    
    app.logger.info(f"WORKER: URL Dropbox finale pour téléchargement: {modified_url}")
    temp_filepath = None

    # Construire un nom de fichier par défaut au cas où Content-Disposition serait manquant
    ts = time.strftime('%Y%m%d-%H%M%S')
    default_filename_base = sanitize_filename(subject_for_default_filename, 180)
    default_filename_with_ts = f"{default_filename_base}_{ts}. téléchargement" # Extension générique

    try:
        headers_db = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response_db = requests.get(modified_url, stream=True, allow_redirects=True, timeout=900, headers=headers_db) # Timeout 15 min pour DL
        response_db.raise_for_status()

        filename_for_onedrive = default_filename_with_ts # Utiliser le nom par défaut initialement
        content_disp = response_db.headers.get('content-disposition')
        
        if content_disp:
            app.logger.info(f"WORKER: Content-Disposition Dropbox: '{content_disp}'")
            # Priorité à filename* (UTF-8)
            m_utf8 = re.search(r"filename\*=UTF-8''([^;\n\r]+)", content_disp, flags=re.IGNORECASE)
            if m_utf8:
                filename_from_cd = requests.utils.unquote(m_utf8.group(1))
                app.logger.info(f"WORKER: Nom de fichier (filename* UTF-8) extrait: '{filename_from_cd}'")
            else:
                # Fallback à filename="...", moins fiable pour les caractères spéciaux
                m_simple = re.search(r'filename="([^"]+)"', content_disp, flags=re.IGNORECASE)
                if m_simple:
                    filename_from_cd = m_simple.group(1)
                    # Essayer de décoder si ça ressemble à du %-encoding, sinon garder tel quel
                    if '%' in filename_from_cd:
                        try: filename_from_cd = requests.utils.unquote(filename_from_cd)
                        except Exception: pass # Garder tel quel si unquote échoue
                    app.logger.info(f"WORKER: Nom de fichier (filename=\"\") extrait: '{filename_from_cd}'")
                else:
                    app.logger.warning(f"WORKER: Impossible de parser 'filename' ou 'filename*' dans Content-Disposition. Utilisation du nom par défaut.")
                    filename_from_cd = None # Pour forcer l'utilisation du nom par défaut

            if filename_from_cd: # Si un nom a été extrait du Content-Disposition
                filename_for_onedrive = sanitize_filename(filename_from_cd)
                # Heuristique pour les dossiers Dropbox (qui sont zippés)
                is_dropbox_folder_link = "dropbox.com/scl/fo/" in unescaped_url
                has_archive_extension = any(filename_for_onedrive.lower().endswith(ext) for ext in ['.zip', '.rar', '.7z'])
                if is_dropbox_folder_link and not has_archive_extension:
                    name_part, _ = os.path.splitext(filename_for_onedrive)
                    filename_for_onedrive = name_part + ".zip"
                    app.logger.info(f"WORKER: Lien de dossier Dropbox détecté, ajout de .zip. Nom final: '{filename_for_onedrive}'")
        else:
            app.logger.warning(f"WORKER: Content-Disposition Dropbox non trouvé. Utilisation du nom par défaut: '{filename_for_onedrive}'")

        if not filename_for_onedrive: # Double sécurité si tout a échoué
             filename_for_onedrive = f"fichier_dropbox_{ts}.bin"

        temp_filepath = DOWNLOAD_TEMP_DIR_RENDER / filename_for_onedrive # Utiliser le nom final pour le temp

        app.logger.info(f"WORKER: Téléchargement Dropbox vers fichier temporaire: '{temp_filepath}'")
        with open(temp_filepath, 'wb') as f:
            for chunk in response_db.iter_content(chunk_size=1024*1024*2): # Chunks de 2MB
                f.write(chunk)
        app.logger.info(f"WORKER: Fichier Dropbox téléchargé avec succès vers '{temp_filepath.name}'.")

        if upload_to_onedrive(temp_filepath, filename_for_onedrive, access_token_graph, target_folder_id_onedrive):
            app.logger.info(f"WORKER: Upload vers OneDrive de '{filename_for_onedrive}' réussi.")
            return True
        else:
            app.logger.error(f"WORKER: Échec de l'upload de '{filename_for_onedrive}' vers OneDrive.")
            return False

    except requests.exceptions.Timeout:
        app.logger.error(f"WORKER: Timeout Dropbox lors du téléchargement de {modified_url}")
        return False
    except requests.exceptions.RequestException as e:
        app.logger.error(f"WORKER: Erreur de requête Dropbox {modified_url}: {e}")
        if hasattr(e, 'response') and e.response is not None: app.logger.error(f"WORKER: Réponse Dropbox: {e.response.status_code} - {e.response.text[:500]}...")
        return False
    except Exception as e_main:
        app.logger.error(f"WORKER: Erreur générale dans download_file_from_dropbox_and_upload_to_onedrive pour {dropbox_url}: {e_main}", exc_info=True)
        return False
    finally:
        if temp_filepath and temp_filepath.exists():
            try:
                temp_filepath.unlink()
                app.logger.info(f"WORKER: Fichier temporaire '{temp_filepath.name}' supprimé.")
            except OSError as e_unlink:
                app.logger.error(f"WORKER: Erreur suppression fichier temporaire '{temp_filepath.name}': {e_unlink}")


def get_processed_urls_from_onedrive(access_token, target_folder_id):
    # (Identique à la version précédente)
    if not access_token or not target_folder_id: return set()
    download_url = f"https://graph.microsoft.com/v1.0/me/drive/items/{target_folder_id}:/{PROCESSED_DROPBOX_URLS_ONEDRIVE_FILENAME}:/content"
    headers = {'Authorization': 'Bearer ' + access_token}
    processed_urls = set(); app.logger.debug(f"Tentative de lecture de {PROCESSED_DROPBOX_URLS_ONEDRIVE_FILENAME}")
    try:
        response = requests.get(download_url, headers=headers)
        if response.status_code == 200:
            lines = response.text.splitlines()
            for line in lines:
                if line.strip(): processed_urls.add(line.strip())
            app.logger.info(f"Lu {len(processed_urls)} URLs depuis {PROCESSED_DROPBOX_URLS_ONEDRIVE_FILENAME}.")
        elif response.status_code == 404:
            app.logger.info(f"{PROCESSED_DROPBOX_URLS_ONEDRIVE_FILENAME} non trouvé. Initialisation.")
        else: response.raise_for_status()
    except requests.exceptions.RequestException as e:
        app.logger.error(f"Erreur téléchargement {PROCESSED_DROPBOX_URLS_ONEDRIVE_FILENAME}: {e}")
        if hasattr(e, 'response') and e.response is not None: app.logger.error(f"Réponse API: {e.response.status_code} - {e.response.text}")
    return processed_urls

def update_processed_urls_on_onedrive(access_token, target_folder_id, urls_to_write_set):
    # (Identique à la version précédente)
    if not access_token or not target_folder_id: return False
    content_to_upload = "\n".join(sorted(list(urls_to_write_set))) if urls_to_write_set else ""
    upload_url = f"https://graph.microsoft.com/v1.0/me/drive/items/{target_folder_id}:/{PROCESSED_DROPBOX_URLS_ONEDRIVE_FILENAME}:/content?@microsoft.graph.conflictBehavior=replace"
    headers = {'Authorization': 'Bearer ' + access_token, 'Content-Type': 'text/plain; charset=utf-8'}
    try:
        response = requests.put(upload_url, headers=headers, data=content_to_upload.encode('utf-8'))
        response.raise_for_status()
        app.logger.info(f"{PROCESSED_DROPBOX_URLS_ONEDRIVE_FILENAME} mis à jour avec {len(urls_to_write_set)} URLs.")
        return True
    except requests.exceptions.RequestException as e:
        app.logger.error(f"Erreur upload {PROCESSED_DROPBOX_URLS_ONEDRIVE_FILENAME}: {e}")
        if hasattr(e, 'response') and e.response is not None: app.logger.error(f"Réponse API: {e.response.status_code} - {e.response.text}")
        return False
# --- FIN Fonctions Utilitaires ---

# --- WORKER THREAD POUR LE TRAITEMENT DROPBOX -> ONEDRIVE ---
def process_dropbox_link_worker(dropbox_url, subject_for_default_filename, email_id_for_logging):
    """Fonction exécutée dans un thread séparé pour gérer le transfert."""
    app.logger.info(f"WORKER_THREAD: Démarrage pour URL: {dropbox_url}, Sujet Fallback: {subject_for_default_filename}, EmailID: {email_id_for_logging}")
    
    access_token_graph = get_onedrive_access_token()
    if not access_token_graph:
        app.logger.error(f"WORKER_THREAD: Échec obtention token Graph pour {dropbox_url}. Arrêt.")
        return

    target_folder_id_onedrive = ensure_onedrive_folder(access_token_graph)
    if not target_folder_id_onedrive:
        app.logger.error(f"WORKER_THREAD: Échec création/vérification dossier OneDrive pour {dropbox_url}. Arrêt.")
        return

    # La vérification des URLs déjà traitées se fait maintenant ici, dans le worker, avant le long téléchargement.
    processed_urls = get_processed_urls_from_onedrive(access_token_graph, target_folder_id_onedrive)
    if dropbox_url in processed_urls:
        app.logger.info(f"WORKER_THREAD: URL {dropbox_url} déjà traitée (vérifié dans le worker). Ignorée.")
        return # Pas besoin de continuer

    app.logger.info(f"WORKER_THREAD: URL {dropbox_url} est nouvelle. Lancement du transfert.")
    success_transfer = download_file_from_dropbox_and_upload_to_onedrive(
        dropbox_url, 
        access_token_graph, 
        target_folder_id_onedrive,
        subject_for_default_filename=subject_for_default_filename
    )

    if success_transfer:
        app.logger.info(f"WORKER_THREAD: Transfert réussi pour {dropbox_url}. Mise à jour de la liste des URLs traitées.")
        # Lire à nouveau au cas où un autre worker aurait écrit entre-temps (peu probable mais plus sûr)
        current_processed_urls = get_processed_urls_from_onedrive(access_token_graph, target_folder_id_onedrive)
        current_processed_urls.add(dropbox_url)
        if not update_processed_urls_on_onedrive(access_token_graph, target_folder_id_onedrive, current_processed_urls):
            app.logger.error(f"WORKER_THREAD: ÉCHEC CRITIQUE - Fichier {dropbox_url} transféré mais impossible de mettre à jour {PROCESSED_DROPBOX_URLS_ONEDRIVE_FILENAME}.")
    else:
        app.logger.error(f"WORKER_THREAD: Échec du transfert pour {dropbox_url}.")
    app.logger.info(f"WORKER_THREAD: Fin de tâche pour URL: {dropbox_url}")


# --- ENDPOINT PRINCIPAL pour WORKFLOW B (Make.com appelle ici) ---
@app.route('/api/process_individual_dropbox_link', methods=['POST'])
def api_process_individual_dropbox_link():
    received_token = request.headers.get('X-API-Token')
    if not EXPECTED_API_TOKEN:
        app.logger.error("API_PROCESS_LINK: PROCESS_API_TOKEN non configuré. Rejet.")
        return jsonify({"status": "error", "message": "Erreur de configuration serveur"}), 500 
    if received_token != EXPECTED_API_TOKEN:
        app.logger.warning(f"API_PROCESS_LINK: Accès non autorisé. Token reçu: '{received_token}'")
        return jsonify({"status": "error", "message": "Non autorisé"}), 401
    
    app.logger.info("API_PROCESS_LINK: Token API validé.")
    app.logger.info(f"API_PROCESS_LINK: Headers: {request.headers}")
    app.logger.info(f"API_PROCESS_LINK: Données brutes: {request.data}")
    
    data = None
    try:
        data = request.get_json(silent=True) 
        if data is None and request.data: 
            app.logger.warning(f"API_PROCESS_LINK: get_json(silent=True) a retourné None. Tentative parsing manuel.")
            try: data = json.loads(request.data.decode('utf-8'))
            except Exception as e_parse: app.logger.error(f"API_PROCESS_LINK: Échec parsing manuel: {e_parse}"); raise
        app.logger.info(f"API_PROCESS_LINK: Données JSON parsées: {data}")
    except Exception as e:
        app.logger.error(f"API_PROCESS_LINK: Erreur parsing JSON: {e}", exc_info=True)
        return jsonify({"status": "error", "message": f"Erreur décodage payload JSON: {str(e)}"}), 400

    if not data or 'dropbox_url' not in data:
        app.logger.error(f"API_PROCESS_LINK: Payload invalide. 'data': {data}. 'dropbox_url' manquante.")
        return jsonify({"status": "error", "message": "dropbox_url manquante ou payload JSON invalide"}), 400

    dropbox_url_to_process = data.get('dropbox_url')
    email_subject_for_filename = data.get('email_subject', 'FichierDropbox') # Fallback
    email_id_for_logging = data.get('email_id', 'N/A')

    app.logger.info(f"API_PROCESS_LINK: Demande reçue pour URL: {dropbox_url_to_process} (Sujet fallback: {email_subject_for_filename}, EmailID: {email_id_for_logging})")

    # Lancer le worker dans un thread séparé
    # La vérification si l'URL est déjà traitée se fera DANS le worker pour éviter des appels OneDrive redondants ici
    # si plusieurs requêtes arrivent quasi en même temps pour la même URL avant que le worker ne la traite.
    # Le worker est responsable de la déduplication avant le téléchargement.
    
    thread = threading.Thread(target=process_dropbox_link_worker, args=(
        dropbox_url_to_process, 
        email_subject_for_filename, 
        email_id_for_logging
    ))
    thread.daemon = True # Permet à l'application de se fermer même si les threads tournent
    thread.start()
    
    app.logger.info(f"API_PROCESS_LINK: Tâche de traitement pour {dropbox_url_to_process} mise en file d'attente (thread démarré).")
    return jsonify({"status": "accepted", "message": f"Demande de traitement pour le lien Dropbox reçue et mise en file d'attente."}), 202


# --- ENDPOINTS POUR DÉCLENCHEMENT LOCAL (si vous souhaitez les garder) ---
@app.route('/api/trigger_local_workflow', methods=['POST'])
def trigger_local_workflow():
    command_payload = request.json or {"command": "start_local_process", "timestamp": time.time()}
    try:
        with open(TRIGGER_SIGNAL_FILE, "w") as f: json.dump(command_payload, f)
        app.logger.info(f"Signal local posé sur {TRIGGER_SIGNAL_FILE}. Payload: {command_payload}")
        return jsonify({"status": "success", "message": "Signal pour workflow local posé", "payload": command_payload}), 200
    except Exception as e:
        app.logger.error(f"Erreur pose signal local: {e}", exc_info=True)
        return jsonify({"status": "error", "message": "Erreur interne pose signal"}), 500

@app.route('/api/check_trigger', methods=['GET'])
def check_trigger():
    response_data = {'command_pending': False, 'payload': None}
    if TRIGGER_SIGNAL_FILE.exists():
        try:
            with open(TRIGGER_SIGNAL_FILE, 'r') as f: payload = json.load(f)
            response_data['command_pending'] = True
            response_data['payload'] = payload
            TRIGGER_SIGNAL_FILE.unlink() 
            app.logger.info(f"Signal local lu et supprimé de {TRIGGER_SIGNAL_FILE}. Payload: {payload}")
        except FileNotFoundError:
            app.logger.info(f"Fichier signal {TRIGGER_SIGNAL_FILE} non trouvé (déjà traité).")
        except Exception as e:
            app.logger.error(f"Erreur traitement signal {TRIGGER_SIGNAL_FILE} : {e}", exc_info=True)
    return jsonify(response_data)

@app.route('/')
def serve_trigger_page():
    # (Identique à la version précédente)
    app.logger.info("Route '/' appelée. Tentative de servir 'trigger_page.html'.")
    serve_dir = Path(current_app.root_path)
    file_to_serve = 'trigger_page.html' 
    expected_file_location = serve_dir / file_to_serve
    if not expected_file_location.is_file():
        app.logger.error(f"ERREUR: '{file_to_serve}' NON TROUVÉ à {expected_file_location.resolve()}")
        return "Erreur: Fichier principal de l'interface non trouvé.", 404
    try:
        return send_from_directory(str(serve_dir), file_to_serve)
    except Exception as e_send:
        app.logger.error(f"Erreur send_from_directory pour '{file_to_serve}': {e_send}", exc_info=True)
        return "Erreur interne du serveur.", 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000)) 
    flask_debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    if not EXPECTED_API_TOKEN:
        app.logger.critical("ALERTE SÉCURITÉ: PROCESS_API_TOKEN N'EST PAS DÉFINIE.")
    app.logger.info(f"Démarrage serveur Flask sur port {port} avec debug={flask_debug_mode}")
    app.run(host='0.0.0.0', port=port, debug=flask_debug_mode)
