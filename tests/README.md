# Tests - render_signal_server

Ce répertoire contient la suite de tests modulaires du projet. Les tests suivent le découpage du code : `tests/email_processing/`, `tests/routes/` et les fichiers à la racine pour les services, utilitaires et scénarios transverses.

## Organisation

- `conftest.py` : fixtures partagées (client Flask, `mock_redis`, configuration de test).
- `tests/routes/` : intégration des blueprints (`api_ingress`, dashboard, etc.).
- `tests/email_processing/` : fenêtres de livraison, routage et orchestration.
- `test_services.py`, `test_r2_transfer_service.py`, `test_routing_rules_service.py` : services.
- `test_utils_*.py` : helpers de temps, texte et validation.
- `test_backfill_recadrage.py` : outil de backfill 30 jours.
- `test_app_render.py` (racine) : tests historiques de l'application Flask.

## Exécution rapide

```bash
# Tous les tests
pytest

# Un fichier
pytest tests/test_services.py -v

# Par marqueur
pytest -m "redis or r2 or resilience"
pytest -m unit
```

La couverture est générée automatiquement par `pytest-cov` (configuration dans `.coveragerc`). Les marqueurs et le timeout de 30 s sont définis dans `pytest.ini`.

## Documentation complète

Voir `docs/core/configuration-reference.md` pour les variables d'environnement nécessaires et `AGENTS.md` pour les conventions de test (blocs Given/When/Then, cas d'échec, `fakeredis`).
