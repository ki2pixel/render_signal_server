from flask import Flask, jsonify, request, send_from_directory
import os
import time
from pathlib import Path

app = Flask(__name__)

# Configurer un chemin pour le fichier de signal.
# Render offre un disque persistant pour les services payants.
# Pour les services gratuits, le système de fichiers est éphémère mais peut fonctionner pour un test.
# Un dossier 'data' à la racine de votre projet sur Render est une option.
SIGNAL_DIR = Path(os.environ.get("RENDER_DISC_PATH", "./signal_data")) # Utilise un disque persistant si monté
SIGNAL_FILE = SIGNAL_DIR / "workflow_trigger_signal.txt"

# Assurer que le dossier pour le signal existe
SIGNAL_DIR.mkdir(parents=True, exist_ok=True)

@app.route('/')
def serve_trigger_page():
    return send_from_directory('.', 'trigger_page.html')

@app.route('/api/trigger_workflow', methods=['POST'])
def set_trigger():
    try:
        # Écrire un timestamp ou un payload JSON simple dans le fichier de signal
        payload = {"command": "run_sequence_0_4", "timestamp": time.time()}
        with open(SIGNAL_FILE, 'w') as f:
            json.dump(payload, f)
        app.logger.info(f"Signal de déclenchement écrit dans {SIGNAL_FILE}")
        return jsonify({'status': 'success', 'message': 'Signal de lancement du workflow positionné.'}), 200
    except Exception as e:
        app.logger.error(f"Erreur lors de l'écriture du signal : {e}", exc_info=True)
        return jsonify({'status': 'error', 'message': f'Erreur serveur lors de la création du signal: {str(e)}'}), 500

@app.route('/api/check_trigger', methods=['GET'])
def check_trigger():
    # Optionnel: ajoutez un simple token pour sécuriser cet endpoint si vous le souhaitez
    # expected_token = "VOTRE_TOKEN_SECRET_PARTAGE_AVEC_APP_PY_LOCAL"
    # received_token = request.args.get("token")
    # if received_token != expected_token:
    #     return jsonify({'error': 'Unauthorized'}), 401
        
    response_data = {'command_pending': False, 'payload': None}
    if SIGNAL_FILE.exists():
        try:
            with open(SIGNAL_FILE, 'r') as f:
                payload = json.load(f)
            
            # Logique pour considérer le signal comme "actif" (ex: récent)
            # Si le signal est plus vieux que X minutes, on pourrait l'ignorer.
            # Pour l'instant, si le fichier existe, la commande est en attente.
            response_data['command_pending'] = True
            response_data['payload'] = payload
            
            # IMPORTANT : Supprimer le fichier de signal après l'avoir lu pour éviter re-déclenchements
            SIGNAL_FILE.unlink() 
            app.logger.info(f"Signal lu et supprimé de {SIGNAL_FILE}")
        except FileNotFoundError: # Peut arriver si un autre poller l'a supprimé entre temps
            app.logger.info(f"Fichier signal {SIGNAL_FILE} non trouvé (probablement déjà traité).")
            response_data['command_pending'] = False
        except Exception as e:
            app.logger.error(f"Erreur lors de la lecture/suppression du signal : {e}", exc_info=True)
            # Ne pas renvoyer command_pending=True si on n'est pas sûr
            response_data['command_pending'] = False 
            # On pourrait retourner une erreur ici, mais pour le client local, il vaut mieux ne pas déclencher
    return jsonify(response_data)

if __name__ == '__main__':
    # Le port est généralement géré par Render via la variable d'environnement PORT
    port = int(os.environ.get('PORT', 8080)) 
    # Écouter sur 0.0.0.0 pour être accessible dans l'environnement Docker de Render
    app.run(host='0.0.0.0', port=port)