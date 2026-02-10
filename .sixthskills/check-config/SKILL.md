---
name: check-config
description: Vérifie l'état du Config Store (Redis/Fichier) via les scripts utilitaires.
---

# Check Config Store

Utilise ce skill pour diagnostiquer des problèmes de configuration ou vérifier la persistance.

## Pré-requis
- `.env` chargé afin de pointer vers le même Redis que l'application.
- Virtualenv `/mnt/venv_ext4/venv_render_signal_server` disponible (les dépendances CLI y sont installées).
- Exécution depuis la racine du repo (les scripts de ce dossier supposent ce chemin).

## Workflow
1. **Activer l'environnement**
   ```bash
   source /mnt/venv_ext4/venv_render_signal_server/bin/activate
   ```
2. **Inspection rapide**
   ```bash
   ./.sixthskills/check-config/inspect_store.sh
   ```
   - Inspecte `processing_prefs`, `webhook_config`, `routing_rules`.
   - Adapter le script si d'autres clés doivent être surveillées.
3. **Analyse ciblée**
   ```bash
   python -m scripts.check_config_store --keys routing_rules --raw
   ```
   - `--keys` ∈ {`magic_link_tokens`, `routing_rules`, `processing_prefs`, `webhook_config`}.
   - `--raw` imprime le JSON indenté pour comparer aux schémas.
4. **API dashboard (optionnel)**
   - `POST /api/verify_config_store` via client authentifié avec `{ "keys": ["routing_rules"], "includeRawJson": true }` pour recouper avec l'UI.
5. **Remédiation**
   - Corriger via `app_config_store.set_config_json()` (shell Python) ou les endpoints POST correspondants.
   - Rejouer l'étape 2 jusqu'à obtenir `status: OK` pour chaque clé.
6. **Traçabilité**
   - Documenter tout drift significatif dans la Memory Bank (progress + decision) et, si nécessaire, dans la documentation.

## Ressources
- `inspect_store.sh` : helper standard (active le venv, inspecte les trois clés critiques).
- `scripts/check_config_store.py` : CLI principal (extensible pour nouvelles validations/clefs).

## Contexte
L'application utilise un système hybride Redis-first avec fallback JSON. Toujours passer par `app_config_store` pour écrire; ne jamais modifier `debug/*.json` pendant l'exécution.
