---
description: Améliorer un Prompt avec le Contexte du Projet (V3)
---

## Workflow /enhance — Améliorer un Prompt avec le Contexte du Projet

1. **Chargement du contexte**  
   - Utiliser `read_file` pour charger tous les fichiers requis du `memory-bank/` conformément au protocole.

2. **Analyse du prompt brut**  
   - Examiner la requête utilisateur et clarifier l'intention (aucun outil particulier requis ici).

3. **Analyse contextuelle à trois niveaux**  
   - **Niveau stratégique** : continuer à utiliser `read_file` pour approfondir les fichiers de la memory bank pertinents.  
   - **Niveau tactique** : parcourir la documentation sous `docs/` en combinant `code_search` (pour identifier les fichiers/documents pertinents) puis `read_file` pour les consulter.  
   - **Niveau implémentation** :  
     1. Utiliser `code_search` (ou `grep_search` si le symbole est connu) pour identifier les 1 à 3 fichiers les plus pertinents.  
     2. Ouvrir ces fichiers avec `read_file` pour collecter les noms de fonctions, variables et bibliothèques nécessaires.

4. **Synthèse du prompt amélioré**  
   - Rédiger le nouveau prompt en citant explicitement les éléments identifiés. (Si une modification de fichier est requise pour documenter la synthèse, utiliser `edit`/`multi_edit`.)

5. **Validation utilisateur**  
   - Présenter uniquement le prompt amélioré avec la formulation imposée.

6. **Exécution après validation**  
   - Une fois la confirmation reçue, suivre les règles générales en continuant d'utiliser `code_search`, `read_file`, `edit`/`multi_edit` (et `grep_search` au besoin) pour mettre en œuvre les actions demandées.