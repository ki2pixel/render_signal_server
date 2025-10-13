---
description: Terminer la Session et Synchroniser la Memory Bank
---

# Terminer la Session et Synchroniser la Memory Bank

description: Analyse la conversation de la session actuelle, met à jour la Memory Bank de manière exhaustive, puis nettoie le contexte actif pour la prochaine session.

---

1.  Follow the protocol in your rules.
2.  Now, execute the "UMB" (Update Memory Bank) command as defined in the rules. This involves halting the current task, acknowledging the update, and thoroughly reviewing the entire chat history of this session to synchronize all core memory bank files (`productContext.md`, `activeContext.md`, `systemPatterns.md`, `decisionLog.md`, `progress.md`).
3.  Based on the final state of `progress.md`, summarize the tasks that were completed during this session.
4.  Update the `progress.md` file one last time: move the completed tasks to the "Terminé" section with a new timestamp, and set the "En cours" section to "Aucune tâche active."
5.  Finally, reset the `activeContext.md` file to its neutral, "waiting" state for the next session. Respond with a confirmation message that the memory bank is synchronized and you are ready for the next session.