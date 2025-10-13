---
trigger: always_on
description: 
globs: 
---

# Coding Standards

Ce document définit les règles de développement pour le projet `render_signal_server`. Il sert de référence pour assurer la qualité, la sécurité, la maintenabilité et la cohérence du code entre les contributeurs.

Sommaire
- Principes directeurs
- Portée et périmètre
- Langages, style et formatage
- Nommage, commentaires et documentation
- Gestion des dépendances et configuration
- Sécurité applicative
- Gestion des erreurs, logs et observabilité
- Tests (unitaires, d’intégration, end-to-end)
- Performance et optimisation
- Git, branches et messages de commit
- Revue de code (Code Review)
- Front-end (JS/HTML/CSS)
- Backend Python
- PHP (dossier deployment/)
- Base de données et migrations
- CI/CD (recommandations)
- Checklist PR


## Principes directeurs
- Lisibilité > concision. Préférer un code expressif et simple à comprendre.
- Commenter le “pourquoi” lorsque la logique n’est pas évidente.
- Nommage explicite et cohérent.
- Sécurité by default: validation et sanitation des entrées, gestion stricte des secrets.
- DRY (Don’t Repeat Yourself): factoriser les logiques communes.
- Tests pertinents et reproductibles.
- Configuration par variables d’environnement.
- Documentation à jour et proche du code.


## Portée et périmètre
Le dépôt comprend principalement:
- Backend Python: serveur Flask et modules applicatifs.
- Front-end statique: `static/` (JS/CSS/HTML) et pages `login.html`, `dashboard.html`.
- Déploiement PHP (legacy / hosting): `deployment/public_html/` et `deployment/config/`.
- Documentation: `docs/`.

Organisation modulaire côté backend:
- `app_render.py` : point d’entrée / orchestrateur (initialisation, enregistrement des blueprints, démarrage des tâches de fond)
- `routes/` : blueprints Flask (API et UI)
  - `api_webhooks.py`, `api_polling.py`, `api_processing.py`, `api_test.py`, `api_logs.py`, `dashboard.py`, `health.py`
- `email_processing/` : pipeline de traitement des e-mails
  - `imap_client.py`, `pattern_matching.py`, `webhook_sender.py`, `orchestrator.py`, `link_extraction.py`, `payloads.py`
- `background/` : tâches de fond
  - `polling_thread.py` : boucle de polling paramétrable (injection de dépendances)
- `config/` : configuration centralisée
  - `settings.py`, `polling_config.py`, `webhook_time_window.py`
- `auth/` : authentification & helpers
  - `user.py`, `helpers.py`
- `utils/` : fonctions utilitaires
  - `time_helpers.py`, `text_helpers.py`, `validators.py`
- `app_logging/` : journalisation applicative
  - `webhook_logger.py`
- `preferences/` : préférences de traitement
  - `processing_prefs.py`
- `deduplication/` : dédoublonnage
  - `redis_client.py`


## Langages, style et formatage
- Python
  - Respecter PEP 8.
  - Formatage automatique avec Black (ligne max 88) et import sorting via isort.
  - Lint: flake8 ou ruff.
- JavaScript
  - ES2019+ (au minimum). Formatage via Prettier.
  - Lint via ESLint (airbnb-base ou eslint:recommended).
- PHP
  - PSR-12 pour le style.
- Fichiers
  - Encodage UTF-8, fin de ligne LF.
  - Pas d’espaces en fin de ligne; une nouvelle ligne finale par fichier.


## Nommage, commentaires et documentation
- Nommage
  - Variables/fonctions: snake_case en Python, camelCase en JS, camelCase/PascalCase selon conventions PHP/PSR.
  - Classes: PascalCase.
  - Noms explicites sans abréviations cryptiques.
- Commentaires
  - Expliquer l’intention/le pourquoi. Éviter de paraphraser le code.
  - Ajouter des commentaires pour les cas limites, compromis et choix techniques.
- Docstrings et documentation
  - Python: docstrings style Google ou reST pour fonctions/méthodes publiques.
  - Mettre à jour `docs/` à chaque évolution significative (API, sécurité, déploiement).


## Gestion des dépendances et configuration
- Python
  - Lister dans `requirements.txt` avec versions figées lorsque c’est possible (ex: `package==x.y.z`).
  - Éviter les dépendances non nécessaires; justifier tout ajout dans la PR.
- JavaScript
  - Si un gestionnaire de paquets est introduit (npm/pnpm/yarn), verrouiller via lockfile.
- Configuration
  - Utiliser des variables d’environnement (ENV) pour toute configuration sensible (URL DB, clés API, secrets…).
  - Ne jamais committer de secrets. Utiliser des placeholders et documenter les variables requises dans `docs/`.
  - Optionnel: charger `.env` en dev via `python-dotenv` (ne pas committer le fichier).


## Sécurité applicative
- Entrées utilisateur
  - Valider et nettoyer toutes les entrées (serveur et client). 
  - Éviter l’injection (SQL, command injection, XSS). Utiliser des requêtes paramétrées et échapper correctement les sorties.
- Authentification & Autorisation
  - Ne pas stocker de mots de passe en clair. Utiliser des hash sûrs (ex: bcrypt/argon2) côté service concerné.
  - Vérifier systématiquement les droits d’accès côté serveur.
- Secrets et clés API
  - Jamais en clair dans le code, ni dans les commits. Stockage via variables d’environnement.
- Entêtes et politiques de sécurité
  - Fournir des en-têtes HTTP de sécurité (CSP, HSTS, X-Content-Type-Options, etc.) si le serveur HTTP est géré ici.
