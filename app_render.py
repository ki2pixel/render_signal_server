from flask import Flask, jsonify, request, send_from_directory, current_app
import os
import time
from pathlib import Path
import json
import logging
import re # Pour les regex
import html as html_parser # Pour html.unescape
import requests # Pour télécharger depuis Dropbox et appeler l'API Graph

# Pour l'API Microsoft Graph (OneDrive) avec MSAL
from msal import ConfidentialClientApplication

app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Config Fichiers Signal/Statut ---
# SIGNAL_DIR is for ephemeral data on Render's free tier
SIGNAL_DIR = Path(os.environ.get("RENDER_DISC_PATH", "./signal_data"))
# TRIGGER_SIGNAL_FILE = SIGNAL_DIR / "workflow_trigger_signal.txt" # Less relevant now
# LOCAL_STATUS_FILE = SIGNAL_DIR / "current_local_status.json" # Less relevant now
DOWNLOAD_TEMP_DIR_RENDER = SIGNAL_DIR / "temp_downloads" # For temporary Dropbox downloads
PROCESSED_EMAIL_IDS_ONEDRIVE_FILENAME = "processed_email_ids_workflow.txt" # Stored on OneDrive

SIGNAL_DIR.mkdir(parents=True, exist_ok=True)
DOWNLOAD_TEMP_DIR_RENDER.mkdir(parents=True, exist_ok=True)

# --- Config Email (SENDER_OF_INTEREST is still key) ---
SENDER_OF_INTEREST = os.environ.get('SENDER_OF_INTEREST')

# --- Config API Microsoft Graph (OneDrive & Mail) ---
ONEDRIVE_CLIENT_ID = os.environ.get('ONEDRIVE_CLIENT_ID')
ONEDRIVE_CLIENT_SECRET = os.environ.get('ONEDRIVE_CLIENT_SECRET')
ONEDRIVE_REFRESH_TOKEN = os.environ.get('ONEDRIVE_REFRESH_TOKEN')

ONEDRIVE_AUTHORITY = "https://login.microsoftonline.com/consumers" # ou votre tenant spécifique
# IMPORTANT: For marking emails as read, "Mail.ReadWrite" is needed.
# If you only use "Mail.Read", the mark-as-read operation will fail.
# Regenerate your refresh token if you change scopes.
ONEDRIVE_SCOPES_DELEGATED = ["Files.ReadWrite", "User.Read", "Mail.ReadWrite"] # Updated scope
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
    return list(set(links))

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
    # Check in parent folder first
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
            app.logger.info(f"Dossier OneDrive '{ONEDRIVE_TARGET_SUBFOLDER_NAME}' trouvé avec ID: {folder_id}")
            return folder_id
        else:
            app.logger.info(f"Dossier OneDrive '{ONEDRIVE_TARGET_SUBFOLDER_NAME}' non trouvé. Tentative de création.")
            payload = {
                "name": ONEDRIVE_TARGET_SUBFOLDER_NAME,
                "folder": {},
                "@microsoft.graph.conflictBehavior": "rename" # or "fail" or "replace"
            }
            response_create = requests.post(folder_create_url, headers=headers, json=payload)
            response_create.raise_for_status()
            folder_id = response_create.json()['id']
            app.logger.info(f"Dossier OneDrive '{ONEDRIVE_TARGET_SUBFOLDER_NAME}' créé avec ID: {folder_id}")
            return folder_id
    except requests.exceptions.RequestException as e:
        app.logger.error(f"Erreur API Graph lors de la vérification/création du dossier OneDrive '{ONEDRIVE_TARGET_SUBFOLDER_NAME}': {e}")
        if hasattr(e, 'response') and e.response is not None:
            app.logger.error(f"Réponse de l'API Graph: {e.response.status_code} - {e.response.text}")
        return None

