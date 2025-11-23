# Suivi de Progression

## Terminé

-   [2025-11-24 00:43] **Application stricte de l'Absence Globale + Tests**
    - Ajout d'une garde de cycle dans `email_processing/orchestrator.py` pour stopper le polling les jours d'absence.
    - Normalisation robuste des jours (`strip().lower()`) dans `_is_webhook_sending_enabled()`.
    - Ajout de tests: normalisation casse/espaces et test d'intégration de la garde de cycle (`tests/test_absence_pause.py`).
    - Résultat: 14/14 tests absence passent; aucun envoi attendu les jours configurés.

-   [2025-11-21 17:49] **Mise à jour de la documentation API suite au workflow /docs-updater**
  - Mise à jour de `docs/api.md` pour inclure les nouveaux champs `absence_pause_enabled` et `absence_pause_days` dans les exemples GET et POST /api/webhooks/config.
  - Ajout des règles de validation : `absence_pause_days` doit être une liste de jours valides (monday, tuesday, wednesday, thursday, friday, saturday, sunday), et au moins un jour si `absence_pause_enabled` est `true`.
  - Cohérence parfaite entre code source et documentation assurée.

-   [2025-11-21 17:41] **Refactoring terminologique : "Presence Pause" → "Absence Globale"**
  - **Refactoring complet** : Changement de terminologie "presence_pause" → "absence_pause" pour une meilleure cohérence logique.
  - **Fonctionnalité Absence Globale** : Permet de bloquer complètement l'envoi de webhooks sur des jours spécifiques de la semaine.
  - **Fichiers impactés** : `services/webhook_config_service.py`, `routes/api_webhooks.py`, `email_processing/orchestrator.py`, `static/dashboard.js`, `dashboard.html`, `docs/webhooks.md`, `tests/test_absence_pause.py`
  - **Tests** : Nouveau fichier `test_absence_pause.py` avec 12 tests couvrant API, service et orchestrateur (12/12 OK)
  - **Résultat** : Terminologie cohérente dans tout le codebase, fonctionnalité préservée, tests validés, commit poussé vers main

-   [2025-11-18 01:35] **Correction des 11 tests en échec (adaptation architecture services)**
  - **Tests dashboard** (2) : Patch `_auth_service.create_user_from_credentials` au lieu de fonction déplacée
  - **Test api_config** (1) : Patch `config.settings.*` au lieu de `routes.api_config.*` 
  - **Tests api_admin presence** (4) : Mock `_config_service.get_presence_config()` au lieu de monkeypatch constantes
  - **Test api_admin check_emails** (1) : Mock `_config_service.is_email_config_valid()` pour validation
  - **Test webhook_logging_integration** : Patch `email_processing.webhook_sender.requests.post` au lieu de `app_render.requests.post`
  - **Isolation tests webhook_logs** : Amélioration fixture `temp_logs_file` avec initialisation liste vide
  - Résultat : **345/348 tests passants (99.1%)**, +8 tests corrigés, 3 échecs isolation (passent individuellement)
  - Couverture : 68.13% (+0.45%)
  - Tests adaptés à l'architecture orientée services (Phases 1→5)

-   [2025-11-18 01:29] **Refactoring maintenabilité : webhook_logger, processing_prefs, routes**
  - Suppression du module legacy `logging/webhook_logger.py` (dupliqué avec `app_logging/webhook_logger.py`)
  - Simplification de `routes/api_logs.py` : utilisation directe de `fetch_webhook_logs()` du helper centralisé
  - Refactorisation de `routes/api_processing.py` : délégation de la validation à `preferences.processing_prefs.validate_processing_prefs()`
  - Conservation des alias UI (`exclude_keywords_recadrage`, `exclude_keywords_autorepondeur`) avec normalisation avant validation
  - Nettoyage des imports inutilisés (json dans api_processing.py)
  - Tests : 337/348 passants (11 échecs préexistants non liés au refactoring)
  - Tests spécifiques webhook_logs validés individuellement (état partagé dans suite complète)
  - Code plus DRY, maintenable et conforme aux Coding Standards

