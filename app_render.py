from flask import Flask, jsonify, request, send_from_directory, current_app
import os
import time
from pathlib import Path
import json
import logging
import re 
import html as html_parser 
import requests 

from msal import ConfidentialClientApplication

app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

SIGNAL_DIR = Path(os.environ.get("RENDER_DISC_PATH", "./signal_data"))
DOWNLOAD_TEMP_DIR_RENDER = SIGNAL_DIR / "temp_downloads"
PROCESSED_DROPBOX_URLS_ONEDRIVE_FILENAME = "processed_dropbox_urls_workflow.txt"

SIGNAL_DIR.mkdir(parents=True, exist_ok=True)
DOWNLOAD_TEMP_DIR_RENDER.mkdir(parents=True, exist_ok=True)

ONEDRIVE_CLIENT_ID = os.environ.get('ONEDRIVE_CLIENT_ID')
ONEDRIVE_CLIENT_SECRET = os.environ.get('ONEDRIVE_CLIENT_SECRET')
ONEDRIVE_REFRESH_TOKEN = os.environ.get('ONEDRIVE_REFRESH_TOKEN')
ONEDRIVE_AUTHORITY = "https://login.microsoftonline.com/consumers"
ONEDRIVE_SCOPES_DELEGATED = ["Files.ReadWrite", "User.Read"]
ONEDRIVE_TARGET_PARENT_FOLDER_ID = os.environ.get('ONEDRIVE_TARGET_PARENT_FOLDER_ID', 'root')
ONEDRIVE_TARGET_SUBFOLDER_NAME = os.environ.get('ONEDRIVE_TARGET_SUBFOLDER_NAME', "DropboxDownloadsWorkflow")

EXPECTED_API_TOKEN = os.environ.get("PROCESS_API_TOKEN") 
if not EXPECTED_API_TOKEN:
    app.logger.warning("CRITICAL SECURITY WARNING: La variable d'environnement pour le token API (ex: PROCESS_API_TOKEN) n'est pas définie côté serveur. L'API de traitement est non sécurisée.")

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

# --- Fonctions Utilitaires (inchangées par rapport à la version précédente pour Workflow B) ---
def sanitize_filename(filename_str, max_length=200):
    sanitized = re.sub(r'[<>:"/\\|?*]', '_', filename_str)
    sanitized = re.sub(r'\.+', '.', sanitized).strip('.')
    return sanitized[:max_length] if sanitized else "default_filename"

def get_onedrive_access_token():
    if not msal_app:
        app.logger.error("MSAL ConfidentialClientApplication (msal_app) n'est pas configurée.")
        return None
    if not ONEDRIVE_REFRESH_TOKEN:
        app.logger.error("ONEDRIVE_REFRESH_TOKEN manquant.")
        return None
    app.logger.info(f"Tentative d'acquisition token Graph API pour scopes: {ONEDRIVE_SCOPES_DELEGATED}")
    result = msal_app.acquire_token_by_refresh_token(ONEDRIVE_REFRESH_TOKEN, scopes=ONEDRIVE_SCOPES_DELEGATED)
    if "access_token" in result:
        app.logger.info("Token d'accès Graph API obtenu.")
        new_rt = result.get("refresh_token")
        if new_rt and new_rt != ONEDRIVE_REFRESH_TOKEN:
             app.logger.warning("Un nouveau refresh token Graph API a été émis. Mettez à jour ONEDRIVE_REFRESH_TOKEN.")
        return result['access_token']
    else:
        app.logger.error(f"Erreur acquisition token Graph API: {result.get('error')} - {result.get('error_description')}")
        app.logger.error(f"Détails complets de l'erreur MSAL: {result}")
        return None

