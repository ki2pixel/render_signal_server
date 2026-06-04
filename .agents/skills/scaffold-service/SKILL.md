---
name: scaffold-service
description: Génère un nouveau Service Python (Singleton) respectant l'architecture et les coding standards du projet.
---

# Scaffold Backend Service

Utilise ce skill lorsqu'il faut créer un nouveau service dans `services/`.

## Standards appliqués
1. **Singleton** : Utilisation de `_instance`, `_lock` et `get_instance`.
2. **Typage & Taille** : `from __future__ import annotations`, Type hints complets (ex: `-> Response` ou `-> tuple[Response, int]`). Les fonctions doivent faire moins de 40 lignes logiques.
3. **Logging** : Utilisation d'un logger injecté ou par défaut (centralisé dans `app_logging/`).
4. **Configuration** : Injection de `ConfigService` (env) et utilisation des fonctions de module `get_config_json` / `set_config_json` de `config.app_config_store` (Redis-first).
5. **Résilience** : Stratégie "Always Fallback" avec catch large aux frontières.

## Template
Utilise le fichier `service_template.py` comme base. Remplace `NewService` par le nom du service demandé (PascalCase) et adapte les docstrings.