-   [2025-11-18 01:18] **Nettoyage et ajustements post-refactoring de app_render.py**
  - Nettoyage d'imports inutilisés (subprocess, requests, urljoin, fcntl, re, LoginManager, UserMixin, login_user, logout_user, current_user)
  - Gestion explicite du flag DISABLE_BACKGROUND_TASKS avec priorité override pour tous les threads de fond
  - Amélioration de _log_webhook_config_startup() pour utiliser WebhookConfigService.get_all_config() quand disponible
  - Ajout de TODO pour déprécation future de auth_user.init_login_manager()
  - Tests validés (8/8 passent), import Python valide, pas de régression
  - Code plus maintenable et fiable post-refactoring orienté services
  - Types et logs sécurisés (imap_client), TypedDict + dédup (link_extraction)
  - Bug has_dropbox_request corrigé + constantes + types (pattern_matching)
  - TypedDict payloads + factorisation Dropbox (payloads)
  - Paramètre attempts + types (webhook_sender)
  - Orchestrator: helpers extraits, constants, TypedDict ParsedEmail, docstrings
  - Tests adaptés + exécution complète: 282 OK, 8 échecs préexistants

-   [2025-11-06 00:45] **Durcissement Render (SIGTERM, Make watcher, redémarrage planifié)**
    - Ajout d'un handler `SIGTERM` dans `app_render.py` pour tracer les arrêts plateforme.
    - Protection du watcher Make pour ne démarrer que si `MAKECOM_API_KEY` est présent.
    - Recommandation et documentation d'une configuration `GUNICORN_CMD_ARGS` avec `--max-requests/--max-requests-jitter` adaptée au trafic (≈ redémarrage quotidien).
    - Push GitHub effectué (`feat: add SIGTERM handler for graceful shutdown logging`).

-   [2025-10-30 14:47] **Stabilisation déploiement PHP (DirectAdmin) + OAuth Gmail Web**
    - Correction des chemins sous DirectAdmin: inclusion `bootstrap_env.php` via `__DIR__` et `.htaccess` (`php_value auto_prepend_file bootstrap_env.php`).
    - Mise à jour `bootstrap_env.php::env_bootstrap_path()` pour distinguer `public_html/` et `data/` (écriture/lecture OK).
    - Correction `GmailOAuthTest.php`: `declare(strict_types=1)` en tout début, chemin `require_once`, réponses JSON propres pour AJAX, logging d'erreurs.
    - Validation end-to-end: dry-run OK, fallback et persistance dans `domains/webhook.kidpixel.fr/data/env.local.php` confirmés.

-   [2025-10-28 12:00] **Correction de l'heure de démarrage des webhooks DESABO**
    - Mise à jour de `orchestrator.py` pour définir `webhooks_time_start` à l'heure de début configurée (par exemple "12h00") pour les e-mails DESABO non urgents traités avant l'ouverture de la fenêtre horaire.
    - Ajout de tests unitaires complets dans `test_orchestrator_desabo_start_before_window.py` pour vérifier le comportement.
    - Mise à jour de la documentation dans `docs/webhooks.md` pour refléter le comportement de l'heure de début pour les DESABO non urgents.
    - Amélioration de la robustesse de la gestion des chemins de fichiers dans `routes/api_logs.py`.

-   [2025-10-25 13:05:00] **Implémentation de la règle URGENT pour DESABO**
    - Ajustement du bypass fenêtre pour les webhooks `detector=desabonnement_journee_tarifs` (urgent skip hors fenêtre, non-urgent bypass conservé). Mises à jour code (`pattern_matching.py`, `orchestrator.py`) + docs (`webhooks.md`).

