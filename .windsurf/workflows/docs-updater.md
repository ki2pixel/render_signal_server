---
description: Analyse la Memory Bank, inspecte le code source impacté, et met à jour TOUTE la documentation associée.
---

## Rappel outils obligatoires (section 2.1 Basic Tools)
- **`read_file`**: Always read related files before making changes. For large files, be mindful to read only the necessary range.
- **`edit` / `multi_edit`**: Primary means for code changes.  
  - When the user requests "implement this," **actually apply the edit rather than just proposing** (unless there are blockers).
  - Keep each edit to a semantically coherent unit of change.
- **`grep_search` / `code_search`**:
  - Use `grep_search` for locating strings and symbols.
  - Use `code_search` for exploring implementation meaning and patterns.

actions:
  # ÉTAPE 1 : Extraire le résumé des changements récents depuis la Memory Bank.
  - tool: memory_bank_reader
    description: "Lire les fichiers de la `memory-bank` pour extraire un résumé des changements les plus récents."
    input:
      context_files:
        - "progress.md"
        - "decisionLog.md"
        - "productContext.md"
        - "systemPatterns.md"
    output: RECENT_CHANGES_SUMMARY

  # ÉTAPE 2 : Lister les fichiers de documentation pour connaître la structure actuelle.
  - tool: file_lister
    description: "Lister tous les fichiers et sous-dossiers du répertoire /docs pour refléter l’arborescence thématique."
    input: "./docs"
    output: DOCS_FILE_STRUCTURE

  # Directive outils : après cette étape, exécuter systématiquement `code_search` pour localiser les portions de code à analyser,
  # enchaîner avec `read_file` pour lire les extraits visés (plage limitée si >1000 lignes), utiliser `grep_search` pour cibler
  # des symboles précis, puis appliquer les corrections via `edit`/`multi_edit` par unités cohérentes.

  # ÉTAPE 3 (HYPOTHÈSE) : L'IA identifie les fichiers de code source pertinents à inspecter.
  - tool: ai_impact_assessor
    description: "À partir du résumé des changements, déduire une liste de fichiers de code source à inspecter pour vérification."
    prompt: |
      En tant qu'architecte logiciel, analyse le résumé des changements récents ci-dessous.
      Ton unique objectif est de déduire et de lister les fichiers de code source (ex: .py, .js) qui ont probablement été modifiés pour implémenter ces changements.
      Ne donne aucune explication. Réponds uniquement avec une liste de chemins de fichiers au format JSON.

      Exemple de réponse :
      ["app_render.py", "static/remote/api.js", "login.html"]

      ---
      **RÉSUMÉ DES CHANGEMENTS RÉCENTS :**
      ```
      {{ RECENT_CHANGES_SUMMARY }}
      ```
    output: IMPACTED_FILES_LIST

  # ÉTAPE 4 (COLLECTE) : Lire le contenu des fichiers de code source identifiés.
  - tool: file_reader
    description: "Lire et concaténer le contenu des fichiers de code source spécifiés."
    input:
      files: "{{ IMPACTED_FILES_LIST }}"
    output: IMPACTED_FILES_CONTENT

  # ÉTAPE 5 (SYNTHÈSE) : L'IA croise toutes les informations pour générer les suggestions finales.
  - tool: ai_doc_analyzer_final
    description: "Analyser le résumé des changements, le contenu du code source et la structure des documents pour proposer des mises à jour complètes."
    prompt: |
      En tant qu'architecte technique méticuleux, ta mission finale est de garantir la parfaite cohérence entre les évolutions du projet et sa documentation.

      Tu disposes de trois sources d'information cruciales :
      1.  **LE POURQUOI (Résumé des changements)** : Le contexte de haut niveau expliquant les modifications récentes.
      2.  **LE QUOI (Contenu du code source)** : Le code des fichiers qui ont été identifiés comme impactés.
      3.  **L'EXISTANT (Structure de la documentation)** : La liste des fichiers de documentation actuels.

      Ton processus de raisonnement doit être le suivant :
      1.  **Analyse le contenu du code source (`IMPACTED_FILES_CONTENT`)** pour identifier les changements concrets : fonctions ajoutées/modifiées, paramètres changés, logique métier altérée.
      2.  **Mets en relation ces changements concrets avec le résumé de haut niveau (`RECENT_CHANGES_SUMMARY`)**. Cela te permet de comprendre l'intention derrière chaque modification de code.
      3.  **Compare ces informations avec la structure de la documentation (`DOCS_FILE_STRUCTURE`)**. Identifie précisément les documents dans `/docs` qui sont maintenant obsolètes ou incomplets.
      4.  **Vérifie les docstrings** dans le code fourni. Sont-elles toujours alignées avec la signature et le comportement des fonctions ?
      5.  **Rédige des suggestions précises et actionnables**. Pour chaque incohérence, propose une mise à jour claire. Fais référence aux fonctions ou aux fichiers spécifiques si nécessaire.

      Présente tes conclusions finales sous forme de liste à puces.

      ---
      **1. RÉSUMÉ DES CHANGEMENTS (LE POURQUOI) :**
      ```
      {{ RECENT_CHANGES_SUMMARY }}
      ```

      **2. CONTENU DU CODE SOURCE IMPACTÉ (LE QUOI) :**
      ```
      {{ IMPACTED_FILES_CONTENT }}
      ```

      **3. STRUCTURE DE LA DOCUMENTATION (L'EXISTANT) :**
      ```
      {{ DOCS_FILE_STRUCTURE }}
      ```
    output: COMPREHENSIVE_DOCS_SUGGESTIONS

  # ÉTAPE 6 : Afficher le résultat final.
  - tool: github_commenter
    description: "Présenter les suggestions de mise à jour de la documentation."
    prompt: |
      ## 📚 Assistant de Documentation (Analyse Complète) 📚

      Après avoir analysé les dernières décisions de la Memory Bank et inspecté le code source concerné, voici mes suggestions pour garder toute la documentation synchronisée :

      {{ COMPREHENSIVE_DOCS_SUGGESTIONS }}

      ---
      *Ces suggestions sont basées à la fois sur le contexte du projet et sur le contenu réel du code. Veuillez les examiner pour assurer la cohérence globale.*
      *Mentionner explicitement les sous-dossiers architecture/, operations/, features/, configuration/, quality/, integrations/, archive/ si certaines mises à jour s’y appliquent.*

notes:
  - "Toujours inclure dans la réponse finale le diff complet ou la version intégrale corrigée de chaque fichier modifié afin que l’utilisateur puisse appliquer les changements manuellement."