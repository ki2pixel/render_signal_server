# Guide de Tests - render_signal_server

Ce document décrit la stratégie de tests et comment exécuter la suite de tests complète du projet.

## Table des matières

- [Vue d'ensemble](#vue-densemble)
- [Installation](#installation)
- [Exécution des tests](#exécution-des-tests)
- [Types de tests](#types-de-tests)
- [Couverture de code](#couverture-de-code)
- [Bonnes pratiques](#bonnes-pratiques)
- [CI/CD](#cicd)

## Vue d'ensemble

Le projet utilise **pytest** comme framework de test avec plusieurs plugins pour améliorer la qualité et la couverture :

- **pytest-cov** : Génération de rapports de couverture
- **pytest-mock** : Helpers pour le mocking
- **pytest-flask** : Helpers spécifiques Flask
- **fakeredis** : Mock Redis pour les tests sans dépendance externe

### Structure des tests

```
render_signal_server-main/
├── test_app_render.py          # Tests existants (58 tests)
├── tests/                      # Nouveaux tests modulaires
│   ├── conftest.py             # Fixtures partagées
│   ├── test_utils_*.py         # Tests unitaires utils/
│   ├── test_auth.py            # Tests unitaires auth/
│   ├── test_email_processing_*.py  # Tests email_processing/
│   ├── test_routes_integration.py  # Tests d'intégration routes/
│   └── test_email_processing_e2e.py  # Tests end-to-end
├── pytest.ini                  # Configuration pytest
└── .coveragerc                 # Configuration couverture
```

## Installation

### Installer les dépendances de test

```bash
# Installer les dépendances de développement
pip install -r requirements-dev.txt
```

Les dépendances de test incluent :
- pytest >= 7.0
- pytest-cov >= 4.0
- pytest-mock >= 3.10
- pytest-flask >= 1.2
- fakeredis >= 2.10
- freezegun >= 1.2
- responses >= 0.23

## Exécution des tests

### Tous les tests

```bash
# Exécuter tous les tests avec couverture
pytest

# Exécuter avec plus de détails
pytest -v

# Exécuter avec affichage des print() pour debug
pytest -s
```

### Tests par catégorie

```bash
# Tests unitaires uniquement
pytest -m unit

# Tests d'intégration uniquement
pytest -m integration

# Tests end-to-end uniquement
pytest -m e2e

# Exclure les tests lents
pytest -m "not slow"

# Exclure les tests nécessitant Redis
pytest -m "not redis"

# Exclure les tests nécessitant IMAP
pytest -m "not imap"
```

### Tests par module

```bash
# Tests d'un module spécifique
pytest tests/test_utils_time_helpers.py

# Tests d'un dossier
pytest tests/

# Tests legacy
pytest test_app_render.py
```

### Tests spécifiques

```bash
# Un test précis
pytest tests/test_auth.py::TestUser::test_user_creation

# Tests contenant un pattern dans le nom
pytest -k "webhook"
```

### Exécution parallèle

```bash
# Exécuter les tests en parallèle (plus rapide)
pytest -n auto

# Avec nombre de workers spécifique
pytest -n 4
```

## Types de tests

### Tests unitaires (`@pytest.mark.unit`)

Tests isolés d'une seule fonction ou classe, sans dépendances externes.

**Exemple :**
```python
@pytest.mark.unit
def test_normalize_text():
    result = normalize_no_accents_lower_trim("Café")
    assert result == "cafe"
```

**Couverture :**
- `utils/` : time_helpers, text_helpers, validators
- `auth/` : user, helpers
- `email_processing/` : pattern_matching, link_extraction, payloads

### Tests d'intégration (`@pytest.mark.integration`)

Tests vérifiant l'interaction entre plusieurs modules ou composants.

**Exemple :**
```python
@pytest.mark.integration
def test_webhook_config_persistence(authenticated_client, temp_file):
    # Test du cycle complet : POST -> persistence -> GET
    response = authenticated_client.post('/api/webhooks/config', json={...})
    assert response.status_code == 200
    
    response = authenticated_client.get('/api/webhooks/config')
    assert response.json['config']['webhook_url'] == expected_url
```

**Couverture :**
- Routes blueprints (`routes/`)
- Flux de configuration
- Persistence (JSON, Redis mock)

### Tests end-to-end (`@pytest.mark.e2e`)

Tests du flux complet de bout en bout.

**Exemple :**
```python
@pytest.mark.e2e
def test_complete_email_processing_flow():
    # 1. Pattern matching
    # 2. Link extraction
    # 3. Payload construction
    # 4. Webhook sending
    # Vérifier le flux complet
```

**Couverture :**
- Flux email → pattern → webhook
- Scénarios Média Solution
- Scénarios DESABO

### Tests spéciaux

**Tests lents** (`@pytest.mark.slow`) : Tests avec timeout > 1s, exécution réseau, etc.

**Tests Redis** (`@pytest.mark.redis`) : Tests nécessitant une instance Redis (utilisent fakeredis).

**Tests IMAP** (`@pytest.mark.imap`) : Tests nécessitant connexion IMAP réelle (skippés par défaut).

## Couverture de code

### Générer un rapport de couverture

```bash
# Rapport dans le terminal
pytest --cov=. --cov-report=term-missing

# Rapport HTML (recommandé)
pytest --cov=. --cov-report=html

# Ouvrir le rapport HTML
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
start htmlcov/index.html  # Windows

### Couverture actuelle et objectifs

- **Suite complète** : **322 tests verts** (statut 2025-10-22)
- **Couverture globale actuelle** : **82.94%** (dernière mise à jour : 2025-10-13)
- **Modules critiques** (`email_processing/`, `auth/`, `utils/`)
  - `email_processing/orchestrator.py` : **80.9%** (tests unitaires pour les helpers d'orchestration + validations des détecteurs)
  - Autres modules critiques : **≥ 80%**
- **Routes** (`routes/`) : **≥ 70%** (atteint)
  - Points saillants après amélioration ciblée :
    - `routes/api_processing.py` : **84.30%**
    - `routes/api_utility.py` : **96.43%**
    - `routes/dashboard.py` : **96.15%**
- **Robustesse `routes/api_logs.py`** : tri déterministe et priorité fichier (lignes 76-84) testés pour garantir les diagnostics sous charge et éviter les flakiness.
- **Objectif global** : **≥ 80%** (actuellement atteint)

### Fichiers exclus de la couverture

Configurés dans `.coveragerc` :
- Tests eux-mêmes
- Fichiers de déploiement
- Static files
- Documentation

## Bonnes pratiques

### 1. Nommage des tests

```python
# ✅ Bon : descriptif et clair
def test_user_creation_with_valid_credentials():
    ...

# ❌ Mauvais : trop vague
def test_user():
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
