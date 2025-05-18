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
ONEDRIVE_REFRESH_TOKEN = os.environ.get('ONEDRIVE_REFRESH_TOKEN') # <-- NOUVEAU: Lire le refresh token

# IMPORTANT: Pour les comptes personnels Microsoft (Outlook.com, Hotmail, Live), l'autorité est 'consumers'
ONEDRIVE_AUTHORITY = "https://login.microsoftonline.com/consumers"
# Scopes délégués demandés lors de l'obtention du refresh token (doivent correspondre)
ONEDRIVE_SCOPES_DELEGATED = ["Files.ReadWrite", "User.Read", "offline_access"]

# ID du dossier parent dans OneDrive (ex: "root" ou un ID spécifique)
ONEDRIVE_TARGET_PARENT_FOLDER_ID = os.environ.get('ONEDRIVE_TARGET_PARENT_FOLDER_ID', 'root') 
ONEDRIVE_TARGET_SUBFOLDER_NAME = os.environ.get('ONEDRIVE_TARGET_SUBFOLDER_NAME', "DropboxDownloadsWorkflow")

msal_app = None
if ONEDRIVE_CLIENT_ID and ONEDRIVE_CLIENT_SECRET:
    app.logger.info(f"Configuration de MSAL ConfidentialClientApplication avec Client ID et Authority: {ONEDRIVE_AUTHORITY}")
    msal_app = ConfidentialClientApplication(
        ONEDRIVE_CLIENT_ID,
        authority=ONEDRIVE_AUTHORITY, # Utiliser l'autorité 'consumers'
        client_credential=ONEDRIVE_CLIENT_SECRET
    )
else:
    app.logger.warning("ONEDRIVE_CLIENT_ID ou ONEDRIVE_CLIENT_SECRET manquant. L'intégration OneDrive sera désactivée.")


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

def get_onedrive_access_token(): # *** CETTE FONCTION EST MISE À JOUR ***
    if not msal_app:
        app.logger.error("MSAL ConfidentialClientApplication (msal_app) n'est pas configurée pour OneDrive.")
        return None
    if not ONEDRIVE_REFRESH_TOKEN:
        app.logger.error("ONEDRIVE_REFRESH_TOKEN manquant dans les variables d'environnement. "
                         "Impossible d'obtenir un token d'accès OneDrive.")
        return None

    app.logger.info("Tentative d'acquisition d'un token d'accès OneDrive en utilisant le refresh token.")
    
    # Utiliser acquire_token_by_refresh_token avec les scopes délégués
    result = msal_app.acquire_token_by_refresh_token(
        ONEDRIVE_REFRESH_TOKEN,
        scopes=ONEDRIVE_SCOPES_DELEGATED 
    )

    if "access_token" in result:
        app.logger.info("Nouveau token d'accès OneDrive obtenu avec succès via refresh token.")
        
        # Gestion optionnelle d'un nouveau refresh token retourné par le serveur
        # Microsoft peut émettre un nouveau refresh token. Idéalement, il faudrait le stocker.
        # Pour une application Render, la mise à jour programmatique des variables d'env n'est pas directe.
        # Le refresh token initial est généralement à longue durée de vie.
        new_rt = result.get("refresh_token")
        if new_rt and new_rt != ONEDRIVE_REFRESH_TOKEN:
            app.logger.warning("Un nouveau refresh token OneDrive a été émis par le serveur. "
                               "L'application continuera d'utiliser l'ancien refresh token (ONEDRIVE_REFRESH_TOKEN). "
                               "Si des problèmes d'authentification surviennent à l'avenir, "
                               "il faudra mettre à jour manuellement ONEDRIVE_REFRESH_TOKEN avec cette nouvelle valeur (si loggée) "
                               "ou le regénérer.")
            # Pour une robustesse accrue, on pourrait stocker ce new_rt dans un fichier sécurisé
            # ou une base de données, mais cela complexifie l'architecture.

        return result['access_token']
    else:
        error_description = result.get('error_description', "Aucune description d'erreur fournie.")
        error_code = result.get('error', "Aucun code d'erreur fourni.")
        app.logger.error(f"Erreur lors de l'acquisition du token OneDrive avec refresh token: {error_code} - {error_description}")
        app.logger.error(f"Détails complets de l'erreur MSAL: {result}")
        # Si le refresh token est invalide (ex: révoqué, expiré), il faudra en obtenir un nouveau
        # manuellement via le script get_refresh_token.py et mettre à jour la variable d'environnement.
        return None

