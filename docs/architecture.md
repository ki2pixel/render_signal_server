# Architecture

Cette application fournit une télécommande web sécurisée (Flask + Flask-Login) et un service de polling d'e-mails IMAP exécuté en tâche de fond.

## Structure modulaire (refactor 2025-10)

### Extractions de modules récentes (2025-10-12)

#### Pipeline de Traitement des Emails
- **`email_processing/`** - Extraction complète de la logique de traitement
  - `imap_client.py` - Gestion des connexions IMAP avec reconnexion automatique
  - `pattern_matching.py` - Détection des motifs spécifiques (Média Solution, DESABO)
  - `webhook_sender.py` - Envoi des webhooks avec gestion des timeouts et des tentatives
  - `orchestrator.py` - Flux de traitement principal avec injection de dépendances
  - `link_extraction.py` - Extraction des URLs de livraison (Dropbox, FromSmash, SwissTransfer)
  - `payloads.py` - Construction des charges utiles pour les webhooks

#### Modules de Support
- **`app_logging/`** - Journalisation centralisée avec fallback Redis
  - `webhook_logger.py` - Enregistrement et consultation des logs des webhooks
  
- **`preferences/`** - Gestion des préférences de traitement
  - `processing_prefs.py` - Validation et persistance des préférences utilisateur
  
- **`deduplication/`** - Prévention des doublons
  - `redis_client.py` - Implémentation basée sur Redis avec fallback en mémoire
  
- **`background/`** - Tâches en arrière-plan
  - `polling_thread.py` - Gestion du thread de polling avec injection de dépendances
  - `lock.py` - Verrouillage singleton pour empêcher l'exécution simultanée de tâches critiques (ex: polling IMAP) dans un environnement multi-processus

#### Utilitaires
- **`utils/`** - Fonctions utilitaires réutilisables
  - `time_helpers.py` - Gestion des fuseaux horaires et des plages horaires
  - `text_helpers.py` - Manipulation de texte et normalisation
  - `validators.py` - Validation des entrées et normalisation

#### Configuration
- **`config/`** - Gestion de la configuration
  - `settings.py` - Variables d'environnement et constantes
  - `polling_config.py` - Configuration du polling (fuseau horaire, vacances, etc.)
  - `webhook_time_window.py` - Gestion des fenêtres horaires des webhooks
  - `runtime_flags.py` - Helpers de persistance des flags runtime (`load_runtime_flags()/save_runtime_flags()`)
  - `webhook_config.py` - Helpers de persistance de la configuration webhooks (`load_webhook_config()/save_webhook_config()`)

#### Routes API
  - `api_webhooks.py` - Gestion de la configuration des webhooks
  - `api_polling.py` - Contrôle du polling d'emails
  - `api_processing.py` - Gestion des préférences de traitement
  - `api_test.py` - Endpoints de test (CORS)
  - `api_logs.py` - Consultation des logs
  - `api_admin.py` - Endpoints administratifs (présence Make, redémarrage, déclenchement manuel `/api/check_emails_and_download`, endpoint de vérification manuelle des e-mails)
  - `api_utility.py` - Utilitaires (ping, trigger, statut local UI)
  - `api_config.py` - Endpoints protégés de configuration (fenêtre horaire webhooks, runtime flags, configuration polling)
  - `dashboard.py` - Routes de l'interface utilisateur
  - `health.py` - Endpoint de santé
- `auth/`
  - `user.py` : gestion Flask-Login (classe `User`, `init_login_manager`, helpers de credentials)
  - `helpers.py` : auth API par clé (`X-API-Key`) pour les endpoints `/api/test/*`
- `config/`
  - `settings.py` : constantes, variables d'environnement, flags et chemins
  - `polling_config.py` : timezone, jours/heures actifs, vacances, validations
  - `webhook_time_window.py` : fenêtre horaire des webhooks (override UI + persistance JSON)
- `routes/`
  - `__init__.py` : export des blueprints
  - `api_logs.py` : gestion des logs de webhooks (`GET /api/webhook_logs`)
  - `api_polling.py` : contrôle du polling d'emails
  - `api_processing.py` : gestion des préférences de traitement, avec support des URLs legacy
  - `api_test.py` : endpoints de test et débogage
  - `api_webhooks.py` : gestion des webhooks entrants
  - `dashboard.py` : routes UI du tableau de bord
  - `health.py` : endpoint de santé
- `utils/`
  - `time_helpers.py`, `text_helpers.py`, `validators.py` : fonctions pures réutilisables (parsing heures, normalisation texte, env bool, etc.)