-   [2025-10-22 20:55] **Stabilisation orchestrateur, webhooks et journaux**
    -   Durcissement de `email_processing/orchestrator.py` (helpers runtime, délégation legacy, règles hors fenêtre, retour explicite pour Media Solution)
    -   Comportement de retry Make.com sécurisé dans `email_processing/webhook_sender.py`
    -   Alignement des défauts et alias runtime dans `routes/api_config.py`, `routes/api_processing.py`, `routes/api_webhooks.py`
    -   Lecture fichier prioritaire, filtrage robuste et tri déterministe dans `routes/api_logs.py`
    -   Suite de 322 tests désormais verte

-   [2025-10-16 22:41] **Synchronisation de la fenêtre horaire globale**
    - Mise à jour de `GET /api/get_webhook_time_window` pour lire depuis le stockage externe
    - Synchronisation automatique de l'état interne au chargement du tableau de bord
    - Maintien de la rétrocompatibilité avec les fichiers locaux
    - Documentation mise à jour dans la Memory Bank

-   [2025-10-16 22:24] **Migration de MySQL vers le stockage JSON externe**
    - Suppression complète du support MySQL et de ses dépendances
    - Implémentation d'un backend PHP sécurisé pour le stockage des configurations
    - Mise en place d'un système de fallback sur fichiers JSON locaux
    - Mise à jour de la documentation complète (configuration.md, storage.md)
    - Suppression des endpoints et de l'interface utilisateur liés à MySQL

-   [2025-10-16 19:20] **Ajout du support des déploiements Render"
    -   Implémentation de 3 méthodes de déploiement : Webhook Render, API Render, et méthode locale de secours
    -   Documentation complète de l'API Render
    -   Gestion robuste des erreurs et journalisation sécurisée

-   [2025-10-15 18:00] **Séparation des fenêtres horaires emails et webhooks**
    -   Création d'une fenêtre horaire dédiée pour le toggle global des webhooks
    -   Nouveaux endpoints API : `GET/POST /api/webhooks/time-window`
    -   Persistance dans `debug/webhook_config.json`
    -   Mise à jour de l'interface utilisateur avec une section dédiée
    -   Gestion indépendante de la fenêtre horaire des emails existante

-   [2025-10-15 15:54] **Correction de l'affichage de l'heure de fin dans les emails**
    -   Ajout de `webhooks_time_end` dans le payload du webhook personnalisé
    -   Mise à jour du template PHP pour afficher l'heure de fin de manière conditionnelle
    -   Correction de la logique de `webhooks_time_start` pour utiliser "maintenant" quand dans la fenêtre horaire

-   [2025-10-15 15:54] **Injection de l'heure de livraison pour les emails Recadrage**
    -   Extraction de `delivery_time` depuis `pattern_matching.check_media_solution_pattern()`
    -   Ajout de `delivery_time` dans le payload du webhook pour le détecteur 'recadrage'
    -   Ajout de logs de diagnostic pour le suivi

-   [2025-10-15 12:34] **Correction du formulaire de test d'envoi Gmail**
    -   Correction des erreurs de syntaxe JavaScript dans `index.php`
    -   Amélioration de la gestion des erreurs et des logs côté client
    -   Validation des entrées utilisateur et gestion des cas d'erreur
    -   Affichage des logs de débogage directement dans l'interface

-   [2025-10-15 11:45] **Unification du flux de webhooks**
    -   Désactivation des routes spécifiques à Make.com (DESABO et Media Solution) dans `email_processing/orchestrator.py`
    -   Suppression des variables d'environnement obsolètes (`RECADRAGE_MAKE_WEBHOOK_URL`, `AUTOREPONDEUR_MAKE_WEBHOOK_URL`)
    -   Amélioration de la détection des liens pour inclure le contenu HTML
    -   Mise à jour de la documentation dans `docs/webhooks.md` et `docs/configuration.md`
    -   Tous les flux passent désormais par `WEBHOOK_URL`