def upload_to_onedrive(filepath, filename_onedrive, access_token, target_folder_id):
    if not access_token or not target_folder_id:
        app.logger.error("Token d'accès OneDrive ou ID dossier cible manquant pour l'upload.")
        return False

    upload_url_simple_put = f"https://graph.microsoft.com/v1.0/me/drive/items/{target_folder_id}:/{filename_onedrive}:/content?@microsoft.graph.conflictBehavior=rename"
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
            if 'upload_session_url' in locals() and file_size >= 4 * 1024 * 1024: # Only try to delete session if it was created
                app.logger.info(f"Tentative d'annulation de la session d'upload: {upload_session_url}")
                requests.delete(upload_session_url, headers={'Authorization': 'Bearer ' + access_token}) # Best effort
        return False
    except Exception as ex:
        app.logger.error(f"Erreur générale inattendue pendant l'upload OneDrive ({filename_onedrive}): {ex}", exc_info=True)
        return False

def download_and_relay_to_onedrive(dropbox_url, access_token_graph, target_folder_id_onedrive):
    app.logger.info(f"Dropbox: URL originale reçue: {dropbox_url}")
    
    unescaped_dropbox_url = html_parser.unescape(dropbox_url)
    app.logger.info(f"Dropbox: URL après html.unescape: {unescaped_dropbox_url}")

    modified_url = unescaped_dropbox_url.replace("dl=0", "dl=1")
    modified_url = re.sub(r'dl=[^&?#]+', 'dl=1', modified_url)
    if '?dl=1' not in modified_url and '&dl=1' not in modified_url:
        if '?' in modified_url:
            modified_url += "&dl=1"
        else:
            modified_url += "?dl=1"
    
    app.logger.info(f"Dropbox: Tentative de téléchargement depuis (URL finale): {modified_url}")
    temp_filepath = None 

    try:
        headers_dropbox = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(modified_url, stream=True, allow_redirects=True, timeout=300, headers=headers_dropbox)
        response.raise_for_status()

        filename_dropbox = "downloaded_file_from_dropbox"
        content_disposition = response.headers.get('content-disposition')
        if content_disposition:
            fn_match_star = re.search(r'filename\*=(?:UTF-8\'\')?([^;\n\r"]+)', content_disposition, flags=re.IGNORECASE)
            if fn_match_star:
                filename_dropbox = requests.utils.unquote(fn_match_star.group(1)).strip('"')
            else:
                fn_match_simple = re.findall('filename="?(.+?)"?(?:;|$)', content_disposition)
                if fn_match_simple: 
                    filename_dropbox = fn_match_simple[0]
        
        app.logger.info(f"Dropbox: Nom de fichier extrait de Content-Disposition: '{filename_dropbox}'")
        filename_onedrive = re.sub(r'[<>:"/\\|?*]', '_', filename_dropbox)
        filename_onedrive = filename_onedrive[:200]
        temp_filepath = DOWNLOAD_TEMP_DIR_RENDER / filename_onedrive

        with open(temp_filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192 * 4):
                f.write(chunk)
        app.logger.info(f"Dropbox: Téléchargé '{filename_dropbox}' vers '{temp_filepath}'")

        # access_token_graph and target_folder_id_onedrive are now passed as arguments
        if access_token_graph and target_folder_id_onedrive:
            if upload_to_onedrive(temp_filepath, filename_onedrive, access_token_graph, target_folder_id_onedrive):
                app.logger.info(f"OneDrive: Succès upload de '{filename_onedrive}'")
                return True # Keep temp file deletion centralized
            else:
                app.logger.error(f"OneDrive: Échec upload de '{filename_onedrive}'")
        else:
            app.logger.error("OneDrive: Token d'accès Graph API ou ID dossier cible manquant pour l'upload.")
        
        return False # Upload failed or prerequisites missing

    except requests.exceptions.Timeout:
        app.logger.error(f"Dropbox: Timeout lors du téléchargement pour {modified_url}")
        return False
    except requests.exceptions.RequestException as e:
        app.logger.error(f"Dropbox: Erreur de téléchargement pour {modified_url}: {e}")
        if hasattr(e, 'response') and e.response is not None:
            app.logger.error(f"Réponse de Dropbox: {e.response.status_code} - {e.response.text[:500]}...")
        return False
    except Exception as e_main:
        app.logger.error(f"Erreur générale dans download_and_relay_to_onedrive pour {dropbox_url}: {e_main}", exc_info=True)
        return False
    finally:
        # Centralized temporary file deletion
        if temp_filepath and temp_filepath.exists(): 
            try:
                temp_filepath.unlink()
                app.logger.info(f"Fichier temporaire '{temp_filepath}' supprimé après tentative de traitement.")
            except OSError as e_unlink:
                app.logger.error(f"Erreur lors de la suppression du fichier temporaire '{temp_filepath}': {e_unlink}")

