---
description: Generate Repomix bundle for LLM analysis
---

# /repomix-bundle — Générer le bundle Repomix

## Objectif
Créer un bundle optimisé du codebase pour analyse par LLMs externes (Claude, ChatGPT, etc.) en utilisant Repomix avec la configuration existante.

## Étapes

1. **Vérification de la configuration**
   - Confirmer que `repomix.config.json` existe et est à jour
   - Vérifier les patterns d'inclusion/exclusion

2. **Génération du bundle**
   // turbo
   ```bash
   npx repomix --config repomix.config.json
   ```

3. **Vérification du résultat**
   - Contrôler que `repomix-output.md` a été généré
   - Vérifier la taille et le compte de tokens
   - Valider que les fichiers critiques sont inclus

## Tools Used

- `read_text_file` - To read repomix configuration
- `run_command` - To execute repomix generation
- `list_directory` - To check output files
- `search_files` - To verify critical files are included in bundle

## Technical Lockdown
Utilisez les outils fast-filesystem (mcp0_fast_*) pour accéder aux fichiers memory-bank avec des chemins absolus.
- Windsurf is now in 'Token-Saver' mode. Minimize context usage by using tools instead of pre-loading.