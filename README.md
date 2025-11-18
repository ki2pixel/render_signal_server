# render_signal_server

Application Flask modulaires pour le pilotage de webhooks et le polling IMAP. Ce dépôt a été refactoré pour passer d'un fichier monolithique (`app_render.py`) à une architecture claire et testable.

## Surveillance et Logs

### Logs Importants
- **Démarrage** : Vérifiez `BG_POLLER: Singleton lock acquired` pour confirmer le bon démarrage du polling.
- **Vivacité** : Des messages `HEARTBEAT: alive` sont émis toutes les 5 minutes pour confirmer que les threads de fond fonctionnent correctement.
- **Arrêt** : `PROCESS: SIGTERM received` indique un arrêt propre du service.
- **Watcher Make** : `MAKE_WATCHER: background thread started` confirme que le watcher est actif (nécessite `ENABLE_BACKGROUND_TASKS` et `MAKECOM_API_KEY`).

### Surveillance Recommandée
- Configurez une alerte sur l'absence de logs `HEARTBEAT` pendant plus de 10 minutes.
- Surveillez les erreurs de connexion IMAP et les échecs d'envoi de webhooks.
- Consultez les logs pour les entrées `WARNING` et `ERROR` pour détecter les problèmes potentiels.

Consultez [la documentation opérationnelle](docs/operational-guide.md) pour plus de détails sur la configuration et le dépannage.

## Architecture

render_signal_server-main/
├── app_logging/
├── auth/
│   ├── user.py                    # Flask-Login (User, LoginManager)
│   └── helpers.py                 # API key (X-API-Key), décorateur api_key_required
├── background/
│   └── polling_thread.py          # Boucle de polling IMAP (thread) + dépendances injectées
├── config/
│   ├── settings.py                # Variables ENV, constantes REF_*, chemins
│   ├── polling_config.py          # Timezone, vacation mode, validation polling
│   └── webhook_time_window.py     # Fenêtre horaire des webhooks (+ override persistant)
├── deduplication/
│   └── redis_client.py            # Dédoublonnage (email ID, groupes de sujet) via Redis (fallback mémoire)
├── email_processing/
│   ├── imap_client.py             # Connexion IMAP
│   ├── pattern_matching.py        # Patterns (Média Solution, DESABO)
│   ├── webhook_sender.py          # Envoi Make.com (timeouts, retries)
│   └── orchestrator.py            # Orchestration du traitement des emails
├── preferences/
│   └── processing_prefs.py        # Préférences de traitement (validation, persistance, Redis + JSON)
├── routes/
│   ├── __init__.py                # Blueprints regroupés
│   ├── api_webhooks.py            # GET/POST /api/webhooks/config
│   ├── api_polling.py             # POST /api/polling/toggle
│   ├── api_processing.py          # GET/POST /api/processing_prefs
│   ├── api_test.py                # /api/test/* (X-API-Key)
│   ├── dashboard.py               # UI /, /login, /logout
│   └── health.py                  # GET /health
├── static/                        # JS/CSS (dashboard)
├── utils/
│   ├── time_helpers.py            # parse_time_hhmm(), is_within_time_window_local()
│   ├── text_helpers.py            # normalize_*, strip_leading_reply_prefixes(), detect_provider()
│   └── validators.py              # env_bool(), normalize_make_webhook_url()
├── app_render.py                  # Serveur Flask (point d’entrée), délégation vers modules
├── dashboard.html                 # UI principale (onglets)
├── login.html                     # Page de login
├── docs/                          # Documentation technique
└── test_app_render.py             # Suite de tests (pytest)
```

Références détaillées: `docs/architecture.md`, `docs/api.md`, `docs/email_polling.md`, `docs/refactoring-roadmap.md`.

## Mises à jour récentes (12/10/2025)

✅ **Architecture Blueprint Finalisée** - Toutes les routes API ont été extraites dans des blueprints Flask dédiés pour une meilleure modularité et maintenabilité.
✅ **Extraction des Modules Complétée** - La logique principale a été extraite dans des modules spécialisés (auth/, config/, email_processing/, background/, etc.)
✅ **58/58 Tests Réussis** - Toutes les refontes préservent la compatibilité ascendante et la couverture de tests.

## Installation (Dev)

Prérequis: Python 3.10+, Redis (optionnel).

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Créer un fichier d’environnement pour le dev (voir `docs/configuration.md` et `debug/render_signal_server.env`). Principales variables:
- `SECRET_KEY`
- `MAKECOM_API_KEY`
- `WEBHOOK_URL`, `WEBHOOK_SSL_VERIFY`
- `RECADRAGE_MAKE_WEBHOOK_URL`, `AUTOREPONDEUR_MAKE_WEBHOOK_URL`
- `POLLING_*` (jours actifs, créneaux, timezone, vacances)
- `ENABLE_BACKGROUND_TASKS`
- `REDIS_URL` (optionnel)

## Exécution

```bash
export FLASK_APP=app_render:app
flask run --host=0.0.0.0 --port=5000
```

En production: Gunicorn derrière Nginx (voir `docs/deployment.md`). Le poller email doit être activé sur un seul process (lock fichier `/tmp/render_signal_server_email_poller.lock`).

## Tests

```bash
pytest test_app_render.py -v
```

La suite actuelle comporte 58 tests. Le refactoring maintient 58/58 au vert.

## Sécurité

- Authentification par session (Flask-Login) pour l’UI.
- Endpoints `/api/test/*` protégés par `X-API-Key` (voir `auth/helpers.py`).
- Variables d’environnement pour tous les secrets. Aucun secret dans le code.

## Journalisation

- Logs applicatifs via `app.logger`.
- Logs des webhooks centralisés via `app_logging/webhook_logger.py` (Redis si dispo, sinon fichier JSON).

## Décisions et Roadmap

- Les décisions sont tracées dans `memory-bank/decisionLog.md`.
- La progression est suivie dans `memory-bank/progress.md`.
- La roadmap de refactoring se trouve dans `docs/refactoring-roadmap.md`.