# --- OneDrive Processed Email ID Management ---
def get_processed_email_ids_from_onedrive(access_token, target_folder_id):
    if not access_token or not target_folder_id:
        app.logger.error("OneDrive: Token ou folder ID manquant pour get_processed_email_ids.")
        return set()
    
    # Construct the path to the item: /drives/{drive-id}/items/{item-id}:/{path}
    # or /me/drive/items/{item-id}:/{path}
    # or /me/drive/root:/{folderName}/{fileName}:/content
    download_url = f"https://graph.microsoft.com/v1.0/me/drive/items/{target_folder_id}:/{PROCESSED_EMAIL_IDS_ONEDRIVE_FILENAME}:/content"
    headers = {'Authorization': 'Bearer ' + access_token}
    processed_ids = set()
    try:
        response = requests.get(download_url, headers=headers)
        if response.status_code == 200:
            lines = response.text.splitlines()
            for line in lines:
                if line.strip():
                    processed_ids.add(line.strip())
            app.logger.info(f"Lu {len(processed_ids)} IDs depuis {PROCESSED_EMAIL_IDS_ONEDRIVE_FILENAME} sur OneDrive.")
        elif response.status_code == 404:
            app.logger.info(f"{PROCESSED_EMAIL_IDS_ONEDRIVE_FILENAME} non trouvé sur OneDrive. Initialisation d'une nouvelle liste.")
        else:
            # This will log the error if it's not 200 or 404
            response.raise_for_status() 
    except requests.exceptions.RequestException as e:
        app.logger.error(f"Erreur téléchargement {PROCESSED_EMAIL_IDS_ONEDRIVE_FILENAME} depuis OneDrive: {e}")
        if hasattr(e, 'response') and e.response is not None:
            app.logger.error(f"Réponse de l'API Graph (get_processed_ids): {e.response.status_code} - {e.response.text}")
    return processed_ids

def update_processed_email_ids_on_onedrive(access_token, target_folder_id, ids_to_write_set):
    if not access_token or not target_folder_id:
        app.logger.error("OneDrive: Token ou folder ID manquant pour update_processed_email_ids.")
        return False
    if not ids_to_write_set: # Don't write an empty file if there's nothing to add and nothing existed
        app.logger.info(f"Aucun ID à écrire dans {PROCESSED_EMAIL_IDS_ONEDRIVE_FILENAME}.")
        # If the file should be created empty, this logic might need adjustment
        # For now, if it's empty and was empty, do nothing. If it was not empty, we need to write.
        # Better: always write the current full set.
        # return True 

    content_to_upload = "\n".join(sorted(list(ids_to_write_set)))
    if not content_to_upload: # Ensure we always write something, even if it's an empty string for an empty set
        content_to_upload = "" 

    # Using @microsoft.graph.conflictBehavior=replace to overwrite the file
    upload_url = f"https://graph.microsoft.com/v1.0/me/drive/items/{target_folder_id}:/{PROCESSED_EMAIL_IDS_ONEDRIVE_FILENAME}:/content?@microsoft.graph.conflictBehavior=replace"
    headers = {'Authorization': 'Bearer ' + access_token, 'Content-Type': 'text/plain; charset=utf-8'}
    try:
        response = requests.put(upload_url, headers=headers, data=content_to_upload.encode('utf-8'))
        response.raise_for_status()
        app.logger.info(f"{PROCESSED_EMAIL_IDS_ONEDRIVE_FILENAME} mis à jour sur OneDrive avec {len(ids_to_write_set)} IDs.")
        return True
    except requests.exceptions.RequestException as e:
        app.logger.error(f"Erreur upload {PROCESSED_EMAIL_IDS_ONEDRIVE_FILENAME} vers OneDrive: {e}")
        if hasattr(e, 'response') and e.response is not None:
            app.logger.error(f"Réponse de l'API Graph (update_processed_ids): {e.response.status_code} - {e.response.text}")
        return False

