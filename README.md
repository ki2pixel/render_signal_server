# render_signal_server

Application Flask modulaire pour le pilotage de webhooks et l'ingestion d'e-mails via Gmail Push. Ce dépôt a été refactoré pour passer d'un fichier monolithique (`app_render.py`) à une architecture claire et testable.

## Documentation

- Documentation principale : `docs/README.md`
- Architecture & services : `docs/core/architecture.md`
- Configuration & stockage : `docs/core/configuration-reference.md`
- Ingestion : `docs/ingestion/gmail-push.md`, `docs/ingestion/legacy-imap.md`, `docs/ingestion/link-extraction.md`
- Traitement : `docs/processing/routing-engine.md`, `docs/processing/pattern-matching.md`, `docs/processing/deduplication-engine.md`, `docs/processing/webhooks-outbound.md`, `docs/processing/file-offload.md`
- Accès & UI : `docs/access/authentication.md`, `docs/access/dashboard-ui.md`, `docs/core/magic-link-auth.md`
- Opérations : `docs/ops/deployment.md`, `docs/ops/monitoring.md`, `docs/ops/runtime-flags.md`, `docs/ops/troubleshooting.md`, `docs/ops/backfill-recadrage.md`
- Tests : `tests/README.md` et `pytest.ini`

## Déploiement Render (Docker + GHCR)

- L’application est construite via le `Dockerfile` racine, qui embarque Gunicorn et la configuration des threads/fils de poller (`GUNICORN_*`).
- Le workflow GitHub Actions `.github/workflows/render-image.yml` :
  1. Construit l’image depuis la racine du dépôt.
  2. La pousse sur GitHub Container Registry (`ghcr.io/<owner>/<repo>:latest` + `:<sha>`).
  3. Déclenche Render par ordre de priorité : Deploy Hook (`RENDER_DEPLOY_HOOK_URL`) → API Render (`RENDER_API_KEY`, `RENDER_SERVICE_ID`, `RENDER_DEPLOY_CLEAR_CACHE`) → fallback manuel.
- Les secrets GHCR/Render doivent être configurés côté GitHub Actions. Render récupère ensuite l’image et injecte les variables historiques (`ENABLE_BACKGROUND_TASKS`, `WEBHOOK_URL`, etc.).
- URL actuelle : `https://render-signal-server-latest.onrender.com` (cf. `memory-bank/activeContext.md` pour l’instance vivante).
- Pour les environnements on-premise, les instructions “Gunicorn + Reverse Proxy” restent valables (cf. `docs/ops/deployment.md`).

## Surveillance et Logs

### Logs Importants
- **Démarrage** : Vérifiez `CFG WEBHOOK: Custom webhook URL configured` pour confirmer la configuration des webhooks.
- **Ingestion Gmail** : Les logs `INGRESS: gmail payload received (email_id=..., sender=..., subject=...)` confirment la réception des e-mails via Apps Script.
- **Arrêt** : `PROCESS: SIGTERM received` indique un arrêt propre du service.
- **Services** : les lignes `SVC: ...Service initialized` confirment l'initialisation des singletons au démarrage.

### Surveillance Recommandée
- Configurez une alerte sur l'absence de logs `INGRESS: gmail payload received` pendant plus de 15 minutes.
- Surveillez les échecs d'envoi de webhooks et les erreurs de traitement Gmail Apps Script.
- Consultez les logs pour les entrées `WARNING` et `ERROR` pour détecter les problèmes potentiels.

Consultez [la documentation de déploiement](docs/ops/deployment.md) et le [guide de dépannage](docs/ops/troubleshooting.md) pour plus de détails.

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
- **Intégration** : `IngressService._maybe_enrich_delivery_links_with_r2` (Gmail Push) et `orchestrator._handle_r2_enrichment` (IMAP) enrichissent `delivery_links` si `R2_FETCH_ENABLED=true`
- **Économies** : ~$5/mois pour 50 GB transférés, auto-nettoyage 24h via `cleanup.js`

### 🐳 Déploiement Docker GHCR
- **Pipeline** : Workflow GitHub Actions `.github/workflows/render-image.yml` (build/push GHCR, déclenchement Render)
- **Image** : `Dockerfile` racine avec Gunicorn, variables `GUNICORN_*`, logs stdout/stderr
- **Déploiement** : URL `https://render-signal-server-latest.onrender.com` via Deploy Hook ou API Render
- **Avantages** : Temps de déploiement réduit, image pré-buildée, logs centralisés