- `email_processing/`
  - `imap_client.py` : création de la connexion IMAP
  - `pattern_matching.py` : détection des patterns e-mail (Média Solution, DESABO), constante `URL_PROVIDERS_PATTERN`
  - `orchestrator.py` : point d'entrée unique pour le cycle de polling et helpers d'orchestration
    - `check_new_emails_and_trigger_webhook()`: Point d'entrée principal qui délègue à l'implémentation legacy
    - `handle_presence_route()`: Gère la détection et le routage des emails de présence "samedi"
      - Paramètres: subject, full_email_content, email_id, sender_raw, tz_for_polling, etc.
      - Retourne: bool (True si routé avec succès)
    - `handle_desabo_route()`: Traite les demandes de désabonnement (DESABO)
      - Paramètres: subject, full_email_content, html_email_content, email_id, etc.
      - Gestion des fenêtres horaires et construction du payload spécifique
    - `handle_media_solution_route()`: Gère les emails de type Média Solution
      - Extraction des liens de livraison et envoi des webhooks
    - `compute_desabo_time_window()`: Calcule la fenêtre temporelle pour les webhooks DESABO
      - Gère les cas "early_ok" et les contraintes horaires
    - `send_custom_webhook_flow()`: Flux complet d'envoi de webhook avec gestion des erreurs
      - Gestion des retries, timeouts, et journalisation
      - Validation des liens de livraison
  - `link_extraction.py` : extraction des URLs fournisseurs (Dropbox, FromSmash, SwissTransfer)
  - `payloads.py` : constructeurs de payloads (webhook custom, DESABO Make)
  - `webhook_sender.py` : envoi Make.com avec injection `logger`/`log_hook`

Objectifs: séparation des responsabilités, testabilité améliorée, réduction du couplage dans `app_render.py`.

## Composants

- Backend Flask (`app_render.py`)
  - Authentification par session via `Flask-Login` (`/login`, `/logout`).
  - API internes:
    - `GET /api/ping` – santé de l'application.
    - `GET /api/check_trigger` – lecture/consommation d'un signal local (fichier `signal_data_app_render/local_workflow_trigger_signal.json`).
    - `POST /api/check_emails_and_download` – lance en arrière-plan une vérification IMAP (protégé: login requis).
  - Thread de fond: `background_email_poller()` démarre au boot via `start_background_tasks()`.

- Frontend (`dashboard.html` + `static/dashboard.js`)
  - `dashboard.js` orchestre l'UI du Dashboard Webhooks: fenêtre horaire globale, configuration du polling (jours/heures, expéditeurs, déduplication, vacances), contrôle du polling IMAP, configuration des URLs webhooks et logs.
  - Remplace l'ancien trio `static/remote/{main.js,api.js,ui.js}`.

- Intégrations externes
  - IMAP (inbox.lt): lecture des e-mails pour extraire des URLs de livraison (Dropbox, FromSmash, SwissTransfer) et métadonnées.
  - Webhook HTTP: envoi des événements vers `WEBHOOK_URL` (personnalisable) et/ou Make.com (`RECADRAGE_MAKE_WEBHOOK_URL`, `AUTOREPONDEUR_MAKE_WEBHOOK_URL`, présence `PRESENCE_*_MAKE_WEBHOOK_URL`).
  - Redis (optionnel): déduplication des e-mails traités via un Set `processed_email_ids_set_v1` et dédup par groupe de sujet.
  - Résolution de liens directs supprimée: Les URLs de partage (Dropbox, FromSmash, SwissTransfer) sont extraites telles quelles (landing pages) et l'UI propose une ouverture manuelle pour éviter la complexité de maintenance liée aux changements des sites.

## Flux principaux

1) Connexion utilisateur
- L'utilisateur se connecte sur `/login` (identifiants définis par variables d'environnement).
- Une fois authentifié, il accède à `/` (Dashboard Webhooks).

2) Dashboard Webhooks
- La page permet de configurer et superviser:
  - Fenêtre horaire globale des webhooks
  - Polling IMAP (jours/heures, liste d'expéditeurs, déduplication sujet, vacances)
  - Activation/désactivation du polling
  - URLs Make.com et webhook custom
  - Historique des webhooks (logs)

3) Polling IMAP et webhook
- Le thread `background_email_poller()` s'exécute pendant la plage horaire active définie.
- Orchestration (entrée unique): `email_processing/orchestrator.check_new_emails_and_trigger_webhook()`
  - Se connecte via IMAP.
  - Filtre les e-mails selon une liste d'expéditeurs autorisés (`SENDER_LIST_FOR_POLLING`).
  - Déduplication via Redis (si configuré) sinon fallback mémoire/process simplifié, et déduplication par groupe de sujet.
  - Routage métier via helpers orchestrateur:
    - Présence « samedi »: `handle_presence_route()` -> Make présence (exclusif)
    - Désabonnement (DESABO): `handle_desabo_route()` -> Make Autorepondeur (start_payload: « début » si early; sinon « maintenant »)
    - Média Solution: `handle_media_solution_route()` -> Make Recadrage
  - Extraction des liens: `link_extraction.extract_provider_links_from_text()` (landing pages uniquement)
  - Payload webhook custom: `payloads.build_custom_webhook_payload()`
  - Envoi Make.com centralisé: `webhook_sender.send_makecom_webhook()`