def ensure_onedrive_folder(access_token):
    headers = {'Authorization': 'Bearer ' + access_token, 'Content-Type': 'application/json'}
    if ONEDRIVE_TARGET_PARENT_FOLDER_ID.lower() == 'root':
        folder_check_url = f"https://graph.microsoft.com/v1.0/me/drive/root/children?$filter=name eq '{ONEDRIVE_TARGET_SUBFOLDER_NAME}'"
        folder_create_url = f"https://graph.microsoft.com/v1.0/me/drive/root/children"
    else:
        folder_check_url = f"https://graph.microsoft.com/v1.0/me/drive/items/{ONEDRIVE_TARGET_PARENT_FOLDER_ID}/children?$filter=name eq '{ONEDRIVE_TARGET_SUBFOLDER_NAME}'"
        folder_create_url = f"https://graph.microsoft.com/v1.0/me/drive/items/{ONEDRIVE_TARGET_PARENT_FOLDER_ID}/children"
    try:
        response = requests.get(folder_check_url, headers=headers)
        response.raise_for_status()
        children = response.json().get('value', [])
        if children:
            folder_id = children[0]['id']
            app.logger.info(f"Dossier OneDrive '{ONEDRIVE_TARGET_SUBFOLDER_NAME}' trouvé ID: {folder_id}")
            return folder_id
        else:
            app.logger.info(f"Dossier OneDrive '{ONEDRIVE_TARGET_SUBFOLDER_NAME}' non trouvé. Création.")
            payload = {"name": ONEDRIVE_TARGET_SUBFOLDER_NAME, "folder": {}, "@microsoft.graph.conflictBehavior": "rename"}
            response_create = requests.post(folder_create_url, headers=headers, json=payload)
            response_create.raise_for_status()
            folder_id = response_create.json()['id']
            app.logger.info(f"Dossier OneDrive '{ONEDRIVE_TARGET_SUBFOLDER_NAME}' créé ID: {folder_id}")
            return folder_id
    except requests.exceptions.RequestException as e:
        app.logger.error(f"Erreur API Graph vérification/création dossier OneDrive: {e}")
        if hasattr(e, 'response') and e.response is not None: app.logger.error(f"Réponse API Graph: {e.response.status_code} - {e.response.text}")
        return None

def upload_to_onedrive(filepath, filename_onedrive, access_token, target_folder_id):
    if not access_token or not target_folder_id:
        app.logger.error("Token d'accès OneDrive ou ID dossier cible manquant pour l'upload.")
        return False
    filename_onedrive_clean = sanitize_filename(filename_onedrive)
    if not filename_onedrive_clean: filename_onedrive_clean = "fichier_par_defaut_upload"
    upload_url_simple_put = f"https://graph.microsoft.com/v1.0/me/drive/items/{target_folder_id}:/{filename_onedrive_clean}:/content?@microsoft.graph.conflictBehavior=rename"
    headers_put = {'Authorization': 'Bearer ' + access_token, 'Content-Type': 'application/octet-stream'}
    file_size = os.path.getsize(filepath)
    app.logger.info(f"Upload de '{filepath.name}' ({file_size} bytes) vers OneDrive ID {target_folder_id} nom '{filename_onedrive_clean}'")
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
            app.logger.info(f"Session d'upload OneDrive créée: {upload_session_url}")
            chunk_size = 5 * 1024 * 1024
            chunks_uploaded_count = 0
            with open(filepath, 'rb') as f_data:
                while True:
                    chunk = f_data.read(chunk_size)
                    if not chunk: break
                    start_byte = chunks_uploaded_count * chunk_size
                    end_byte = start_byte + len(chunk) - 1
                    chunk_headers = {'Content-Length': str(len(chunk)), 'Content-Range': f'bytes {start_byte}-{end_byte}/{file_size}'}
                    response_chunk = requests.put(upload_session_url, headers=chunk_headers, data=chunk)
                    response_chunk.raise_for_status()
                    final_response = response_chunk
                    chunks_uploaded_count += 1
            app.logger.info(f"Tous les chunks de '{filepath.name}' uploadés.")
        if final_response and final_response.status_code < 300:
            app.logger.info(f"Fichier '{filename_onedrive_clean}' uploadé avec succès. Réponse: {final_response.status_code}")
            return True
        else:
            app.logger.error(f"Erreur après upload OneDrive ({filename_onedrive_clean}). Status: {final_response.status_code if final_response else 'N/A'}")
            return False
    except requests.exceptions.RequestException as e:
        app.logger.error(f"Erreur API Graph upload vers OneDrive ({filename_onedrive_clean}): {e}")
        if hasattr(e, 'response') and e.response is not None: app.logger.error(f"Réponse API Graph: {e.response.status_code} - {e.response.text}")
        if 'upload_session_url' in locals() and file_size >= 4 * 1024 * 1024:
            requests.delete(upload_session_url, headers={'Authorization': 'Bearer ' + access_token}) # Best effort
        return False
    except Exception as ex:
        app.logger.error(f"Erreur générale upload OneDrive ({filename_onedrive_clean}): {ex}", exc_info=True)
        return False

