---
trigger: always_on
description: 
globs: 
---

memory_system_rules:
  primary_system: "memory-bank"
  
initialization:
  trigger: "first_interaction"
  priority: "immediate"
  required: true
  actions:
    - "Before doing ANYTHING else, read and fully internalize ALL rules in this file."
    - "Check if memory-bank/ directory exists."
    - "If memory-bank exists: Read all core files (productContext.md, activeContext.md, systemPatterns.md, decisionLog.md, progress.md). Set status to [MEMORY BANK: ACTIVE]."
    - "If memory-bank does NOT exist: Inform user. Ask to create and provide yes and no response choices. If yes, create directory and core files with basic structure and populate files with initial content, based upon any available information. If no, set status to [MEMORY BANK: INACTIVE]."
    - "Load context from memory-bank files if active."
    - "Proceed with task or if no task is given, suggest 2-4 tasks based upon memory-bank/ content."

  validation:
    - "Verify memory-bank status (ACTIVE/INACTIVE)."
    - "If ACTIVE, confirm core files were read."

system_validation:
  startup:
    - "Verify .windsurfrules loaded"
    - "Check memory-bank accessibility if expected"
    - "Confirm initialization sequence complete"

memory_bank:
  core_files:
    activeContext.md:
      purpose: "Track session state and goals (objectives, decisions, questions, blockers)"
    productContext.md:
      purpose: "Define project scope (overview, components, organization, standards)"
    progress.md:
      purpose: "Track work status (completed, current, next, issues)"
    decisionLog.md:
      purpose: "Record decisions (technical, architecture, implementation, alternatives)"
    systemPatterns.md: # Optional but recommended
      purpose: "Document recurring patterns and standards (coding, architecture, testing)"
  file_handling:
    read_all_at_startup: true # Implied by initialization actions
    build_complete_context: true # Implied by initialization actions

general:
  status_prefix: "Begin EVERY response with either '[MEMORY BANK: ACTIVE]' or '[MEMORY BANK: INACTIVE]', according to the current state of the Memory Bank."

memory_bank_updates:
  frequency: "UPDATE MEMORY BANK THROUGHOUT THE CHAT SESSION, WHEN SIGNIFICANT CHANGES OCCUR IN THE PROJECT. Use judgment to determine significance."
  decisionLog.md:
    trigger: "When a significant architectural decision is made (new component, data flow change, technology choice, etc.)."
    action: "Append new information (decision, rationale, implications) using insert_content. Never overwrite. Include timestamp."
    format: "[YYYY-MM-DD HH:MM:SS] - [Summary of Decision]"
  productContext.md:
    trigger: "When the high-level project description, goals, features, or overall architecture changes significantly."
    action: "Append new information or modify existing entries using insert_content or apply_diff. Append timestamp and summary as footnote."
    format: "[YYYY-MM-DD HH:MM:SS] - [Summary of Change]"
  systemPatterns.md:
    trigger: "When new architectural patterns are introduced or existing ones are modified."
    action: "Append new patterns or modify existing entries using insert_content or apply_diff. Include timestamp."
    format: "[YYYY-MM-DD HH:MM:SS] - [Description of Pattern/Change]"
  activeContext.md:
    trigger: "When the current focus of work changes, or when significant progress is made."
    action: "Append to the relevant section (Current Focus, Recent Changes, Open Questions/Issues) or modify existing entries using insert_content or apply_diff. Include timestamp."
    format: "[YYYY-MM-DD HH:MM:SS] - [Summary of Change/Focus/Issue]"
  progress.md:
    trigger: "When a task begins, is completed, or its status changes."
    action: "Append the new entry using insert_content. Never overwrite. Include timestamp."
    format: "[YYYY-MM-DD HH:MM:SS] - [Summary of Progress Update]"