## Structure des fichiers clefs

- `app_render.py` – application Flask, enregistrement des blueprints (`routes/`), configuration et démarrage; la logique métier est déléguée aux modules. La taille a été réduite (≈727 lignes) et vise ≈500 lignes.
- `routes/api_config.py` – endpoints de configuration protégés: fenêtre horaire, runtime flags, config polling.
- `routes/api_admin.py` – endpoints administratifs: webhook présence Make, redémarrage serveur.
- `routes/api_utility.py` – utilitaires (ping, trigger, statut local UI).
- `config/runtime_flags.py` – I/O centralisée des flags runtime.
- `config/webhook_config.py` – I/O centralisée pour la configuration webhooks.
- `dashboard.html` – interface Dashboard Webhooks.
- `static/dashboard.js` – logique UI centralisée du dashboard.
- `requirements.txt` – dépendances Python.
 - `deployment/` – ancien/alternative: application PHP reproduisant une partie du scénario Make.com (documentation incluse). Ce dossier est indépendant du serveur Flask. Note: par compatibilité avec des systèmes existants, toutes les URLs détectées (Dropbox, FromSmash, SwissTransfer) sont enregistrées dans la table `logs_dropbox` via la colonne `url_dropbox`.

## Décisions techniques

- Flask-Login pour simplicité des sessions et décorateurs `@login_required`.
- Thread Python pour le polling IMAP: évite un scheduler externe, suffisant pour des volumétries modestes.
- Redis optionnel: robuste pour éviter les retraitements multi-processus/instances.
- Variables d'environnement pour toutes les informations sensibles ou spécifiques à l'environnement.

## Flags Runtime Persistés

Pour faciliter le débogage en production sans redémarrage, un système de flags runtime permet l'activation/désactivation dynamique de fonctionnalités critiques.
- Fichier de persistance: `debug/runtime_flags.json` (via `config/runtime_flags.py`).
- Flags disponibles: `DISABLE_EMAIL_ID_DEDUP` (bypass déduplication par email ID), `ALLOW_CUSTOM_WEBHOOK_WITHOUT_LINKS` (skip webhook custom si aucun lien détecté).
- Chargés au démarrage et surchargeables via variables d'environnement; modifiables via API/UI.
- Persistés pour survivre aux restarts.

## Parsing Email Multi-Part

L'extraction d'informations des emails traite désormais les parties text/plain et text/html séparément pour une couverture complète.

## Sécurité opérationnelle des tâches de fond

- Singleton inter-processus pour le poller IMAP via `fcntl` + fichier de verrou.
  - Activation explicite par `ENABLE_BACKGROUND_TASKS=true` (voir `docs/configuration.md`).
  - Chemin du lock configuré via `BG_POLLER_LOCK_FILE` (défaut: `/tmp/render_signal_server_email_poller.lock`).
  - Recommandation: n'activer le poller que sur un seul worker/process (ou service dédié) dans les déploiements Gunicorn multi-workers.

## Fenêtre horaire des webhooks (override UI)

- Indépendante de la planification IMAP. Configure une contrainte horaire pour l'envoi des webhooks (incluant Make présence/désabonnement).
- Configurable depuis l'UI (`dashboard.html`), persistée dans `debug/webhook_time_window.json` et rechargée dynamiquement via `config/webhook_time_window.py`.
- Les champs `webhooks_time_start` / `webhooks_time_end` peuvent être ajoutés aux payloads (voir `docs/webhooks.md`).

## Limitations connues

- Le polling IMAP en thread unique ne convient pas à de très fortes volumétries.
- Des valeurs de référence (REF_*) existent dans le code pour faciliter le dev: à surcharger impérativement en production via env vars.

## Diagramme de séquence (texte/ASCII)

```
Participant           Action
-----------           ---------------------------------------------------------
Utilisateur           Ouvre /login et s'authentifie
UI (dashboard)        Reçoit session -> affiche Dashboard Webhooks '/'

Flask (thread BG)     background_email_poller() actif dans la fenêtre horaire
Flask                 check_new_emails_and_trigger_webhook()
IMAP                  Connexion, recherche, lecture des messages
Flask                 Filtre expéditeurs + dédup (Redis si dispo) + dédup groupe sujet
Flask                 check_media_solution_pattern() -> URLs (Dropbox/FromSmash/SwissTransfer) + delivery_time
Flask                 POST payload JSON -> WEBHOOK_URL / Make.com
Webhook Receiver      200 OK (ou 4xx/5xx en cas d'erreur)
Flask                 Log succès/échec et continue la boucle
Flask                 Lance check_new_emails_and_trigger_webhook() en thread
UI                    Affiche message "tâche lancée" (202)
```
