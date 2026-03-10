---
name: run-tests
description: Exécute la suite de tests (unitaires, intégration, couverture) en utilisant l'environnement virtuel spécifique du projet.
---

# Run Tests

Utilise ce skill pour lancer les tests du projet `render_signal_server`.

## Usage recommandé

- Préférer le runner officiel à la racine :
  ```bash
  ./run_tests.sh [options]
  ```
  Ce script active le venv `/mnt/venv_ext4/venv_render_signal_server`, expose les options (`-u/--unit`, `-i/--integration`, `-f/--fast`, `-c/--coverage`, etc.) et prend en charge la couverture HTML.
- Exemples courants :
  - Tous les tests + couverture : `./run_tests.sh -a -c`
  - Tests unitaires rapides : `./run_tests.sh -u`
  - Tests d'intégration avec couverture : `./run_tests.sh -i -c`
  - Tests ciblés : `./run_tests.sh -n -u` pour n'exécuter que les nouveaux fichiers en mode unitaire.

## Raccourci local

- Le helper `./.cline/skills/run-tests/run_tests.sh` est un helper legacy minimal qui exécute `pytest --cov=.`. Préférez `./run_tests.sh` à la racine pour bénéficier des options réelles du projet.