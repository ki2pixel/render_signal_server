# Patrons Système et Architecture

Ce document recense les patrons de conception et les standards récurrents dans le projet.

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