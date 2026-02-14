---
name: Redis Config Guardian
description: Inspect and reconcile Redis-stored configs (processing_prefs, routing_rules, webhook_config, magic_link_tokens) using the approved scripts, APIs, and dashboard flows. Trigger when validating config drift, migrations, or debugging persistence issues.
globs: 
  - "**/app_config_store.py"
  - "config/*.py"
alwaysApply: false
---

# Redis Config Guardian

## Objectif
Garantir que les quatre configurations critiques stockées dans Redis restent cohérentes avec leurs fallbacks fichiers et l'état attendu du dashboard.

## Pré-requis
- `.env` chargé pour pointer sur le même Redis que l'application.
- Virtualenv `/mnt/venv_ext4/venv_render_signal_server` disponible.
- Accès aux fichiers `debug/*.json` (fallbacks).

## Workflow rapide
1. **Préparer l'environnement**
   - Charger `.env` local.
   - Utiliser l'environnement `/mnt/venv_ext4/venv_render_signal_server` si disponible.
2. **Audit complet**
   - Lancer le helper `./.windsurf/skills/redis-config-guardian/audit_redis_configs.sh`.
   - Le script inspecte les 4 clés et compare avec les fichiers `debug/*.json`.
3. **Inspection CLI**
   - Exécuter `python -m scripts.check_config_store --keys <liste> [--raw]`.
   - Vérifier `status`, `message` et `summary` pour chaque clé.
4. **API Dashboard**
   - Endpoint `POST /api/verify_config_store` via client authentifié pour exposer les mêmes diagnostics.
   - Activer l'option `includeRawJson` uniquement pour le débogage.
5. **Remédiation**
   - Diff Redis ↔ `debug/*.json` avec `app_config_store` (utiliser `set_config_json` via shell Python ou API dédiée).
   - Relancer `/api/verify_config_store` jusqu'à obtenir `OK` partout.
6. **Traçabilité**
   - Noter les corrections dans la Memory Bank (progress + decision) si l'écart était significatif.

## Ressources
- `audit_redis_configs.sh` : active le venv, inspecte les 4 clés, et compare avec les fallbacks fichiers.

## Bonnes pratiques
- Ne jamais éditer les fichiers `debug/*.json` pendant que l'app tourne. Passer par `app_config_store`.
- En cas d'erreur `INVALID`: capturer `message`, vérifier `_updated_at` et reconstruire la structure attendue (voir schémas dans `config/*.py`).
- Ajouter un test ciblé si l'écart provenait d'une évolution de schéma.
