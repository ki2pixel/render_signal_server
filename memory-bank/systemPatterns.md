# Patrons Système et Architecture

Ce document recense les patrons de conception et les standards récurrents dans le projet.

## Gestion des erreurs et initialisation dans l'interface utilisateur (2025-11-30)

- **Prévention de la double initialisation** : 
  - Utilisation d'un flag global `window.__tabsInitialized` pour s'assurer que les composants UI ne sont initialisés qu'une seule fois
  - Vérification systématique de ce flag avant toute initialisation de composant
  - Journalisation des tentatives d'initialisation multiples pour le débogage

- **Gestion robuste des erreurs API** :
  - Vérification systématique de `res.ok` avant d'appeler `res.json()`
  - Gestion explicite des réponses non-200 avec des messages d'erreur utilisateur clairs
  - Journalisation détaillée des erreurs côté client pour le débogage
  - Gestion des erreurs de parsing JSON avec des blocs try/catch

- **Mise en cache intelligente** :
  - Forçage du rechargement du cache côté serveur avant les requêtes GET critiques
  - Mise à jour optimiste de l'interface utilisateur lors des opérations POST
  - Synchronisation bidirectionnelle entre le cache et l'interface utilisateur

## Gestion des fenêtres horaires et traitement des e-mails

- **Fenêtres horaires configurables** : Le système utilise des fenêtres horaires configurables pour le traitement des e-mails et l'envoi de webhooks. Ces fenêtres sont définies par des variables d'environnement (`WEBHOOK_TIME_START`, `WEBHOOK_TIME_END`) et peuvent être modifiées via l'interface d'administration.

- **Traitement spécial pour les e-mails DESABO** :
  - **Cas non urgent** : Pour les e-mails DESABO non urgents reçus avant l'ouverture de la fenêtre horaire, l'heure de début est définie sur l'heure de début configurée (par exemple "12h00") plutôt que sur l'heure actuelle.
  - **Cas urgent** : Les e-mails DESABO marqués comme urgents ne contournent pas la fenêtre horaire et sont traités uniquement pendant les heures d'ouverture.
  - **Détection d'urgence** : La détection d'urgence est basée sur la présence de mots-clés ("urgent", "urgence") dans le sujet ou le corps de l'e-mail.

- **Gestion robuste des chemins de fichiers** : Les fonctions qui manipulent des fichiers utilisent `pathlib.Path` pour une gestion cohérente des chemins sur différents systèmes d'exploitation. Les chemins sont vérifiés pour l'existence avant toute opération de lecture/écriture.

- **Journalisation structurée** : Les événements importants sont enregistrés avec un format structuré pour faciliter l'analyse et le débogage. Les journaux incluent des métadonnées telles que l'ID de l'e-mail, le type de détecteur et les décisions de traitement prises.

## Authentification par Magic Link (2026-01-07)

- **Service dédié** : `MagicLinkService` (singleton) gère la génération/consommation de tokens, stockage JSON (`MAGIC_LINK_TOKENS_FILE`) et signatures HMAC (`FLASK_SECRET_KEY`).
- **Modes supportés** :
  - One-shot (TTL configurable via `MAGIC_LINK_TTL_SECONDS`, flag `single_use=True`), auto-révocation après consommation.
  - Permanent (`single_use=False`, expiration `None`), destiné aux accès fréquents; nécessite révocation manuelle en cas d'incident.
- **Flux UI/API** : Endpoint `/api/auth/magic-link` protégé par session admin, bouton dédié dans `dashboard.html` + `static/dashboard.js` avec option "illimitée" et copie auto.
- **Sécurité** : Logs contextualisés (user, expiration), nettoyage régulier des tokens expirés, signature forte HMAC SHA-256, stockage verrouillé par `RLock`.

## Refactoring terminologique : "Presence Pause" → "Absence Globale" (2025-11-21)

- **Configuration persistante** : La fonctionnalité Absence Globale utilise des champs JSON persistants (`absence_pause_enabled`, `absence_pause_days`) dans `debug/webhook_config.json`.
- **Validation stricte** : Les jours valides sont normalisés en minuscules et vérifiés contre la liste ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"].
- **Priorité maximale** : L'absence globale a la plus haute priorité dans la logique d'envoi de webhooks, ignorant les autres règles (fenêtre horaire, bypass DESABO).
- **Interface utilisateur** : Toggle binaire avec sélection multiple de jours, validation côté client et serveur.
- **API REST** : Endpoints GET/POST `/api/webhooks/config` pour récupération et mise à jour de la configuration.
- **Tests complets** : Couverture des cas nominaux, limites et d'erreur pour API, service et orchestrateur.

## Suppression de la fonctionnalité "Presence" (2025-11-18)