def ensure_onedrive_folder(access_token):
    """Vérifie si le sous-dossier cible existe, sinon le crée. Retourne son ID."""
    headers = {'Authorization': 'Bearer ' + access_token, 'Content-Type': 'application/json'}
    
    folder_check_url = f"https://graph.microsoft.com/v1.0/me/drive/items/{ONEDRIVE_TARGET_PARENT_FOLDER_ID}/children?$filter=name eq '{ONEDRIVE_TARGET_SUBFOLDER_NAME}'"
    try:
        response = requests.get(folder_check_url, headers=headers)
        response.raise_for_status() # Lève une exception pour les codes d'erreur HTTP
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
    
    final_response = None # Pour stocker la réponse finale de l'upload

    try:
        if file_size < 4 * 1024 * 1024: # Pour les petits fichiers (< 4MB)
            with open(filepath, 'rb') as f_data:
                response = requests.put(upload_url_simple_put, headers=headers_put, data=f_data)
                response.raise_for_status()
                final_response = response
        else: # Pour les gros fichiers, utiliser une session d'upload
            create_session_url = f"https://graph.microsoft.com/v1.0/me/drive/items/{target_folder_id}:/{filename_onedrive}:/createUploadSession"
            session_payload = {"item": {"@microsoft.graph.conflictBehavior": "rename"}}
            session_headers = {'Authorization': 'Bearer ' + access_token, 'Content-Type': 'application/json'}
            
            session_response = requests.post(create_session_url, headers=session_headers, json=session_payload)
            session_response.raise_for_status()
            upload_session_url = session_response.json()['uploadUrl']
            app.logger.info(f"Session d'upload OneDrive créée: {upload_session_url}")
            
            chunk_size = 5 * 1024 * 1024 # 5MB chunks
            chunks_uploaded_count = 0
            with open(filepath, 'rb') as f_data:
                while True:
                    chunk = f_data.read(chunk_size)
                    if not chunk:
                        break 
                    
                    start_byte = chunks_uploaded_count * chunk_size
                    end_byte = start_byte + len(chunk) - 1
                    
                    chunk_headers = {
                        'Content-Length': str(len(chunk)),
                        'Content-Range': f'bytes {start_byte}-{end_byte}/{file_size}'
                    }
                    
                    app.logger.info(f"Upload du chunk: bytes {start_byte}-{end_byte}/{file_size}")
                    response_chunk = requests.put(upload_session_url, headers=chunk_headers, data=chunk)
                    response_chunk.raise_for_status() # Lève une exception pour les erreurs
                    final_response = response_chunk # Le dernier chunk réussi contient les infos du fichier
                    chunks_uploaded_count += 1
            app.logger.info(f"Tous les chunks de '{filepath.name}' uploadés.")

        if final_response and final_response.status_code < 300: # 200 OK ou 201 Created
            app.logger.info(f"Fichier '{filename_onedrive}' uploadé avec succès sur OneDrive. Réponse: {final_response.status_code}")
            return True
        else:
            # Ce cas ne devrait pas être atteint si raise_for_status() fonctionne comme prévu
            app.logger.error(f"Erreur inattendue après l'upload OneDrive ({filename_onedrive}). Status: {final_response.status_code if final_response else 'N/A'}")
            return False

    except requests.exceptions.RequestException as e:
        app.logger.error(f"Erreur API Graph lors de l'upload vers OneDrive ({filename_onedrive}): {e}")
        if hasattr(e, 'response') and e.response is not None:
            app.logger.error(f"Réponse de l'API Graph: {e.response.status_code} - {e.response.text}")
            if e.response.status_code == 401: # Unauthorized
                 app.logger.error("L'erreur 401 Unauthorized suggère un problème avec le token d'accès. Vérifiez sa validité et les scopes.")
            # Si c'était une session d'upload, il faudrait l'annuler en cas d'échec partiel
            if 'upload_session_url' in locals() and file_size >= 4 * 1024 * 1024:
                app.logger.info(f"Tentative d'annulation de la session d'upload: {upload_session_url}")
                requests.delete(upload_session_url, headers={'Authorization': 'Bearer ' + access_token}) # Pas besoin de vérifier la réponse ici
        return False
    except Exception as ex:
        app.logger.error(f"Erreur générale inattendue pendant l'upload OneDrive ({filename_onedrive}): {ex}", exc_info=True)
        return False