# --- Fonction principale pour vérifier les emails via Microsoft Graph API ---
def check_emails_via_graph_and_download():
    app.logger.info("Déclenchement vérification emails via Graph API et téléchargement Dropbox.")
    
    access_token = get_onedrive_access_token()
    if not access_token:
        app.logger.error("Impossible d'obtenir un token d'accès Graph API.")
        return -1, 0 # error_flag, num_downloaded

    if not SENDER_OF_INTEREST:
        app.logger.error("SENDER_OF_INTEREST n'est pas configuré. Impossible de filtrer les emails.")
        return -1, 0

    target_folder_id_onedrive = ensure_onedrive_folder(access_token)
    if not target_folder_id_onedrive:
        app.logger.error("Impossible d'obtenir/créer le dossier cible sur OneDrive.")
        return -1, 0

    # Get all currently known processed IDs from OneDrive
    all_processed_email_ids = get_processed_email_ids_from_onedrive(access_token, target_folder_id_onedrive)
    # Keep track of IDs processed in this specific run to add them later
    newly_processed_ids_this_run = set()

    headers_graph_mail = {'Authorization': 'Bearer ' + access_token, 'Prefer': 'outlook.body-content-type="text"'} # Request body as text
    
    # Fetch unread emails. Can be further filtered by date if needed.
    filter_query_graph = "isRead eq false" 
    # Filter by sender directly in Graph API if possible, otherwise filter in Python
    # filter_query_graph += f" and from/emailAddress/address eq '{SENDER_OF_INTEREST}'" # More efficient
    orderby_query_graph = "receivedDateTime desc"
    top_query_graph = "50" # Process more emails if available

    messages_url = f"https://graph.microsoft.com/v1.0/me/mailFolders/inbox/messages?$filter={filter_query_graph}&$orderby={orderby_query_graph}&$top={top_query_graph}&$select=id,subject,from,receivedDateTime,body,bodyPreview,isRead"
    app.logger.info(f"Appel API Graph (Mail): {messages_url}")
    
    num_files_downloaded_successfully_total = 0

    try:
        response = requests.get(messages_url, headers=headers_graph_mail)
        response.raise_for_status()
        emails_data = response.json().get('value', [])
        app.logger.info(f"Trouvé {len(emails_data)} email(s) via Graph API (filtrés par 'non lu').")

        for email_item in emails_data:
            email_id_graph = email_item['id']
            
            if email_id_graph in all_processed_email_ids:
                app.logger.debug(f"Email Graph ID: {email_id_graph} déjà dans la liste des traités (OneDrive), ignoré.")
                continue # Already processed in a previous run
            
            subject = email_item.get('subject', "N/A")
            from_address_info = email_item.get('from', {}).get('emailAddress', {})
            actual_sender_address = from_address_info.get('address', '').lower()
            received_time = email_item.get('receivedDateTime', "N/A")
            
            app.logger.info(f"Examen Email Graph ID: {email_id_graph}, De: {actual_sender_address}, Reçu: {received_time}, Sujet: '{subject}'")
            
            # Mark this email ID for addition to the processed list, regardless of outcome below
            # This prevents re-scanning it constantly if it's problematic or irrelevant
            newly_processed_ids_this_run.add(email_id_graph)

            if SENDER_OF_INTEREST.lower() != actual_sender_address:
                app.logger.info(f"Email Graph ID {email_id_graph} ignoré (expéditeur '{actual_sender_address}' ne correspond pas).")
                # No need to mark as read if it's not from the sender of interest and we already added to processed list.
                continue 
            
            app.logger.info(f"Traitement Email Graph ID: {email_id_graph} (Expéditeur '{actual_sender_address}' CORRESPOND)")
            
            body_content_type = email_item.get('body', {}).get('contentType', 'html').lower() # Default to html
            body_content = email_item.get('body', {}).get('content', '')

            if not body_content and 'bodyPreview' in email_item and email_item.get('bodyPreview'):
                app.logger.info(f"Corps principal vide pour email {email_id_graph}, utilisation de bodyPreview.")
                body_content = email_item.get('bodyPreview', '')
            
            if body_content:
                # If body is HTML, Graph API might have already unescaped it if text was requested.
                # If it's still HTML, find_dropbox_links might need to be more robust or body needs cleaning.
                # For now, assume find_dropbox_links can handle plain text or simple HTML content.
                links_found = find_dropbox_links(body_content)
                if links_found:
                    app.logger.info(f"Email Graph ID {email_id_graph}: Liens Dropbox trouvés: {links_found}")
                    at_least_one_link_download_success_for_this_email = False

                    for link_idx, link in enumerate(links_found):
                        app.logger.info(f"Traitement du lien {link_idx+1}/{len(links_found)}: {link} pour l'email ID {email_id_graph}")
                        # Pass existing token and target folder ID
                        if download_and_relay_to_onedrive(link, access_token, target_folder_id_onedrive):
                            num_files_downloaded_successfully_total += 1
                            at_least_one_link_download_success_for_this_email = True
                        else:
                            app.logger.error(f"Échec du traitement du lien {link} pour l'email Graph ID {email_id_graph}")
                    
                    if at_least_one_link_download_success_for_this_email:
                         app.logger.info(f"Au moins un lien traité avec succès pour l'email {email_id_graph}.")
                    # Mark email as read only if we actually processed it (found sender, found links)
                    # This requires Mail.ReadWrite scope for the token
                    mark_as_read_url = f"https://graph.microsoft.com/v1.0/me/messages/{email_id_graph}"
                    patch_payload = {"isRead": True}
                    try:
                        mark_response = requests.patch(mark_as_read_url, headers=headers_graph_mail, json=patch_payload) # Use headers_graph_mail
                        mark_response.raise_for_status()
                        app.logger.info(f"Email Graph ID {email_id_graph} marqué comme lu.")
                    except requests.exceptions.RequestException as e_mark:
                        app.logger.warning(f"Échec du marquage comme lu pour l'email Graph ID {email_id_graph}: {e_mark}. Vérifiez les permissions (Mail.ReadWrite).")
                        if hasattr(e_mark, 'response') and e_mark.response is not None:
                             app.logger.warning(f"Mark as read API Response: {e_mark.response.status_code} - {e_mark.response.text}")
                else: 
                    app.logger.info(f"Email Graph ID {email_id_graph}: Aucun lien Dropbox trouvé dans le corps.")
                    # Still mark as read if from correct sender but no links, to avoid re-scanning
                    mark_as_read_url = f"https://graph.microsoft.com/v1.0/me/messages/{email_id_graph}"
                    patch_payload = {"isRead": True}
                    try:
                        mark_response = requests.patch(mark_as_read_url, headers=headers_graph_mail, json=patch_payload)
                        mark_response.raise_for_status()
                        app.logger.info(f"Email Graph ID {email_id_graph} (pas de liens) marqué comme lu.")
                    except requests.exceptions.RequestException as e_mark:
                        app.logger.warning(f"Échec du marquage comme lu (pas de liens) pour {email_id_graph}: {e_mark}.")

            else: 
                app.logger.warning(f"Email Graph ID {email_id_graph}: Corps de l'email vide ou non récupérable.")
                # Optionally mark as read here too if desired.

    except requests.exceptions.RequestException as e_graph:
        app.logger.error(f"Erreur API Graph lors de la lecture des emails: {e_graph}")
        if hasattr(e_graph, 'response') and e_graph.response is not None:
            app.logger.error(f"Réponse API Graph (Mail): {e_graph.response.status_code} - {e_graph.response.text}")
        return -1, num_files_downloaded_successfully_total # error_flag, files_downloaded
    except Exception as ex_general:
        app.logger.error(f"Erreur inattendue pendant la lecture des emails via Graph API: {ex_general}", exc_info=True)
        return -1, num_files_downloaded_successfully_total # error_flag, files_downloaded
    finally:
        # Update the processed IDs list on OneDrive with all IDs encountered in this run
        if newly_processed_ids_this_run:
            app.logger.info(f"Mise à jour de {PROCESSED_EMAIL_IDS_ONEDRIVE_FILENAME} sur OneDrive.")
            all_ids_to_write_to_onedrive = all_processed_email_ids.union(newly_processed_ids_this_run)
            if not update_processed_email_ids_on_onedrive(access_token, target_folder_id_onedrive, all_ids_to_write_to_onedrive):
                app.logger.error("Échec critique: Impossible de mettre à jour la liste des IDs traités sur OneDrive.")
                # This is a problem, as next run might re-process emails.
                # However, returning -1 from the main function handles general error state.

    return 0, num_files_downloaded_successfully_total # success_flag (0 means no major error), files_downloaded

