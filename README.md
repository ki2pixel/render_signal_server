# render_signal_server

Application Flask modulaires pour le pilotage de webhooks et le polling IMAP. Ce dépôt a été refactoré pour passer d'un fichier monolithique (`app_render.py`) à une architecture claire et testable.

## Documentation

- Documentation principale : `docs/README.md`
- Architecture & services : `docs/architecture/overview.md`
- API HTTP : `docs/architecture/api.md`
- Pôles Fonctionnels : `docs/features/` (`email_polling.md`, `webhooks.md`, `ui.md`)
- Configuration & Stockage : `docs/configuration/` (`configuration.md`, `storage.md`, `installation.md`)
- Déploiement & Opérations : `docs/operations/` (`deploiement.md`, `operational-guide.md`, `checklist_production.md`, `depannage.md`)
- Tests & qualité : `docs/quality/testing.md`
- Intégrations : `docs/integrations/` (`r2_offload.md`, `r2_dropbox_limitations.md`, `gmail-oauth-setup.md`)

## Déploiement Render (Docker + GHCR)

- L’application est construite via le `Dockerfile` racine, qui embarque Gunicorn et la configuration des threads/fils de poller (`GUNICORN_*`).
- Le workflow GitHub Actions `.github/workflows/render-image.yml` :
  1. Construit l’image depuis la racine du dépôt.
  2. La pousse sur GitHub Container Registry (`ghcr.io/<owner>/<repo>:latest` + `:<sha>`).
  3. Déclenche Render par ordre de priorité : Deploy Hook (`RENDER_DEPLOY_HOOK_URL`) → API Render (`RENDER_API_KEY`, `RENDER_SERVICE_ID`, `RENDER_DEPLOY_CLEAR_CACHE`) → fallback manuel.
- Les secrets GHCR/Render doivent être configurés côté GitHub Actions. Render récupère ensuite l’image et injecte les variables historiques (`ENABLE_BACKGROUND_TASKS`, `WEBHOOK_URL`, etc.).
- URL actuelle : `https://render-signal-server-latest.onrender.com` (cf. `memory-bank/activeContext.md` pour l’instance vivante).
- Pour les environnements on-premise, les instructions “Gunicorn + Reverse Proxy” restent valables (cf. `docs/deploiement.md`).

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

## Nouvelles fonctionnalités (2026)

### 🎯 Absence Globale
- **Fonctionnalité** : Blocage complet de l'envoi de webhooks sur des jours spécifiques de la semaine
- **Configuration** : Via l'interface dashboard ou API (`/api/webhooks/config`)
- **Priorité** : Plus haute priorité, ignore les autres règles (fenêtre horaire, bypass DESABO)
- **Implémentation** : Service `WebhookConfigService` avec champs `absence_pause_enabled`/`absence_pause_days`

### 🔐 Authentification par Magic Link
- **Service** : `MagicLinkService` (singleton) pour générer/valider des tokens signés HMAC SHA-256
- **Stockage** : Tokens dans `MAGIC_LINK_TOKENS_FILE` (JSON verrouillé) avec TTL configurable
- **API** : Endpoint `/api/auth/magic-link` (session requise) pour générer liens one-shot ou permanents
- **Interface** : Dashboard `dashboard.html` avec bouton de génération et copie automatique
- **Sécurité** : Logs `MAGIC_LINK:*`, nettoyage auto tokens expirés, support stockage partagé via API PHP

### ☁️ Offload Cloudflare R2
- **Service** : `R2TransferService` (singleton) pour économiser la bande passante Render
- **Architecture** : Worker Cloudflare `deployment/cloudflare-worker/worker.js` avec authentification `X-R2-FETCH-TOKEN`
- **Fonctionnalités** : Normalisation Dropbox, fetch distant, persistance paires `source_url`/`r2_url` dans `webhook_links.json`
- **Intégration** : Orchestrator `email_processing/orchestrator.py#645-711` enrichit `delivery_links` si `R2_FETCH_ENABLED=true`
- **Économies** : ~$5/mois pour 50 GB transférés, auto-nettoyage 24h via `cleanup.js`

### 🐳 Déploiement Docker GHCR
- **Pipeline** : Workflow GitHub Actions `.github/workflows/render-image.yml` (build/push GHCR, déclenchement Render)
- **Image** : `Dockerfile` racine avec Gunicorn, variables `GUNICORN_*`, logs stdout/stderr
- **Déploiement** : URL `https://render-signal-server-latest.onrender.com` via Deploy Hook ou API Render
- **Avantages** : Temps de déploiement réduit, image pré-buildée, logs centralisés

## Architecture