def download_and_relay_to_onedrive(dropbox_url):
    """Télécharge depuis Dropbox et upload sur OneDrive."""
    modified_url = dropbox_url.replace("dl=0", "dl=1")
    modified_url = re.sub(r'dl=[^&]+', 'dl=1', modified_url) # Plus robuste
    app.logger.info(f"Dropbox: Téléchargement depuis {modified_url}")

    try:
        response = requests.get(modified_url, stream=True, allow_redirects=True, timeout=300) # Timeout augmenté
        response.raise_for_status()

        filename_dropbox = "downloaded_file_from_dropbox" # Nom par défaut plus descriptif
        content_disposition = response.headers.get('content-disposition')
        if content_disposition:
            fn_match = re.search(r'filename\*?=(?:UTF-8\'\')?([^;\n\r"]+)', content_disposition, flags=re.IGNORECASE)
            if fn_match:
                filename_dropbox = requests.utils.unquote(fn_match.group(1)).strip('"')
            else: # Fallback pour les cas simples sans encodage spécial
                fn_match_simple = re.findall('filename="?(.+?)"?(?:;|$)', content_disposition)
                if fn_match_simple: filename_dropbox = fn_match_simple[0]

        filename_onedrive = re.sub(r'[<>:"/\\|?*]', '_', filename_dropbox) # Nettoyer pour OneDrive
        filename_onedrive = filename_onedrive[:200] # Limiter la longueur du nom de fichier si nécessaire
        temp_filepath = DOWNLOAD_TEMP_DIR_RENDER / filename_onedrive

        with open(temp_filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192 * 4): 
                f.write(chunk)
        app.logger.info(f"Dropbox: Téléchargé '{filename_dropbox}' vers '{temp_filepath}'")

        access_token = get_onedrive_access_token() # Obtient le token via refresh token
        if access_token:
            target_folder_id = ensure_onedrive_folder(access_token)
            if target_folder_id:
                if upload_to_onedrive(temp_filepath, filename_onedrive, access_token, target_folder_id):
                    app.logger.info(f"OneDrive: Succès upload de '{filename_onedrive}'")
                    if temp_filepath.exists(): temp_filepath.unlink() 
                    return True
                else:
                    app.logger.error(f"OneDrive: Échec upload de '{filename_onedrive}'")
            else:
                app.logger.error("OneDrive: Impossible d'obtenir/créer le dossier cible.")
        else:
            app.logger.error("OneDrive: Impossible d'obtenir le token d'accès (get_onedrive_access_token a échoué).")
        
        # Si l'upload a échoué mais le téléchargement a réussi, garder le fichier temp pour investigation
        # if temp_filepath.exists(): temp_filepath.unlink() 
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
        if 'temp_filepath' in locals() and temp_filepath.exists():
             app.logger.info(f"Le fichier temporaire {temp_filepath} est conservé suite à l'erreur.")
        return False

