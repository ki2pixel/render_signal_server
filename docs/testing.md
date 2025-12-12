# 🧪 Guide de Tests - Render Signal Server

Ce document décrit la stratégie de tests complète pour le projet, couvrant les tests unitaires, d'intégration et end-to-end, ainsi que les bonnes pratiques et les métriques de qualité.

## 📋 Table des Matières

- [📊 Vue d'ensemble](#-vue-densemble)
- [⚙️ Installation](#-installation)
- [🚀 Exécution des tests](#-exécution-des-tests)
- [🧩 Types de tests](#-types-de-tests)
- [📈 Couverture de code](#-couverture-de-code)
- [🎯 Bonnes pratiques](#-bonnes-pratiques)
- [🔄 CI/CD](#-cicd)
- [🔍 Dépannage](#-dépannage)
- [📊 Métriques de qualité](#-métriques-de-qualité)

## 📊 Vue d'ensemble

Le projet utilise **pytest** comme framework de test principal, avec une suite d'outils modernes pour assurer une couverture maximale et une détection précoce des régressions.

### 🧰 Outils Principaux

- **pytest** - Framework de test principal
- **pytest-cov** - Analyse de couverture de code
- **pytest-mock** - Création de mocks et de stubs
- **pytest-flask** - Intégration avec Flask
- **fakeredis** - Mock Redis pour les tests
- **freezegun** - Contrôle du temps dans les tests
- **responses** - Mock des requêtes HTTP
- **hypothesis** - Tests basés sur la propriété

### 🏗️ Structure des Tests

```
render_signal_server-main/
├── tests/
│   ├── unit/                  # Tests unitaires
│   │   ├── services/          # Tests des services
│   │   ├── utils/             # Tests des utilitaires
│   │   └── auth/              # Tests d'authentification
│   │
│   ├── integration/           # Tests d'intégration
│   │   ├── api/               # Tests des routes API
│   │   └── services/          # Tests d'intégration des services
│   │
│   ├── e2e/                   # Tests end-to-end
│   │   ├── email_processing/  # Flux complets de traitement d'emails
│   │   └── webhooks/          # Tests des webhooks
│   │
│   ├── fixtures/              # Données de test
│   ├── conftest.py            # Configuration et fixtures partagées
│   └── helpers/               # Utilitaires de test
│
├── pytest.ini                 # Configuration pytest
└── .coveragerc                # Configuration de la couverture
```

### 📊 Métriques Clés

- **Couverture de code** : 67.3% (objectif : 80%+)
- **Tests passants** : 282/290 (97.2%)
- **Temps d'exécution** : ~45s (sans les tests lents)
- **Dernière exécution** : 2025-11-18 14:30:45

## ⚙️ Installation

### Prérequis

- Python 3.9+
- pip 20.0+
- Redis (optionnel, pour les tests d'intégration complets)

### Installation des Dépendances

```bash
# Cloner le dépôt
git clone https://github.com/votre-utilisateur/render_signal_server.git
cd render_signal_server

# Créer un environnement virtuel (recommandé)
python -m venv venv
source venv/bin/activate  # Sur Windows: .\venv\Scripts\activate

# Installer les dépendances de développement
pip install -r requirements-dev.txt
```

### Configuration de l'Environnement

Créez un fichier `.env.test` à la racine du projet avec les variables d'environnement nécessaires :

```env
FLASK_ENV=testing
FLASK_APP=app_render.py
TESTING=True
DISABLE_BACKGROUND_TASKS=true
```

### Dépendances de Test

| Package | Version | Description |
|---------|---------|-------------|
| pytest | >=7.0 | Framework de test principal |
| pytest-cov | >=4.0 | Couverture de code |
| pytest-mock | >=3.10 | Mocks et stubs |
| pytest-flask | >=1.2 | Intégration Flask |
| fakeredis | >=2.10 | Mock Redis |
| freezegun | >=1.2 | Contrôle du temps |
| responses | >=0.23 | Mock HTTP |
| hypothesis | >=6.0 | Tests basés sur la propriété |
| black | >=22.0 | Formatage du code |
| flake8 | >=4.0 | Linting |
| mypy | >=0.9 | Vérification des types |
| safety | >=2.0 | Vérification des vulnérabilités |

## 🚀 Exécution des Tests

### 🎯 Exécution de Base

```bash
# Tous les tests avec couverture
pytest --cov=.

# Avec plus de détails
pytest -v

# Afficher les sorties de débogage
pytest -s

# Arrêter au premier échec
pytest -x

# Exécuter uniquement les tests qui ont échoué lors de la dernière exécution
pytest --last-failed
```

### 🧩 Tests par Catégorie

```bash
# Tests unitaires
pytest -m unit

# Tests d'intégration
pytest -m integration

# Tests end-to-end
pytest -m e2e

# Exclure les tests lents
pytest -m "not slow"

# Exclure les tests nécessitant Redis
pytest -m "not redis"

# Exclure les tests nécessitant IMAP
pytest -m "not imap"

# Exécuter les tests marqués comme critiques
pytest -m "critical"
```

### 📂 Tests par Module ou Classe

```bash
# Tous les tests d'un module
pytest tests/unit/services/test_config_service.py

# Tous les tests d'une classe
pytest tests/unit/services/test_config_service.py::TestConfigService

# Un test spécifique
pytest tests/unit/services/test_config_service.py::TestConfigService::test_get_setting
```

### 🔍 Filtrage des Tests

```bash
# Par nom de test
pytest -k "config"

# Exclure certains tests
pytest -k "not slow and not integration"

# Afficher les tests les plus lents
pytest --durations=10
```

### ⚡ Exécution Parallèle

```bash
# Détection automatique du nombre de cœurs
pytest -n auto

# Spécifier le nombre de workers
pytest -n 4

# Mode fail-fast en parallèle
pytest -n auto --dist=loadscope -x
```

### 📊 Rapports de Couverture

```bash
# Générer un rapport HTML
pytest --cov=. --cov-report=html

# Afficher les parties non couvertes
pytest --cov=. --cov-report=term-missing

# Définir un seuil minimum de couverture (échec si en dessous)
pytest --cov=. --cov-fail-under=80
```

## 🧩 Types de Tests

### 🧪 Tests Unitaires (`@pytest.mark.unit`)

Tests isolés d'une seule unité de code (fonction, méthode, classe) sans dépendances externes.

**Objectif** : Vérifier le comportement d'une unité de code de manière isolée.

**Exemple :**
```python
@pytest.mark.unit
def test_normalize_text():
    """Teste la normalisation du texte (suppression des accents, minuscules)."""
    result = normalize_no_accents_lower_trim("Café Élégant")
    assert result == "cafe elegant"
```

**Couverture Actuelle :**
- `utils/` : Fonctions utilitaires (time_helpers, text_helpers, validators)
- `auth/` : Gestion de l'authentification (user, helpers)
- `email_processing/` : Traitement des emails (pattern_matching, link_extraction, payloads)
- `services/` :
  - `ConfigService` : Gestion de la configuration
  - `RuntimeFlagsService` : Gestion des flags runtime
  - `WebhookConfigService` : Configuration des webhooks
  - `DeduplicationService` : Prévention des doublons
  - `AuthService` : Authentification et autorisation
  - `PollingConfigService` : Configuration du polling
  - `tests/test_absence_pause.py` : vérifie la normalisation des jours (`strip().lower()`) et la garde de cycle (`ABSENCE_PAUSE`), garantissant que le poller s'arrête avant toute connexion IMAP les jours d'absence.

### 🔄 Tests d'Intégration (`@pytest.mark.integration`)

Tests vérifiant l'interaction entre plusieurs composants ou modules.

**Objectif** : Vérifier que les composants fonctionnent correctement ensemble.

**Exemple :**
```python
@pytest.mark.integration
def test_webhook_config_persistence(authenticated_client, temp_file):
    """Teste le cycle complet de persistance de la configuration des webhooks."""
    # 1. Création d'une configuration
    config_data = {
        "webhook_url": "https://api.example.com/webhook",
        "enabled": True,
        "timeout": 30
    }
    
    # 2. Enregistrement de la configuration
    response = authenticated_client.post(
        '/api/webhooks/config',
        json=config_data,
        headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 200
    
    # 3. Récupération de la configuration
    response = authenticated_client.get('/api/webhooks/config')
    assert response.status_code == 200
    
    # 4. Vérification des données
    saved_config = response.json['config']
    assert saved_config['webhook_url'] == config_data['webhook_url']
    assert saved_config['enabled'] == config_data['enabled']
    assert saved_config['timeout'] == config_data['timeout']
```

**Couverture Actuelle :**
- Routes API (`routes/`)
- Intégration des services
- Persistance des données (JSON, Redis)
- Validation des entrées/sorties
- Gestion des erreurs

### 🌐 Tests End-to-End (`@pytest.mark.e2e`)

Tests du flux complet de bout en bout, simulant un utilisateur réel.

**Objectif** : Vérifier que l'ensemble du système fonctionne comme prévu.

**Exemple :**
```python
@pytest.mark.e2e
def test_complete_email_processing_flow(
    imap_server_mock, 
    webhook_receiver,
    test_email_with_dropbox_links
):
    """Teste le flux complet de réception et traitement d'un email."""
    # 1. Configuration du mock IMAP pour retourner un email de test
    imap_server_mock.add_email(test_email_with_dropbox_links)
    
    # 2. Déclenchement du traitement
    response = test_client.post('/api/check_emails_and_download')
    assert response.status_code == 202
    
    # 3. Vérification que le webhook a été appelé
    webhook_receiver.wait_for_request(timeout=5.0)
    
    # 4. Vérification du contenu du webhook
    request = webhook_receiver.get_latest_request()
    payload = request.get_json()
    
    assert payload['subject'] == test_email_with_dropbox_links['subject']
    assert len(payload['links']) > 0
    assert payload['detector'] == 'media_solution'
```

**Couverture Actuelle :**
- Flux complet de traitement des emails
- Scénarios Média Solution
- Scénarios DESABO (urgent/non urgent)
- Gestion des erreurs et reprises
- Notifications et webhooks

### 🎲 Tests de Propriété (`@pytest.mark.property`)

Tests basés sur des propriétés avec génération aléatoire de données.

**Objectif** : Détecter les cas limites et les erreurs subtiles.

**Exemple :**
```python
from hypothesis import given, strategies as st

@given(
    text=st.text(
        alphabet=st.characters(
            min_codepoint=1,
            max_codepoint=1000,
            blacklist_categories=('Cc', 'Cs')
        ),
        min_size=1
    )
)
@pytest.mark.property
def test_normalize_no_accents_property(text):
    """Teste que la normalisation conserve la longueur du texte."""
    normalized = normalize_no_accents(text)
    assert len(normalized) == len(text)
```

**Couverture Actuelle :**
- Fonctions de manipulation de texte
- Validation des entrées
- Conversion de formats
- Gestion des cas limites

### 🏷️ Marqueurs de Test

Le projet utilise des marqueurs pour catégoriser et contrôler l'exécution des tests.

#### Marqueurs Intégrés

- `@pytest.mark.slow` : Tests prenant plus de temps à s'exécuter
  ```bash
  # Exclure les tests lents
  pytest -m "not slow"
  ```

- `@pytest.mark.redis` : Tests nécessitant Redis
  ```bash
  # Exécuter uniquement les tests Redis
  pytest -m "redis"
  
  # Exclure les tests Redis
  pytest -m "not redis"
  ```

- `@pytest.mark.imap` : Tests nécessitant une connexion IMAP
  ```bash
  # Exécuter les tests IMAP (nécessite une configuration valide)
  pytest -m "imap"
  ```

- `@pytest.mark.e2e` : Tests end-to-end
  ```bash
  # Exécuter uniquement les tests E2E
  pytest -m "e2e"
  ```

#### Marqueurs Personnalisés

- `@pytest.mark.critical` : Tests critiques pour la validation des fonctionnalités principales
  ```bash
  # Exécuter uniquement les tests critiques
  pytest -m "critical"
  ```

- `@pytest.mark.flaky` : Tests sujets à des échecs intermittents
  ```bash
  # Réessayer les tests échoués jusqu'à 3 fois
  pytest --reruns 3 -m "flaky"
  ```

- `@pytest.mark.performance` : Tests de performance
  ```bash
  # Exécuter les tests de performance
  pytest -m "performance"
  ```

### 🧠 Tests Paramétrés

Utilisation de `@pytest.mark.parametrize` pour tester plusieurs scénarios avec des données différentes.

**Exemple :**
```python
@pytest.mark.parametrize("input_text,expected_output", [
    ("Hello World", "hello world"),
    ("TEST", "test"),
    ("MiXeD CaSe", "mixed case"),
    ("", ""),
    ("   trim   ", "trim"),
])
def test_normalize_text(input_text, expected_output):
    assert normalize_text(input_text) == expected_output
```

### 🧪 Fixtures

Les fixtures sont définies dans `tests/conftest.py` et peuvent être utilisées dans tous les tests.

**Fixtures Principales :**
- `app` : Instance de l'application Flask
- `client` : Client de test Flask
- `db` : Base de données de test
- `redis_client` : Client Redis (ou mock)
- `imap_server_mock` : Mock du serveur IMAP
- `webhook_receiver` : Serveur de test pour recevoir les webhooks

**Exemple d'Utilisation :**
```python
def test_webhook_endpoint(client, webhook_receiver):
    # Configuration du webhook
    webhook_url = webhook_receiver.get_url()
    
    # Envoi d'une requête au webhook
    response = client.post(
        "/api/webhooks",
        json={"message": "test"},
        headers={"Content-Type": "application/json"}
    )
    
    # Vérification de la réponse
    assert response.status_code == 200
    
    # Vérification que le webhook a été appelé
    webhook_receiver.wait_for_request()
    request = webhook_receiver.get_latest_request()
    assert request.get_json()["message"] == "test"
```

## 📈 Couverture de Code

### Génération des Rapports

```bash
# Rapport HTML interactif (ouvre le navigateur)
pytest --cov=. --cov-report=html

# Afficher les parties non couvertes dans le terminal
pytest --cov=. --cov-report=term-missing

# Définir un seuil minimum (échec si non atteint)
pytest --cov=. --cov-fail-under=70

# Combiner plusieurs formats de rapport
pytest --cov=. --cov-report=html --cov-report=term-missing

# Ouvrir le rapport HTML après génération
python -m webbrowser htmlcov/index.html  # Multiplateforme
# Rapport HTML interactif (ouvre le navigateur)
pytest --cov=. --cov-report=html

# Afficher les parties non couvertes dans le terminal
pytest --cov=. --cov-report=term-missing

# Définir un seuil minimum (échec si non atteint)
pytest --cov=. --cov-fail-under=70

# Combiner plusieurs formats de rapport
pytest --cov=. --cov-report=html --cov-report=term-missing

# Ouvrir le rapport HTML après génération
python -m webbrowser htmlcov/index.html  # Multiplateforme
```

### État Actuel de la Couverture (2025-11-18)

| Métrique | Valeur | Objectif |
|----------|--------|----------|
| Tests passants | 282/290 (97.2%) | 100% |
| Couverture globale | 67.3% | 75%+ |
| Temps d'exécution | ~45s (hors tests lents) | < 2 min |

### Modules Clés et Couverture

#### Services Principaux
- `services/runtime_flags_service.py` : 82% (cache TTL, invalidation, persistance)
- `services/webhook_config_service.py` : 78% (validation HTTPS, normalisation Make.com)
- `services/deduplication_service.py` : 75% (Redis + fallback mémoire)
- `services/config_service.py` : 85% (gestion de la configuration)
- `services/auth_service.py` : 80% (authentification et autorisation)

#### Traitement des Emails
- `email_processing/orchestrator.py` : 72% (flux principal de traitement)
- `email_processing/pattern_matching.py` : 88% (détection des modèles d'emails)
- `email_processing/link_extraction.py` : 85% (extraction des liens)

#### Routes API
- `routes/api_config.py` : 78% (gestion de la configuration)
- `routes/api_webhooks.py` : 75% (gestion des webhooks)
- `routes/api_logs.py` : 82% (journalisation et consultation des logs)

### Configuration de la Couverture

Le fichier `.coveragerc` définit les exclusions et la configuration :

```ini
[run]
source = .
omit =
    /venv/*
    /tests/*
    */__pycache__/*
    */.pytest_cache/*
    */version.py
    */__init__.py

[report]
# Seuil d'échec (configuré dans CI)
fail_under = 70

# Exclure les parties non pertinentes pour la couverture
exclude_lines =
    pragma: no cover
    def __repr__
    raise NotImplementedError
    if __name__ == .__main__.:
    pass
    raise ImportError
    @abc.abstractmethod
    @pytest.fixture
    @pytest.mark
    # Ignorer les méthodes magiques
    def __[a-zA-Z0-9_]+__
    # Ignorer les propriétés
    @property\s+def
    # Ignorer les setters
    @[a-zA-Z0-9_]+\.setter\s
```

### Stratégies d'Amélioration

#### 1. Analyse des Zones à Améliorer

```bash
# Identifier les fichiers avec moins de 70% de couverture
pytest --cov=. --cov-report=term-missing | grep -v "100%" | sort -k4 -n

# Générer un rapport HTML pour une analyse détaillée
pytest --cov=. --cov-report=html
```

#### 2. Exemples de Tests Manquants

**Fonction à tester :**
```python
def calculate_discount(price, discount_percent):
    if discount_percent < 0 or discount_percent > 100:
        raise ValueError("Discount must be between 0 and 100")
    return price * (1 - discount_percent / 100)
```

**Tests manquants :**
```python
import pytest

@pytest.mark.parametrize("price, discount, expected", [
    (100, 10, 90.0),     # Réduction de 10%
    (100, 0, 100.0),     # Aucune réduction
    (100, 100, 0.0),     # 100% de réduction
    (100, 50, 50.0),     # 50% de réduction
    (0, 10, 0.0),        # Prix à zéro
])
def test_calculate_discount(price, discount, expected):
    assert calculate_discount(price, discount) == expected

# Tester les cas d'erreur
@pytest.mark.parametrize("discount", [-1, 101])
def test_calculate_discount_invalid(discount):
    with pytest.raises(ValueError):
        calculate_discount(100, discount)
```

#### 3. Exclure du Code Délibérément

```python
# Exclure une fonction spécifique
def experimental_feature():  # pragma: no cover
    """Fonction expérimentale non encore testée."""
    pass

# Exclure un bloc de code
if DEBUG_MODE:  # pragma: no cover
    logger.warning("Mode débogage activé")
```

### Intégration Continue

Configuration recommandée pour GitHub Actions (`.github/workflows/tests.yml`) :

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      redis:
        image: redis
        ports: [6379:6379]
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.9'
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements-dev.txt
    
    - name: Run tests with coverage
      env:
        REDIS_URL: redis://localhost:6379/0
      run: |
        pytest --cov=. --cov-report=xml --cov-fail-under=70
    
    - name: Upload coverage to Codecov
      uses: codecov/codecov-action@v3
      with:
        token: ${{ secrets.CODECOV_TOKEN }}
        file: ./coverage.xml
        fail_ci_if_error: true
```

### Outils Recommandés

- **Codecov** : Suivi de la couverture dans le temps
- **SonarQube** : Analyse statique et métriques de qualité
- **Pylint** : Vérification de la qualité du code
- **Black** : Formatage automatique du code
- **pre-commit** : Exécution automatique des tests avant les commits

## 🎯 Bonnes Pratiques de Test

### 1. Nommage des Tests

```python
# ✅ Bon : descriptif et clair
def test_user_creation_with_valid_credentials():
    ...

def test_webhook_retry_on_failure():
    ...

# ❌ Mauvais : trop vague
def test_user():
    ...

def test_1():
    ...
```

### 2. Structure AAA (Arrange-Act-Assert)

```python
def test_webhook_config_update():
    # Arrange : préparer les données
    config = {'webhook_url': 'https://example.com/hook'}
    
    # Act : exécuter l'action
    result = update_webhook_config(config)
    
    # Assert : vérifier le résultat
    assert result['status'] == 'success'
    assert result['url'] == config['webhook_url']
```

### 3. Utilisation de Fixtures

```python
import pytest

@pytest.fixture
def test_user():
    """Crée un utilisateur de test avec des données par défaut."""
    return {
        'username': 'testuser',
        'email': 'test@example.com',
        'is_active': True
    }

def test_user_activation(test_user):
    # Utilisation de la fixture
    assert test_user['is_active'] is True
    
    # Test de la désactivation
    test_user['is_active'] = False
    assert test_user['is_active'] is False
```

### 4. Tests Paramétrés

```python
import pytest

@pytest.mark.parametrize("input_value,expected_output", [
    ("hello", "HELLO"),
    ("WORLD", "WORLD"),
    ("", ""),
    ("123", "123"),
])
def test_uppercase(input_value, expected_output):
    assert input_value.upper() == expected_output
```

## 🔄 CI/CD

### Configuration de Base

Le fichier `.github/workflows/tests.yml` est configuré pour :
1. Exécuter les tests sur chaque push et pull request
2. Tester sur Python 3.9 et 3.10
3. Utiliser Redis comme service pour les tests d'intégration
4. Générer un rapport de couverture
5. Envoyer les résultats à Codecov

### Déploiement Automatique

Pour activer le déploiement automatique après des tests réussis :

```yaml
# Dans .github/workflows/deploy.yml
name: Deploy

on:
  push:
    branches: [main]
  workflow_run:
    workflows: ["Tests"]
    types: [completed]

jobs:
  deploy:
    if: github.ref == 'refs/heads/main' && github.event.workflow_run.conclusion == 'success'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      # Étapes de déploiement...
```

## 🔍 Dépannage

### Tests Échouant de Manière Aléatoire

1. **Problème de concurrence** : Utilisez `@pytest.mark.flaky` pour les tests non déterministes
2. **Données partagées** : Assurez-vous que chaque test est isolé
3. **Dépendances externes** : Mockez les appels réseau et les bases de données

### Erreurs Courantes

```
# Erreur : Base de données verrouillée
# Solution : Assurez-vous de fermer correctement les connexions dans les fixtures

# Erreur : Timeout des tests
# Solution : Marquez les tests lents avec @pytest.mark.slow et exécutez-les séparément

# Erreur : Échec de l'authentification
# Solution : Vérifiez les jetons et les identifiants dans les variables d'environnement de test
```

## 📊 Métriques de Qualité

### Objectifs

- Couverture de code : 80% minimum
- Taux de réussite des tests : 100%
- Temps d'exécution total : < 2 minutes
- Nombre de tests unitaires > tests d'intégration > tests E2E

### Suivi

- Tableau de bord Codecov pour la couverture de code
- Rapports de tests GitHub Actions pour les échecs
- Métriques SonarQube pour la dette technique

## 📚 Ressources

- [Documentation officielle de pytest](https://docs.pytest.org/)
- [pytest-cov documentation](https://pytest-cov.readthedocs.io/)
- [pytest-flask documentation](https://pytest-flask.readthedocs.io/)
- [Meilleures pratiques pour les tests Python](https://docs.pytest.org/en/stable/goodpractices.html)

---

*Dernière mise à jour : 2025-11-18*

### Stratégies d'Amélioration

#### 1. Analyse des Zones à Améliorer

```bash
# Identifier les fichiers avec moins de 70% de couverture
pytest --cov=. --cov-report=term-missing | grep -v "100%" | sort -k4 -n

# Générer un rapport HTML pour une analyse détaillée
pytest --cov=. --cov-report=html
```

#### 2. Exemples de Tests Manquants

**Fonction à tester :**
```python
def calculate_discount(price, discount_percent):
    if discount_percent < 0 or discount_percent > 100:
        raise ValueError("Discount must be between 0 and 100")
    return price * (1 - discount_percent / 100)
```

**Tests manquants :**
```python
import pytest

@pytest.mark.parametrize("price, discount, expected", [
    (100, 10, 90.0),     # Réduction de 10%
    (100, 0, 100.0),     # Aucune réduction
    (100, 100, 0.0),     # 100% de réduction
    (100, 50, 50.0),     # 50% de réduction
    (0, 10, 0.0),        # Prix à zéro
])
def test_calculate_discount(price, discount, expected):
    assert calculate_discount(price, discount) == expected

# Tester les cas d'erreur
@pytest.mark.parametrize("discount", [-1, 101])
def test_calculate_discount_invalid(discount):
    with pytest.raises(ValueError):
        calculate_discount(100, discount)
```

#### 3. Exclure du Code Délibérément

```python
# Exclure une fonction spécifique
def experimental_feature():  # pragma: no cover
    """Fonction expérimentale non encore testée."""
    pass

# Exclure un bloc de code
if DEBUG_MODE:  # pragma: no cover
    logger.warning("Mode débogage activé")
```

### Intégration Continue

Configuration recommandée pour GitHub Actions (`.github/workflows/tests.yml`) :

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      redis:
        image: redis
        ports: [6379:6379]
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.9'
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements-dev.txt
    
    - name: Run tests with coverage
      env:
        REDIS_URL: redis://localhost:6379/0
      run: |
        pytest --cov=. --cov-report=xml --cov-fail-under=70
    
    - name: Upload coverage to Codecov
      uses: codecov/codecov-action@v3
      with:
        token: ${{ secrets.CODECOV_TOKEN }}
        file: ./coverage.xml
        fail_ci_if_error: true
```

### Outils Recommandés

- **Codecov** : Suivi de la couverture dans le temps
- **SonarQube** : Analyse statique et métriques de qualité
- **Pylint** : Vérification de la qualité du code
- **Black** : Formatage automatique du code

### 2. Structure AAA (Arrange-Act-Assert)

```python
def test_webhook_config_update():
    # Arrange : préparer les données
    config = {'webhook_url': 'https://example.com/hook'}
    
    # Act : exécuter l'action
    result = update_webhook_config(config)
    
    # Assert : vérifier le résultat
    assert result['success'] is True
```

### 3. Utiliser les fixtures

```python
# Plutôt que de créer manuellement des mocks
def test_with_fixture(mock_logger, temp_file):
    # Les fixtures sont automatiquement injectées
    ...
```

### 4. Isolation des tests

```python
# Chaque test doit être indépendant
@pytest.fixture(autouse=True)
def reset_state():
    # Setup
    yield
    # Cleanup automatique après chaque test
```

### 5. Mocking approprié

```python
# Mock uniquement les dépendances externes
with patch('requests.post') as mock_post:
    mock_post.return_value.status_code = 200
    result = send_webhook(...)
    assert result is True
```

### 6. Singletons des services (tests)

- Certains services sont des Singletons (ex: `RuntimeFlagsService`, `WebhookConfigService`).
- Avant/Après un test, vous pouvez réinitialiser l'instance pour isoler l'état:

```python
from services.runtime_flags_service import RuntimeFlagsService
from services.webhook_config_service import WebhookConfigService

def setup_function():
    RuntimeFlagsService.reset_instance()
    WebhookConfigService.reset_instance()
```

- Utilisez des fichiers temporaires (`tmp_path`) pour la persistence JSON dans les tests.

### 7. Stratégie API‑first

- Privilégier la validation par les endpoints (GET/POST) qui consomment les services.
- Exemple: mettre à jour des flags via `POST /api/update_runtime_flags` puis vérifier `GET /api/get_runtime_flags`.
- Pour la config webhook, tester la validation HTTPS et le masquage d'URL via `GET/POST /api/webhooks/config`.

## Fixtures communes

Définies dans `tests/conftest.py` :

- `mock_redis` : Client Redis mocké (fakeredis)
- `mock_logger` : Logger mocké
- `temp_file` : Fichier temporaire
- `temp_dir` : Répertoire temporaire
- `flask_app` : Instance Flask pour tests
- `flask_client` : Client de test Flask
- `authenticated_flask_client` : Client Flask authentifié
- `sample_email_body` : Corps d'email exemple
- `sample_email_subject` : Sujet d'email exemple

## Debugging

### Afficher les logs

```bash
# Afficher tous les logs
pytest -s --log-cli-level=DEBUG

# Afficher seulement les logs d'un module
pytest -s --log-cli-level=DEBUG -k "test_webhook"
```

### Arrêter au premier échec

```bash
pytest -x
```

### Lancer le debugger au premier échec

```bash
pytest --pdb
```

### Ré-exécuter seulement les tests échoués

```bash
# Premier run
pytest

# Ré-exécuter seulement les échecs
pytest --lf

# Ré-exécuter les échecs puis tous les autres
pytest --ff
```

## CI/CD

### Configuration recommandée

```yaml
# .github/workflows/tests.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.10'
    
    - name: Install dependencies
      run: |
        pip install -r requirements-dev.txt
    
    - name: Run tests with coverage
      run: |
        pytest --cov=. --cov-report=xml --cov-report=term
    
    - name: Upload coverage
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml
```

### Pré-commit hooks (optionnel)

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: pytest-check
        name: pytest-check
        entry: pytest
        language: system
        pass_filenames: false
        always_run: true
```

## Checklist avant mise en production

Avant de déployer en production, vérifier :

- [ ] Tous les tests passent : `pytest`
- [ ] Couverture ≥ 75% : `pytest --cov=. --cov-report=term`
- [ ] Pas de tests skippés non intentionnels
- [ ] Tests d'intégration passent avec config réelle
- [ ] Documentation à jour
- [ ] Variables d'environnement documentées
- [ ] Logs de debug désactivés en production

## Commandes utiles

```bash
# Suite complète optimale
pytest -v --cov=. --cov-report=html --cov-report=term-missing -n auto

# Tests rapides (skip slow et external)
pytest -m "not slow and not imap and not redis"

# Tests critiques avant commit
pytest -m "unit or integration" --cov=. --cov-report=term

# Vérifier la syntaxe sans exécuter
pytest --collect-only

# Statistiques de la suite de tests
pytest --co -q
```

## Ressources

- [Documentation pytest](https://docs.pytest.org/)
- [pytest-cov documentation](https://pytest-cov.readthedocs.io/)
- [pytest-flask documentation](https://pytest-flask.readthedocs.io/)
- [Best practices pytest](https://docs.pytest.org/en/stable/goodpractices.html)

---

**Note** : Ce guide est vivant et doit être mis à jour lors de l'ajout de nouveaux types de tests ou pratiques.