-   [2025-10-15 00:59] **Nouveau flux webhook « recadrage » (Make blueprint RECADRAGE_MAKE_WEBHOOK_URL)**
    -   Branche `detector === 'recadrage'` implémentée: détection « urgence » dans le sujet; usage de `delivery_time` pour le cas non urgent
    -   Envoi via `GmailMailer` avec logs et gestion d'erreurs cohérentes
    -   Tests cURL urgent/non urgent: succès, emails envoyés

-   [2025-10-15 00:58] **Intégration Gmail OAuth (PHP) pour envoi d'emails et flux détecteurs**
    -   Ajout/renforcement de `deployment/src/GmailMailer.php` (OAuth2 refresh→access + envoi RFC822 via Gmail API)
    -   Débogage 401 résolu (OAuth Playground « Use your own OAuth credentials » + nouveau refresh token)
    -   Intégration côté `deployment/src/WebhookHandler.php`

-   [2025-10-15 01:00] **Assouplissement de la validation des payloads pour détecteurs**
    -   `validateWebhookData()` accepte `detector` + `subject` + `sender_email` sans `receivedDateTime`/`delivery_links`/`email_content`
    -   Permet les flux d’autorépondeur Gmail sans contraintes Media Solution

-   [2025-10-14 20:33] **Mise à jour de la documentation suite au workflow /docs-updater**
    - Vérification et mise à jour de `docs/architecture.md` : ajout de la mention du miroir optionnel dans `handle_media_solution_route()`
    - Ajout dans `docs/email_polling.md` d'une section sur la journalisation et traçabilité du polling
    - Vérification de `docs/api.md` : confirmation absence de références aux endpoints Make supprimés
    - Mise à jour de la Memory Bank (decisionLog.md et progress.md)
    - Cohérence parfaite entre code source et documentation assurée

-   [2025-10-14 20:30] **Correction du miroir des liens SwissTransfer**
    - Correction de l'indentation dans `orchestrator.py`
    - Activation de `mirror_media_to_custom: true` dans `debug/processing_prefs.json`
    - Ajout dans `DEFAULT_PROCESSING_PREFS` de `api_processing.py`
    - Documentation complète dans `docs/configuration.md`
    - Ajout de logs de diagnostic dans `app_render.py`
    - Validation : Les liens SwissTransfer/Dropbox/FromSmash sont maintenant correctement transmis au webhook PHP avec réponse HTTP 200

-   [2025-10-14 15:54] **Amélioration des logs de polling et correction des tests**
    -   Ajout de logs "POLLER: Email read from IMAP" lors de la lecture d'un email dans `email_processing/orchestrator.py`.
    -   Promotion du log "marked as read" à niveau INFO dans `email_processing/imap_client.py`.
    -   Ajout de logs "IGNORED" pour les motifs de rejet (fetch KO, expéditeur non autorisé, déduplication email/groupe, fenêtre horaire non satisfaite dans Présence/DESABO).
    -   Ajout d'alias de module pour tests dans `routes/api_config.py` (POLLING_ACTIVE_DAYS, etc.).
    -   Shim de compatibilité pour endpoint polling toggle dans `routes/api_polling.py`.
    -   Hook de délégation dans orchestrator pour attentes de tests.
    -   Résultat: 316 tests passants, traçabilité améliorée sans régression.

-   [2025-10-14 14:25] **Mise à jour de docs/ui.md suite à workflow /docs-updater**
    -   Suppression des références aux contrôles "Vacances" supprimés de `dashboard.html`
    -   Ajustement de la section "Contrôle du Polling IMAP" en "Préférences Make (Polling IMAP)" pour refléter l'onglet actuel
    -   Suppression des références à `#pollingToggle` et mise à jour des appels API (`/api/get_polling_config`, `/api/update_polling_config`)
    -   Ajout d'une note sur le contrôle manuel Make uniquement
    -   Cohérence parfaite entre code source et documentation

