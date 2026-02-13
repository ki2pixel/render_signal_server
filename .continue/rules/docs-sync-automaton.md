---
description: Analyse la Memory Bank, inspecte le code source impacté, et met à jour TOUTE la documentation associée.
globs: 
  - "**/*.{py,js,md}"
alwaysApply: true
---

# Docs Sync Automaton

Skill à invoquer pour exécuter une mise à jour documentaire complète selon le workflow `/docs-updater`.

## Pré-requis
- Memory Bank à jour (`memory-bank/{activeContext,progress,decisionLog}.md`).
- Accès au repo pour exécuter `tree`, `cloc`, `radon`.
- Virtualenv `/mnt/venv_ext4/venv_render_signal_server` (pour les scripts d'audit).

## Workflow
1. **Collecte Contexte**
   - Lire `memory-bank/{activeContext,progress,decisionLog}.md`.
   - Identifier les fichiers impactés par la feature/bugfix.
2. **Audit Code**
   - Lancer le helper `./.windsurf/skills/docs-sync-automaton/run_docs_audit.sh`.
   - Noter les modules modifiés pour guider les docs.
3. **Plan Docs**
   - Associer chaque changement à un fichier dans `docs/` (access/, core/, ingestion/, ops/, processing/) ou README.
   - Prévoir les sections à mettre à jour (tables de services, workflows, API, UX, etc.).
4. **Écriture**
   - Utiliser un ton descriptif, mentionner les dates si pertinent.
   - Ajouter des ancres/table des matières pour les nouveaux fichiers.
5. **Validation**
   - Relire la cohérence (typos, liens, références croisées).
   - Mettre à jour la Memory Bank (progress + decision) pour tracer la doc.
6. **Tests / Commandes**
   - Si le workflow exige, exécuter `python scripts/docs/lint_links.py` (exemple) ou autre validation doc.

## Ressources
- `run_docs_audit.sh` : active le venv, exécute `tree -L 2`, `cloc docs/`, `radon cc app_render.py services routes`.

## Conseils
- Toujours citer les fichiers modifiés dans le récap final.
- Pour les guides longs, déplacer les détails dans `docs/processing/*` ou `docs/ops/*` et résumer dans `docs/README.md`.
- Synchroniser les captures JSON/ENV si de nouvelles variables sont introduites.
- La nouvelle structure docs utilise 5 dossiers : access/ (auth, UI), core/ (architecture, config), ingestion/ (gmail push, legacy IMAP), ops/ (déploiement, monitoring, dépannage), processing/ (offload R2, routing, webhooks).
