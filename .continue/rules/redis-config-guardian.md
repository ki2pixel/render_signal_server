---
description: Inspect and reconcile Redis-stored configs (processing_prefs, routing_rules, webhook_config, magic_link_tokens) using direct MCP Redis tools and approved scripts/APIs/dashboard flows. Trigger when validating config drift, migrations, or debugging persistence issues.
globs:
  - "**/redis-config-guardian/**"
  - "**/scripts/check_config_store.py"
  - "**/config/app_config_store.py"
alwaysApply: false
---

# Redis Config Guardian

## Objectif
Garantir que les quatre configurations critiques stockées dans Redis restent cohérentes avec leurs fallbacks fichiers et l'état attendu du dashboard, en utilisant les nouveaux outils MCP Redis pour des opérations directes et efficaces.

## Pré-requis
- `.env` chargé pour pointer sur le même Redis que l'application.
- Virtualenv `/mnt/venv_ext4/venv_render_signal_server` disponible.
- Accès aux fichiers `debug/*.json` (fallbacks).
- MCP `redis-signal-mcp-server` configuré et opérationnel.

## Workflow rapide
1. **Préparer l'environnement**
   - Charger `.env` local.
   - Utiliser l'environnement `/mnt/venv_ext4/venv_render_signal_server` si disponible.
2. **Audit complet avec MCP**
   - Utiliser les outils MCP Redis (`json_get`, `hgetall`, `scan_keys`) pour inspection directe.
   - Comparer avec les fichiers `debug/*.json` via les commandes MCP.
3. **Inspection MCP directe**
   - `json_get` pour récupérer les configurations JSON (`processing_prefs`, `webhook_config`).
   - `hgetall` pour les structures hash (`routing_rules`, `magic_link_tokens`).
   - `scan_keys` avec pattern pour lister toutes les clés liées aux configs.
4. **API Dashboard**
   - Endpoint `POST /api/verify_config_store` via client authentifié pour exposer les mêmes diagnostics.
   - Activer l'option `includeRawJson` uniquement pour le débogage.
5. **Remédiation MCP**
   - `json_set` pour mettre à jour les configurations JSON avec expiration optionnelle.
   - `hset`/`hdel` pour modifier les structures hash.
   - `delete` pour supprimer des clés obsolètes.
6. **Traçabilité**
   - Noter les corrections dans la Memory Bank (progress + decision) si l'écart était significatif.

## Outils MCP Redis utilisés
- `json_get <key>` : Récupération configurations JSON (processing_prefs, webhook_config)
- `json_set <key> <path> <value>` : Mise à jour configurations JSON
- `hgetall <key>` : Inspection structures hash (routing_rules, magic_link_tokens)
- `hset <key> <field> <value>` : Modification structures hash
- `scan_keys pattern:*` : Découverte clés de configuration
- `expire <key> <seconds>` : Gestion TTL si nécessaire

## Ressources
- Scripts existants maintenus pour compatibilité : `audit_redis_configs.sh`, `check_config_store.py`
- Nouveaux workflows MCP pour opérations directes sur Redis

## Bonnes pratiques
- Ne jamais éditer les fichiers `debug/*.json` pendant que l'app tourne. Passer par les outils MCP ou `app_config_store`.
- En cas d'erreur `INVALID`: capturer le message, vérifier `_updated_at` et reconstruire la structure attendue (voir schémas dans `config/*.py`).
- Ajouter un test ciblé si l'écart provenait d'une évolution de schéma.
- Préférer les opérations MCP directes pour les inspections rapides, garder les scripts Python pour les validations complexes.