-   [2025-10-14 14:21] **Suppression des contrôles automatisés Make (UI + Backend)**
    -   Suppression du toggle global "Activer les scénarios Make" et de la section "Vacances" dans `dashboard.html`
    -   Nettoyage de `static/dashboard.js` : suppression des références à `vacationStart`, `vacationEnd`, `updateVacationStatus()` et `enableGlobalPolling`
    -   Mise à jour de `docs/webhooks.md` pour indiquer contrôle manuel uniquement dans Make.com
    -   Suppression des appels API Make dans `routes/api_config.py` (plus de trigger `toggle_all_scenarios()`)
    -   Raison : erreurs 403 persistantes sur l'API Make, passage au contrôle manuel

-   [2025-10-14 00:24:00] **Ajout de logs explicites pour le redémarrage serveur**
    -   Modification de `routes/api_admin.py` pour journaliser les demandes de redémarrage initiées depuis l'UI.
    -   Logs "ADMIN: Server restart requested..." et "scheduled (background)" via `current_app.logger.info()`.
    -   Amélioration de la traçabilité pour diagnostiquer les échecs (permissions sudoers, etc.).

-   [2025-10-14 00:24:00] **Correction de la persistance des heures de polling dans l'UI**
    -   Modification de `routes/api_config.py` pour lire depuis `config.settings` (live) et mettre à jour dynamiquement après sauvegarde.
    -   Résolution du bug où les anciennes valeurs réapparaissaient après clic sur "💾 Enregistrer la Configuration Polling".
    -   Cohérence immédiate entre UI et backend sans redémarrage.

-   [2025-10-13 22:50] **Configuration de la fenêtre horaire des webhooks**
    -   Modification de `app_render.py` pour charger les valeurs par défaut des variables d'environnement `WEBHOOKS_TIME_START` et `WEBHOOKS_TIME_END`
    -   Conservation de la possibilité de surcharge via l'interface utilisateur
    -   Vérification du bon fonctionnement avec les webhooks DESABO

-   [2025-10-13 12:20] **Mise en place de la suite de tests complète**
    -   **Statut** : ✅ **SUITE DE TESTS CRÉÉE AVEC SUCCÈS**
    -   **Résultats** :
        -   213 tests créés au total (187 passants, 26 à ajuster)
        -   Couverture de code : ~30% (à augmenter après corrections)
        -   Infrastructure de test complète :
            -   Configuration pytest avec marqueurs (unit, integration, e2e, slow, redis, imap)
            -   Fixtures partagées dans `conftest.py`
            -   Script d'exécution `run_tests.sh`
            -   Documentation complète dans `docs/testing.md`

-   [2025-10-13 01:10] **Refactoring Étape 5 (final) : Migration de la dernière route**
    -   Déplacement de `/api/check_emails_and_download` de `app_render.py` vers `routes/api_admin.py`, protégé par `@login_required` et exécuté en tâche de fond.
    -   Suppression de la route legacy dans `app_render.py` (plus aucun `@app.route` dans ce fichier).
    -   Mise à jour de `docs/refactoring-conformity-report.md` pour marquer 100% des routes migrées.
    -   ✅ 58/58 tests verts.

-   [2025-10-13 00:52] **Refactor: lock singleton, auth centralization, docs sync**
    -   Extraction du verrou inter-processus vers `background/lock.py`.
    -   Centralisation de l'authentification dans `auth/user.py`.
    -   Mise à jour de la documentation (`docs/architecture.md`, `docs/refactoring-conformity-report.md`).
    -   Résultat: `app_render.py` ≈ 511 lignes, ✅ 58/58 tests verts.

-   [2025-10-12 23:36] **Refactoring Étape 5 : Extraction des Routes API (Blueprints)**
    -   Création du blueprint `api_logs` pour `/api/webhook_logs`.
    -   Mise à jour du blueprint `api_processing` avec support des URLs legacy.
    -   Suppression des handlers legacy de `app_render.py`.
    -   Mise à jour de la documentation (`architecture.md`, `api.md`).
    -   ✅ 58/58 tests passent avec succès et rétrocompatibilité maintenue.