- **Nettoyage du code** : Suppression complète de la fonctionnalité "Presence" qui n'était plus utilisée, incluant :
  - Éléments d'interface utilisateur dans `dashboard.html` et `dashboard.js`
  - Endpoints API dans `api_webhooks.py` et `api_admin.py`
  - Méthodes liées dans `ConfigService` et `WebhookConfigService`
  - Logique d'orchestration dans `orchestrator.py`
  - Variables d'environnement obsolètes (`PRESENCE_FLAG`, `PRESENCE_TRUE_MAKE_WEBHOOK_URL`, `PRESENCE_FALSE_MAKE_WEBHOOK_URL`)

- **Avantages** :
  - Réduction de la complexité du code
  - Amélioration des performances en supprimant le code inutile
  - Simplification de la maintenance future
  - Réduction de la surface d'attaque de l'application

- **Impact** :
  - Aucun impact sur les fonctionnalités principales
  - Tous les tests passent avec succès
  - Documentation mise à jour pour refléter les changements

## Tests et Qualité du Code

- **Structure des Tests** : Organisation en dossiers `tests/` avec une structure reflétant l'architecture du code source. Utilisation de préfixes `test_` pour les fichiers de test et les fonctions de test.
- **Marqueurs Pytest** : Utilisation de marqueurs personnalisés pour catégoriser les tests :
  - `@pytest.mark.unit` : Tests unitaires isolés
  - `@pytest.mark.integration` : Tests d'intégration entre composants
  - `@pytest.mark.e2e` : Tests de bout en bout
  - `@pytest.mark.slow` : Tests lents (accès réseau, fichiers, etc.)
  - `@pytest.mark.redis` : Tests nécessitant Redis
  - `@pytest.mark.imap` : Tests nécessitant un serveur IMAP
- **Fixtures Partagées** : Définition de fixtures communes dans `conftest.py` pour éviter la duplication de code de test :
  - `mock_redis` : Mock de Redis pour les tests
  - `mock_logger` : Capture des logs pour vérification
  - `flask_client` : Client de test Flask
  - `authenticated_flask_client` : Client authentifié pour les tests d'API
- **Tests de Validation** : Vérification des entrées/sorties des fonctions avec des cas limites et des erreurs attendues.
- **Tests d'Intégration** : Vérification du bon fonctionnement des composants ensemble, notamment les blueprints Flask.
- **Tests End-to-End** : Vérification des flux complets (ex: réception email → traitement → envoi webhook).
- **Couverture de Code** : Configuration via `.coveragerc` pour suivre la couverture des tests et identifier les zones non couvertes.
- **Exécution des Tests** : Script `run_tests.sh` pour faciliter l'exécution sélective des tests (unité, intégration, e2e) avec options de couverture et de verbosité.

## Architecture & Déploiement

-   **Modèle de Configuration Hiérarchique** : La configuration suit un modèle hiérarchique où les valeurs par défaut sont définies dans le code (`REF_*`), peuvent être remplacées par des variables d'environnement, et enfin par des surcharges via l'interface utilisateur. Ce modèle est particulièrement utilisé pour les paramètres de fenêtres horaires (ex: `WEBHOOKS_TIME_START`, `WEBHOOKS_TIME_END`).

-   **Configuration par Environnement** : Toute la configuration (secrets, URLs, paramètres) est injectée via des variables d'environnement. Le code contient des valeurs `REF_*` pour le développement uniquement.
-   **Service Web + Worker en Arrière-plan** : L'application Flask sert une API/UI et gère en parallèle une tâche de fond (le polling IMAP) dans un thread distinct. Ce patron évite de bloquer les requêtes HTTP et ne nécessite pas de scheduler externe (comme Celery ou cron) pour des besoins simples.
-   **Déploiement via Reverse Proxy** : Le déploiement standard se fait via un serveur d'application (Gunicorn) derrière un reverse proxy (Nginx), qui gère la terminaison SSL, les headers de sécurité et le service des fichiers statiques.
-   **Flags Runtime Persistés** : Pour les fonctionnalités de débogage ou temporaires, utiliser des flags runtime chargés depuis un fichier JSON (ex: `runtime_flags.json`), appliqués au démarrage et modifiables via API/UI sans redémarrage. Exemples: bypass dedup, skip webhooks conditionnels. Persistance via fichier pour survivre aux restarts, UI pour contrôle dynamique.

---

## Architecture orientée services (2025-11-17)

