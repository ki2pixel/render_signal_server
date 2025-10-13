# Tests - render_signal_server

Ce répertoire contient la suite de tests modulaires pour le projet.

## Structure

```
tests/
├── conftest.py                          # Fixtures partagées
├── test_utils_time_helpers.py           # Tests utils/time_helpers.py
├── test_utils_text_helpers.py           # Tests utils/text_helpers.py
├── test_utils_validators.py             # Tests utils/validators.py
├── test_auth.py                         # Tests auth/ (user, helpers)
├── test_email_processing_link_extraction.py   # Tests link_extraction.py
├── test_email_processing_payloads.py    # Tests payloads.py
├── test_email_processing_pattern_matching.py  # Tests pattern_matching.py
├── test_routes_integration.py           # Tests d'intégration routes/
└── test_email_processing_e2e.py         # Tests end-to-end
```

## Exécution rapide

```bash
# Tous les tests de ce dossier
pytest tests/

# Avec couverture
pytest tests/ --cov=. --cov-report=term-missing

# Tests unitaires seulement
pytest tests/ -m unit
```

## Documentation complète

Voir [docs/testing.md](../docs/testing.md) pour le guide complet.
