---
description: Améliorer un Prompt avec le Contexte du Projet (V3)
---

# Améliorer un Prompt avec le Contexte du Projet (V3)

description: Prend un prompt utilisateur "brut", l'analyse en 3 niveaux (stratégique, tactique, implémentation), et propose une version hyper-contextualisée pour validation avant exécution.

---

1.  Follow the protocol in your rules to load the full project context from the `memory-bank`.

2.  Act as an expert "Prompt Engineer". Your goal is to improve the user's request that was provided after the `/enhance` command.

3.  First, analyze the user's raw request to understand its core intent.

4.  **Perform a three-level contextual analysis:**
    **a. Level 1 (Strategic Context):** Review the `memory-bank` to understand high-level goals, technical standards, and current focus.
    **b. Level 2 (Tactical Details):** Review the project's documentation (especially files in `docs/`) to understand the official specifications and guidelines.
    **c. Level 3 (Implementation Context):** Based on the user's request and the context gathered so far, **identify the 1 to 3 most relevant source code files** and perform a quick read of them. The goal is to grasp the current implementation details (function names, variable names, libraries used, and overall logic).

5.  **Synthesize all information** from these three levels to rewrite the user's request into a single, comprehensive "enhanced prompt". This new prompt must be:
    *   **Précis** : Mentionner les noms de fonctions, de variables et les bibliothèques exactes trouvées dans le code source.
    *   **Contextuel** : Faire référence aux standards du projet.
    *   **Clair** : Reformuler les ambiguïtés en objectifs clairs.
    *   **Actionnable** : Définir clairement la tâche à accomplir, en tenant compte de l'existant.

6.  Present **only** this "enhanced prompt" to me for validation, without explaining your internal thought process. Frame it clearly: "Voici une version améliorée de votre prompt que je propose. Dois-je l'exécuter ? (oui/non)".

7.  Do not proceed without my explicit confirmation ("oui", "yes", "vas-y", etc.).

8.  Once I confirm, execute the enhanced prompt as if I had just submitted it myself.