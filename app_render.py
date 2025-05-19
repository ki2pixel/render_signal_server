from flask import Flask, jsonify, request, send_from_directory, current_app
import os
import time
from pathlib import Path
import json
import logging
import re # Pour les regex
import html as html_parser # <<< NOUVEL IMPORT pour html.unescape
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
# Scopes actuels: ["Files.ReadWrite", "User.Read", "Mail.Read"]
# Si vous ajoutez Mail.ReadWrite, mettez-le à jour ici et régénérez le refresh token
ONEDRIVE_SCOPES_DELEGATED = ["Files.ReadWrite", "User.Read", "Mail.Read"] 
ONEDRIVE_TARGET_PARENT_FOLDER_ID = os.environ.get('ONEDRIVE_TARGET_PARENT_FOLDER_ID', 'root')
ONEDRIVE_TARGET_SUBFOLDER_NAME = os.environ.get('ONEDRIVE_TARGET_SUBFOLDER_NAME', "DropboxDownloadsWorkflow")

msal_app = None
if ONEDRIVE_CLIENT_ID and ONEDRIVE_CLIENT_SECRET:
    app.logger.info(f"Configuration de MSAL ConfidentialClientApplication avec Client ID et Authority: {ONEDRIVE_AUTHORITY}")
    msal_app = ConfidentialClientApplication(
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
    return list(set(links)) # Retourne une liste de liens uniques

def get_processed_email_ids():
    if not PROCESSED_EMAIL_IDS_FILE.exists():
        return set()
    with open(PROCESSED_EMAIL_IDS_FILE, 'r') as f:
        return set(line.strip() for line in f)

def add_processed_email_id(email_id_str):
    with open(PROCESSED_EMAIL_IDS_FILE, 'a') as f:
        f.write(email_id_str + "\n")

def get_onedrive_access_token():
    if not msal_app:
        app.logger.error("MSAL ConfidentialClientApplication (msal_app) n'est pas configurée pour Graph API.")
        return None
    if not ONEDRIVE_REFRESH_TOKEN:
        app.logger.error("ONEDRIVE_REFRESH_TOKEN manquant. Impossible d'obtenir un token d'accès Graph API.")
        return None

    app.logger.info(f"Tentative d'acquisition d'un token d'accès Graph API en utilisant le refresh token pour les scopes: {ONEDRIVE_SCOPES_DELEGATED}")
    
    result = msal_app.acquire_token_by_refresh_token(
        ONEDRIVE_REFRESH_TOKEN,
        scopes=ONEDRIVE_SCOPES_DELEGATED
    )

    if "access_token" in result:
        app.logger.info("Nouveau token d'accès Graph API obtenu avec succès via refresh token.")
        new_rt = result.get("refresh_token")
        if new_rt and new_rt != ONEDRIVE_REFRESH_TOKEN:
            app.logger.warning("Un nouveau refresh token Graph API a été émis. "
                               "Il est conseillé de le mettre à jour manuellement (variable d'environnement ONEDRIVE_REFRESH_TOKEN).")
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

# --- MODIFIED: download_and_relay_to_onedrive ---
def download_and_relay_to_onedrive(dropbox_url):
    app.logger.info(f"Dropbox: URL originale reçue: {dropbox_url}")
    
    # Étape 1: Décoder les entités HTML (ex: & -> &)
    unescaped_dropbox_url = html_parser.unescape(dropbox_url)
    app.logger.info(f"Dropbox: URL après html.unescape: {unescaped_dropbox_url}")

    # Étape 2: Remplacer dl=0 par dl=1 et s'assurer qu'il n'y a qu'un seul dl=1
    # La première substitution remplace explicitement "dl=0" s'il existe.
    modified_url = unescaped_dropbox_url.replace("dl=0", "dl=1")
    # La seconde substitution (regex) s'assure que tout paramètre "dl=X" devient "dl=1".
    # Utile si le lien avait déjà dl=autre_chose ou si le replace ci-dessus n'a pas fonctionné (ex: lien direct avec dl=1).
    modified_url = re.sub(r'dl=[^&?#]+', 'dl=1', modified_url) 
    # Note: Changement mineur dans la regex pour ne pas capturer au-delà de '&', '?' ou '#'

    app.logger.info(f"Dropbox: Tentative de téléchargement depuis (URL finale): {modified_url}")
    temp_filepath = None 

    try:
        # Étape 3: Définir un User-Agent commun
        headers_dropbox = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        # Utiliser les headers_dropbox dans la requête
        response = requests.get(modified_url, stream=True, allow_redirects=True, timeout=300, headers=headers_dropbox)
        response.raise_for_status()

        filename_dropbox = "downloaded_file_from_dropbox" # Default
        content_disposition = response.headers.get('content-disposition')
        if content_disposition:
            # Tente d'abord de trouver filename* (standard pour les caractères non-ASCII)
            fn_match_star = re.search(r'filename\*=(?:UTF-8\'\')?([^;\n\r"]+)', content_disposition, flags=re.IGNORECASE)
            if fn_match_star:
                filename_dropbox = requests.utils.unquote(fn_match_star.group(1)).strip('"')
            else:
                # Sinon, tente de trouver filename= (plus simple)
                fn_match_simple = re.findall('filename="?(.+?)"?(?:;|$)', content_disposition)
                if fn_match_simple: 
                    filename_dropbox = fn_match_simple[0]
        
        app.logger.info(f"Dropbox: Nom de fichier extrait de Content-Disposition: '{filename_dropbox}'")

        # Nettoyer le nom de fichier pour OneDrive
        filename_onedrive = re.sub(r'[<>:"/\\|?*]', '_', filename_dropbox) # Caractères invalides pour noms de fichiers Windows/OneDrive
        filename_onedrive = filename_onedrive[:200] # Limiter la longueur
        temp_filepath = DOWNLOAD_TEMP_DIR_RENDER / filename_onedrive

        with open(temp_filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192 * 4): # 32KB chunks
                f.write(chunk)
        app.logger.info(f"Dropbox: Téléchargé '{filename_dropbox}' vers '{temp_filepath}'")

        access_token_graph = get_onedrive_access_token()
        if access_token_graph:
            target_folder_id = ensure_onedrive_folder(access_token_graph)
            if target_folder_id:
                if upload_to_onedrive(temp_filepath, filename_onedrive, access_token_graph, target_folder_id):
                    app.logger.info(f"OneDrive: Succès upload de '{filename_onedrive}'")
                    if temp_filepath and temp_filepath.exists(): 
                        try:
                            temp_filepath.unlink()
                            app.logger.info(f"Fichier temporaire '{temp_filepath}' supprimé.")
                        except OSError as e_unlink:
                            app.logger.error(f"Erreur lors de la suppression du fichier temporaire '{temp_filepath}': {e_unlink}")
                    return True
                else:
                    app.logger.error(f"OneDrive: Échec upload de '{filename_onedrive}'")
            else:
                app.logger.error("OneDrive: Impossible d'obtenir/créer le dossier cible.")
        else:
            app.logger.error("OneDrive: Impossible d'obtenir le token d'accès Graph API.")
        
        # Si on arrive ici, quelque chose a échoué après le téléchargement Dropbox réussi
        return False

    except requests.exceptions.Timeout:
        app.logger.error(f"Dropbox: Timeout lors du téléchargement pour {modified_url}")
        return False
    except requests.exceptions.RequestException as e: # Inclut HTTPError (comme 400, 404, 500 de Dropbox)
        app.logger.error(f"Dropbox: Erreur de téléchargement pour {modified_url}: {e}")
        if hasattr(e, 'response') and e.response is not None:
            app.logger.error(f"Réponse de Dropbox: {e.response.status_code} - {e.response.text[:500]}...") # Log first 500 chars of response
        return False
    except Exception as e_main: # Erreur générale (ex: problème d'écriture fichier)
        app.logger.error(f"Erreur générale dans download_and_relay_to_onedrive pour {dropbox_url}: {e_main}", exc_info=True)
        # Ne pas supprimer le fichier temporaire en cas d'erreur générale pour investigation,
        # sauf si l'erreur est spécifiquement lors du téléchargement Dropbox lui-même.
        if temp_filepath and temp_filepath.exists() and not isinstance(e_main, (requests.exceptions.RequestException, requests.exceptions.Timeout)):
             app.logger.info(f"Le fichier temporaire {temp_filepath} est conservé suite à l'erreur générale.")
        return False
    finally:
        # S'assurer que les fichiers temporaires sont supprimés si l'upload OneDrive a échoué
        # mais que le téléchargement Dropbox a réussi et qu'il n'y a pas eu d'autre erreur majeure
        # avant ou pendant l'upload OneDrive.
        # Cette logique est délicate, la suppression est déjà gérée après un upload OneDrive réussi.
        # Si l'upload échoue, il peut être utile de garder le fichier pour débogage.
        pass


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

    headers_graph = {'Authorization': 'Bearer ' + access_token, 'Content-Type': 'application/json'}
    
    filter_query_graph = "isRead eq false"
    orderby_query_graph = "receivedDateTime desc"
    top_query_graph = "20"

    messages_url = f"https://graph.microsoft.com/v1.0/me/mailFolders/inbox/messages?$filter={filter_query_graph}&$orderby={orderby_query_graph}&$top={top_query_graph}"
    app.logger.info(f"Appel API Graph: {messages_url}")
    
    num_downloaded_total = 0
    processed_graph_email_ids = get_processed_email_ids()

    try:
        response = requests.get(messages_url, headers={'Authorization': 'Bearer ' + access_token}) # Content-Type pas nécessaire pour GET
        response.raise_for_status()
        emails_data = response.json().get('value', [])
        app.logger.info(f"Trouvé {len(emails_data)} email(s) non lus via Graph API (avant filtrage expéditeur en Python).")

        for email_item in emails_data:
            email_id_graph = email_item['id']
            
            if email_id_graph in processed_graph_email_ids:
                app.logger.debug(f"Email Graph ID: {email_id_graph} déjà traité, ignoré.")
                continue
            
            subject = email_item.get('subject', "N/A")
            from_address_info = email_item.get('from', {}).get('emailAddress', {})
            actual_sender_address = from_address_info.get('address', '').lower()
            
            app.logger.info(f"Examen Email Graph ID: {email_id_graph}, De: {actual_sender_address}, Sujet: '{subject}'")
            
            if SENDER_OF_INTEREST.lower() != actual_sender_address:
                app.logger.info(f"Email Graph ID {email_id_graph} ignoré (expéditeur '{actual_sender_address}' ne correspond pas à '{SENDER_OF_INTEREST.lower()}').")
                add_processed_email_id(email_id_graph)
                continue
            
            app.logger.info(f"Traitement Email Graph ID: {email_id_graph} (Expéditeur '{actual_sender_address}' CORRESPOND)")
            
            body_content = email_item.get('body', {}).get('content', '')
            if not body_content and 'bodyPreview' in email_item and email_item.get('bodyPreview'):
                body_content = email_item.get('bodyPreview', '')
            
            if body_content:
                links_found = find_dropbox_links(body_content)
                if links_found:
                    app.logger.info(f"Email Graph ID {email_id_graph}: Liens Dropbox trouvés: {links_found}")
                    email_processed_successfully_for_marking = False # Drapeau pour marquer comme lu

                    for link_idx, link in enumerate(links_found):
                        app.logger.info(f"Traitement du lien {link_idx+1}/{len(links_found)}: {link} pour l'email ID {email_id_graph}")
                        if download_and_relay_to_onedrive(link): # Si UN lien est téléchargé avec succès
                            num_downloaded_total += 1
                            email_processed_successfully_for_marking = True # Email a été traité (au moins un lien)
                        else:
                            app.logger.error(f"Échec du traitement du lien {link} pour l'email Graph ID {email_id_graph}")
                    
                    # Marquer l'email comme traité (dans le fichier) et comme lu (via API)
                    # SI au moins un lien a été tenté (même si tous les téléchargements de ce mail ont échoué)
                    # OU si l'email est du SENDER_OF_INTEREST mais n'avait pas de liens (géré plus bas).
                    # Ici, nous sommes dans le cas où des liens ONT été trouvés.
                    add_processed_email_id(email_id_graph)
                    if email_processed_successfully_for_marking: # Ou peut-être toujours marquer lu si du SENDER_OF_INTEREST ? A débattre.
                                                                # Pour l'instant, on ne marque lu que si un DL a réussi.
                                                                # Modification: On va marquer lu si des liens ont été trouvés et traités,
                                                                # même si le download échoue, pour éviter de le retraiter.
                        mark_as_read_url = f"https://graph.microsoft.com/v1.0/me/messages/{email_id_graph}"
                        patch_payload = {"isRead": True}
                        try:
                            mark_response = requests.patch(mark_as_read_url, headers=headers_graph, json=patch_payload)
                            mark_response.raise_for_status()
                            app.logger.info(f"Email Graph ID {email_id_graph} marqué comme lu (car des liens ont été traités).")
                        except requests.exceptions.RequestException as e_mark:
                            app.logger.warning(f"Échec du marquage comme lu pour l'email Graph ID {email_id_graph}: {e_mark}")
                            # Loggue l'erreur mais continue. La permission Mail.ReadWrite est nécessaire.
                else: # Du SENDER_OF_INTEREST mais pas de liens trouvés
                    app.logger.info(f"Email Graph ID {email_id_graph}: Aucun lien Dropbox trouvé dans le corps.")
                    add_processed_email_id(email_id_graph) # Marquer comme traité pour ne pas le re-scanner.
            else: # Du SENDER_OF_INTEREST mais corps vide
                app.logger.warning(f"Email Graph ID {email_id_graph}: Corps de l'email vide ou non récupérable.")
                add_processed_email_id(email_id_graph) # Marquer comme traité.

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
            if time.time() - lock_file.stat().st_mtime < 300: # 5 minutes
                 app.logger.warning("Vérification des emails déjà en cours (lock file récent).")
                 return jsonify({"status": "busy", "message": "Vérification des emails déjà en cours."}), 429
            else:
                app.logger.warning("Ancien lock file trouvé, suppression et poursuite.")
                lock_file.unlink(missing_ok=True)
        except OSError as e:
            app.logger.error(f"Erreur avec le lock file {lock_file}: {e}")
            # Poursuivre peut être risqué, mais bloquer complètement peut être pire.
            # Pour l'instant, on logue et on continue.

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

        if num_downloaded == -1: # Erreur spécifique retournée par la fonction de check
            msg = "Une erreur est survenue pendant la vérification des emails via Graph API."
            status_code = 500
        else:
            msg = f"Vérification emails (Graph API) terminée. {num_downloaded} nouveau(x) fichier(s) transféré(s) vers OneDrive."
            status_code = 200
        
        app.logger.info(msg)
        return jsonify({"status": "success" if status_code==200 else "error", "message": msg, "files_downloaded": num_downloaded if num_downloaded !=-1 else 0}), status_code

    except Exception as e:
        app.logger.error(f"Erreur inattendue dans l'endpoint /api/check_emails_and_download: {e}", exc_info=True)
        return jsonify({"status": "error", "message": f"Erreur inattendue: {str(e)}"}), 500
    finally:
        if lock_file.exists(): 
            try:
                lock_file.unlink(missing_ok=True)
            except OSError as e_unlink_lock:
                app.logger.error(f"Impossible de supprimer le lock file {lock_file} en fin de traitement: {e_unlink_lock}")


# --- Nouvelle Route Principale pour servir trigger_page.html ---
@app.route('/')
def serve_trigger_page():
    app.logger.info("Route '/' appelée. Tentative de servir 'trigger_page.html'.")
    # Servir depuis le répertoire racine du projet où se trouve app_render.py
    directory_to_serve_from = Path(current_app.root_path) 
    file_to_serve = 'trigger_page.html'
    
    # Vérification plus robuste si le fichier existe
    # Note: send_from_directory résout le chemin relatif au deuxième argument (directory).
    # Ici, on va passer le chemin absolu au dossier et juste le nom du fichier.
    # Ou plus simple: current_app.root_path est le dossier de l'app, donc on peut servir depuis '.'
    # si trigger_page.html est au même niveau que app_render.py
    # Si trigger_page.html est dans un sous-dossier 'static' ou 'templates', ajuster.
    # Pour Render, si trigger_page.html est à la racine du repo, `.` devrait fonctionner.
    
    # Simplifions: on suppose que trigger_page.html est au même niveau que app_render.py
    # ou dans un chemin géré par Flask par défaut (ex: 'static' si utilisé avec url_for)
    # send_from_directory(directory, path) -> directory est le dossier, path est le fichier DANS ce dossier.
    
    # Si trigger_page.html est à la racine du projet (où app_render.py est):
    serve_dir = '.' 
    # Si trigger_page.html est dans un dossier 'public' à la racine:
    # serve_dir = 'public'
    
    expected_file_location = Path(current_app.root_path) / serve_dir / file_to_serve
    
    if not expected_file_location.is_file():
        app.logger.error(f"ERREUR: '{file_to_serve}' NON TROUVÉ à l'emplacement attendu: {expected_file_location.resolve()}")
        try:
            # Lister le contenu du répertoire racine de l'application pour le débogage
            content_list_root = os.listdir(Path(current_app.root_path))
            app.logger.info(f"Contenu du dossier racine de l'application ('{Path(current_app.root_path)}'): {content_list_root}")
            if (Path(current_app.root_path) / serve_dir).exists() and (Path(current_app.root_path) / serve_dir).is_dir():
                 content_list_serve_dir = os.listdir(Path(current_app.root_path) / serve_dir)
                 app.logger.info(f"Contenu du dossier de service ('{Path(current_app.root_path) / serve_dir}'): {content_list_serve_dir}")
        except Exception as e_ls:
            app.logger.error(f"Impossible de lister le contenu du dossier pour le débogage: {e_ls}")
        return "Erreur: Fichier principal de l'interface non trouvé. Vérifiez les logs du serveur.", 404

    try:
        return send_from_directory(serve_dir, file_to_serve)
    except Exception as e_send:
        app.logger.error(f"Erreur send_from_directory pour '{file_to_serve}' depuis '{serve_dir}': {e_send}", exc_info=True)
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
    # Mettre debug=True localement peut aider, mais False en production sur Render
    flask_debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    app.logger.info(f"Démarrage du serveur Flask sur le port {port} avec debug={flask_debug_mode}")
    app.run(host='0.0.0.0', port=port, debug=flask_debug_mode)