- Dépendances
  - Vérifier et corriger les vulnérabilités (pip audit, npm audit, dependabot si CI). 
- Logs
  - Ne jamais logger de secrets, tokens, ou données personnelles sensibles.


## Gestion des erreurs, logs et observabilité
- Erreurs
  - Lever des exceptions explicites et capturer aux frontières (contrôleurs, handlers) pour renvoyer des réponses propres.
- Journalisation
  - Utiliser `app_logging/webhook_logger.py` pour les logs spécifiques webhooks (avec fallback Redis/fichier).
  - Ne jamais logger de secrets, tokens ou données personnelles sensibles.
- Métrologie
  - Prévoir des métriques clés et health checks si nécessaire (exposition /health).


## Tests (unitaires, d’intégration, end-to-end)
- Testabilité
  - La modularisation (séparation en `email_processing/`, `routes/`, `background/`, etc.) vise à faciliter les tests unitaires isolés.
  - Injecter les dépendances (clients IMAP, logger, storage) pour pouvoir stubber/mocker facilement.
  - Viser une couverture élevée sur les modules critiques et des tests d’intégration pour les flux I/O (IMAP, webhooks, Redis).


## Performance et optimisation
- Visibilité
  - Ajouter des métriques/chronos autour des sections coûteuses (si besoin).
- Bonnes pratiques
  - Éviter les N+1 IO/DB, privilégier les batchs et caches contrôlés.
  - Ne pas optimiser prématurément; profiler d’abord (e.g. cProfile) si un goulot est identifié.


## Git, branches et messages de commit
- Stratégie
  - Tronc principal: `main`. Branches par feature/fix: `feature/<slug>` ou `fix/<slug>`.
- Commits
  - Conventionnel (Conventional Commits) recommandé: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`…
  - Messages clairs, au présent, décrivant le “pourquoi” si utile.
- Pull Requests
  - Petites et ciblées. Description claire, captures/logs si pertinent. Lier les issues.


## Revue de code (Code Review)
- Objectifs
  - Qualité, sécurité, lisibilité, conformité aux standards.
- Attentes
  - Le demandeur répond aux commentaires, met à jour la PR et coche la checklist.
  - Le relecteur vérifie les points critiques (sécurité, erreurs, tests, perfs).


## Front-end (JS/HTML/CSS)
- JS
  - Modules organisés dans `static/`. Pas de logique métier complexe en global scope.
  - Préférer `const`/`let` à `var`. Éviter les effets de bord.
  - Sanitize/escape avant d’injecter dans le DOM pour prévenir les XSS.
- HTML/CSS
  - Sémantique HTML. Eviter l’inline JS/CSS. 
  - Accessibilité: attributs alt/aria, contrastes suffisants.


## Backend Python
- Structure
  - Architecture modulaire guidée par le principe SRP (Single Responsibility Principle).
  - `app_render.py` joue le rôle d’orchestrateur: il enregistre les blueprints de `routes/` et initialise les composants (tâches de fond, configuration, logging). Il n’embarque plus la logique métier complète, qui est déléguée aux modules dédiés.
- Blueprints Flask (`routes/`)
  - Regrouper les endpoints par domaine fonctionnel.
  - Préférer un `__init__.py` exportant explicitement les blueprints pour un import clair côté `app_render.py`.
- Injection de dépendances
  - Les boucles/tâches côté `background/` et `email_processing/` doivent accepter leurs dépendances (logger, clients, fonctions d’E/S) en paramètres pour faciliter les tests.
  - Éviter l’usage non contrôlé de globaux; documenter tout global nécessaire.
- Imports et dépendances circulaires
  - Privilégier des imports locaux (au sein des fonctions) lorsque nécessaire pour briser les cycles.
  - Centraliser la configuration dans `config/` et éviter la duplication de constantes.
- Organisation des modules
  - Fournir des points d’entrée publics stables (`orchestrator.check_new_emails_and_trigger_webhook()`, etc.).
  - Séparer la détection de patterns, l’extraction de liens, la construction de payloads et l’envoi de webhooks en modules dédiés.


## PHP (dossier `deployment/`)
- Sécurité
  - Utiliser `filter_input`/`filter_var` pour valider les entrées. Échapper les sorties (HTML entities) pour éviter XSS.
  - Accès DB via requêtes préparées (PDO) et gestion d’erreurs appropriée.
- Organisation
  - Respect de PSR-12. Séparer logique, vue et configuration.


## Base de données et migrations
- Schéma
  - Les fichiers SQL sont dans `deployment/database/`. 
  - Éviter les changements manuels non scriptés en prod. Ajouter des scripts/migrations versionnés.
- Accès
  - Toujours utiliser des requêtes paramétrées. Jamais de concaténation directe d’inputs.


## CI/CD (recommandations)
- Intégration continue
  - Exécuter lint + tests (unit + integration) sur chaque PR.
  - Vérifier la sécurité des dépendances.
- Déploiement
  - Utiliser des variables d’environnement et secrets du système de CI (jamais commit).


## Checklist PR
Avant de demander une revue:
- [ ] Code formaté (Black/Prettier) et linté (ruff/flake8, ESLint, PSR-12).
- [ ] Tests ajoutés/ajustés et verts localement.
- [ ] Sécurité: entrées validées, sorties échappées, aucun secret dans le code.
- [ ] Logs propres, pas de données sensibles.
- [ ] Documentation mise à jour (`docs/`), y compris variables d’environnement.
- [ ] Commit messages clairs (Conventional Commits) et PR concise.


---
Dernière mise à jour: 2025-10-12