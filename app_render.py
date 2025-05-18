from flask import Flask, jsonify, request, send_from_directory
import os
import time
from pathlib import Path
import json
import logging
import re # Pour les regex
import imaplib # Pour lire les emails
import email # Pour parser les emails
from email.header import decode_header
import requests # Pour télécharger depuis Dropbox et appeler l'API Graph

# Pour l'API Microsoft Graph (OneDrive) avec MSAL
from msal import ConfidentialClientApplication

app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Config Fichiers Signal/Statut (comme avant) ---
SIGNAL_DIR = Path(os.environ.get("RENDER_DISC_PATH", "./signal_data"))
TRIGGER_SIGNAL_FILE = SIGNAL_DIR / "workflow_trigger_signal.txt"
LOCAL_STATUS_FILE = SIGNAL_DIR / "current_local_status.json"
PROCESSED_EMAIL_IDS_FILE = SIGNAL_DIR / "processed_email_ids.txt" # Pour éviter de retraiter les emails
DOWNLOAD_TEMP_DIR_RENDER = SIGNAL_DIR / "temp_downloads" # Pour stocker temporairement avant upload OneDrive

SIGNAL_DIR.mkdir(parents=True, exist_ok=True)
DOWNLOAD_TEMP_DIR_RENDER.mkdir(parents=True, exist_ok=True)

# --- Config Email & Dropbox ---
IMAP_SERVER = os.environ.get('IMAP_SERVER')
EMAIL_ACCOUNT = os.environ.get('EMAIL_ACCOUNT')
EMAIL_PASSWORD = os.environ.get('EMAIL_PASSWORD')
SENDER_OF_INTEREST = os.environ.get('SENDER_OF_INTEREST')

# --- Config API Microsoft Graph (OneDrive) ---
ONEDRIVE_CLIENT_ID = os.environ.get('ONEDRIVE_CLIENT_ID')
ONEDRIVE_CLIENT_SECRET = os.environ.get('ONEDRIVE_CLIENT_SECRET')
ONEDRIVE_TENANT_ID = os.environ.get('ONEDRIVE_TENANT_ID')
ONEDRIVE_AUTHORITY = f"https://login.microsoftonline.com/{ONEDRIVE_TENANT_ID}"
ONEDRIVE_SCOPES = ["https://graph.microsoft.com/.default"]
# ID du dossier parent dans OneDrive (ex: "root" ou un ID spécifique)
# Vous pouvez obtenir l'ID d'un dossier via l'Explorateur Graph ou l'API
ONEDRIVE_TARGET_PARENT_FOLDER_ID = os.environ.get('ONEDRIVE_TARGET_FOLDER_ID', 'root') 
ONEDRIVE_TARGET_SUBFOLDER_NAME = "DropboxDownloadsWorkflow" # Nom du sous-dossier à créer/utiliser

msal_app = None
if ONEDRIVE_CLIENT_ID and ONEDRIVE_CLIENT_SECRET:
    msal_app = ConfidentialClientApplication(
        ONEDRIVE_CLIENT_ID,
        authority=ONEDRIVE_AUTHORITY,
        client_credential=ONEDRIVE_CLIENT_SECRET
    )

# --- Fonctions Utilitaires (find_dropbox_links, etc.) ---
def find_dropbox_links(text):
    pattern = r'https?://www\.dropbox\.com/scl/(?:fo|fi)/[a-zA-Z0-9_/\-]+?\?[^ \n\r<>"]+'
    links = re.findall(pattern, text)
    return list(set(links)) # Éviter les doublons de liens dans un même email

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
        app.logger.error("MSAL app non configurée pour OneDrive.")
        return None
    result = msal_app.acquire_token_silent(ONEDRIVE_SCOPES, account=None)
    if not result:
        app.logger.info("Pas de token MSAL en cache, acquisition d'un nouveau token pour OneDrive.")
        result = msal_app.acquire_token_for_client(scopes=ONEDRIVE_SCOPES)
    if "access_token" in result:
        return result['access_token']
    else:
        app.logger.error(f"Erreur d'acquisition du token OneDrive: {result.get('error_description')}")
        return None

