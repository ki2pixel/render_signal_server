---
name: run-tests
description: Exécute la suite de tests (unitaires, résilience, couverture) en utilisant l'environnement virtuel spécifique du projet.
---

# Run Tests

Utilise ce skill pour lancer les tests du projet `render_signal_server`.

## Usage

L'IA doit exécuter le script `run_tests.sh` fourni dans ce dossier.
Il active l'environnement virtuel `/mnt/venv_ext4/venv_render_signal_server` avant de lancer `pytest`.

## Options

- Si l'utilisateur demande "tous les tests", lance la commande par défaut (coverage inclus).
- Si l'utilisateur demande des "tests de résilience", utilise le marqueur `-m "redis or r2 or resilience"`.