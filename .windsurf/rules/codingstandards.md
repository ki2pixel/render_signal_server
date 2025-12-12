---
trigger: always_on
description: 
globs: 
---

# Coding Standards – Proposition Temporaire pour render_signal_server

## Principes directeurs

- Lisibilité avant concision. Le code doit être simple à comprendre pour un autre développeur.
- Commenter le pourquoi lorsqu’une logique n’est pas évidente (décision métier, compromis techniques), pas le comment évident.
- Nommage explicite et cohérent; éviter les abréviations cryptiques.
- Sécurité par défaut: validation et sanitation des entrées, gestion stricte des secrets.
- DRY: factoriser les logiques communes (services, helpers, utilitaires).
- Tests pertinents, reproductibles et intégrés au flux de travail (voir docs/testing.md).
- Configuration pilotée par variables d’environnement et stockage de config dédié.
- Documentation à jour et proche du code (docs/, memory-bank, commentaires ciblés).

---

## Portée et périmètre

Le dépôt comprend principalement:

- Backend Python: serveur Flask, services applicatifs et modules métier.
- Front-end statique: `static/` et `dashboard.html` (Dashboard Webhooks).
- Services orientés métier/configuration dans `services/`.
- Traitement des e-mails dans `email_processing/`.
- Tâches de fond dans `background/`.
- Configuration centralisée dans `config/`.
- Authentification dans `auth/`.
- Déduplication dans `deduplication/`.
- Journalisation dans `app_logging/`.
- Préférences de traitement dans `preferences/`.
- Déploiement / intégrations PHP dans `deployment/` (legacy mais maintenu).
- Documentation dans `docs/` et contexte dans `memory-bank/`.

Organisation modulaire côté backend (vue synthétique):

- `app_render.py`
  - Point d’entrée Flask / orchestrateur.
  - Initialise les services principaux.
  - Enregistre les blueprints `routes/`.
  - Configure logging, CORS, tâches de fond et intégrations externes.

- `routes/` (blueprints Flask)
  - `api_webhooks.py` (config webhooks via WebhookConfigService).
  - `api_config.py` (runtime flags, polling config via services).
  - `api_admin.py` (tâches d’administration, check emails, redémarrage, déploiement Render).
  - `api_processing.py` (préférences de traitement, URLs legacy supportées).
  - `api_logs.py` (logs webhooks).
  - `api_polling.py`, `api_test.py`, `api_make.py`, `api_utility.py`, `dashboard.py`, `health.py`.

- `services/` (architecture orientée services)
  - `ConfigService` (config centralisée, accès typé à config.settings, secrets, Render, auth dashboard, dédup).
  - `RuntimeFlagsService` (Singleton, `runtime_flags.json`, cache TTL, accès et mise à jour des flags runtime).
  - `WebhookConfigService` (Singleton, config webhooks, validation stricte, normalisation Make, cache + store externe, Absence Globale).
  - `AuthService` (authentification dashboard et API, intégration Flask-Login, décorateurs `api_key_required` et similaires).
  - `PollingConfigService` (exposé depuis `config/polling_config.py`, accès centralisé à la config de polling IMAP et timezone).
  - `DeduplicationService` (dédup email ID et subject groups, Redis + fallback mémoire, clés issues de ConfigService).

- `email_processing/`
  - `orchestrator.py` (cycle de polling, application des règles métier, Absence Globale, fenêtres horaires, détecteurs, envoi de webhooks).
  - `imap_client.py`, `pattern_matching.py`, `link_extraction.py`, `payloads.py`, `webhook_sender.py`.

- `background/`
  - `polling_thread.py` (boucle générique de polling IMAP avec dépendances injectées).
  - `lock.py` (verrou singleton inter-processus).

- `docs/`
  - Référentiel de spécification (architecture, API, configuration, tests, sécurité, webhooks, stockage, etc.).

---

## Langages, style et formatage

- Python
  - Respect strict de PEP 8.
  - Formatage automatique avec Black (ligne max 88) et tri des imports avec isort.
  - Lint via flake8 ou ruff (idéalement intégré en CI).