```
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
│   ├── webhook_sender.py          # Envoi des webhooks externes (timeouts, retries)
│   └── orchestrator.py            # Orchestration du traitement des emails
├── preferences/
│   └── processing_prefs.py        # Préférences de traitement (validation, persistance, Redis + JSON)
├── routes/
│   ├── __init__.py                # Blueprints regroupés
│   ├── api_webhooks.py            # Gestion de la configuration des webhooks
│   ├── api_polling.py             # Endpoints liés au polling IMAP
│   ├── api_processing.py          # Préférences de traitement (GET/POST)
│   ├── api_test.py                # /api/test/* (X-API-Key)
│   ├── api_admin.py               # Administration (redémarrage, déploiement Render, check emails)
│   ├── api_config.py              # Configuration runtime (fenêtres horaires, flags, polling)
│   ├── api_utility.py             # Ping, triggers locaux, statut
│   ├── api_make.py                # Pilotage manuel des scénarios Make (legacy)
│   ├── api_auth.py                # Authentification Magic Link
│   ├── dashboard.py               # UI /, /login, /logout
│   └── health.py                  # GET /health
├── services/                      # Services orientés métier/configuration (ConfigService, AuthService, etc.)
│   ├── config_service.py          # Gestion centralisée de la configuration
│   ├── auth_service.py            # Authentification et autorisation
│   ├── runtime_flags_service.py   # Gestion dynamique des fonctionnalités (Singleton)
│   ├── webhook_config_service.py  # Configuration et validation des webhooks (Singleton)
│   ├── deduplication_service.py   # Prévention des doublons (Redis + fallback mémoire)
│   ├── polling_config_service.py  # Configuration du polling IMAP
│   ├── r2_transfer_service.py     # Offload Cloudflare R2 (Singleton)
│   └── magic_link_service.py      # Gestion des magic links (Singleton)
├── static/                        # JS/CSS (dashboard)
├── utils/
│   ├── time_helpers.py            # parse_time_hhmm(), is_within_time_window_local()
│   ├── text_helpers.py            # normalize_*, strip_leading_reply_prefixes(), detect_provider()
│   └── validators.py              # env_bool(), normalize_make_webhook_url()
├── app_render.py                  # Serveur Flask (point d'entrée), enregistrement des blueprints et services
├── dashboard.html                 # UI principale (onglets)
├── login.html                     # Page de login
├── docs/                          # Documentation technique (voir docs/README.md)
├── test_app_render.py             # Tests historiques sur app_render.py
└── tests/                         # Suite de tests principale (pytest)
```

Références détaillées : `docs/README.md`, `docs/architecture.md`, `docs/api.md`, `docs/email_polling.md`, `docs/testing.md`.

## Refactoring (historique)

Le refactoring complet vers l'architecture orientée services (services dédiés, blueprints, nettoyage d'app_render.py, montée en couverture de tests) est documenté en détail dans :

- `docs/refactoring-conformity-report.md` – rapport de conformité final
- `ACHIEVEMENT_100_PERCENT.md` – récapitulatif "100% refactoring" (historique)

## Installation (Dev)

Prérequis : Python 3.10+, Redis (optionnel).

**Environnement virtuel prioritaire (partagé)**  
Pour économiser l’espace disque local et mutualiser les dépendances, utilise le virtualenv partagé monté sur `/mnt/venv_ext4/venv_render_signal_server` :

```bash
python3 -m venv /mnt/venv_ext4/venv_render_signal_server
source /mnt/venv_ext4/venv_render_signal_server/bin/activate
python -m pip install -r requirements.txt
```

Assure-toi que `which python` et `python -m pip --version` pointent vers `/mnt/venv_ext4/venv_render_signal_server/bin` avant de lancer la moindre commande Flask/pytest.

**Alternative locale**  
Si tu n’as pas accès au montage `/mnt/venv_ext4`, tu peux encore créer un virtualenv local à la racine :

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Créer un fichier d’environnement pour le dev (voir `docs/configuration.md` et `debug/render_signal_server.env`). Principales variables:
- `FLASK_SECRET_KEY`
- `DASHBOARD_USER`, `DASHBOARD_PASSWORD` (anciennement `TRIGGER_PAGE_*`)
- `EMAIL_ADDRESS`, `EMAIL_PASSWORD`, `IMAP_SERVER`, `IMAP_PORT`, `IMAP_USE_SSL`
- `WEBHOOK_URL`, `WEBHOOK_SSL_VERIFY`
- `POLLING_*` (jours actifs, créneaux, timezone, vacances)
- `ENABLE_BACKGROUND_TASKS`
- `REDIS_URL` (optionnel)
- Variables R2 (`R2_FETCH_*`) pour l'offload Cloudflare
- Variables Magic Link (`MAGIC_LINK_TTL_SECONDS`, `MAGIC_LINK_TOKENS_FILE`)
- Variables Render (`RENDER_*`) pour le déploiement via Render

Voir `docs/configuration.md` pour la liste complète et à jour.

## Exécution

```bash
export FLASK_APP=app_render:app
flask run --host=0.0.0.0 --port=5000
```

En production: Gunicorn derrière Nginx (voir `docs/deploiement.md`). Le poller email doit être activé sur un seul process (lock fichier `/tmp/render_signal_server_email_poller.lock`).

## Tests

```bash
pytest test_app_render.py -v
```

Voir `docs/testing.md` pour l'état actuel de la suite de tests et de la couverture.

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
