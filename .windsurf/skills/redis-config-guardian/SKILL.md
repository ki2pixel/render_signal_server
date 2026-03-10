---
name: redis-config-guardian
description: Inspect and reconcile Redis-stored configs (processing_prefs, routing_rules, webhook_config, magic_link_tokens) using direct MCP Redis tools and approved scripts/APIs/dashboard flows. Trigger when validating config drift, migrations, or debugging persistence issues.
---

# Redis Config Guardian

## Objectif
Garantir que les configurations critiques stockées dans Redis restent cohérentes avec leurs fallbacks fichiers et l'état attendu du dashboard, en tenant compte du mode réel du projet : JSON sérialisé dans des clés string Redis via `config/app_config_store.py`.

## Pré-requis
- `.env` chargé pour pointer sur le même Redis que l'application.
- Virtualenv `/mnt/venv_ext4/venv_render_signal_server` disponible.
- Accès aux fichiers `debug/*.json` (fallbacks).
- MCP `redis-signal-mcp-server` configuré et opérationnel.
- Compréhension du préfixe de clés Redis `CONFIG_STORE_REDIS_PREFIX` (par défaut `r:ss:config:`).

## Workflow rapide
1. **Préparer l'environnement**
   - Charger `.env` local.
   - Utiliser l'environnement `/mnt/venv_ext4/venv_render_signal_server` si disponible.
2. **Audit complet avec MCP**
   - Utiliser les outils MCP Redis (`scan_keys`, `get`, éventuellement `set`) pour inspection directe des clés string contenant du JSON.
   - Comparer avec les fichiers `debug/*.json` et le résultat de `scripts/check_config_store.py`.
3. **Inspection MCP directe**
   - `scan_keys` avec le pattern du préfixe de config pour lister les clés persistées.
   - `get` pour récupérer les payloads JSON sérialisés (`processing_prefs`, `webhook_config`, `routing_rules`, `magic_link_tokens`, `runtime_flags`).
   - Parser le JSON retourné avant comparaison avec les fallbacks fichiers et les schémas attendus.
4. **API Dashboard**
   - Endpoint `POST /api/verify_config_store` via client authentifié pour exposer les mêmes diagnostics.
   - Activer l'option `raw` uniquement pour le débogage.
5. **Remédiation MCP**
   - `set` pour réécrire un payload JSON sérialisé lorsque la correction directe est justifiée.
   - `delete` pour supprimer des clés obsolètes.
   - Réserver `app_config_store.set_config_json()` ou les endpoints dashboard pour les corrections métier normales.
6. **Traçabilité**
   - Noter les corrections dans la Memory Bank (progress + decision) si l'écart était significatif.

## Outils MCP Redis utilisés
- `scan_keys pattern:*` : Découverte clés de configuration
- `get <key>` : Lecture des clés string Redis contenant du JSON sérialisé
- `set <key> <value>` : Réécriture ciblée d'un payload JSON si nécessaire
- `expire <key> <seconds>` : Gestion TTL si nécessaire

## Ressources
- Scripts existants maintenus pour compatibilité : `audit_redis_configs.sh`, `check_config_store.py`
- Workflows MCP pour inspection rapide des clés string Redis et comparaison avec `runtime_flags`/`debug/*.json`

## Bonnes pratiques
- Ne jamais éditer les fichiers `debug/*.json` pendant que l'app tourne. Passer par les outils MCP ou `app_config_store`.
- En cas d'erreur `INVALID`: capturer le message, vérifier `_updated_at` et reconstruire la structure attendue (voir schémas dans `config/*.py`).
- Ajouter un test ciblé si l'écart provenait d'une évolution de schéma.
- Préférer les opérations MCP directes pour les inspections rapides, garder les scripts Python pour les validations complexes.