def download_and_relay_to_onedrive(dropbox_url, access_token_graph, target_folder_id_onedrive, preferred_filename_from_subject=None):
    app.logger.info(f"Dropbox: URL originale: {dropbox_url}")
    unescaped_dropbox_url = html_parser.unescape(dropbox_url)
    modified_url = unescaped_dropbox_url.replace("dl=0", "dl=1")
    modified_url = re.sub(r'dl=[^&?#]+', 'dl=1', modified_url)
    if '?dl=1' not in modified_url and '&dl=1' not in modified_url:
        modified_url = modified_url + ("&" if "?" in modified_url else "?") + "dl=1"
    app.logger.info(f"Dropbox: Téléchargement depuis (URL finale): {modified_url}")
    temp_filepath = None 
    try:
        headers_dropbox = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(modified_url, stream=True, allow_redirects=True, timeout=300, headers=headers_dropbox)
        response.raise_for_status()
        filename_from_dropbox = "downloaded_file_from_dropbox"
        content_disposition = response.headers.get('content-disposition')
        if content_disposition:
            fn_match_star = re.search(r"filename\*=(?:UTF-8'')?([^;\n\r\"]+)", content_disposition, flags=re.IGNORECASE)
            if fn_match_star: filename_from_dropbox = requests.utils.unquote(fn_match_star.group(1)).strip('"')
            else:
                fn_match_simple = re.findall('filename="?(.+?)"?(?:;|$)', content_disposition)
                if fn_match_simple: filename_from_dropbox = fn_match_simple[0]
        
        if preferred_filename_from_subject:
            dropbox_filename_ext = ""
            if '.' in filename_from_dropbox:
                try: dropbox_filename_ext = "." + filename_from_dropbox.rsplit('.', 1)[1]
                except IndexError: pass 
            filename_onedrive_base = sanitize_filename(preferred_filename_from_subject, max_length=180) 
            if dropbox_filename_ext and not filename_onedrive_base.lower().endswith(dropbox_filename_ext.lower()):
                 filename_onedrive = filename_onedrive_base + dropbox_filename_ext
            else:
                 filename_onedrive = filename_onedrive_base
            app.logger.info(f"Nom de fichier basé sur sujet: '{filename_onedrive}' (Base: '{preferred_filename_from_subject}', Ext: '{dropbox_filename_ext}')")
        else:
            filename_onedrive = sanitize_filename(filename_from_dropbox)
            app.logger.info(f"Nom de fichier de Dropbox: '{filename_onedrive}' (Original: '{filename_from_dropbox}')")
        if not filename_onedrive: filename_onedrive = "fichier_dropbox_telecharge" 
        temp_filepath = DOWNLOAD_TEMP_DIR_RENDER / filename_onedrive 
        with open(temp_filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192 * 4): f.write(chunk)
        app.logger.info(f"Dropbox: Téléchargé vers '{temp_filepath}'")
        if access_token_graph and target_folder_id_onedrive:
            if upload_to_onedrive(temp_filepath, filename_onedrive, access_token_graph, target_folder_id_onedrive):
                app.logger.info(f"OneDrive: Succès upload de '{filename_onedrive}'")
                return True
            else:
                app.logger.error(f"OneDrive: Échec upload de '{filename_onedrive}'")
        else:
            app.logger.error("OneDrive: Token d'accès ou ID dossier cible manquant pour l'upload.")
        return False
    except requests.exceptions.RequestException as e:
        app.logger.error(f"Dropbox: Erreur de téléchargement {modified_url}: {e}")
        if hasattr(e, 'response') and e.response is not None: app.logger.error(f"Réponse Dropbox: {e.response.status_code} - {e.response.text[:500]}...")
        return False
    except Exception as e_main:
        app.logger.error(f"Erreur générale download_and_relay_to_onedrive {dropbox_url}: {e_main}", exc_info=True)
        return False
    finally:
        if temp_filepath and temp_filepath.exists():
            try:
                temp_filepath.unlink()
                app.logger.info(f"Fichier temporaire '{temp_filepath}' supprimé.")
            except OSError as e_unlink:
                app.logger.error(f"Erreur suppression fichier temporaire '{temp_filepath}': {e_unlink}")

def get_processed_urls_from_onedrive(access_token, target_folder_id):
    if not access_token or not target_folder_id: return set()
    download_url = f"https://graph.microsoft.com/v1.0/me/drive/items/{target_folder_id}:/{PROCESSED_DROPBOX_URLS_ONEDRIVE_FILENAME}:/content"
    headers = {'Authorization': 'Bearer ' + access_token}
    processed_urls = set()
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
        if hasattr(e, 'response') and e.response is not None: app.logger.error(f"Réponse API Graph (get_processed_urls): {e.response.status_code} - {e.response.text}")
    return processed_urls

