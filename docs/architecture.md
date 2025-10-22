# Architecture

Cette application fournit une télécommande web sécurisée (Flask + Flask-Login) et un service de polling d'e-mails IMAP exécuté en tâche de fond.

## Structure modulaire (refactor 2025-10)

### Dernières évolutions (2025-10-16)

#### Migration vers le Stockage Externe
- **Remplacement de MySQL** : Passage à une solution de stockage externe via API PHP avec fallback sur fichiers JSON locaux
- **Fichiers de configuration** :
  - `debug/webhook_config.json` : Configuration des webhooks et fenêtres horaires
  - `debug/processing_prefs.json` : Préférences de traitement
  - `debug/webhook_time_window.json` : Configuration de la fenêtre horaire des webhooks
- **Avantages** :
  - Simplification de l'infrastructure (plus besoin de base de données dédiée)
  - Meilleure portabilité entre environnements
  - Facilité de sauvegarde et de restauration

#### Séparation des Fenêtres Horaire
- **Deux fenêtres indépendantes** :
  - **Fenêtre des e-mails** : Contrôle quand les e-mails sont récupérés du serveur IMAP
  - **Fenêtre des webhooks** : Contrôle quand les notifications sont envoyées aux webhooks
- **Gestion via API** :
  - Endpoints dédiés pour la configuration (`/api/webhooks/time-window`)
  - Persistance dans `webhook_time_window.json`
  - Rechargement dynamique sans redémarrage

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
  - `app_config_store.py` - Gestion unifiée de la configuration avec fallback sur stockage externe ou fichiers locaux

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
    - `check_new_emails_and_trigger_webhook()` : Flux natif complet (plus de délégation legacy) qui gère
      - la connexion IMAP, la déduplication, l'extraction des contenus plain/HTML
      - l'inférence de `detector` (`recadrage` via `check_media_solution_pattern`, `desabonnement_journee_tarifs` via `check_desabo_conditions`)
      - le contrôle de la fenêtre horaire globale avec exceptions par détecteur :
        - `desabonnement_journee_tarifs` contourne la fenêtre et force l'envoi
        - `recadrage` est marqué lu/traité hors fenêtre pour éviter les retraits
      - le déclenchement du flux webhook personnalisé `send_custom_webhook_flow()` (payloads unifiés + miroir médias)
    - `handle_presence_route()` : Gère la détection et le routage des emails de présence "samedi"
    - `compute_desabo_time_window()` : Calcule la fenêtre temporelle pour les webhooks DESABO (`early_ok`, start=`maintenant`)
    - `send_custom_webhook_flow()` : Flux complet d'envoi de webhook avec gestion des erreurs
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
  - **Fenêtre horaire des webhooks** : Configuration indépendante des horaires d'envoi
  - **Fenêtre horaire des e-mails** : Configuration des horaires de récupération IMAP
  - **Préférences de traitement** :
    - Mots-clés d'exclusion (globaux et par webhook)
    - Taille maximale des e-mails
    - Paramètres de nouvelle tentative
    - Miroir des médias vers le webhook personnalisé
  - **Statut du système** :
    - État du service de polling
    - Dernière exécution
    - Prochaine exécution planifiée
  - **Journaux** : Consultation des logs et des webhooks récents

3) Polling IMAP et webhook
- Le thread `background_email_poller()` s'exécute pendant la plage horaire active des e-mails.
- Orchestration (entrée unique): `email_processing/orchestrator.check_new_emails_and_trigger_webhook()`
  - **Connexion IMAP** : Établissement de la connexion avec reconnexion automatique en cas d'échec
  - **Filtrage** :
    - Filtrage par expéditeurs autorisés (`SENDER_LIST_FOR_POLLING`)
    - Vérification de la taille maximale des e-mails
    - Filtrage par mots-clés d'exclusion (globaux et spécifiques au webhook)
  - **Déduplication** :
    - Par ID d'e-mail (via Redis ou en mémoire)
    - Par groupe de sujet (regroupement des e-mails similaires)
  - **Traitement** :
    - Vérification de la fenêtre horaire des webhooks
    - Extraction des liens de médias (SwissTransfer, Dropbox, FromSmash)
    - Construction du payload selon le type d'e-mail détecté
  - **Notification** :
    - Envoi du webhook personnalisé (si configuré)
    - Miroir des médias vers le webhook personnalisé (si activé)
    - Journalisation complète des actions et des erreurs
  - **Gestion des erreurs** :
    - Nouvelles tentatives en cas d'échec
    - Délai entre les tentatives configurable
    - Journalisation détaillée des erreurs

## Gestion de la Configuration

### Chargement de la Configuration
1. **Stockage Externe** (prioritaire) :
   - Requête HTTP vers l'API de configuration externe
   - Authentification via `CONFIG_API_TOKEN`
   - Timeout et gestion des erreurs
2. **Fallback Local** :
   - Lecture des fichiers JSON locaux (`debug/*.json`)
   - Création avec valeurs par défaut si inexistants
   - Validation des données lues

### Mise à Jour de la Configuration
1. **Via l'API** :
   - Validation des données reçues
   - Sauvegarde vers le stockage externe
   - Mise à jour du fichier local en cas de succès
2. **Via l'Interface Utilisateur** :
   - Validation côté client et serveur
   - Appel à l'API de configuration
   - Mise à jour de l'interface en temps réel