### 🎨 Frontend Moderne & Sécurisé (2026-01-18)
- **Architecture modulaire ES6** : Refactorisation complète de `dashboard.js` (1488 → 237 lignes) en modules spécialisés
- **Services frontend** : `ApiService.js` (client API), `WebhookService.js` (config+logs), `LogService.js` (timer intelligent), `RoutingRulesService.js` (règles), `TabManager.js` (onglets accessibles), `MessageHelper.js` (messages et toasts)
- **Sécurité renforcée** : construction DOM sans `innerHTML`, gestion centralisée des 401/403, validation des URL webhook
- **Performance** : bascule d'onglets instantanée (panneaux déjà présents), polling des logs coupé quand l'onglet est masqué, accessibilité WCAG AA
- **Tests** : cinq suites Vitest (`static/__tests__/`) pour `ApiService`, `WebhookService`, `DOMHelper`, `debounce` et le bandeau de statut
- **Audit complet** : Audit frontend unifié ✅ toutes phases terminées (sécurité, architecture, UX/accessibilité)

### 🛡️ Résilience Infrastructure (Lot 2/3 - 2026-01-14)
- **Verrou distribué Redis** : prévention du multi-polling IMAP legacy avec la clé `render_signal:poller_lock` (TTL 5min) + fallback fcntl ; Gmail Push utilise le verrou in-flight par email de `DeduplicationService`
- **Fallback R2 garanti** : Conservation URLs sources, try/except large, flux continu même si Worker R2 échoue
- **Watchdog IMAP** : Timeout 30s anti-zombie sur connexions `imaplib.IMAP4_SSL/IMAP4`
- **Anti-OOM** : Troncature HTML à 1MB avant parsing pour prévenir les OOM kills sur conteneurs 512MB
- **Tests résilience** : `test_lock_redis.py`, `test_r2_resilience.py` avec validation complète des scénarios de défaillance

### Services Principaux
- **`ConfigService`** – Gestion centralisée de la configuration
- **`AuthService`** – Authentification et autorisation
- **`IngressService`** – Ingestion Gmail Push (validation, déduplication, R2, envoi webhook)
- **`RuntimeFlagsService`** – Gestion dynamique des fonctionnalités (Singleton)
- **`WebhookConfigService`** – Configuration et validation des webhooks (Singleton)
- **`RoutingRulesService`** – Règles de routage dynamiques (cache TTL, Redis-first)
- **`DeduplicationService`** – Prévention des doublons et verrou in-flight (Redis + fallback)
- **`MagicLinkService`** – Magic links signés en alternative au mot de passe (Singleton)
- **`R2TransferService`** – Offload Cloudflare R2 (Singleton)
- **`RateLimitService`**, **`RuntimeMetricsService`**, **`WebhookLoggerService`** – Limitation de débit, métriques et journalisation webhook

## Architecture

```
render_signal_server-main/
├── app_logging/
│   └── webhook_logger.py           # Logs webhook (Redis + fallback JSON)
├── auth/
│   ├── user.py                     # Flask-Login (User, LoginManager)
│   └── helpers.py                  # API key (X-API-Key), décorateur api_key_required
├── config/
│   ├── settings.py                 # Variables ENV, constantes, chemins
│   ├── app_config_store.py         # Config store Redis + fallback fichier
│   ├── runtime_flags.py            # Flags runtime (Gmail Push, envoi webhook)
│   ├── webhook_config.py           # Configuration webhooks
│   └── webhook_time_window.py      # Fenêtre horaire globale
├── deduplication/
│   ├── redis_client.py             # Verrou in-flight + dédoublonnage Redis
│   └── subject_group.py            # Groupes de sujets
├── email_processing/
│   ├── imap_client.py              # Connexion IMAP (legacy)
│   ├── pattern_matching.py         # Patterns Média Solution / DESABO
│   ├── link_extraction.py          # Extraction Dropbox / FromSmash / SwissTransfer
│   ├── delivery_time_resolver.py   # Report des livraisons hors fenêtre
│   ├── payloads.py                 # Construction des payloads webhook
│   └── orchestrator.py             # Orchestration IMAP + envoi webhook
├── preferences/
│   └── processing_prefs.py         # Préférences de traitement (Redis + JSON)
├── routes/
│   ├── api_ingress.py              # POST /api/ingress/gmail (Gmail Push)
│   ├── api_webhooks.py             # Configuration des webhooks
│   ├── api_processing.py           # Préférences de traitement
│   ├── api_routing_rules.py        # Règles de routage dynamiques
│   ├── api_test.py                 # /api/test/* (X-API-Key)
│   ├── api_admin.py                # Administration (déploiement Render, config store)
│   ├── api_config.py               # Fenêtres horaires et flags runtime
│   ├── api_utility.py              # Ping, triggers locaux, statut
│   ├── api_auth.py                 # Authentification Magic Link
│   ├── api_logs.py                 # Journal des webhooks
│   ├── dashboard.py                # UI /, /login, /logout
│   └── health.py                   # GET /health
├── services/                       # Services métier (voir services/README.md)
│   ├── ingress_service.py          # Ingestion Gmail Push
│   ├── routing_rules_service.py    # Routage dynamique
│   ├── webhook_config_service.py   # Configuration webhooks
│   ├── deduplication_service.py    # Déduplication
│   ├── magic_link_service.py       # Magic links
│   ├── r2_transfer_service.py      # Offload Cloudflare R2
│   ├── runtime_flags_service.py    # Flags runtime
│   ├── rate_limit_service.py       # Limitation de débit
│   ├── runtime_metrics_service.py  # Métriques runtime
│   ├── webhook_logger_service.py   # Journalisation webhook
│   ├── config_service.py           # Configuration centralisée
│   └── auth_service.py             # Authentification et autorisation
├── scripts/
│   ├── backfill_recadrage_emails.py  # Backfill 30 jours de email_proxy.php
│   ├── check_config_store.py         # Audit du config store
│   └── google_script.js              # Apps Script Gmail Push
├── static/                         # Modules ES6 et CSS du dashboard (Vite)
├── utils/
│   ├── time_helpers.py             # parse_time_hhmm(), is_within_time_window_local()
│   ├── text_helpers.py             # normalize_*, strip_leading_reply_prefixes()
│   ├── validators.py               # env_bool(), validation des URLs webhook
│   ├── storage_backend.py          # Fallback de stockage Redis/fichier
│   ├── rate_limit.py               # Limitation de débit
│   └── limiter.py                  # Limiteur partagé
├── tests/                          # Suite pytest (voir tests/README.md)
├── app_render.py                   # Point d'entrée Flask, enregistrement des blueprints
├── dashboard.html                  # UI principale (onglets)
├── login.html                      # Page de login
└── docs/                           # Documentation technique (voir docs/README.md)
```