- **Services dédiés par responsabilité** : Encapsuler la logique métier et de configuration par services (`ConfigService`, `RuntimeFlagsService`, `WebhookConfigService`, `AuthService`, `PollingConfigService`, `DeduplicationService`).
- **Singletons avec cache TTL** : Pour les configurations volatiles ou fréquemment lues, utiliser des Singletons avec cache mémoire et TTL (ex: `RuntimeFlagsService` TTL=60s; `WebhookConfigService` avec cache/invalidation).
- **Intégration routes** : Les blueprints (`routes/*`) doivent consommer les services (import ou récupération d’instance via `get_instance()`) plutôt que d’accéder aux modules globaux (`config.*`).
- **Normalisation/Validation** : Centraliser la validation stricte (ex: URLs HTTPS) et la normalisation (ex: Make.com) dans `WebhookConfigService` au lieu de la logique dispersée dans les routes.
- **Nettoyage legacy** : Préférer des appels directs aux services et supprimer progressivement les wrappers de compatibilité une fois les tests verts.
- **Tests** : Vérifier prioritairement via l’API (GET/POST) plutôt que lecture directe de fichiers; garder des tests unitaires de service isolés pour la logique de validation/cache.

## Code et Logique

-   **Authentification par Session** : L'accès aux routes protégées est géré par des sessions côté serveur, mises en place par Flask-Login. Le client conserve un cookie de session.
-   **Déduplication via Set** : Pour éviter de traiter plusieurs fois le même e-mail, un identifiant unique est généré pour chaque message et stocké dans un ensemble (Set). L'implémentation privilégie Redis pour la persistance, avec un fallback en mémoire.
-   **Communication par Webhook Sortant** : La notification vers des systèmes externes est réalisée via des requêtes HTTP POST (webhooks) vers des URLs configurables.
-   **Fenêtres d'Activité Programmées** : La tâche de fond (polling IMAP) ne s'exécute que pendant des plages horaires et des jours spécifiques, définis par des variables d'environnement, afin de limiter la consommation de ressources.
-   **Validation et Nettoyage des Entrées** : Le principe de "sécurité par défaut" impose la validation et le nettoyage de toutes les entrées utilisateur pour prévenir les injections (XSS, SQL, etc.), notamment côté PHP.
-   **Parsing Multi-Part Emails** : Pour la détection de contenu (URLs, termes), traiter les parties text/plain et text/html séparément, combiner les textes nettoyés (via BeautifulSoup pour HTML) afin de capturer les informations présentes uniquement dans le HTML. Debug logs pour indiquer l'usage de HTML.

## Tâches d'arrière-plan (Poller IMAP)

-   **Singleton inter-processus pour le poller** : Le thread `background_email_poller()` ne doit s'exécuter qu'une seule fois par machine/cluster d'app. On applique un verrou fichier via `fcntl` et on exige `ENABLE_BACKGROUND_TASKS=1|true|yes` pour le démarrer. Le lockfile par défaut est `/tmp/render_signal_server_email_poller.lock` et peut être surchargé par `BG_POLLER_LOCK_FILE`.
    - Avantages: évite les multi-instances en environnement Gunicorn multi-workers, réduit les risques d'OOM/timeouts, clarifie l'intention opératoire.
    - Bonnes pratiques: activer le poller sur un seul process (ou service dédié), garder les autres workers sans poller.

## Tests

-   **Pyramide des Tests** : L'approche de test préconise une majorité de tests unitaires, complétés par des tests d'intégration pour les interactions I/O (base de données, réseau), et potentiellement des tests E2E pour les flux critiques. `pytest` est l'outil recommandé.

## Orchestrateur email — Patterns (2025-11-18)
- Helpers module-level: éviter les fonctions imbriquées longues et non testables.
- TypedDict pour les structures transmises (ParsedEmail) afin de clarifier les contrats.
- Constantes nommées (IMAP_*, DETECTOR_*, ROUTE_*) pour éviter les magic strings et les typos.
- Découpage fetch/parse vs. logique de routing pour réduire la complexité cyclomatique.
- Logs défensifs: messages concis, pas de contenu sensible, format %s, early-returns.

## Moteur de Routage Dynamique (2026-01-25)

- **Service Redis-first** : `RoutingRulesService` (singleton, cache TTL 30s) avec validation stricte et normalisation des URLs webhook.
- **Pattern d'évaluation séquentielle** : Les règles sont évaluées dans l'ordre, la première correspondance est utilisée, support du flag `stop_processing`.
- **Fallback backend** : Génération automatique de règles "backend-*" reproduisant les comportements historiques (DESABO/Media Solution) lors de la première utilisation.
- **Validation temps réel** : Vérification des URLs HTTPS (obligatoires) ou tokens Make.com, protection contre les injections regex.
- **Architecture modulaire frontend** : Service ES6 `RoutingRulesService.js` avec builder visuel, drag-drop, auto-sauvegarde debounce 2-3s.
- **Tests complets** : 12 tests couvrant service (3), API (3), et orchestrator (6) avec marqueurs `@pytest.mark.routing`.