def ensure_onedrive_folder(access_token):
    """Vérifie si le sous-dossier cible existe, sinon le crée. Retourne son ID."""
    headers = {'Authorization': 'Bearer ' + access_token, 'Content-Type': 'application/json'}
    
    # Vérifier si le dossier existe déjà
    folder_check_url = f"https://graph.microsoft.com/v1.0/me/drive/items/{ONEDRIVE_TARGET_PARENT_FOLDER_ID}/children?$filter=name eq '{ONEDRIVE_TARGET_SUBFOLDER_NAME}'"
    response = requests.get(folder_check_url, headers=headers)
    response.raise_for_status()
    children = response.json().get('value', [])
    
    if children:
        folder_id = children[0]['id']
        app.logger.info(f"Dossier OneDrive '{ONEDRIVE_TARGET_SUBFOLDER_NAME}' trouvé avec ID: {folder_id}")
        return folder_id
    else:
        # Créer le dossier
        folder_create_url = f"https://graph.microsoft.com/v1.0/me/drive/items/{ONEDRIVE_TARGET_PARENT_FOLDER_ID}/children"
        payload = {
            "name": ONEDRIVE_TARGET_SUBFOLDER_NAME,
            "folder": {},
            "@microsoft.graph.conflictBehavior": "rename" # ou "fail" ou "replace"
        }
        response = requests.post(folder_create_url, headers=headers, json=payload)
        response.raise_for_status()
        folder_id = response.json()['id']
        app.logger.info(f"Dossier OneDrive '{ONEDRIVE_TARGET_SUBFOLDER_NAME}' créé avec ID: {folder_id}")
        return folder_id


def upload_to_onedrive(filepath, filename_onedrive, access_token, target_folder_id):
    if not access_token or not target_folder_id:
        app.logger.error("Token d'accès OneDrive ou ID dossier cible manquant pour l'upload.")
        return False
        
    upload_url = f"https://graph.microsoft.com/v1.0/me/drive/items/{target_folder_id}:/{filename_onedrive}:/content"
    headers = {'Authorization': 'Bearer ' + access_token, 'Content-Type': 'application/octet-stream'}
    
    file_size = os.path.getsize(filepath)
    app.logger.info(f"Tentative d'upload de '{filepath.name}' ({file_size} bytes) vers OneDrive folder ID {target_folder_id} sous le nom '{filename_onedrive}'")

    # Pour les petits fichiers (< 4MB), un simple PUT suffit
    if file_size < 4 * 1024 * 1024:
        with open(filepath, 'rb') as f_data:
            response = requests.put(upload_url, headers=headers, data=f_data)
    else: # Pour les gros fichiers, utiliser une session d'upload
        create_session_url = f"https://graph.microsoft.com/v1.0/me/drive/items/{target_folder_id}:/{filename_onedrive}:/createUploadSession"
        session_payload = {
            "item": {
                "@microsoft.graph.conflictBehavior": "rename"
            }
        }
        session_headers = {'Authorization': 'Bearer ' + access_token, 'Content-Type': 'application/json'}
        session_response = requests.post(create_session_url, headers=session_headers, json=session_payload)
        if session_response.status_code >= 300:
             app.logger.error(f"Erreur création session d'upload OneDrive: {session_response.status_code} - {session_response.text}")
             return False
        upload_session_url = session_response.json()['uploadUrl']
        app.logger.info(f"Session d'upload OneDrive créée: {upload_session_url}")
        
        # Uploader par morceaux
        chunk_size = 5 * 1024 * 1024 # 5MB chunks
        chunks_uploaded = 0
        with open(filepath, 'rb') as f_data:
            while True:
                chunk = f_data.read(chunk_size)
                if not chunk:
                    break # Fin du fichier
                
                start_byte = chunks_uploaded * chunk_size
                end_byte = start_byte + len(chunk) - 1
                
                chunk_headers = {
                    'Content-Length': str(len(chunk)),
                    'Content-Range': f'bytes {start_byte}-{end_byte}/{file_size}'
                }
                
                app.logger.info(f"Upload du chunk: bytes {start_byte}-{end_byte}/{file_size}")
                response = requests.put(upload_session_url, headers=chunk_headers, data=chunk)
                if response.status_code >= 300 and response.status_code != 201 and response.status_code != 200: # 201 Created (dernier chunk), 200 OK (chunk intermédiaire)
                    app.logger.error(f"Erreur upload chunk OneDrive: {response.status_code} - {response.text}")
                    # Annuler la session d'upload
                    requests.delete(upload_session_url)
                    return False
                chunks_uploaded += 1
        app.logger.info(f"Tous les chunks de '{filepath.name}' uploadés.")
        # La réponse du dernier PUT (si 201 ou 200) contient les métadonnées du fichier final.

    if response.status_code < 300: # 200 OK ou 201 Created
        app.logger.info(f"Fichier '{filename_onedrive}' uploadé avec succès sur OneDrive.")
        return True
    else:
        app.logger.error(f"Erreur finale upload OneDrive ({filename_onedrive}): {response.status_code} - {response.text}")
        return False

