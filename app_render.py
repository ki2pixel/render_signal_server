from flask import Flask, jsonify, request, send_from_directory
import os
import time
from pathlib import Path
import json
import logging # Pour un meilleur logging sur Render

app = Flask(__name__)

# Configuration du logging pour l'app Render
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

SIGNAL_DIR = Path(os.environ.get("RENDER_DISC_PATH", "./signal_data"))
TRIGGER_SIGNAL_FILE = SIGNAL_DIR / "workflow_trigger_signal.txt"
LOCAL_STATUS_FILE = SIGNAL_DIR / "current_local_status.json" # Nouveau fichier pour le statut local

SIGNAL_DIR.mkdir(parents=True, exist_ok=True)

@app.route('/')
def serve_trigger_page():
    return send_from_directory('.', 'trigger_page.html')

@app.route('/api/trigger_workflow', methods=['POST'])
def set_trigger():
    try:
        payload = {"command": "run_sequence_0_4", "timestamp": time.time()}
        with open(TRIGGER_SIGNAL_FILE, 'w') as f:
            json.dump(payload, f)
        app.logger.info(f"Signal de déclenchement écrit : {TRIGGER_SIGNAL_FILE}")
        # Initialiser le statut local comme "Commande envoyée, en attente de prise en charge..."
        initial_status = {"status_text": "Commande envoyée, en attente de prise en charge par la machine locale...", "timestamp": time.time()}
        with open(LOCAL_STATUS_FILE, 'w') as f_status:
            json.dump(initial_status, f_status)
        return jsonify({'status': 'success', 'message': 'Signal de lancement positionné.'}), 200
    except Exception as e:
        app.logger.error(f"Erreur écriture signal/statut initial : {e}", exc_info=True)
        return jsonify({'status': 'error', 'message': f'Erreur serveur: {str(e)}'}), 500

@app.route('/api/check_trigger', methods=['GET']) # Utilisé par app.py local
def check_trigger():
    response_data = {'command_pending': False, 'payload': None}
    if TRIGGER_SIGNAL_FILE.exists():
        try:
            with open(TRIGGER_SIGNAL_FILE, 'r') as f:
                payload = json.load(f)
            response_data['command_pending'] = True
            response_data['payload'] = payload
            TRIGGER_SIGNAL_FILE.unlink()
            app.logger.info(f"Signal de déclenchement lu et supprimé : {TRIGGER_SIGNAL_FILE}")
        except Exception as e:
            app.logger.error(f"Erreur lecture/suppression signal : {e}", exc_info=True)
            response_data['command_pending'] = False 
    return jsonify(response_data)

@app.route('/api/update_local_status', methods=['POST']) # Utilisé par app.py local
def update_local_status():
    try:
        data = request.json
        if not data or 'status_text' not in data:
            return jsonify({'status': 'error', 'message': 'Payload de statut invalide.'}), 400
        
        status_to_write = {
            "status_text": data.get("status_text"),
            "current_step_name": data.get("current_step_name", ""),
            "progress_current": data.get("progress_current", 0),
            "progress_total": data.get("progress_total", 0),
            "overall_status": data.get("overall_status", "En cours..."), # ex: "En cours...", "Terminé", "Échoué"
            "timestamp": time.time()
        }
        with open(LOCAL_STATUS_FILE, 'w') as f:
            json.dump(status_to_write, f)
        app.logger.info(f"Statut local mis à jour : {status_to_write.get('overall_status')} - {status_to_write.get('status_text')}")
        return jsonify({'status': 'success', 'message': 'Statut local mis à jour.'}), 200
    except Exception as e:
        app.logger.error(f"Erreur mise à jour statut local : {e}", exc_info=True)
        return jsonify({'status': 'error', 'message': f'Erreur serveur: {str(e)}'}), 500

@app.route('/api/get_local_status', methods=['GET']) # Utilisé par trigger_page.html
def get_local_status():
    if LOCAL_STATUS_FILE.exists():
        try:
            with open(LOCAL_STATUS_FILE, 'r') as f:
                status_data = json.load(f)
            # Optionnel: vérifier si le statut est récent
            # if time.time() - status_data.get("timestamp", 0) > 300: # Plus de 5 minutes
            #     return jsonify({"status_text": "Aucun statut récent de la machine locale.", "overall_status": "Inconnu"})
            return jsonify(status_data), 200
        except Exception as e:
            app.logger.error(f"Erreur lecture statut local : {e}", exc_info=True)
            return jsonify({"status_text": "Erreur lecture statut local sur le serveur.", "overall_status": "Erreur Serveur"}), 500
    else:
        return jsonify({"status_text": "Aucun statut disponible pour la machine locale.", "overall_status": "Non Démarré"}), 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
