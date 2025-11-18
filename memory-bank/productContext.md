# Contexte Produit : render_signal_server

## 1. Vue d'ensemble

Le projet `render_signal_server` est une application web qui remplit deux fonctions principales :
1.  **Télécommande web sécurisée** : Fournit une interface utilisateur (UI) protégée par authentification pour déclencher et superviser des workflows sur un "worker local" distant.
2.  **Service de polling d'e-mails** : Exécute une tâche de fond qui surveille une boîte de réception IMAP, filtre les e-mails pertinents, en extrait des informations (liens de partage, fenêtres de livraison) et déclenche des webhooks vers des services externes (URL personnalisée, Make.com). Les liens de partage (Dropbox, FromSmash, SwissTransfer) sont fournis tels quels, sans résolution automatique des liens directs.

L'application est construite en Python avec le framework Flask pour le backend et des fichiers statiques (JS/HTML/CSS) pour le frontend.

## 2. Composants principaux

### Architecture Modulaire (2025-10-13)

-   **Point d'entrée** (`app_render.py`):
    -   Initialisation de l'application Flask
    -   Configuration des blueprints
    -   Lancement des tâches de fond

-   **Routes API** (`routes/`):
    -   `api_admin.py`: Gestion des tâches d'administration (redémarrage, tests)
    -   `api_config.py`: Configuration des webhooks et des préférences
    -   `api_polling.py`: Gestion du polling IMAP
    -   `api_processing.py`: Traitement des e-mails
    -   `api_webhooks.py`: Gestion des webhooks

-   **Traitement des e-mails** (`email_processing/`):
    -   `orchestrator.py`: Orchestration du flux de traitement
    -   `pattern_matching.py`: Détection des motifs (Média Solution, Désabonnement)
    -   `webhook_sender.py`: Envoi des webhooks avec retry

-   **Tâches de fond** (`background/`):
    -   `polling_thread.py`: Boucle de polling IMAP
    -   `lock.py`: Verrouillage inter-processus

-   **Utilitaires** (`utils/`):
    -   `text_helpers.py`: Traitement de texte
    -   `time_helpers.py`: Gestion des dates/heures
    -   `validators.py`: Validation des entrées

-   **Suite de Tests** :
    -   **257 tests** (100% passants)
    -   **Couverture de code** : 71.9% (seuil CI à 70%)
    -   **Tests critiques** :
        - Détection des motifs d'e-mails
        - Gestion des webhooks (succès/échec/retry)
        - Déduplication des e-mails (Redis/mémoire)
        - Gestion des erreurs et timeouts

## 4. État Actuel (2025-10-13)

Le projet a récemment subi un important refactoring pour améliorer sa maintenabilité :

-   **Architecture modulaire** avec séparation claire des responsabilités
-   **Migration complète** des routes vers des blueprints Flask
-   **Couverture de tests** >70% (seuil CI) avec 257 tests passants
-   **Documentation** à jour dans `TESTING_STATUS.md`
-   **CI/CD** configurée avec GitHub Actions (seuil de couverture à 70%)

### Prochaines étapes potentielles

-   Améliorer la couverture des modules critiques (<80%)
-   Ajouter des tests d'intégration avec Redis/IMAP (marqués `@pytest.mark.redis`/`@pytest.mark.imap`)
-   Documenter les patterns d'intégration courants dans `systemPatterns.md`

-   **Routes via Blueprints (`routes/`)** :
    -   `health.py` → `GET /health`
    -   `api_webhooks.py` → `GET/POST /api/webhooks/config`
    -   `api_polling.py` → `POST /api/polling/toggle`
    -   `api_processing.py` → `GET/POST /api/processing_prefs`
    -   `api_test.py` → `/api/test/*`
    -   `dashboard.py` → `/`, `/login`, `/logout`

-   **Tâches d’arrière-plan (`background/`)** :
    -   `polling_thread.py` expose `background_email_poller_loop(...)` (boucle générique avec dépendances injectées)
    -   `app_render.background_email_poller()` délègue à cette boucle

## 3. Organisation et Standards

-   **Code source principal** : `app_render.py`
-   **Dépendances Python** : `requirements.txt` (Flask, requests, python-dotenv, imap-tools, schedule, redis, python-dateutil)
-   **Configuration** : Exclusivement via variables d'environnement (documenté dans `configuration.md`).
-   **Standards de code** : Définis dans `codingstandards.md` (PEP 8, Black, isort pour Python; Prettier, ESLint pour JS; PSR-12 for PHP).
-   **Documentation** : Organisée dans des fichiers Markdown à la racine.

---

## 5. Mise à jour (2025-11-17) — Architecture orientée services

-   Refactoring complet en 5 phases pour adopter une architecture orientée services.
-   Services créés et intégrés (6): `ConfigService`, `RuntimeFlagsService` (Singleton, cache 60s), `WebhookConfigService` (Singleton, validation stricte + normalisation), `AuthService`, `PollingConfigService`, `DeduplicationService`.
-   Intégrations clés:
    -   `app_render.py` initialise les services et délègue la logique configuration/auth/dédup aux services.
    -   Routes migrées: `api_config.py` → RuntimeFlagsService, `dashboard.py` → AuthService, `api_webhooks.py` → WebhookConfigService, `api_admin.py` → ConfigService.
-   Nettoyage: suppression des wrappers legacy, appels directs aux services, tests adaptés pour vérifier via API plutôt que lecture de fichiers.
-   Qualité: 83/83 tests passent (100%). Couverture globale ≈ 41.16% (+~15 pts). Statut: Production Ready.

## Mise à jour (2025-11-18) — Refactoring email_processing
- Modules refactorés: imap_client, link_extraction, pattern_matching, payloads, webhook_sender, orchestrator.
- Ajout massif de types (TypedDict, signatures explicites), logs sécurisés, robustesse renforcée.
- Orchestrator: helpers extraits, constants, TypedDict ParsedEmail, docstrings complètes, helper de parsing d'e-mail.
- Tests: 282 passants, 8 échecs préexistants focussés sur routes legacy (non liés au refactor).
- Couverture globale ≈ 67.3%.

## Mise à jour (2025-11-18) — Nettoyage post-refactoring de app_render.py
- Nettoyage d'imports inutilisés post-architecture orientée services (subprocess, requests, urljoin, fcntl, re, LoginManager, UserMixin, login_user, logout_user, current_user).
- Gestion explicite du flag DISABLE_BACKGROUND_TASKS avec priorité override pour tous les threads de fond (_heartbeat, _bg_email_poller, _make_watcher).
- Amélioration de _log_webhook_config_startup() pour utiliser WebhookConfigService quand disponible.
- Ajout de TODO pour déprécation future de auth_user.init_login_manager() en faveur de AuthService.
- Code plus maintenable et contrôle fiable des tâches de fond, aucune régression fonctionnelle.