### Synchronisation
- **Au Démarrage** : Chargement de la configuration depuis le stockage externe ou les fichiers locaux
- **Pendant l'Exécution** : Rechargement dynamique lors des modifications via l'API/UI
- **En Cas d'Erreur** : Utilisation de la dernière configuration valide avec notification de l'erreur

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
 - `deployment/` – application PHP reproduisant les scénarios Make.com, incluant :
   - Envoi d'emails via Gmail OAuth pour les flux `autorepondeur` et `recadrage`
   - Gestion des webhooks entrants avec détecteurs (`recadrage`, `desabonnement_journee_tarifs`)
   - Persistance des liens (Dropbox, FromSmash, SwissTransfer) dans la table `logs_dropbox`
   - Configuration via variables d'environnement (`GMAIL_CLIENT_*`, `GMAIL_REFRESH_TOKEN`, etc.)
   
   > **Note** : Cette couche PHP est autonome et s'exécute indépendamment du serveur Flask principal, offrant une redondance pour les fonctionnalités critiques.

## Décisions techniques

- **Authentification** : Flask-Login pour la simplicité des sessions et décorateurs `@login_required`
- **Polling IMAP** : Thread Python natif pour éviter la dépendance à un planificateur externe
- **Stockage** :
  - Migration de MySQL vers une solution externe avec fallback JSON local
  - Redis optionnel pour la déduplication en environnement multi-instances
  - Fichiers JSON pour la persistance locale des configurations
- **Sécurité** :
  - Variables d'environnement pour les informations sensibles
  - Validation stricte des entrées utilisateur
  - Journalisation détaillée des actions sensibles
- **Évolutivité** :
  - Architecture modulaire facilitant l'ajout de nouveaux fournisseurs de stockage
  - API RESTful pour une intégration avec d'autres services
  - Configuration dynamique sans redémarrage
- **Maintenabilité** :
  - Documentation complète et à jour
  - Tests automatisés pour les composants critiques
  - Journalisation structurée pour le débogage

## Gestion des Fonctionnalités

### Flags Runtime Persistés

Pour faciliter le débogage en production sans redémarrage, un système de flags runtime permet l'activation/désactivation dynamique de fonctionnalités critiques :
- **Stockage** : `debug/runtime_flags.json` (via `config/runtime_flags.py`)
- **Flags disponibles** :
  - `DISABLE_EMAIL_ID_DEDUP` : Désactive la déduplication par ID d'e-mail
  - `ALLOW_CUSTOM_WEBHOOK_WITHOUT_LINKS` : Autorise l'envoi de webhooks même sans liens détectés
  - `MIRROR_MEDIA_TO_CUSTOM` : Active l'envoi des liens de médias au webhook personnalisé
- **Gestion** :
  - Chargement au démarrage
  - Surcharge possible via variables d'environnement
  - Modification via API/UI
  - Persistance entre les redémarrages

### Préférences de Traitement

Configuration avancée du comportement du système :
- **Stockage** : `debug/processing_prefs.json`
- **Paramètres** :
  - Mots-clés d'exclusion (globaux et par webhook)
  - Taille maximale des e-mails
  - Paramètres de nouvelle tentative
  - Configuration du miroir des médias
- **Validation** : Vérification des valeurs avant application
- **API** : Endpoints pour la lecture et la mise à jour

### Fenêtres Horaire

Deux fenêtres horaires indépendantes :
1. **E-mails** : Contrôle quand les e-mails sont récupérés du serveur IMAP
   - Configuration via variables d'environnement
   - Priorité sur la configuration du polling

2. **Webhooks** : Contrôle quand les notifications sont envoyées
   - Configuration via l'interface ou l'API
   - Persistée dans `debug/webhook_time_window.json`
   - Rechargement dynamique sans redémarrage

## Parsing Email Multi-Part

L'extraction d'informations des emails traite désormais les parties text/plain et text/html séparément pour une couverture complète.

## Sécurité opérationnelle des tâches de fond

- Singleton inter-processus pour le poller IMAP via `fcntl` + fichier de verrou.
  - Activation explicite par `ENABLE_BACKGROUND_TASKS=true` (voir `docs/configuration.md`).
  - Chemin du lock configuré via `BG_POLLER_LOCK_FILE` (défaut: `/tmp/render_signal_server_email_poller.lock`).
  - Recommandation: n'activer le poller que sur un seul worker/process (ou service dédié) dans les déploiements Gunicorn multi-workers.

## Fenêtres Horaire

### Fenêtre Horaire des E-mails
- **Objectif** : Contrôler quand les e-mails sont récupérés du serveur IMAP
- **Configuration** :
  - Variables d'environnement : `POLLING_ACTIVE_START_HOUR`, `POLLING_ACTIVE_END_HOUR`, `POLLING_ACTIVE_DAYS`
  - Priorité sur la configuration du polling
- **Comportement** :
  - Aucun e-mail n'est récupéré en dehors de la fenêtre horaire
  - La planification est gérée par le thread de polling

### Fenêtre Horaire des Webhooks
- **Objectif** : Contrôler quand les notifications sont envoyées aux webhooks
- **Configuration** :
  - Interface utilisateur (`dashboard.html`) ou API (`/api/webhooks/time-window`)
  - Persistée dans `debug/webhook_time_window.json`
  - Rechargement dynamique sans redémarrage
- **Comportement** :
  - Les webhooks sont mis en file d'attente en dehors de la fenêtre horaire
  - Exécution différée jusqu'à la prochaine fenêtre active
  - Désactivable pour un envoi immédiat

### Intégration dans les Payloads
Les champs suivants sont ajoutés aux payloads des webhooks :
- `webhooks_time_start` : Heure de début de la fenêtre horaire (format `HHhMM`)
- `webhooks_time_end` : Heure de fin de la fenêtre horaire (format `HHhMM`)
- `webhook_window_enabled` : Indique si la fenêtre horaire est activée

Ces champs permettent aux systèmes distants d'adapter leur comportement en fonction des contraintes horaires configurées.

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
