---
name: end
description: end workflow migrated from Windsurf as executable prompt
invokable: true
---

## Workflow /end — Terminer la Session et Synchroniser la Memory Bank

1. **Initialisation obligatoire**  
   - Suivre le protocole général des règles.  
   - Utiliser `read_text_file` ou `read_multiple_files` pour charger successivement `memory-bank/productContext.md`, `memory-bank/activeContext.md`, `memory-bank/systemPatterns.md`, `memory-bank/decisionLog.md` et `memory-bank/progress.md`.

2. **Commande UMB**  
   - Exécuter la commande UMB comme décrit dans les règles.  
   - Pour toute lecture supplémentaire liée à la session, continuer à utiliser `read_text_file`.  
   - Pour localiser du contexte additionnel hors memory-bank, employer `search` ou `advanced-search` avant d'inspecter un fichier spécifique avec `read_text_file`.

3. **Synthèse des tâches de la session**  
   - Relire `memory-bank/progress.md` via `read_text_file` pour identifier les tâches terminées pendant la session.

4. **Mise à jour finale de progress.md**  
   - Utiliser `edit_file` pour déplacer les tâches vers la section "Terminé" avec un nouveau timestamp et s'assurer que "En cours" est défini sur "Aucune tâche active".

5. **Réinitialisation d'activeContext.md**  
  - Employer `edit_file` pour remettre le contenu à l'état neutre décrit dans les règles.

6. **Confirmation**  
  - Après vérification finale des fichiers mis à jour avec `read_text_file`, confirmer que la Memory Bank est synchronisée et que vous êtes prêt pour la prochaine session.