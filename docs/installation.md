# Installation et exécution locale

## Prérequis

- Python 3.10+
- Accès IMAP sortant (pare-feu autorisé)
- (Optionnel) Redis accessible si vous souhaitez la déduplication persistante

## Installation

1. Créer un environnement virtuel
```
python3 -m venv .venv
source .venv/bin/activate
```

2. Installer les dépendances
```
pip install -r requirements.txt
```

3. Définir les variables d'environnement minimales (voir `configuration.md`). Exemple (dev):
```
export FLASK_SECRET_KEY="change-me"
export TRIGGER_PAGE_USER="admin"
export TRIGGER_PAGE_PASSWORD="votre_mot_de_passe"
# Email / IMAP
export EMAIL_ADDRESS="..."
export EMAIL_PASSWORD="..."
export IMAP_SERVER="mail.inbox.lt"
export IMAP_PORT=993
export IMAP_USE_SSL=true
# Webhook
export WEBHOOK_URL="https://votre-domaine.tld/webhook"
```

4. Lancer en local (débogage)
```
export FLASK_APP=app_render:app
flask run --host=0.0.0.0 --port=10000
```
- Accéder à http://localhost:10000

## Exécution via Gunicorn (recommandé)

```
pip install gunicorn
# Exemple simple (2 workers sync, à adapter):
gunicorn -w 2 -b 0.0.0.0:10000 app_render:app
```

### Tâches de fond (polling IMAP) et verrou singleton

- Le poller IMAP tourne en **tâche de fond** et doit être activé explicitement via les variables d'environnement (voir `docs/configuration.md`):
  - `ENABLE_BACKGROUND_TASKS=true`
  - `BG_POLLER_LOCK_FILE=/tmp/render_signal_server_email_poller.lock` (défaut)
- Un **verrou fichier** (singleton inter-processus) est utilisé pour éviter plusieurs pollers en parallèle (voir `background/lock.py`).
- Recommandation: n'activer `ENABLE_BACKGROUND_TASKS=true` que sur **un seul** process/worker (ou un service dédié) en production.

## Fichiers statiques et templates

- `dashboard.html` est la page principale (UI Dashboard Webhooks)
- JavaScript principal: `static/dashboard.js`