Références détaillées : `docs/README.md`, `docs/core/architecture.md`, `docs/core/configuration-reference.md`, `docs/ingestion/legacy-imap.md`, `tests/README.md`.

## Refactoring (historique)

Le refactoring vers l'architecture orientée services (services dédiés, blueprints, réduction d'`app_render.py`) est retracé dans :

- `memory-bank/decisionLog.md` – décisions d'architecture et arbitrages
- `memory-bank/archive/` – entrées historiques de progression
- `docs/core/architecture.md` – état courant de l'architecture

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

Créer un fichier d’environnement pour le dev (voir `docs/core/configuration-reference.md` et `debug/render_signal_server.env`). Principales variables:
- `FLASK_SECRET_KEY`
- `TRIGGER_PAGE_USER`, `TRIGGER_PAGE_PASSWORD` (identifiants du dashboard)
- `EMAIL_ADDRESS`, `EMAIL_PASSWORD`, `IMAP_SERVER`, `IMAP_PORT`, `IMAP_USE_SSL` (legacy IMAP, conservés pour les tests)
- `WEBHOOK_URL`, `WEBHOOK_SSL_VERIFY`
- `POLLING_*` (legacy IMAP, conservés pour les tests)
- `ENABLE_BACKGROUND_TASKS` (legacy IMAP)
- `REDIS_URL` (optionnel)
- Variables R2 (`R2_FETCH_*`) pour l'offload Cloudflare
- Variables Magic Link (`MAGIC_LINK_TTL_SECONDS`, `MAGIC_LINK_TOKENS_FILE`)
- Variables Render (`RENDER_*`) pour le déploiement via Render

Voir `docs/core/configuration-reference.md` pour la liste complète et à jour.

## Exécution

```bash
export FLASK_APP=app_render:app
flask run --host=0.0.0.0 --port=5000
```

En production: Gunicorn derrière Nginx (voir `docs/ops/deployment.md`). Le poller IMAP legacy doit être activé sur un seul process (lock fichier `/tmp/render_signal_server_email_poller.lock` via `ENABLE_BACKGROUND_TASKS=true`). En Gmail Push, l'idempotence est portée par le verrou in-flight par email de `DeduplicationService`.

## Tests

```bash
pytest                                  # suite complète
pytest test_app_render.py -v            # tests historiques de l'application
npm test                                # suites Vitest du frontend
```

**État de référence** : se référer au dernier run CI ; la suite recense plus de 400 fonctions de test (couverture générée par `pytest-cov`).

- **Tests unitaires** : Services, helpers, validation
- **Tests d'intégration** : Routes API, services ensemble
- **Tests résilience** : Redis lock, fallback R2, anti-OOM
- **Tests frontend** : Vitest + jsdom (`ApiService`, `WebhookService`, `DOMHelper`, `debounce`, statut global)

Voir `tests/README.md` et `.coveragerc` pour la stratégie de tests et le calcul de couverture.

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
- La tâche en cours et les prochaines étapes sont suivies dans `memory-bank/activeContext.md`.