-   [2025-10-12 23:04] **Refactoring Étape 2b : Nettoyage des duplications**
    -   Suppression des constantes et variables redondantes dans `app_render.py`.
    -   Remplacement par des alias vers `config.settings` pour la configuration centralisée.
    -   Utilisation des helpers centralisés.
    -   ✅ 58/58 tests passent avec succès.

-   [2025-10-12 22:50] **Refactoring Étape 7+ : Modules Additionnels (Dédoublonnage, Logs, Préférences)**
    -   **7A: Dédoublonnage Redis** (`deduplication/redis_client.py`)
    -   **7B: Journalisation Webhooks** (`app_logging/webhook_logger.py`)
    -   **7C: Préférences de Traitement** (`preferences/processing_prefs.py`)
    -   ✅ 58/58 tests passent avec succès et rétrocompatibilité maintenue.

-   [2025-10-12 21:18] **Refactoring Étape 8 : Nettoyage + README**
    -   Nettoyage des imports inutilisés dans `app_render.py`.
    -   Ajout de `README.md` décrivant l'architecture modulaire, installation, exécution et tests.
    -   ✅ 58/58 tests réussis.

-   [2025-10-12 19:27] **Refactoring Étape 6 : Background Polling (extraction du thread)**
    -   Création du package `background/` avec `polling_thread.py`.
    -   Extraction de la boucle de polling dans `background.polling_thread.background_email_poller_loop()`.
    -   Aucune régression, ✅ 58/58 tests passent.

-   [2025-10-12 10:37] **Refactoring Étape 4E : Orchestrateur finalisé + Docs synchronisées**
    -   Point d'entrée unique `email_processing/orchestrator.check_new_emails_and_trigger_webhook()`.
    -   Finalisation des helpers (Présence, DESABO, Média Solution).
    -   Documentation mise à jour (`docs/architecture.md`, `docs/refactoring-roadmap.md`, `docs/email_polling.md`).
    -   ✅ 58/58 tests réussis.

-   [2025-10-12 09:36] **Refactoring Étape 4D : Webhook Sender (Make.com)**
    -   Création de `email_processing/webhook_sender.py` avec `send_makecom_webhook()`.
    -   Délégation depuis `app_render.py` tout en conservant la signature publique.
    -   ✅ 58/58 tests pytest passent (100%).

-   [2025-10-12 09:34] **Refactoring Étape 4C : Helper DESABO**
    -   Ajout de `check_desabo_conditions()` dans `email_processing/pattern_matching.py`.
    -   Remplacement du bloc inline DESABO dans `app_render.py` par l'appel au helper.
    -   ✅ 58/58 tests pytest passent (100%).

-   [2025-10-12 01:10] **Création de la Roadmap de Refactoring Complète**
    -   Création de `docs/refactoring-roadmap.md` - Document de référence exhaustif pour guider toutes les futures sessions de refactoring.

-   [2025-10-12 01:02] **Refactoring Étape 4B : Extraction pattern matching email (Média Solution)**
    -   Extraction complète de `check_media_solution_pattern()` vers `email_processing/pattern_matching.py`.
    -   ✅ 58/58 tests pytest passent (100%), aucune régression fonctionnelle.

-   [2025-10-12 00:54] **Refactoring Étape 4 : Extraction du traitement email (Approche incrémentale minimale)**
    -   Création du module `email_processing/imap_client.py` avec `create_imap_connection()`.
    -   ✅ 58/58 tests pytest passent (100%), approche sûre et progressive validée.

-   [2025-10-12 00:49] **Refactoring Étape 3 : Extraction de l'authentification dans auth/**
    -   Création des modules `auth/user.py` et `auth/helpers.py`.
    -   Extraction de la classe `User`, `LoginManager`, `verify_credentials()`, etc.
    -   ✅ 58/58 tests pytest passent (100%), aucune régression fonctionnelle.