- JavaScript
  - ES2019 minimum.
  - Formatage via Prettier.
  - Lint via ESLint (configuration airbnb-base ou eslint:recommended).

- PHP (deployment)
  - Respect de PSR-12.

- Fichiers
  - Encodage UTF-8, fins de ligne LF.
  - Aucune espace en fin de ligne; un retour à la ligne final par fichier.

---

## Nommage, commentaires et documentation

- Nommage
  - Python: snake_case pour fonctions/variables, PascalCase pour classes.
  - JavaScript: camelCase pour fonctions/variables, PascalCase pour classes.
  - PHP: conventions PSR (camelCase/PascalCase selon contexte).
  - Noms explicites décrivant l’intention (ex: email_config_valid, deduplication_service, absence_pause_enabled).

- Commentaires
  - Expliquer l’intention, les cas limites et les compromis.
  - Éviter de commenter le code évident ou paraphraser les signatures.
  - Documenter les décisions non triviales avec un renvoi éventuel vers `memory-bank/decisionLog.md`.

- Docstrings et documentation
  - Docstrings Python pour fonctions et classes publiques (style Google ou reST), en particulier dans `services/`, `email_processing/`, `background/`.
  - Documentation fonctionnelle et opérationnelle dans `docs/` (architecture, API, configuration, sécurité, tests, webhooks, etc.).
  - Tenir synchronisés: code, docs et memory-bank (productContext, decisionLog, progress, systemPatterns).

---

## Gestion des dépendances et configuration

- Python
  - Lister les dépendances dans `requirements.txt` (avec versions figées quand c’est pertinent) et `requirements-dev.txt` pour les outils de dev/test.
  - Limiter l’ajout de packages; toute nouvelle dépendance doit être justifiée et documentée (impact sécurité et maintenance).

- JavaScript
  - Si un gestionnaire de paquets est utilisé (npm/pnpm/yarn), conserver un lockfile et configurer des scripts cohérents (lint, build, tests front si introduits).

- Configuration
  - Toute configuration sensible (secrets, tokens, URL externes, identifiants) provient de variables d’environnement.
  - Les valeurs de référence présentes dans le code (prefixe REF) ne doivent pas être utilisées en production.
  - Utiliser les services et helpers dédiés pour la lecture de configuration:
    - `ConfigService` pour la plupart des accès config, y compris credentials dashboard, tokens API, clés Render.
    - `RuntimeFlagsService` pour les flags de débogage ou de comportement runtime.
    - `WebhookConfigService` pour la configuration webhook (URL, Absence Globale, etc.).
    - `PollingConfigService` pour la configuration polling IMAP.
  - Ne pas accéder directement aux fichiers JSON dans `debug/` depuis les routes; passer par les services ou helpers `config/app_config_store.py`.

---

## Sécurité applicative

- Entrées utilisateur et API
  - Valider et nettoyer systématiquement toutes les entrées côté serveur (Flask, PHP) et, si nécessaire, côté client.
  - Éviter les injections (SQL, commande, XSS) via requêtes paramétrées, échappement correct des données affichées et contrôle strict des chemins de fichiers.

- Authentification et autorisation
  - Utiliser Flask-Login pour l’authentification UI (`dashboard.py`), via `AuthService.init_flask_login`.
  - Protéger les endpoints sensibles avec `@login_required` et/ou des décorateurs basés sur `AuthService` (par exemple `api_key_required`, `test_api_key_required`).
  - Ne jamais stocker de mots de passe en clair; les identifiants dashboard sont fournis via ENV.

- Secrets et clés
  - Ne jamais commit de secrets ou tokens.
  - `FLASK_SECRET_KEY` doit être défini en production et suffisamment robuste.
  - Les clés API (Render, Make, Gmail, etc.) doivent être gérées via ENV côté Flask ou PHP.

- Webhooks
  - Pour les appels sortants, activer la vérification SSL en production (certificats valides); la désactivation éventuelle (mode legacy/test) doit être explicitement loggée et documentée.
  - Toute future exposition de webhooks entrants doit être protégée par tokens, HMAC ou IP allowlist, et validée en amont (voir docs/securite.md).