# --- Endpoint pour Déclencher la Vérification des Emails (via Graph API) ---
@app.route('/api/check_emails_and_download', methods=['POST'])
def api_check_emails_and_download():
    app.logger.info("API: Déclenchement de la vérification des emails (via Graph API) et téléchargement.")
    
    # Simple lock mechanism to prevent concurrent runs, suitable for Render free tier
    lock_file_path = SIGNAL_DIR / "email_check.lock"
    try:
        # Try to create lock file exclusively. If it exists, another process is running.
        # O_CREAT | O_EXCL will fail if file exists.
        fd = os.open(lock_file_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.close(fd) # Close immediately, we just need the file to exist
        app.logger.info(f"Lock file {lock_file_path} créé.")
    except FileExistsError:
        # Check lock file age. If older than X minutes, assume stale and proceed.
        try:
            lock_age = time.time() - lock_file_path.stat().st_mtime
            if lock_age > 300: # 5 minutes
                app.logger.warning(f"Lock file {lock_file_path} est ancien ({lock_age:.0f}s). Suppression et poursuite.")
                lock_file_path.unlink(missing_ok=True) # Attempt to remove stale lock
                # Try to acquire lock again
                fd = os.open(lock_file_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.close(fd)
            else:
                app.logger.warning(f"Vérification des emails déjà en cours (lock file {lock_file_path} récent).")
                return jsonify({"status": "busy", "message": "Vérification des emails déjà en cours."}), 429
        except Exception as e_lock_check: # Catch issues with stat or unlink
            app.logger.error(f"Erreur lors de la vérification/suppression du lock file {lock_file_path}: {e_lock_check}")
            return jsonify({"status": "error", "message": "Erreur interne (gestion du lock file)."}), 500
    except OSError as e_create_lock:
        app.logger.error(f"Impossible de créer le lock file {lock_file_path}: {e_create_lock}")
        return jsonify({"status": "error", "message": "Erreur interne (création lock file)."}), 500


    error_flag, num_downloaded = 0, 0
    try:
        if not all([ONEDRIVE_CLIENT_ID, ONEDRIVE_CLIENT_SECRET, ONEDRIVE_REFRESH_TOKEN, SENDER_OF_INTEREST]):
            msg = "Configuration Graph API ou SENDER_OF_INTEREST incomplète."
            app.logger.error(msg)
            return jsonify({"status": "error", "message": msg}), 500

        error_flag, num_downloaded = check_emails_via_graph_and_download()

        if error_flag == -1: 
            msg = "Une erreur est survenue pendant la vérification des emails via Graph API."
            status_code = 500
        else:
            msg = f"Vérification emails (Graph API) terminée. {num_downloaded} nouveau(x) fichier(s) transféré(s) vers OneDrive."
            status_code = 200
        
        app.logger.info(msg)
        return jsonify({"status": "success" if status_code==200 else "error", 
                        "message": msg, 
                        "files_downloaded": num_downloaded}), status_code

    except Exception as e:
        app.logger.error(f"Erreur inattendue dans l'endpoint /api/check_emails_and_download: {e}", exc_info=True)
        return jsonify({"status": "error", "message": f"Erreur inattendue: {str(e)}"}), 500
    finally:
        if lock_file_path.exists(): 
            try:
                lock_file_path.unlink(missing_ok=True)
                app.logger.info(f"Lock file {lock_file_path} supprimé.")
            except OSError as e_unlink_lock:
                app.logger.error(f"Impossible de supprimer le lock file {lock_file_path} en fin de traitement: {e_unlink_lock}")


# --- Nouvelle Route Principale pour servir trigger_page.html ---
@app.route('/')
def serve_trigger_page():
    app.logger.info("Route '/' appelée. Tentative de servir 'trigger_page.html'.")
    # Assuming trigger_page.html is in the same directory as app_render.py
    # or in a 'static' subfolder if you prefer. For Render, typically at root.
    # current_app.root_path is the directory where app_render.py is located.
    serve_dir = Path(current_app.root_path)
    file_to_serve = 'trigger_page.html'
    
    expected_file_location = serve_dir / file_to_serve
    
    if not expected_file_location.is_file():
        app.logger.error(f"ERREUR: '{file_to_serve}' NON TROUVÉ à l'emplacement attendu: {expected_file_location.resolve()}")
        try:
            content_list_root = os.listdir(serve_dir)
            app.logger.info(f"Contenu du dossier racine de l'application ('{serve_dir}'): {content_list_root}")
        except Exception as e_ls:
            app.logger.error(f"Impossible de lister le contenu du dossier pour le débogage: {e_ls}")
        return "Erreur: Fichier principal de l'interface non trouvé. Vérifiez les logs du serveur.", 404

    try:
        # send_from_directory's first argument is a directory, second is path relative to it
        return send_from_directory(str(serve_dir), file_to_serve)
    except Exception as e_send:
        app.logger.error(f"Erreur send_from_directory pour '{file_to_serve}' depuis '{serve_dir}': {e_send}", exc_info=True)
        return "Erreur interne du serveur lors de la tentative de servir la page.", 500

# --- Endpoints de statut (peuvent être utiles pour le débogage depuis la page web) ---
# These are less critical now that the main logic is in check_emails_and_download
# but can be kept or removed.
# @app.route('/api/trigger_workflow', methods=['POST']) ...
# @app.route('/api/check_trigger', methods=['GET']) ...
# @app.route('/api/update_local_status', methods=['POST']) ...
# @app.route('/api/get_local_status', methods=['GET']) ...


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    flask_debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    app.logger.info(f"Démarrage du serveur Flask sur le port {port} avec debug={flask_debug_mode}")
    app.run(host='0.0.0.0', port=port, debug=flask_debug_mode)
