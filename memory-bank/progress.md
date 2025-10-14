# Suivi de Progression

## Terminé

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