- Redis
  - Utiliser `REDIS_URL` avec mot de passe et TLS si possible.
  - Ne pas exposer Redis publiquement.

- Logs
  - Ne pas logger de secrets, contenu d’email complet ni données très sensibles.
  - Utiliser `app_logging/webhook_logger.py` pour la journalisation webhooks (avec fallback mémoire/fichier).

---

## Gestion des erreurs, logs et observabilité

- Erreurs
  - Lever des exceptions explicites dans les services et helpers, les attraper aux frontières (routes, tâches de fond) pour renvoyer des réponses propres.
  - Ne pas masquer silencieusement les erreurs sans log; préférer des logs au moins au niveau warning.

- Logs
  - Centraliser la logique liée aux logs webhooks dans `app_logging/webhook_logger.py`.
  - Conserver des logs structurés et contextualisés (ID email, détecteur, décision prise) sans contenu sensible.
  - Respecter la configuration de niveau de log fournie par ENV (par exemple FLASK_LOG_LEVEL).

- Observabilité
  - Utiliser les handlers existants (heartbeat, SIGTERM) pour diagnostiquer les problèmes de threads de fond et redémarrages Render.
  - Prévoir des logs clairs sur le démarrage/arrêt des tâches de fond (`background/polling_thread.py`, lock file, flags ENABLE_BACKGROUND_TASKS, DISABLE_BACKGROUND_TASKS).

---

## Tests (unitaires, intégration, end-to-end)

Les règles détaillées de tests sont décrites dans `docs/testing.md`. Ce fichier fait foi pour:

- La structure de la suite de tests.
- Les marqueurs pytest (`unit`, `integration`, `e2e`, `redis`, `imap`, etc.).
- Les objectifs de couverture et la configuration `.coveragerc`.

Règles de haut niveau:

- Pyramide de tests
  - Majorité de tests unitaires (services, utils, helpers).
  - Couverture significative par tests d’intégration (routes API, services ensemble).
  - Tests E2E ciblés sur les flux critiques (polling complet, webhooks, absence globale, etc.).

- Services
  - `ConfigService`, `RuntimeFlagsService`, `WebhookConfigService`, `AuthService`, `PollingConfigService`, `DeduplicationService` doivent avoir des tests unitaires ciblés.
  - Pour les Singletons, prévoir des helpers/fixtures pour réinitialiser l’instance (`reset_instance`) dans les tests.
  - Tester les services aussi via les endpoints API correspondants (approche API-first) lorsque pertinent.

- Traitement des e-mails
  - Tester `email_processing/orchestrator.py` à la fois de manière unitaire (helpers) et par scénarios d’intégration/E2E.
  - Couvrir les règles métier spécifiques (DESABO urgent vs non urgent, Absence Globale, fenêtres horaires, dédup, miroir média vers webhook custom).

- Web UI
  - Tester les comportements critiques de `static/dashboard.js` (au minimum via tests d’intégration côté Flask ou tests front si introduits).

- CI
  - L’exécution de pytest avec couverture est obligatoire en CI.
  - Le seuil minimal de couverture et le mode de rapport sont définis dans `docs/testing.md` et `.coveragerc` (ne pas dupliquer ici les chiffres).

---

## Performance et optimisation

- Ne pas optimiser prématurément; baser les optimisations sur des mesures (profilage, logs, métriques).
- Éviter les boucles sur des volumes élevés avec I O bloquantes; préférer les batchs.
- Privilégier l’usage de caches contrôlés pour les données consultées fréquemment (RuntimeFlagsService, WebhookConfigService).
- Éviter les requêtes IMAP ou HTTP inutiles; respecter les règles de fenêtres horaires et de déduplication pour limiter la charge.

---

## Git, branches et messages de commit

- Branches
  - Branches par feature ou fix: `feature/<slug>` ou `fix/<slug>`.
  - Utiliser des branches de courte durée, PRs ciblées.

- Messages de commit
  - Format recommandé type Conventional Commits: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`.
  - Messages au présent, concis et explicites; mentionner le pourquoi si utile.

- Pull Requests
  - Petites, ciblées, avec descr