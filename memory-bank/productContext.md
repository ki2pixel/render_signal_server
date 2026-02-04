# Contexte Produit : render_signal_server

## 1. Vue d'ensemble

Le projet `render_signal_server` est une application web qui remplit deux fonctions principales :
1. **Télécommande web sécurisée** : Fournit une interface utilisateur (UI) protégée par authentification pour déclencher et superviser des workflows sur un "worker local" distant.
2. **Service d'ingestion Gmail Push** : Reçoit les emails directement depuis Google Apps Script via l'endpoint `POST /api/ingress/gmail`, les traite (détection de motifs, routing dynamique, enrichissement R2) et déclenche des webhooks vers des services externes (URL personnalisée, Make.com). Les liens de partage (Dropbox, FromSmash, SwissTransfer) sont enrichis avec offload Cloudflare R2 quand activé, avec fallback gracieux.

L'application est construite en Python avec le framework Flask pour le backend et une architecture frontend ES6 modulaire pour le dashboard.

## 2. Composants principaux

### Architecture Modulaire (2025-10-13)

-   **Point d'entrée** (`app_render.py`):
    -   Initialisation de l'application Flask
    -   Configuration des blueprints
    -   Lancement des tâches de fond

-   **Routes API** (`routes/`):
    -   `api_admin.py`: Gestion des tâches d'administration (redémarrage, tests)
    -   `api_config.py`: Configuration des webhooks et des runtime flags
    -   `api_ingress.py`: Ingestion Gmail Push (endpoint unique `POST /api/ingress/gmail`)
    -   `api_processing.py`: Traitement des préférences (legacy)
    -   `api_webhooks.py`: Gestion des webhooks
    -   `api_routing_rules.py`: Moteur de routage dynamique
    -   `api_auth.py`: Magic links et authentification

-   **Traitement des e-mails** (`email_processing/`):
    -   `orchestrator.py`: Orchestration du flux Gmail Push (validation, routing, enrichissement)
    -   `pattern_matching.py`: Détection des motifs (Média Solution, Désabonnement)
    -   `webhook_sender.py`: Envoi des webhooks avec retry
    -   `link_extraction.py`: Extraction des liens fournisseurs
    -   `payloads.py`: Construction des payloads JSON

-   **Services** (`services/`):
    -   `config_service.py`: Service de configuration centralisé
    -   `runtime_flags_service.py`: Flags runtime avec persistance Redis (Singleton)
    -   `webhook_config_service.py`: Configuration webhooks avec validation (Singleton)
    -   `auth_service.py`: Authentification et sessions
    -   `deduplication_service.py`: Déduplication emails/subjects (Redis-first)
    -   `routing_rules_service.py`: Moteur de routage dynamique (Redis-first, Singleton)
    -   `magic_link_service.py`: Magic links pour authentification sans mot de passe (Singleton)
    -   `r2_transfer_service.py`: Offload Cloudflare R2 (Singleton)

-   **Utilitaires** (`utils/`):
    -   `text_helpers.py`: Traitement de texte
    -   `time_helpers.py`: Gestion des dates/heures
    -   `validators.py`: Validation des entrées

-   **Suite de Tests** :
    -   **356 tests** (100% passants)
    -   **Couverture de code** : 67.73% (seuil CI à 70%)
    -   **Tests critiques** :
        - Ingestion Gmail Push et authentification
        - Moteur de routage dynamique
        - Gestion des webhooks (succès/échec/retry)
        - Déduplication des e-mails (Redis/mémoire)
        - Services Redis-first et fallbacks
        - Offload R2 et résilience

## 4. État Actuel (2026-02-04)

Le projet a terminé avec succès une migration majeure vers Gmail Push et une architecture orientée services :

-   **Architecture Gmail Push** : Retrait complet du polling IMAP (7 phases), ingestion unique via Apps Script → `/api/ingress/gmail` avec authentification Bearer, allowlist expéditeurs et routing dynamique.
-   **Services Redis-first** : Configurations persistées dans Redis (`runtime_flags`, `webhook_config`, `processing_prefs`, `routing_rules`, `magic_link_tokens`) avec fallback fichiers pour résilience.
-   **Runtime Flags** : Toggle dynamique `gmail_ingress_enabled` dans dashboard (onglet Outils) avec persistance Redis et debug logging complet.
-   **Offload R2** : Service `R2TransferService` pour enrichissement automatique des liens Dropbox vers Cloudflare R2 avec fallback gracieux.
-   **Routing Rules Engine** : Moteur de routage dynamique avec builder UI drag-drop, validation temps réel et support du flag `stop_processing`.
-   **Frontend ES6 Modulaire** : Dashboard refactorisé en modules (`ApiService`, `WebhookService`, `LogService`, `TabManager`) avec UX avancée (timeline, panneaux pliables, auto-sauvegarde).
-   **Magic Links** : Authentification sans mot de passe via `MagicLinkService` avec tokens signés HMAC et TTL configurable.
-   **Tests complets** : 356/356 tests passants, couverture 67.73%, suites spécialisées (Redis, R2, résilience).