# --- Endpoint pour Déclencher la Vérification des Emails ---
@app.route('/api/check_emails_and_download', methods=['POST'])
def check_emails_and_download():
    app.logger.info("Déclenchement manuel de la vérification des emails et téléchargement Dropbox vers OneDrive.")
    
    # Verrou simple pour éviter exécutions concurrentes (optionnel mais recommandé pour les cron jobs fréquents)
    lock_file = SIGNAL_DIR / "email_check.lock"
    if lock_file.exists():
        try: # Vérifier l'âge du verrou pour éviter un blocage permanent en cas de crash
            if time.time() - lock_file.stat().st_mtime < 300: # 5 minutes
                 app.logger.warning("Vérification des emails déjà en cours (lock file récent).")
                 return jsonify({"status": "busy", "message": "Vérification des emails déjà en cours."}), 429
            else:
                app.logger.warning("Ancien lock file trouvé, suppression et poursuite.")
                lock_file.unlink()
        except OSError as e: # Erreur de suppression, etc.
            app.logger.error(f"Erreur avec le lock file {lock_file}: {e}")


    lock_file.touch()
    num_downloaded = 0
    try:
        if not all([IMAP_SERVER, EMAIL_ACCOUNT, EMAIL_PASSWORD, SENDER_OF_INTEREST]):
            msg = "Configuration email (IMAP_SERVER, EMAIL_ACCOUNT, etc.) incomplète sur le serveur."
            app.logger.error(msg)
            if lock_file.exists(): lock_file.unlink()
            return jsonify({"status": "error", "message": msg}), 500

        # Vérification de la configuration OneDrive minimale pour cette fonctionnalité
        if not all([ONEDRIVE_CLIENT_ID, ONEDRIVE_CLIENT_SECRET, ONEDRIVE_REFRESH_TOKEN]):
            msg = "Configuration OneDrive (CLIENT_ID, CLIENT_SECRET, REFRESH_TOKEN) incomplète."
            app.logger.error(msg)
            if lock_file.exists(): lock_file.unlink()
            return jsonify({"status": "error", "message": msg}), 500

        mail_conn = imaplib.IMAP4_SSL(IMAP_SERVER)
        mail_conn.login(EMAIL_ACCOUNT, EMAIL_PASSWORD)
        mail_conn.select('inbox')
        
        processed_ids = get_processed_email_ids()
        
        search_criteria = f'(FROM "{SENDER_OF_INTEREST}")'
        # Alternative: '(UNSEEN FROM "SENDER_OF_INTEREST")' pour ne prendre que les non-lus
        # Mais le filtrage par processed_ids est plus robuste contre les ratés ou redémarrages.
        
        status, messages = mail_conn.search(None, search_criteria)

        if status == 'OK':
            email_id_bytes_list = messages[0].split()
            app.logger.info(f"Trouvé {len(email_id_bytes_list)} email(s) de '{SENDER_OF_INTEREST}' (avant filtrage des déjà traités).")

            # Trier pour traiter les plus anciens d'abord ou les plus récents d'abord.
            # reversed() traite les plus récents en premier si la liste d'IDs est triée par réception.
            for email_id_bytes in reversed(email_id_bytes_list): 
                email_id_str = email_id_bytes.decode()
                if email_id_str in processed_ids:
                    # app.logger.debug(f"Email ID {email_id_str} déjà traité, ignoré.") # Moins verbeux
                    continue

                app.logger.info(f"Traitement email ID: {email_id_str}")
                _, msg_data = mail_conn.fetch(email_id_bytes, '(RFC822)')
                if not msg_data or not msg_data[0]: # Vérifier si msg_data est valide
                    app.logger.warning(f"Email ID {email_id_str}: Données de message vides ou invalides.")
                    add_processed_email_id(email_id_str) # Marquer comme traité pour éviter boucle infinie
                    continue

                msg_content = email.message_from_bytes(msg_data[0][1])
                
                body_text = ""
                if msg_content.is_multipart():
                    for part in msg_content.walk():
                        content_type = part.get_content_type()
                        content_disposition = str(part.get("Content-Disposition"))

                        if content_type in ["text/plain", "text/html"] and "attachment" not in content_disposition:
                            try:
                                payload = part.get_payload(decode=True)
                                charset = part.get_content_charset() or 'utf-8'
                                body_text += payload.decode(charset, errors='replace') + "\n"
                            except Exception as e_decode:
                                app.logger.warning(f"Email ID {email_id_str}: Erreur décodage partie ({content_type}): {e_decode}")
                else:
                    try:
                        payload = msg_content.get_payload(decode=True)
                        charset = msg_content.get_content_charset() or 'utf-8'
                        body_text = payload.decode(charset, errors='replace')
                    except Exception as e_decode_single:
                        app.logger.warning(f"Email ID {email_id_str}: Erreur décodage corps (simple): {e_decode_single}")
                
                if body_text:
                    links_found = find_dropbox_links(body_text)
                    if links_found:
                        app.logger.info(f"Email ID {email_id_str}: Liens Dropbox trouvés: {links_found}")
                        success_for_this_email = True
                        for link in links_found:
                            if not download_and_relay_to_onedrive(link):
                                success_for_this_email = False # Si un lien échoue, on considère l'email comme non entièrement traité (ou on logue l'erreur)
                                app.logger.error(f"Échec du traitement du lien {link} pour l'email ID {email_id_str}")
                            else:
                                num_downloaded += 1
                        # Marquer comme traité seulement si tous les liens ont réussi,
                        # ou toujours marquer pour éviter de le retraiter si certains liens sont problématiques.
                        # Actuellement: on marque comme traité même si un lien échoue, pour éviter de le scanner à nouveau.
                        # Une meilleure stratégie pourrait être de stocker les liens échoués pour une nouvelle tentative.
                        add_processed_email_id(email_id_str)
                    else:
                        app.logger.info(f"Email ID {email_id_str}: Aucun lien Dropbox trouvé dans le corps.")
                        add_processed_email_id(email_id_str) 
                else:
                    app.logger.warning(f"Email ID {email_id_str}: Impossible d'extraire le corps du texte (vide ou non décodable).")
                    add_processed_email_id(email_id_str) # Marquer pour ne pas le re-scanner
        else:
             app.logger.error(f"Échec de la recherche d'emails: {status}")
        mail_conn.close() # Fermer la boîte sélectionnée
        mail_conn.logout()
        
        msg = f"Vérification des emails terminée. {num_downloaded} nouveau(x) fichier(s) téléchargé(s) et transféré(s) vers OneDrive."
        app.logger.info(msg)
        if lock_file.exists(): lock_file.unlink()
        return jsonify({"status": "success", "message": msg, "files_downloaded": num_downloaded})

    except imaplib.IMAP4.error as e_imap:
        app.logger.error(f"Erreur IMAP: {e_imap}", exc_info=True)
        if lock_file.exists(): lock_file.unlink()
        return jsonify({"status": "error", "message": f"Erreur IMAP: {str(e_imap)}"}), 500
    except Exception as e:
        app.logger.error(f"Erreur inattendue pendant la vérification des emails: {e}", exc_info=True)
        if lock_file.exists(): lock_file.unlink()
        return jsonify({"status": "error", "message": f"Erreur inattendue: {str(e)}"}), 500