archive_policy:
  trigger: "When decisionLog.md or progress.md exceed 90 days d'historique actif OU deviennent difficilement lisibles (>~500 lignes)."
  retention: "Les fichiers principaux ne doivent conserver que les entrées des 90 derniers jours. L'historique complet est archivé par trimestre."
  actions:
    - "Créer (si absent) le dossier `memory-bank/archive/` et un fichier trimestriel (ex: decisionLog_2025Q4.md, progress_2025Q4.md)."
    - "Déplacer les entrées plus anciennes que la période active vers le fichier d'archive correspondant (copier les sections puis les supprimer du fichier principal)."
    - "Ajouter/mettre à jour dans les fichiers principaux une section `Archives disponibles` listant les fichiers d'archives pertinents."
    - "Ajouter/mettre à jour une section `Highlights <période>` résumant les décisions clés conservées."
    - "Documenter la politique d'archivage et la date d'application dans decisionLog.md/progress.md."
    - "Mettre à jour la documentation ou les références (docs/refactoring-roadmap.md, docs/refactoring-conformity-report.md, etc.) qui pointent vers ces fichiers."

umb: # Update Memory Bank command
  trigger: "^(Update Memory Bank|UMB)$"
  instructions:
    - "Halt Current Task: Stop current activity."
    - "Acknowledge Command: Respond with '[MEMORY BANK: UPDATING]'."
    - "Review Chat History: Analyze the complete current chat session."
  core_update_process: |
      1. Current Session Review: Analyze chat history for relevant decisions, context changes, progress updates, clarifications etc.
      2. Comprehensive Updates: Update relevant memory bank files based on the review, following the rules defined in 'memory_bank_updates'.
      3. Memory Bank Synchronization: Ensure consistency across updated files.

  task_focus: "During UMB, focus ONLY on capturing information explicitly present in the *current chat session* (clarifications, decisions, progress). Do NOT summarize the entire project or perform actions outside this scope."
  cross_mode_updates: "Capture relevant information from the chat session irrespective of conceptual 'modes' mentioned, adding it to the appropriate Memory Bank files."
  
  post_umb_actions:
    - "State: Memory Bank fully synchronized based on current chat session."
    - "State: Session context preserved for continuation."

documentation_context:
  trigger: "When the user's prompt explicitly asks a question about the project's 'documentation', 'docs', "doc", 'guide', 'guidelines', 'API reference', or how a specific feature is documented."
  instructions:
    - "Acknowledge that the user is asking a question specifically about the project's own documentation."
    - "Before answering, state clearly: 'I will consult the project's internal documentation to answer your question.'"
    - "Prioritize reading and analyzing the content of all files located in the `docs/` and `deployment/`. Pay special attention to README.md, architecture.md, api.md, configuration.md, email_polling.md, and installation.md to formulate a comprehensive answer."
    - "Formulate your answer based *primarily* on the information found in these documentation files."
    - "If the documentation and the code seem to conflict, mention the conflict and ask the user for clarification, citing both sources."

coding_and_architecture_context:
  trigger: "When the user's prompt asks to generate, modify, refactor, or create code, or asks an architectural question. Keywords: create, write, implement, change, update, fix, debug, refactor, class, function, script, service, route, component, style, test, architecture, créer, crée, écrire, écris, implémenter, implémente, changer, change, modifier, modifie, mettre à jour, mets à jour, actualiser, actualise, corriger, corrige, réparer, répare, résoudre, résous, déboguer, débogue, refactoriser, refactorise, classe, fonction, composant, tester, teste"
  instructions:
    - "Acknowledge that the user's request involves writing or changing code or discussing architecture."
    - "Before generating any code, state clearly: 'I will adhere to the project's mandatory architectural and coding standards.'"
    - "Prioritize reading and fully internalizing the content of the `.windsurf/rules/codingstandards.md` file. This file contains MANDATORY rules."
    - "Formulate your code, explanation, and implementation plan based *strictly* on the principles found in `codingstandards.md`."
    - "If the user's request seems to conflict with a rule in `codingstandards.md`, you MUST state the conflict, explain the rule from the document, and ask for clarification before proceeding."