### Prochaines étapes potentielles

-   Améliorer la couverture des modules critiques (<80%)
-   Optimiser la complexité de l'orchestrateur (réduction des branches Media Solution/DESABO)
-   Documenter les patterns d'intégration courants dans `systemPatterns.md` (déjà fait partiellement)
-   Explorer la migration vers Pydantic pour validation des préférences

-   **Routes via Blueprints (`routes/`)** :
    -   `health.py` → `GET /health`
    -   `api_webhooks.py` → `GET/POST /api/webhooks/config`
    -   `api_ingress.py` → `POST /api/ingress/gmail` (ingestion Gmail Push)
    -   `api_routing_rules.py` → `GET/POST /api/routing_rules`
    -   `api_processing.py` → `GET/POST /api/processing_prefs` (legacy)
    -   `api_test.py` → `/api/test/*`
    -   `api_config.py` → `GET/POST /api/runtime_flags`
    -   `api_auth.py` → `POST /api/auth/magic-link`
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

## Mise à jour (2025-11-18) — Suppression de la fonctionnalité "Presence"
- **Suppression complète** de la fonctionnalité "Presence" obsolète, incluant :
  - Éléments d'interface utilisateur dans `dashboard.html` et `dashboard.js`
  - Endpoints API dans `api_webhooks.py` et `api_admin.py`
  - Méthodes liées dans `ConfigService` et `WebhookConfigService`
  - Logique d'orchestration dans `orchestrator.py`
  - Variables d'environnement obsolètes (`PRESENCE_FLAG`, `PRESENCE_TRUE_MAKE_WEBHOOK_URL`, `PRESENCE_FALSE_MAKE_WEBHOOK_URL`)
- **Tests** : Suppression ou marquage comme skip des tests liés à la présence
- **Documentation** : Mise à jour pour refléter les changements
- **Avantages** : Réduction de la complexité, amélioration des performances, simplification de la maintenance
- **Statut** : Déployé en production, tous les tests passent avec succès

## Mise à jour (2025-11-21) — Refactoring terminologique : "Presence Pause" → "Absence Globale"
- **Refactoring complet** : Changement de terminologie "presence_pause" → "absence_pause" pour une meilleure cohérence logique.
- **Fonctionnalité Absence Globale** : Permet de bloquer complètement l'envoi de webhooks sur des jours spécifiques de la semaine.
  - **Configuration** : Via l'interface utilisateur (dashboard) ou API (`/api/webhooks/config`)
  - **Comportement** : Aucun email envoyé (DESABO ni Media Solution) les jours sélectionnés, de 00h00 à 23h59
  - **Priorité** : Plus haute priorité, ignore les autres règles (fenêtre horaire, bypass DESABO)
  - **Validation** : Au moins un jour doit être sélectionné si activé, jours valides : monday-sunday
- **Fichiers impactés** : `services/webhook_config_service.py`, `routes/api_webhooks.py`, `email_processing/orchestrator.py`, `static/dashboard.js`, `dashboard.html`, `docs/webhooks.md`, `tests/test_absence_pause.py`
- **Tests** : 12/12 tests passent (100%), couverture maintenue
- **Statut** : Refactoring terminé, déployé en production

## Mise à jour (2026-01-25) — Moteur de Routage Dynamique
- Implémentation complète d'un moteur de routage dynamique pour les e-mails entrants.
- Service `RoutingRulesService` (singleton, Redis-first) avec validation et normalisation des règles.
- API REST `/api/routing_rules` (GET/POST) sécurisée avec validation stricte.
- Intégration dans l'orchestrateur : évaluation des règles avant envoi webhook par défaut, support du flag `stop_processing`.
- Interface utilisateur dans le dashboard : builder de règles avec drag-drop, autosave debounce, accessibilité ARIA.
- Tests exhaustifs : 12 tests couvrant service (3), API (3) et orchestrator (6).
- Fichiers impactés : `services/routing_rules_service.py`, `routes/api_routing_rules.py`, `email_processing/orchestrator.py`, `dashboard.html`, `static/services/RoutingRulesService.js`, `static/dashboard.js`, tests associés.
- Statut : Terminé avec succès, prêt pour production.