def download_and_relay_to_onedrive(dropbox_url):
    """Télécharge depuis Dropbox et upload sur OneDrive."""
    modified_url = dropbox_url.replace("dl=0", "dl=1")
    modified_url = re.sub(r'dl=[^&]+', 'dl=1', modified_url)
    app.logger.info(f"Dropbox: Téléchargement depuis {modified_url}")

    try:
        response = requests.get(modified_url, stream=True, allow_redirects=True, timeout=180) # Timeout plus long
        response.raise_for_status()

        filename_dropbox = "downloaded_file.zip" # Nom par défaut
        content_disposition = response.headers.get('content-disposition')
        if content_disposition:
            fn_match = re.findall('filename="?(.+?)"?(?:;|$)', content_disposition)
            if fn_match: filename_dropbox = fn_match[0]
        
        # Nettoyer le nom de fichier pour OneDrive (caractères non valides, etc.)
        filename_onedrive = re.sub(r'[<>:"/\\|?*]', '_', filename_dropbox)
        temp_filepath = DOWNLOAD_TEMP_DIR_RENDER / filename_onedrive # Utiliser le nom nettoyé pour le temp aussi

        with open(temp_filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192 * 4): # Plus gros chunks pour le téléchargement
                f.write(chunk)
        app.logger.info(f"Dropbox: Téléchargé '{filename_dropbox}' vers '{temp_filepath}'")

        access_token = get_onedrive_access_token()
        if access_token:
            target_folder_id = ensure_onedrive_folder(access_token)
            if target_folder_id:
                if upload_to_onedrive(temp_filepath, filename_onedrive, access_token, target_folder_id):
                    app.logger.info(f"OneDrive: Succès upload de '{filename_onedrive}'")
                    if temp_filepath.exists(): temp_filepath.unlink() # Supprimer le fichier temporaire
                    return True
                else:
                    app.logger.error(f"OneDrive: Échec upload de '{filename_onedrive}'")
            else:
                app.logger.error("OneDrive: Impossible d'obtenir/créer le dossier cible.")
        else:
            app.logger.error("OneDrive: Impossible d'obtenir le token d'accès.")
        
        # Si l'upload a échoué mais le téléchargement a réussi, garder le fichier temp pour investigation
        # if temp_filepath.exists(): temp_filepath.unlink() 
        return False

    except requests.exceptions.RequestException as e:
        app.logger.error(f"Dropbox: Erreur de téléchargement pour {modified_url}: {e}")
        return False
    except Exception as e_main:
        app.logger.error(f"Erreur générale dans download_and_relay_to_onedrive pour {dropbox_url}: {e_main}", exc_info=True)
        return False

# --- Endpoints API (trigger_page, trigger_workflow, check_trigger, update_local_status, get_local_status comme avant) ---
# ... (vos endpoints existants) ...