def update_processed_urls_on_onedrive(access_token, target_folder_id, urls_to_write_set):
    if not access_token or not target_folder_id: return False
    content_to_upload = "\n".join(sorted(list(urls_to_write_set))) if urls_to_write_set else ""
    upload_url = f"https://graph.microsoft.com/v1.0/me/drive/items/{target_folder_id}:/{PROCESSED_DROPBOX_URLS_ONEDRIVE_FILENAME}:/content?@microsoft.graph.conflictBehavior=replace"
    headers = {'Authorization': 'Bearer ' + access_token, 'Content-Type': 'text/plain; charset=utf-8'}
    try:
        response = requests.put(upload_url, headers=headers, data=content_to_upload.encode('utf-8'))
        response.raise_for_status()
        app.logger.info(f"{PROCESSED_DROPBOX_URLS_ONEDRIVE_FILENAME} mis à jour sur OneDrive avec {len(urls_to_write_set)} URLs.")
        return True
    except requests.exceptions.RequestException as e:
        app.logger.error(f"Erreur upload {PROCESSED_DROPBOX_URLS_ONEDRIVE_FILENAME}: {e}")
        if hasattr(e, 'response') and e.response is not None: app.logger.error(f"Réponse API Graph (update_processed_urls): {e.response.status_code} - {e.response.text}")
        return False
# --- FIN Fonctions Utilitaires ---

@app.route('/api/process_individual_dropbox_link', methods=['POST'])
def api_process_individual_dropbox_link():
    received_token = request.headers.get('X-API-Token')
    if not EXPECTED_API_TOKEN:
        app.logger.error("API_PROCESS_LINK: Mesure de sécurité non configurée côté serveur (EXPECTED_API_TOKEN manquant). Rejet de la requête.")
        return jsonify({"status": "error", "message": "Erreur de configuration serveur"}), 500 
    if received_token != EXPECTED_API_TOKEN:
        app.logger.warning(f"API_PROCESS_LINK: Tentative d'accès non autorisé. Token reçu: '{received_token}'") # Ne pas logger EXPECTED_API_TOKEN
        return jsonify({"status": "error", "message": "Non autorisé"}), 401
    
    app.logger.info("API_PROCESS_LINK: Token API validé.")

    # --- NOUVEAU LOGGING POUR DÉBOGUER LE PAYLOAD ---
    app.logger.info(f"API_PROCESS_LINK: Headers de la requête: {request.headers}")
    app.logger.info(f"API_PROCESS_LINK: Contenu brut de la requête (request.data): {request.data}")
    
    data = None
    try:
        # Tenter de parser le JSON. force=True ignore le Content-Type si Flask a des soucis.
        # silent=True retourne None au lieu de lever une erreur si ce n'est pas du JSON.
        data = request.get_json(silent=True) 
        if data is None and request.data: # Si get_json(silent=True) retourne None mais qu'il y avait des données brutes
            app.logger.warning(f"API_PROCESS_LINK: request.get_json(silent=True) a retourné None, mais request.data n'était pas vide. Tentative de parsing manuel.")
            try:
                data = json.loads(request.data.decode('utf-8')) # Essayer de parser manuellement
                app.logger.info(f"API_PROCESS_LINK: Données JSON parsées manuellement: {data}")
            except json.JSONDecodeError as e_manual_json:
                app.logger.error(f"API_PROCESS_LINK: Échec du parsing JSON manuel: {e_manual_json}. Données brutes: {request.data}")
                return jsonify({"status": "error", "message": "Payload JSON invalide ou malformé (parsing manuel échoué)"}), 400
            except Exception as e_decode:
                app.logger.error(f"API_PROCESS_LINK: Erreur lors du décodage UTF-8 ou autre du payload: {e_decode}. Données brutes: {request.data}")
                return jsonify({"status": "error", "message": "Erreur décodage payload"}), 400

        app.logger.info(f"API_PROCESS_LINK: Données JSON parsées (après tentatives): {data}")
    except Exception as e:
        app.logger.error(f"API_PROCESS_LINK: Exception lors de request.get_json() ou du parsing: {e}", exc_info=True)
        # Ne pas retourner ici, la vérification 'if not data' ci-dessous gérera le cas où data est None.

    if not data or 'dropbox_url' not in data:
        app.logger.error(f"API_PROCESS_LINK: Payload invalide. 'data' est None ou 'dropbox_url' est manquante. Données finales: {data}")
        return jsonify({"status": "error", "message": "dropbox_url manquante ou payload JSON invalide"}), 400
    # --- FIN DU NOUVEAU LOGGING ---

    dropbox_url_to_process = data.get('dropbox_url')
    email_subject_for_filename = data.get('email_subject') 
    email_id_for_logging = data.get('email_id', 'N/A')

    app.logger.info(f"API_PROCESS_LINK: Demande de traitement pour URL: {dropbox_url_to_process} (Sujet: {email_subject_for_filename}, EmailID: {email_id_for_logging})")

    access_token = get_onedrive_access_token()
    if not access_token:
        return jsonify({"status": "error", "message": "Impossible d'obtenir token Graph API"}), 500

    target_folder_id = ensure_onedrive_folder(access_token)
    if not target_folder_id:
        return jsonify({"status": "error", "message": "Impossible de trouver/créer dossier OneDrive"}), 500

    processed_urls = get_processed_urls_from_onedrive(access_token, target_folder_id)

    if dropbox_url_to_process in processed_urls:
        app.logger.info(f"API_PROCESS_LINK: URL {dropbox_url_to_process} déjà traitée. Ignorée.")
        return jsonify({"status": "skipped", "message": "URL déjà traitée"}), 200

    app.logger.info(f"API_PROCESS_LINK: Traitement de la nouvelle URL: {dropbox_url_to_process}")
    
    success = download_and_relay_to_onedrive(
        dropbox_url_to_process, 
        access_token, 
        target_folder_id,
        preferred_filename_from_subject=email_subject_for_filename 
    )

    if success:
        processed_urls.add(dropbox_url_to_process)
        if update_processed_urls_on_onedrive(access_token, target_folder_id, processed_urls):
            app.logger.info(f"API_PROCESS_LINK: URL {dropbox_url_to_process} traitée et ajoutée à la liste.")
            return jsonify({"status": "success", "message": f"Lien Dropbox traité (Sujet: {email_subject_for_filename})."}), 200
        else:
            app.logger.error(f"API_PROCESS_LINK: URL {dropbox_url_to_process} traitée, MAIS échec màj liste URLs traitées sur OneDrive.")
            return jsonify({"status": "partial_error", "message": "Fichier transféré mais échec màj liste URLs."}), 500 
    else:
        app.logger.error(f"API_PROCESS_LINK: Échec du traitement du lien Dropbox: {dropbox_url_to_process}")
        return jsonify({"status": "error", "message": f"Échec traitement lien Dropbox (Sujet: {email_subject_for_filename})."}), 500