# --- Endpoints API de base (non modifiés par rapport à la demande, mais inclus pour la complétude) ---
@app.route('/')
def home():
    return "Signal Server for Workflow Orchestration is running."

@app.route('/signal_status_page')
def signal_status_page():
    return send_from_directory('.', 'signal_status_page.html')

@app.route('/api/trigger_workflow', methods=['POST'])
def trigger_workflow():
    timestamp = time.time()
    with open(TRIGGER_SIGNAL_FILE, "w") as f:
        f.write(str(timestamp))
    app.logger.info(f"Workflow triggered via API at {timestamp}. Signal file updated.")
    return jsonify({"status": "success", "message": "Workflow triggered", "timestamp": timestamp})

@app.route('/api/check_trigger', methods=['GET'])
def check_trigger():
    if TRIGGER_SIGNAL_FILE.exists():
        try:
            timestamp = TRIGGER_SIGNAL_FILE.read_text()
            TRIGGER_SIGNAL_FILE.unlink() # Consommer le signal
            app.logger.info(f"Trigger signal consumed. Timestamp: {timestamp}")
            return jsonify({"triggered": True, "timestamp": float(timestamp)})
        except Exception as e:
            app.logger.error(f"Error processing trigger signal file: {e}")
            return jsonify({"triggered": False, "error": str(e)}), 500
    return jsonify({"triggered": False})

@app.route('/api/update_local_status', methods=['POST'])
def update_local_status():
    data = request.json
    with open(LOCAL_STATUS_FILE, "w") as f:
        json.dump(data, f)
    app.logger.info(f"Local status updated: {data}")
    return jsonify({"status": "success", "message": "Local status updated"})

@app.route('/api/get_local_status', methods=['GET'])
def get_local_status():
    if LOCAL_STATUS_FILE.exists():
        with open(LOCAL_STATUS_FILE, "r") as f:
            status_data = json.load(f)
        return jsonify(status_data)
    return jsonify({"status": "idle", "message": "No local status file found."})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    # debug=False est généralement mieux pour Render, True pour le dev local si besoin
    app.run(host='0.0.0.0', port=port, debug=os.environ.get('FLASK_DEBUG', 'False').lower() == 'true')

--- END OF FILE app_render.py ---