# --- Nouvel Endpoint pour Déclencher la Vérification des Emails ---
@app.route('/api/check_emails_and_download', methods=['POST'])
def check_emails_and_download():
    app.logger.info("Déclenchement manuel de la vérification des emails et téléchargement Dropbox.")
    # Pour éviter les exécutions multiples si le cron job est fréquent, on pourrait ajouter un verrou simple.
    # if Path(SIGNAL_DIR / "email_check.lock").exists():
    #     return jsonify({"status": "busy", "message": "Vérification des emails déjà en cours."}), 429

    # Path(SIGNAL_DIR / "email_check.lock").touch()
    num_downloaded = 0
    try:
        if not all([IMAP_SERVER, EMAIL_ACCOUNT, EMAIL_PASSWORD, SENDER_OF_INTEREST]):
            msg = "Configuration email incomplète sur le serveur Render."
            app.logger.error(msg)
            return jsonify({"status": "error", "message": msg}), 500

        mail_conn = imaplib.IMAP4_SSL(IMAP_SERVER)
        mail_conn.login(EMAIL_ACCOUNT, EMAIL_PASSWORD)
        mail_conn.select('inbox')
        
        processed_ids = get_processed_email_ids()
        
        # Chercher les emails de l'expéditeur (on peut filtrer sur UNSEEN plus tard si besoin)
        # Pour le test, on prend tous les emails du sender, et on filtre avec processed_ids
        search_criteria = f'(FROM "{SENDER_OF_INTEREST}")'
        status, messages = mail_conn.search(None, search_criteria)

        if status == 'OK':
            email_id_bytes_list = messages[0].split()
            app.logger.info(f"Trouvé {len(email_id_bytes_list)} email(s) de '{SENDER_OF_INTEREST}'.")

            for email_id_bytes in reversed(email_id_bytes_list): # Traiter les plus récents d'abord
                email_id_str = email_id_bytes.decode()
                if email_id_str in processed_ids:
                    app.logger.info(f"Email ID {email_id_str} déjà traité, ignoré.")
                    continue

                app.logger.info(f"Traitement email ID: {email_id_str}")
                _, msg_data = mail_conn.fetch(email_id_bytes, '(RFC822)')
                msg_content = email.message_from_bytes(msg_data[0][1])
                
                # ... (logique d'extraction du corps de l'email, comme dans le script fourni) ...
                body_text = ""
                if msg_content.is_multipart():
                    for part in msg_content.walk():
                        if part.get_content_type() in ["text/plain", "text/html"] and \
                           "attachment" not in str(part.get("Content-Disposition")):
                            try:
                                body_text += part.get_payload(decode=True).decode(part.get_content_charset() or 'utf-8', errors='ignore') + "\n"
                            except: pass
                else:
                    try:
                        body_text = msg_content.get_payload(decode=True).decode(msg_content.get_content_charset() or 'utf-8', errors='ignore')
                    except: pass
                
                if body_text:
                    links_found = find_dropbox_links(body_text)
                    if links_found:
                        app.logger.info(f"Email ID {email_id_str}: Liens Dropbox trouvés: {links_found}")
                        for link in links_found:
                            if download_and_relay_to_onedrive(link):
                                num_downloaded += 1
                        add_processed_email_id(email_id_str) # Marquer comme traité APRES traitement des liens
                    else:
                        app.logger.info(f"Email ID {email_id_str}: Aucun lien Dropbox trouvé dans le corps.")
                        add_processed_email_id(email_id_str) # Marquer aussi pour ne pas le re-scanner inutilement
                else:
                    app.logger.warning(f"Email ID {email_id_str}: Impossible d'extraire le corps du texte.")
                    add_processed_email_id(email_id_str)
        mail_conn.logout()
        
        msg = f"Vérification des emails terminée. {num_downloaded} nouveau(x) fichier(s) téléchargé(s) et transféré(s) vers OneDrive."
        app.logger.info(msg)
        # if Path(SIGNAL_DIR / "email_check.lock").exists(): Path(SIGNAL_DIR / "email_check.lock").unlink()
        return jsonify({"status": "success", "message": msg, "files_downloaded": num_downloaded})

    except imaplib.IMAP4.error as e_imap:
        app.logger.error(f"Erreur IMAP: {e_imap}", exc_info=True)
        # if Path(SIGNAL_DIR / "email_check.lock").exists(): Path(SIGNAL_DIR / "email_check.lock").unlink()
        return jsonify({"status": "error", "message": f"Erreur IMAP: {str(e_imap)}"}), 500
    except Exception as e:
        app.logger.error(f"Erreur inattendue pendant vérification emails: {e}", exc_info=True)
        # if Path(SIGNAL_DIR / "email_check.lock").exists(): Path(SIGNAL_DIR / "email_check.lock").unlink()
        return jsonify({"status": "error", "message": f"Erreur inattendue: {str(e)}"}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port) # debug=False est généralement mieux pour Render
