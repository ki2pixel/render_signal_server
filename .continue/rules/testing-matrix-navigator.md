---
name: Testing Matrix Navigator
description: Guide for selecting and executing the correct pytest suites (unit, redis, r2, resilience) with environment setup and coverage expectations.
alwaysApply: false
---

# Testing Matrix Navigator

Utilise cette compétence pour planifier et exécuter les tests pertinents après une modification.

## Pré-requis
- Virtualenv `/mnt/venv_ext4/venv_render_signal_server` activé.
- Variables ENV exportées (`FLASK_SECRET_KEY`, etc.) via `.env`.
- Accès aux marqueurs Pytest (`redis`, `r2`, `resilience`, `unit`, `slow`).

## Matrice de décision
| Contexte | Commande helper | Description |
| --- | --- | --- |
| Modifications backend générales | `./run_tests.sh -u` | Tests unitaires sans dépendances externes |
| Config/Redis | `./run_tests.sh -i -c` | Tests d'intégration + couverture store |
| R2 / Webhooks | `./run_tests.sh -i -c` | Tests d'intégration + couverture service |
| Poller / Résilience | `./run_tests.sh -i -c` | Tests d'intégration + couverture |
| Tests ciblés routing rules | `./run_tests.sh -n -c` | Nouveaux tests avec couverture |
| Full suite | `./run_tests.sh -a -c` | Tous les tests avec couverture |

## Workflow
1. **Préparer l'environnement**
   - Activer `/mnt/venv_ext4/venv_render_signal_server`.
   - Exporter les variables requises via `.env`.
2. **Sélectionner la suite**
   - Utiliser `./run_tests.sh` avec les options appropriées.
   - Pour un diff large, exécuter `pytest --maxfail=1 --disable-warnings` d'abord, puis `pytest --cov=.`.
3. **Commandes avancées**
   - Tests ciblés : `pytest tests/routes/test_api_routing_rules.py`
   - Scénarios spécifiques : `pytest tests/email_processing/test_routing_rules_orchestrator.py -k stop_processing`
   - Durées : `pytest --durations=20`
4. **Analyse des résultats**
   - Corriger immédiatement les échecs introduits.
   - Si une suite est flaky, documenter dans la Memory Bank avec étapes de reproduction.
5. **Rapports**
   - Pour la CI, viser couverture ≥70% (88 cols, black/isort conformes).

## Ressources
- `run_tests.sh` : script principal à la racine qui active le venv et exécute les suites demandées (unit, integration, e2e, fast, coverage).

## Conseils
- Grouper les tests par dossier modifié pour diagnostiquer plus vite.
- Relire `pytest.ini` pour les options par défaut (plugins, markers).
- Ajouter des tests Given/When/Then lors de nouvelles fonctionnalités.