@app.route('/')
def serve_trigger_page():
    app.logger.info("Route '/' appelée. Tentative de servir 'trigger_page.html'.")
    serve_dir = Path(current_app.root_path)
    file_to_serve = 'trigger_page.html'
    expected_file_location = serve_dir / file_to_serve
    if not expected_file_location.is_file():
        app.logger.error(f"ERREUR: '{file_to_serve}' NON TROUVÉ à {expected_file_location.resolve()}")
        try:
            content_list_root = os.listdir(serve_dir)
            app.logger.info(f"Contenu du dossier racine de l'application ('{serve_dir}'): {content_list_root}")
        except Exception as e_ls:
            app.logger.error(f"Impossible de lister le contenu du dossier pour le débogage: {e_ls}")
        return "Erreur: Fichier principal de l'interface non trouvé. Vérifiez les logs du serveur.", 404
    try:
        return send_from_directory(str(serve_dir), file_to_serve)
    except Exception as e_send:
        app.logger.error(f"Erreur send_from_directory pour '{file_to_serve}' depuis '{serve_dir}': {e_send}", exc_info=True)
        return "Erreur interne du serveur lors de la tentative de servir la page.", 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    flask_debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    if not EXPECTED_API_TOKEN:
        app.logger.critical("ALERTE DE SÉCURITÉ CRITIQUE: La variable d'environnement pour le token API (ex: PROCESS_API_TOKEN) N'EST PAS DÉFINIE. L'API EST OUVERTE SANS AUTHENTIFICATION.")
    app.logger.info(f"Démarrage du serveur Flask sur le port {port} avec debug={flask_debug_mode}")
    app.run(host='0.0.0.0', port=port, debug=flask_debug_mode)
