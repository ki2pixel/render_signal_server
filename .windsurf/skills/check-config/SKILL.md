---
name: check-config
description: Vérifie l'état du Config Store (Redis/Fichier) via les scripts utilitaires.
---

# Check Config Store

Utilise ce skill pour diagnostiquer des problèmes de configuration ou vérifier la persistance.

## Actions
1. Active l'environnement virtuel standard :
   ```bash
   source /mnt/venv_ext4/venv_render_signal_server/bin/activate
   ```
2. Exécute la commande canonique :
   ```bash
   python -m scripts.check_config_store
   ```
3. Ajoute les options nécessaires (`--key`, `--raw`, etc.) selon le besoin tout en restant dans cet environnement.

## Contexte
L'application utilise un système hybride Redis-First avec fallback fichier JSON. Ce script permet de voir ce qui est réellement stocké.