-   [2025-10-12 00:41] **Refactoring Étape 2 : Extraction de la configuration dans config/**
    -   Création des modules `config/settings.py`, `config/polling_config.py`, `config/webhook_time_window.py`.
    -   Centralisation de 45+ variables de configuration.
    -   ✅ 58/58 tests pytest passent (100%), aucune régression fonctionnelle.

-   [2025-10-12 00:27] **Refactoring Étape 1 : Extraction des fonctions utilitaires dans utils/**
    -   Création des modules `utils/time_helpers.py`, `utils/text_helpers.py`, `utils/validators.py`.
    -   Extraction de 6 fonctions pures depuis `app_render.py`.
    -   ✅ 58/58 tests pytest passent (100%), aucune régression fonctionnelle.

-   [2025-10-11 23:59] **Gestion indépendante des mots-clés d'exclusion par webhook**
    -   Ajout de la gestion des mots-clés (Recadrage / Autorépondeur) avec persistance JSON et endpoints sessionnés (`/api/get_processing_prefs`, `/api/update_processing_prefs`).

-   [2025-10-10 11:04] **Suppression de la résolution automatique des liens et des dépendances associées**
    -   Suppression de la résolution automatique pour SwissTransfer/FromSmash.
    -   Suppression des dépendances Playwright et BeautifulSoup.
    -   Mise à jour de l'interface utilisateur et de la documentation.

-   [2025-10-08 13:00] **Correction du comportement du webhook DESABO**
    -   Utilisation de "maintenant" uniquement quand l'email est traité dans la fenêtre horaire.
    -   Mise à jour de la documentation `email_polling.md`.

-   [2025-10-06 13:05] **Ajout de la section UI "Flags Runtime (Debug)"**
    -   Implémentation de toggles et des endpoints API associés (`/api/get_runtime_flags`, `/api/update_runtime_flags`).

-   [2025-10-06 12:45] **Ajout de l'endpoint de test pour vider la déduplication**
    -   Création de `/api/test/clear_email_dedup` pour effacer un email ID du set Redis.

-   [2025-10-06 12:37] **Ajout d'un flag pour les webhooks custom sans liens**
    -   Le flag `ALLOW_CUSTOM_WEBHOOK_WITHOUT_LINKS` permet de skipper le webhook si aucun lien n'est détecté.

-   [2025-10-06 12:23] **Extension du parsing email au contenu HTML**
    -   Traitement des parties HTML et texte pour une meilleure détection de liens.

-   [2025-10-06 12:20] **Correction de bug sur l'API de configuration du polling**
    -   Résolution d'une erreur 500 sur `/api/update_polling_config` en ajoutant des variables globales manquantes.

-   [2025-10-06 12:10] **Ajout de logs détaillés pour la déduplication**
    -   Meilleure traçabilité pour la déduplication des emails.

-   [2025-10-05 15:57] **Ajout de la fonctionnalité de redémarrage serveur depuis l'UI**
    -   Création de l'endpoint `/api/restart_server` (protégé) et du bouton associé dans l'interface.

-   [2025-10-05 15:29] **Réorganisation de l'UI avec une navigation par onglets**
    -   Mise à jour de `dashboard.html` et `static/dashboard.js` pour une interface à onglets (Vue d’ensemble, Webhooks, Polling, etc.).

-   [2025-10-05 14:46:51] **Création d'endpoints de test avec authentification par clé API**
    -   Création des endpoints `/api/test/*` pour un accès CORS-enabled.
    -   Mise à jour de la page de test pour utiliser `X-API-Key`.

-   [2025-10-05 12:35:00] **Amélioration de l'UX pour la configuration des jours de polling**
    -   Remplacement du champ texte `POLLING_ACTIVE_DAYS` par 7 cases à cocher.
    -   Renommage de `trigger_page.html` en `dashboard.html`.

## En cours

Aucune tâche active.

## À faire

Aucune tâche active.